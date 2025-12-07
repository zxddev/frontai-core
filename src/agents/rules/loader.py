"""
规则加载器

从YAML文件或数据库加载TRR规则和硬约束规则
支持文件级缓存，避免重复解析
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import yaml

from .models import (
    TRRRule,
    TriggerConfig,
    ActionConfig,
    Condition,
    ConditionOperator,
    ConditionLogic,
    CapabilityRequirement,
    RulePriority,
    HardRule,
    HardRuleCheck,
    HardRuleCondition,
    HardRuleAction,
    HardRuleSeverity,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 模块级缓存：{file_path: (mtime, rules_list)}
_trr_rules_cache: Dict[str, Tuple[float, List[TRRRule]]] = {}
_hard_rules_cache: Dict[str, Tuple[float, List[HardRule]]] = {}
_cache_lock = threading.Lock()

# 缓存统计计数器
_cache_stats = {
    "trr_hits": 0,
    "trr_misses": 0,
    "hard_hits": 0,
    "hard_misses": 0,
}


def clear_rules_cache() -> None:
    """清除所有规则缓存（用于热更新或测试）"""
    with _cache_lock:
        _trr_rules_cache.clear()
        _hard_rules_cache.clear()
        logger.info("规则缓存已清除")


def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息
    
    Returns:
        包含命中率等统计数据的字典
    """
    with _cache_lock:
        stats = _cache_stats.copy()
    
    trr_total = stats["trr_hits"] + stats["trr_misses"]
    hard_total = stats["hard_hits"] + stats["hard_misses"]
    
    return {
        "trr_rules": {
            "hits": stats["trr_hits"],
            "misses": stats["trr_misses"],
            "hit_rate": round(stats["trr_hits"] / trr_total, 3) if trr_total > 0 else 0.0,
        },
        "hard_rules": {
            "hits": stats["hard_hits"],
            "misses": stats["hard_misses"],
            "hit_rate": round(stats["hard_hits"] / hard_total, 3) if hard_total > 0 else 0.0,
        },
        "cache_size": {
            "trr_entries": len(_trr_rules_cache),
            "hard_entries": len(_hard_rules_cache),
        },
    }


def reset_cache_stats() -> None:
    """重置缓存统计计数器"""
    with _cache_lock:
        _cache_stats["trr_hits"] = 0
        _cache_stats["trr_misses"] = 0
        _cache_stats["hard_hits"] = 0
        _cache_stats["hard_misses"] = 0
    logger.debug("缓存统计已重置")


