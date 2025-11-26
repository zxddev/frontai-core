"""
前端API通用响应格式

前端期望的响应结构: {code, message, data, timestamp}
"""

from datetime import datetime
from typing import TypeVar, Generic, Optional, Any

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    前端统一响应格式
    
    code: 200成功，其他为错误码
    message: 响应消息
    data: 业务数据
    timestamp: ISO8601时间戳
    """
    code: int = Field(default=200, description="响应码，200表示成功")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="业务数据")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="时间戳")

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> "ApiResponse[T]":
        """成功响应"""
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Any = None) -> "ApiResponse":
        """错误响应"""
        return cls(code=code, message=message, data=data)


class PageData(BaseModel, Generic[T]):
    """分页数据结构"""
    items: list[T] = Field(default_factory=list, description="当前页数据")
    total: int = Field(default=0, description="总数量")
    page: int = Field(default=1, description="当前页码")
    pageSize: int = Field(default=20, description="每页数量")
    totalPages: int = Field(default=0, description="总页数")
