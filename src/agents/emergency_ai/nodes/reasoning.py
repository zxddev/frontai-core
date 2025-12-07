"""
阶段2: 规则推理节点

使用知识图谱查询TRR规则，使用规则引擎进行匹配。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import EmergencyAIState, MatchedTRRRule, CapabilityRequirement, RuleConflict
from ..tools.kg_tools import query_trr_rules_async, query_capability_mapping_async

logger = logging.getLogger(__name__)


# ============================================================================
# 标准能力编码参考（与 capability_codes_v2 数据库表统一）
# ============================================================================
# 搜索类(search): SEARCH_LIFE_DETECT, SEARCH_THERMAL, SEARCH_CANINE, SEARCH_SONAR
# 救援类(rescue): RESCUE_STRUCTURAL, RESCUE_CONFINED, RESCUE_ROPE, RESCUE_WATER_SWIFT, RESCUE_WATER_FLOOD
# 医疗类(medical): MEDICAL_TRIAGE, MEDICAL_FIRST_AID, MEDICAL_TRAUMA, MEDICAL_CPR, MEDICAL_TRANSPORT
# 危化类(hazmat): HAZMAT_DETECT, HAZMAT_CONTAIN, HAZMAT_DECON, HAZMAT_FIRE
# 消防类(fire): FIRE_SUPPRESS, FIRE_FOREST, FIRE_HIGH_RISE
# 工程类(engineering): ENG_SHORING, ENG_DEMOLITION, ENG_LIFTING
# 保障类(logistics): LOG_POWER, LOG_LIGHTING, LOG_COMM, LOG_SHELTER, LOG_SUPPLY


# ============================================================================
# 规则冲突检测
# ============================================================================

# 预定义的互斥规则对（任务级别）
EXCLUSIVE_TASK_PAIRS = [
    # 灭火 vs 禁止喷水（化学品泄漏场景）
    ("TASK_WATER_SPRAY", "TASK_NO_WATER"),
    # 通风 vs 密闭空间（有毒气体场景）  
    ("TASK_VENTILATION", "TASK_SEAL_AREA"),
    # 人员疏散 vs 就地避难
    ("TASK_EVACUATION", "TASK_SHELTER_IN_PLACE"),
    # 高压水枪 vs 低压雾化（特定火灾场景）
    ("TASK_HIGH_PRESSURE", "TASK_LOW_PRESSURE_MIST"),
]

# 预定义的资源竞争对（同一资源不能同时执行冲突任务）
RESOURCE_CONFLICT_GROUPS = {
    "WATER_SUPPLY": ["TASK_WATER_SPRAY", "TASK_FOAM_SPRAY", "TASK_COOLING"],
    "VENTILATION_EQUIP": ["TASK_VENTILATION", "TASK_SMOKE_EXHAUST"],
}


def detect_rule_conflicts(
    matched_rules: List[MatchedTRRRule],
    task_requirements: List[Dict[str, Any]],
) -> List[RuleConflict]:
    """
    检测匹配规则之间的冲突
    
    Args:
        matched_rules: 匹配的规则列表
        task_requirements: 生成的任务需求列表
        
    Returns:
        检测到的冲突列表
    """
    conflicts: List[RuleConflict] = []
    all_tasks = {t["task_code"] for t in task_requirements}
    
    # 检查互斥任务对
    for task1, task2 in EXCLUSIVE_TASK_PAIRS:
        if task1 in all_tasks and task2 in all_tasks:
            # 找到产生这两个任务的规则
            source_rules = []
            for rule in matched_rules:
                if task1 in rule["triggered_tasks"] or task2 in rule["triggered_tasks"]:
                    source_rules.append(rule["rule_id"])
            
            conflict: RuleConflict = {
                "conflict_type": "action_conflict",
                "conflicting_tasks": [task1, task2],
                "conflicting_rules": list(set(source_rules)),
                "description": f"任务{task1}与{task2}互斥，不能同时执行",
                "resolution_options": [
                    f"保留{task1}，移除{task2}",
                    f"保留{task2}，移除{task1}",
                    "由指挥官现场判断",
                ],
            }
            conflicts.append(conflict)
            logger.warning(
                f"[冲突检测] 发现互斥任务: {task1} vs {task2}",
                extra={"source_rules": source_rules}
            )
    
    # 检查资源竞争
    for resource, competing_tasks in RESOURCE_CONFLICT_GROUPS.items():
        active_competing = [t for t in competing_tasks if t in all_tasks]
        if len(active_competing) > 1:
            source_rules = []
            for rule in matched_rules:
                for task in active_competing:
                    if task in rule["triggered_tasks"]:
                        source_rules.append(rule["rule_id"])
            
            conflict = {
                "conflict_type": "resource_conflict",
                "conflicting_tasks": active_competing,
                "conflicting_rules": list(set(source_rules)),
                "description": f"资源{resource}被多个任务竞争: {active_competing}",
                "resolution_options": [
                    "按优先级顺序执行",
                    "分配更多资源",
                    "由指挥官协调",
                ],
            }
            conflicts.append(conflict)
            logger.warning(
                f"[冲突检测] 发现资源竞争: {resource} <- {active_competing}",
                extra={"source_rules": source_rules}
            )
    
    if conflicts:
        logger.info(f"[冲突检测] 共发现{len(conflicts)}个冲突")
    else:
        logger.info("[冲突检测] 未发现规则冲突")
    
    return conflicts


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
        raise RuntimeError(f"[规则匹配] Neo4j未返回匹配规则，disaster_type={parsed_disaster.get('disaster_type')}")
    
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
    
    # 打印规则匹配结果
    logger.info(f"【规则匹配】从{len(kg_rules)}条规则中匹配到{len(matched_rules)}条:")
    for rule in matched_rules:
        logger.info(f"  - {rule['rule_id']}: {rule['rule_name']} (原因: {rule['match_reason']})")
        logger.info(f"    触发任务: {rule['triggered_tasks']}")
        logger.info(f"    需要能力: {rule['required_capabilities']}")
    
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
    
    # 检测规则冲突
    rule_conflicts = detect_rule_conflicts(matched_rules, unique_tasks)
    
    # 合并已有冲突和新检测到的冲突
    existing_conflicts = list(state.get("rule_conflicts", []))
    all_conflicts = existing_conflicts + rule_conflicts
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["apply_rules"]
    trace["rules_matched"] = len(matched_rules)
    trace["conflicts_detected"] = len(rule_conflicts)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "规则匹配完成",
        extra={
            "matched_rules": len(matched_rules),
            "tasks": len(unique_tasks),
            "capabilities": len(capability_requirements),
            "conflicts": len(rule_conflicts),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "matched_rules": matched_rules,
        "task_requirements": unique_tasks,
        "capability_requirements": capability_requirements,
        "rule_conflicts": all_conflicts,
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
