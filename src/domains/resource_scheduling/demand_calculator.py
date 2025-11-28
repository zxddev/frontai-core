"""
物资需求计算器

根据灾情计算物资需求量:
1. 优先从 supplies_v2 查询物资及其 properties 中的需求参数
2. 根据受灾人数和持续天数计算总需求量
3. 考虑优先级和紧急程度

与 equipment_preparation 智能体共享相同的物资编码体系。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .equipment_schemas import SupplyRequirement

logger = logging.getLogger(__name__)


@dataclass
class SupplyStandard:
    """物资需求标准"""
    supply_code: str
    supply_name: str
    category: str
    per_person_per_day: float
    unit: str
    priority: str


@dataclass
class DemandCalculationResult:
    """需求计算结果"""
    disaster_type: str
    affected_count: int
    duration_days: int
    requirements: List[SupplyRequirement]
    elapsed_ms: int
    source: str  # "database" or "default"


class SupplyDemandCalculator:
    """
    物资需求计算器
    
    根据灾害类型、受灾人数、持续天数计算物资需求。
    """

    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self._db = db

    async def calculate(
        self,
        disaster_type: str,
        affected_count: int,
        duration_days: int = 3,
        trapped_count: int = 0,
        priority_filter: Optional[List[str]] = None,
    ) -> DemandCalculationResult:
        """
        计算物资需求
        
        Args:
            disaster_type: 灾害类型（earthquake/flood/fire/hazmat/landslide）
            affected_count: 受灾人数（包括疏散安置人员）
            duration_days: 预计持续天数
            trapped_count: 被困人数（需要额外的救援物资）
            priority_filter: 只返回指定优先级的物资
            
        Returns:
            DemandCalculationResult
        """
        start_time = time.perf_counter()
        logger.info(
            f"[物资需求计算] 开始 disaster={disaster_type} "
            f"affected={affected_count} trapped={trapped_count} days={duration_days}"
        )

        # 1. 查询物资需求标准
        standards, source = await self._get_supply_standards(disaster_type)
        
        if not standards:
            logger.warning(f"[物资需求计算] 未找到{disaster_type}的物资标准")
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return DemandCalculationResult(
                disaster_type=disaster_type,
                affected_count=affected_count,
                duration_days=duration_days,
                requirements=[],
                elapsed_ms=elapsed_ms,
                source=source,
            )

        # 2. 计算需求量
        requirements: List[SupplyRequirement] = []
        
        for std in standards:
            # 过滤优先级
            if priority_filter and std.priority not in priority_filter:
                continue

            # 计算基础需求 = 人数 × 人均每天 × 天数
            base_quantity = affected_count * std.per_person_per_day * duration_days

            # 被困人员可能需要额外物资（医疗类增加50%）
            if trapped_count > 0 and std.category in ["medical", "rescue"]:
                extra = trapped_count * std.per_person_per_day * duration_days * 0.5
                base_quantity += extra

            # 向上取整
            quantity = self._round_up_quantity(base_quantity, std.unit)

            req = SupplyRequirement(
                supply_code=std.supply_code,
                supply_name=std.supply_name,
                category=std.category,
                quantity=quantity,
                unit=std.unit,
                priority=std.priority,
            )
            requirements.append(req)

        # 按优先级排序
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        requirements.sort(key=lambda r: priority_order.get(r.priority, 9))

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"[物资需求计算] 完成: {len(requirements)}种物资, "
            f"来源={source}, 耗时{elapsed_ms}ms"
        )

        return DemandCalculationResult(
            disaster_type=disaster_type,
            affected_count=affected_count,
            duration_days=duration_days,
            requirements=requirements,
            elapsed_ms=elapsed_ms,
            source=source,
        )

    async def _get_supply_standards(
        self,
        disaster_type: str,
    ) -> tuple[List[SupplyStandard], str]:
        """
        获取物资需求标准
        
        从 supplies_v2 表查询适用于该灾害类型的物资，
        使用 properties.per_person_per_day 作为需求计算参数。
        """
        if self._db is not None:
            standards = await self._query_supplies_as_standards(disaster_type)
            if standards:
                return standards, "supplies_v2"

        logger.warning(f"[物资需求计算] 无法从数据库获取{disaster_type}的物资标准")
        return [], "none"

    async def _query_supplies_as_standards(
        self,
        disaster_type: str,
    ) -> List[SupplyStandard]:
        """
        从 supplies_v2 表查询物资作为需求标准
        
        使用 applicable_disasters 和 required_for_disasters 过滤，
        从 properties JSON 读取 per_person_per_day 参数。
        """
        sql = text("""
            SELECT 
                code AS supply_code,
                name AS supply_name, 
                category,
                COALESCE((properties->>'per_person_per_day')::float, 1.0) AS per_person_per_day,
                COALESCE(unit, 'piece') AS unit,
                CASE 
                    WHEN :disaster_type = ANY(required_for_disasters) THEN 'critical'
                    WHEN :disaster_type = ANY(applicable_disasters) THEN 'high'
                    ELSE 'medium'
                END AS priority
            FROM operational_v2.supplies_v2
            WHERE :disaster_type = ANY(applicable_disasters)
               OR :disaster_type = ANY(required_for_disasters)
               OR category IN ('medical', 'life')
            ORDER BY 
                CASE 
                    WHEN :disaster_type = ANY(required_for_disasters) THEN 1
                    WHEN :disaster_type = ANY(applicable_disasters) THEN 2
                    ELSE 3
                END,
                category,
                code
        """)

        try:
            result = await self._db.execute(sql, {"disaster_type": disaster_type})
            
            standards: List[SupplyStandard] = []
            for row in result.fetchall():
                std = SupplyStandard(
                    supply_code=row.supply_code,
                    supply_name=row.supply_name,
                    category=row.category,
                    per_person_per_day=float(row.per_person_per_day),
                    unit=row.unit,
                    priority=row.priority,
                )
                standards.append(std)

            logger.info(f"[物资需求计算] 从supplies_v2查询到{len(standards)}种物资")
            return standards

        except Exception as e:
            logger.warning(f"[物资需求计算] 查询supplies_v2失败: {e}")
            return []

    def _round_up_quantity(self, quantity: float, unit: str) -> float:
        """
        向上取整数量
        
        对于大单位（如帐篷）取整数，小单位（如升）保留1位小数。
        """
        if unit in ["unit", "piece", "set", "pack", "box"]:
            # 整数单位，向上取整
            import math
            return float(math.ceil(quantity))
        else:
            # 其他单位，保留1位小数
            return round(quantity, 1)


