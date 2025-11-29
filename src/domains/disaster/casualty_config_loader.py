"""
伤亡估算模型参数加载器

从 config.algorithm_parameters 表加载伤亡估算模型参数，
替代 casualty_estimator.py 中的硬编码系数。

设计原则：
1. 无Fallback：数据库中找不到配置时直接报错
2. 缓存优化：使用内存缓存减少重复查询
3. 类型安全：返回强类型的参数对象

使用示例：
```python
loader = CasualtyConfigLoader(config_service)

# 加载建筑脆弱性参数
params = await loader.get_building_vulnerability("C")

# 加载时间因素
time_factors = await loader.get_time_factors()

# 加载洪涝参数
flood_params = await loader.get_flood_hazard_params()
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
class BuildingVulnerabilityParams:
    """建筑脆弱性参数"""
    building_type: str
    base_rate: float           # 基础死亡率
    coefficient_b: float       # 对数衰减系数
    collapse_rate: float       # 倒塌率
    fatality_rate_if_collapsed: float  # 倒塌后死亡率
    injury_ratio_severe: float # 重伤/死亡比
    injury_ratio_minor: float  # 轻伤/死亡比
    trapped_ratio: float       # 被困率
    description_cn: str = ""


@dataclass
class TimeFactors:
    """时段室内因子"""
    night_0_6: float
    morning_6_8: float
    work_8_18: float
    evening_18_22: float
    late_22_24: float
    default: float


@dataclass
class FloodHazardParams:
    """洪涝危险度参数"""
    dv_thresholds: dict[str, dict[str, float]]  # 深度-流速阈值
    warning_time_factor: float
    night_factor: float


@dataclass
class SecondaryHazardParams:
    """次生灾害参数"""
    trigger_magnitude: float
    base_probability: float
    fatality_rate: float
    injury_rate: float
    factors: dict[str, float]  # 影响因子


class CasualtyConfigLoader:
    """
    伤亡估算参数数据库加载器
    
    从数据库加载伤亡估算模型的所有参数，替代硬编码常量。
    """
    
    CATEGORY = "casualty"
    
    def __init__(self, config_service: AlgorithmConfigService):
        self._config = config_service
        # 内存缓存
        self._building_cache: dict[str, BuildingVulnerabilityParams] = {}
        self._time_factors_cache: Optional[TimeFactors] = None
        self._flood_cache: Optional[FloodHazardParams] = None
    
    async def get_building_vulnerability(
        self,
        building_type: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> BuildingVulnerabilityParams:
        """
        获取建筑脆弱性参数
        
        Args:
            building_type: 建筑类型 (A/B/C/D/E)
            region_code: 地区代码（用于加载地区定制参数）
            department_code: 部门代码
            
        Returns:
            BuildingVulnerabilityParams 对象
            
        Raises:
            ConfigurationMissingError: 找不到配置时抛出
        """
        cache_key = f"{building_type}:{region_code}:{department_code}"
        
        if cache_key in self._building_cache:
            return self._building_cache[cache_key]
        
        code = f"CASUALTY-BUILDING-{building_type.upper()}"
        params = await self._config.get_or_raise(
            self.CATEGORY,
            code,
            region_code=region_code,
            department_code=department_code,
        )
        
        result = BuildingVulnerabilityParams(
            building_type=params["building_type"],
            base_rate=params["base_rate"],
            coefficient_b=params["coefficient_b"],
            collapse_rate=params["collapse_rate"],
            fatality_rate_if_collapsed=params["fatality_rate_if_collapsed"],
            injury_ratio_severe=params["injury_ratio_severe"],
            injury_ratio_minor=params["injury_ratio_minor"],
            trapped_ratio=params["trapped_ratio"],
            description_cn=params.get("description_cn", ""),
        )
        
        self._building_cache[cache_key] = result
        return result
    
    async def get_all_building_vulnerabilities(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> dict[str, BuildingVulnerabilityParams]:
        """
        获取所有建筑类型的脆弱性参数
        
        Returns:
            {building_type: BuildingVulnerabilityParams} 字典
        """
        result = {}
        for btype in ["A", "B", "C", "D", "E"]:
            try:
                params = await self.get_building_vulnerability(
                    btype, region_code, department_code
                )
                result[btype] = params
            except ConfigurationMissingError:
                # 某个类型不存在时记录警告但继续
                logger.warning(f"[CasualtyLoader] 建筑类型{btype}配置缺失")
        
        if not result:
            raise ConfigurationMissingError(
                category=self.CATEGORY,
                code="CASUALTY-BUILDING-*",
            )
        
        return result
    
    async def get_time_factors(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> TimeFactors:
        """
        获取时段室内因子
        
        Returns:
            TimeFactors 对象
        """
        if self._time_factors_cache:
            return self._time_factors_cache
        
        params = await self._config.get_or_raise(
            self.CATEGORY,
            "CASUALTY-TIME-FACTORS",
            region_code=region_code,
            department_code=department_code,
        )
        
        result = TimeFactors(
            night_0_6=params["night_0_6"],
            morning_6_8=params["morning_6_8"],
            work_8_18=params["work_8_18"],
            evening_18_22=params["evening_18_22"],
            late_22_24=params["late_22_24"],
            default=params["default"],
        )
        
        self._time_factors_cache = result
        return result
    
    async def get_flood_hazard_params(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> FloodHazardParams:
        """
        获取洪涝危险度参数
        
        Returns:
            FloodHazardParams 对象
        """
        if self._flood_cache:
            return self._flood_cache
        
        params = await self._config.get_or_raise(
            self.CATEGORY,
            "CASUALTY-FLOOD-DV",
            region_code=region_code,
            department_code=department_code,
        )
        
        result = FloodHazardParams(
            dv_thresholds=params["dv_thresholds"],
            warning_time_factor=params["warning_time_factor"],
            night_factor=params["night_factor"],
        )
        
        self._flood_cache = result
        return result
    
    async def get_secondary_hazard_params(
        self,
        hazard_type: str,  # "landslide" or "fire"
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> SecondaryHazardParams:
        """
        获取次生灾害参数
        
        Args:
            hazard_type: 次生灾害类型 (landslide/fire)
            
        Returns:
            SecondaryHazardParams 对象
        """
        code = f"CASUALTY-SECONDARY-{hazard_type.upper()}"
        params = await self._config.get_or_raise(
            self.CATEGORY,
            code,
            region_code=region_code,
            department_code=department_code,
        )
        
        # 根据类型解析不同的factors字段
        if hazard_type.lower() == "landslide":
            factors = params.get("slope_factor", {})
        elif hazard_type.lower() == "fire":
            factors = params.get("urban_density_factor", {})
        else:
            factors = {}
        
        return SecondaryHazardParams(
            trigger_magnitude=params["trigger_magnitude"],
            base_probability=params["base_probability"],
            fatality_rate=params["fatality_rate"],
            injury_rate=params["injury_rate"],
            factors=factors,
        )
    
    def clear_cache(self) -> None:
        """清除内存缓存"""
        self._building_cache.clear()
        self._time_factors_cache = None
        self._flood_cache = None
        logger.debug("[CasualtyLoader] 内存缓存已清除")
