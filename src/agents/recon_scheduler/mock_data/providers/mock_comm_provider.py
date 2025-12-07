"""
通信覆盖Mock Provider

基于预定义的基站位置和简化的信号衰减模型，模拟通信覆盖。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .base_provider import (
    CommCoverageProvider,
    Point3D,
    CoverageResult,
)


class MockCommCoverageProvider:
    """通信覆盖Mock实现"""

    def __init__(self, data_path: Path | str | None = None):
        if data_path is None:
            data_path = Path(__file__).parent.parent / "comm_coverage.json"
        self._data_path = Path(data_path)
        self._data: dict[str, Any] | None = None
        self._base_stations: list[dict] = []
        self._blind_zones: list[dict] = []

    def _load_data(self) -> None:
        """懒加载数据"""
        if self._data is not None:
            return
        if self._data_path.exists():
            with open(self._data_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._base_stations = self._data.get("base_stations", [])
            self._blind_zones = self._data.get("blind_zones", [])
        else:
            self._data = {}
            self._base_stations = self._get_default_stations()
            self._blind_zones = []

    def _get_default_stations(self) -> list[dict]:
        """默认基站配置（四川茂县区域）"""
        return [
            {
                "id": "bs_maoxian_01",
                "name": "茂县主基站",
                "location": {"lat": 31.68, "lng": 103.85, "alt": 1600},
                "power_dbm": 43,
                "frequency_mhz": 1800,
            },
            {
                "id": "bs_maoxian_02",
                "name": "茂县北基站",
                "location": {"lat": 31.75, "lng": 103.88, "alt": 1800},
                "power_dbm": 40,
                "frequency_mhz": 1800,
            },
        ]

    def _calculate_distance(
        self, lat1: float, lng1: float, alt1: float,
        lat2: float, lng2: float, alt2: float
    ) -> float:
        """计算两点间的3D距离 (m)"""
        R = 6371000  # 地球半径 (m)
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        horizontal_dist = R * c

        vertical_dist = abs(alt2 - alt1)
        return math.sqrt(horizontal_dist ** 2 + vertical_dist ** 2)

    def _calculate_signal_strength(
        self, distance_m: float, power_dbm: float, frequency_mhz: float
    ) -> float:
        """
        简化的自由空间路径损耗模型
        FSPL(dB) = 20*log10(d) + 20*log10(f) - 27.55
        """
        if distance_m < 1:
            distance_m = 1
        fspl = 20 * math.log10(distance_m) + 20 * math.log10(frequency_mhz) - 27.55
        return power_dbm - fspl

    def _is_in_blind_zone(self, lat: float, lng: float) -> bool:
        """检查点是否在盲区内"""
        for zone in self._blind_zones:
            geometry = zone.get("geometry", {})
            if geometry.get("type") == "Polygon":
                coords = geometry.get("coordinates", [[]])[0]
                if self._point_in_polygon(lat, lng, coords):
                    return True
        return False

    def _point_in_polygon(
        self, lat: float, lng: float, polygon: list[list[float]]
    ) -> bool:
        """射线法判断点是否在多边形内"""
        n = len(polygon)
        if n < 3:
            return False
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i][0], polygon[i][1]  # lng, lat
            xj, yj = polygon[j][0], polygon[j][1]
            if ((yi > lat) != (yj > lat)) and \
               (lng < (xj - xi) * (lat - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    async def get_signal_strength(
        self, lat: float, lng: float, alt: float
    ) -> float:
        """获取指定位置的信号强度 (dBm)"""
        self._load_data()

        if self._is_in_blind_zone(lat, lng):
            return -120.0

        max_signal = -120.0
        for station in self._base_stations:
            loc = station["location"]
            distance = self._calculate_distance(
                lat, lng, alt,
                loc["lat"], loc["lng"], loc["alt"]
            )
            signal = self._calculate_signal_strength(
                distance,
                station["power_dbm"],
                station["frequency_mhz"]
            )
            max_signal = max(max_signal, signal)

        return max_signal

    async def check_line_of_sight(
        self, p1: Point3D, p2: Point3D
    ) -> bool:
        """检查两点之间是否有视距"""
        self._load_data()
        num_samples = 10
        for i in range(num_samples + 1):
            t = i / num_samples
            lat = p1.lat + t * (p2.lat - p1.lat)
            lng = p1.lng + t * (p2.lng - p1.lng)
            if self._is_in_blind_zone(lat, lng):
                return False
        return True

    async def predict_coverage_along_path(
        self, path: list[Point3D], sample_interval_m: float = 100.0
    ) -> list[CoverageResult]:
        """预测路径上各采样点的信号覆盖"""
        self._load_data()
        results: list[CoverageResult] = []

        for point in path:
            signal = await self.get_signal_strength(point.lat, point.lng, point.alt)
            has_coverage = signal >= -90.0

            nearest_station_id = None
            min_dist = float("inf")
            for station in self._base_stations:
                loc = station["location"]
                dist = self._calculate_distance(
                    point.lat, point.lng, point.alt,
                    loc["lat"], loc["lng"], loc["alt"]
                )
                if dist < min_dist:
                    min_dist = dist
                    nearest_station_id = station["id"]

            results.append(CoverageResult(
                point=point,
                signal_dbm=signal,
                has_coverage=has_coverage,
                nearest_station_id=nearest_station_id,
                line_of_sight=not self._is_in_blind_zone(point.lat, point.lng),
            ))

        return results

    async def find_blind_zones(
        self, path: list[Point3D], threshold_dbm: float = -90.0
    ) -> list[tuple[int, int]]:
        """找出路径上的盲区段"""
        coverage_results = await self.predict_coverage_along_path(path)
        blind_segments: list[tuple[int, int]] = []
        in_blind = False
        start_idx = 0

        for i, result in enumerate(coverage_results):
            if result.signal_dbm < threshold_dbm:
                if not in_blind:
                    in_blind = True
                    start_idx = i
            else:
                if in_blind:
                    blind_segments.append((start_idx, i - 1))
                    in_blind = False

        if in_blind:
            blind_segments.append((start_idx, len(path) - 1))

        return blind_segments


CommCoverageProvider.register(MockCommCoverageProvider)
