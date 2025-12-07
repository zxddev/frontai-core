"""
侦察调度模拟数据模块

为演示系统提供模拟数据，后期可替换为真实数据源。
数据源切换通过 Provider 接口实现，无需修改业务代码。
"""
from __future__ import annotations

from .providers import (
    CommCoverageProvider,
    DeviceDataProvider,
    MockCommCoverageProvider,
    MockDeviceDataProvider,
    Point3D,
    DeviceProfile,
    BatteryHealth,
    EnergyParams,
    CoverageResult,
    get_comm_provider,
    get_device_provider,
)

__all__ = [
    "CommCoverageProvider",
    "DeviceDataProvider",
    "MockCommCoverageProvider",
    "MockDeviceDataProvider",
    "Point3D",
    "DeviceProfile",
    "BatteryHealth",
    "EnergyParams",
    "CoverageResult",
    "get_comm_provider",
    "get_device_provider",
]
