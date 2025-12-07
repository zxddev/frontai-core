"""
Provider Protocol 定义

定义通信覆盖和设备数据的抽象接口，支持Mock和真实数据源切换。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from datetime import datetime


@dataclass(frozen=True)
class Point3D:
    """3D坐标点 (WGS84)"""
    lat: float
    lng: float
    alt: float  # 海拔高度 (m), EGM96 geoid

    def to_tuple(self) -> tuple[float, float, float]:
        return (self.lat, self.lng, self.alt)


@dataclass
class BatteryHealth:
    """电池健康状态"""
    device_id: str
    capacity_mah: int
    voltage_v: float
    cycle_count: int
    health_percent: float  # 0-100
    temperature_c: float
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class EnergyParams:
    """能耗计算参数"""
    base_consumption_per_km: float  # %/km
    climb_consumption_per_100m: float  # %/100m
    hover_consumption_per_min: float  # %/min
    cruise_speed_ms: float  # m/s
    max_payload_kg: float
    battery_health_factor: float = 1.0  # 电池老化系数


@dataclass
class DeviceProfile:
    """设备配置"""
    device_id: str
    device_type: str  # e.g., "DJI_M30T"
    category: str  # "multirotor" | "fixed_wing"
    energy_params: EnergyParams
    max_speed_ms: float
    max_altitude_m: float
    max_wind_resistance_ms: float
    max_endurance_min: float = 30.0  # 最大续航时间（分钟）
    validation_retries: int = 3  # 设备级重试次数覆盖


@dataclass
class CoverageResult:
    """覆盖检测结果"""
    point: Point3D
    signal_dbm: float
    has_coverage: bool  # signal_dbm >= -90
    nearest_station_id: str | None = None
    line_of_sight: bool = True


@runtime_checkable
class CommCoverageProvider(Protocol):
    """通信覆盖数据Provider接口"""

    async def get_signal_strength(
        self, lat: float, lng: float, alt: float
    ) -> float:
        """
        获取指定位置的信号强度
        
        Args:
            lat: 纬度 (WGS84)
            lng: 经度 (WGS84)
            alt: 海拔高度 (m)
        
        Returns:
            信号强度 (dBm), 无信号返回 -120
        """
        ...

    async def check_line_of_sight(
        self, p1: Point3D, p2: Point3D
    ) -> bool:
        """
        检查两点之间是否有视距（无地形遮挡）
        
        Args:
            p1: 起点
            p2: 终点
        
        Returns:
            True if 有视距, False if 被遮挡
        """
        ...

    async def predict_coverage_along_path(
        self, path: list[Point3D], sample_interval_m: float = 100.0
    ) -> list[CoverageResult]:
        """
        预测路径上各采样点的信号覆盖
        
        Args:
            path: 路径点列表
            sample_interval_m: 采样间隔 (m)
        
        Returns:
            各采样点的覆盖结果
        """
        ...

    async def find_blind_zones(
        self, path: list[Point3D], threshold_dbm: float = -90.0
    ) -> list[tuple[int, int]]:
        """
        找出路径上的盲区段
        
        Args:
            path: 路径点列表
            threshold_dbm: 信号阈值
        
        Returns:
            盲区段索引列表 [(start_idx, end_idx), ...]
        """
        ...


@runtime_checkable
class DeviceDataProvider(Protocol):
    """设备数据Provider接口"""

    async def get_device_profile(self, device_id: str) -> DeviceProfile | None:
        """
        获取设备配置
        
        Args:
            device_id: 设备ID
        
        Returns:
            设备配置，不存在返回 None
        """
        ...

    async def get_battery_health(self, device_id: str) -> BatteryHealth | None:
        """
        获取电池健康状态
        
        Args:
            device_id: 设备ID
        
        Returns:
            电池状态，不存在返回 None
        """
        ...

    async def list_available_devices(
        self, category: str | None = None
    ) -> list[str]:
        """
        列出可用设备ID
        
        Args:
            category: 设备类型过滤，None表示全部
        
        Returns:
            设备ID列表
        """
        ...

    async def get_energy_params(self, device_id: str) -> EnergyParams | None:
        """
        获取设备能耗参数
        
        Args:
            device_id: 设备ID
        
        Returns:
            能耗参数，不存在返回 None
        """
        ...
