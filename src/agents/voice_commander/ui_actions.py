"""
UI动作协议定义

定义语音助手响应中的前端UI联动动作。
前端需要监听 ai_response 消息中的 ui_actions 字段并执行相应操作。

协议版本: 1.0
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class UIActionType(str, Enum):
    """UI动作类型枚举"""
    # 地图操作
    MAP_FLY_TO = "map.flyTo"              # 飞行到实体或坐标
    MAP_HIGHLIGHT = "map.highlight"        # 高亮实体
    MAP_CLEAR_HIGHLIGHT = "map.clearHighlight"  # 清除高亮
    MAP_SHOW_ROUTE = "map.showRoute"      # 显示路径
    
    # 实体操作
    ENTITY_SHOW_DETAIL = "entity.showDetail"  # 显示实体详情面板
    ENTITY_SELECT = "entity.select"           # 选中实体
    
    # 面板操作
    PANEL_OPEN = "panel.open"             # 打开面板
    PANEL_CLOSE = "panel.close"           # 关闭面板
    
    # 通知
    NOTIFICATION_SHOW = "notification.show"  # 显示通知


class PanelType(str, Enum):
    """面板类型枚举"""
    TASK_LIST = "task_list"           # 任务列表面板
    TASK_DETAIL = "task_detail"       # 任务详情面板
    ENTITY_DETAIL = "entity_detail"   # 实体详情面板
    RESOURCE_LIST = "resource_list"   # 资源列表面板
    SITUATION = "situation"           # 态势面板


class NotificationLevel(str, Enum):
    """通知级别"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class UIAction(BaseModel):
    """UI动作基类"""
    action: UIActionType = Field(..., description="动作类型")
    
    class Config:
        use_enum_values = True


class MapFlyToAction(UIAction):
    """地图飞行定位动作"""
    action: UIActionType = UIActionType.MAP_FLY_TO
    entity_id: Optional[str] = Field(None, description="目标实体ID")
    coordinates: Optional[List[float]] = Field(None, description="目标坐标 [lng, lat]")
    zoom: Optional[int] = Field(14, description="缩放级别")
    duration: Optional[int] = Field(1000, description="动画时长(ms)")


class MapHighlightAction(UIAction):
    """地图高亮动作"""
    action: UIActionType = UIActionType.MAP_HIGHLIGHT
    entity_ids: List[str] = Field(..., description="要高亮的实体ID列表")
    color: Optional[str] = Field("#FF4444", description="高亮颜色")
    duration: Optional[int] = Field(5000, description="高亮持续时间(ms)，0表示永久")


class MapClearHighlightAction(UIAction):
    """清除地图高亮"""
    action: UIActionType = UIActionType.MAP_CLEAR_HIGHLIGHT


class EntityShowDetailAction(UIAction):
    """显示实体详情"""
    action: UIActionType = UIActionType.ENTITY_SHOW_DETAIL
    entity_id: str = Field(..., description="实体ID")
    entity_type: Optional[str] = Field(None, description="实体类型: team/vehicle/device")


class PanelOpenAction(UIAction):
    """打开面板"""
    action: UIActionType = UIActionType.PANEL_OPEN
    panel: PanelType = Field(..., description="面板类型")
    params: Optional[Dict[str, Any]] = Field(None, description="面板参数")


class PanelCloseAction(UIAction):
    """关闭面板"""
    action: UIActionType = UIActionType.PANEL_CLOSE
    panel: Optional[PanelType] = Field(None, description="要关闭的面板，None表示关闭当前面板")


class NotificationShowAction(UIAction):
    """显示通知"""
    action: UIActionType = UIActionType.NOTIFICATION_SHOW
    message: str = Field(..., description="通知内容")
    level: NotificationLevel = Field(NotificationLevel.INFO, description="通知级别")
    duration: Optional[int] = Field(3000, description="显示时长(ms)")


# 联合类型，用于类型注解
UIActionUnion = Union[
    MapFlyToAction,
    MapHighlightAction,
    MapClearHighlightAction,
    EntityShowDetailAction,
    PanelOpenAction,
    PanelCloseAction,
    NotificationShowAction,
]


class AIResponse(BaseModel):
    """
    AI响应结构
    
    语音WebSocket发送此结构给前端，包含文本回复和UI动作指令。
    """
    type: str = Field("ai_response", description="消息类型")
    text: str = Field(..., description="文本回复内容")
    ui_actions: List[Dict[str, Any]] = Field(default_factory=list, description="UI动作列表")
    context: Optional[Dict[str, Any]] = Field(None, description="上下文信息，用于连续对话")
    
    @classmethod
    def create(
        cls,
        text: str,
        ui_actions: Optional[List[UIActionUnion]] = None,
        mentioned_entities: Optional[List[str]] = None,
        mentioned_tasks: Optional[List[str]] = None,
    ) -> "AIResponse":
        """
        创建AI响应
        
        Args:
            text: 文本回复
            ui_actions: UI动作列表
            mentioned_entities: 提到的实体ID列表（用于上下文指代）
            mentioned_tasks: 提到的任务ID列表
        """
        actions_dict = []
        if ui_actions:
            for action in ui_actions:
                actions_dict.append(action.model_dump(exclude_none=True))
        
        context = None
        if mentioned_entities or mentioned_tasks:
            context = {
                "mentioned_entities": mentioned_entities or [],
                "mentioned_tasks": mentioned_tasks or [],
            }
        
        return cls(
            text=text,
            ui_actions=actions_dict,
            context=context,
        )


# 便捷工厂函数
def fly_to_entity(entity_id: str, zoom: int = 14) -> MapFlyToAction:
    """创建飞行到实体的动作"""
    return MapFlyToAction(entity_id=entity_id, zoom=zoom)


def fly_to_coordinates(lng: float, lat: float, zoom: int = 14) -> MapFlyToAction:
    """创建飞行到坐标的动作"""
    return MapFlyToAction(coordinates=[lng, lat], zoom=zoom)


def highlight_entities(entity_ids: List[str], duration: int = 5000) -> MapHighlightAction:
    """创建高亮实体的动作"""
    return MapHighlightAction(entity_ids=entity_ids, duration=duration)


def show_entity_detail(entity_id: str, entity_type: Optional[str] = None) -> EntityShowDetailAction:
    """创建显示实体详情的动作"""
    return EntityShowDetailAction(entity_id=entity_id, entity_type=entity_type)


def open_panel(panel: PanelType, **params: Any) -> PanelOpenAction:
    """创建打开面板的动作"""
    return PanelOpenAction(panel=panel, params=params if params else None)


def show_notification(message: str, level: NotificationLevel = NotificationLevel.INFO) -> NotificationShowAction:
    """创建显示通知的动作"""
    return NotificationShowAction(message=message, level=level)
