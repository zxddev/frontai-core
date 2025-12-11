"""
指令生成节点

将步骤分配转换为最终的步骤级指令输出。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import TaskCoordinatorState
from ..schemas import (
    StepInstruction,
    TaskCoordinatorOutput,
    TeamRole,
)

logger = logging.getLogger(__name__)


def _convert_to_instruction(
    assignment,
) -> StepInstruction:
    """
    将 StepAssignment 转换为 StepInstruction

    Args:
        assignment: 步骤分配

    Returns:
        步骤指令
    """
    return StepInstruction(
        step_id=assignment.step_id,
        step_name=assignment.step_name,
        sequence=assignment.sequence,
        teams=assignment.teams,
        cooperation_mode=assignment.cooperation_mode.value,
        depends_on=assignment.depends_on,
        estimated_duration=assignment.estimated_duration,
        completion_criteria=assignment.completion_criteria,
        safety_notes=assignment.safety_notes,
    )


def _calculate_total_duration(instructions: List[StepInstruction]) -> int:
    """
    计算总预估时长

    考虑步骤依赖关系，并行步骤取最长时间。

    Args:
        instructions: 步骤指令列表

    Returns:
        总时长（分钟）
    """
    if not instructions:
        return 0

    # 简化计算：按序列号分组，同序列号的取最大值
    sequence_durations: Dict[int, int] = {}
    for inst in instructions:
        seq = inst.sequence
        if seq not in sequence_durations:
            sequence_durations[seq] = inst.estimated_duration
        else:
            # 同序列号可能并行，取最大值
            sequence_durations[seq] = max(
                sequence_durations[seq],
                inst.estimated_duration,
            )

    return sum(sequence_durations.values())


async def generate_instructions(state: TaskCoordinatorState) -> Dict[str, Any]:
    """
    指令生成节点

    将步骤分配转换为最终输出。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段
    """
    logger.info("[TaskCoordinator] 生成步骤指令")
    start_time = time.time()

    step_assignments = state.get("step_assignments", [])
    matched_sop = state.get("matched_sop")
    task_allocation = state.get("task_allocation")
    warnings = list(state.get("warnings", []))

    if not step_assignments:
        return {
            "errors": state.get("errors", []) + ["无步骤分配"],
            "current_phase": "failed",
        }

    # 转换为指令
    instructions = [
        _convert_to_instruction(assignment)
        for assignment in step_assignments
    ]

    # 按序列号排序
    instructions.sort(key=lambda x: x.sequence)

    # 计算总时长
    total_duration = _calculate_total_duration(instructions)

    # 提取警告消息
    warning_messages = [w.message for w in warnings]

    # 构建最终输出
    output = TaskCoordinatorOutput(
        task_id=task_allocation.task_id if task_allocation else "unknown",
        task_name=task_allocation.task_name if task_allocation else "未知任务",
        sop_template=matched_sop.id if matched_sop else "unknown",
        total_steps=len(instructions),
        estimated_duration_minutes=total_duration,
        step_instructions=instructions,
        warnings=warning_messages,
    )

    elapsed_ms = int((time.time() - start_time) * 1000)

    total_teams = sum(len(inst.teams) for inst in instructions)
    logger.info(
        f"[TaskCoordinator] 指令生成完成: "
        f"steps={len(instructions)}, "
        f"teams={total_teams}, "
        f"duration={total_duration}min"
    )

    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_instructions"]
    trace["output_steps"] = len(instructions)
    trace["output_duration"] = total_duration

    return {
        "final_output": output,
        "warnings": warnings,
        "trace": trace,
        "current_phase": "completed",
        "execution_time_ms": state.get("execution_time_ms", 0) + elapsed_ms,
    }
