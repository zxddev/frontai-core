"""
AI Agent模块异常定义

错误码规范:
- AI4xxx: 客户端错误（请求问题）
- AI5xxx: 服务端错误（系统问题）
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.exceptions import AppException


# 错误码常量
class AIErrorCode:
    """AI模块错误码"""
    # 4xx 客户端错误
    TASK_NOT_FOUND = "AI4001"
    SCHEME_NOT_FOUND = "AI4002"
    RESOURCE_LOCKED = "AI4003"
    INVALID_INPUT = "AI4004"
    EVENT_NOT_FOUND = "AI4005"
    
    # 5xx 服务端错误
    RULE_LOAD_FAILED = "AI5001"
    CIRCUIT_BREAKER_OPEN = "AI5002"
    DATABASE_TIMEOUT = "AI5003"
    REDIS_UNAVAILABLE = "AI5004"
    ALGORITHM_FAILED = "AI5005"


class AIAgentError(AppException):
    """
    AI Agent模块基础异常
    
    所有AI模块异常必须继承此类
    """
    
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_code=error_code,
            message=message,
            details=details,
        )
        self.message = message
        self.details = details


class AITaskNotFoundError(AIAgentError):
    """任务不存在"""
    
    def __init__(self, task_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code=AIErrorCode.TASK_NOT_FOUND,
            message=f"任务不存在: {task_id}",
            details={"task_id": task_id},
        )


class AISchemeNotFoundError(AIAgentError):
    """方案不存在"""
    
    def __init__(self, scheme_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code=AIErrorCode.SCHEME_NOT_FOUND,
            message=f"方案不存在: {scheme_id}",
            details={"scheme_id": scheme_id},
        )


class AIEventNotFoundError(AIAgentError):
    """事件不存在"""
    
    def __init__(self, event_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code=AIErrorCode.EVENT_NOT_FOUND,
            message=f"事件不存在: {event_id}",
            details={"event_id": event_id},
        )


class AIResourceLockedError(AIAgentError):
    """资源已被锁定"""
    
    def __init__(
        self,
        locked_resources: List[str],
        locked_by: Optional[str] = None,
        retry_after_seconds: int = 30,
    ) -> None:
        super().__init__(
            status_code=409,
            error_code=AIErrorCode.RESOURCE_LOCKED,
            message=f"资源已被锁定: {', '.join(locked_resources)}",
            details={
                "locked_resources": locked_resources,
                "locked_by": locked_by,
                "retry_after_seconds": retry_after_seconds,
            },
        )
        self.locked_resources = locked_resources
        self.retry_after_seconds = retry_after_seconds


class AIInvalidInputError(AIAgentError):
    """输入参数无效"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            status_code=400,
            error_code=AIErrorCode.INVALID_INPUT,
            message=message,
            details=details,
        )


class AIRuleLoadError(AIAgentError):
    """规则加载失败"""
    
    def __init__(self, rule_file: str, reason: str) -> None:
        super().__init__(
            status_code=500,
            error_code=AIErrorCode.RULE_LOAD_FAILED,
            message=f"规则加载失败: {rule_file}",
            details={"rule_file": rule_file, "reason": reason},
        )


class AICircuitBreakerOpenError(AIAgentError):
    """熔断器已打开"""
    
    def __init__(self, breaker_name: str, recovery_seconds: float) -> None:
        super().__init__(
            status_code=503,
            error_code=AIErrorCode.CIRCUIT_BREAKER_OPEN,
            message=f"熔断器已打开: {breaker_name}",
            details={
                "breaker_name": breaker_name,
                "recovery_time_seconds": round(recovery_seconds, 1),
            },
        )


class AIDatabaseTimeoutError(AIAgentError):
    """数据库查询超时"""
    
    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(
            status_code=504,
            error_code=AIErrorCode.DATABASE_TIMEOUT,
            message=f"数据库查询超时: {operation}",
            details={
                "operation": operation,
                "timeout_seconds": timeout_seconds,
            },
        )


class AIRedisUnavailableError(AIAgentError):
    """Redis不可用"""
    
    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=503,
            error_code=AIErrorCode.REDIS_UNAVAILABLE,
            message=f"Redis不可用: {reason}",
            details={"reason": reason},
        )


class AIAlgorithmFailedError(AIAgentError):
    """算法执行失败"""
    
    def __init__(self, algorithm: str, reason: str) -> None:
        super().__init__(
            status_code=500,
            error_code=AIErrorCode.ALGORITHM_FAILED,
            message=f"算法执行失败: {algorithm}",
            details={"algorithm": algorithm, "reason": reason},
        )


__all__ = [
    "AIErrorCode",
    "AIAgentError",
    "AITaskNotFoundError",
    "AISchemeNotFoundError",
    "AIEventNotFoundError",
    "AIResourceLockedError",
    "AIInvalidInputError",
    "AIRuleLoadError",
    "AICircuitBreakerOpenError",
    "AIDatabaseTimeoutError",
    "AIRedisUnavailableError",
    "AIAlgorithmFailedError",
]
