"""
预警监测智能体模块

功能：
- 接收第三方灾情数据
- 分析对车辆和救援队伍的影响
- 生成预警决策
- 通过WebSocket推送预警消息
- 支持人工选择绕行（Human in the Loop）
"""
from .agent import EarlyWarningAgent, get_early_warning_agent
from .state import (
    EarlyWarningState,
    create_initial_state,
    DisasterSituation,
    AffectedObject,
    WarningDecision,
    WarningRecord,
    WarningLevel,
    WarningStatus,
    ResponseAction,
)
from .schemas import (
    DisasterUpdateRequest,
    DisasterSituationResponse,
    WarningRecordResponse,
    WarningListResponse,
    WarningAcknowledgeRequest,
    WarningRespondRequest,
    DetourOption,
    DetourOptionsResponse,
    ConfirmDetourRequest,
    DisasterUpdateResponse,
    WarningNotification,
)
from .repository import DisasterRepository, WarningRepository

__all__ = [
    # Agent
    "EarlyWarningAgent",
    "get_early_warning_agent",
    # State
    "EarlyWarningState",
    "create_initial_state",
    "DisasterSituation",
    "AffectedObject",
    "WarningDecision",
    "WarningRecord",
    "WarningLevel",
    "WarningStatus",
    "ResponseAction",
    # Schemas
    "DisasterUpdateRequest",
    "DisasterSituationResponse",
    "WarningRecordResponse",
    "WarningListResponse",
    "WarningAcknowledgeRequest",
    "WarningRespondRequest",
    "DetourOption",
    "DetourOptionsResponse",
    "ConfirmDetourRequest",
    "DisasterUpdateResponse",
    "WarningNotification",
    # Repository
    "DisasterRepository",
    "WarningRepository",
]
