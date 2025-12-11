"""
设备匹配节点

根据步骤需求和队伍设备进行匹配分配。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List, Set

from ..state import TaskCoordinatorState
from ..schemas import (
    StepAssignment,
    TeamRole,
    CoordinatorWarning,
)

logger = logging.getLogger(__name__)


def _match_equipment_for_team(
    required_equipment: List[str],
    team_equipment: List[str],
) -> List[str]:
    """
    为队伍匹配设备

    策略：从队伍拥有的设备中选择步骤所需的设备

    Args:
        required_equipment: 步骤所需设备
        team_equipment: 队伍拥有的设备

    Returns:
        分配给该队伍的设备列表
    """
    if not required_equipment or not team_equipment:
        return []

    # 简单匹配：队伍有的 ∩ 步骤需要的
    team_set = set(e.upper() for e in team_equipment)
    return [req for req in required_equipment if req.upper() in team_set]


def _get_team_equipment_map(
    state: TaskCoordinatorState,
) -> Dict[str, List[str]]:
    """
    构建队伍ID -> 设备列表的映射

    Args:
        state: 当前状态

    Returns:
        队伍设备映射
    """
    task_allocation = state.get("task_allocation")
    if not task_allocation:
        return {}

    return {
        team.team_id: team.equipment
        for team in task_allocation.allocated_teams
    }


async def match_equipment(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    设备匹配节点

    为每个步骤的每个队伍分配设备。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info("[TaskCoordinator] 匹配设备")
    start_time = time.time()

    step_assignments = state.get("step_assignments", [])
    sop_steps = state.get("sop_steps", [])
    warnings = list(state.get("warnings", []))

    if not step_assignments:
        return {
            "errors": state.get("errors", []) + ["无步骤分配"],
            "current_phase": "failed",
        }

    # 构建步骤ID -> 所需设备的映射
    step_equipment_map: Dict[str, List[str]] = {
        step.id: step.required_equipment
        for step in sop_steps
    }

    # 构建队伍ID -> 设备列表的映射
    team_equipment_map = _get_team_equipment_map(state)

    # 全局设备分配记录
    equipment_assignments: Dict[str, List[str]] = {}
    missing_equipment: List[Dict[str, Any]] = []

    # 更新后的步骤分配
    updated_assignments: List[StepAssignment] = []

    for assignment in step_assignments:
        required_equipment = step_equipment_map.get(assignment.step_id, [])
        assigned_in_step: Set[str] = set()
        updated_teams: List[TeamRole] = []

        for team_role in assignment.teams:
            team_equipment = team_equipment_map.get(team_role.team_id, [])

            # 匹配设备
            matched = _match_equipment_for_team(
                required_equipment,
                team_equipment,
            )

            # 更新队伍角色的设备
            updated_team = TeamRole(
                team_id=team_role.team_id,
                team_name=team_role.team_name,
                role=team_role.role,
                responsibilities=team_role.responsibilities,
                equipment=matched,
            )
            updated_teams.append(updated_team)

            # 记录分配
            if team_role.team_id not in equipment_assignments:
                equipment_assignments[team_role.team_id] = []
            equipment_assignments[team_role.team_id].extend(matched)

            assigned_in_step.update(matched)

        # 检查是否有未分配的设备
        missing = [e for e in required_equipment if e not in assigned_in_step]
        if missing:
            missing_equipment.append({
                "step_id": assignment.step_id,
                "step_name": assignment.step_name,
                "missing": missing,
            })
            warnings.append(CoordinatorWarning(
                code="EQUIPMENT_MISSING",
                message=f"步骤 '{assignment.step_name}' 缺少设备: {', '.join(missing)}",
                severity="warning",
                related_step=assignment.step_id,
            ))

        # 创建更新后的分配
        updated_assignments.append(StepAssignment(
            step_id=assignment.step_id,
            step_name=assignment.step_name,
            sequence=assignment.sequence,
            teams=updated_teams,
            cooperation_mode=assignment.cooperation_mode,
            depends_on=assignment.depends_on,
            estimated_duration=assignment.estimated_duration,
            completion_criteria=assignment.completion_criteria,
            safety_notes=assignment.safety_notes,
        ))

    elapsed_ms = int((time.time() - start_time) * 1000)

    total_equipment = sum(len(v) for v in equipment_assignments.values())
    logger.info(
        f"[TaskCoordinator] 设备匹配完成: "
        f"teams={len(equipment_assignments)}, "
        f"equipment={total_equipment}, "
        f"missing={len(missing_equipment)}"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_equipment"]
    trace["equipment_assigned"] = total_equipment

    return {
        "step_assignments": updated_assignments,
        "equipment_assignments": equipment_assignments,
        "warnings": warnings,
        "trace": trace,
        "current_phase": "generate_instructions",
        "execution_time_ms": state.get("execution_time_ms", 0) + elapsed_ms,
    }
