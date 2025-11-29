"""
Sphere 标准物资需求计算器

基于 WHO/Sphere 人道主义标准计算物资需求:
1. 按响应阶段(immediate/short_term/recovery)选择不同标准
2. 按缩放基准(人/伤员/面积)计算需求量
3. 考虑气候因素调整
4. 支持特殊需求群体(老人/儿童/残疾人)

替换旧的 SupplyDemandCalculator，提供更精确的需求估算。
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.disaster.sphere_standards import (
    ResponsePhase,
    ClimateType,
    ScalingBasis,
    SphereCategory,
    SphereStandard,
)
from src.domains.disaster.casualty_estimator import CasualtyEstimate
from src.infra.config.algorithm_config_service import (
    AlgorithmConfigService,
    ConfigurationMissingError,
)
from src.domains.disaster.sphere_standards_loader import SphereStandardsLoader

logger = logging.getLogger(__name__)


@dataclass
class SpecialNeeds:
    """特殊需求群体比例"""
    elderly_ratio: float = 0.15      # 老年人比例 (默认15%)
    children_ratio: float = 0.20     # 儿童比例 (默认20%)
    disabled_ratio: float = 0.05    # 残疾人比例 (默认5%)
    pregnant_ratio: float = 0.02    # 孕妇比例 (默认2%)
    
    def total_vulnerable_ratio(self) -> float:
        """弱势群体总比例"""
        return min(0.5, self.elderly_ratio + self.children_ratio + 
                   self.disabled_ratio + self.pregnant_ratio)


@dataclass
class SupplyRequirement:
    """物资需求项"""
    supply_code: str           # 物资编码
    supply_name: str          # 物资名称
    sphere_code: str          # Sphere标准代码
    category: str             # 品类 (WASH/FOOD/SHELTER/HEALTH/NFI)
    quantity: float           # 需求数量
    unit: str                 # 单位
    priority: str             # 优先级 (critical/high/medium/low)
    scaling_basis: str        # 计算基准
    phase: str                # 响应阶段
    notes: str = ""           # 备注


@dataclass
class DemandCalculationResult:
    """需求计算结果"""
    phase: ResponsePhase
    casualty_estimate: Optional[CasualtyEstimate]
    duration_days: int
    climate: ClimateType
    requirements: List[SupplyRequirement]
    summary: Dict[str, float]   # 按品类汇总
    elapsed_ms: int
    
    def get_category_total(self, category: str) -> float:
        """获取某品类的总需求数量"""
        return sum(r.quantity for r in self.requirements if r.category == category)


class SphereDemandCalculator:
    """
    符合 Sphere 标准的物资需求计算器
    
    主要改进:
    1. 按响应阶段选择不同标准
    2. 区分缩放基准（per_person/per_displaced/per_casualty等）
    3. 考虑气候因素
    4. 支持特殊需求群体
    5. 提供置信区间
    6. 【v19】从数据库加载配置，无Fallback
    
    注意：必须提供config_service参数，否则无法加载Sphere标准
    """

    def __init__(
        self, 
        db: Optional[AsyncSession] = None,
        config_service: Optional[AlgorithmConfigService] = None,
    ) -> None:
        self._db = db
        self._config_service = config_service
        # Sphere标准加载器（从数据库加载）
        self._standards_loader: Optional[SphereStandardsLoader] = None
        if config_service:
            self._standards_loader = SphereStandardsLoader(config_service)
        # 物资编码映射缓存 (Sphere标准代码 -> 系统物资编码)
        self._supply_code_cache: Optional[Dict[str, str]] = None

    async def calculate(
        self,
        phase: ResponsePhase,
        casualty_estimate: Optional[CasualtyEstimate] = None,
        affected_population: int = 0,
        duration_days: int = 3,
        climate: ClimateType = ClimateType.TEMPERATE,
        special_needs: Optional[SpecialNeeds] = None,
        category_filter: Optional[List[SphereCategory]] = None,
        rescuer_count: int = 0,
        command_group_count: int = 0,
        bed_count: int = 0,
    ) -> DemandCalculationResult:
        """
        计算物资需求
        
        Args:
            phase: 响应阶段 (immediate/short_term/recovery)
            casualty_estimate: 伤亡估算结果 (来自CasualtyEstimator)
            affected_population: 受影响人口 (如果没有casualty_estimate)
            duration_days: 预计持续天数
            climate: 气候类型
            special_needs: 特殊需求群体比例
            category_filter: 只计算指定品类
            rescuer_count: 救援人员总数（用于COMM/RESCUE_OPS类别）
            command_group_count: 指挥组数量（用于COMM类别）
            bed_count: 床位数量（用于医护人员配比）
            
        Returns:
            DemandCalculationResult
        """
        start_time = time.perf_counter()
        
        # 1. 确定人口基数
        if casualty_estimate:
            pop_affected = casualty_estimate.affected
            pop_displaced = casualty_estimate.displaced
            pop_casualties = casualty_estimate.total_casualties
            pop_trapped = casualty_estimate.trapped
        else:
            pop_affected = affected_population
            pop_displaced = int(affected_population * 0.3)  # 默认30%需要转移
            pop_casualties = int(affected_population * 0.01)  # 默认1%伤亡
            pop_trapped = int(affected_population * 0.005)   # 默认0.5%被困
        
        logger.info(
            f"[Sphere计算] phase={phase.value} affected={pop_affected} "
            f"displaced={pop_displaced} casualties={pop_casualties} days={duration_days}"
        )
        
        # 2. 获取适用于该阶段的Sphere标准（从数据库加载，无Fallback）
        if self._standards_loader:
            # 【v19】从数据库加载Sphere标准
            applicable_standards = await self._standards_loader.load_by_phase(phase)
        else:
            # 没有配置服务时直接报错，不使用硬编码Fallback
            raise ConfigurationMissingError(
                category="sphere",
                code="*",
            )
        
        # 3. 按品类过滤
        if category_filter:
            applicable_standards = [
                s for s in applicable_standards 
                if s.category in category_filter
            ]
        
        # 4. 加载物资编码映射
        if self._db and self._supply_code_cache is None:
            self._supply_code_cache = await self._load_supply_code_mapping()
        
        # 5. 计算每个标准的需求量
        requirements: List[SupplyRequirement] = []
        
        for std in applicable_standards:
            # 根据缩放基准选择人口基数
            base_count = self._get_base_count(
                std.scaling_basis,
                pop_affected=pop_affected,
                pop_displaced=pop_displaced,
                pop_casualties=pop_casualties,
                pop_trapped=pop_trapped,
                rescuer_count=rescuer_count,
                command_group_count=command_group_count,
                bed_count=bed_count,
            )
            
            if base_count <= 0:
                continue
            
            # 计算需求量 (包含气候调整)
            quantity = std.get_quantity(
                base_count=base_count * duration_days,
                climate=climate,
                use_target=False,  # 使用最低标准
            )
            
            # 特殊需求调整
            if special_needs:
                quantity *= (1.0 + special_needs.total_vulnerable_ratio() * 0.2)
            
            # 向上取整
            quantity = self._round_up_quantity(quantity, std.unit)
            
            # 确定优先级
            priority = self._determine_priority(std, phase)
            
            # 查找系统物资编码
            supply_code = self._get_supply_code(std.code)
            
            req = SupplyRequirement(
                supply_code=supply_code,
                supply_name=std.name_cn,
                sphere_code=std.code,
                category=std.category.value,
                quantity=quantity,
                unit=std.unit,
                priority=priority,
                scaling_basis=std.scaling_basis.value,
                phase=phase.value,
                notes=std.description,
            )
            requirements.append(req)
        
        # 6. 按优先级排序
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        requirements.sort(key=lambda r: (priority_order.get(r.priority, 9), r.category))
        
        # 7. 按品类汇总
        summary: Dict[str, float] = {}
        for req in requirements:
            key = f"{req.category}_{req.unit}"
            summary[key] = summary.get(key, 0) + req.quantity
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        logger.info(
            f"[Sphere计算] 完成: {len(requirements)}项需求, 耗时{elapsed_ms}ms"
        )
        
        return DemandCalculationResult(
            phase=phase,
            casualty_estimate=casualty_estimate,
            duration_days=duration_days,
            climate=climate,
            requirements=requirements,
            summary=summary,
            elapsed_ms=elapsed_ms,
        )

    async def calculate_multi_phase(
        self,
        casualty_estimate: CasualtyEstimate,
        phase_durations: Dict[ResponsePhase, int],
        climate: ClimateType = ClimateType.TEMPERATE,
    ) -> Dict[ResponsePhase, DemandCalculationResult]:
        """
        计算多阶段物资需求
        
        Args:
            casualty_estimate: 伤亡估算
            phase_durations: 各阶段持续天数 {IMMEDIATE: 3, SHORT_TERM: 14, ...}
            climate: 气候类型
            
        Returns:
            各阶段的需求计算结果
        """
        results = {}
        
        for phase, days in phase_durations.items():
            if days > 0:
                results[phase] = await self.calculate(
                    phase=phase,
                    casualty_estimate=casualty_estimate,
                    duration_days=days,
                    climate=climate,
                )
        
        return results

    def _get_base_count(
        self,
        scaling_basis: ScalingBasis,
        pop_affected: int,
        pop_displaced: int,
        pop_casualties: int,
        pop_trapped: int,
        rescuer_count: int = 0,
        command_group_count: int = 0,
        bed_count: int = 0,
    ) -> int:
        """
        根据缩放基准获取人口/资源基数
        
        v2扩展: 支持救援人员、指挥组、床位等新缩放基准
        """
        mapping = {
            ScalingBasis.PER_PERSON: pop_affected,
            ScalingBasis.PER_DISPLACED: pop_displaced,
            ScalingBasis.PER_CASUALTY: pop_casualties,
            ScalingBasis.PER_TRAPPED: pop_trapped,
            ScalingBasis.PER_AREA_KM2: 1,  # 面积需要外部传入
            ScalingBasis.PER_TEAM: 1,       # 队伍数需要外部传入
            ScalingBasis.FIXED: 1,
            # v2: 新增缩放基准
            ScalingBasis.PER_RESCUER: rescuer_count,
            ScalingBasis.PER_COMMAND_GROUP: command_group_count,
            ScalingBasis.PER_BED: bed_count,
        }
        return mapping.get(scaling_basis, pop_affected)

    def _determine_priority(
        self,
        std: SphereStandard,
        phase: ResponsePhase,
    ) -> str:
        """确定物资优先级"""
        # 立即响应阶段的核心物资
        if phase == ResponsePhase.IMMEDIATE:
            if std.category in [SphereCategory.WASH, SphereCategory.HEALTH]:
                return "critical"
            if std.code in ["SPHERE-FOOD-002", "SPHERE-SHELTER-003"]:
                return "critical"
            # 通信设备在立即响应阶段是关键
            if std.category == SphereCategory.COMM:
                return "critical"
            # 救援人员保障是高优先级
            if std.category == SphereCategory.RESCUE_OPS:
                return "high"
            return "high"
        
        # 短期救济阶段
        if phase == ResponsePhase.SHORT_TERM:
            if std.category == SphereCategory.SHELTER:
                return "critical"
            if std.category in [SphereCategory.WASH, SphereCategory.FOOD]:
                return "high"
            # 通信和救援人员保障继续保持高优先级
            if std.category in [SphereCategory.COMM, SphereCategory.RESCUE_OPS]:
                return "high"
            return "medium"
        
        # 恢复重建阶段
        return "medium"

    async def _load_supply_code_mapping(self) -> Dict[str, str]:
        """
        从数据库加载 Sphere 标准代码到系统物资编码的映射
        
        查找 supplies_v2 中 properties.sphere_code 字段
        """
        mapping = {}
        
        if not self._db:
            return mapping
        
        try:
            sql = text("""
                SELECT 
                    code,
                    properties->>'sphere_code' AS sphere_code
                FROM operational_v2.supplies_v2
                WHERE properties->>'sphere_code' IS NOT NULL
            """)
            result = await self._db.execute(sql)
            
            for row in result.fetchall():
                if row.sphere_code:
                    mapping[row.sphere_code] = row.code
            
            logger.info(f"[Sphere计算] 加载{len(mapping)}个物资编码映射")
            
        except Exception as e:
            logger.warning(f"[Sphere计算] 加载物资编码映射失败: {e}")
        
        return mapping

    def _get_supply_code(self, sphere_code: str) -> str:
        """获取系统物资编码，如果没有映射则返回Sphere代码"""
        if self._supply_code_cache:
            return self._supply_code_cache.get(sphere_code, sphere_code)
        return sphere_code

    def _round_up_quantity(self, quantity: float, unit: str) -> float:
        """向上取整数量"""
        if unit in ["unit", "piece", "set", "pack", "box", "kit"]:
            return float(math.ceil(quantity))
        elif unit in ["liter", "kg", "m2"]:
            return round(quantity, 1)
        else:
            return round(quantity, 2)


# =============================================================================
# 便捷函数
# =============================================================================

async def calculate_earthquake_demand(
    db: AsyncSession,
    magnitude: float,
    affected_population: int,
    building_type: str = "C",
    duration_days: int = 3,
    climate: ClimateType = ClimateType.TEMPERATE,
) -> Tuple[CasualtyEstimate, DemandCalculationResult]:
    """
    地震物资需求计算便捷函数
    
    一站式完成伤亡估算和物资需求计算。
    
    Args:
        db: 数据库会话
        magnitude: 震级
        affected_population: 受影响人口
        building_type: 建筑类型 (A-E)
        duration_days: 响应天数
        climate: 气候类型
        
    Returns:
        (伤亡估算, 物资需求)
    """
    from src.domains.disaster.casualty_estimator import (
        CasualtyEstimator,
        BuildingVulnerability,
    )
    
    # 1. 伤亡估算
    estimator = CasualtyEstimator()
    building = BuildingVulnerability(building_type)
    
    casualty = estimator.estimate_earthquake(
        magnitude=magnitude,
        depth_km=15,  # 默认深度
        population=affected_population,
        building_type=building,
    )
    
    # 2. 物资需求计算
    calculator = SphereDemandCalculator(db)
    demand = await calculator.calculate(
        phase=ResponsePhase.IMMEDIATE,
        casualty_estimate=casualty,
        duration_days=duration_days,
        climate=climate,
    )
    
    return casualty, demand
