"""通用优先级打分引擎

基于 config.algorithm_parameters(category='scoring') 的配置执行优先级打分，
支持：
- Recon 首次无人侦察目标优先级
- 后续任务/通道/安置点/物资等统一打分

核心原则：
- 所有规则均来自数据库配置，代码中不写死权重
- 无Fallback：配置缺失时由 AlgorithmConfigService 抛错
- AI 残差仅作为受限维度参与，不能推翻硬规则
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, TypedDict

from pydantic import BaseModel, Field

from src.agents.rules.models import ConditionOperator
from src.infra.config.algorithm_config_service import AlgorithmConfigService


logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """打分对象类型枚举"""

    RISK_AREA = "risk_area"
    RECON_TARGET = "recon_target"
    TASK = "task"
    ROUTE = "route"
    SHELTER = "shelter"
    SUPPLY_REQUEST = "supply_request"


class ScoringContext(TypedDict, total=False):
    """通用打分上下文

    为了方便跨业务复用，这里只约定通用字段，具体含义由各业务 adapter 保证。
    """

    scenario_id: str
    event_id: Optional[str]
    entity_type: EntityType
    entity_id: Optional[str]
    features: Dict[str, Any]
    texts: List[str]
    tags: Dict[str, str]


class DimensionContribution(TypedDict, total=False):
    """单个维度的贡献明细"""

    weight: float
    raw_value: Optional[float]
    normalized_value: Optional[float]
    score: float


class PriorityScoringResult(TypedDict, total=False):
    """打分结果结构"""

    entity_id: Optional[str]
    entity_type: str
    score: float
    priority: str
    components: Dict[str, DimensionContribution]
    hard_rules_triggered: List[str]
    ai_residual: Optional[float]
    reasons: List[str]


class AiResidualProvider(Protocol):
    """AI 残差信号提供器接口

    为了在高并发场景下减少 LLM 调用次数，这里使用 batch 接口。
    """

    async def score_batch(
        self,
        contexts: List[ScoringContext],
        rule_code: str,
    ) -> Dict[str, float]:
        """返回每个 entity_id 对应的残差分数[-1.0, 1.0] 区间内。

        返回字典的 key 必须是 context.entity_id，未命中时视为 0。
        """


class TransformType(str, Enum):
    """数值变换类型

    用于描述非 AI 维度的归一化方向。
    """

    LINEAR = "linear"
    INVERT = "invert"


class ScoringDimension(BaseModel):
    """单个打分维度配置"""

    name: str = Field(..., description="维度名称")
    weight: float = Field(..., ge=0.0, le=1.0, description="维度权重")
    source: str = Field(..., description="取值路径，如 features.risk_level / ai.suggestion_score")
    scale: Optional[str] = Field(
        default=None,
        description="值域刻度，如 '0-10'，用于线性归一化",
    )
    normalize_by: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="按某个基数归一化，例如 per 10000 people",
    )
    max: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="最大值截断，用于避免异常值放大",
    )
    transform: TransformType = Field(
        default=TransformType.LINEAR,
        description="线性还是反向归一化",
    )
    clamp: Optional[List[float]] = Field(
        default=None,
        description="钳位区间[min, max]，AI残差等可用 [-0.2,0.2]",
    )


class HardRuleConditionExpr(BaseModel):
    """硬规则触发条件表达式"""

    field: str = Field(..., description="字段路径，如 features.risk_level")
    operator: ConditionOperator = Field(..., description="比较操作符")
    value: Any = Field(..., description="比较阈值")


class HardRuleConfig(BaseModel):
    """硬规则配置"""

    id: str = Field(..., description="硬规则ID，用于trace")
    condition: HardRuleConditionExpr = Field(..., alias="if", description="触发条件")
    set_priority: Optional[str] = Field(
        default=None,
        description="直接设置优先级（如 critical）",
    )
    floor_priority: Optional[str] = Field(
        default=None,
        description="设置优先级下限（如至少为 high）",
    )
    min_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="触发时强制最低分数",
    )

    class Config:
        allow_population_by_field_name = True


class PriorityBucket(BaseModel):
    """优先级区间配置"""

    name: str = Field(..., description="优先级名称：critical/high/medium/low")
    min_score: float = Field(..., ge=0.0, le=1.0, description="该优先级的最低分")


class ScoringRuleSet(BaseModel):
    """完整打分规则集"""

    entity_type: str = Field(..., description="适用的实体类型")
    dimensions: List[ScoringDimension] = Field(..., description="维度配置")
    hard_rules: List[HardRuleConfig] = Field(
        default_factory=list,
        description="硬规则列表",
    )
    priority_buckets: List[PriorityBucket] = Field(
        ..., description="优先级区间配置"
    )


@dataclass(slots=True)
class _ResolvedRuleSet:
    """内部缓存用的规则集封装"""

    rule_code: str
    config: ScoringRuleSet


class PriorityScoringEngine:
    """通用优先级打分引擎

    业务方只需：
    1. 将自己的领域对象转换为 ScoringContext
    2. 传入对应的 rule_code（如 SCORING_RECON_TARGET_V1）
    """

    def __init__(
        self,
        config_service: AlgorithmConfigService,
        ai_residual_provider: Optional[AiResidualProvider] = None,
    ) -> None:
        self._config_service = config_service
        self._ai = ai_residual_provider
        self._cache: Dict[str, _ResolvedRuleSet] = {}

    async def _load_ruleset(self, rule_code: str) -> _ResolvedRuleSet:
        """从config.algorithm_parameters加载并解析规则集"""

        cached = self._cache.get(rule_code)
        if cached is not None:
            return cached

        params = await self._config_service.get_or_raise(
            category="scoring",
            code=rule_code,
        )
        config = ScoringRuleSet.model_validate(params)
        ruleset = _ResolvedRuleSet(rule_code=rule_code, config=config)
        self._cache[rule_code] = ruleset
        logger.info(
            "加载scoring规则集完成",
            extra={
                "rule_code": rule_code,
                "dimensions": [d.name for d in config.dimensions],
                "hard_rules": [r.id for r in config.hard_rules],
            },
        )
        return ruleset

    async def score_many(
        self,
        contexts: List[ScoringContext],
        rule_code: str,
    ) -> List[PriorityScoringResult]:
        """批量打分接口

        Recon 等场景会一次性为多个目标打分，使用批量接口便于 AI 残差合并调用。
        """

        if not contexts:
            return []

        ruleset = await self._load_ruleset(rule_code)

        # 准备 AI 残差：仅当规则中显式声明了 ai 维度且注入了 provider
        ai_scores: Dict[str, float] = {}
        if self._ai and any(
            dim.source.startswith("ai.") for dim in ruleset.config.dimensions
        ):
            try:
                ai_scores = await self._ai.score_batch(contexts, rule_code)
            except Exception as e:  # noqa: BLE001
                # 为了稳健性，这里将AI残差视为可选增强信号，失败时打0分并记录日志
                logger.warning("AI残差计算失败，降级为0", extra={"error": str(e)})
                ai_scores = {}

        results: List[PriorityScoringResult] = []
        for ctx in contexts:
            entity_id = ctx.get("entity_id")
            residual = ai_scores.get(entity_id or "", 0.0)
            result = self._score_single(ctx, ruleset.config, residual)
            results.append(result)

        return results

    async def score(
        self,
        context: ScoringContext,
        rule_code: str,
    ) -> PriorityScoringResult:
        """单对象打分便捷接口"""

        results = await self.score_many([context], rule_code)
        return results[0]

    # ======================================================================
    # 内部实现
    # ======================================================================

    def _score_single(
        self,
        ctx: ScoringContext,
        config: ScoringRuleSet,
        ai_residual_value: float,
    ) -> PriorityScoringResult:
        features: Dict[str, Any] = ctx.get("features", {}) or {}
        tags: Dict[str, str] = ctx.get("tags", {}) or {}

        # AI 特征容器
        ai_context = {"suggestion_score": ai_residual_value}

        # 统一的数据视图，供路径解析使用
        data_root: Dict[str, Any] = {
            "features": features,
            "tags": tags,
            "ai": ai_context,
        }

        components: Dict[str, DimensionContribution] = {}
        hard_triggered: List[str] = []
        reasons: List[str] = []

        # 先评估硬规则（只读 features/tags/ai，不修改分数）
        forced_priority: Optional[str] = None
        floor_priority: Optional[str] = None
        min_score_floor: Optional[float] = None

        for rule in config.hard_rules:
            if self._eval_condition(rule.condition, data_root):
                hard_triggered.append(rule.id)
                if rule.set_priority:
                    forced_priority = rule.set_priority
                if rule.floor_priority:
                    # 多条floor规则时取最高优先级
                    floor_priority = self._max_priority(floor_priority, rule.floor_priority)
                if rule.min_score is not None:
                    min_score_floor = max(min_score_floor or 0.0, rule.min_score)

        # 然后按维度线性加权
        total_score = 0.0
        ai_contribution: Optional[float] = None

        for dim in config.dimensions:
            raw = self._resolve_path(data_root, dim.source)

            # AI 维度：允许负贡献，例如 [-0.2, 0.2]
            if dim.source.startswith("ai."):
                value = self._to_float(raw)
                if dim.clamp and len(dim.clamp) == 2:
                    lo, hi = dim.clamp
                    value = max(min(value, hi), lo)
                normalized = value
                score = normalized * dim.weight
                ai_contribution = normalized
            else:
                normalized = self._normalize_dimension(dim, raw)
                score = normalized * dim.weight

            total_score += score
            components[dim.name] = DimensionContribution(
                weight=dim.weight,
                raw_value=self._to_float_or_none(raw),
                normalized_value=normalized,
                score=score,
            )

        # 应用硬规则的最低分约束
        if min_score_floor is not None and total_score < min_score_floor:
            reasons.append(
                f"score raised to hard-rule floor {min_score_floor:.3f} from {total_score:.3f}",
            )
            total_score = min_score_floor

        # 根据分数映射优先级
        bucket_priority = self._map_priority(total_score, config.priority_buckets)

        # 应用 floor_priority
        final_priority = bucket_priority
        if floor_priority:
            final_priority = self._max_priority(bucket_priority, floor_priority) or bucket_priority

        # 应用强制 priority
        if forced_priority:
            if forced_priority != bucket_priority:
                reasons.append(
                    f"priority overridden by hard rule from {bucket_priority} to {forced_priority}",
                )
            final_priority = forced_priority

        return PriorityScoringResult(
            entity_id=ctx.get("entity_id"),
            entity_type=(ctx.get("entity_type") or "unknown"),
            score=total_score,
            priority=final_priority,
            components=components,
            hard_rules_triggered=hard_triggered,
            ai_residual=ai_contribution,
            reasons=reasons,
        )

    # ------------------------------------------------------------------
    # 条件/归一化辅助函数
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_path(root: Dict[str, Any], path: str) -> Any:
        """从嵌套dict中解析字段路径，如 "features.risk_level"。

        为了保持Zero Magic，解析失败时返回None而不是抛异常，
        具体行为由上层归一化逻辑处理。
        """

        parts = path.split(".")
        current: Any = root
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    @staticmethod
    def _to_float(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):  # noqa: TRY003
            return 0.0

    @staticmethod
    def _to_float_or_none(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        try:
            return float(value)
        except (TypeError, ValueError):  # noqa: TRY003
            return None

    def _normalize_dimension(self, dim: ScoringDimension, raw: Any) -> float:
        """将原始值归一化到[0,1]，不适用于AI残差维度。

        缺失或无法解析的值统一按0处理，以保证算法鲁棒性。
        """

        value = self._to_float(raw)

        # normalize_by 优先
        if dim.normalize_by is not None:
            normalized = value / dim.normalize_by
        elif dim.scale:
            try:
                min_s, max_s = dim.scale.split("-")
                min_v = float(min_s)
                max_v = float(max_s)
                if max_v <= min_v:
                    normalized = 0.0
                else:
                    normalized = (value - min_v) / (max_v - min_v)
            except Exception:  # noqa: BLE001
                normalized = 0.0
        elif dim.max is not None and dim.max > 0:
            normalized = value / dim.max
        else:
            # 没有提供任何刻度信息时，假定已是0-1区间
            normalized = value

        # 截断到[0,1]
        if normalized < 0.0:
            normalized = 0.0
        elif normalized > 1.0:
            normalized = 1.0

        if dim.transform == TransformType.INVERT:
            normalized = 1.0 - normalized

        return normalized

    def _eval_condition(self, expr: HardRuleConditionExpr, root: Dict[str, Any]) -> bool:
        """执行简单条件判断，仅支持有限操作符集合。"""

        left = self._resolve_path(root, expr.field)
        right = expr.value
        op = expr.operator

        if op == ConditionOperator.EQ:
            return left == right
        if op == ConditionOperator.NE:
            return left != right

        # 数值比较时尝试转为float
        if op in {
            ConditionOperator.GT,
            ConditionOperator.GTE,
            ConditionOperator.LT,
            ConditionOperator.LTE,
        }:
            left_f = self._to_float(left)
            right_f = self._to_float(right)
            if op == ConditionOperator.GT:
                return left_f > right_f
            if op == ConditionOperator.GTE:
                return left_f >= right_f
            if op == ConditionOperator.LT:
                return left_f < right_f
            return left_f <= right_f

        if op == ConditionOperator.IN:
            return left in (right or [])
        if op == ConditionOperator.NOT_IN:
            return left not in (right or [])

        if op == ConditionOperator.CONTAINS:
            if isinstance(left, str) and isinstance(right, str):
                return right in left
            if isinstance(left, list):
                return right in left
            return False

        if op == ConditionOperator.REGEX:
            try:
                import re

                pattern = re.compile(str(right))
                return isinstance(left, str) and bool(pattern.search(left))
            except Exception:  # noqa: BLE001
                return False

        return False

    @staticmethod
    def _map_priority(score: float, buckets: List[PriorityBucket]) -> str:
        """根据分数映射优先级，按 min_score 降序匹配第一条。"""

        sorted_buckets = sorted(buckets, key=lambda b: b.min_score, reverse=True)
        for bucket in sorted_buckets:
            if score >= bucket.min_score:
                return bucket.name
        # 理论上不应走到这里，但为了健壮性提供默认值
        return sorted_buckets[-1].name if sorted_buckets else "low"

    @staticmethod
    def _priority_level(name: Optional[str]) -> int:
        """将优先级名称映射为可比较的等级。"""

        if name is None:
            return -1
        mapping = {
            "low": 0,
            "medium": 1,
            "high": 2,
            "critical": 3,
        }
        return mapping.get(name, 0)

    def _max_priority(self, a: Optional[str], b: Optional[str]) -> Optional[str]:
        """返回优先级更高的那个（critical > high > medium > low）。"""

        if a is None:
            return b
        if b is None:
            return a
        return a if self._priority_level(a) >= self._priority_level(b) else b


__all__ = [
    "EntityType",
    "ScoringContext",
    "PriorityScoringResult",
    "AiResidualProvider",
    "PriorityScoringEngine",
]