class RuleLoader:
    """规则加载器"""
    
    # 默认规则文件路径
    DEFAULT_TRR_PATH = "config/rules/trr_emergency.yaml"
    DEFAULT_HARD_RULES_PATH = "config/rules/hard_rules.yaml"
    
    @classmethod
    def load_trr_rules(cls, path: Optional[str] = None, use_cache: bool = True) -> List[TRRRule]:
        """
        加载TRR触发规则（支持缓存）
        
        Args:
            path: YAML文件路径，默认使用DEFAULT_TRR_PATH
            use_cache: 是否使用缓存，默认True
            
        Returns:
            规则列表，按weight降序排列
        """
        file_path = Path(path or cls.DEFAULT_TRR_PATH)
        cache_key = str(file_path.absolute())
        
        if not file_path.exists():
            logger.warning(f"TRR规则文件不存在: {file_path}")
            return []
        
        current_mtime = file_path.stat().st_mtime
        
        # 检查缓存
        if use_cache:
            with _cache_lock:
                if cache_key in _trr_rules_cache:
                    cached_mtime, cached_rules = _trr_rules_cache[cache_key]
                    if cached_mtime == current_mtime:
                        _cache_stats["trr_hits"] += 1
                        logger.debug(f"TRR规则使用缓存: {len(cached_rules)}条")
                        return cached_rules
                _cache_stats["trr_misses"] += 1
        
        # 缓存未命中或禁用缓存，重新加载
        logger.info(f"加载TRR规则: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"YAML解析失败: {e}")
            raise ValueError(f"TRR规则文件格式错误: {e}")
        
        if not data or "rules" not in data:
            logger.warning("TRR规则文件为空或缺少rules字段")
            return []
        
        rules: List[TRRRule] = []
        raw_rules: Dict[str, Any] = data.get("rules", {})
        
        for rule_id, rule_data in raw_rules.items():
            try:
                rule = cls._parse_trr_rule(rule_id, rule_data)
                rules.append(rule)
                logger.debug(f"加载规则: {rule_id} - {rule.name}")
            except Exception as e:
                logger.error(f"解析规则{rule_id}失败: {e}")
                raise ValueError(f"规则{rule_id}格式错误: {e}")
        
        # 按权重降序排列
        rules.sort(key=lambda r: r.weight, reverse=True)
        logger.info(f"共加载{len(rules)}条TRR规则")
        
        # 更新缓存
        with _cache_lock:
            _trr_rules_cache[cache_key] = (current_mtime, rules)
        
        return rules
    
    @classmethod
    def _parse_trr_rule(cls, rule_id: str, data: Dict) -> TRRRule:
        """解析单条TRR规则"""
        # 解析触发配置
        trigger_data = data.get("trigger", {})
        conditions = [
            Condition(
                field=c["field"],
                operator=ConditionOperator(c["operator"]),
                value=c["value"],
            )
            for c in trigger_data.get("conditions", [])
        ]
        trigger = TriggerConfig(
            conditions=conditions,
            logic=ConditionLogic(trigger_data.get("logic", "AND")),
        )
        
        # 解析动作配置
        actions_data = data.get("actions", {})
        capabilities = [
            CapabilityRequirement(
                code=cap["code"],
                priority=RulePriority(cap["priority"]),
                min_quantity=cap.get("min_quantity", 1),
            )
            for cap in actions_data.get("required_capabilities", [])
        ]
        actions = ActionConfig(
            task_types=actions_data.get("task_types", []),
            required_capabilities=capabilities,
            resource_types=actions_data.get("resource_types", []),
            grouping_pattern=actions_data.get("grouping_pattern"),
            tactical_notes=actions_data.get("tactical_notes"),
        )
        
        return TRRRule(
            id=rule_id,
            name=data.get("name", rule_id),
            description=data.get("description"),
            trigger=trigger,
            actions=actions,
            priority=RulePriority(data.get("priority", "medium")),
            weight=float(data.get("weight", 0.5)),
        )
    
    @classmethod
    def load_hard_rules(cls, path: Optional[str] = None, use_cache: bool = True) -> List[HardRule]:
        """
        加载硬约束规则（支持缓存）
        
        Args:
            path: YAML文件路径，默认使用DEFAULT_HARD_RULES_PATH
            use_cache: 是否使用缓存，默认True
            
        Returns:
            硬规则列表
        """
        file_path = Path(path or cls.DEFAULT_HARD_RULES_PATH)
        cache_key = str(file_path.absolute())
        
        if not file_path.exists():
            logger.warning(f"硬规则文件不存在: {file_path}")
            return []
        
        current_mtime = file_path.stat().st_mtime
        
        # 检查缓存
        if use_cache:
            with _cache_lock:
                if cache_key in _hard_rules_cache:
                    cached_mtime, cached_rules = _hard_rules_cache[cache_key]
                    if cached_mtime == current_mtime:
                        _cache_stats["hard_hits"] += 1
                        logger.debug(f"硬规则使用缓存: {len(cached_rules)}条")
                        return cached_rules
                _cache_stats["hard_misses"] += 1
        
        # 缓存未命中或禁用缓存，重新加载
        logger.info(f"加载硬规则: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"YAML解析失败: {e}")
            raise ValueError(f"硬规则文件格式错误: {e}")
        
        if not data or "rules" not in data:
            logger.warning("硬规则文件为空或缺少rules字段")
            return []
        
        rules: List[HardRule] = []
        raw_rules: Dict[str, Any] = data.get("rules", {})
        
        for rule_id, rule_data in raw_rules.items():
            try:
                rule = cls._parse_hard_rule(rule_id, rule_data)
                rules.append(rule)
                logger.debug(f"加载硬规则: {rule_id} - {rule.name}")
            except Exception as e:
                logger.error(f"解析硬规则{rule_id}失败: {e}")
                raise ValueError(f"硬规则{rule_id}格式错误: {e}")
        
        logger.info(f"共加载{len(rules)}条硬规则")
        
        # 更新缓存
        with _cache_lock:
            _hard_rules_cache[cache_key] = (current_mtime, rules)
        
        return rules
    
    @classmethod
    def _parse_hard_rule(cls, rule_id: str, data: Dict) -> HardRule:
        """解析单条硬规则"""
        # 解析检查配置
        check_data = data.get("check", {})
        check = HardRuleCheck(
            field=check_data["field"],
            operator=ConditionOperator(check_data["operator"]),
            threshold=check_data.get("threshold"),
            threshold_field=check_data.get("threshold_field"),
        )
        
        # 解析前置条件（可选）
        condition = None
        if "condition" in data:
            cond_data = data["condition"]
            condition = HardRuleCondition(
                field=cond_data["field"],
                operator=ConditionOperator(cond_data["operator"]),
                value=cond_data["value"],
            )
        
        return HardRule(
            id=rule_id,
            name=data.get("name", rule_id),
            description=data.get("description"),
            check=check,
            condition=condition,
            action=HardRuleAction(data.get("action", "reject")),
            message=data.get("message", "规则检查失败"),
            severity=HardRuleSeverity(data.get("severity", "high")),
        )
    
    @classmethod
    async def load_safety_rules_from_db(
        cls, 
        db: "AsyncSession"
    ) -> Dict[str, List[HardRule]]:
        """
        从数据库加载安全规则（三级规则体系）
        
        Args:
            db: 数据库会话
            
        Returns:
            按规则类型分类的字典:
            {
                "reject": [...],      # 硬性阻断规则
                "break_glass": [...], # Break Glass规则
                "warn": [...]         # 软性提示规则
            }
        """
        from sqlalchemy import select
        from .db_models import SafetyRule
        
        # 查询所有启用的规则
        stmt = select(SafetyRule).where(
            SafetyRule.is_active == True
        ).order_by(SafetyRule.sort_order)
        
        result = await db.execute(stmt)
        rows = result.scalars().all()
        
        # 按类型分类
        rules_by_type: Dict[str, List[HardRule]] = {
            "reject": [],
            "break_glass": [],
            "warn": [],
        }
        
        for row in rows:
            try:
                rule = cls._db_row_to_hard_rule(row)
                rule_type = row.rule_type
                if rule_type in rules_by_type:
                    rules_by_type[rule_type].append(rule)
                else:
                    logger.warning(f"未知规则类型: {rule_type}, 规则ID: {row.rule_id}")
            except Exception as e:
                logger.error(f"解析数据库规则失败: {row.rule_id} - {e}")
        
        logger.info(
            f"从数据库加载安全规则: reject={len(rules_by_type['reject'])}, "
            f"break_glass={len(rules_by_type['break_glass'])}, "
            f"warn={len(rules_by_type['warn'])}"
        )
        
        return rules_by_type
    
    @classmethod
    def _db_row_to_hard_rule(cls, row) -> HardRule:
        """
        将数据库行转换为 HardRule 对象
        
        Args:
            row: SafetyRule ORM 对象
            
        Returns:
            HardRule 对象
        """
        # 解析检查配置
        check = HardRuleCheck(
            field=row.check_field,
            operator=ConditionOperator(row.check_operator),
            threshold=row.check_threshold,
            threshold_field=row.check_threshold_field,
        )
        
        # 解析前置条件（可选）
        condition = None
        if row.condition_field and row.condition_operator:
            condition = HardRuleCondition(
                field=row.condition_field,
                operator=ConditionOperator(row.condition_operator),
                value=row.condition_value,
            )
        
        # 映射 rule_type 到 HardRuleAction
        action_map = {
            "reject": HardRuleAction.REJECT,
            "break_glass": HardRuleAction.BREAK_GLASS,
            "warn": HardRuleAction.WARN,
        }
        action = action_map.get(row.rule_type, HardRuleAction.REJECT)
        
        # 映射 severity 到 HardRuleSeverity
        severity_map = {
            "critical": HardRuleSeverity.CRITICAL,
            "high": HardRuleSeverity.HIGH,
            "medium": HardRuleSeverity.MEDIUM,
            "low": HardRuleSeverity.MEDIUM,  # low 映射到 medium（枚举中没有 low）
        }
        severity = severity_map.get(row.severity, HardRuleSeverity.HIGH)
        
        return HardRule(
            id=row.rule_id,
            name=row.rule_name,
            description=row.risk_description,  # Break Glass 的 risk_description 作为 description
            check=check,
            condition=condition,
            action=action,
            message=row.message_template,
            severity=severity,
        )
