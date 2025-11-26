"""
WebSocket 连接管理器

功能：
- 连接管理（连接/断开/心跳）
- 频道订阅（events/tasks/telemetry/alerts等）
- 消息广播（单播/组播/广播）
- 断线重连支持（消息回放）
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class WSMessage:
    """WebSocket消息"""
    id: str
    channel: str
    event_type: str
    payload: dict
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "channel": self.channel,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class WSConnection:
    """WebSocket连接"""
    websocket: WebSocket
    client_id: str
    scenario_id: Optional[UUID] = None
    subscribed_channels: set = field(default_factory=set)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    last_msg_id: Optional[str] = None


class ConnectionManager:
    """WebSocket连接管理器"""
    
    # 支持的频道
    CHANNELS = {
        "events",       # 事件更新
        "tasks",        # 任务更新
        "schemes",      # 方案更新
        "telemetry",    # 遥测数据（位置更新）
        "alerts",       # 告警通知
        "messages",     # 指挥消息
        "entities",     # 地图实体更新
    }
    
    def __init__(self):
        # client_id -> WSConnection
        self.connections: dict[str, WSConnection] = {}
        # scenario_id -> set of client_ids
        self.scenario_connections: dict[UUID, set[str]] = defaultdict(set)
        # channel -> set of client_ids
        self.channel_subscriptions: dict[str, set[str]] = defaultdict(set)
        # 消息历史（用于断线重连回放）
        self.message_history: list[WSMessage] = []
        self.max_history_size = 1000
        self._msg_counter = 0
    
    async def connect(
        self, 
        websocket: WebSocket, 
        client_id: str, 
        scenario_id: Optional[UUID] = None
    ) -> WSConnection:
        """建立连接"""
        await websocket.accept()
        
        conn = WSConnection(
            websocket=websocket,
            client_id=client_id,
            scenario_id=scenario_id,
        )
        self.connections[client_id] = conn
        
        if scenario_id:
            self.scenario_connections[scenario_id].add(client_id)
        
        logger.info(f"WebSocket connected: {client_id}, scenario: {scenario_id}")
        
        # 发送连接确认
        await self._send(websocket, {
            "type": "connected",
            "client_id": client_id,
            "scenario_id": str(scenario_id) if scenario_id else None,
            "available_channels": list(self.CHANNELS),
        })
        
        return conn
    
    def disconnect(self, client_id: str):
        """断开连接"""
        conn = self.connections.pop(client_id, None)
        if conn:
            if conn.scenario_id:
                self.scenario_connections[conn.scenario_id].discard(client_id)
            for channel in conn.subscribed_channels:
                self.channel_subscriptions[channel].discard(client_id)
            logger.info(f"WebSocket disconnected: {client_id}")
    
    async def subscribe(self, client_id: str, channels: list[str]) -> list[str]:
        """订阅频道"""
        conn = self.connections.get(client_id)
        if not conn:
            return []
        
        subscribed = []
        for channel in channels:
            if channel in self.CHANNELS:
                conn.subscribed_channels.add(channel)
                self.channel_subscriptions[channel].add(client_id)
                subscribed.append(channel)
        
        logger.info(f"Client {client_id} subscribed to: {subscribed}")
        return subscribed
    
    async def unsubscribe(self, client_id: str, channels: list[str]) -> list[str]:
        """取消订阅"""
        conn = self.connections.get(client_id)
        if not conn:
            return []
        
        unsubscribed = []
        for channel in channels:
            if channel in conn.subscribed_channels:
                conn.subscribed_channels.discard(channel)
                self.channel_subscriptions[channel].discard(client_id)
                unsubscribed.append(channel)
        
        return unsubscribed
    
    async def broadcast_to_channel(
        self, 
        channel: str, 
        event_type: str, 
        payload: dict,
        scenario_id: Optional[UUID] = None,
    ):
        """向频道广播消息"""
        msg = self._create_message(channel, event_type, payload)
        self._add_to_history(msg)
        
        client_ids = self.channel_subscriptions.get(channel, set())
        
        # 如果指定了scenario_id，只发送给该场景的客户端
        if scenario_id:
            scenario_clients = self.scenario_connections.get(scenario_id, set())
            client_ids = client_ids & scenario_clients
        
        for client_id in client_ids:
            await self._send_to_client(client_id, msg)
    
    async def broadcast_to_scenario(
        self, 
        scenario_id: UUID, 
        channel: str, 
        event_type: str, 
        payload: dict
    ):
        """向指定场景的所有客户端广播"""
        await self.broadcast_to_channel(channel, event_type, payload, scenario_id)
    
    async def send_to_client(
        self, 
        client_id: str, 
        channel: str, 
        event_type: str, 
        payload: dict
    ):
        """向指定客户端发送消息"""
        msg = self._create_message(channel, event_type, payload)
        await self._send_to_client(client_id, msg)
    
    async def replay_messages(self, client_id: str, last_msg_id: str) -> int:
        """回放错过的消息（断线重连）"""
        conn = self.connections.get(client_id)
        if not conn:
            return 0
        
        # 找到last_msg_id之后的消息
        replay_start = False
        replayed = 0
        
        for msg in self.message_history:
            if replay_start:
                if msg.channel in conn.subscribed_channels:
                    await self._send_to_client(client_id, msg)
                    replayed += 1
            elif msg.id == last_msg_id:
                replay_start = True
        
        logger.info(f"Replayed {replayed} messages to {client_id}")
        return replayed
    
    async def heartbeat(self, client_id: str):
        """心跳更新"""
        conn = self.connections.get(client_id)
        if conn:
            conn.last_heartbeat = datetime.utcnow()
            await self._send(conn.websocket, {"type": "pong"})
    
    def _create_message(self, channel: str, event_type: str, payload: dict) -> WSMessage:
        """创建消息"""
        self._msg_counter += 1
        return WSMessage(
            id=f"msg_{self._msg_counter}_{datetime.utcnow().timestamp()}",
            channel=channel,
            event_type=event_type,
            payload=payload,
        )
    
    def _add_to_history(self, msg: WSMessage):
        """添加到消息历史"""
        self.message_history.append(msg)
        if len(self.message_history) > self.max_history_size:
            self.message_history = self.message_history[-self.max_history_size:]
    
    async def _send_to_client(self, client_id: str, msg: WSMessage):
        """发送消息给客户端"""
        conn = self.connections.get(client_id)
        if conn:
            try:
                await self._send(conn.websocket, msg.to_dict())
                conn.last_msg_id = msg.id
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def _send(self, websocket: WebSocket, data: dict):
        """发送JSON数据"""
        await websocket.send_json(data)


# 全局连接管理器实例
ws_manager = ConnectionManager()


# ============================================================================
# 便捷广播函数（供业务模块调用）
# ============================================================================

async def broadcast_event_update(scenario_id: UUID, event_type: str, event_data: dict):
    """广播事件更新"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "events", event_type, event_data
    )


