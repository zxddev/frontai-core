"""
任务智能分发Agent

基于LangGraph实现，支持双模式运行：
- Mode 1: 初始分配 - 将方案任务批量分配给执行者
- Mode 2: 动态调整 - 响应事件变化进行重新分配，支持human-in-the-loop
"""
from __future__ import annotations

from .agent import TaskDispatchAgent, get_task_dispatch_agent
from .state import (
    TaskDispatchState,
    TaskAssignment,
    DispatchEvent,
    DispatchEventType,
    DispatchAction,
    DispatchActionType,
    ExecutorInfo,
    create_initial_dispatch_state,
    create_dynamic_dispatch_state,
)

__all__ = [
    "TaskDispatchAgent",
    "get_task_dispatch_agent",
    "TaskDispatchState",
    "TaskAssignment",
    "DispatchEvent",
    "DispatchEventType",
    "DispatchAction",
    "DispatchActionType",
    "ExecutorInfo",
    "create_initial_dispatch_state",
    "create_dynamic_dispatch_state",
]
