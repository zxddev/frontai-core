"""
输出生成节点

格式化方案输出，生成推荐理由
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from ..state import SchemeGenerationState, SchemeOutputState
from ..utils import track_node_time

logger = logging.getLogger(__name__)


@track_node_time("generate_output")
def generate_output(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    输出生成节点
    
    将处理结果格式化为最终输出
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含schemes和completed_at
    """
    logger.info("开始执行输出生成节点")
    
    scheme_scores = state.get("scheme_scores", [])
    feasible_schemes = state.get("feasible_schemes", [])
    matched_rules = state.get("matched_rules", [])
    resource_allocations = state.get("resource_allocations", [])
    pareto_solutions = state.get("pareto_solutions", [])
    event_analysis = state.get("event_analysis", {})
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    # 构建方案映射
    feasible_map = {s["solution_id"]: s for s in feasible_schemes}
    pareto_map = {s["solution_id"]: s for s in pareto_solutions}
    
    # 生成方案输出
    schemes: List[SchemeOutputState] = []
    
    for score in scheme_scores:
        scheme_id = score["scheme_id"]
        feasible = feasible_map.get(scheme_id, {})
        pareto = pareto_map.get(scheme_id, {})
        
        objectives = feasible.get("objectives", pareto.get("objectives", {}))
        
        # 生成任务列表
        tasks = _generate_tasks_from_rules(matched_rules, objectives)
        
        # 格式化资源分配
        formatted_allocations = _format_resource_allocations(
            resource_allocations, tasks
        )
        
        # 格式化触发规则
        formatted_rules = _format_matched_rules(matched_rules)
        
        # 计算预估指标
        estimated_metrics = _calculate_estimated_metrics(
            objectives, resource_allocations, tasks
        )
        
        # 生成推荐理由
        rationale = _generate_rationale(
            score, objectives, matched_rules, resource_allocations
        )
        
        # 计算AI置信度评分
        confidence_score = _calculate_confidence_score(
            score, objectives, matched_rules, resource_allocations, len(errors)
        )
        
        scheme: SchemeOutputState = {
            "scheme_id": f"scheme-{uuid4().hex[:8]}",
            "rank": score["rank"],
            "score": score["total_score"],
            "confidence_score": confidence_score,
            "tasks": tasks,
            "resource_allocations": formatted_allocations,
            "triggered_rules": formatted_rules,
            "estimated_metrics": estimated_metrics,
            "rationale": rationale,
        }
        schemes.append(scheme)
    
    logger.info(f"输出生成完成: {len(schemes)}个方案")
    
    # 更新追踪信息
    trace["output_schemes_count"] = len(schemes)
    trace.setdefault("nodes_executed", []).append("generate_output")
    
    return {
        "schemes": schemes,
        "completed_at": datetime.utcnow(),
        "trace": trace,
        "errors": errors,
    }


