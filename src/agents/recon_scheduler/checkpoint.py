"""
检查点系统

支持任务中断后的恢复重规划。
- Redis: 短期存储 (TTL 24h)
- PostgreSQL: 长期/关键任务存储 (永久)
- 分布式锁: 防止并发恢复

基于 spec.md Requirement: Checkpoint and Resume with Re-Plan
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Optional

from src.core.redis import get_redis_client, redis_available
from src.core.database import get_db

logger = logging.getLogger(__name__)

# 配置常量
CHECKPOINT_KEY_PREFIX = "recon:checkpoint:"
LOCK_KEY_PREFIX = "recon:mission:"
LOCK_SUFFIX = ":lock"

LOCK_TTL_SECONDS = 60
LOCK_RENEWAL_SECONDS = 30
LOCK_ACQUIRE_TIMEOUT = 5.0

REDIS_TTL_HOURS = 24
SCHEMA_VERSION = "1.0.0"

# 任务时长阈值 (小时)
LONG_MISSION_THRESHOLD_HOURS = 1.0


@dataclass
class CheckpointPayload:
    """检查点数据结构"""
    mission_id: str
    checkpoint_id: str
    timestamp: str  # ISO8601
    schema_version: str = SCHEMA_VERSION
    
    # 位置状态
    current_position_utm: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (E, N, alt)
    heading: float = 0.0
    utm_zone: str = "48N"
    
    # 进度
    covered_area_mask: list[list[float]] = field(default_factory=list)  # UTM polygon
    remaining_waypoints: list[dict] = field(default_factory=list)
    progress_percent: float = 0.0
    remaining_distance_m: float = 0.0
    
    # 环境快照
    environment_snapshot: dict = field(default_factory=dict)
    
    # 缓存的智能事件
    cached_intelligence: list[dict] = field(default_factory=list)
    
    # 元数据
    device_id: str = ""
    is_critical: bool = False
    mission_duration_hours: float = 0.0
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "CheckpointPayload":
        """从字典创建"""
        # 处理tuple字段
        if "current_position_utm" in data and isinstance(data["current_position_utm"], list):
            data["current_position_utm"] = tuple(data["current_position_utm"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def is_version_compatible(self, other_version: str) -> tuple[bool, str]:
        """
        检查版本兼容性
        
        Returns:
            (is_compatible, message)
        """
        current_parts = self.schema_version.split(".")
        other_parts = other_version.split(".")
        
        # Major版本不同: 不兼容
        if current_parts[0] != other_parts[0]:
            return False, f"Major version mismatch: {self.schema_version} vs {other_version}"
        
        # Minor版本不同: 兼容但警告
        if current_parts[1] != other_parts[1]:
            return True, f"Minor version diff: {self.schema_version} vs {other_version} (compatible with warning)"
        
        return True, "Version compatible"


@dataclass
class LockInfo:
    """锁信息"""
    node_id: str
    timestamp: str
    pid: int
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "LockInfo":
        return cls(**data)
    
    @classmethod
    def create(cls) -> "LockInfo":
        """创建当前进程的锁信息"""
        return cls(
            node_id=os.environ.get("NODE_ID", f"node-{uuid.uuid4().hex[:8]}"),
            timestamp=datetime.now().isoformat(),
            pid=os.getpid()
        )


class CheckpointError(Exception):
    """检查点异常基类"""
    pass


class MissionLockedError(CheckpointError):
    """任务已被锁定"""
    def __init__(self, mission_id: str, lock_info: LockInfo):
        self.mission_id = mission_id
        self.lock_info = lock_info
        super().__init__(f"Mission {mission_id} is locked by {lock_info.node_id}")


class CheckpointVersionError(CheckpointError):
    """检查点版本不兼容"""
    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(f"Checkpoint version mismatch: expected {expected}, got {actual}")


class CheckpointNotFoundError(CheckpointError):
    """检查点未找到"""
    pass


class CheckpointManager:
    """
    检查点管理器
    
    用法:
        manager = CheckpointManager()
        
        # 保存检查点
        checkpoint_id = await manager.save_checkpoint(state)
        
        # 恢复任务
        state = await manager.resume_mission(mission_id)
    """
    
    def __init__(self):
        self._lock_renewal_tasks: dict[str, asyncio.Task] = {}
    
    async def save_checkpoint(
        self,
        state: dict,
        force_postgres: bool = False,
    ) -> str:
        """
        保存检查点
        
        Args:
            state: 当前ReconSchedulerState
            force_postgres: 强制写入PostgreSQL
            
        Returns:
            checkpoint_id
        """
        checkpoint_id = f"ckpt-{uuid.uuid4().hex[:12]}"
        mission_id = state.get("mission_id") or state.get("event_id", "unknown")
        
        # 构建检查点数据
        payload = CheckpointPayload(
            mission_id=mission_id,
            checkpoint_id=checkpoint_id,
            timestamp=datetime.now().isoformat(),
            schema_version=SCHEMA_VERSION,
            # 位置
            current_position_utm=tuple(state.get("current_position_utm", (0, 0, 0))),
            heading=state.get("heading", 0.0),
            utm_zone=state.get("utm_zone", "48N"),
            # 进度
            covered_area_mask=state.get("covered_area_mask", []),
            remaining_waypoints=state.get("remaining_waypoints", []),
            progress_percent=state.get("progress_percent", 0.0),
            remaining_distance_m=state.get("remaining_distance_m", 0.0),
            # 环境
            environment_snapshot={
                "wind_speed": state.get("environment", {}).get("wind_speed", 0),
                "wind_direction": state.get("environment", {}).get("wind_direction", 0),
                "temperature": state.get("environment", {}).get("temperature", 20),
                "comm_coverage": state.get("comm_coverage_snapshot", {}),
                "constraints": state.get("flight_constraints", {}),
            },
            # 缓存
            cached_intelligence=state.get("buffered_events", []),
            # 元数据
            device_id=state.get("device_id", ""),
            is_critical=state.get("is_critical", False),
            mission_duration_hours=state.get("mission_duration_hours", 0.0),
        )
        
        # 决定存储策略
        use_postgres = (
            force_postgres
            or payload.is_critical
            or payload.mission_duration_hours >= LONG_MISSION_THRESHOLD_HOURS
        )
        
        # 写入Redis
        await self._save_to_redis(payload)
        logger.info(f"Checkpoint saved to Redis: {checkpoint_id}")
        
        # 条件写入PostgreSQL
        if use_postgres:
            await self._save_to_postgres(payload)
            logger.info(f"Checkpoint saved to PostgreSQL: {checkpoint_id}")
        
        return checkpoint_id
    
    async def _save_to_redis(self, payload: CheckpointPayload) -> None:
        """保存到Redis"""
        if not await redis_available():
            logger.warning("Redis not available, skipping Redis checkpoint")
            return
        
        client = await get_redis_client()
        key = f"{CHECKPOINT_KEY_PREFIX}{payload.mission_id}"
        ttl = int(REDIS_TTL_HOURS * 3600)
        
        await client.set(key, json.dumps(payload.to_dict()), ex=ttl)
    
    async def _save_to_postgres(self, payload: CheckpointPayload) -> None:
        """保存到PostgreSQL"""
        try:
            async for session in get_db():
                # 使用原生SQL (避免依赖ORM模型)
                from sqlalchemy import text
                
                query = text("""
                    INSERT INTO recon_checkpoints (
                        checkpoint_id, mission_id, payload, created_at, schema_version
                    ) VALUES (
                        :checkpoint_id, :mission_id, :payload, :created_at, :schema_version
                    )
                    ON CONFLICT (mission_id) DO UPDATE SET
                        checkpoint_id = EXCLUDED.checkpoint_id,
                        payload = EXCLUDED.payload,
                        created_at = EXCLUDED.created_at,
                        schema_version = EXCLUDED.schema_version
                """)
                
                await session.execute(query, {
                    "checkpoint_id": payload.checkpoint_id,
                    "mission_id": payload.mission_id,
                    "payload": json.dumps(payload.to_dict()),
                    "created_at": datetime.now(),
                    "schema_version": payload.schema_version,
                })
                await session.commit()
                break  # 只需执行一次
        except Exception as e:
            logger.error(f"Failed to save checkpoint to PostgreSQL: {e}")
            # 不抛出异常，Redis是主要存储
    
    async def load_checkpoint(self, mission_id: str) -> Optional[CheckpointPayload]:
        """
        加载检查点
        
        按优先级: Redis -> PostgreSQL
        
        Returns:
            CheckpointPayload or None if not found
        """
        # 尝试Redis
        payload = await self._load_from_redis(mission_id)
        if payload:
            logger.info(f"Checkpoint loaded from Redis: {mission_id}")
            return payload
        
        # Fallback到PostgreSQL
        payload = await self._load_from_postgres(mission_id)
        if payload:
            logger.info(f"Checkpoint loaded from PostgreSQL: {mission_id}")
            return payload
        
        return None
    
    async def _load_from_redis(self, mission_id: str) -> Optional[CheckpointPayload]:
        """从Redis加载"""
        if not await redis_available():
            return None
        
        try:
            client = await get_redis_client()
            key = f"{CHECKPOINT_KEY_PREFIX}{mission_id}"
            data = await client.get(key)
            
            if data:
                return CheckpointPayload.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Failed to load checkpoint from Redis: {e}")
        
        return None
    
    async def _load_from_postgres(self, mission_id: str) -> Optional[CheckpointPayload]:
        """从PostgreSQL加载"""
        try:
            async for session in get_db():
                from sqlalchemy import text
                
                query = text("""
                    SELECT payload FROM recon_checkpoints
                    WHERE mission_id = :mission_id
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                result = await session.execute(query, {"mission_id": mission_id})
                row = result.fetchone()
                
                if row:
                    payload_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    return CheckpointPayload.from_dict(payload_data)
                break  # 只需执行一次
        except Exception as e:
            logger.error(f"Failed to load checkpoint from PostgreSQL: {e}")
        
        return None
    
    async def resume_mission(self, mission_id: str) -> dict:
        """
        恢复任务
        
        1. 获取分布式锁
        2. 加载检查点
        3. 验证版本兼容性
        4. 构建恢复状态 (需要重规划)
        
        Returns:
            ReconSchedulerState for re-planning
            
        Raises:
            MissionLockedError: 任务已被其他进程锁定
            CheckpointNotFoundError: 检查点不存在
            CheckpointVersionError: 版本不兼容
        """
        # 1. 获取锁
        if not await self.acquire_mission_lock(mission_id):
            # 获取当前锁信息
            lock_info = await self._get_lock_info(mission_id)
            raise MissionLockedError(mission_id, lock_info or LockInfo.create())
        
        try:
            # 2. 加载检查点
            payload = await self.load_checkpoint(mission_id)
            if not payload:
                raise CheckpointNotFoundError(f"No checkpoint found for mission: {mission_id}")
            
            # 3. 验证版本
            is_compatible, msg = payload.is_version_compatible(SCHEMA_VERSION)
            if not is_compatible:
                raise CheckpointVersionError(SCHEMA_VERSION, payload.schema_version)
            if "warning" in msg.lower():
                logger.warning(msg)
            
            # 4. 构建恢复状态
            state = self._build_resume_state(payload)
            
            logger.info(f"Mission resumed: {mission_id}, progress={payload.progress_percent:.1f}%")
            return state
            
        except Exception:
            # 失败时释放锁
            await self.release_mission_lock(mission_id)
            raise
    
    def _build_resume_state(self, payload: CheckpointPayload) -> dict:
        """
        构建恢复状态
        
        关键: 设置 needs_replan=True 触发重规划
        """
        return {
            "mission_id": payload.mission_id,
            "event_id": payload.mission_id,
            "device_id": payload.device_id,
            # 位置恢复
            "current_position_utm": payload.current_position_utm,
            "heading": payload.heading,
            "utm_zone": payload.utm_zone,
            # 进度恢复
            "covered_area_mask": payload.covered_area_mask,
            "remaining_waypoints": payload.remaining_waypoints,
            "progress_percent": payload.progress_percent,
            "remaining_distance_m": payload.remaining_distance_m,
            # 环境恢复
            "environment": {
                "wind_speed": payload.environment_snapshot.get("wind_speed", 0),
                "wind_direction": payload.environment_snapshot.get("wind_direction", 0),
                "temperature": payload.environment_snapshot.get("temperature", 20),
            },
            "flight_constraints": payload.environment_snapshot.get("constraints", {}),
            # 缓存恢复
            "buffered_events": payload.cached_intelligence,
            # 恢复标志
            "is_resumed": True,
            "needs_replan": True,  # 触发重规划
            "resume_checkpoint_id": payload.checkpoint_id,
            "resume_timestamp": datetime.now().isoformat(),
            # 元数据
            "is_critical": payload.is_critical,
        }
    
    async def acquire_mission_lock(self, mission_id: str) -> bool:
        """
        获取任务分布式锁
        
        Returns:
            True if lock acquired
        """
        if not await redis_available():
            logger.warning("Redis not available, lock acquisition skipped")
            return True  # 无Redis时默认允许
        
        client = await get_redis_client()
        lock_key = f"{LOCK_KEY_PREFIX}{mission_id}{LOCK_SUFFIX}"
        lock_info = LockInfo.create()
        
        try:
            # 尝试获取锁 (NX=仅不存在时设置)
            acquired = await asyncio.wait_for(
                client.set(
                    lock_key,
                    json.dumps(lock_info.to_dict()),
                    nx=True,
                    ex=LOCK_TTL_SECONDS
                ),
                timeout=LOCK_ACQUIRE_TIMEOUT
            )
            
            if acquired:
                # 启动锁续期任务
                self._start_lock_renewal(mission_id, lock_key)
                logger.info(f"Mission lock acquired: {mission_id}")
                return True
            
            logger.warning(f"Mission lock not acquired (already locked): {mission_id}")
            return False
            
        except asyncio.TimeoutError:
            logger.error(f"Lock acquisition timeout: {mission_id}")
            return False
        except Exception as e:
            logger.error(f"Lock acquisition failed: {e}")
            return False
    
    async def release_mission_lock(self, mission_id: str) -> None:
        """释放任务锁"""
        # 停止续期任务
        if mission_id in self._lock_renewal_tasks:
            self._lock_renewal_tasks[mission_id].cancel()
            del self._lock_renewal_tasks[mission_id]
        
        if not await redis_available():
            return
        
        try:
            client = await get_redis_client()
            lock_key = f"{LOCK_KEY_PREFIX}{mission_id}{LOCK_SUFFIX}"
            await client.delete(lock_key)
            logger.info(f"Mission lock released: {mission_id}")
        except Exception as e:
            logger.error(f"Failed to release mission lock: {e}")
    
    async def _get_lock_info(self, mission_id: str) -> Optional[LockInfo]:
        """获取当前锁信息"""
        if not await redis_available():
            return None
        
        try:
            client = await get_redis_client()
            lock_key = f"{LOCK_KEY_PREFIX}{mission_id}{LOCK_SUFFIX}"
            data = await client.get(lock_key)
            
            if data:
                return LockInfo.from_dict(json.loads(data))
        except Exception:
            pass
        
        return None
    
    def _start_lock_renewal(self, mission_id: str, lock_key: str) -> None:
        """启动锁续期后台任务"""
        async def renewal_loop():
            while True:
                await asyncio.sleep(LOCK_RENEWAL_SECONDS)
                try:
                    if await redis_available():
                        client = await get_redis_client()
                        await client.expire(lock_key, LOCK_TTL_SECONDS)
                        logger.debug(f"Lock renewed: {mission_id}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Lock renewal failed: {e}")
        
        task = asyncio.create_task(renewal_loop())
        self._lock_renewal_tasks[mission_id] = task
    
    async def delete_checkpoint(self, mission_id: str) -> None:
        """删除检查点 (任务完成后清理)"""
        # 删除Redis
        if await redis_available():
            try:
                client = await get_redis_client()
                key = f"{CHECKPOINT_KEY_PREFIX}{mission_id}"
                await client.delete(key)
            except Exception as e:
                logger.error(f"Failed to delete Redis checkpoint: {e}")
        
        # 删除PostgreSQL
        try:
            async for session in get_db():
                from sqlalchemy import text
                query = text("DELETE FROM recon_checkpoints WHERE mission_id = :mission_id")
                await session.execute(query, {"mission_id": mission_id})
                await session.commit()
                break  # 只需执行一次
        except Exception as e:
            logger.error(f"Failed to delete PostgreSQL checkpoint: {e}")
        
        logger.info(f"Checkpoint deleted: {mission_id}")


