"""
设备管理模块

对应SQL表: operational_v2.devices_v2
"""

from .router import router
from .service import DeviceService
from .schemas import (
    DeviceCreate, DeviceUpdate, DeviceResponse, 
    DeviceListResponse, DeviceType, DeviceStatus
)

__all__ = [
    "router",
    "DeviceService", 
    "DeviceCreate", 
    "DeviceUpdate", 
    "DeviceResponse",
    "DeviceListResponse",
    "DeviceType",
    "DeviceStatus",
]
