"""
阶段2: 规则推理节点

使用知识图谱查询TRR规则，使用规则引擎进行匹配。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import EmergencyAIState, MatchedTRRRule, CapabilityRequirement
from ..tools.kg_tools import query_trr_rules_async, query_capability_mapping_async

logger = logging.getLogger(__name__)


async def query_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    规则查询节点：从知识图谱查询TRR规则
    
    根据灾害类型从Neo4j知识图谱中查询匹配的TRR触发规则。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行规则查询节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取灾情信息
    parsed_disaster = state.get("parsed_disaster")
    if not parsed_disaster:
        logger.error("无灾情解析结果，无法查询规则")
        return {
            "errors": state.get("errors", []) + ["无灾情解析结果"],
            "matched_rules": [],
        }
    
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    
    # 构建查询条件
    conditions = {
        "has_building_collapse": parsed_disaster.get("has_building_collapse", False),
        "has_trapped_persons": parsed_disaster.get("has_trapped_persons", False),
        "has_secondary_fire": parsed_disaster.get("has_secondary_fire", False),
        "has_hazmat_leak": parsed_disaster.get("has_hazmat_leak", False),
        "has_road_damage": parsed_disaster.get("has_road_damage", False),
        "affected_population": parsed_disaster.get("affected_population", 0),
        "building_damage_level": parsed_disaster.get("building_damage_level", "unknown"),
    }
    
    # 查询知识图谱
    try:
        kg_rules = await query_trr_rules_async(
            disaster_type=disaster_type,
            conditions=conditions,
        )
        
        # 更新追踪信息
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["query_rules"]
        trace["kg_calls"] = trace.get("kg_calls", 0) + 1
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "规则查询完成",
            extra={"rules_found": len(kg_rules), "elapsed_ms": elapsed_ms}
        )
        
        # 暂存原始规则，下一步进行匹配
        return {
            "_kg_rules": kg_rules,
            "trace": trace,
            "current_phase": "reasoning",
        }
        
    except Exception as e:
        logger.error("规则查询失败", extra={"error": str(e)})
        return {
            "errors": state.get("errors", []) + [f"规则查询失败: {str(e)}"],
            "_kg_rules": [],
        }


async def apply_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    规则匹配节点：应用TRR规则引擎
    
    对查询到的规则进行条件匹配，生成任务需求和能力需求列表。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行规则匹配节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取查询到的规则
    kg_rules = state.get("_kg_rules", [])
    parsed_disaster = state.get("parsed_disaster", {})
    
    if not kg_rules:
        logger.warning("无可用规则，使用默认规则")
        # 使用默认规则
        kg_rules = _get_default_rules(parsed_disaster)
    
    # 规则匹配
    matched_rules: List[MatchedTRRRule] = []
    all_tasks: List[Dict[str, Any]] = []
    all_capabilities: List[str] = []
    
    for rule in kg_rules:
        # 评估触发条件
        is_matched, match_reason = _evaluate_rule_conditions(
            rule=rule,
            disaster_info=parsed_disaster,
        )
        
        if is_matched:
            matched_rule: MatchedTRRRule = {
                "rule_id": rule.get("rule_id", ""),
                "rule_name": rule.get("rule_name", ""),
                "disaster_type": rule.get("disaster_type", ""),
                "priority": rule.get("priority", "medium"),
                "weight": rule.get("weight", 0.5),
                "triggered_tasks": [t.get("task_code", "") for t in rule.get("triggered_tasks", [])],
                "required_capabilities": [c.get("capability_code", "") for c in rule.get("required_capabilities", [])],
                "match_reason": match_reason,
            }
            matched_rules.append(matched_rule)
            
            # 收集任务
            for task in rule.get("triggered_tasks", []):
                task_info = {
                    "task_code": task.get("task_code"),
                    "task_name": task.get("task_name"),
                    "priority": task.get("priority", "medium"),
                    "source_rule": rule.get("rule_id"),
                    "sequence": task.get("sequence", 999),
                }
                all_tasks.append(task_info)
            
            # 收集能力
            for cap in rule.get("required_capabilities", []):
                cap_code = cap.get("capability_code")
                if cap_code and cap_code not in all_capabilities:
                    all_capabilities.append(cap_code)
    
    # 去重并排序任务
    seen_tasks = set()
    unique_tasks = []
    for task in sorted(all_tasks, key=lambda x: (x.get("sequence", 999), x.get("priority", "medium"))):
        if task["task_code"] not in seen_tasks:
            seen_tasks.add(task["task_code"])
            unique_tasks.append(task)
    
    # 查询能力映射
    capability_requirements: List[CapabilityRequirement] = []
    if all_capabilities:
        try:
            cap_mappings = await query_capability_mapping_async(all_capabilities)
            for mapping in cap_mappings:
                cap_req: CapabilityRequirement = {
                    "capability_code": mapping.get("capability_code", ""),
                    "capability_name": mapping.get("capability_name", ""),
                    "priority": "high",  # 从规则获取
                    "source_rule": "",   # 可追溯
                    "provided_by": [rt.get("resource_code", "") for rt in mapping.get("resource_types", [])],
                }
                capability_requirements.append(cap_req)
        except Exception as e:
            logger.warning("能力映射查询失败", extra={"error": str(e)})
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["apply_rules"]
    trace["rules_matched"] = len(matched_rules)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "规则匹配完成",
        extra={
            "matched_rules": len(matched_rules),
            "tasks": len(unique_tasks),
            "capabilities": len(capability_requirements),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "matched_rules": matched_rules,
        "task_requirements": unique_tasks,
        "capability_requirements": capability_requirements,
        "trace": trace,
    }


def _evaluate_rule_conditions(
    rule: Dict[str, Any],
    disaster_info: Dict[str, Any],
) -> tuple[bool, str]:
    """
    评估规则触发条件
    
    Args:
        rule: 规则定义
        disaster_info: 灾情信息
        
    Returns:
        (是否匹配, 匹配原因)
    """
    conditions = rule.get("trigger_conditions", [])
    logic = rule.get("trigger_logic", "AND")
    
    if not conditions:
        # 无条件，默认匹配
        return True, "无触发条件，默认匹配"
    
    results = []
    reasons = []
    
    for cond in conditions:
        # 解析条件字符串，如 "has_building_collapse = true"
        if isinstance(cond, str):
            parts = cond.replace(" ", "").split("=")
            if len(parts) == 2:
                field, expected = parts
                actual = disaster_info.get(field)
                
                # 布尔值比较
                if expected.lower() == "true":
                    matched = actual is True
                elif expected.lower() == "false":
                    matched = actual is False
                else:
                    # 数值比较
                    try:
                        if ">=" in cond:
                            field, expected = cond.split(">=")
                            matched = float(disaster_info.get(field.strip(), 0)) >= float(expected.strip())
                        elif ">" in cond:
                            field, expected = cond.split(">")
                            matched = float(disaster_info.get(field.strip(), 0)) > float(expected.strip())
                        else:
                            matched = str(actual).lower() == expected.lower()
                    except (ValueError, TypeError):
                        matched = False
                
                results.append(matched)
                if matched:
                    reasons.append(f"{field}={actual}")
    
    if logic == "AND":
        is_matched = all(results) if results else True
    else:  # OR
        is_matched = any(results) if results else False
    
    match_reason = "条件满足: " + ", ".join(reasons) if reasons else "默认匹配"
    return is_matched, match_reason


def _get_default_rules(disaster_info: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    获取默认规则（知识图谱不可用时的降级）
    
    标准能力编码（与Neo4j和数据库统一）：
    - LIFE_DETECTION: 生命探测
    - STRUCTURAL_RESCUE: 结构救援
    - MEDICAL_TRIAGE: 医疗分诊
    - EMERGENCY_TREATMENT: 紧急救治
    - FIRE_SUPPRESSION: 火灾扑救
    - CONFINED_SPACE_RESCUE: 狭小空间救援
    - WATER_RESCUE: 水上救援
    - COMMUNICATION_SUPPORT: 通信保障
    """
    disaster_type = disaster_info.get("disaster_type", "earthquake")
    
    default_rules = []
    
    # 地震默认规则
    if disaster_type == "earthquake":
        if disaster_info.get("has_building_collapse") or disaster_info.get("has_trapped_persons"):
            default_rules.append({
                "rule_id": "DEFAULT-EQ-001",
                "rule_name": "默认地震搜救规则",
                "disaster_type": "earthquake",
                "priority": "critical",
                "weight": 0.9,
                "trigger_conditions": [],
                "triggered_tasks": [
                    {"task_code": "SEARCH_RESCUE", "task_name": "搜索救援", "priority": "critical", "sequence": 1},
                    {"task_code": "MEDICAL_EMERGENCY", "task_name": "医疗急救", "priority": "critical", "sequence": 2},
                ],
                "required_capabilities": [
                    {"capability_code": "LIFE_DETECTION", "capability_name": "生命探测"},
                    {"capability_code": "STRUCTURAL_RESCUE", "capability_name": "结构救援"},
                    {"capability_code": "MEDICAL_TRIAGE", "capability_name": "医疗分诊"},
                ],
            })
        
        if disaster_info.get("has_secondary_fire"):
            default_rules.append({
                "rule_id": "DEFAULT-EQ-002",
                "rule_name": "默认地震火灾规则",
                "disaster_type": "earthquake",
                "priority": "critical",
                "weight": 0.85,
                "trigger_conditions": [],
                "triggered_tasks": [
                    {"task_code": "FIRE_SUPPRESSION", "task_name": "火灾扑救", "priority": "critical", "sequence": 1},
                ],
                "required_capabilities": [
                    {"capability_code": "FIRE_SUPPRESSION", "capability_name": "火灾扑救"},
                ],
            })
    
    return default_rules
