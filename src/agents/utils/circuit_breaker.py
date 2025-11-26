"""
熔断器实现

防止单点故障拖垮整个系统
- CLOSED: 正常状态，请求通过
- OPEN: 熔断状态，快速失败
- HALF_OPEN: 半开状态，允许少量请求试探
"""
from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 3       # 失败次数阈值
    recovery_timeout: float = 30.0   # 熔断恢复时间(秒)
    half_open_max_calls: int = 1     # 半开状态最大试探次数
    timeout: float = 30.0            # 单次调用超时(秒)
    excluded_exceptions: tuple = ()  # 不触发熔断的异常类型


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    half_open_calls: int = 0


class CircuitBreakerError(Exception):
    """熔断器异常"""
    pass


class CircuitBreakerOpen(CircuitBreakerError):
    """熔断器已打开"""
    def __init__(self, name: str, remaining_time: float):
        self.name = name
        self.remaining_time = remaining_time
        super().__init__(
            f"熔断器[{name}]已打开，剩余恢复时间: {remaining_time:.1f}秒"
        )


class CircuitBreakerTimeout(CircuitBreakerError):
    """熔断器超时"""
    def __init__(self, name: str, timeout: float):
        self.name = name
        self.timeout = timeout
        super().__init__(f"熔断器[{name}]调用超时: {timeout}秒")


class CircuitBreaker:
    """
    熔断器
    
    用法:
        breaker = CircuitBreaker("optimizer", failure_threshold=3, timeout=30)
        
        # 同步
        result = breaker.call(some_function, arg1, arg2)
        
        # 异步
        result = await breaker.call_async(some_async_function, arg1, arg2)
        
        # 装饰器
        @breaker
        def my_function():
            pass
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        timeout: float = 30.0,
        half_open_max_calls: int = 1,
        excluded_exceptions: tuple = (),
    ):
        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            timeout=timeout,
            half_open_max_calls=half_open_max_calls,
            excluded_exceptions=excluded_exceptions,
        )
        self._stats = CircuitBreakerStats()
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        with self._lock:
            self._check_state_transition()
            return self._stats.state
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._stats.state.value,
                "failure_count": self._stats.failure_count,
                "success_count": self._stats.success_count,
                "last_failure_time": self._stats.last_failure_time,
            }
    
    def _check_state_transition(self) -> None:
        """检查状态转换"""
        if self._stats.state == CircuitState.OPEN:
            elapsed = time.time() - self._stats.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        old_state = self._stats.state
        self._stats.state = new_state
        self._stats.last_state_change = time.time()
        
        if new_state == CircuitState.HALF_OPEN:
            self._stats.half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._stats.failure_count = 0
        
        logger.info(f"熔断器[{self.name}]状态变更: {old_state.value} -> {new_state.value}")
    
    def _on_success(self) -> None:
        """调用成功回调"""
        with self._lock:
            self._stats.success_count += 1
            
            if self._stats.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)
    
    def _on_failure(self, exc: Exception) -> None:
        """调用失败回调"""
        # 排除特定异常
        if isinstance(exc, self.config.excluded_exceptions):
            return
        
        with self._lock:
            self._stats.failure_count += 1
            self._stats.last_failure_time = time.time()
            
            if self._stats.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._stats.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
    
    def _check_can_execute(self) -> None:
        """检查是否允许执行"""
        with self._lock:
            self._check_state_transition()
            
            if self._stats.state == CircuitState.OPEN:
                remaining = self.config.recovery_timeout - (
                    time.time() - self._stats.last_failure_time
                )
                raise CircuitBreakerOpen(self.name, max(0, remaining))
            
            if self._stats.state == CircuitState.HALF_OPEN:
                if self._stats.half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpen(self.name, self.config.recovery_timeout)
                self._stats.half_open_calls += 1
    
    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """同步调用"""
        self._check_can_execute()
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    async def call_async(
        self, 
        func: Callable[..., T], 
        *args: Any, 
        **kwargs: Any
    ) -> T:
        """异步调用（带超时）"""
        self._check_can_execute()
        
        try:
            if asyncio.iscoroutinefunction(func):
                coro = func(*args, **kwargs)
            else:
                # 同步函数包装为协程
                loop = asyncio.get_event_loop()
                coro = loop.run_in_executor(None, lambda: func(*args, **kwargs))
            
            result = await asyncio.wait_for(coro, timeout=self.config.timeout)
            self._on_success()
            return result
            
        except asyncio.TimeoutError:
            self._on_failure(CircuitBreakerTimeout(self.name, self.config.timeout))
            raise CircuitBreakerTimeout(self.name, self.config.timeout)
        except Exception as e:
            self._on_failure(e)
            raise
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """装饰器用法"""
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await self.call_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                return self.call(func, *args, **kwargs)
            return sync_wrapper
    
    def reset(self) -> None:
        """重置熔断器"""
        with self._lock:
            self._stats = CircuitBreakerStats()
            logger.info(f"熔断器[{self.name}]已重置")


# 全局熔断器注册表
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
    timeout: float = 30.0,
) -> CircuitBreaker:
    """
    获取或创建熔断器
    
    Args:
        name: 熔断器名称（唯一标识）
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时(秒)
        timeout: 调用超时(秒)
    
    Returns:
        熔断器实例
    """
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                timeout=timeout,
            )
        return _circuit_breakers[name]


def get_all_circuit_breakers_stats() -> Dict[str, Dict[str, Any]]:
    """获取所有熔断器统计"""
    with _registry_lock:
        return {name: cb.stats for name, cb in _circuit_breakers.items()}


def reset_all_circuit_breakers() -> None:
    """重置所有熔断器"""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
