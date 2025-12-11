"""
接收任务分配节点

验证和预处理来自 emergency_ai 的任务分配。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any

from ..state import TaskCoordinatorState
from ..schemas import CoordinatorWarning

logger = logging.getLogger(__name__)


def receive_allocation(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    接收任务分配节点

    验证输入数据，提取关键信息。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info(
        "[TaskCoordinator] 接收任务分配",
        extra={"event_id": state.get("event_id")}
    )
    start_time = time.time()

    task_allocation = state.get("task_allocation")
    warnings = list(state.get("warnings", []))
    errors = list(state.get("errors", []))

    # 验证必要字段
    if not task_allocation:
        errors.append("缺少任务分配信息")
        return {
            "errors": errors,
            "current_phase": "failed",
        }

    # 验证队伍信息
    allocated_teams = task_allocation.allocated_teams
    if not allocated_teams:
        warnings.append(CoordinatorWarning(
            code="NO_TEAMS",
            message="任务未分配队伍，将尝试从 SOP 推断所需队伍",
            severity="warning",
        ))

    # 验证灾害类型
    disaster_type = task_allocation.disaster_type
    if not disaster_type or disaster_type == "unknown":
        # 尝试从 disaster_info 获取
        disaster_info = state.get("disaster_info", {})
        disaster_type = disaster_info.get("disaster_type", "unknown")
        if disaster_type == "unknown":
            warnings.append(CoordinatorWarning(
                code="UNKNOWN_DISASTER_TYPE",
                message="未知灾害类型，将使用通用 SOP",
                severity="warning",
            ))

    elapsed_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"[TaskCoordinator] 任务接收完成: "
        f"task_id={task_allocation.task_id}, "
        f"disaster_type={disaster_type}, "
        f"teams={len(allocated_teams)}"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["receive_allocation"]
    trace["input_teams_count"] = len(allocated_teams)

    return {
        "warnings": warnings,
        "errors": errors,
        "trace": trace,
        "current_phase": "match_sop",
        "execution_time_ms": elapsed_ms,
    }
