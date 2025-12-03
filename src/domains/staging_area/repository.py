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

    async def find_safe_points(
        self,
        scenario_id: UUID,
        center_lon: float,
        center_lat: float,
        search_radius_m: float = 30000,
        min_buffer_m: float = 500,
        max_slope_deg: float = 15,
        min_area_m2: Optional[float] = None,
        require_water: bool = False,
        require_power: bool = False,
        require_helicopter: bool = False,
        require_ground_stability: Optional[str] = None,
        require_network_type: Optional[str] = None,
        max_distance_to_supply_m: Optional[float] = None,
        max_distance_to_medical_m: Optional[float] = None,
        site_types: Optional[List[str]] = None,
        top_n: int = 5,
    ) -> List[dict]:
        """
        查找安全点位
        
        使用 PostGIS 空间查询，支持多种筛选条件。
        """
        # 构建动态 WHERE 条件
        conditions = [
            "scenario_id = :scenario_id",
            "ST_DWithin(location, ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography, :search_radius_m)",
        ]
        params = {
            "scenario_id": scenario_id,
            "center_lon": center_lon,
            "center_lat": center_lat,
            "search_radius_m": search_radius_m,
            "top_n": top_n,
        }
        
        # 坡度条件
        if max_slope_deg is not None:
            conditions.append("(slope_degree IS NULL OR slope_degree <= :max_slope_deg)")
            params["max_slope_deg"] = max_slope_deg
        
        # 面积条件
        if min_area_m2 is not None:
            conditions.append("(area_m2 IS NULL OR area_m2 >= :min_area_m2)")
            params["min_area_m2"] = min_area_m2
        
        # 设施条件
        if require_water:
            conditions.append("has_water_supply = TRUE")
        if require_power:
            conditions.append("has_power_supply = TRUE")
        if require_helicopter:
            conditions.append("can_helicopter_land = TRUE")
        
        # 地面稳定性条件
        if require_ground_stability:
            stability_levels = {
                "excellent": ["excellent"],
                "good": ["excellent", "good"],
                "moderate": ["excellent", "good", "moderate"],
            }
            allowed = stability_levels.get(require_ground_stability, [])
            if allowed:
                conditions.append("ground_stability = ANY(:stability_levels)")
                params["stability_levels"] = allowed
        
        # 网络类型条件
        if require_network_type:
            conditions.append("primary_network_type = :network_type")
            params["network_type"] = require_network_type
        
        # 距离补给点条件
        if max_distance_to_supply_m is not None:
            conditions.append("(nearest_supply_depot_m IS NULL OR nearest_supply_depot_m <= :max_supply_dist)")
            params["max_supply_dist"] = max_distance_to_supply_m
        
        # 距离医疗点条件
        if max_distance_to_medical_m is not None:
            conditions.append("(nearest_medical_point_m IS NULL OR nearest_medical_point_m <= :max_medical_dist)")
            params["max_medical_dist"] = max_distance_to_medical_m
        
        # 场地类型条件
        if site_types:
            conditions.append("site_type = ANY(:site_types)")
            params["site_types"] = site_types
        
        where_clause = " AND ".join(conditions)
        
        sql = text(f"""
            WITH danger_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id
                AND area_type IN ('danger_zone', 'blocked', 'collapsed', 'fire', 'landslide')
            ),
            candidates AS (
                SELECT 
                    s.id,
                    s.site_code,
                    s.name,
                    s.site_type,
                    ST_X(s.location::geometry) as longitude,
                    ST_Y(s.location::geometry) as latitude,
                    s.area_m2,
                    s.slope_degree,
                    s.ground_stability,
                    s.has_water_supply,
                    s.has_power_supply,
                    s.can_helicopter_land,
                    s.primary_network_type,
                    s.nearest_supply_depot_m,
                    s.nearest_medical_point_m,
                    ST_Distance(
                        s.location,
                        ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography
                    ) as distance_m,
                    COALESCE(
                        (SELECT MIN(ST_Distance(s.location, dz.geometry::geography))
                         FROM danger_zones dz),
                        999999
                    ) as distance_to_danger_m
                FROM operational_v2.rescue_staging_sites_v2 s
                WHERE {where_clause}
            )
            SELECT 
                id, site_code, name, site_type,
                longitude, latitude, area_m2, slope_degree,
                ground_stability, has_water_supply, has_power_supply,
                can_helicopter_land, primary_network_type,
                nearest_supply_depot_m, nearest_medical_point_m,
                distance_m, distance_to_danger_m
            FROM candidates
            WHERE distance_to_danger_m >= :min_buffer_m
            ORDER BY distance_m ASC
            LIMIT :top_n
        """)
        
        params["min_buffer_m"] = min_buffer_m
        
        try:
            result = await self._db.execute(sql, params)
            rows = result.fetchall()
            
            sites = []
            for row in rows:
                # 计算简单评分
                score = self._calculate_safe_point_score(
                    distance_m=row[15],
                    distance_to_danger_m=row[16],
                    has_water=row[9],
                    has_power=row[10],
                    can_helicopter=row[11],
                    area_m2=row[6],
                    slope_degree=row[7],
                )
                
                sites.append({
                    "site_id": row[0],
                    "site_code": row[1],
                    "name": row[2],
                    "site_type": row[3],
                    "longitude": row[4],
                    "latitude": row[5],
                    "area_m2": float(row[6]) if row[6] else None,
                    "slope_degree": float(row[7]) if row[7] else None,
                    "ground_stability": row[8] or "unknown",
                    "has_water_supply": row[9] or False,
                    "has_power_supply": row[10] or False,
                    "can_helicopter_land": row[11] or False,
                    "primary_network_type": row[12] or "none",
                    "nearest_supply_depot_m": float(row[13]) if row[13] else None,
                    "nearest_medical_point_m": float(row[14]) if row[14] else None,
                    "distance_m": float(row[15]),
                    "distance_to_danger_m": float(row[16]) if row[16] else None,
                    "score": score,
                })
            
            logger.info(f"[安全点位搜索] 找到 {len(sites)} 个符合条件的点位")
            return sites
            
        except Exception as e:
            logger.error(f"[安全点位搜索] 数据库查询失败: {e}")
            raise

    @staticmethod
    def _calculate_safe_point_score(
        distance_m: float,
        distance_to_danger_m: float,
        has_water: bool,
        has_power: bool,
        can_helicopter: bool,
        area_m2: Optional[float],
        slope_degree: Optional[float],
    ) -> float:
        """计算安全点位评分"""
        score = 0.0
        
        # 距离评分 (越近越好，30km内)
        if distance_m <= 30000:
            score += 0.3 * (1 - distance_m / 30000)
        
        # 安全距离评分 (距危险区越远越好)
        if distance_to_danger_m:
            safety_score = min(distance_to_danger_m / 5000, 1.0)
            score += 0.3 * safety_score
        else:
            score += 0.3
        
        # 设施评分
        facility_score = 0.0
        if has_water:
            facility_score += 0.4
        if has_power:
            facility_score += 0.3
        if can_helicopter:
            facility_score += 0.3
        score += 0.2 * facility_score
        
        # 面积评分
        if area_m2 and area_m2 >= 2000:
            area_score = min(area_m2 / 10000, 1.0)
            score += 0.1 * area_score
        
        # 坡度评分 (越平越好)
        if slope_degree is not None:
            slope_score = max(0, 1 - slope_degree / 15)
            score += 0.1 * slope_score
        else:
            score += 0.05
        
        return round(min(score, 1.0), 3)
