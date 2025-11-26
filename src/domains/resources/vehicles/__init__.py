"""
车辆管理模块

对应SQL表: operational_v2.vehicles_v2
"""

from .router import router
from .service import VehicleService
from .schemas import (
    VehicleCreate, VehicleUpdate, VehicleResponse, 
    VehicleListResponse, VehicleType, VehicleStatus
)

__all__ = [
    "router",
    "VehicleService", 
    "VehicleCreate", 
    "VehicleUpdate", 
    "VehicleResponse",
    "VehicleListResponse",
    "VehicleType",
    "VehicleStatus",
]