async def broadcast_task_update(scenario_id: UUID, event_type: str, task_data: dict):
    """广播任务更新"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "tasks", event_type, task_data
    )


async def broadcast_scheme_update(scenario_id: UUID, event_type: str, scheme_data: dict):
    """广播方案更新"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "schemes", event_type, scheme_data
    )


async def broadcast_telemetry(scenario_id: UUID, entity_type: str, entity_id: str, location: dict):
    """广播遥测/位置更新（指定场景）"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "telemetry", "location_update", {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "location": location,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


async def broadcast_telemetry_batch(updates: list[dict]):
    """
    广播批量遥测更新（全局，不限定场景）
    
    用于第三方设备批量上报的遥测数据推送，设备可能跨多个场景。
    订阅telemetry频道的所有客户端都会收到消息。
    
    Args:
        updates: 遥测更新列表，每项包含:
            - device_id: 设备ID
            - entity_id: 关联实体ID
            - location: {"longitude": float, "latitude": float}
            - speed_kmh: 速度(可选)
            - heading: 航向(可选)
    """
    await ws_manager.broadcast_to_channel(
        channel="telemetry",
        event_type="batch_location_update",
        payload={
            "updates": updates,
            "count": len(updates),
            "timestamp": datetime.utcnow().isoformat(),
        },
        scenario_id=None,  # 不限定场景
    )


async def broadcast_alert(scenario_id: UUID, alert_type: str, alert_data: dict):
    """广播告警"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "alerts", alert_type, alert_data
    )


async def broadcast_entity_update(scenario_id: UUID, event_type: str, entity_data: dict):
    """广播实体更新"""
    await ws_manager.broadcast_to_scenario(
        scenario_id, "entities", event_type, entity_data
    )
