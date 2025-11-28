"""
风险区域管理模块

提供风险区域的创建、查询、更新、删除等接口
"""

from .router import router
from .schemas import (
    RiskAreaType,
    SeverityLevel,
    PassageStatus,
    RiskAreaCreateRequest,
    RiskAreaUpdateRequest,
    RiskAreaResponse,
)

__all__ = [
    "router",
    "RiskAreaType",
    "SeverityLevel",
    "PassageStatus",
    "RiskAreaCreateRequest",
    "RiskAreaUpdateRequest",
    "RiskAreaResponse",
]
