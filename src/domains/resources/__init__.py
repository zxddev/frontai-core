"""
资源管理模块

包含:
- vehicles: 车辆管理 (operational_v2.vehicles_v2)
- teams: 救援队伍管理 (operational_v2.rescue_teams_v2)
- devices: 设备管理 (operational_v2.devices_v2)
"""

from .vehicles.router import router as vehicles_router
from .teams.router import router as teams_router
from .devices.router import router as devices_router

__all__ = [
    "vehicles_router",
    "teams_router", 
    "devices_router",
]
