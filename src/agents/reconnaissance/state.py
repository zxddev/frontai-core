"""无人设备首次侦察智能体状态定义

该状态用于在LangGraph中在各节点之间传递数据。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ReconTarget(TypedDict, total=False):
    """侦察目标

    对应一个风险区域或从风险区域细分出的扇区/关键设施。
    """

    target_id: str
    risk_area_id: Optional[str]
    name: str
    geometry: Dict[str, Any]
    features: Dict[str, Any]
    score: float
    priority: str
    reasons: List[str]


class DeviceInfo(TypedDict, total=False):
    """参与本次侦察的无人设备简要信息"""

    device_id: str
    code: str
    name: str
    device_type: str  # drone/dog/ship/robot
    env_type: str  # air/land/sea - 设备作业环境
    in_vehicle_id: Optional[str]
    status: str


class DeviceAssignment(TypedDict, total=False):
    """设备到目标的初始分配结果"""

    device_id: str
    device_name: str
    device_type: str
    target_id: str
    target_name: str
    priority: str
    reason: str  # 分配理由


class ReconMissionStep(TypedDict, total=False):
    """单个侦察任务的执行步骤"""

    step_id: str
    step_name: str  # 步骤名称，如"起飞准备"、"区域扫描"
    description: str  # 步骤描述
    duration_minutes: int  # 预计耗时（分钟）
    key_actions: List[str]  # 关键动作列表


class ReconMission(TypedDict, total=False):
    """单个设备的侦察任务方案"""

    mission_id: str
    device_id: str
    device_name: str
    device_type: str
    target_id: str
    target_name: str
    priority: str

    # 侦察方案详情
    mission_objective: str  # 任务目标
    recon_focus: List[str]  # 侦察重点（关注什么）
    recon_method: str  # 侦察方法（如何执行）
    route_description: str  # 路线描述
    altitude_or_depth: str  # 飞行高度/水面距离（适用时）
    estimated_duration_minutes: int  # 预计总耗时
    steps: List[ReconMissionStep]  # 执行步骤

    # 协同配合
    coordination_notes: str  # 与其他设备的协同说明
    handoff_conditions: str  # 交接条件（如发现情况后如何处理）

    # 安全注意事项
    safety_notes: List[str]  # 安全注意事项
    abort_conditions: List[str]  # 中止条件


class ReconPlan(TypedDict, total=False):
    """完整的侦察执行方案"""

    plan_id: str
    scenario_id: str
    created_at: str

    # 方案概述
    summary: str  # 方案概述
    total_duration_minutes: int  # 总预计耗时
    phase_count: int  # 分几个阶段

    # 任务列表
    missions: List[ReconMission]

    # 整体协同方案
    coordination_strategy: str  # 整体协同策略
    communication_plan: str  # 通讯方案
    contingency_plan: str  # 应急预案

    # 阶段划分
    phases: List[Dict[str, Any]]  # 阶段列表，每阶段包含哪些任务


class ReconState(TypedDict, total=False):
    """无人设备首次侦察智能体状态"""

    # 输入
    scenario_id: str
    event_id: Optional[str]

    # 上下文
    risk_areas: List[Dict[str, Any]]
    devices: List[DeviceInfo]

    # 中间结果
    candidate_targets: List[ReconTarget]

    # 输出
    scored_targets: List[ReconTarget]
    assignments: List[DeviceAssignment]
    explanation: str
    recon_plan: Optional[ReconPlan]  # 侦察执行方案

    # 追踪
    errors: List[str]
    trace: Dict[str, Any]
    current_phase: str


__all__ = [
    "ReconTarget",
    "DeviceInfo",
    "DeviceAssignment",
    "ReconMissionStep",
    "ReconMission",
    "ReconPlan",
    "ReconState",
]
