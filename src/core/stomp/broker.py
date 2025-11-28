"""
STOMP消息代理

基于Redis Pub/Sub实现消息路由和广播
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4
from collections import defaultdict

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from src.core.redis import get_redis_client
from .connection import StompConnection
from .frames import StompFrame, StompCommand


logger = logging.getLogger(__name__)


class StompBroker:
    """
    STOMP消息代理
    
    架构:
    - WebSocket连接管理
    - Redis Pub/Sub消息转发
    - 订阅路由和消息分发
    
    主题命名规范:
    - /topic/xxx: 广播主题（一对多）
    - /queue/xxx: 队列主题（一对一，负载均衡）
    - /user/{user_id}/xxx: 用户私有主题
    """
    
    # Redis频道前缀
    REDIS_CHANNEL_PREFIX = "stomp:"
    
    def __init__(self):
        # 连接管理: session_id -> StompConnection
        self.connections: dict[str, StompConnection] = {}
        
        # 目标订阅索引: destination -> set[session_id]
        self.destination_subscribers: dict[str, set[str]] = defaultdict(set)
        
        # 场景订阅索引: scenario_id -> set[session_id]
        self.scenario_subscribers: dict[UUID, set[str]] = defaultdict(set)
        
        # Redis Pub/Sub
        self._redis: Optional[Redis] = None
        self._pubsub: Optional[PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None
        
        # 心跳任务
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_interval = 30  # 秒
        
        # 运行状态
        self._running = False
    
    async def start(self):
        """启动消息代理"""
        if self._running:
            return
        
        logger.info("Starting STOMP broker...")
        self._running = True
        
        # 初始化Redis连接（允许失败，降级到本地模式）
        try:
            self._redis = await get_redis_client()
            self._pubsub = self._redis.pubsub()
            
            # 订阅Redis通配符频道
            await self._pubsub.psubscribe(f"{self.REDIS_CHANNEL_PREFIX}*")
            
            # 启动Redis消息监听
            self._listener_task = asyncio.create_task(self._redis_listener())
            logger.info("STOMP broker Redis mode enabled")
        except Exception as e:
            logger.warning(f"Redis connection failed, running in local-only mode: {e}")
            self._redis = None
            self._pubsub = None
        
        # 启动心跳检测
        self._heartbeat_task = asyncio.create_task(self._heartbeat_checker())
        
        logger.info("STOMP broker started")
    
    async def stop(self):
        """停止消息代理"""
        if not self._running:
            return
        
        logger.info("Stopping STOMP broker...")
        self._running = False
        
        # 取消任务
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭Pub/Sub
        if self._pubsub:
            await self._pubsub.punsubscribe()
            await self._pubsub.close()
        
        # 断开所有连接
        for conn in list(self.connections.values()):
            await self.disconnect(conn.session_id)
        
        logger.info("STOMP broker stopped")
    
    async def connect(self, conn: StompConnection):
        """注册连接"""
        self.connections[conn.session_id] = conn
        
        if conn.scenario_id:
            self.scenario_subscribers[conn.scenario_id].add(conn.session_id)
        
        logger.info(f"STOMP connection registered: {conn.session_id}, client={conn.client_id}")
    
    async def disconnect(self, session_id: str):
        """断开连接"""
        conn = self.connections.pop(session_id, None)
        if not conn:
            return
        
        # 清理订阅索引
        for destination in conn.get_subscribed_destinations():
            self.destination_subscribers[destination].discard(session_id)
        
        if conn.scenario_id:
            self.scenario_subscribers[conn.scenario_id].discard(session_id)
        
        logger.info(f"STOMP connection disconnected: {session_id}")
    
    async def subscribe(self, session_id: str, destination: str, subscription_id: str, ack_mode: str = "auto"):
        """处理订阅"""
        conn = self.connections.get(session_id)
        if not conn:
            return
        
        conn.add_subscription(subscription_id, destination, ack_mode)
        self.destination_subscribers[destination].add(session_id)
        
        logger.info(f"Subscription: {session_id} -> {destination}")
    
    async def unsubscribe(self, session_id: str, subscription_id: str):
        """处理取消订阅"""
        conn = self.connections.get(session_id)
        if not conn:
            return
        
        sub = conn.remove_subscription(subscription_id)
        if sub:
            self.destination_subscribers[sub.destination].discard(session_id)
    
    async def send_to_destination(self, destination: str, body: Any, scenario_id: Optional[UUID] = None):
        """
        发送消息到目标
        
        同时:
        1. 直接发送给已连接的订阅者
        2. 发布到Redis（支持多实例部署）
        """
        if isinstance(body, dict):
            body_str = json.dumps(body, ensure_ascii=False, default=str)
        else:
            body_str = str(body)
        
        # 发布到Redis（跨实例广播）
        redis_channel = self._destination_to_channel(destination)
        message = {
            "destination": destination,
            "body": body_str,
            "scenario_id": str(scenario_id) if scenario_id else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if self._redis:
            await self._redis.publish(redis_channel, json.dumps(message))
        
        # 本地直接发送（减少延迟）
        await self._deliver_local(destination, body_str, scenario_id)
    
    async def send_to_user(self, user_id: str, destination: str, body: Any):
        """发送消息给特定用户"""
        user_dest = f"/user/{user_id}{destination}"
        await self.send_to_destination(user_dest, body)
    
    async def send_to_scenario(self, scenario_id: UUID, destination: str, body: Any):
        """发送消息给场景内所有订阅者"""
        await self.send_to_destination(destination, body, scenario_id)
    
    async def broadcast(self, destination: str, body: Any):
        """广播消息给所有订阅者"""
        await self.send_to_destination(destination, body)
    
    async def _deliver_local(self, destination: str, body: str, scenario_id: Optional[UUID] = None):
        """本地投递消息"""
        # 获取订阅了该目标的会话
        session_ids = set()
        
        # 精确匹配
        if destination in self.destination_subscribers:
            session_ids.update(self.destination_subscribers[destination])
        
        # 通配符匹配
        for pattern, subs in self.destination_subscribers.items():
            if self._match_pattern(pattern, destination):
                session_ids.update(subs)
        
        # 如果指定了场景，过滤只发给该场景的连接
        if scenario_id:
            scenario_sessions = self.scenario_subscribers.get(scenario_id, set())
            session_ids = session_ids & scenario_sessions
        
        # 投递
        for session_id in session_ids:
            conn = self.connections.get(session_id)
            if conn and conn.is_connected:
                try:
                    await conn.send_message(destination, body)
                except Exception as e:
                    logger.error(f"Failed to deliver to {session_id}: {e}")
    
    async def _redis_listener(self):
        """Redis消息监听器"""
        logger.info("Redis listener started")
        
        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break
                
                if message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        destination = data.get("destination")
                        body = data.get("body")
                        scenario_id = data.get("scenario_id")
                        
                        if destination and body:
                            scenario_uuid = UUID(scenario_id) if scenario_id else None
                            await self._deliver_local(destination, body, scenario_uuid)
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
        
        except asyncio.CancelledError:
            logger.info("Redis listener cancelled")
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
    
    async def _heartbeat_checker(self):
        """心跳检测"""
        logger.info("Heartbeat checker started")
        
        try:
            while self._running:
                await asyncio.sleep(self._heartbeat_interval)
                
                now = datetime.utcnow()
                timeout = self._heartbeat_interval * 3  # 3次心跳超时
                
                for session_id, conn in list(self.connections.items()):
                    elapsed = (now - conn.last_activity).total_seconds()
                    if elapsed > timeout:
                        logger.warning(f"Connection timeout: {session_id}")
                        await self.disconnect(session_id)
        
        except asyncio.CancelledError:
            logger.info("Heartbeat checker cancelled")
    
    def _destination_to_channel(self, destination: str) -> str:
        """将STOMP目标转换为Redis频道"""
        # /topic/map.entity.update -> stomp:topic:map.entity.update
        clean_dest = destination.lstrip("/").replace("/", ":")
        return f"{self.REDIS_CHANNEL_PREFIX}{clean_dest}"
    
    @staticmethod
    def _match_pattern(pattern: str, destination: str) -> bool:
        """匹配通配符模式"""
        if pattern == destination:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            parts = destination.split(".")
            pattern_parts = prefix.split(".")
            return parts[:len(pattern_parts)] == pattern_parts and len(parts) == len(pattern_parts) + 1
        if pattern.endswith(".>"):
            prefix = pattern[:-2]
            return destination.startswith(prefix + ".")
        return False
    
    # =========================================================================
    # 便捷广播方法（业务层调用）
    # =========================================================================
    
    async def broadcast_entity_create(self, entity_data: dict, scenario_id: Optional[UUID] = None):
        """广播实体创建"""
        await self.send_to_destination("/topic/map.entity.create", {"payload": entity_data}, scenario_id)
    
    async def broadcast_entity_update(self, entity_data: dict, scenario_id: Optional[UUID] = None):
        """广播实体更新"""
        await self.send_to_destination("/topic/map.entity.update", {"payload": entity_data}, scenario_id)
    
    async def broadcast_entity_delete(self, entity_id: str, scenario_id: Optional[UUID] = None):
        """广播实体删除（仅ID）"""
        await self.send_to_destination("/topic/map.entity.delete", {"payload": {"id": entity_id}}, scenario_id)
    
    async def broadcast_entity_delete_full(self, entity_data: dict, scenario_id: Optional[UUID] = None):
        """广播实体删除（包含完整信息：id, type, layerCode）"""
        await self.send_to_destination("/topic/map.entity.delete", {"payload": entity_data}, scenario_id)
    
    async def broadcast_location(self, location_data: dict, scenario_id: Optional[UUID] = None):
        """广播实时位置"""
        await self.send_to_destination("/topic/realtime.location", {"payload": location_data}, scenario_id)
    
    async def broadcast_event(self, event_type: str, event_data: dict, scenario_id: Optional[UUID] = None):
        """广播事件"""
        await self.send_to_destination(f"/topic/scenario.{event_type}.triggered", {"payload": event_data}, scenario_id)
    
    async def broadcast_task(self, task_data: dict, scenario_id: Optional[UUID] = None):
        """广播任务"""
        await self.send_to_destination("/topic/scenario.task.triggered", {"payload": task_data}, scenario_id)
    
    async def broadcast_alert(self, alert_data: dict, scenario_id: Optional[UUID] = None):
        """广播告警"""
        await self.send_to_destination("/topic/alerts", {"payload": alert_data}, scenario_id)


# 全局单例
stomp_broker = StompBroker()
