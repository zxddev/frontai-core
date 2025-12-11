"""
角色分配节点

为每个步骤分配队伍角色（主攻/配合/保障）。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List, Set

from ..state import TaskCoordinatorState
from ..schemas import (
    SOPStep,
    TeamInfo,
    TeamRole,
    TeamRoleType,
    StepAssignment,
    CooperationMode,
    CoordinatorWarning,
)

logger = logging.getLogger(__name__)


def _calculate_capability_match(
    team_capabilities: List[str],
    required_capabilities: List[str],
) -> float:
    """
    计算能力匹配度

    Args:
        team_capabilities: 队伍能力列表
        required_capabilities: 步骤所需能力

    Returns:
        匹配度 (0-1)
    """
    if not required_capabilities:
        return 0.5  # 无要求时给中等分

    team_caps = set(c.upper() for c in team_capabilities)
    req_caps = set(c.upper() for c in required_capabilities)

    if not req_caps:
        return 0.5

    matched = team_caps.intersection(req_caps)
    return len(matched) / len(req_caps)


def _assign_teams_to_step(
    step: SOPStep,
    available_teams: List[TeamInfo],
    already_assigned: Set[str],
) -> List[TeamRole]:
    """
    为单个步骤分配队伍角色

    策略（修改后）：
    1. 所有传入的队伍都参与每个步骤
    2. 按能力匹配度排序，分配角色（主攻/配合/保障）
    3. 不过滤任何队伍，确保与 emergency_ai 推荐的队伍一致

    Args:
        step: SOP 步骤
        available_teams: 可用队伍列表（全部参与）
        already_assigned: 已分配的队伍ID（此参数保留但不再用于过滤）

    Returns:
        TeamRole 列表（包含所有队伍）
    """
    if not available_teams:
        return []

    assigned_roles: List[TeamRole] = []

    # 按能力匹配度排序队伍
    scored_teams = []
    for team in available_teams:
        score = _calculate_capability_match(
            team.capabilities,
            step.required_capabilities,
        )
        scored_teams.append((team, score))

    scored_teams.sort(key=lambda x: x[1], reverse=True)

    # 所有队伍都参与，按排名分配角色
    # 第1名：主攻，第2-3名：配合，其余：保障
    for idx, (team, score) in enumerate(scored_teams):
        if idx == 0:
            role_type = TeamRoleType.PRIMARY
        elif idx <= 2:
            role_type = TeamRoleType.SUPPORT
        else:
            role_type = TeamRoleType.LOGISTICS

        # 生成职责描述
        responsibilities = _generate_responsibilities(step, role_type)

        assigned_roles.append(TeamRole(
            team_id=team.team_id,
            team_name=team.team_name,
            role=role_type,
            responsibilities=responsibilities,
            equipment=[],  # 设备在下一节点分配
        ))

    return assigned_roles


def _generate_responsibilities(step: SOPStep, role: TeamRoleType) -> List[str]:
    """
    根据步骤和角色生成职责描述

    Args:
        step: SOP 步骤
        role: 角色类型

    Returns:
        职责列表
    """
    base_responsibilities = []

    if role == TeamRoleType.PRIMARY:
        base_responsibilities.append(f"负责执行{step.name}的主要任务")
        if step.required_capabilities:
            base_responsibilities.append(f"运用{', '.join(step.required_capabilities[:2])}能力")
    elif role == TeamRoleType.SUPPORT:
        base_responsibilities.append(f"配合主攻队伍完成{step.name}")
        base_responsibilities.append("提供必要的辅助支持")
    elif role == TeamRoleType.LOGISTICS:
        base_responsibilities.append("保障物资供应和后勤支持")
        base_responsibilities.append("维护通讯畅通")
    elif role == TeamRoleType.STANDBY:
        base_responsibilities.append("待命准备，随时接替或增援")

    if step.safety_notes:
        base_responsibilities.append(f"注意：{step.safety_notes}")

    return base_responsibilities


def _determine_cooperation_mode(step: SOPStep, team_count: int) -> CooperationMode:
    """
    确定协作模式

    Args:
        step: SOP 步骤
        team_count: 分配的队伍数量

    Returns:
        协作模式
    """
    if team_count <= 1:
        return CooperationMode.SEQUENTIAL

    if step.parallel_allowed:
        return CooperationMode.PARALLEL
    else:
        return CooperationMode.SUPPORT


async def assign_roles(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    角色分配节点

    为每个步骤分配队伍和角色。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info("[TaskCoordinator] 分配队伍角色")
    start_time = time.time()

    sop_steps = state.get("sop_steps", [])
    task_allocation = state.get("task_allocation")
    step_dependencies = state.get("step_dependencies", {})
    warnings = list(state.get("warnings", []))

    if not sop_steps:
        return {
            "errors": state.get("errors", []) + ["无 SOP 步骤"],
            "current_phase": "failed",
        }

    # 获取可用队伍
    available_teams = task_allocation.allocated_teams if task_allocation else []

    # 如果没有队伍，生成警告但继续（可能后续会补充）
    if not available_teams:
        warnings.append(CoordinatorWarning(
            code="NO_TEAMS_AVAILABLE",
            message="无可用队伍，步骤分配将为空",
            severity="warning",
        ))

    # 为每个步骤分配角色
    step_assignments: List[StepAssignment] = []
    unassigned_roles: List[Dict[str, Any]] = []

    for step in sop_steps:
        already_assigned: Set[str] = set()
        team_roles = _assign_teams_to_step(step, available_teams, already_assigned)

        # 检查是否所有角色都已分配
        roles_needed = step.roles or ["主攻"]
        if len(team_roles) < len(roles_needed):
            missing_count = len(roles_needed) - len(team_roles)
            unassigned_roles.append({
                "step_id": step.id,
                "step_name": step.name,
                "missing_roles": roles_needed[len(team_roles):],
                "missing_count": missing_count,
            })
            warnings.append(CoordinatorWarning(
                code="ROLE_UNASSIGNED",
                message=f"步骤 '{step.name}' 缺少 {missing_count} 个角色",
                severity="warning",
                related_step=step.id,
            ))

        # 确定协作模式
        cooperation_mode = _determine_cooperation_mode(step, len(team_roles))

        step_assignments.append(StepAssignment(
            step_id=step.id,
            step_name=step.name,
            sequence=step.sequence,
            teams=team_roles,
            cooperation_mode=cooperation_mode,
            depends_on=step_dependencies.get(step.id, []),
            estimated_duration=step.duration_minutes,
            completion_criteria=step.completion_criteria,
            safety_notes=step.safety_notes,
        ))

    elapsed_ms = int((time.time() - start_time) * 1000)

    total_assignments = sum(len(sa.teams) for sa in step_assignments)
    logger.info(
        f"[TaskCoordinator] 角色分配完成: "
        f"steps={len(step_assignments)}, "
        f"assignments={total_assignments}, "
        f"unassigned={len(unassigned_roles)}"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["assign_roles"]
    trace["total_assignments"] = total_assignments

    return {
        "step_assignments": step_assignments,
        "unassigned_roles": unassigned_roles,
        "warnings": warnings,
        "trace": trace,
        "current_phase": "match_equipment",
        "execution_time_ms": state.get("execution_time_ms", 0) + elapsed_ms,
    }
