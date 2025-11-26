"""
Redis客户端模块

提供异步Redis连接管理，支持分布式锁等功能
"""
from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import settings

logger = logging.getLogger(__name__)

# 全局Redis客户端实例
_redis_client: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """
    获取异步Redis客户端
    
    使用连接池管理连接，支持自动重连
    
    Returns:
        Redis异步客户端实例
        
    Raises:
        RedisError: Redis连接失败
    """
    global _redis_client
    
    if _redis_client is None:
        logger.info(f"初始化Redis连接: {settings.redis_url}")
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
        )
    
    return _redis_client


async def close_redis_client() -> None:
    """关闭Redis连接"""
    global _redis_client
    
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis连接已关闭")


async def check_redis_health() -> dict[str, any]:
    """
    检查Redis健康状态
    
    Returns:
        健康状态字典，包含connected和latency_ms
    """
    import time
    
    try:
        client = await get_redis_client()
        start = time.time()
        await client.ping()
        latency_ms = (time.time() - start) * 1000
        
        return {
            "connected": True,
            "latency_ms": round(latency_ms, 2),
        }
    except RedisError as e:
        logger.warning(f"Redis健康检查失败: {e}")
        return {
            "connected": False,
            "error": str(e),
        }


async def redis_available() -> bool:
    """
    检查Redis是否可用
    
    Returns:
        True如果Redis可连接，否则False
    """
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except RedisError:
        return False


__all__ = [
    "get_redis_client",
    "close_redis_client",
    "check_redis_health",
    "redis_available",
    "RedisError",
]
