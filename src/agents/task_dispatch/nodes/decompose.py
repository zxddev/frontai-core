"""
方案拆解节点

将SchemeGenerationAgent输出的方案拆解为具体可执行的任务列表
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import uuid4

from ..state import (
    TaskDispatchState,
    DecomposedTaskState,
    TaskDependencyState,
    LocationState,
)

logger = logging.getLogger(__name__)

# 任务类型到预估时长的映射(分钟)
TASK_DURATION_DEFAULTS: Dict[str, int] = {
    "search_rescue": 120,
    "fire_fighting": 90,
    "medical": 60,
    "logistics": 45,
    "evacuation": 90,
    "hazmat": 120,
    "assessment": 30,
    "communication": 20,
}

# 任务类型到所需技能的映射
TASK_SKILL_REQUIREMENTS: Dict[str, List[str]] = {
    "search_rescue": ["rescue_operation", "life_detection"],
    "fire_fighting": ["fire_suppression", "hazmat_handling"],
    "medical": ["medical_treatment", "triage"],
    "logistics": ["logistics", "equipment_operation"],
    "evacuation": ["crowd_control", "evacuation_management"],
    "hazmat": ["hazmat_handling", "chemical_protection"],
    "assessment": ["damage_assessment", "structural_analysis"],
    "communication": ["communication", "coordination"],
}


def decompose_scheme(state: TaskDispatchState) -> Dict[str, Any]:
    """
    方案拆解节点
    
    将方案中的资源分配转换为具体任务列表，建立任务依赖关系
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(
        "开始方案拆解",
        extra={"scheme_id": state.get("scheme_id"), "event_id": state.get("event_id")}
    )
    
    scheme_data = state.get("scheme_data", {})
    if not scheme_data:
        logger.error("方案数据为空，无法拆解")
        return {
            "decomposed_tasks": [],
            "task_dependencies": [],
            "errors": state.get("errors", []) + ["方案数据为空"],
            "trace": _update_trace(state, "decompose_scheme", {"status": "failed", "reason": "empty_scheme"}),
        }
    
    # 提取资源分配
    resource_allocations = scheme_data.get("resource_allocations", [])
    triggered_rules = scheme_data.get("triggered_rules", [])
    event_location = _extract_event_location(scheme_data)
    
    logger.info(f"方案包含 {len(resource_allocations)} 个资源分配")
    
    # 拆解为任务
    decomposed_tasks: List[DecomposedTaskState] = []
    task_dependencies: List[TaskDependencyState] = []
    
    # 按任务类型分组生成任务
    task_type_groups = _group_allocations_by_task_type(resource_allocations, triggered_rules)
    
    prev_task_ids: Dict[str, str] = {}  # 记录每种类型的前置任务ID
    
    for task_type, allocations in task_type_groups.items():
        for idx, alloc in enumerate(allocations):
            task_id = f"task-{task_type}-{uuid4().hex[:8]}"
            
            # 构建任务
            task = _build_task_from_allocation(
                task_id=task_id,
                task_type=task_type,
                allocation=alloc,
                event_location=event_location,
                index=idx,
            )
            decomposed_tasks.append(task)
            
            # 建立依赖关系：搜救→医疗→转运
            dependency = _build_task_dependency(task_id, task_type, prev_task_ids)
            if dependency:
                task_dependencies.append(dependency)
                # 更新任务的前置依赖
                task["predecessors"] = dependency["depends_on"]
            
            prev_task_ids[task_type] = task_id
    
    logger.info(
        f"方案拆解完成: {len(decomposed_tasks)} 个任务, {len(task_dependencies)} 个依赖关系",
        extra={"task_types": list(task_type_groups.keys())}
    )
    
    return {
        "decomposed_tasks": decomposed_tasks,
        "task_dependencies": task_dependencies,
        "trace": _update_trace(state, "decompose_scheme", {
            "task_count": len(decomposed_tasks),
            "dependency_count": len(task_dependencies),
            "task_types": list(task_type_groups.keys()),
        }),
    }


def _extract_event_location(scheme_data: Dict[str, Any]) -> LocationState:
    """从方案数据提取事件位置"""
    # 尝试从 event_analysis 获取
    event_analysis = scheme_data.get("event_analysis", {})
    location = event_analysis.get("location", {})
    
    if location.get("latitude") and location.get("longitude"):
        return LocationState(
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
        )
    
    # 默认位置（应该由上游保证不会走到这里）
    logger.warning("方案数据中缺少事件位置，使用默认值")
    return LocationState(latitude=31.2, longitude=121.5)


