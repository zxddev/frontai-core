"""
方案生成Agent工具函数

提供节点耗时追踪等通用功能
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, Dict, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Dict[str, Any]])


def track_node_time(node_name: str) -> Callable[[F], F]:
    """
    节点耗时追踪装饰器
    
    自动记录节点执行时间到trace.node_timings
    
    Args:
        node_name: 节点名称
        
    Usage:
        @track_node_time("match_resources")
        def match_resources(state: SchemeGenerationState) -> Dict[str, Any]:
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.perf_counter()
            
            try:
                result = func(state)
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.error(f"节点{node_name}执行失败: {e}, 耗时{elapsed_ms:.2f}ms")
                raise
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            
            # 更新trace中的节点耗时
            trace = result.get("trace", state.get("trace", {}))
            if "node_timings" not in trace:
                trace["node_timings"] = {}
            trace["node_timings"][node_name] = round(elapsed_ms, 2)
            result["trace"] = trace
            
            logger.debug(f"节点{node_name}执行完成: {elapsed_ms:.2f}ms")
            
            return result
        
        return wrapper  # type: ignore
    return decorator
