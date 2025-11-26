"""
Agent状态基类

定义共享的状态类型和工具
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from typing_extensions import TypedDict


class BaseState(TypedDict, total=False):
    """
    Agent状态基类
    
    所有Agent状态必须继承此类，确保包含追踪信息
    """
    # 标识
    task_id: str
    
    # 追踪信息
    trace: Dict[str, Any]
    errors: List[str]
    
    # 时间戳
    started_at: datetime
    completed_at: Optional[datetime]


class TraceInfo(TypedDict, total=False):
    """追踪信息结构"""
    algorithms_used: List[str]
    nodes_executed: List[str]
    execution_time_ms: float
    model_version: str