def _group_allocations_by_task_type(
    allocations: List[Dict[str, Any]],
    rules: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """按任务类型分组资源分配"""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    
    for alloc in allocations:
        # 从分配中获取任务类型
        task_types = alloc.get("assigned_task_types", [])
        if not task_types:
            # 根据资源类型推断
            resource_type = alloc.get("resource_type", "")
            task_types = _infer_task_types_from_resource(resource_type)
        
        for task_type in task_types:
            if task_type not in groups:
                groups[task_type] = []
            groups[task_type].append(alloc)
    
    return groups


def _infer_task_types_from_resource(resource_type: str) -> List[str]:
    """根据资源类型推断任务类型"""
    mapping = {
        "heavy_rescue": ["search_rescue"],
        "light_rescue": ["search_rescue"],
        "fire_engine": ["fire_fighting"],
        "medical_team": ["medical"],
        "logistics_team": ["logistics"],
        "hazmat_team": ["hazmat"],
        "assessment_team": ["assessment"],
    }
    return mapping.get(resource_type, ["search_rescue"])


def _build_task_from_allocation(
    task_id: str,
    task_type: str,
    allocation: Dict[str, Any],
    event_location: LocationState,
    index: int,
) -> DecomposedTaskState:
    """从资源分配构建任务"""
    resource_name = allocation.get("resource_name", "未知资源")
    
    # 获取任务时长
    duration = TASK_DURATION_DEFAULTS.get(task_type, 60)
    
    # 获取所需技能
    required_skills = TASK_SKILL_REQUIREMENTS.get(task_type, [])
    
    # 构建所需资源
    resource_type = allocation.get("resource_type", "rescue_team")
    required_resources = {resource_type: 1}
    
    # 计算优先级：搜救最高，评估最低
    priority_map = {
        "search_rescue": 1,
        "fire_fighting": 1,
        "hazmat": 1,
        "medical": 2,
        "evacuation": 2,
        "logistics": 3,
        "assessment": 4,
        "communication": 4,
    }
    priority = priority_map.get(task_type, 3)
    
    return DecomposedTaskState(
        task_id=task_id,
        task_name=f"{_get_task_type_name(task_type)}-{index + 1}",
        task_type=task_type,
        priority=priority,
        duration_min=duration,
        location=event_location,
        predecessors=[],
        required_resources=required_resources,
        required_skills=required_skills,
        deadline_min=None,
        source_allocation_id=allocation.get("resource_id"),
    )


def _get_task_type_name(task_type: str) -> str:
    """获取任务类型中文名"""
    names = {
        "search_rescue": "搜救",
        "fire_fighting": "灭火",
        "medical": "医疗救治",
        "logistics": "物资运输",
        "evacuation": "人员疏散",
        "hazmat": "危化品处置",
        "assessment": "灾情评估",
        "communication": "通信协调",
    }
    return names.get(task_type, task_type)


def _build_task_dependency(
    task_id: str,
    task_type: str,
    prev_task_ids: Dict[str, str],
) -> TaskDependencyState | None:
    """构建任务依赖关系"""
    # 依赖规则：搜救→医疗→转运，灭火→危化品
    dependency_rules = {
        "medical": ["search_rescue"],
        "logistics": ["medical", "search_rescue"],
        "hazmat": ["fire_fighting"],
        "evacuation": ["assessment"],
    }
    
    depends_on_types = dependency_rules.get(task_type, [])
    depends_on_ids = []
    
    for dep_type in depends_on_types:
        if dep_type in prev_task_ids:
            depends_on_ids.append(prev_task_ids[dep_type])
    
    if not depends_on_ids:
        return None
    
    return TaskDependencyState(
        task_id=task_id,
        depends_on=depends_on_ids,
        dependency_type="finish_to_start",
    )


def _update_trace(
    state: TaskDispatchState,
    node_name: str,
    node_result: Dict[str, Any],
) -> Dict[str, Any]:
    """更新追踪信息"""
    trace = state.get("trace", {}).copy()
    nodes_executed = trace.get("nodes_executed", [])
    nodes_executed.append(node_name)
    trace["nodes_executed"] = nodes_executed
    trace[node_name] = node_result
    return trace
