"""
地形检测器

基于 DEM 数据进行 3D 地形碰撞检测。
支持 Mock 模式和真实 DEM 模式。

DEM 数据源 (spec定义):
- File: data/四川省.tif (SRTM 30m resolution)
- CRS: EPSG:4326 (WGS84)
- Height baseline: EGM96 geoid
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger(__name__)

# DEM 文件路径
DEFAULT_DEM_PATH = Path("data/四川省.tif")

# 安全间隙
DEFAULT_TERRAIN_CLEARANCE_M = 30.0  # 最小离地高度
DEFAULT_OBSTACLE_CLEARANCE_M = 50.0  # 障碍物安全间隙


@dataclass
class TerrainPoint:
    """地形点"""
    lat: float
    lng: float
    ground_elevation_m: float  # 地面高程 (EGM96 geoid)
    

@dataclass
class CollisionResult:
    """碰撞检测结果"""
    has_collision: bool
    collision_points: list[dict]  # [{lat, lng, flight_alt, ground_alt, clearance}]
    min_clearance_m: float
    max_ground_elevation_m: float


class TerrainChecker:
    """
    地形检测器
    
    支持两种模式:
    - Mock 模式: 使用简化的高程模型 (基于经纬度估算)
    - DEM 模式: 使用真实 DEM 数据 (rasterio)
    """
    
    def __init__(
        self,
        dem_path: Optional[Path] = None,
        use_mock: bool = True,
        terrain_clearance_m: float = DEFAULT_TERRAIN_CLEARANCE_M
    ):
        self._dem_path = dem_path or DEFAULT_DEM_PATH
        self._use_mock = use_mock
        self._terrain_clearance = terrain_clearance_m
        self._dem = None
        
        if not use_mock:
            self._load_dem()
    
    def _load_dem(self) -> None:
        """加载 DEM 数据"""
        try:
            import rasterio
            if self._dem_path.exists():
                self._dem = rasterio.open(self._dem_path)
                logger.info(f"DEM loaded: {self._dem_path}")
            else:
                logger.warning(f"DEM file not found: {self._dem_path}, falling back to mock")
                self._use_mock = True
        except ImportError:
            logger.warning("rasterio not installed, using mock terrain")
            self._use_mock = True
        except Exception as e:
            logger.error(f"Failed to load DEM: {e}, using mock terrain")
            self._use_mock = True
    
    def _get_mock_elevation(self, lat: float, lng: float) -> float:
        """
        Mock 高程模型
        
        茂县区域 (31.5-32.0, 103.5-104.0) 高程范围约 1500-4000m
        使用简化模型: 基础高程 + 山脊模拟
        """
        # 基础高程 (茂县县城约1600m)
        base_elevation = 1600.0
        
        # 模拟山脊 (北部和西部较高)
        lat_factor = (lat - 31.5) * 500  # 越北越高
        lng_factor = (104.0 - lng) * 300  # 越西越高
        
        # 添加一些随机性 (基于经纬度的确定性变化)
        variation = math.sin(lat * 100) * 50 + math.cos(lng * 100) * 30
        
        elevation = base_elevation + lat_factor + lng_factor + variation
        
        # 限制范围
        return max(1200.0, min(4500.0, elevation))
    
    def _get_dem_elevation(self, lat: float, lng: float) -> float:
        """从 DEM 获取高程"""
        if self._dem is None:
            return self._get_mock_elevation(lat, lng)
        
        try:
            # 将经纬度转换为像素坐标
            row, col = self._dem.index(lng, lat)
            # 读取高程值
            elevation = self._dem.read(1)[row, col]
            
            # 处理无效值
            if elevation < -1000 or elevation > 10000:
                return self._get_mock_elevation(lat, lng)
            
            return float(elevation)
        except Exception:
            return self._get_mock_elevation(lat, lng)
    
    def get_elevation(self, lat: float, lng: float) -> float:
        """
        获取指定位置的地面高程
        
        Args:
            lat: 纬度 (WGS84)
            lng: 经度 (WGS84)
        
        Returns:
            地面高程 (m, EGM96 geoid)
        """
        if self._use_mock:
            return self._get_mock_elevation(lat, lng)
        return self._get_dem_elevation(lat, lng)
    
    def get_elevation_along_path(
        self,
        waypoints: Sequence[dict],
        sample_interval_m: float = 50.0
    ) -> list[TerrainPoint]:
        """
        获取路径上的地形高程序列
        
        Args:
            waypoints: 航点列表 [{lat, lng, alt_m}, ...]
            sample_interval_m: 采样间隔 (m)
        
        Returns:
            地形点列表
        """
        terrain_points = []
        
        for i, wp in enumerate(waypoints):
            lat, lng = wp["lat"], wp["lng"]
            elevation = self.get_elevation(lat, lng)
            terrain_points.append(TerrainPoint(lat=lat, lng=lng, ground_elevation_m=elevation))
            
            # 在航段中间采样
            if i < len(waypoints) - 1:
                next_wp = waypoints[i + 1]
                # 计算航段距离
                dist = self._calculate_distance(lat, lng, next_wp["lat"], next_wp["lng"])
                num_samples = max(1, int(dist / sample_interval_m))
                
                for j in range(1, num_samples):
                    t = j / num_samples
                    sample_lat = lat + t * (next_wp["lat"] - lat)
                    sample_lng = lng + t * (next_wp["lng"] - lng)
                    sample_elev = self.get_elevation(sample_lat, sample_lng)
                    terrain_points.append(TerrainPoint(
                        lat=sample_lat, lng=sample_lng, ground_elevation_m=sample_elev
                    ))
        
        return terrain_points
    
    def check_terrain_collision(
        self,
        waypoints: Sequence[dict],
        clearance_m: Optional[float] = None
    ) -> CollisionResult:
        """
        检测航线是否与地形碰撞
        
        Args:
            waypoints: 航点列表 [{lat, lng, alt_m}, ...]
            clearance_m: 最小离地高度 (m)
        
        Returns:
            碰撞检测结果
        """
        clearance = clearance_m or self._terrain_clearance
        collision_points = []
        min_clearance = float('inf')
        max_ground = 0.0
        
        for i, wp in enumerate(waypoints):
            lat, lng = wp["lat"], wp["lng"]
            flight_alt = wp.get("alt_m", 100)
            ground_alt = self.get_elevation(lat, lng)
            
            actual_clearance = flight_alt - ground_alt
            min_clearance = min(min_clearance, actual_clearance)
            max_ground = max(max_ground, ground_alt)
            
            if actual_clearance < clearance:
                collision_points.append({
                    "waypoint_idx": i,
                    "lat": lat,
                    "lng": lng,
                    "flight_alt_m": flight_alt,
                    "ground_alt_m": ground_alt,
                    "clearance_m": actual_clearance,
                    "required_clearance_m": clearance,
                })
            
            # 检查航段中间点
            if i < len(waypoints) - 1:
                next_wp = waypoints[i + 1]
                # 简化: 检查中点
                mid_lat = (lat + next_wp["lat"]) / 2
                mid_lng = (lng + next_wp["lng"]) / 2
                mid_flight_alt = (flight_alt + next_wp.get("alt_m", 100)) / 2
                mid_ground = self.get_elevation(mid_lat, mid_lng)
                
                mid_clearance = mid_flight_alt - mid_ground
                min_clearance = min(min_clearance, mid_clearance)
                max_ground = max(max_ground, mid_ground)
                
                if mid_clearance < clearance:
                    collision_points.append({
                        "waypoint_idx": f"{i}-{i+1}_mid",
                        "lat": mid_lat,
                        "lng": mid_lng,
                        "flight_alt_m": mid_flight_alt,
                        "ground_alt_m": mid_ground,
                        "clearance_m": mid_clearance,
                        "required_clearance_m": clearance,
                    })
        
        return CollisionResult(
            has_collision=len(collision_points) > 0,
            collision_points=collision_points,
            min_clearance_m=min_clearance if min_clearance != float('inf') else 0.0,
            max_ground_elevation_m=max_ground,
        )
    
    def get_safe_altitude(
        self,
        waypoints: Sequence[dict],
        clearance_m: Optional[float] = None
    ) -> float:
        """
        计算安全飞行高度
        
        Args:
            waypoints: 航点列表
            clearance_m: 最小离地高度
        
        Returns:
            建议的最小飞行高度 (m, MSL)
        """
        clearance = clearance_m or self._terrain_clearance
        max_ground = 0.0
        
        for wp in waypoints:
            ground = self.get_elevation(wp["lat"], wp["lng"])
            max_ground = max(max_ground, ground)
        
        return max_ground + clearance
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """计算两点间距离 (m)"""
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


# 全局实例 (懒加载)
_terrain_checker: Optional[TerrainChecker] = None


def get_terrain_checker(use_mock: bool = True) -> TerrainChecker:
    """获取地形检测器实例"""
    global _terrain_checker
    if _terrain_checker is None:
        _terrain_checker = TerrainChecker(use_mock=use_mock)
    return _terrain_checker
