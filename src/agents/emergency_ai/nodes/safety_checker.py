"""
战略层节点: 安全规则检查

使用JSON条件匹配检查方案是否违反安全规则。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from sqlalchemy import text

from ..state import EmergencyAIState, SafetyViolation

logger = logging.getLogger(__name__)


def match_json_condition(condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
    """
    匹配JSON条件
    
    支持的条件格式:
    - 简单匹配: {"key": "value"} - 检查 context[key] == value
    - 大于比较: {"key": {"$gt": 10}} - 检查 context[key] > 10
    - 小于比较: {"key": {"$lt": 10}} - 检查 context[key] < 10
    - 存在检查: {"key": {"$exists": true}} - 检查 key in context
    
    Args:
        condition: JSON条件
        context: 待检查的上下文
        
    Returns:
        是否匹配
    """
    for key, expected in condition.items():
        actual = context.get(key)
        
        if isinstance(expected, dict):
            # 复杂条件
            for op, val in expected.items():
                if op == "$gt":
                    if actual is None or actual <= val:
                        return False
                elif op == "$lt":
                    if actual is None or actual >= val:
                        return False
                elif op == "$gte":
                    if actual is None or actual < val:
                        return False
                elif op == "$lte":
                    if actual is None or actual > val:
                        return False
                elif op == "$exists":
                    if val and key not in context:
                        return False
                    if not val and key in context:
                        return False
                elif op == "$ne":
                    if actual == val:
                        return False
                elif op == "$in":
                    if actual not in val:
                        return False
        else:
            # 简单相等匹配
            if actual != expected:
                return False
    
    return True


async def check_safety_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    安全规则检查节点：检查方案是否违反安全规则
    
    1. 从PostgreSQL查询所有激活的安全规则
    2. 构建当前态势上下文
    3. 使用JSON条件匹配检查每条规则
    4. 收集违规信息
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 safety_violations
    """
    event_id = state["event_id"]
    parsed_disaster = state.get("parsed_disaster", {})
    
    logger.info(
        "【安全规则】开始执行",
        extra={
            "event_id": event_id,
            "disaster_type": parsed_disaster.get("disaster_type") if parsed_disaster else None,
        }
    )
    start_time = time.time()
    
    # 构建检查上下文
    context: Dict[str, Any] = {}
    
    if parsed_disaster:
        context.update({
            "disaster_type": parsed_disaster.get("disaster_type"),
            "has_building_collapse": parsed_disaster.get("has_building_collapse", False),
            "has_trapped_persons": parsed_disaster.get("has_trapped_persons", False),
            "has_secondary_fire": parsed_disaster.get("has_secondary_fire", False),
            "has_hazmat_leak": parsed_disaster.get("has_hazmat_leak", False),
            "has_road_damage": parsed_disaster.get("has_road_damage", False),
            "severity": parsed_disaster.get("severity"),
            "affected_population": parsed_disaster.get("affected_population", 0),
        })
    
    # 添加结构化输入
    structured_input = state.get("structured_input", {})
    context.update({
        "has_gas_leak": structured_input.get("has_gas_leak", False),
        "has_toxic_gas": structured_input.get("has_toxic_gas", False),
        "structural_stability": structured_input.get("structural_stability", "unknown"),
        "aftershock_risk": structured_input.get("aftershock_risk", "unknown"),
        "water_level_danger": structured_input.get("water_level_danger", False),
        "is_night_operation": structured_input.get("is_night_operation", False),
        "weather_condition": structured_input.get("weather_condition", "normal"),
        "communication_status": structured_input.get("communication_status", "normal"),
    })
    
    # 添加资源覆盖率
    recommended_scheme = state.get("recommended_scheme")
    if recommended_scheme:
        context["resource_coverage"] = recommended_scheme.get("coverage_rate", 1.0)
    
    # 添加连续作业时间
    context["continuous_operation_hours"] = structured_input.get("continuous_operation_hours", 0)
    
    logger.info(
        "【安全规则】构建检查上下文",
        extra={"context": context}
    )
    
    # 从PostgreSQL查询安全规则
    from src.core.database import AsyncSessionLocal
    
    query = text("""
        SELECT rule_id, rule_type, name, condition, action, message, priority
        FROM config.safety_rules
        WHERE is_active = TRUE
        ORDER BY priority DESC, rule_type
    """)
    
    logger.info("【PostgreSQL】查询安全规则", extra={"query": str(query)})
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(query)
        rule_rows = result.fetchall()
    
    logger.info(
        "【PostgreSQL】查询结果",
        extra={"count": len(rule_rows)}
    )
    
    if not rule_rows:
        raise ValueError(f"【安全规则】PostgreSQL未找到安全规则配置，event_id={event_id}")
    
    # 检查每条规则
    safety_violations: List[SafetyViolation] = []
    
    for row in rule_rows:
        rule_id = row.rule_id
        condition = row.condition
        
        logger.info(
            "【安全规则】检查规则",
            extra={"rule_id": rule_id, "condition": condition}
        )
        
        # 匹配条件
        if match_json_condition(condition, context):
            violation = SafetyViolation(
                rule_id=rule_id,
                rule_type=row.rule_type,
                action=row.action,
                message=row.message,
                matched_condition=condition,
            )
            safety_violations.append(violation)
            
            if row.rule_type == "hard":
                logger.error(
                    "【安全规则】硬规则违反",
                    extra={"rule_id": rule_id, "message": row.message}
                )
            else:
                logger.warning(
                    "【安全规则】软规则触发",
                    extra={"rule_id": rule_id, "message": row.message}
                )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["check_safety_rules"]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【安全规则】执行完成",
        extra={
            "event_id": event_id,
            "violations_count": len(safety_violations),
            "hard_violations": len([v for v in safety_violations if v["rule_type"] == "hard"]),
            "soft_violations": len([v for v in safety_violations if v["rule_type"] == "soft"]),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "safety_violations": safety_violations,
        "trace": trace,
        "current_phase": "strategic_safety",
    }
