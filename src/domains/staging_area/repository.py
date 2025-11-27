"""
救援队驻扎点数据访问层
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.staging_area.schemas import (
    CandidateSite,
    StagingSiteType,
    GroundStability,
    NetworkType,
)

logger = logging.getLogger(__name__)


class StagingAreaRepository:
    """驻扎点数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def search_candidates(
        self,
        scenario_id: UUID,
        center_lon: float,
        center_lat: float,
        max_distance_m: float = 50000,
        min_buffer_from_danger_m: float = 500,
        max_slope_deg: float = 15,
        require_water: bool = False,
        require_power: bool = False,
        require_helicopter: bool = False,
        max_results: int = 50,
    ) -> List[CandidateSite]:
        """
        搜索候选驻扎点
        
        使用PostGIS空间查询，排除危险区域内的点位。
        """
        sql = text("""
            SELECT 
                site_id,
                site_code,
                site_name,
                site_type,
                longitude,
                latitude,
                area_m2,
                slope_degree,
                has_water_supply,
                has_power_supply,
                can_helicopter_land,
                primary_network_type,
                distance_from_center_m,
                min_distance_to_danger_m
            FROM operational_v2.search_staging_candidates(
                :scenario_id,
                :center_lon,
                :center_lat,
                :max_distance_m,
                :min_buffer_m,
                :max_slope_deg,
                :require_water,
                :require_power,
                :require_helicopter,
                :max_results
            )
        """)
        
        try:
            result = await self._db.execute(sql, {
                "scenario_id": scenario_id,
                "center_lon": center_lon,
                "center_lat": center_lat,
                "max_distance_m": max_distance_m,
                "min_buffer_m": min_buffer_from_danger_m,
                "max_slope_deg": max_slope_deg,
                "require_water": require_water,
                "require_power": require_power,
                "require_helicopter": require_helicopter,
                "max_results": max_results,
            })
            
            candidates: List[CandidateSite] = []
            for row in result.fetchall():
                site_type = self._parse_site_type(row[3])
                network_type = self._parse_network_type(row[11])
                
                candidates.append(CandidateSite(
                    id=row[0],
                    site_code=row[1],
                    name=row[2],
                    site_type=site_type,
                    longitude=row[4],
                    latitude=row[5],
                    area_m2=float(row[6]) if row[6] else None,
                    slope_degree=float(row[7]) if row[7] else None,
                    has_water_supply=row[8] or False,
                    has_power_supply=row[9] or False,
                    can_helicopter_land=row[10] or False,
                    primary_network_type=network_type,
                    distance_to_danger_m=float(row[13]) if row[13] else None,
                    scenario_id=scenario_id,
                ))
            
            logger.info(f"[驻扎点搜索] 找到 {len(candidates)} 个候选点")
            return candidates
            
        except Exception as e:
            logger.error(f"[驻扎点搜索] 数据库查询失败: {e}")
            raise
    
    async def get_danger_zones(
        self,
        scenario_id: UUID,
    ) -> List[dict]:
        """
        获取危险区域列表
        """
        sql = text("""
            SELECT 
                id,
                area_type,
                ST_AsText(geometry) as geometry_wkt,
                risk_level,
                passable
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = :scenario_id
            AND area_type IN ('danger_zone', 'blocked', 'flooded', 'collapsed', 'fire')
        """)
        
        result = await self._db.execute(sql, {"scenario_id": scenario_id})
        zones = []
        for row in result.fetchall():
            zones.append({
                "id": row[0],
                "area_type": row[1],
                "geometry_wkt": row[2],
                "risk_level": row[3] or 5,
                "passable": row[4] or False,
            })
        return zones
    
    async def get_site_details(
        self,
        site_ids: List[UUID],
    ) -> List[CandidateSite]:
        """
        获取驻扎点详细信息
        """
        if not site_ids:
            return []
        
        sql = text("""
            SELECT 
                id,
                site_code,
                name,
                site_type,
                ST_X(location::geometry) as longitude,
                ST_Y(location::geometry) as latitude,
                area_m2,
                slope_degree,
                ground_stability,
                has_water_supply,
                has_power_supply,
                can_helicopter_land,
                primary_network_type,
                signal_quality,
                nearest_supply_depot_m,
                nearest_medical_point_m,
                nearest_command_post_m,
                scenario_id
            FROM operational_v2.rescue_staging_sites_v2
            WHERE id = ANY(:site_ids)
        """)
        
        result = await self._db.execute(sql, {"site_ids": site_ids})
        sites: List[CandidateSite] = []
        for row in result.fetchall():
            site_type = self._parse_site_type(row[3])
            ground_stability = self._parse_ground_stability(row[8])
            network_type = self._parse_network_type(row[12])
            
            sites.append(CandidateSite(
                id=row[0],
                site_code=row[1],
                name=row[2],
                site_type=site_type,
                longitude=row[4],
                latitude=row[5],
                area_m2=float(row[6]) if row[6] else None,
                slope_degree=float(row[7]) if row[7] else None,
                ground_stability=ground_stability,
                has_water_supply=row[9] or False,
                has_power_supply=row[10] or False,
                can_helicopter_land=row[11] or False,
                primary_network_type=network_type,
                signal_quality=row[13],
                nearest_supply_depot_m=float(row[14]) if row[14] else None,
                nearest_medical_point_m=float(row[15]) if row[15] else None,
                nearest_command_post_m=float(row[16]) if row[16] else None,
                scenario_id=row[17],
            ))
        return sites
    
    @staticmethod
    def _parse_site_type(value: Optional[str]) -> StagingSiteType:
        if not value:
            return StagingSiteType.OTHER
        try:
            return StagingSiteType(value)
        except ValueError:
            return StagingSiteType.OTHER
    
    @staticmethod
    def _parse_ground_stability(value: Optional[str]) -> GroundStability:
        if not value:
            return GroundStability.UNKNOWN
        try:
            return GroundStability(value)
        except ValueError:
            return GroundStability.UNKNOWN
    
    @staticmethod
    def _parse_network_type(value: Optional[str]) -> NetworkType:
        if not value:
            return NetworkType.NONE
        try:
            return NetworkType(value)
        except ValueError:
            return NetworkType.NONE
