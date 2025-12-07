"""
设备数据Mock Provider

基于预定义的设备配置文件，提供设备参数和电池状态。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .base_provider import (
    DeviceDataProvider,
    DeviceProfile,
    BatteryHealth,
    EnergyParams,
)


class MockDeviceDataProvider:
    """设备数据Mock实现"""

    def __init__(self, data_path: Path | str | None = None):
        if data_path is None:
            data_path = Path(__file__).parent.parent / "device_profiles.json"
        self._data_path = Path(data_path)
        self._data: dict[str, Any] | None = None
        self._devices: dict[str, dict] = {}
        self._type_mapping: dict[str, list[str]] = {}

    def _load_data(self) -> None:
        """懒加载数据"""
        if self._data is not None:
            return
        if self._data_path.exists():
            with open(self._data_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            for device in self._data.get("devices", []):
                device_id = device.get("device_id", device.get("device_type"))
                self._devices[device_id] = device
            self._type_mapping = self._data.get("device_type_mapping", {})
        else:
            self._data = {"devices": []}
            self._devices = self._get_default_devices()
            self._type_mapping = {"drone": ["multirotor", "vtol_fixed_wing"], "dog": ["ugv_quadruped"]}

    def _get_default_devices(self) -> dict[str, dict]:
        """默认设备配置（仅在配置文件不存在时使用）"""
        return {
            "dev-drone-002": {
                "device_id": "dev-drone-002",
                "device_type": "DJI_M300",
                "device_name": "经纬M300 RTK侦察无人机",
                "category": "multirotor",
                "capabilities": ["rgb_camera", "thermal_camera", "mapping"],
                "base_consumption_per_km": 4.0,
                "climb_consumption_per_100m": 2.5,
                "hover_consumption_per_min": 2.0,
                "cruise_speed_ms": 17.0,
                "max_speed_ms": 23.0,
                "max_payload_kg": 2.7,
                "max_altitude_m": 500,
                "max_wind_resistance_ms": 12.0,
                "max_endurance_min": 55,
                "effective_endurance_min": 55,
                "ready_time_min": 0,
                "validation_retries": 3,
                "battery": {
                    "capacity_mah": 10000,
                    "voltage_v": 52.8,
                    "cycle_count": 30,
                    "health_percent": 98,
                    "temperature_c": 22.0,
                },
            },
            "dev-drone-004": {
                "device_id": "dev-drone-004",
                "device_type": "DJI_MAVIC3T",
                "device_name": "御3行业版热成像无人机",
                "category": "multirotor",
                "capabilities": ["rgb_camera", "thermal_camera", "zoom_camera"],
                "base_consumption_per_km": 3.0,
                "climb_consumption_per_100m": 2.0,
                "hover_consumption_per_min": 1.5,
                "cruise_speed_ms": 15.0,
                "max_speed_ms": 21.0,
                "max_payload_kg": 0.5,
                "max_altitude_m": 500,
                "max_wind_resistance_ms": 12.0,
                "max_endurance_min": 45,
                "effective_endurance_min": 45,
                "ready_time_min": 0,
                "validation_retries": 3,
                "battery": {
                    "capacity_mah": 5000,
                    "voltage_v": 17.6,
                    "cycle_count": 50,
                    "health_percent": 95,
                    "temperature_c": 25.0,
                },
            },
        }
    
    def _get_device_type(self, category: str) -> str:
        """根据category获取设备类型（drone/dog）"""
        for dtype, categories in self._type_mapping.items():
            if category in categories:
                return dtype
        return "unknown"

    def _parse_device_profile(self, data: dict) -> DeviceProfile:
        """解析设备配置"""
        battery = data.get("battery", {})
        cycle_count = battery.get("cycle_count", 0)
        health_factor = 1 + cycle_count / 500 * 0.2

        energy_params = EnergyParams(
            base_consumption_per_km=data.get("base_consumption_per_km", 3.0),
            climb_consumption_per_100m=data.get("climb_consumption_per_100m", 2.0),
            hover_consumption_per_min=data.get("hover_consumption_per_min", 1.5),
            cruise_speed_ms=data.get("cruise_speed_ms", 15.0),
            max_payload_kg=data.get("max_payload_kg", 0.5),
            battery_health_factor=health_factor,
        )

        return DeviceProfile(
            device_id=data.get("device_id", data.get("device_type", "unknown")),
            device_type=data.get("device_type", "unknown"),
            category=data.get("category", "multirotor"),
            energy_params=energy_params,
            max_speed_ms=data.get("max_speed_ms", 23.0),
            max_altitude_m=data.get("max_altitude_m", 500),
            max_wind_resistance_ms=data.get("max_wind_resistance_ms", 12.0),
            max_endurance_min=data.get("max_endurance_min", 30.0),
            validation_retries=data.get("validation_retries", 3),
        )

    def _parse_battery_health(self, device_id: str, battery: dict) -> BatteryHealth:
        """解析电池状态"""
        return BatteryHealth(
            device_id=device_id,
            capacity_mah=battery.get("capacity_mah", 5000),
            voltage_v=battery.get("voltage_v", 22.2),
            cycle_count=battery.get("cycle_count", 0),
            health_percent=battery.get("health_percent", 100),
            temperature_c=battery.get("temperature_c", 25.0),
            last_updated=datetime.now(),
        )

    async def get_device_profile(self, device_id: str) -> DeviceProfile | None:
        """获取设备配置"""
        self._load_data()
        device_data = self._devices.get(device_id)
        if device_data is None:
            return None
        return self._parse_device_profile(device_data)

    async def get_battery_health(self, device_id: str) -> BatteryHealth | None:
        """获取电池健康状态"""
        self._load_data()
        device_data = self._devices.get(device_id)
        if device_data is None:
            return None
        battery = device_data.get("battery", {})
        return self._parse_battery_health(device_id, battery)

    async def list_available_devices(
        self, category: str | None = None
    ) -> list[str]:
        """列出可用设备ID"""
        self._load_data()
        if category is None:
            return list(self._devices.keys())
        return [
            device_id
            for device_id, data in self._devices.items()
            if data.get("category") == category
        ]

    async def get_energy_params(self, device_id: str) -> EnergyParams | None:
        """获取设备能耗参数"""
        profile = await self.get_device_profile(device_id)
        if profile is None:
            return None
        return profile.energy_params


DeviceDataProvider.register(MockDeviceDataProvider)
