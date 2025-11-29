"""
路由参数数据库加载器

从 config.algorithm_parameters 表加载道路速度和地形系数，
替代 db_route_engine.py 中的硬编码常量。

设计原则：
1. 无Fallback：数据库中找不到配置时直接报错
2. 缓存优化：使用内存缓存减少重复查询

使用示例：
```python
loader = RoutingConfigLoader(config_service)

# 获取道路速度
speed = await loader.get_road_speed("motorway")  # 返回 120

# 获取地形系数
factor = await loader.get_terrain_factor("mountain")  # 返回 0.6

# 批量加载
road_speeds = await loader.get_all_road_speeds()
terrain_factors = await loader.get_all_terrain_factors()
```
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.infra.config.algorithm_config_service import (
    AlgorithmConfigService,
    ConfigurationMissingError,
)

logger = logging.getLogger(__name__)


@dataclass
class RoadSpeedParams:
    """道路速度参数"""
    road_type: str
    default_speed_kmh: int
    min_speed_kmh: int
    max_speed_kmh: int


@dataclass
class VehicleSpeedLimits:
    """车辆类型速度限制"""
    vehicle_type: str
    max_speed_kmh: int
    urban_limit_kmh: int
    emergency_bonus: float = 1.0
    terrain_independent: bool = False


@dataclass
class DisasterImpactParams:
    """灾害影响参数"""
    disaster_type: str
    params: dict[str, Any]


class RoutingConfigLoader:
    """
    路由参数数据库加载器
    
    从数据库加载道路速度、地形系数等路由相关参数。
    """
    
    CATEGORY = "routing"
    
    def __init__(self, config_service: AlgorithmConfigService):
        self._config = config_service
        # 内存缓存
        self._road_speeds_cache: Optional[dict[str, int]] = None
        self._terrain_factors_cache: Optional[dict[str, float]] = None
        self._vehicle_limits_cache: Optional[dict[str, VehicleSpeedLimits]] = None
        self._disaster_impact_cache: Optional[dict[str, Any]] = None
    
    async def get_road_speed(
        self,
        road_type: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> int:
        """
        获取道路类型默认速度
        
        Args:
            road_type: 道路类型 (motorway/trunk/primary/secondary等)
            region_code: 地区代码
            department_code: 部门代码
            
        Returns:
            默认速度 (km/h)
        """
        # 先尝试缓存
        if self._road_speeds_cache and not region_code and not department_code:
            road_type_upper = road_type.upper()
            if road_type_upper in self._road_speeds_cache:
                return self._road_speeds_cache[road_type_upper]
        
        code = f"ROAD-SPEED-{road_type.upper()}"
        params = await self._config.get_or_raise(
            self.CATEGORY,
            code,
            region_code=region_code,
            department_code=department_code,
        )
        
        return params["default_speed_kmh"]
    
    async def get_all_road_speeds(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, int]:
        """
        获取所有道路类型的速度
        
        Returns:
            {road_type: speed_kmh} 字典
        """
        if self._road_speeds_cache and not region_code and not department_code:
            return self._road_speeds_cache
        
        all_params = await self._config.get_all_by_category(self.CATEGORY)
        
        result = {}
        for code, params in all_params.items():
            if code.startswith("ROAD-SPEED-"):
                road_type = code.replace("ROAD-SPEED-", "").lower()
                result[road_type] = params["default_speed_kmh"]
        
        if not region_code and not department_code:
            self._road_speeds_cache = result
        
        logger.info(f"[RoutingLoader] 加载{len(result)}种道路类型速度")
        return result
    
    async def get_terrain_factor(
        self,
        terrain_type: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> float:
        """
        获取地形速度系数
        
        Args:
            terrain_type: 地形类型 (urban/suburban/mountain等)
            
        Returns:
            速度调整系数 (0.0-1.0)
        """
        factors = await self.get_all_terrain_factors(region_code, department_code)
        
        if terrain_type not in factors:
            raise ConfigurationMissingError(
                category=self.CATEGORY,
                code=f"TERRAIN-FACTORS.{terrain_type}",
            )
        
        return factors[terrain_type]
    
    async def get_all_terrain_factors(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, float]:
        """
        获取所有地形类型的速度系数
        
        Returns:
            {terrain_type: factor} 字典
        """
        if self._terrain_factors_cache and not region_code and not department_code:
            return self._terrain_factors_cache
        
        params = await self._config.get_or_raise(
            self.CATEGORY,
            "TERRAIN-FACTORS",
            region_code=region_code,
            department_code=department_code,
        )
        
        if not region_code and not department_code:
            self._terrain_factors_cache = params
        
        return params
    
    async def get_vehicle_speed_limits(
        self,
        vehicle_type: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> VehicleSpeedLimits:
        """
        获取车辆类型速度限制
        
        Args:
            vehicle_type: 车辆类型 (car/truck/ambulance/fire_truck等)
            
        Returns:
            VehicleSpeedLimits 对象
        """
        all_limits = await self.get_all_vehicle_speed_limits(region_code, department_code)
        
        if vehicle_type not in all_limits:
            raise ConfigurationMissingError(
                category=self.CATEGORY,
                code=f"VEHICLE-SPEED-LIMITS.{vehicle_type}",
            )
        
        return all_limits[vehicle_type]
    
    async def get_all_vehicle_speed_limits(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, VehicleSpeedLimits]:
        """
        获取所有车辆类型的速度限制
        
        Returns:
            {vehicle_type: VehicleSpeedLimits} 字典
        """
        if self._vehicle_limits_cache and not region_code and not department_code:
            return self._vehicle_limits_cache
        
        params = await self._config.get_or_raise(
            self.CATEGORY,
            "VEHICLE-SPEED-LIMITS",
            region_code=region_code,
            department_code=department_code,
        )
        
        result = {}
        for vtype, limits in params.items():
            result[vtype] = VehicleSpeedLimits(
                vehicle_type=vtype,
                max_speed_kmh=limits["max_speed_kmh"],
                urban_limit_kmh=limits["urban_limit_kmh"],
                emergency_bonus=limits.get("emergency_bonus", 1.0),
                terrain_independent=limits.get("terrain_independent", False),
            )
        
        if not region_code and not department_code:
            self._vehicle_limits_cache = result
        
        return result
    
    async def get_disaster_impact_params(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        获取灾害对道路影响的参数
        
        Returns:
            {disaster_type: params} 字典
        """
        if self._disaster_impact_cache and not region_code and not department_code:
            return self._disaster_impact_cache
        
        params = await self._config.get_or_raise(
            self.CATEGORY,
            "DISASTER-IMPACT-FACTORS",
            region_code=region_code,
            department_code=department_code,
        )
        
        if not region_code and not department_code:
            self._disaster_impact_cache = params
        
        return params
    
    def clear_cache(self) -> None:
        """清除内存缓存"""
        self._road_speeds_cache = None
        self._terrain_factors_cache = None
        self._vehicle_limits_cache = None
        self._disaster_impact_cache = None
        logger.debug("[RoutingLoader] 内存缓存已清除")
