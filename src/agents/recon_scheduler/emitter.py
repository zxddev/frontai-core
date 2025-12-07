"""
流式情报发射器

基于 spec.md Requirement: Streaming Intelligence Emission 实现。
双写 STOMP + PostGIS，支持本地缓冲和幂等性。

写入顺序:
1. 生成 event_id (UUID v4)
2. 写入 STOMP (实时, 失败不阻塞)
3. 写入 PostGIS (持久化, 失败重试)

幂等性: PostGIS 使用 event_id 作为唯一键, ON CONFLICT DO NOTHING
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable, Awaitable

from .state import IntelligenceEvent, EventType

logger = logging.getLogger(__name__)

# 优先级阈值 (>= 60 为 critical)
CRITICAL_PRIORITY_THRESHOLD = 60

# 最大缓冲事件数
MAX_BUFFER_SIZE = 1000

# 重试配置
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # 秒


@dataclass
class EmitterConfig:
    """发射器配置"""
    stomp_destination: str = "/topic/recon/intelligence"
    max_buffer_size: int = MAX_BUFFER_SIZE
    max_retries: int = MAX_RETRIES
    retry_backoff_base: float = RETRY_BACKOFF_BASE
    critical_threshold: int = CRITICAL_PRIORITY_THRESHOLD


@dataclass
class EmitResult:
    """发射结果"""
    event_id: str
    stomp_success: bool
    postgis_success: bool
    buffered: bool = False
    error: Optional[str] = None


class StreamEmitter:
    """
    流式情报发射器
    
    双写 STOMP + PostGIS，支持本地缓冲和自动重试。
    """
    
    def __init__(
        self,
        config: EmitterConfig = None,
        stomp_writer: Optional[Callable[[dict], Awaitable[bool]]] = None,
        postgis_writer: Optional[Callable[[dict], Awaitable[bool]]] = None
    ):
        """
        初始化发射器
        
        Args:
            config: 发射器配置
            stomp_writer: STOMP 写入函数 (可注入用于测试)
            postgis_writer: PostGIS 写入函数 (可注入用于测试)
        """
        self.config = config or EmitterConfig()
        self._stomp_writer = stomp_writer
        self._postgis_writer = postgis_writer
        
        # 缓冲队列 (网络断开时使用)
        self._buffer: deque[IntelligenceEvent] = deque(maxlen=self.config.max_buffer_size * 2)
        
        # 已发送的 event_id 集合 (用于幂等性检查)
        self._sent_ids: set[str] = set()
        
        # 统计
        self._stats = {
            "emitted": 0,
            "buffered": 0,
            "dropped": 0,
            "retried": 0,
        }
    
    @property
    def buffer_size(self) -> int:
        """当前缓冲大小"""
        return len(self._buffer)
    
    @property
    def stats(self) -> dict:
        """统计信息"""
        return {**self._stats, "buffer_size": self.buffer_size}
    
    def _is_critical(self, event: IntelligenceEvent) -> bool:
        """判断是否为 critical 事件"""
        return event.get("priority", 0) >= self.config.critical_threshold
    
    def _generate_event_id(self) -> str:
        """生成事件ID (UUID v4)"""
        return str(uuid.uuid4())
    
    def _ensure_event_id(self, event: IntelligenceEvent) -> str:
        """确保事件有 event_id"""
        if not event.get("event_id"):
            event["event_id"] = self._generate_event_id()
        return event["event_id"]
    
    def _ensure_timestamp(self, event: IntelligenceEvent) -> None:
        """确保事件有 timestamp"""
        if not event.get("timestamp"):
            event["timestamp"] = datetime.now().isoformat()
    
    async def _write_stomp(self, event: IntelligenceEvent) -> bool:
        """写入 STOMP"""
        if self._stomp_writer:
            try:
                return await self._stomp_writer(dict(event))
            except Exception as e:
                logger.warning(f"STOMP write failed: {e}")
                return False
        
        # 默认实现: 使用 stomp_broker
        try:
            from src.core.stomp.broker import stomp_broker
            await stomp_broker.broadcast_event(
                destination=self.config.stomp_destination,
                event_type=event.get("event_type", "UNKNOWN"),
                data=dict(event)
            )
            return True
        except Exception as e:
            logger.warning(f"STOMP broadcast failed: {e}")
            return False
    
    async def _write_postgis(self, event: IntelligenceEvent) -> bool:
        """
        写入 PostGIS
        
        使用 ON CONFLICT DO NOTHING 实现幂等性
        """
        if self._postgis_writer:
            try:
                return await self._postgis_writer(dict(event))
            except Exception as e:
                logger.warning(f"PostGIS write failed: {e}")
                return False
        
        # 默认实现: 直接返回 True (实际应调用 EventService)
        # 此处为 Mock，实际集成时替换
        logger.debug(f"PostGIS write (mock): event_id={event.get('event_id')}")
        return True
    
    async def _write_postgis_with_retry(self, event: IntelligenceEvent) -> bool:
        """带重试的 PostGIS 写入"""
        for attempt in range(self.config.max_retries):
            if await self._write_postgis(event):
                return True
            
            # 指数退避
            delay = self.config.retry_backoff_base * (2 ** attempt)
            logger.info(f"PostGIS retry {attempt + 1}/{self.config.max_retries}, delay={delay}s")
            self._stats["retried"] += 1
            await asyncio.sleep(delay)
        
        return False
    
    def _buffer_event(self, event: IntelligenceEvent) -> bool:
        """
        缓冲事件
        
        缓冲满时丢弃最老的非 critical 事件
        """
        # 检查缓冲是否已满
        if len(self._buffer) >= self.config.max_buffer_size:
            # 找到并移除最老的非 critical 事件
            for i, buffered in enumerate(self._buffer):
                if not self._is_critical(buffered):
                    del self._buffer[i]
                    self._stats["dropped"] += 1
                    logger.warning(f"Buffer overflow, dropped non-critical event: {buffered.get('event_id')}")
                    break
            else:
                # 全是 critical，移除最老的
                dropped = self._buffer.popleft()
                self._stats["dropped"] += 1
                logger.warning(f"Buffer overflow, dropped oldest critical event: {dropped.get('event_id')}")
        
        self._buffer.append(event)
        self._stats["buffered"] += 1
        return True
    
    async def emit_event(self, event: IntelligenceEvent) -> EmitResult:
        """
        发射事件
        
        Args:
            event: 情报事件
            
        Returns:
            发射结果
        """
        # 确保有 event_id 和 timestamp
        event_id = self._ensure_event_id(event)
        self._ensure_timestamp(event)
        
        # 幂等性检查
        if event_id in self._sent_ids:
            logger.debug(f"Event already sent, skipping: {event_id}")
            return EmitResult(
                event_id=event_id,
                stomp_success=True,
                postgis_success=True,
                buffered=False
            )
        
        # 1. 写入 STOMP (fire-and-forget if failed)
        stomp_success = await self._write_stomp(event)
        
        # 2. 写入 PostGIS (with retry)
        postgis_success = await self._write_postgis_with_retry(event)
        
        # 记录已发送
        if postgis_success:
            self._sent_ids.add(event_id)
            self._stats["emitted"] += 1
        
        # 如果 PostGIS 失败，缓冲事件
        buffered = False
        if not postgis_success:
            self._buffer_event(event)
            buffered = True
        
        # critical 事件 PostGIS 失败时发出 HEALTH 警告
        if not postgis_success and self._is_critical(event):
            logger.error(f"Critical event PostGIS write failed: {event_id}")
            # 可以在此发送 HEALTH warning 事件
        
        return EmitResult(
            event_id=event_id,
            stomp_success=stomp_success,
            postgis_success=postgis_success,
            buffered=buffered,
            error=None if postgis_success else "PostGIS write failed"
        )
    
    async def flush_buffer(self) -> int:
        """
        刷新缓冲区，重试写入所有缓冲事件
        
        Returns:
            成功写入的事件数
        """
        if not self._buffer:
            return 0
        
        success_count = 0
        events_to_retry = list(self._buffer)
        self._buffer.clear()
        
        for event in events_to_retry:
            event_id = event.get("event_id")
            
            # 跳过已发送的
            if event_id in self._sent_ids:
                continue
            
            if await self._write_postgis_with_retry(event):
                self._sent_ids.add(event_id)
                success_count += 1
            else:
                # 重新放回缓冲
                self._buffer.append(event)
        
        logger.info(f"Buffer flush: {success_count}/{len(events_to_retry)} events written")
        return success_count
    
    def create_event(
        self,
        event_type: str,
        mission_id: str,
        priority: int,
        payload: dict,
        geometry: Optional[dict] = None,
        confidence: Optional[float] = None,
        source: Optional[str] = None
    ) -> IntelligenceEvent:
        """
        创建情报事件
        
        Args:
            event_type: 事件类型 (PERCEPTION/HEALTH/PLAN/CHECKPOINT)
            mission_id: 任务ID
            priority: 优先级
            payload: 载荷数据
            geometry: GeoJSON 几何 (可选)
            confidence: 置信度 (可选)
            source: 来源 (可选)
        
        Returns:
            IntelligenceEvent
        """
        return {
            "event_id": self._generate_event_id(),
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "mission_id": mission_id,
            "geometry": geometry,
            "confidence": confidence,
            "source": source,
            "priority": priority,
            "payload": payload,
        }
    
    async def emit_perception(
        self,
        mission_id: str,
        detection_type: str,
        geometry: dict,
        confidence: float,
        source: str,
        payload: Optional[dict] = None
    ) -> EmitResult:
        """发射感知事件"""
        priority = self._get_perception_priority(detection_type, confidence)
        event = self.create_event(
            event_type=EventType.PERCEPTION.value,
            mission_id=mission_id,
            priority=priority,
            payload={
                "detection_type": detection_type,
                **(payload or {})
            },
            geometry=geometry,
            confidence=confidence,
            source=source
        )
        return await self.emit_event(event)
    
    async def emit_health(
        self,
        mission_id: str,
        device_id: str,
        metric_name: str,
        metric_value: Any,
        severity: str = "INFO"
    ) -> EmitResult:
        """发射健康事件"""
        priority = {"INFO": 20, "WARN": 60, "CRITICAL": 80}.get(severity, 20)
        event = self.create_event(
            event_type=EventType.HEALTH.value,
            mission_id=mission_id,
            priority=priority,
            payload={
                "device_id": device_id,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "severity": severity,
            }
        )
        return await self.emit_event(event)
    
    async def emit_checkpoint(
        self,
        mission_id: str,
        checkpoint_id: str,
        progress_percent: float,
        remaining_distance_m: float
    ) -> EmitResult:
        """发射检查点事件"""
        event = self.create_event(
            event_type=EventType.CHECKPOINT.value,
            mission_id=mission_id,
            priority=20,  # CHECKPOINT 非 critical
            payload={
                "checkpoint_id": checkpoint_id,
                "progress_percent": progress_percent,
                "remaining_distance_m": remaining_distance_m,
            }
        )
        return await self.emit_event(event)
    
    def _get_perception_priority(self, detection_type: str, confidence: float) -> int:
        """计算感知事件优先级"""
        base_priorities = {
            "SURVIVOR_DETECTED": 100,
            "OBSTACLE_DETECTED": 80,
            "ROUTE_BLOCKED": 70,
            "HEALTH_WARNING": 60,
        }
        base = base_priorities.get(detection_type, 30)
        return int(base * confidence)


# 全局发射器实例 (懒加载)
_global_emitter: Optional[StreamEmitter] = None


def get_emitter() -> StreamEmitter:
    """获取全局发射器实例"""
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = StreamEmitter()
    return _global_emitter
