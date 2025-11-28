"""
Redis状态持久化

移动会话状态的存储和恢复，支持应用重启后继续执行
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Set
from uuid import UUID

from redis.asyncio import Redis

from src.core.redis import get_redis_client, redis_available
from .schemas import MovementSession, BatchMovementSession, MovementState

logger = logging.getLogger(__name__)


# Redis Key 前缀
KEY_PREFIX = "movement"
SESSION_KEY_PREFIX = f"{KEY_PREFIX}:session"
BATCH_KEY_PREFIX = f"{KEY_PREFIX}:batch"
ACTIVE_SET_KEY = f"{KEY_PREFIX}:active"
ENTITY_SESSION_KEY = f"{KEY_PREFIX}:entity"

# 默认过期时间（24小时）
DEFAULT_TTL_SECONDS = 86400


class MovementPersistence:
    """
    移动会话持久化管理器
    
    Redis数据结构：
    - movement:session:{session_id} -> JSON(MovementSession)
    - movement:batch:{batch_id} -> JSON(BatchMovementSession)
    - movement:active -> SET[session_id, ...]
    - movement:entity:{entity_id} -> session_id
    """
    
    def __init__(self, redis: Optional[Redis] = None) -> None:
        self._redis = redis
        self._local_cache: dict[str, MovementSession] = {}
        self._local_batch_cache: dict[str, BatchMovementSession] = {}
        self._active_sessions: Set[str] = set()
        self._entity_to_session: dict[str, str] = {}
    
    async def _get_redis(self) -> Optional[Redis]:
        """获取Redis客户端，失败时返回None"""
        if self._redis is not None:
            return self._redis
        
        try:
            if await redis_available():
                self._redis = await get_redis_client()
                return self._redis
        except Exception as e:
            logger.warning(f"Redis不可用，使用内存存储: {e}")
        
        return None
    
    # =========================================================================
    # 会话存储
    # =========================================================================
    
    async def save_session(self, session: MovementSession) -> None:
        """保存移动会话"""
        session_key = f"{SESSION_KEY_PREFIX}:{session.session_id}"
        session_data = session.model_dump_json()
        
        # 保存到本地缓存
        self._local_cache[session.session_id] = session
        
        # 保存实体到会话的映射
        entity_id_str = str(session.entity_id)
        self._entity_to_session[entity_id_str] = session.session_id
        
        # 尝试保存到Redis
        redis = await self._get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.set(session_key, session_data, ex=DEFAULT_TTL_SECONDS)
                pipe.set(
                    f"{ENTITY_SESSION_KEY}:{entity_id_str}",
                    session.session_id,
                    ex=DEFAULT_TTL_SECONDS
                )
                
                # 活跃会话索引
                if session.state in (MovementState.PENDING, MovementState.MOVING, MovementState.PAUSED, MovementState.EXECUTING_TASK):
                    pipe.sadd(ACTIVE_SET_KEY, session.session_id)
                else:
                    pipe.srem(ACTIVE_SET_KEY, session.session_id)
                
                await pipe.execute()
            except Exception as e:
                logger.warning(f"Redis保存失败: {e}")
        
        # 更新本地活跃索引
        if session.state in (MovementState.PENDING, MovementState.MOVING, MovementState.PAUSED, MovementState.EXECUTING_TASK):
            self._active_sessions.add(session.session_id)
        else:
            self._active_sessions.discard(session.session_id)
    
    async def get_session(self, session_id: str) -> Optional[MovementSession]:
        """获取移动会话"""
        # 先查本地缓存
        if session_id in self._local_cache:
            return self._local_cache[session_id]
        
        # 查Redis
        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.get(f"{SESSION_KEY_PREFIX}:{session_id}")
                if data:
                    session = MovementSession.model_validate_json(data)
                    self._local_cache[session_id] = session
                    return session
            except Exception as e:
                logger.warning(f"Redis读取失败: {e}")
        
        return None
    
    async def delete_session(self, session_id: str) -> None:
        """删除移动会话"""
        session = self._local_cache.pop(session_id, None)
        self._active_sessions.discard(session_id)
        
        if session:
            entity_id_str = str(session.entity_id)
            self._entity_to_session.pop(entity_id_str, None)
        
        redis = await self._get_redis()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.delete(f"{SESSION_KEY_PREFIX}:{session_id}")
                pipe.srem(ACTIVE_SET_KEY, session_id)
                if session:
                    pipe.delete(f"{ENTITY_SESSION_KEY}:{session.entity_id}")
                await pipe.execute()
            except Exception as e:
                logger.warning(f"Redis删除失败: {e}")
    
    async def get_session_by_entity(self, entity_id: UUID) -> Optional[MovementSession]:
        """根据实体ID获取会话"""
        entity_id_str = str(entity_id)
        
        # 先查本地
        session_id = self._entity_to_session.get(entity_id_str)
        if session_id:
            return await self.get_session(session_id)
        
        # 查Redis
        redis = await self._get_redis()
        if redis:
            try:
                session_id = await redis.get(f"{ENTITY_SESSION_KEY}:{entity_id_str}")
                if session_id:
                    return await self.get_session(session_id)
            except Exception as e:
                logger.warning(f"Redis查询失败: {e}")
        
        return None
    
    async def get_active_sessions(self) -> List[MovementSession]:
        """获取所有活跃会话"""
        sessions = []
        
        # 获取活跃会话ID列表
        session_ids = set(self._active_sessions)
        
        redis = await self._get_redis()
        if redis:
            try:
                redis_ids = await redis.smembers(ACTIVE_SET_KEY)
                session_ids.update(redis_ids)
            except Exception as e:
                logger.warning(f"Redis查询活跃会话失败: {e}")
        
        # 获取会话详情
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session and session.state in (
                MovementState.PENDING, 
                MovementState.MOVING, 
                MovementState.PAUSED,
                MovementState.EXECUTING_TASK
            ):
                sessions.append(session)
        
        return sessions
    
    # =========================================================================
    # 批量会话存储
    # =========================================================================
    
    async def save_batch_session(self, batch: BatchMovementSession) -> None:
        """保存批量会话"""
        batch_key = f"{BATCH_KEY_PREFIX}:{batch.batch_id}"
        batch_data = batch.model_dump_json()
        
        self._local_batch_cache[batch.batch_id] = batch
        
        redis = await self._get_redis()
        if redis:
            try:
                await redis.set(batch_key, batch_data, ex=DEFAULT_TTL_SECONDS)
            except Exception as e:
                logger.warning(f"Redis保存批量会话失败: {e}")
    
    async def get_batch_session(self, batch_id: str) -> Optional[BatchMovementSession]:
        """获取批量会话"""
        if batch_id in self._local_batch_cache:
            return self._local_batch_cache[batch_id]
        
        redis = await self._get_redis()
        if redis:
            try:
                data = await redis.get(f"{BATCH_KEY_PREFIX}:{batch_id}")
                if data:
                    batch = BatchMovementSession.model_validate_json(data)
                    self._local_batch_cache[batch_id] = batch
                    return batch
            except Exception as e:
                logger.warning(f"Redis读取批量会话失败: {e}")
        
        return None
    
    async def delete_batch_session(self, batch_id: str) -> None:
        """删除批量会话"""
        self._local_batch_cache.pop(batch_id, None)
        
        redis = await self._get_redis()
        if redis:
            try:
                await redis.delete(f"{BATCH_KEY_PREFIX}:{batch_id}")
            except Exception as e:
                logger.warning(f"Redis删除批量会话失败: {e}")
    
    # =========================================================================
    # 清理
    # =========================================================================
    
    async def cleanup_completed(self) -> int:
        """清理已完成的会话（保留24小时）"""
        cleaned = 0
        now = datetime.utcnow()
        retention = timedelta(hours=24)
        
        for session_id in list(self._local_cache.keys()):
            session = self._local_cache.get(session_id)
            if session and session.state in (MovementState.COMPLETED, MovementState.CANCELLED):
                if session.completed_at and (now - session.completed_at) > retention:
                    await self.delete_session(session_id)
                    cleaned += 1
        
        logger.info(f"清理完成的会话: {cleaned}个")
        return cleaned


# 全局单例
_persistence: Optional[MovementPersistence] = None


async def get_persistence() -> MovementPersistence:
    """获取持久化管理器单例"""
    global _persistence
    if _persistence is None:
        _persistence = MovementPersistence()
    return _persistence
