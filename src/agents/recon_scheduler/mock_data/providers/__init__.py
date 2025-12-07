"""Provider接口和Mock实现导出"""
from __future__ import annotations

from .base_provider import (
    CommCoverageProvider,
    DeviceDataProvider,
    Point3D,
    DeviceProfile,
    BatteryHealth,
    EnergyParams,
    CoverageResult,
)
from .mock_comm_provider import MockCommCoverageProvider
from .mock_device_provider import MockDeviceDataProvider

_comm_provider: CommCoverageProvider | None = None
_device_provider: DeviceDataProvider | None = None


def get_comm_provider() -> CommCoverageProvider:
    """获取通信覆盖Provider（懒加载单例）"""
    global _comm_provider
    if _comm_provider is None:
        _comm_provider = MockCommCoverageProvider()
    return _comm_provider


def get_device_provider() -> DeviceDataProvider:
    """获取设备数据Provider（懒加载单例）"""
    global _device_provider
    if _device_provider is None:
        _device_provider = MockDeviceDataProvider()
    return _device_provider


__all__ = [
    "CommCoverageProvider",
    "DeviceDataProvider",
    "Point3D",
    "DeviceProfile",
    "BatteryHealth",
    "EnergyParams",
    "CoverageResult",
    "MockCommCoverageProvider",
    "MockDeviceDataProvider",
    "get_comm_provider",
    "get_device_provider",
]
