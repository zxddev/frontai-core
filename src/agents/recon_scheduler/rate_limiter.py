"""
速率限制器

基于滑动窗口的限流实现，支持:
- 设备级限流 (2次/分钟)
- 全局L2限流 (10次/分钟)
- 队列超时控制

基于 spec.md Requirement: Performance Guardrails
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """超过速率限制"""
    def __init__(self, key: str, limit: int, window: int, retry_after: float):
        self.key = key
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for '{key}': {limit} per {window}s, retry after {retry_after:.1f}s"
        )


class QueueTimeoutError(Exception):
    """队列等待超时"""
    def __init__(self, queue_name: str, timeout: float):
        self.queue_name = queue_name
        self.timeout = timeout
        super().__init__(f"Queue timeout for '{queue_name}' after {timeout}s")


@dataclass
class RateLimitResult:
    """限流检查结果"""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: float = 0.0


class SlidingWindowRateLimiter:
    """
    滑动窗口限流器
    
    使用时间戳列表实现精确的滑动窗口
    """
    
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        key_func: Optional[Callable[[dict], str]] = None,
    ):
        """
        Args:
            limit: 窗口内允许的最大请求数
            window_seconds: 窗口时间(秒)
            key_func: 从状态提取限流key的函数，None表示全局限流
        """
        self.limit = limit
        self.window = window_seconds
        self.key_func = key_func
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
    
    def _get_key(self, state: Optional[dict] = None) -> str:
        """获取限流key"""
        if self.key_func is None or state is None:
            return "__global__"
        return self.key_func(state)
    
    def _cleanup_old_timestamps(self, key: str, now: float) -> None:
        """清理过期时间戳"""
        cutoff = now - self.window
        self._timestamps[key] = [ts for ts in self._timestamps[key] if ts > cutoff]
    
    async def check(self, state: Optional[dict] = None) -> RateLimitResult:
        """
        检查是否允许请求 (不消耗配额)
        
        Returns:
            RateLimitResult
        """
        async with self._lock:
            key = self._get_key(state)
            now = time.time()
            
            self._cleanup_old_timestamps(key, now)
            
            current_count = len(self._timestamps[key])
            allowed = current_count < self.limit
            remaining = max(0, self.limit - current_count)
            
            # 计算重置时间
            if self._timestamps[key]:
                oldest = min(self._timestamps[key])
                reset_at = oldest + self.window
                retry_after = max(0, reset_at - now) if not allowed else 0
            else:
                reset_at = now + self.window
                retry_after = 0
            
            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after,
            )
    
    async def acquire(self, state: Optional[dict] = None) -> RateLimitResult:
        """
        尝试获取配额
        
        Returns:
            RateLimitResult
            
        Raises:
            RateLimitExceededError: 如果超过限制
        """
        async with self._lock:
            key = self._get_key(state)
            now = time.time()
            
            self._cleanup_old_timestamps(key, now)
            
            current_count = len(self._timestamps[key])
            
            if current_count >= self.limit:
                oldest = min(self._timestamps[key])
                retry_after = (oldest + self.window) - now
                raise RateLimitExceededError(key, self.limit, self.window, retry_after)
            
            # 记录时间戳
            self._timestamps[key].append(now)
            
            return RateLimitResult(
                allowed=True,
                remaining=self.limit - current_count - 1,
                reset_at=now + self.window,
            )
    
    async def wait_and_acquire(
        self,
        state: Optional[dict] = None,
        timeout: float = 30.0,
    ) -> RateLimitResult:
        """
        等待直到获取配额或超时
        
        Args:
            state: 状态字典
            timeout: 最大等待时间(秒)
            
        Returns:
            RateLimitResult
            
        Raises:
            QueueTimeoutError: 等待超时
        """
        start = time.time()
        key = self._get_key(state)
        
        while True:
            elapsed = time.time() - start
            if elapsed >= timeout:
                raise QueueTimeoutError(f"rate_limit:{key}", timeout)
            
            try:
                return await self.acquire(state)
            except RateLimitExceededError as e:
                wait_time = min(e.retry_after, timeout - elapsed, 1.0)
                if wait_time <= 0:
                    raise QueueTimeoutError(f"rate_limit:{key}", timeout)
                await asyncio.sleep(wait_time)
    
    def reset(self, state: Optional[dict] = None) -> None:
        """重置限流计数"""
        key = self._get_key(state)
        self._timestamps[key] = []
    
    def reset_all(self) -> None:
        """重置所有限流计数"""
        self._timestamps.clear()


class ConcurrencySemaphore:
    """
    并发控制信号量
    
    带超时的信号量包装
    """
    
    def __init__(self, max_concurrent: int, name: str = "default"):
        self.max_concurrent = max_concurrent
        self.name = name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_count = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self, timeout: float = 30.0) -> bool:
        """
        获取信号量
        
        Args:
            timeout: 最大等待时间
            
        Returns:
            True if acquired
            
        Raises:
            QueueTimeoutError: 等待超时
        """
        try:
            acquired = await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=timeout
            )
            if acquired:
                async with self._lock:
                    self._active_count += 1
            return acquired
        except asyncio.TimeoutError:
            raise QueueTimeoutError(f"semaphore:{self.name}", timeout)
    
    def release(self) -> None:
        """释放信号量"""
        self._semaphore.release()
        asyncio.create_task(self._decrement_count())
    
    async def _decrement_count(self) -> None:
        async with self._lock:
            self._active_count = max(0, self._active_count - 1)
    
    @property
    def active(self) -> int:
        """当前活跃数"""
        return self._active_count
    
    @property
    def available(self) -> int:
        """可用配额"""
        return self.max_concurrent - self._active_count
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


# ============ 预配置的限流器实例 ============

# 设备级限流: 2次/分钟
DEVICE_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=2,
    window_seconds=60,
    key_func=lambda s: s.get("device_id", "__unknown__")
)

# 全局L2限流: 10次/分钟
L2_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=10,
    window_seconds=60,
)

# L2并发信号量: max 3
L2_SEMAPHORE = ConcurrencySemaphore(max_concurrent=3, name="l2_validation")

# 规划并发信号量: max 5
PLANNING_SEMAPHORE = ConcurrencySemaphore(max_concurrent=5, name="planning")

# 队列超时配置
QUEUE_TIMEOUT_SECONDS = 30.0


async def check_device_rate_limit(state: dict) -> RateLimitResult:
    """检查设备限流"""
    return await DEVICE_RATE_LIMITER.check(state)


async def acquire_device_rate_limit(state: dict) -> RateLimitResult:
    """获取设备限流配额"""
    return await DEVICE_RATE_LIMITER.acquire(state)


async def check_l2_rate_limit() -> RateLimitResult:
    """检查L2全局限流"""
    return await L2_RATE_LIMITER.check()


async def acquire_l2_rate_limit() -> RateLimitResult:
    """获取L2全局限流配额"""
    return await L2_RATE_LIMITER.acquire()


def get_rate_limiter_stats() -> dict[str, Any]:
    """获取限流器统计信息"""
    return {
        "device_limiter": {
            "limit": DEVICE_RATE_LIMITER.limit,
            "window": DEVICE_RATE_LIMITER.window,
            "active_keys": len(DEVICE_RATE_LIMITER._timestamps),
        },
        "l2_limiter": {
            "limit": L2_RATE_LIMITER.limit,
            "window": L2_RATE_LIMITER.window,
        },
        "l2_semaphore": {
            "max": L2_SEMAPHORE.max_concurrent,
            "active": L2_SEMAPHORE.active,
            "available": L2_SEMAPHORE.available,
        },
        "planning_semaphore": {
            "max": PLANNING_SEMAPHORE.max_concurrent,
            "active": PLANNING_SEMAPHORE.active,
            "available": PLANNING_SEMAPHORE.available,
        },
    }


__all__ = [
    "SlidingWindowRateLimiter",
    "ConcurrencySemaphore",
    "RateLimitResult",
    "RateLimitExceededError",
    "QueueTimeoutError",
    "DEVICE_RATE_LIMITER",
    "L2_RATE_LIMITER",
    "L2_SEMAPHORE",
    "PLANNING_SEMAPHORE",
    "QUEUE_TIMEOUT_SECONDS",
    "check_device_rate_limit",
    "acquire_device_rate_limit",
    "check_l2_rate_limit",
    "acquire_l2_rate_limit",
    "get_rate_limiter_stats",
]
