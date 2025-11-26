"""
规则触发节点

调用TRRRuleEngine匹配触发规则
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from ..state import SchemeGenerationState, MatchedRuleState
from ..utils import track_node_time
from ...rules import TRRRuleEngine

logger = logging.getLogger(__name__)


@track_node_time("apply_trr_rules")
def apply_trr_rules(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    规则触发节点
    
    从事件分析结果中提取上下文，调用TRRRuleEngine匹配规则
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含matched_rules
    """
    logger.info("开始执行规则触发节点")
    
    event_analysis = state.get("event_analysis", {})
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    # 构造规则匹配上下文
    context = _build_rule_context(event_analysis)
    logger.debug(f"规则上下文: {context}")
    
    # 调用规则引擎
    engine = TRRRuleEngine()
    
    try:
        matched = engine.evaluate(context)
        logger.info(f"规则匹配完成: {len(matched)}条规则")
    except Exception as e:
        logger.error(f"规则匹配失败: {e}")
        errors.append(f"规则匹配失败: {e}")
        return {
            "matched_rules": [],
            "errors": errors,
        }
    
    # 转换为状态格式
    matched_rules: list[MatchedRuleState] = []
    for rule in matched:
        matched_rule: MatchedRuleState = {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "priority": rule.priority.value,
            "weight": rule.weight,
            "task_types": rule.actions.task_types,
            "required_capabilities": [
                {
                    "code": cap.code,
                    "priority": cap.priority.value,
                    "min_quantity": cap.min_quantity,
                }
                for cap in rule.actions.required_capabilities
            ],
            "resource_types": rule.actions.resource_types,
            "grouping_pattern": rule.actions.grouping_pattern,
            "tactical_notes": rule.actions.tactical_notes,
        }
        matched_rules.append(matched_rule)
    
    # 更新追踪信息
    trace["trr_rules_matched"] = [r["rule_id"] for r in matched_rules]
    trace.setdefault("nodes_executed", []).append("apply_trr_rules")
    
    logger.info(f"匹配的规则: {trace['trr_rules_matched']}")
    
    return {
        "matched_rules": matched_rules,
        "trace": trace,
        "errors": errors,
    }


def _build_rule_context(event_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    从事件分析结果构建规则匹配上下文
    支持扩展版规则库（56条TRR + 45条硬规则）
    """
    assessment = event_analysis.get("assessment", {})
    location = event_analysis.get("location", {})
    
    context = {
        # ========== 基础字段 ==========
        "disaster_type": event_analysis.get("disaster_type", "unknown"),
        "incident_level": assessment.get("disaster_level", "III"),
        
        # ========== 人员相关 ==========
        "has_trapped": _has_trapped(assessment),
        "has_buried": assessment.get("has_buried", False),
        "has_casualties": _get_estimated_casualties(assessment) > 0,
        "estimated_casualties": _get_estimated_casualties(assessment),
        "casualties": _get_estimated_casualties(assessment),
        "exposed_population": assessment.get("exposed_population", 0),
        "affected_population": assessment.get("affected_population", 0),
        "crowd_density": assessment.get("crowd_density", 0),
        
        # ========== 地震相关 ==========
        "magnitude": assessment.get("magnitude", 0),
        "collapse_area_sqm": assessment.get("collapse_area_sqm", 0),
        "building_type": assessment.get("building_type"),
        "water_supply_disrupted": assessment.get("water_supply_disrupted", False),
        "power_outage_area_sqkm": assessment.get("power_outage_area_sqkm", 0),
        "gas_leak_detected": assessment.get("gas_leak_detected", False),
        "barrier_lake_formed": assessment.get("barrier_lake_formed", False),
        
        # ========== 火灾相关 ==========
        "fire_type": assessment.get("fire_type"),
        "fire_cause": assessment.get("fire_cause"),
        "fire_location": assessment.get("fire_location"),
        "building_height_m": assessment.get("building_height_m", 0),
        
        # ========== 危化品相关 ==========
        "has_leak": assessment.get("has_leak", False),
        "has_explosion": assessment.get("has_explosion", False),
        "hazmat_type": assessment.get("hazmat_type"),
        "incident_type": assessment.get("incident_type"),
        
        # ========== 洪涝相关 ==========
        "flood_type": assessment.get("flood_type"),
        "flood_location": assessment.get("flood_location"),
        "dam_emergency": assessment.get("dam_emergency", False),
        
        # ========== 台风/天气相关 ==========
        "typhoon_level": assessment.get("typhoon_level"),
        "typhoon_landed": assessment.get("typhoon_landed", False),
        "lightning_density": assessment.get("lightning_density"),
        "hail_diameter_mm": assessment.get("hail_diameter_mm", 0),
        
        # ========== 交通/矿山事故 ==========
        "vehicle_type": assessment.get("vehicle_type"),
        "accident_location": assessment.get("accident_location"),
        "accident_type": assessment.get("accident_type"),
        
        # ========== 环境条件 ==========
        "is_night_operation": event_analysis.get("is_night_operation", False),
        "communication_status": event_analysis.get("communication_status", "normal"),
        "scene_complexity": assessment.get("scene_complexity", "normal"),
        "requires_expert": assessment.get("requires_expert", False),
        "scene_control_required": assessment.get("scene_control_required", True),
        "media_attention": assessment.get("media_attention", False),
        "expected_duration_hours": assessment.get("expected_duration_hours", 2),
    }
    
    return context


def _has_trapped(assessment: Dict[str, Any]) -> bool:
    """判断是否有被困人员"""
    casualties = assessment.get("estimated_casualties", {})
    trapped = casualties.get("trapped", 0)
    
    if trapped > 0:
        return True
    
    # 根据其他字段推断
    if assessment.get("has_trapped"):
        return True
    
    return False


def _get_estimated_casualties(assessment: Dict[str, Any]) -> int:
    """获取预估伤亡总数"""
    casualties = assessment.get("estimated_casualties", {})
    
    if isinstance(casualties, (int, float)):
        return int(casualties)
    
    if not isinstance(casualties, dict):
        return 0
    
    # 支持多种字段名
    deaths = casualties.get("deaths", 0) or casualties.get("dead", 0)
    injuries = casualties.get("injuries", 0) or casualties.get("injured", 0)
    trapped = casualties.get("trapped", 0)
    missing = casualties.get("missing", 0)
    
    return int(deaths + injuries + trapped + missing)