def _generate_tasks_from_rules(
    matched_rules: List[Dict[str, Any]],
    objectives: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从匹配规则生成任务列表"""
    tasks: List[Dict[str, Any]] = []
    task_id_counter = 1
    
    # 收集所有任务类型
    task_types_seen = set()
    
    for rule in matched_rules:
        for task_type in rule.get("task_types", []):
            if task_type in task_types_seen:
                continue
            task_types_seen.add(task_type)
            
            task = {
                "task_id": f"T{task_id_counter:03d}",
                "name": _get_task_name(task_type),
                "task_type": task_type,
                "phase": _get_task_phase(task_type),
                "priority": _get_task_priority(rule.get("priority", "medium")),
                "required_capabilities": [
                    cap["code"] for cap in rule.get("required_capabilities", [])
                ],
                "source_rule_id": rule.get("rule_id"),
                "estimated_duration_min": _estimate_task_duration(task_type),
            }
            tasks.append(task)
            task_id_counter += 1
    
    # 按优先级排序
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda t: priority_order.get(t["priority"], 2))
    
    return tasks


def _get_task_name(task_type: str) -> str:
    """获取任务名称"""
    names = {
        "search_rescue": "人员搜救",
        "medical_emergency": "医疗急救",
        "fire_suppression": "火灾扑救",
        "hazmat_containment": "危化品处置",
        "evacuation": "人员疏散",
        "water_rescue": "水域救援",
        "debris_clearing": "废墟清理",
        "hazard_monitoring": "灾害监测",
        "reconnaissance": "现场侦察",
        "heavy_rescue": "重型救援",
        "communication_support": "通信保障",
        "logistics_support": "后勤保障",
        "mass_casualty_incident": "批量伤员救治",
        "drainage": "排水作业",
        "traffic_control": "交通管制",
    }
    return names.get(task_type, task_type.replace("_", " ").title())


def _get_task_phase(task_type: str) -> str:
    """获取任务阶段"""
    immediate_tasks = {"search_rescue", "fire_suppression", "medical_emergency", "hazmat_containment"}
    if task_type in immediate_tasks:
        return "immediate"
    return "follow_up"


def _get_task_priority(rule_priority: str) -> str:
    """获取任务优先级"""
    return rule_priority


def _estimate_task_duration(task_type: str) -> int:
    """估算任务时长（分钟）"""
    durations = {
        "search_rescue": 120,
        "medical_emergency": 60,
        "fire_suppression": 90,
        "hazmat_containment": 180,
        "evacuation": 60,
        "water_rescue": 90,
        "debris_clearing": 240,
        "hazard_monitoring": 480,
        "reconnaissance": 30,
    }
    return durations.get(task_type, 60)


def _format_resource_allocations(
    allocations: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """格式化资源分配"""
    formatted = []
    
    for idx, alloc in enumerate(allocations):
        # 尝试匹配任务
        assigned_task_id = tasks[idx]["task_id"] if idx < len(tasks) else None
        assigned_task_types = alloc.get("assigned_task_types", [])
        
        # 如果没有assigned_task_types，从匹配的任务中提取
        if not assigned_task_types and assigned_task_id:
            for task in tasks:
                if task.get("task_id") == assigned_task_id:
                    assigned_task_types = [task.get("task_type", "unknown")]
                    break
        
        formatted_alloc = {
            "resource_id": alloc.get("resource_id"),
            "resource_name": alloc.get("resource_name"),
            "resource_type": alloc.get("resource_type"),
            "assigned_task_id": assigned_task_id,
            "assigned_task_types": assigned_task_types,  # 用于数据库持久化
            "role": _get_resource_role(alloc.get("resource_type", "")),
            "match_score": alloc.get("match_score", 0),
            "recommendation_reason": alloc.get("recommendation_reason", ""),
            "alternatives": alloc.get("alternatives", []),
        }
        formatted.append(formatted_alloc)
    
    return formatted


def _get_resource_role(resource_type: str) -> str:
    """获取资源角色"""
    roles = {
        "rescue_team": "主搜救力量",
        "medical_team": "医疗救护力量",
        "fire_team": "灭火力量",
        "hazmat_team": "危化品处置力量",
        "water_rescue_team": "水域救援力量",
        "engineering_team": "工程抢修力量",
    }
    return roles.get(resource_type, "支援力量")


def _format_matched_rules(matched_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """格式化匹配规则"""
    return [
        {
            "rule_id": rule.get("rule_id"),
            "rule_name": rule.get("rule_name"),
            "priority": rule.get("priority"),
            "tactical_notes": rule.get("tactical_notes"),
        }
        for rule in matched_rules
    ]


def _calculate_estimated_metrics(
    objectives: Dict[str, Any],
    allocations: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """计算预估指标"""
    return {
        "total_response_time_min": objectives.get("response_time", 15),
        "coverage_rate": objectives.get("coverage_rate", 0.95),
        "total_cost_yuan": objectives.get("cost", 100000),
        "risk_level": "low" if objectives.get("risk", 0.05) < 0.1 else "medium",
        "teams_deployed": len(allocations),
        "tasks_count": len(tasks),
        "estimated_duration_min": sum(t.get("estimated_duration_min", 60) for t in tasks),
    }


def _calculate_confidence_score(
    score: Dict[str, Any],
    objectives: Dict[str, Any],
    matched_rules: List[Dict[str, Any]],
    allocations: List[Dict[str, Any]],
    error_count: int,
) -> float:
    """
    计算AI置信度评分
    
    综合考虑：方案得分、能力覆盖率、规则匹配数、错误数
    """
    confidence = 0.5  # 基础分
    
    # 方案得分贡献 (0-0.2)
    total_score = score.get("total_score", 50)
    confidence += min(0.2, total_score / 500)
    
    # 能力覆盖率贡献 (0-0.2)
    coverage = objectives.get("coverage_rate", 0.8)
    confidence += coverage * 0.2
    
    # 规则匹配数贡献 (0-0.1)
    rule_count = len(matched_rules)
    confidence += min(0.1, rule_count * 0.025)
    
    # 资源分配数贡献 (0-0.05)
    alloc_count = len(allocations)
    confidence += min(0.05, alloc_count * 0.005)
    
    # 错误惩罚
    confidence -= error_count * 0.05
    
    # 确保范围在 0.3-0.98 之间
    return round(max(0.3, min(0.98, confidence)), 3)


def _generate_rationale(
    score: Dict[str, Any],
    objectives: Dict[str, Any],
    matched_rules: List[Dict[str, Any]],
    allocations: List[Dict[str, Any]],
) -> str:
    """生成推荐理由"""
    # 获取触发的规则
    rule_names = [r.get("rule_name", "") for r in matched_rules[:2]]
    rules_str = "、".join(rule_names) if rule_names else "应急响应规则"
    
    # 获取部署的资源
    resource_names = [a.get("resource_name", "") for a in allocations[:3]]
    resources_str = "、".join(resource_names) if resource_names else "应急救援力量"
    
    response_time = objectives.get("response_time", 15)
    coverage = objectives.get("coverage_rate", 0.95)
    
    rationale = (
        f"该方案综合得分{score['total_score']:.1f}分，"
        f"基于{rules_str}生成。"
        f"部署{resources_str}等{len(allocations)}支力量，"
        f"预计{response_time:.0f}分钟内到达现场，"
        f"覆盖{coverage*100:.0f}%的救援需求。"
    )
    
    # 添加战术建议
    tactical_notes = [r.get("tactical_notes") for r in matched_rules if r.get("tactical_notes")]
    if tactical_notes:
        rationale += f" 注意事项：{tactical_notes[0]}"
    
    return rationale
