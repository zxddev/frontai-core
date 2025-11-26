"""
资源分配锁模块

防止多个事件同时分配同一资源（队伍/装备等）
使用Redis实现分布式锁，支持降级到数据库锁
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Set

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.redis import get_redis_client, redis_available
from src.agents.exceptions import AIResourceLockedError, AIRedisUnavailableError

logger = logging.getLogger(__name__)

# 锁配置
LOCK_KEY_PREFIX = "ai:team_lock:"
DEFAULT_LOCK_TTL = 300  # 5分钟


class ResourceLock:
    """
    资源锁管理器
    
    支持Redis分布式锁，Redis不可用时降级到数据库锁
    """
    
    def __init__(
        self,
        event_id: str,
        ttl_seconds: int = DEFAULT_LOCK_TTL,
    ) -> None:
        """
        Args:
            event_id: 事件ID，作为锁持有者标识
            ttl_seconds: 锁过期时间（秒）
        """
        self._event_id = event_id
        self._ttl = ttl_seconds
        self._locked_teams: Set[str] = set()
        self._use_redis = True
    
    async def acquire_team_locks(
        self,
        team_ids: List[str],
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """
        批量锁定队伍
        
        原子性操作：要么全部锁定成功，要么全部失败
        
        Args:
            team_ids: 队伍ID列表
            db: 数据库session（用于降级）
            
        Returns:
            True如果锁定成功
            
        Raises:
            AIResourceLockedError: 资源已被其他事件锁定
        """
        if not team_ids:
            return True
        
        # 尝试Redis锁
        if await redis_available():
            return await self._acquire_redis_locks(team_ids)
        
        # Redis不可用，降级到数据库锁
        logger.warning("Redis不可用，降级到数据库锁")
        self._use_redis = False
        
        if db is None:
            raise AIRedisUnavailableError("Redis不可用且未提供数据库session")
        
        return await self._acquire_db_locks(team_ids, db)
    
    async def _acquire_redis_locks(self, team_ids: List[str]) -> bool:
        """
        使用Redis批量锁定
        
        使用Pipeline保证原子性
        """
        client = await get_redis_client()
        lock_value = f"{self._event_id}:{time.time()}"
        
        # 检查是否有已被锁定的资源
        locked_by_others: List[str] = []
        
        for team_id in team_ids:
            key = f"{LOCK_KEY_PREFIX}{team_id}"
            existing = await client.get(key)
            if existing and not existing.startswith(self._event_id):
                locked_by_others.append(team_id)
        
        if locked_by_others:
            logger.warning(f"资源已被锁定: {locked_by_others}")
            raise AIResourceLockedError(
                locked_resources=locked_by_others,
                retry_after_seconds=30,
            )
        
        # 原子性批量锁定
        pipe = client.pipeline()
        for team_id in team_ids:
            key = f"{LOCK_KEY_PREFIX}{team_id}"
            pipe.set(key, lock_value, nx=True, ex=self._ttl)
        
        results = await pipe.execute()
        
        # 检查结果
        failed_indices = [i for i, r in enumerate(results) if not r]
        
        if failed_indices:
            # 部分失败，回滚已锁定的
            await self._rollback_redis_locks(
                [team_ids[i] for i in range(len(team_ids)) if i not in failed_indices]
            )
            failed_teams = [team_ids[i] for i in failed_indices]
            logger.warning(f"部分资源锁定失败: {failed_teams}")
            raise AIResourceLockedError(
                locked_resources=failed_teams,
                retry_after_seconds=30,
            )
        
        self._locked_teams = set(team_ids)
        logger.info(f"Redis锁定成功: {len(team_ids)}个队伍, event={self._event_id}")
        return True
    
    async def _rollback_redis_locks(self, team_ids: List[str]) -> None:
        """回滚Redis锁"""
        if not team_ids:
            return
        
        try:
            client = await get_redis_client()
            pipe = client.pipeline()
            for team_id in team_ids:
                pipe.delete(f"{LOCK_KEY_PREFIX}{team_id}")
            await pipe.execute()
        except RedisError as e:
            logger.error(f"回滚Redis锁失败: {e}")
    
    async def _acquire_db_locks(
        self,
        team_ids: List[str],
        db: AsyncSession,
    ) -> bool:
        """
        使用数据库行级锁（SELECT FOR UPDATE）
        
        注意：需要在调用方的事务中使用
        """
        from src.domains.teams.models import RescueTeam
        
        # SELECT FOR UPDATE锁定行
        stmt = (
            select(RescueTeam)
            .where(RescueTeam.id.in_(team_ids))
            .where(RescueTeam.status == "standby")
            .with_for_update(nowait=True)
        )
        
        try:
            result = await db.execute(stmt)
            locked_teams = result.scalars().all()
            
            if len(locked_teams) != len(team_ids):
                # 有队伍不可锁定
                locked_ids = {str(t.id) for t in locked_teams}
                failed = [tid for tid in team_ids if tid not in locked_ids]
                raise AIResourceLockedError(
                    locked_resources=failed,
                    retry_after_seconds=30,
                )
            
            self._locked_teams = set(team_ids)
            logger.info(f"数据库锁定成功: {len(team_ids)}个队伍, event={self._event_id}")
            return True
            
        except Exception as e:
            if "could not obtain lock" in str(e).lower():
                raise AIResourceLockedError(
                    locked_resources=team_ids,
                    retry_after_seconds=30,
                )
            raise
    
    async def release_locks(self) -> None:
        """
        释放所有锁
        
        Redis锁会自动过期，但主动释放可以更快释放资源
        数据库锁在事务提交/回滚时自动释放
        """
        if not self._locked_teams:
            return
        
        if self._use_redis:
            await self._release_redis_locks()
        
        self._locked_teams.clear()
    
    async def _release_redis_locks(self) -> None:
        """释放Redis锁"""
        try:
            client = await get_redis_client()
            pipe = client.pipeline()
            
            for team_id in self._locked_teams:
                key = f"{LOCK_KEY_PREFIX}{team_id}"
                # 只删除自己持有的锁
                pipe.delete(key)
            
            await pipe.execute()
            logger.info(f"Redis锁已释放: {len(self._locked_teams)}个队伍")
            
        except RedisError as e:
            logger.error(f"释放Redis锁失败: {e}")
    
    @property
    def locked_teams(self) -> Set[str]:
        """获取已锁定的队伍ID"""
        return self._locked_teams.copy()


async def get_locked_teams() -> dict[str, str]:
    """
    获取所有当前被锁定的队伍
    
    Returns:
        {team_id: event_id} 映射
    """
    if not await redis_available():
        return {}
    
    try:
        client = await get_redis_client()
        keys = await client.keys(f"{LOCK_KEY_PREFIX}*")
        
        if not keys:
            return {}
        
        result = {}
        for key in keys:
            team_id = key.replace(LOCK_KEY_PREFIX, "")
            value = await client.get(key)
            if value:
                event_id = value.split(":")[0]
                result[team_id] = event_id
        
        return result
        
    except RedisError as e:
        logger.error(f"获取锁定队伍失败: {e}")
        return {}


__all__ = [
    "ResourceLock",
    "get_locked_teams",
    "LOCK_KEY_PREFIX",
    "DEFAULT_LOCK_TTL",
]
