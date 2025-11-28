"""
STOMP WebSocket连接管理
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Callable, Awaitable
from uuid import UUID, uuid4
from dataclasses import dataclass, field

from fastapi import WebSocket

from .frames import StompFrame, StompCommand, connected_frame, message_frame, receipt_frame, error_frame


logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """订阅信息"""
    id: str
    destination: str
    ack_mode: str = "auto"  # auto, client, client-individual
    pending_acks: set[str] = field(default_factory=set)


@dataclass
class StompConnection:
    """STOMP连接"""
    websocket: WebSocket
    session_id: str
    client_id: Optional[str] = None
    scenario_id: Optional[UUID] = None
    
    # STOMP协议状态
    version: str = "1.2"
    heart_beat_client: int = 0  # 客户端心跳间隔(ms)
    heart_beat_server: int = 10000  # 服务端心跳间隔(ms)
    
    # 订阅管理
    subscriptions: dict[str, Subscription] = field(default_factory=dict)
    
    # 连接状态
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    is_connected: bool = False
    
    # 消息计数器
    _message_counter: int = 0
    
    # SockJS 模式标志
    sockjs_mode: bool = False
    
    def __post_init__(self):
        if not self.session_id:
            self.session_id = str(uuid4())
    
    async def send_frame(self, frame: StompFrame):
        """发送STOMP帧"""
        from starlette.websockets import WebSocketState
        
        self.last_activity = datetime.utcnow()
        try:
            # 检查 WebSocket application_state（Starlette 用此属性判断连接状态）
            if self.websocket.application_state != WebSocketState.CONNECTED:
                logger.warning(f"WebSocket not connected for {self.session_id}, state={self.websocket.application_state}")
                self.is_connected = False
                return
            
            if self.sockjs_mode:
                # SockJS 格式: a["STOMP帧文本"]
                stomp_text = frame.to_text()
                await self.websocket.send_text('a' + json.dumps([stomp_text]))
            else:
                # 原生 WebSocket 使用 JSON 格式
                await self.websocket.send_text(frame.to_json())
        except RuntimeError as e:
            # WebSocket 已断开
            if "not connected" in str(e).lower() or "accept" in str(e).lower():
                logger.warning(f"WebSocket disconnected for {self.session_id}: {e}")
                self.is_connected = False
            else:
                logger.error(f"Failed to send frame to {self.session_id}: {e}")
                raise
        except Exception as e:
            logger.error(f"Failed to send frame to {self.session_id}: {e}")
            raise
    
    async def send_connected(self):
        """发送CONNECTED帧"""
        frame = connected_frame(
            version=self.version,
            heart_beat=f"{self.heart_beat_server},{self.heart_beat_server}",
        )
        frame.headers["session"] = self.session_id
        logger.info(f"Sending CONNECTED frame: {repr(frame.to_text()[:200])}")
        await self.send_frame(frame)
        self.is_connected = True
    
    async def send_message(self, destination: str, body: str, subscription_id: Optional[str] = None):
        """发送MESSAGE帧"""
        self._message_counter += 1
        message_id = f"{self.session_id}-{self._message_counter}"
        
        # 查找匹配的订阅
        sub_id = subscription_id
        if not sub_id:
            for sub in self.subscriptions.values():
                if self._match_destination(sub.destination, destination):
                    sub_id = sub.id
                    break
        
        if not sub_id:
            logger.warning(f"No subscription for destination: {destination}")
            return
        
        frame = message_frame(
            destination=destination,
            message_id=message_id,
            subscription=sub_id,
            body=body,
        )
        
        subscription = self.subscriptions.get(sub_id)
        if subscription and subscription.ack_mode != "auto":
            subscription.pending_acks.add(message_id)
        
        await self.send_frame(frame)
    
    async def send_receipt(self, receipt_id: str):
        """发送RECEIPT帧"""
        await self.send_frame(receipt_frame(receipt_id))
    
    async def send_error(self, message: str, details: str = ""):
        """发送ERROR帧"""
        await self.send_frame(error_frame(message, details))
    
    def add_subscription(self, sub_id: str, destination: str, ack_mode: str = "auto"):
        """添加订阅"""
        self.subscriptions[sub_id] = Subscription(
            id=sub_id,
            destination=destination,
            ack_mode=ack_mode,
        )
        logger.info(f"Subscription added: {sub_id} -> {destination}")
    
    def remove_subscription(self, sub_id: str) -> Optional[Subscription]:
        """移除订阅"""
        sub = self.subscriptions.pop(sub_id, None)
        if sub:
            logger.info(f"Subscription removed: {sub_id}")
        return sub
    
    def ack_message(self, message_id: str):
        """确认消息"""
        for sub in self.subscriptions.values():
            if message_id in sub.pending_acks:
                sub.pending_acks.discard(message_id)
                logger.debug(f"Message ACKed: {message_id}")
                return True
        return False
    
    def nack_message(self, message_id: str):
        """否定确认消息"""
        for sub in self.subscriptions.values():
            if message_id in sub.pending_acks:
                sub.pending_acks.discard(message_id)
                logger.debug(f"Message NACKed: {message_id}")
                return True
        return False
    
    def get_subscribed_destinations(self) -> list[str]:
        """获取所有订阅的目标"""
        return [sub.destination for sub in self.subscriptions.values()]
    
    def is_subscribed_to(self, destination: str) -> bool:
        """检查是否订阅了指定目标"""
        for sub in self.subscriptions.values():
            if self._match_destination(sub.destination, destination):
                return True
        return False
    
    @staticmethod
    def _match_destination(pattern: str, destination: str) -> bool:
        """匹配目标（支持通配符）"""
        # 简单实现：完全匹配或前缀匹配
        if pattern == destination:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return destination.startswith(prefix)
        if pattern.endswith(".>"):
            prefix = pattern[:-2]
            return destination.startswith(prefix)
        return False
    
    def update_activity(self):
        """更新活动时间"""
        self.last_activity = datetime.utcnow()
