# 侦察调度模拟数据

本目录存放侦察Agent的模拟数据，用于演示系统。后期接入真实数据时，只需实现对应的Provider接口。

## 目录结构

```
mock_data/
├── __init__.py              # 模块导出
├── README.md                # 本文档
├── comm_coverage.json       # 通信覆盖模拟数据
├── device_profiles.json     # 设备参数模拟数据
└── providers/
    ├── __init__.py          # Provider导出
    ├── base_provider.py     # Protocol接口定义
    ├── mock_comm_provider.py    # 通信覆盖Mock实现
    └── mock_device_provider.py  # 设备数据Mock实现
```

## 数据格式

### comm_coverage.json

通信覆盖栅格数据，基于基站位置和地形计算信号强度。

```json
{
  "version": "1.0.0",
  "base_stations": [
    {
      "id": "bs_001",
      "name": "茂县基站",
      "location": {"lat": 31.68, "lng": 103.85, "alt": 1600},
      "power_dbm": 43,
      "frequency_mhz": 1800
    }
  ],
  "coverage_grid": {
    "bounds": {"min_lat": 31.5, "max_lat": 31.9, "min_lng": 103.7, "max_lng": 104.1},
    "resolution_m": 100,
    "data": [[...]]  // 信号强度矩阵 (dBm)
  },
  "blind_zones": [
    {
      "id": "bz_001",
      "geometry": {"type": "Polygon", "coordinates": [...]},
      "reason": "山体遮挡"
    }
  ]
}
```

### device_profiles.json

设备能耗参数，用于动态能耗计算。

```json
{
  "version": "1.0.0",
  "devices": [
    {
      "device_type": "DJI_M30T",
      "category": "multirotor",
      "base_consumption_per_km": 3.0,      // %/km
      "climb_consumption_per_100m": 2.0,   // %/100m
      "hover_consumption_per_min": 1.5,    // %/min
      "cruise_speed_ms": 15.0,
      "max_speed_ms": 23.0,
      "max_payload_kg": 0.5,
      "max_altitude_m": 500,
      "max_wind_resistance_ms": 12.0,
      "battery": {
        "capacity_mah": 5000,
        "voltage_v": 22.2,
        "cycle_count": 50,
        "health_percent": 95
      }
    }
  ]
}
```

## 接入真实数据

1. 实现 `CommCoverageProvider` 接口，查询真实通信覆盖服务
2. 实现 `DeviceDataProvider` 接口，查询设备管理系统
3. 修改 `get_comm_provider()` / `get_device_provider()` 返回真实实现
4. 或通过环境变量 `RECON_DATA_SOURCE=real` 切换

## Provider接口

```python
from typing import Protocol

class CommCoverageProvider(Protocol):
    async def get_signal_strength(self, lat: float, lng: float, alt: float) -> float:
        """获取指定位置的信号强度 (dBm)"""
        ...
    
    async def check_line_of_sight(self, p1: Point3D, p2: Point3D) -> bool:
        """检查两点之间是否有视距"""
        ...
    
    async def predict_coverage_along_path(self, path: list[Point3D]) -> list[float]:
        """预测路径上各点的信号强度"""
        ...

class DeviceDataProvider(Protocol):
    async def get_device_profile(self, device_id: str) -> DeviceProfile:
        """获取设备参数"""
        ...
    
    async def get_battery_health(self, device_id: str) -> BatteryHealth:
        """获取电池健康状态"""
        ...
```
