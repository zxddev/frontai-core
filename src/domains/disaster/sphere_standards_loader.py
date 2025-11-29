"""
Sphere标准数据库加载器

从 config.algorithm_parameters 表加载Sphere人道主义标准，
替代 sphere_standards.py 中的硬编码 SPHERE_STANDARDS 字典。

设计原则：
1. 无Fallback：数据库中找不到配置时直接报错
2. 缓存优化：使用内存缓存减少重复查询
3. 类型安全：将JSONB转换为强类型的 SphereStandard 对象

使用示例：
```python
loader = SphereStandardsLoader(config_service)

# 加载所有标准
standards = await loader.load_all()

# 按类别加载
wash_standards = await loader.load_by_category(SphereCategory.WASH)

# 按阶段加载
immediate_standards = await loader.load_by_phase(ResponsePhase.IMMEDIATE)
```
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from src.infra.config.algorithm_config_service import (
    AlgorithmConfigService,
    ConfigurationMissingError,
)
from src.domains.disaster.sphere_standards import (
    ResponsePhase,
    ClimateType,
    ScalingBasis,
    SphereCategory,
    SphereStandard,
)

logger = logging.getLogger(__name__)


class SphereStandardsLoader:
    """
    Sphere标准数据库加载器
    
    从数据库加载Sphere标准，替代硬编码的SPHERE_STANDARDS字典。
    加载的数据会在内存中缓存，避免重复查询。
    """
    
    # 数据库中的类别名
    CATEGORY = "sphere"
    
    def __init__(self, config_service: AlgorithmConfigService):
        self._config = config_service
        self._cache: Optional[dict[str, SphereStandard]] = None
    
    async def load_all(
        self,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
        force_refresh: bool = False,
    ) -> dict[str, SphereStandard]:
        """
        加载所有Sphere标准
        
        Args:
            region_code: 地区代码（用于加载地区定制配置）
            department_code: 部门代码（用于加载部门定制配置）
            force_refresh: 强制刷新缓存
            
        Returns:
            {code: SphereStandard} 字典
            
        Raises:
            ConfigurationMissingError: 数据库中没有Sphere标准时抛出
        """
        # 检查缓存（注意：缓存不区分region/department，需要时可以扩展）
        if self._cache and not force_refresh and not region_code and not department_code:
            return self._cache
        
        # 从数据库加载
        raw_params = await self._config.get_all_by_category(
            self.CATEGORY,
            region_code=region_code,
            department_code=department_code,
        )
        
        # 转换为SphereStandard对象
        standards = {}
        for code, params in raw_params.items():
            try:
                standard = self._parse_standard(code, params)
                standards[code] = standard
            except Exception as e:
                # 配置格式错误也是严重问题，不应该被忽略
                logger.error(f"[SphereLoader] 解析标准失败: {code}, error={e}")
                raise ConfigurationMissingError(
                    category=self.CATEGORY,
                    code=code,
                ) from e
        
        logger.info(f"[SphereLoader] 从数据库加载{len(standards)}条Sphere标准")
        
        # 更新缓存（仅缓存全国通用配置）
        if not region_code and not department_code:
            self._cache = standards
        
        return standards
    
    async def load_by_code(
        self,
        code: str,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> SphereStandard:
        """
        加载单个Sphere标准
        
        Args:
            code: 标准编码 (如 SPHERE-WASH-001)
            region_code: 地区代码
            department_code: 部门代码
            
        Returns:
            SphereStandard对象
            
        Raises:
            ConfigurationMissingError: 找不到指定标准时抛出
        """
        params = await self._config.get_or_raise(
            self.CATEGORY,
            code,
            region_code=region_code,
            department_code=department_code,
        )
        
        return self._parse_standard(code, params)
    
    async def load_by_category(
        self,
        category: SphereCategory,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> list[SphereStandard]:
        """
        按Sphere类别加载标准（WASH/FOOD/SHELTER等）
        
        Args:
            category: Sphere类别
            region_code: 地区代码
            department_code: 部门代码
            
        Returns:
            该类别的所有标准列表
        """
        all_standards = await self.load_all(region_code, department_code)
        
        return [
            std for std in all_standards.values()
            if std.category == category
        ]
    
    async def load_by_phase(
        self,
        phase: ResponsePhase,
        region_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> list[SphereStandard]:
        """
        按响应阶段加载适用的标准
        
        Args:
            phase: 响应阶段 (immediate/short_term/recovery)
            region_code: 地区代码
            department_code: 部门代码
            
        Returns:
            该阶段适用的所有标准列表
        """
        all_standards = await self.load_all(region_code, department_code)
        
        return [
            std for std in all_standards.values()
            if std.applies_to_phase(phase)
        ]
    
    def clear_cache(self) -> None:
        """清除内存缓存"""
        self._cache = None
        logger.debug("[SphereLoader] 内存缓存已清除")
    
    def _parse_standard(self, code: str, params: dict[str, Any]) -> SphereStandard:
        """
        将JSONB参数解析为SphereStandard对象
        
        Args:
            code: 标准编码
            params: 从数据库加载的JSONB参数
            
        Returns:
            SphereStandard对象
        """
        # 解析applicable_phases
        phase_strs = params.get("applicable_phases", [])
        applicable_phases = frozenset(
            ResponsePhase(p) for p in phase_strs
        )
        
        # 解析climate_factors
        climate_factors_raw = params.get("climate_factors", {})
        climate_factors = {
            ClimateType(k): v 
            for k, v in climate_factors_raw.items()
        }
        
        # 解析scaling_basis
        scaling_basis = ScalingBasis(params["scaling_basis"])
        
        # 解析category（从code推断，如SPHERE-WASH-001 -> WASH）
        category_str = self._infer_category_from_code(code)
        category = SphereCategory(category_str)
        
        return SphereStandard(
            code=code,
            name=params.get("name", code),  # 从数据库name字段获取，如果没有用code
            name_cn=params.get("name_cn", ""),
            category=category,
            min_quantity=params["min_quantity"],
            target_quantity=params["target_quantity"],
            unit=params["unit"],
            scaling_basis=scaling_basis,
            applicable_phases=applicable_phases,
            climate_factors=climate_factors,
            reference=params.get("reference", ""),
            description=params.get("description", ""),
        )
    
    def _infer_category_from_code(self, code: str) -> str:
        """
        从编码推断Sphere类别
        
        编码格式: SPHERE-{CATEGORY}-{NUMBER}
        例如: SPHERE-WASH-001 -> WASH
              SPHERE-COMM-002 -> COMM
              SPHERE-RES-001 -> RESCUE_OPS
        """
        parts = code.split("-")
        if len(parts) >= 2:
            cat = parts[1]
            # 特殊映射
            if cat == "RES":
                return "RESCUE_OPS"
            return cat
        return "OTHER"


# =============================================================================
# 便捷函数
# =============================================================================

async def get_sphere_standards(
    config_service: AlgorithmConfigService,
    region_code: Optional[str] = None,
    department_code: Optional[str] = None,
) -> dict[str, SphereStandard]:
    """
    便捷函数：获取所有Sphere标准
    
    Args:
        config_service: 配置服务实例
        region_code: 地区代码
        department_code: 部门代码
        
    Returns:
        {code: SphereStandard} 字典
    """
    loader = SphereStandardsLoader(config_service)
    return await loader.load_all(region_code, department_code)


async def get_standards_by_phase(
    config_service: AlgorithmConfigService,
    phase: ResponsePhase,
    region_code: Optional[str] = None,
    department_code: Optional[str] = None,
) -> list[SphereStandard]:
    """
    便捷函数：获取指定阶段的Sphere标准
    
    Args:
        config_service: 配置服务实例
        phase: 响应阶段
        region_code: 地区代码
        department_code: 部门代码
        
    Returns:
        该阶段适用的标准列表
    """
    loader = SphereStandardsLoader(config_service)
    return await loader.load_by_phase(phase, region_code, department_code)
