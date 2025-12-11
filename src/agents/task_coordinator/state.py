"""
Task Coordinator 状态定义

使用 TypedDict 定义 LangGraph 状态。
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, TypedDict

from .schemas import (
    TaskAllocation,
    SOPTemplate,
    SOPStep,
    StepAssignment,
    TaskCoordinatorOutput,
    CoordinatorWarning,
)


class TaskCoordinatorState(TypedDict, total=False):
    """
    Task Coordinator Agent 状态

    遵循 LangGraph 状态设计原则：
    - 每个阶段只写自己的输出字段
    - 状态字段按流程阶段组织
    """

    # ========== 输入 ==========
    event_id: str                                    # 事件ID
    task_allocation: TaskAllocation                  # 来自 emergency_ai 的任务分配
    disaster_info: Optional[Dict[str, Any]]          # 灾情信息

    # ========== 阶段1: SOP匹配 ==========
    matched_sop: Optional[SOPTemplate]               # 匹配到的 SOP 模板
    sop_match_score: float                           # 匹配分数
    sop_match_reason: str                            # 匹配原因

    # ========== 阶段2: 步骤分解 ==========
    sop_steps: List[SOPStep]                         # SOP 步骤列表（从 Neo4j 加载）
    step_dependencies: Dict[str, List[str]]          # 步骤依赖关系 {step_id: [depends_on_ids]}

    # ========== 阶段3: 角色分配 ==========
    step_assignments: List[StepAssignment]           # 步骤分配结果
    unassigned_roles: List[Dict[str, Any]]           # 未能分配的角色

    # ========== 阶段4: 设备匹配 ==========
    equipment_assignments: Dict[str, List[str]]      # 设备分配 {team_id: [equipment_list]}
    equipment_gaps: List[Dict[str, Any]]             # 设备缺口

    # ========== 阶段5: 指令生成 ==========
    final_output: Optional[TaskCoordinatorOutput]    # 最终输出

    # ========== 元数据 ==========
    current_phase: str                               # 当前阶段
    warnings: List[CoordinatorWarning]               # 警告列表
    errors: List[str]                                # 错误列表
    trace: Dict[str, Any]                            # 追踪信息
    execution_time_ms: int                           # 执行时间
