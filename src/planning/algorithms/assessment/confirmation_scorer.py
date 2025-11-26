"""
事件确认评分算法

业务逻辑:
=========
1. 计算确认评分 = AI置信度×0.6 + 规则匹配度×0.3 + 来源可信度×0.1
2. 检查自动确认硬规则(AC-001~AC-004)
3. 决定状态流转: confirmed/pre_confirmed/pending

参考:
- 设计文档: docs/emergency-brain/接口设计/02_AI_Agent接口设计.md
- 数据库表: events_v2.confirmation_score, events_v2.matched_auto_confirm_rules
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus, Location

logger = logging.getLogger(__name__)


class EventStatus(Enum):
    """事件状态枚举"""
    PENDING = "pending"
    PRE_CONFIRMED = "pre_confirmed"
    CONFIRMED = "confirmed"


class AutoConfirmRule(Enum):
    """自动确认规则编码"""
    AC_001 = "AC-001"  # 多源交叉验证
    AC_002 = "AC-002"  # 传感器+AI双触发
    AC_003 = "AC-003"  # 官方系统紧急
    AC_004 = "AC-004"  # 明确被困人员


@dataclass
class ConfirmationInput:
    """确认评分输入"""
    ai_confidence: float              # AI置信度 (0-1)
    source_trust_level: float         # 来源可信度 (0-1)
    source_system: str                # 来源系统 (110/119/120/sensor/manual等)
    source_type: str                  # 来源类型 (manual_report/sensor_alert等)
    is_urgent: bool                   # 是否紧急
    estimated_victims: int            # 预估被困人数
    priority: str                     # 优先级 (critical/high/medium/low)
    event_location: Optional[Location]  # 事件位置
    reported_at: datetime             # 上报时间
    nearby_events: List[Dict]         # 同位置30分钟内其他事件


@dataclass
class ConfirmationResult:
    """确认评分结果"""
    confirmation_score: float         # 确认评分 (0-1)
    matched_rules: List[str]          # 匹配的AC规则
    rule_match_score: float           # 规则匹配度 (0-1)
    recommended_status: str           # 推荐状态
    auto_confirmed: bool              # 是否自动确认
    rationale: str                    # 决策理由
    score_breakdown: Dict[str, Dict]  # 评分细分


class ConfirmationScorer(AlgorithmBase):
    """
    事件确认评分算法
    
    使用示例:
    ```python
    scorer = ConfirmationScorer()
    result = scorer.run({
        "ai_confidence": 0.85,
        "source_trust_level": 0.95,
        "source_system": "110",
        "source_type": "external_system",
        "is_urgent": True,
        "estimated_victims": 20,
        "priority": "critical",
        "event_location": {"lat": 30.5728, "lng": 104.0657},
        "reported_at": "2025-11-25T10:30:00Z",
        "nearby_events": []
    })
    ```
    """
    
    # 评分权重
    WEIGHT_AI_CONFIDENCE: float = 0.6
    WEIGHT_RULE_MATCH: float = 0.3
    WEIGHT_SOURCE_TRUST: float = 0.1
    
    # 状态阈值
    THRESHOLD_AUTO_CONFIRM: float = 0.85
    THRESHOLD_PRE_CONFIRM: float = 0.60
    
    # 官方系统列表
    OFFICIAL_SYSTEMS: Tuple[str, ...] = ("110", "119", "120")
    
    # 规则匹配需要的最小置信度
    RULE_AC002_MIN_CONFIDENCE: float = 0.8
    RULE_AC004_MIN_CONFIDENCE: float = 0.7
    
    # 多源验证参数
    MULTI_SOURCE_RADIUS_M: float = 500.0
    MULTI_SOURCE_WINDOW_MIN: int = 30
    MULTI_SOURCE_MIN_SOURCES: int = 2
    
    def get_default_params(self) -> Dict[str, Any]:
        """获取默认参数"""
        return {
            "weight_ai_confidence": self.WEIGHT_AI_CONFIDENCE,
            "weight_rule_match": self.WEIGHT_RULE_MATCH,
            "weight_source_trust": self.WEIGHT_SOURCE_TRUST,
            "threshold_auto_confirm": self.THRESHOLD_AUTO_CONFIRM,
            "threshold_pre_confirm": self.THRESHOLD_PRE_CONFIRM,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        """验证输入合法性"""
        required_fields = ["ai_confidence", "source_trust_level", "source_system"]
        for field in required_fields:
            if field not in problem:
                return False, f"缺少必填字段: {field}"
        
        # 验证数值范围
        ai_conf = problem.get("ai_confidence", 0)
        if not 0 <= ai_conf <= 1:
            return False, f"ai_confidence必须在0-1之间，当前值: {ai_conf}"
        
        trust = problem.get("source_trust_level", 0)
        if not 0 <= trust <= 1:
            return False, f"source_trust_level必须在0-1之间，当前值: {trust}"
        
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行确认评分计算"""
        # 解析输入
        input_data = self._parse_input(problem)
        
        logger.info(
            "开始确认评分计算",
            extra={
                "ai_confidence": input_data.ai_confidence,
                "source_system": input_data.source_system,
                "is_urgent": input_data.is_urgent,
                "estimated_victims": input_data.estimated_victims,
            }
        )
        
        # 检查自动确认规则
        matched_rules, rule_details = self._check_auto_confirm_rules(input_data)
        
        # 计算规则匹配度 (匹配任意规则则为1.0)
        rule_match_score = 1.0 if matched_rules else 0.0
        
        # 计算确认评分
        confirmation_score = self._calculate_score(
            input_data.ai_confidence,
            rule_match_score,
            input_data.source_trust_level,
        )
        
        # 决定状态
        recommended_status, auto_confirmed, rationale = self._decide_status(
            confirmation_score=confirmation_score,
            matched_rules=matched_rules,
            input_data=input_data,
        )
        
        # 构造评分细分
        score_breakdown = {
            "ai_confidence": {
                "value": input_data.ai_confidence,
                "weight": self.WEIGHT_AI_CONFIDENCE,
                "contribution": round(input_data.ai_confidence * self.WEIGHT_AI_CONFIDENCE, 4),
            },
            "rule_match": {
                "value": rule_match_score,
                "weight": self.WEIGHT_RULE_MATCH,
                "contribution": round(rule_match_score * self.WEIGHT_RULE_MATCH, 4),
            },
            "source_trust": {
                "value": input_data.source_trust_level,
                "weight": self.WEIGHT_SOURCE_TRUST,
                "contribution": round(input_data.source_trust_level * self.WEIGHT_SOURCE_TRUST, 4),
            },
        }
        
        result = ConfirmationResult(
            confirmation_score=round(confirmation_score, 4),
            matched_rules=[r.value for r in matched_rules],
            rule_match_score=rule_match_score,
            recommended_status=recommended_status,
            auto_confirmed=auto_confirmed,
            rationale=rationale,
            score_breakdown=score_breakdown,
        )
        
        logger.info(
            "确认评分计算完成",
            extra={
                "confirmation_score": result.confirmation_score,
                "matched_rules": result.matched_rules,
                "recommended_status": result.recommended_status,
                "auto_confirmed": result.auto_confirmed,
            }
        )
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=result,
            metrics={
                "confirmation_score": result.confirmation_score,
                "rule_count": len(matched_rules),
                "auto_confirmed": 1 if auto_confirmed else 0,
            },
            trace={
                "input": problem,
                "rule_details": rule_details,
                "score_breakdown": score_breakdown,
            },
            time_ms=0,
        )
    
    def _parse_input(self, problem: Dict[str, Any]) -> ConfirmationInput:
        """解析输入参数"""
        # 解析位置
        location = None
        if "event_location" in problem and problem["event_location"]:
            loc_data = problem["event_location"]
            if isinstance(loc_data, dict):
                location = Location(
                    lat=loc_data.get("lat", loc_data.get("latitude", 0)),
                    lng=loc_data.get("lng", loc_data.get("longitude", 0)),
                )
            elif isinstance(loc_data, Location):
                location = loc_data
        
        # 解析时间
        reported_at = problem.get("reported_at")
        if isinstance(reported_at, str):
            reported_at = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
        elif reported_at is None:
            reported_at = datetime.utcnow()
        
        return ConfirmationInput(
            ai_confidence=float(problem.get("ai_confidence", 0)),
            source_trust_level=float(problem.get("source_trust_level", 0.5)),
            source_system=str(problem.get("source_system", "unknown")),
            source_type=str(problem.get("source_type", "manual_report")),
            is_urgent=bool(problem.get("is_urgent", False)),
            estimated_victims=int(problem.get("estimated_victims", 0)),
            priority=str(problem.get("priority", "medium")),
            event_location=location,
            reported_at=reported_at,
            nearby_events=list(problem.get("nearby_events", [])),
        )
    
    def _check_auto_confirm_rules(
        self, input_data: ConfirmationInput
    ) -> Tuple[List[AutoConfirmRule], Dict[str, Dict]]:
        """
        检查自动确认规则
        
        规则定义:
        - AC-001: 同位置(500m内)30分钟内≥2个不同来源上报
        - AC-002: 来源=传感器告警 且 AI置信度≥0.8
        - AC-003: 来源∈{110,119,120} 且 is_urgent=true
        - AC-004: estimated_victims>=1 且 AI置信度>=0.7
        """
        matched: List[AutoConfirmRule] = []
        details: Dict[str, Dict] = {}
        
        # AC-001: 多源交叉验证
        ac001_matched, ac001_detail = self._check_ac001(input_data)
        details["AC-001"] = ac001_detail
        if ac001_matched:
            matched.append(AutoConfirmRule.AC_001)
            logger.info("规则AC-001匹配: 多源交叉验证")
        
        # AC-002: 传感器+AI双触发
        ac002_matched, ac002_detail = self._check_ac002(input_data)
        details["AC-002"] = ac002_detail
        if ac002_matched:
            matched.append(AutoConfirmRule.AC_002)
            logger.info("规则AC-002匹配: 传感器+AI双触发")
        
        # AC-003: 官方系统紧急
        ac003_matched, ac003_detail = self._check_ac003(input_data)
        details["AC-003"] = ac003_detail
        if ac003_matched:
            matched.append(AutoConfirmRule.AC_003)
            logger.info("规则AC-003匹配: 官方系统紧急")
        
        # AC-004: 明确被困人员
        ac004_matched, ac004_detail = self._check_ac004(input_data)
        details["AC-004"] = ac004_detail
        if ac004_matched:
            matched.append(AutoConfirmRule.AC_004)
            logger.info("规则AC-004匹配: 明确被困人员")
        
        return matched, details
    
    def _check_ac001(self, input_data: ConfirmationInput) -> Tuple[bool, Dict]:
        """
        AC-001: 多源交叉验证
        条件: 同位置(500m内)30分钟内≥2个不同来源上报
        """
        detail = {
            "rule": "同位置(500m内)30分钟内≥2个不同来源上报",
            "checked": False,
            "matched": False,
            "reason": "",
        }
        
        if not input_data.nearby_events:
            detail["reason"] = "无邻近事件数据"
            return False, detail
        
        detail["checked"] = True
        
        # 统计不同来源数量
        sources = {input_data.source_system}
        for event in input_data.nearby_events:
            src = event.get("source_system", "")
            if src and src != input_data.source_system:
                sources.add(src)
        
        if len(sources) >= self.MULTI_SOURCE_MIN_SOURCES:
            detail["matched"] = True
            detail["reason"] = f"发现{len(sources)}个不同来源: {list(sources)}"
            return True, detail
        
        detail["reason"] = f"仅发现{len(sources)}个来源，需要至少{self.MULTI_SOURCE_MIN_SOURCES}个"
        return False, detail
    
    def _check_ac002(self, input_data: ConfirmationInput) -> Tuple[bool, Dict]:
        """
        AC-002: 传感器+AI双触发
        条件: 来源=传感器告警 且 AI置信度≥0.8
        """
        detail = {
            "rule": "来源=传感器告警 且 AI置信度≥0.8",
            "checked": True,
            "matched": False,
            "reason": "",
            "source_type": input_data.source_type,
            "ai_confidence": input_data.ai_confidence,
        }
        
        is_sensor = input_data.source_type == "sensor_alert"
        confidence_ok = input_data.ai_confidence >= self.RULE_AC002_MIN_CONFIDENCE
        
        if is_sensor and confidence_ok:
            detail["matched"] = True
            detail["reason"] = f"传感器来源且AI置信度{input_data.ai_confidence}≥{self.RULE_AC002_MIN_CONFIDENCE}"
            return True, detail
        
        reasons = []
        if not is_sensor:
            reasons.append(f"来源类型为{input_data.source_type}，非传感器")
        if not confidence_ok:
            reasons.append(f"AI置信度{input_data.ai_confidence}<{self.RULE_AC002_MIN_CONFIDENCE}")
        detail["reason"] = "; ".join(reasons)
        return False, detail
    
    def _check_ac003(self, input_data: ConfirmationInput) -> Tuple[bool, Dict]:
        """
        AC-003: 官方系统紧急
        条件: 来源∈{110,119,120} 且 is_urgent=true
        """
        detail = {
            "rule": "来源∈{110,119,120} 且 is_urgent=true",
            "checked": True,
            "matched": False,
            "reason": "",
            "source_system": input_data.source_system,
            "is_urgent": input_data.is_urgent,
        }
        
        is_official = input_data.source_system in self.OFFICIAL_SYSTEMS
        
        if is_official and input_data.is_urgent:
            detail["matched"] = True
            detail["reason"] = f"来源{input_data.source_system}为官方系统且标记紧急"
            return True, detail
        
        reasons = []
        if not is_official:
            reasons.append(f"来源{input_data.source_system}非官方系统{self.OFFICIAL_SYSTEMS}")
        if not input_data.is_urgent:
            reasons.append("未标记紧急")
        detail["reason"] = "; ".join(reasons)
        return False, detail
    
    def _check_ac004(self, input_data: ConfirmationInput) -> Tuple[bool, Dict]:
        """
        AC-004: 明确被困人员
        条件: estimated_victims>=1 且 AI置信度>=0.7
        """
        detail = {
            "rule": "estimated_victims>=1 且 AI置信度>=0.7",
            "checked": True,
            "matched": False,
            "reason": "",
            "estimated_victims": input_data.estimated_victims,
            "ai_confidence": input_data.ai_confidence,
        }
        
        has_victims = input_data.estimated_victims >= 1
        confidence_ok = input_data.ai_confidence >= self.RULE_AC004_MIN_CONFIDENCE
        
        if has_victims and confidence_ok:
            detail["matched"] = True
            detail["reason"] = f"有{input_data.estimated_victims}名被困人员且AI置信度{input_data.ai_confidence}≥{self.RULE_AC004_MIN_CONFIDENCE}"
            return True, detail
        
        reasons = []
        if not has_victims:
            reasons.append(f"预估被困人数{input_data.estimated_victims}<1")
        if not confidence_ok:
            reasons.append(f"AI置信度{input_data.ai_confidence}<{self.RULE_AC004_MIN_CONFIDENCE}")
        detail["reason"] = "; ".join(reasons)
        return False, detail
    
    def _calculate_score(
        self,
        ai_confidence: float,
        rule_match_score: float,
        source_trust: float,
    ) -> float:
        """
        计算确认评分
        
        公式: score = ai_confidence×0.6 + rule_match×0.3 + source_trust×0.1
        """
        score = (
            ai_confidence * self.WEIGHT_AI_CONFIDENCE +
            rule_match_score * self.WEIGHT_RULE_MATCH +
            source_trust * self.WEIGHT_SOURCE_TRUST
        )
        return min(1.0, max(0.0, score))
    
    def _decide_status(
        self,
        confirmation_score: float,
        matched_rules: List[AutoConfirmRule],
        input_data: ConfirmationInput,
    ) -> Tuple[str, bool, str]:
        """
        决定事件状态
        
        规则:
        1. 满足任一AC规则 OR score>=0.85 → confirmed, auto=true
        2. 0.6<=score<0.85 OR priority∈{critical,high} → pre_confirmed
        3. score<0.6 → pending
        """
        # 规则1: 自动确认
        if matched_rules:
            rule_names = [r.value for r in matched_rules]
            rationale = f"满足自动确认规则{rule_names}，评分{confirmation_score:.2f}"
            return EventStatus.CONFIRMED.value, True, rationale
        
        if confirmation_score >= self.THRESHOLD_AUTO_CONFIRM:
            rationale = f"确认评分{confirmation_score:.2f}≥{self.THRESHOLD_AUTO_CONFIRM}，自动确认"
            return EventStatus.CONFIRMED.value, True, rationale
        
        # 规则2: 预确认
        if confirmation_score >= self.THRESHOLD_PRE_CONFIRM:
            rationale = f"确认评分{confirmation_score:.2f}在[{self.THRESHOLD_PRE_CONFIRM},{self.THRESHOLD_AUTO_CONFIRM})区间，预确认等待人工复核"
            return EventStatus.PRE_CONFIRMED.value, False, rationale
        
        if input_data.priority in ("critical", "high"):
            rationale = f"优先级为{input_data.priority}，虽评分{confirmation_score:.2f}较低，仍预确认"
            return EventStatus.PRE_CONFIRMED.value, False, rationale
        
        # 规则3: 待确认
        rationale = f"确认评分{confirmation_score:.2f}<{self.THRESHOLD_PRE_CONFIRM}，待人工确认"
        return EventStatus.PENDING.value, False, rationale
