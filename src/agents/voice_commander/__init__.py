"""
语音指挥Agent模块

提供语音交互的空间查询、任务状态查询和资源状态查询能力。

模块结构:
- semantic_router.py - 语义路由层（毫秒级意图分流）
- spatial_graph.py - 空间查询Agent（位置、距离、区域状态）
- task_agent.py - 任务查询Agent（任务进度、状态统计）
- resource_agent.py - 资源查询Agent（队伍状态、可用资源）
- ui_actions.py - UI联动动作协议定义
- state.py - 状态定义
- schemas.py - 数据模型
- tools/ - 工具集
"""

from .state import SpatialAgentState, CommanderAgentState
from .schemas import (
    EntityLocation,
    NearestUnitResult,
    AreaStatus,
    TacticalCommand,
    PendingCommand,
)
from .ui_actions import (
    AIResponse,
    UIActionType,
    PanelType,
    NotificationLevel,
)

__all__ = [
    "SpatialAgentState",
    "CommanderAgentState",
    "EntityLocation",
    "NearestUnitResult",
    "AreaStatus",
    "TacticalCommand",
    "PendingCommand",
    "AIResponse",
    "UIActionType",
    "PanelType",
    "NotificationLevel",
]
