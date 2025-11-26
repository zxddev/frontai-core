from fastapi import HTTPException
from typing import Optional, Any


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Any] = None,
    ):
        super().__init__(status_code=status_code, detail={
            "error_code": error_code,
            "message": message,
            "details": details,
        })
        self.error_code = error_code


class NotFoundError(AppException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            status_code=404,
            error_code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} not found: {resource_id}",
        )


class ConflictError(AppException):
    def __init__(self, error_code: str, message: str):
        super().__init__(
            status_code=409,
            error_code=error_code,
            message=message,
        )


class ValidationError(AppException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=400,
            error_code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class AuthenticationError(AppException):
    """认证失败异常（401）"""
    def __init__(self, code: str, message: str):
        super().__init__(
            status_code=401,
            error_code=code,
            message=message,
        )


class AuthorizationError(AppException):
    """授权失败异常（403）"""
    def __init__(self, code: str, message: str):
        super().__init__(
            status_code=403,
            error_code=code,
            message=message,
        )
