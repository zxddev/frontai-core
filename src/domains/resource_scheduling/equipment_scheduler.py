"""
装备调度器

根据能力需求推断并调度装备:
1. 查询能力→装备映射（capability_equipment_v2）
2. 查询可用装备（devices_v2 + supplies_v2 where is_consumable=false）
3. 选择最优装备组合（距离最近、满足数量）
"""
from __future__ import annotations

import logging
import math
import time
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .equipment_schemas import (
    EquipmentType,
    EquipmentPriority,
    LocationType,
    EquipmentRequirement,
    EquipmentCandidate,
    EquipmentAllocation,
    EquipmentSchedulingResult,
)

logger = logging.getLogger(__name__)


class EquipmentScheduler:
    """
    装备调度器
    
    根据能力需求推断所需装备，并从可用库存中选择最优分配。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def schedule(
        self,
        capability_codes: List[str],
        destination_lon: float,
        destination_lat: float,
        max_distance_km: float = 100.0,
    ) -> EquipmentSchedulingResult:
        """
        执行装备调度
        
        Args:
            capability_codes: 能力编码列表
            destination_lon: 目标点经度
            destination_lat: 目标点纬度
            max_distance_km: 最大搜索距离
            
        Returns:
            EquipmentSchedulingResult
        """
        start_time = time.perf_counter()
        logger.info(
            f"[装备调度] 开始 capabilities={capability_codes} "
            f"destination=({destination_lon:.4f},{destination_lat:.4f})"
        )

        errors: List[str] = []
        warnings: List[str] = []

        # 1. 查询能力→装备映射
        requirements = await self._query_equipment_requirements(capability_codes)
        
        if not requirements:
            logger.warning("[装备调度] 未找到能力对应的装备需求映射")
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return EquipmentSchedulingResult(
                success=True,
                allocations=[],
                required_met=0,
                required_total=0,
                recommended_met=0,
                recommended_total=0,
                total_equipment_count=0,
                elapsed_ms=elapsed_ms,
                warnings=["未找到能力对应的装备需求"],
            )

        logger.info(f"[装备调度] 需要的装备: {len(requirements)}种")

        # 统计必须/推荐装备数量
        required_reqs = [r for r in requirements if r.priority == EquipmentPriority.REQUIRED]
        recommended_reqs = [r for r in requirements if r.priority == EquipmentPriority.RECOMMENDED]

        # 2. 查询可用装备
        candidates = await self._query_available_equipment(
            requirements=requirements,
            destination_lon=destination_lon,
            destination_lat=destination_lat,
            max_distance_km=max_distance_km,
        )

        logger.info(f"[装备调度] 找到候选装备: {len(candidates)}个")

        # 3. 分配装备（贪心策略：距离最近优先）
        allocations, met_requirements = self._allocate_equipment(
            requirements=requirements,
            candidates=candidates,
        )

        # 计算满足率
        required_met = len([r for r in required_reqs if r.equipment_code in met_requirements])
        recommended_met = len([r for r in recommended_reqs if r.equipment_code in met_requirements])

        # 检查必须装备是否全部满足
        unmet_required = [r for r in required_reqs if r.equipment_code not in met_requirements]
        if unmet_required:
            for r in unmet_required:
                warnings.append(f"必须装备未满足: {r.equipment_name}({r.equipment_code})")

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"[装备调度] 完成: 分配{len(allocations)}件装备, "
            f"必须{required_met}/{len(required_reqs)}, "
            f"推荐{recommended_met}/{len(recommended_reqs)}, "
            f"耗时{elapsed_ms}ms"
        )

        return EquipmentSchedulingResult(
            success=required_met == len(required_reqs),
            allocations=allocations,
            required_met=required_met,
            required_total=len(required_reqs),
            recommended_met=recommended_met,
            recommended_total=len(recommended_reqs),
            total_equipment_count=sum(a.allocated_quantity for a in allocations),
            elapsed_ms=elapsed_ms,
            errors=errors,
            warnings=warnings,
        )

    async def _query_equipment_requirements(
        self,
        capability_codes: List[str],
    ) -> List[EquipmentRequirement]:
        """从capability_equipment_v2查询能力对应的装备需求"""
        if not capability_codes:
            return []

        sql = text("""
            SELECT 
                capability_code,
                capability_name,
                equipment_type,
                equipment_code,
                equipment_name,
                min_quantity,
                max_quantity,
                priority,
                description
            FROM operational_v2.capability_equipment_v2
            WHERE capability_code = ANY(:capability_codes)
            ORDER BY 
                CASE priority 
                    WHEN 'required' THEN 1 
                    WHEN 'recommended' THEN 2 
                    ELSE 3 
                END,
                capability_code
        """)

        result = await self._db.execute(sql, {"capability_codes": capability_codes})
        
        requirements: List[EquipmentRequirement] = []
        for row in result.fetchall():
            req = EquipmentRequirement(
                capability_code=row[0],
                equipment_type=EquipmentType(row[2]),
                equipment_code=row[3],
                equipment_name=row[4] or "",
                min_quantity=row[5] or 1,
                max_quantity=row[6],
                priority=EquipmentPriority(row[7]) if row[7] else EquipmentPriority.REQUIRED,
                description=row[8] or "",
            )
            requirements.append(req)

        return requirements

    async def _query_available_equipment(
        self,
        requirements: List[EquipmentRequirement],
        destination_lon: float,
        destination_lat: float,
        max_distance_km: float,
    ) -> List[EquipmentCandidate]:
        """查询可用装备（设备+非消耗品物资）"""
        # 分类装备编码
        device_codes = [r.equipment_code for r in requirements if r.equipment_type == EquipmentType.DEVICE]
        supply_codes = [r.equipment_code for r in requirements if r.equipment_type == EquipmentType.SUPPLY]

        candidates: List[EquipmentCandidate] = []

        # 1. 查询设备（devices_v2）
        if device_codes:
            device_candidates = await self._query_devices(
                device_codes=device_codes,
                destination_lon=destination_lon,
                destination_lat=destination_lat,
                max_distance_km=max_distance_km,
            )
            candidates.extend(device_candidates)

        # 2. 查询非消耗品物资（supplies_v2 where is_consumable=false）
        # 物资可能在队伍自带或仓库中
        if supply_codes:
            supply_candidates = await self._query_equipment_supplies(
                supply_codes=supply_codes,
                destination_lon=destination_lon,
                destination_lat=destination_lat,
                max_distance_km=max_distance_km,
            )
            candidates.extend(supply_candidates)

        return candidates

    async def _query_devices(
        self,
        device_codes: List[str],
        destination_lon: float,
        destination_lat: float,
        max_distance_km: float,
    ) -> List[EquipmentCandidate]:
        """查询可用设备"""
        sql = text("""
            SELECT 
                d.id,
                d.code,
                d.name,
                d.base_capabilities,
                -- 设备位置：优先使用关联实体的位置，否则使用车辆位置
                COALESCE(e.longitude, v_loc.longitude) as longitude,
                COALESCE(e.latitude, v_loc.latitude) as latitude,
                d.in_vehicle_id,
                v.name as vehicle_name,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(
                        COALESCE(e.longitude, v_loc.longitude, 0), 
                        COALESCE(e.latitude, v_loc.latitude, 0)
                    ), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography
                ) / 1000.0 as distance_km
            FROM operational_v2.devices_v2 d
            LEFT JOIN operational_v2.layer_entities_v2 e ON d.entity_id = e.id
            LEFT JOIN operational_v2.vehicles_v2 v ON d.in_vehicle_id = v.id
            LEFT JOIN operational_v2.layer_entities_v2 v_loc ON v.entity_id = v_loc.id
            WHERE d.code = ANY(:device_codes)
            AND d.status = 'available'
            AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(
                    COALESCE(e.longitude, v_loc.longitude, 0), 
                    COALESCE(e.latitude, v_loc.latitude, 0)
                ), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography,
                :max_distance_m
            )
            ORDER BY distance_km ASC
        """)

        try:
            result = await self._db.execute(sql, {
                "device_codes": device_codes,
                "dest_lon": destination_lon,
                "dest_lat": destination_lat,
                "max_distance_m": max_distance_km * 1000,
            })

            candidates: List[EquipmentCandidate] = []
            for row in result.fetchall():
                # 确定位置类型
                location_type = LocationType.VEHICLE if row[6] else LocationType.WAREHOUSE
                location_id = row[6] if row[6] else row[0]  # 车辆ID或设备ID
                location_name = row[7] if row[7] else "独立设备"

                candidate = EquipmentCandidate(
                    equipment_id=row[0],
                    equipment_code=row[1],
                    equipment_name=row[2],
                    equipment_type=EquipmentType.DEVICE,
                    location_type=location_type,
                    location_id=location_id,
                    location_name=location_name,
                    longitude=row[4] or 0,
                    latitude=row[5] or 0,
                    available_quantity=1,  # 设备通常是单个
                    distance_km=row[8] or 0,
                    capabilities=row[3] or [],
                )
                candidates.append(candidate)

            return candidates
        except Exception as e:
            logger.warning(f"[装备调度] 查询设备失败: {e}")
            return []

    async def _query_equipment_supplies(
        self,
        supply_codes: List[str],
        destination_lon: float,
        destination_lat: float,
        max_distance_km: float,
    ) -> List[EquipmentCandidate]:
        """
        查询非消耗品物资（装备）
        
        物资来源:
        1. 队伍自带（通过team_capabilities或properties推断）
        2. 车辆装载（vehicle_supply_loads_v2）
        3. 仓库存储（shelters_v2 where shelter_type='supply_depot'）
        """
        # 首先从equipment_inventory_v2查询（如果有数据）
        sql_inventory = text("""
            SELECT 
                ei.equipment_id,
                ei.equipment_code,
                s.name as equipment_name,
                ei.location_type,
                ei.location_id,
                ei.location_name,
                ei.longitude,
                ei.latitude,
                ei.available_quantity,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(ei.longitude, ei.latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography
                ) / 1000.0 as distance_km
            FROM operational_v2.equipment_inventory_v2 ei
            JOIN operational_v2.supplies_v2 s ON ei.equipment_code = s.code
            WHERE ei.equipment_code = ANY(:supply_codes)
            AND ei.equipment_type = 'supply'
            AND ei.available_quantity > 0
            AND ei.longitude IS NOT NULL
            AND ei.latitude IS NOT NULL
            AND ST_DWithin(
                ST_SetSRID(ST_MakePoint(ei.longitude, ei.latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography,
                :max_distance_m
            )
            ORDER BY distance_km ASC
        """)

        try:
            result = await self._db.execute(sql_inventory, {
                "supply_codes": supply_codes,
                "dest_lon": destination_lon,
                "dest_lat": destination_lat,
                "max_distance_m": max_distance_km * 1000,
            })

            candidates: List[EquipmentCandidate] = []
            for row in result.fetchall():
                candidate = EquipmentCandidate(
                    equipment_id=row[0],
                    equipment_code=row[1],
                    equipment_name=row[2] or "",
                    equipment_type=EquipmentType.SUPPLY,
                    location_type=LocationType(row[3]),
                    location_id=row[4],
                    location_name=row[5] or "",
                    longitude=row[6],
                    latitude=row[7],
                    available_quantity=row[8],
                    distance_km=row[9] or 0,
                )
                candidates.append(candidate)

            if candidates:
                return candidates

        except Exception as e:
            logger.debug(f"[装备调度] equipment_inventory_v2查询失败（可能表不存在）: {e}")

        # 备选方案：从shelters查询物资储备点
        sql_shelter = text("""
            SELECT 
                sh.id,
                sh.name,
                ST_X(sh.location::geometry) as longitude,
                ST_Y(sh.location::geometry) as latitude,
                sh.supply_inventory,
                ST_Distance(
                    sh.location::geography,
                    ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography
                ) / 1000.0 as distance_km
            FROM public.evacuation_shelters_v2 sh
            WHERE sh.shelter_type = 'supply_depot'
            AND sh.status = 'open'
            AND ST_DWithin(
                sh.location::geography,
                ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography,
                :max_distance_m
            )
            ORDER BY distance_km ASC
            LIMIT 20
        """)

        try:
            result = await self._db.execute(sql_shelter, {
                "dest_lon": destination_lon,
                "dest_lat": destination_lat,
                "max_distance_m": max_distance_km * 1000,
            })

            candidates = []
            for row in result.fetchall():
                shelter_id = row[0]
                shelter_name = row[1]
                lon = row[2]
                lat = row[3]
                inventory = row[4] or {}
                distance = row[5]

                # 从inventory中查找匹配的装备
                for code in supply_codes:
                    # inventory格式可能是 {supply_code: quantity} 或 {supply_name: quantity}
                    quantity = inventory.get(code, 0)
                    if quantity > 0:
                        candidate = EquipmentCandidate(
                            equipment_id=shelter_id,
                            equipment_code=code,
                            equipment_name=code,
                            equipment_type=EquipmentType.SUPPLY,
                            location_type=LocationType.SHELTER,
                            location_id=shelter_id,
                            location_name=shelter_name,
                            longitude=lon,
                            latitude=lat,
                            available_quantity=quantity,
                            distance_km=distance,
                        )
                        candidates.append(candidate)

            return candidates

        except Exception as e:
            logger.warning(f"[装备调度] 查询物资储备点失败: {e}")
            return []

    def _allocate_equipment(
        self,
        requirements: List[EquipmentRequirement],
        candidates: List[EquipmentCandidate],
    ) -> Tuple[List[EquipmentAllocation], Set[str]]:
        """
        分配装备（贪心策略）
        
        按优先级处理需求，每个需求选择距离最近的候选装备。
        """
        allocations: List[EquipmentAllocation] = []
        met_requirements: Set[str] = set()
        
        # 跟踪已分配的数量
        allocated_counts: Dict[UUID, int] = {}  # {equipment_id: allocated}

        # 按优先级排序：required > recommended > optional
        sorted_requirements = sorted(
            requirements,
            key=lambda r: (
                0 if r.priority == EquipmentPriority.REQUIRED else
                1 if r.priority == EquipmentPriority.RECOMMENDED else 2
            )
        )

        for req in sorted_requirements:
            # 找到匹配的候选装备
            matching_candidates = [
                c for c in candidates
                if c.equipment_code == req.equipment_code
            ]

            # 按距离排序
            matching_candidates.sort(key=lambda c: c.distance_km)

            needed = req.min_quantity
            allocated_for_req = 0

            for candidate in matching_candidates:
                if needed <= 0:
                    break

                # 计算可分配数量
                already_allocated = allocated_counts.get(candidate.equipment_id, 0)
                available = candidate.available_quantity - already_allocated

                if available <= 0:
                    continue

                # 分配
                to_allocate = min(needed, available)
                
                allocation = EquipmentAllocation(
                    equipment_id=candidate.equipment_id,
                    equipment_code=candidate.equipment_code,
                    equipment_name=candidate.equipment_name,
                    equipment_type=candidate.equipment_type,
                    source_type=candidate.location_type,
                    source_id=candidate.location_id,
                    source_name=candidate.location_name,
                    allocated_quantity=to_allocate,
                    for_capability=req.capability_code,
                    distance_km=candidate.distance_km,
                )
                allocations.append(allocation)

                # 更新计数
                allocated_counts[candidate.equipment_id] = already_allocated + to_allocate
                allocated_for_req += to_allocate
                needed -= to_allocate

            # 检查是否满足需求
            if allocated_for_req >= req.min_quantity:
                met_requirements.add(req.equipment_code)

        return allocations, met_requirements

    @staticmethod
    def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """计算两点间的球面距离（公里）"""
        R = 6371.0
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        return R * c
