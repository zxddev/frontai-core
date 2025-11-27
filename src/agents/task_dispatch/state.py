"""
任务智能分发状态定义

定义TaskDispatchAgent的状态类型，支持双模式运行：
- Mode 1: 初始分配（批量处理方案）
- Mode 2: 动态调整（响应事件变化）
"""
from __future__ import annotations

from typing import TypedDict, Annotated, List, Dict, Any, Optional, Literal
from uuid import UUID
from datetime import datetime
from enum import Enum

from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


# ============================================================================
# 枚举定义
# ============================================================================

class DispatchEventType(str, Enum):
    """分发事件类型"""
    TASK_REJECTED = "task_rejected"           # 执行者拒绝任务
    TASK_FAILED = "task_failed"               # 任务执行失败
    TASK_TIMEOUT = "task_timeout"             # 任务执行超时
    RESOURCE_UNAVAILABLE = "resource_unavailable"  # 资源不可用
    NEW_URGENT_TASK = "new_urgent_task"       # 新紧急任务
    PRIORITY_CHANGE = "priority_change"       # 优先级变更
    RESOURCE_STATUS_CHANGE = "resource_status_change"  # 资源状态变化


class DispatchActionType(str, Enum):
    """分发行动类型"""
    REASSIGN = "reassign"                     # 重新分配任务
    RETRY = "retry"                           # 重试当前分配
    ESCALATE = "escalate"                     # 上报人工处理
    PREEMPT = "preempt"                       # 抢占其他任务资源
    WAIT = "wait"                             # 等待
    CANCEL = "cancel"                         # 取消任务


class AssignmentStatus(str, Enum):
    """分配状态"""
    PENDING = "pending"                       # 待分配
    ASSIGNED = "assigned"                     # 已分配
    ACCEPTED = "accepted"                     # 已接受
    IN_PROGRESS = "in_progress"               # 执行中
    COMPLETED = "completed"                   # 已完成
    FAILED = "failed"                         # 失败
    REJECTED = "rejected"                     # 被拒绝


# ============================================================================
# 数据类型定义
# ============================================================================

class TaskAssignment(TypedDict):
    """任务分配记录"""
    assignment_id: str                        # 分配ID
    task_id: str                              # 任务ID
    task_name: str                            # 任务名称
    task_priority: str                        # 任务优先级 critical/high/medium/low
    executor_id: str                          # 执行者ID
    executor_name: str                        # 执行者名称
    executor_type: str                        # 执行者类型 team/vehicle/equipment
    status: str                               # 分配状态
    scheduled_start: Optional[str]            # 计划开始时间
    scheduled_end: Optional[str]              # 计划结束时间
    actual_start: Optional[str]               # 实际开始时间
    instructions: str                         # 执行指令
    created_at: str                           # 创建时间
    updated_at: str                           # 更新时间


class DispatchEvent(TypedDict):
    """分发事件"""
    event_id: str                             # 事件ID
    event_type: str                           # 事件类型
    task_id: Optional[str]                    # 关联任务ID
    executor_id: Optional[str]                # 关联执行者ID
    reason: str                               # 事件原因
    details: Dict[str, Any]                   # 事件详情
    occurred_at: str                          # 发生时间
    priority: str                             # 事件优先级


class DispatchAction(TypedDict):
    """分发行动"""
    action_type: str                          # 行动类型
    task_id: str                              # 目标任务ID
    old_executor_id: Optional[str]            # 原执行者ID
    new_executor_id: Optional[str]            # 新执行者ID
    reasoning: str                            # 决策理由
    confidence: float                         # 置信度 0-1
    estimated_impact: Dict[str, Any]          # 预估影响


class ExecutorInfo(TypedDict):
    """执行者信息"""
    executor_id: str                          # 执行者ID
    executor_name: str                        # 执行者名称
    executor_type: str                        # 类型 team/vehicle/equipment
    capabilities: List[str]                   # 能力列表
    current_load: int                         # 当前负载（任务数）
    max_load: int                             # 最大负载
    status: str                               # 状态 available/busy/offline
    location: Dict[str, float]                # 位置 {lat, lng}
    eta_minutes: Optional[int]                # 预计到达时间


class SchemeTaskInfo(TypedDict):
    """方案中的任务信息（来自EmergencyAI）"""
    task_id: str                              # 任务ID
    task_name: str                            # 任务名称
    phase: str                                # 所属阶段
    priority: str                             # 优先级
    sequence: int                             # 执行顺序
    depends_on: List[str]                     # 依赖任务
    required_capabilities: List[str]          # 所需能力
    duration_min: int                         # 预计时长(分钟)
    golden_hour: Optional[int]                # 黄金救援时间窗口