# 全局实例
_checkpoint_manager: Optional[CheckpointManager] = None


def get_checkpoint_manager() -> CheckpointManager:
    """获取检查点管理器单例"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
    return _checkpoint_manager


# 便捷函数
async def save_checkpoint(state: dict, force_postgres: bool = False) -> str:
    """保存检查点"""
    return await get_checkpoint_manager().save_checkpoint(state, force_postgres)


async def load_checkpoint(mission_id: str) -> Optional[CheckpointPayload]:
    """加载检查点"""
    return await get_checkpoint_manager().load_checkpoint(mission_id)


async def resume_mission(mission_id: str) -> dict:
    """恢复任务"""
    return await get_checkpoint_manager().resume_mission(mission_id)


async def release_mission_lock(mission_id: str) -> None:
    """释放任务锁"""
    await get_checkpoint_manager().release_mission_lock(mission_id)


__all__ = [
    "CheckpointPayload",
    "CheckpointManager",
    "CheckpointError",
    "MissionLockedError",
    "CheckpointVersionError",
    "CheckpointNotFoundError",
    "LockInfo",
    "get_checkpoint_manager",
    "save_checkpoint",
    "load_checkpoint",
    "resume_mission",
    "release_mission_lock",
    "SCHEMA_VERSION",
]
