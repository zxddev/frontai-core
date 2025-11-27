"""
任务智能分发节点模块

包含两种模式的处理节点：
- Mode 1: 初始分配节点
- Mode 2: 动态调整节点
"""
from __future__ import annotations

from .initial_dispatch import (
    extract_capability_needs,
    query_available_executors,
    match_executors,
    schedule_tasks,
    generate_dispatch_orders,
)

from .analyze_event import analyze_dispatch_event
from .decide_action import decide_dispatch_action
from .execute_action import execute_dispatch_action
from .notify import notify_stakeholders

__all__ = [
    # Mode 1: 初始分配
    "extract_capability_needs",
    "query_available_executors",
    "match_executors",
    "schedule_tasks",
    "generate_dispatch_orders",
    # Mode 2: 动态调整
    "analyze_dispatch_event",
    "decide_dispatch_action",
    "execute_dispatch_action",
    "notify_stakeholders",
]