# ============================================================================
# 主状态定义
# ============================================================================

class TaskDispatchState(TypedDict):
    """
    任务智能分发状态
    
    支持双模式运行：
    - Mode 1: 初始分配（从方案生成分配）
    - Mode 2: 动态调整（响应事件变化）
    """
    # ========== 上下文信息 ==========
    event_id: str                             # 应急事件ID
    scheme_id: Optional[str]                  # 方案ID（初始分配时必需）
    mode: str                                 # 运行模式 initial/dynamic
    
    # ========== 方案输入（Mode 1: 初始分配） ==========
    scheme_tasks: List[SchemeTaskInfo]        # 方案任务列表
    allocated_teams: List[Dict[str, Any]]     # 已分配的救援队伍（来自EmergencyAI）
    
    # ========== 当前分配状态 ==========
    current_assignments: List[TaskAssignment] # 当前任务-执行者映射
    available_executors: List[ExecutorInfo]   # 可用执行者列表
    
    # ========== 事件处理（Mode 2: 动态调整） ==========
    pending_events: List[DispatchEvent]       # 待处理事件队列
    current_event: Optional[DispatchEvent]    # 当前处理的事件
    
    # ========== LLM对话 ==========
    messages: Annotated[List[BaseMessage], add_messages]  # 消息历史
    
    # ========== 决策结果 ==========
    proposed_action: Optional[DispatchAction] # LLM建议的行动
    requires_human_approval: bool             # 是否需要人工确认
    human_decision: Optional[str]             # 人工决策结果 approve/reject/modify
    
    # ========== 执行结果 ==========
    dispatch_orders: List[Dict[str, Any]]     # 生成的调度指令
    notifications_sent: List[Dict[str, Any]]  # 已发送的通知
    
    # ========== 追踪信息 ==========
    trace: Dict[str, Any]                     # 执行追踪
    errors: List[str]                         # 错误列表
    current_phase: str                        # 当前阶段
    execution_time_ms: int                    # 执行耗时


def create_initial_dispatch_state(
    event_id: str,
    scheme_id: str,
    scheme_tasks: List[Dict[str, Any]],
    allocated_teams: List[Dict[str, Any]],
) -> TaskDispatchState:
    """
    创建初始分配状态（Mode 1）
    
    Args:
        event_id: 应急事件ID
        scheme_id: 方案ID
        scheme_tasks: 方案任务列表
        allocated_teams: 已分配的救援队伍
        
    Returns:
        初始化的TaskDispatchState
    """
    return TaskDispatchState(
        event_id=event_id,
        scheme_id=scheme_id,
        mode="initial",
        scheme_tasks=scheme_tasks,
        allocated_teams=allocated_teams,
        current_assignments=[],
        available_executors=[],
        pending_events=[],
        current_event=None,
        messages=[],
        proposed_action=None,
        requires_human_approval=False,
        human_decision=None,
        dispatch_orders=[],
        notifications_sent=[],
        trace={
            "phases_executed": [],
            "llm_calls": 0,
            "db_calls": 0,
            "algorithms_used": [],
            "decisions_made": [],
        },
        errors=[],
        current_phase="init",
        execution_time_ms=0,
    )


def create_dynamic_dispatch_state(
    event_id: str,
    current_assignments: List[TaskAssignment],
    dispatch_event: DispatchEvent,
) -> TaskDispatchState:
    """
    创建动态调整状态（Mode 2）
    
    Args:
        event_id: 应急事件ID
        current_assignments: 当前分配状态
        dispatch_event: 触发的分发事件
        
    Returns:
        初始化的TaskDispatchState
    """
    return TaskDispatchState(
        event_id=event_id,
        scheme_id=None,
        mode="dynamic",
        scheme_tasks=[],
        allocated_teams=[],
        current_assignments=current_assignments,
        available_executors=[],
        pending_events=[dispatch_event],
        current_event=dispatch_event,
        messages=[],
        proposed_action=None,
        requires_human_approval=False,
        human_decision=None,
        dispatch_orders=[],
        notifications_sent=[],
        trace={
            "phases_executed": [],
            "llm_calls": 0,
            "db_calls": 0,
            "algorithms_used": [],
            "decisions_made": [],
            "trigger_event": dispatch_event["event_id"],
        },
        errors=[],
        current_phase="init",
        execution_time_ms=0,
    )
