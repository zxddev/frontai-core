"""
GIS服务：提供地理信息查询

目前基于本地数据库/配置实现，未来可接入外部GIS API。
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class LocationInfo:
    """位置信息"""
    address: str
    population_density: float  # 人/km2
    terrain_type: str          # urban/suburban/rural/mountain
    elevation: float = 0.0     # 海拔(m)
    
class GISService:
    """GIS服务单例"""
    
    # 预置的区域数据 (模拟GIS数据库)
    # 茂县及周边区域
    _PRESET_ZONES = [
        {
            "name": "茂县凤仪镇 (城区)",
            "bounds": (103.84, 31.67, 103.87, 31.69), # min_lon, min_lat, max_lon, max_lat
            "density": 5000,
            "terrain": "urban",
            "elevation": 1580
        },
        {
            "name": "茂县南新镇",
            "bounds": (103.85, 31.60, 103.90, 31.66),
            "density": 2000,
            "terrain": "suburban",
            "elevation": 1600
        },
        {
            "name": "成都市区",
            "bounds": (104.0, 30.5, 104.1, 30.7),
            "density": 15000,
            "terrain": "urban",
            "elevation": 500
        }
    ]
    
    # 默认值
    _DEFAULT_DENSITY = 1000.0
    _DEFAULT_TERRAIN = "mountain"  # 默认山区（川西特点）
    
    @classmethod
    async def get_location_info(cls, lat: float, lon: float) -> LocationInfo:
        """
        获取位置详细信息
        
        Args:
            lat: 纬度
            lon: 经度
            
        Returns:
            位置信息对象
        """
        # 1. 查找预置区域
        for zone in cls._PRESET_ZONES:
            min_lon, min_lat, max_lon, max_lat = zone["bounds"]
            if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
                logger.info(f"[GIS] 命中预置区域: {zone['name']}")
                return LocationInfo(
                    address=zone["name"],
                    population_density=zone["density"],
                    terrain_type=zone["terrain"],
                    elevation=zone["elevation"]
                )
        
        # 2. 未命中，返回默认值 (带有一定的随机扰动以模拟真实感?) 
        # 不，工程化要严谨，返回默认值并记录日志
        logger.info(f"[GIS] 未命中预置区域，使用默认参数: lat={lat}, lon={lon}")
        
        return LocationInfo(
            address=f"未知区域 ({lat:.4f}, {lon:.4f})",
            population_density=cls._DEFAULT_DENSITY,
            terrain_type=cls._DEFAULT_TERRAIN,
            elevation=1000.0
        )

    @classmethod
    async def get_distance_matrix(cls, origins: list, destinations: list) -> list:
        """获取距离矩阵 (预留接口)"""
        # 目前资源匹配模块自己算了Haversine，这里先留空
        pass
