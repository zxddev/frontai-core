"""
物资需求计算器

根据灾情计算物资需求量:
1. 从supply_standards_v2查询物资需求标准
2. 根据受灾人数和持续天数计算总需求量
3. 考虑优先级和紧急程度
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


# 内置默认标准（数据库无数据时使用）
DEFAULT_SUPPLY_STANDARDS: Dict[str, Dict[str, Dict]] = {
    "earthquake": {
        "SP-LIFE-WATER": {"name": "饮用水", "per_day": 2.5, "unit": "liter", "priority": "critical"},
        "SP-LIFE-FOOD": {"name": "应急食品", "per_day": 0.5, "unit": "kg", "priority": "critical"},
        "SP-SHELTER-TENT": {"name": "救灾帐篷", "per_day": 0.2, "unit": "unit", "priority": "high"},
        "SP-SHELTER-BLANKET": {"name": "保暖毯", "per_day": 1.0, "unit": "piece", "priority": "high"},
        "SP-MED-KIT": {"name": "急救包", "per_day": 0.1, "unit": "set", "priority": "high"},
    },
    "flood": {
        "SP-LIFE-WATER": {"name": "饮用水", "per_day": 3.0, "unit": "liter", "priority": "critical"},
        "SP-LIFE-FOOD": {"name": "应急食品", "per_day": 0.5, "unit": "kg", "priority": "critical"},
        "SP-WATER-VEST": {"name": "救生衣", "per_day": 1.0, "unit": "piece", "priority": "critical"},
        "SP-SHELTER-TENT": {"name": "救灾帐篷", "per_day": 0.2, "unit": "unit", "priority": "high"},
        "SP-MED-KIT": {"name": "急救包", "per_day": 0.15, "unit": "set", "priority": "high"},
    },
    "fire": {
        "SP-LIFE-WATER": {"name": "饮用水", "per_day": 3.0, "unit": "liter", "priority": "critical"},
        "SP-MED-KIT": {"name": "急救包", "per_day": 0.2, "unit": "set", "priority": "critical"},
        "SP-MED-BURN": {"name": "烧伤药膏", "per_day": 0.5, "unit": "tube", "priority": "critical"},
        "SP-PROT-MASK": {"name": "防烟面罩", "per_day": 1.0, "unit": "piece", "priority": "critical"},
    },
    "hazmat": {
        "SP-LIFE-WATER": {"name": "饮用水", "per_day": 2.5, "unit": "liter", "priority": "critical"},
        "SP-MED-KIT": {"name": "急救包", "per_day": 0.2, "unit": "set", "priority": "critical"},
        "SP-PROT-MASK": {"name": "防毒面具", "per_day": 1.0, "unit": "piece", "priority": "critical"},
        "SP-MED-ANTIDOTE": {"name": "解毒药品", "per_day": 0.5, "unit": "dose", "priority": "critical"},
    },
    "landslide": {
        "SP-LIFE-WATER": {"name": "饮用水", "per_day": 2.5, "unit": "liter", "priority": "critical"},
        "SP-LIFE-FOOD": {"name": "应急食品", "per_day": 0.5, "unit": "kg", "priority": "critical"},
        "SP-SHELTER-TENT": {"name": "救灾帐篷", "per_day": 0.2, "unit": "unit", "priority": "high"},
        "SP-MED-KIT": {"name": "急救包", "per_day": 0.15, "unit": "set", "priority": "high"},
    },
}


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
        
        优先从数据库查询，无数据时使用内置默认值。
        """
        # 尝试从数据库查询
        if self._db is not None:
            standards = await self._query_standards_from_db(disaster_type)
            if standards:
                return standards, "database"

        # 使用内置默认值
        defaults = DEFAULT_SUPPLY_STANDARDS.get(disaster_type, {})
        standards = []
        for code, info in defaults.items():
            std = SupplyStandard(
                supply_code=code,
                supply_name=info.get("name", code),
                category=info.get("category", "life"),
                per_person_per_day=info.get("per_day", 1.0),
                unit=info.get("unit", "unit"),
                priority=info.get("priority", "medium"),
            )
            standards.append(std)

        return standards, "default"

    async def _query_standards_from_db(
        self,
        disaster_type: str,
    ) -> List[SupplyStandard]:
        """从数据库查询物资标准"""
        sql = text("""
            SELECT 
                supply_code,
                supply_name,
                COALESCE(supply_category, 'life') as category,
                per_person_per_day,
                unit,
                priority
            FROM operational_v2.supply_standards_v2
            WHERE disaster_type = :disaster_type
            ORDER BY 
                CASE priority 
                    WHEN 'critical' THEN 1 
                    WHEN 'high' THEN 2 
                    WHEN 'medium' THEN 3 
                    ELSE 4 
                END
        """)

        try:
            result = await self._db.execute(sql, {"disaster_type": disaster_type})
            
            standards: List[SupplyStandard] = []
            for row in result.fetchall():
                std = SupplyStandard(
                    supply_code=row[0],
                    supply_name=row[1] or row[0],
                    category=row[2],
                    per_person_per_day=float(row[3]),
                    unit=row[4],
                    priority=row[5],
                )
                standards.append(std)

            return standards

        except Exception as e:
            logger.warning(f"[物资需求计算] 数据库查询失败: {e}")
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

    def calculate_sync(
        self,
        disaster_type: str,
        affected_count: int,
        duration_days: int = 3,
        trapped_count: int = 0,
    ) -> List[SupplyRequirement]:
        """
        同步版本的需求计算（不查数据库，只用默认值）
        
        用于不需要异步的场景。
        """
        defaults = DEFAULT_SUPPLY_STANDARDS.get(disaster_type, {})
        requirements: List[SupplyRequirement] = []

        for code, info in defaults.items():
            per_day = info.get("per_day", 1.0)
            base_quantity = affected_count * per_day * duration_days

            if trapped_count > 0 and info.get("category") in ["medical", "rescue"]:
                base_quantity += trapped_count * per_day * duration_days * 0.5

            quantity = self._round_up_quantity(base_quantity, info.get("unit", "unit"))

            req = SupplyRequirement(
                supply_code=code,
                supply_name=info.get("name", code),
                category=info.get("category", "life"),
                quantity=quantity,
                unit=info.get("unit", "unit"),
                priority=info.get("priority", "medium"),
            )
            requirements.append(req)

        return requirements
