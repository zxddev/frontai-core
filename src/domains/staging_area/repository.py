"""
救援队驻扎点数据访问层

提供驻扎点候选搜索、安全点位查找等功能。
基于 PostGIS 空间查询，支持多维度评分和分类安全距离过滤。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.staging_area.constants import (
    HAZARD_SAFE_DISTANCES,
    HAZARD_TYPE_NAMES,
    EVALUATION_WEIGHTS,
    TERRAIN_WEIGHTS,
    ACCESSIBILITY_WEIGHTS,
    FACILITY_WEIGHTS,
    HAZARD_RISK_WEIGHTS,
    SLOPE_THRESHOLDS,
    GROUND_STABILITY_SCORES,
    NETWORK_TYPE_SCORES,
    SIGNAL_QUALITY_MULTIPLIERS,
    AREA_THRESHOLDS,
    DISTANCE_REFERENCE_VALUES,
    RISK_WARNING_THRESHOLDS,
    SLOPE_WARNING_THRESHOLDS,
)
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
        enable_poi_collection: bool = True,
        min_candidates_for_poi: int = 10,
    ) -> List[dict]:
        """
        查找安全点位（增强版）

        使用 PostGIS 空间查询，支持:
        - 分类灾害区域查询（滑坡、泥石流、洪水、火灾、堰塞湖等）
        - 分类安全距离过滤（不同灾害类型使用不同安全距离）
        - 多维度评分（灾害风险、地形安全、可达性、设施条件、通信质量）
        - 风险提示生成
        - POI动态采集（当数据库候选点不足时自动从高德API采集）

        Args:
            scenario_id: 想定ID
            center_lon: 搜索中心经度
            center_lat: 搜索中心纬度
            search_radius_m: 搜索半径(m)
            min_buffer_m: 距危险区最小缓冲距离(m)，作为默认安全距离
            max_slope_deg: 最大坡度(度)
            min_area_m2: 最小面积要求(m²)
            require_water: 是否要求水源
            require_power: 是否要求电源
            require_helicopter: 是否要求直升机起降
            require_ground_stability: 地面稳定性要求
            require_network_type: 通信网络类型要求
            max_distance_to_supply_m: 距补给点最大距离(m)
            max_distance_to_medical_m: 距医疗点最大距离(m)
            site_types: 限定场地类型列表
            top_n: 返回前N个结果
            enable_poi_collection: 是否启用POI动态采集（默认启用）
            min_candidates_for_poi: 触发POI采集的最小候选点数量阈值

        Returns:
            安全点位列表，包含评分详情和风险提示
        """
        logger.info(
            f"[安全点位搜索] 开始查询: scenario={scenario_id}, "
            f"center=({center_lon:.6f}, {center_lat:.6f}), "
            f"radius={search_radius_m}m, min_buffer={min_buffer_m}m, "
            f"max_slope={max_slope_deg}°, top_n={top_n}, "
            f"enable_poi_collection={enable_poi_collection}"
        )

        # 如果启用POI采集，先检查并补充数据
        if enable_poi_collection:
            await self._ensure_poi_data(
                center_lon=center_lon,
                center_lat=center_lat,
                search_radius_m=search_radius_m,
                scenario_id=scenario_id,
                min_candidates=min_candidates_for_poi,
            )

        # 构建动态 WHERE 条件
        conditions = [
            "(scenario_id = :scenario_id OR scenario_id IS NULL)",
            "ST_DWithin(location, ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography, :search_radius_m)",
        ]
        params: Dict[str, any] = {
            "scenario_id": scenario_id,
            "center_lon": center_lon,
            "center_lat": center_lat,
            "search_radius_m": search_radius_m,
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

        # 获取各类灾害的安全距离阈值
        # 地震烈度区域（依据GB 51143-2015和活动断层避让标准）
        seismic_red_safe_dist = HAZARD_SAFE_DISTANCES.get("seismic_red", 5000)
        seismic_orange_safe_dist = HAZARD_SAFE_DISTANCES.get("seismic_orange", 3000)
        seismic_yellow_safe_dist = HAZARD_SAFE_DISTANCES.get("seismic_yellow", 1000)
        # 次生灾害
        landslide_safe_dist = HAZARD_SAFE_DISTANCES.get("landslide", 1000)
        debris_flow_safe_dist = HAZARD_SAFE_DISTANCES.get("debris_flow", 500)
        flooded_safe_dist = HAZARD_SAFE_DISTANCES.get("flooded", 800)
        fire_safe_dist = HAZARD_SAFE_DISTANCES.get("fire", 500)
        dammed_lake_safe_dist = HAZARD_SAFE_DISTANCES.get("dammed_lake", 3000)
        other_danger_safe_dist = max(min_buffer_m, HAZARD_SAFE_DISTANCES.get("default", 500))

        logger.info(
            f"[安全点位搜索] 安全距离配置: "
            f"地震红区={seismic_red_safe_dist}m, 地震橙区={seismic_orange_safe_dist}m, "
            f"地震黄区={seismic_yellow_safe_dist}m, 滑坡={landslide_safe_dist}m, "
            f"泥石流={debris_flow_safe_dist}m, 洪水={flooded_safe_dist}m, "
            f"火灾={fire_safe_dist}m, 堰塞湖={dammed_lake_safe_dist}m, "
            f"其他危险区={other_danger_safe_dist}m"
        )

        # 分类查询各类灾害区域并计算距离
        sql = text(f"""
            WITH
            -- 地震烈度区域（最重要的安全过滤条件）
            seismic_red_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'seismic_red'
            ),
            seismic_orange_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'seismic_orange'
            ),
            seismic_yellow_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'seismic_yellow'
            ),
            -- 次生灾害区域
            landslide_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'landslide'
            ),
            debris_flow_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'debris_flow'
            ),
            flooded_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'flooded'
            ),
            fire_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'fire'
            ),
            dammed_lake_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id AND area_type = 'dammed_lake'
            ),
            other_danger_zones AS (
                SELECT geometry
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = :scenario_id
                AND area_type IN ('danger_zone', 'blocked', 'collapsed', 'contaminated', 'liquefaction')
            ),

            -- 计算候选点到各类灾害区的距离
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
                    s.signal_quality,
                    s.nearest_road_distance_m,
                    s.nearest_supply_depot_m,
                    s.nearest_medical_point_m,
                    s.elevation_m,
                    ST_Distance(
                        s.location,
                        ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography
                    ) as distance_to_center_m,

                    -- 地震烈度区域距离（最重要）
                    (SELECT MIN(ST_Distance(s.location, sr.geometry::geography)) FROM seismic_red_zones sr) as dist_to_seismic_red_m,
                    (SELECT MIN(ST_Distance(s.location, so.geometry::geography)) FROM seismic_orange_zones so) as dist_to_seismic_orange_m,
                    (SELECT MIN(ST_Distance(s.location, sy.geometry::geography)) FROM seismic_yellow_zones sy) as dist_to_seismic_yellow_m,
                    -- 次生灾害距离
                    (SELECT MIN(ST_Distance(s.location, lz.geometry::geography)) FROM landslide_zones lz) as dist_to_landslide_m,
                    (SELECT MIN(ST_Distance(s.location, df.geometry::geography)) FROM debris_flow_zones df) as dist_to_debris_flow_m,
                    (SELECT MIN(ST_Distance(s.location, fz.geometry::geography)) FROM flooded_zones fz) as dist_to_flooded_m,
                    (SELECT MIN(ST_Distance(s.location, fi.geometry::geography)) FROM fire_zones fi) as dist_to_fire_m,
                    (SELECT MIN(ST_Distance(s.location, dl.geometry::geography)) FROM dammed_lake_zones dl) as dist_to_dammed_lake_m,
                    (SELECT MIN(ST_Distance(s.location, od.geometry::geography)) FROM other_danger_zones od) as dist_to_other_danger_m

                FROM operational_v2.rescue_staging_sites_v2 s
                WHERE {where_clause}
            ),

            -- 检查各类灾害区域是否存在
            seismic_red_exists AS (SELECT EXISTS(SELECT 1 FROM seismic_red_zones) as exists),
            seismic_orange_exists AS (SELECT EXISTS(SELECT 1 FROM seismic_orange_zones) as exists),
            seismic_yellow_exists AS (SELECT EXISTS(SELECT 1 FROM seismic_yellow_zones) as exists),
            landslide_exists AS (SELECT EXISTS(SELECT 1 FROM landslide_zones) as exists),
            debris_flow_exists AS (SELECT EXISTS(SELECT 1 FROM debris_flow_zones) as exists),
            flooded_exists AS (SELECT EXISTS(SELECT 1 FROM flooded_zones) as exists),
            fire_exists AS (SELECT EXISTS(SELECT 1 FROM fire_zones) as exists),
            dammed_lake_exists AS (SELECT EXISTS(SELECT 1 FROM dammed_lake_zones) as exists),
            other_danger_exists AS (SELECT EXISTS(SELECT 1 FROM other_danger_zones) as exists)

            SELECT
                id, site_code, name, site_type,
                longitude, latitude, area_m2, slope_degree,
                ground_stability, has_water_supply, has_power_supply,
                can_helicopter_land, primary_network_type, signal_quality,
                nearest_road_distance_m, nearest_supply_depot_m, nearest_medical_point_m,
                elevation_m, distance_to_center_m,
                dist_to_seismic_red_m, dist_to_seismic_orange_m, dist_to_seismic_yellow_m,
                dist_to_landslide_m, dist_to_debris_flow_m, dist_to_flooded_m,
                dist_to_fire_m, dist_to_dammed_lake_m, dist_to_other_danger_m
            FROM candidates
            WHERE
                -- 地震烈度区域安全距离过滤（最重要，必须远离震中）
                -- 逻辑：如果该类型灾害区域存在，则必须满足安全距离；如果不存在，则通过
                ((SELECT exists FROM seismic_red_exists) = FALSE OR dist_to_seismic_red_m >= :seismic_red_safe_dist)
                AND ((SELECT exists FROM seismic_orange_exists) = FALSE OR dist_to_seismic_orange_m >= :seismic_orange_safe_dist)
                AND ((SELECT exists FROM seismic_yellow_exists) = FALSE OR dist_to_seismic_yellow_m >= :seismic_yellow_safe_dist)
                -- 次生灾害安全距离过滤
                AND ((SELECT exists FROM landslide_exists) = FALSE OR dist_to_landslide_m >= :landslide_safe_dist)
                AND ((SELECT exists FROM debris_flow_exists) = FALSE OR dist_to_debris_flow_m >= :debris_flow_safe_dist)
                AND ((SELECT exists FROM flooded_exists) = FALSE OR dist_to_flooded_m >= :flooded_safe_dist)
                AND ((SELECT exists FROM fire_exists) = FALSE OR dist_to_fire_m >= :fire_safe_dist)
                AND ((SELECT exists FROM dammed_lake_exists) = FALSE OR dist_to_dammed_lake_m >= :dammed_lake_safe_dist)
                AND ((SELECT exists FROM other_danger_exists) = FALSE OR dist_to_other_danger_m >= :other_danger_safe_dist)
            LIMIT :limit
        """)

        params["seismic_red_safe_dist"] = seismic_red_safe_dist
        params["seismic_orange_safe_dist"] = seismic_orange_safe_dist
        params["seismic_yellow_safe_dist"] = seismic_yellow_safe_dist
        params["landslide_safe_dist"] = landslide_safe_dist
        params["debris_flow_safe_dist"] = debris_flow_safe_dist
        params["flooded_safe_dist"] = flooded_safe_dist
        params["fire_safe_dist"] = fire_safe_dist
        params["dammed_lake_safe_dist"] = dammed_lake_safe_dist
        params["other_danger_safe_dist"] = other_danger_safe_dist
        params["limit"] = top_n * 3  # 多取一些用于评分后筛选

        # 详细日志：SQL查询参数
        logger.info(
            f"[安全点位搜索] SQL查询参数: scenario_id={scenario_id}, "
            f"center=({center_lon:.6f}, {center_lat:.6f}), "
            f"search_radius={search_radius_m}m, limit={params['limit']}"
        )
        logger.debug(
            f"[安全点位搜索] 安全距离参数: "
            f"seismic_red={seismic_red_safe_dist}m, seismic_orange={seismic_orange_safe_dist}m, "
            f"seismic_yellow={seismic_yellow_safe_dist}m, landslide={landslide_safe_dist}m, "
            f"debris_flow={debris_flow_safe_dist}m, flooded={flooded_safe_dist}m, "
            f"fire={fire_safe_dist}m, dammed_lake={dammed_lake_safe_dist}m"
        )

        try:
            result = await self._db.execute(sql, params)
            rows = result.fetchall()

            logger.info(f"[安全点位搜索] 初步筛选结果: {len(rows)} 个候选点通过安全距离过滤")

            sites = []
            for row in rows:
                # 提取各类灾害距离（列顺序：19-21为地震烈度区域，22-27为次生灾害）
                hazard_distances: Dict[str, Optional[float]] = {
                    # 地震烈度区域（最重要）
                    "seismic_red": float(row[19]) if row[19] is not None else None,
                    "seismic_orange": float(row[20]) if row[20] is not None else None,
                    "seismic_yellow": float(row[21]) if row[21] is not None else None,
                    # 次生灾害
                    "landslide": float(row[22]) if row[22] is not None else None,
                    "debris_flow": float(row[23]) if row[23] is not None else None,
                    "flooded": float(row[24]) if row[24] is not None else None,
                    "fire": float(row[25]) if row[25] is not None else None,
                    "dammed_lake": float(row[26]) if row[26] is not None else None,
                    "other_danger": float(row[27]) if row[27] is not None else None,
                }

                # 计算多维度评分
                total_score, score_breakdown, risk_warnings = self._calculate_safe_point_score_v2(
                    distance_to_center_m=float(row[18]) if row[18] else 0,
                    distances_to_hazards=hazard_distances,
                    slope_degree=float(row[7]) if row[7] else None,
                    ground_stability=row[8],
                    elevation_m=float(row[17]) if row[17] else None,
                    nearest_road_distance_m=float(row[14]) if row[14] else None,
                    nearest_supply_depot_m=float(row[15]) if row[15] else None,
                    nearest_medical_point_m=float(row[16]) if row[16] else None,
                    has_water=row[9] or False,
                    has_power=row[10] or False,
                    can_helicopter=row[11] or False,
                    area_m2=float(row[6]) if row[6] else None,
                    network_type=row[12],
                    signal_quality=row[13],
                )

                site_code = row[1]
                logger.debug(
                    f"[安全点位搜索] 评分计算: site={site_code}, "
                    f"灾害风险={score_breakdown.get('hazard_risk', 0):.3f}, "
                    f"地形安全={score_breakdown.get('terrain', 0):.3f}, "
                    f"可达性={score_breakdown.get('accessibility', 0):.3f}, "
                    f"设施条件={score_breakdown.get('facility', 0):.3f}, "
                    f"通信质量={score_breakdown.get('communication', 0):.3f}, "
                    f"总分={total_score:.3f}"
                )

                if risk_warnings:
                    logger.warning(f"[安全点位搜索] 风险提示: site={site_code}, warnings={risk_warnings}")

                # 计算综合危险区距离（取最小值，用于兼容旧接口）
                min_danger_dist = None
                for dist in hazard_distances.values():
                    if dist is not None:
                        if min_danger_dist is None or dist < min_danger_dist:
                            min_danger_dist = dist

                sites.append({
                    "site_id": row[0],
                    "site_code": site_code,
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
                    "nearest_supply_depot_m": float(row[15]) if row[15] else None,
                    "nearest_medical_point_m": float(row[16]) if row[16] else None,
                    "distance_m": float(row[18]),
                    "distance_to_danger_m": min_danger_dist,
                    "score": total_score,
                    # 新增字段
                    "score_breakdown": score_breakdown,
                    "risk_warnings": risk_warnings,
                    "hazard_distances": hazard_distances,
                })

            # 按总分排序并取前 top_n 个
            sites.sort(key=lambda x: x["score"], reverse=True)
            sites = sites[:top_n]

            logger.info(
                f"[安全点位搜索] 完成: 返回 {len(sites)} 个点位"
                + (f", 最高分={sites[0]['score']:.3f}, 最低分={sites[-1]['score']:.3f}" if sites else "")
            )

            return sites

        except Exception as e:
            logger.error(f"[安全点位搜索] 数据库查询失败: {e}", exc_info=True)
            raise

    def _calculate_safe_point_score_v2(
        self,
        distance_to_center_m: float,
        distances_to_hazards: Dict[str, Optional[float]],
        slope_degree: Optional[float],
        ground_stability: Optional[str],
        elevation_m: Optional[float],
        nearest_road_distance_m: Optional[float],
        nearest_supply_depot_m: Optional[float],
        nearest_medical_point_m: Optional[float],
        has_water: bool,
        has_power: bool,
        can_helicopter: bool,
        area_m2: Optional[float],
        network_type: Optional[str],
        signal_quality: Optional[str],
    ) -> Tuple[float, Dict[str, float], List[str]]:
        """
        多维度安全点位评分算法（增强版）

        基于 GIS-AHP-TOPSIS 多准则决策方法，综合评估5个维度:
        1. 灾害风险 (35%) - 距各类灾害区的安全距离
        2. 地形安全 (25%) - 坡度、地面稳定性、高程
        3. 可达性 (20%) - 距道路、医疗点、补给点距离
        4. 设施条件 (15%) - 水电、直升机、面积
        5. 通信质量 (5%) - 网络类型、信号质量

        Args:
            distance_to_center_m: 距搜索中心距离(m)
            distances_to_hazards: 到各类灾害区的距离字典
            slope_degree: 坡度(度)
            ground_stability: 地面稳定性
            elevation_m: 高程(m)
            nearest_road_distance_m: 距最近道路距离(m)
            nearest_supply_depot_m: 距最近补给点距离(m)
            nearest_medical_point_m: 距最近医疗点距离(m)
            has_water: 是否有水源
            has_power: 是否有电源
            can_helicopter: 是否可直升机起降
            area_m2: 面积(m²)
            network_type: 网络类型
            signal_quality: 信号质量

        Returns:
            (总评分, 各维度评分详情, 风险提示列表)
        """
        risk_warnings: List[str] = []
        score_breakdown: Dict[str, float] = {}

        # 1. 灾害风险评分 (35%)
        hazard_score, hazard_warnings = self._calc_hazard_risk_score(distances_to_hazards)
        score_breakdown["hazard_risk"] = round(hazard_score, 3)
        risk_warnings.extend(hazard_warnings)

        # 2. 地形安全评分 (25%)
        terrain_score, terrain_warnings = self._calc_terrain_score(
            slope_degree, ground_stability, elevation_m
        )
        score_breakdown["terrain"] = round(terrain_score, 3)
        risk_warnings.extend(terrain_warnings)

        # 3. 可达性评分 (20%)
        accessibility_score = self._calc_accessibility_score(
            distance_to_center_m,
            nearest_road_distance_m,
            nearest_supply_depot_m,
            nearest_medical_point_m,
        )
        score_breakdown["accessibility"] = round(accessibility_score, 3)

        # 4. 设施条件评分 (15%)
        facility_score = self._calc_facility_score(
            has_water, has_power, can_helicopter, area_m2
        )
        score_breakdown["facility"] = round(facility_score, 3)

        # 5. 通信质量评分 (5%)
        communication_score = self._calc_communication_score(network_type, signal_quality)
        score_breakdown["communication"] = round(communication_score, 3)

        # 加权计算总分
        total_score = (
            EVALUATION_WEIGHTS["hazard_risk"] * hazard_score +
            EVALUATION_WEIGHTS["terrain"] * terrain_score +
            EVALUATION_WEIGHTS["accessibility"] * accessibility_score +
            EVALUATION_WEIGHTS["facility"] * facility_score +
            EVALUATION_WEIGHTS["communication"] * communication_score
        )

        return round(min(total_score, 1.0), 3), score_breakdown, risk_warnings

    def _calc_hazard_risk_score(
        self,
        distances_to_hazards: Dict[str, Optional[float]],
    ) -> Tuple[float, List[str]]:
        """
        计算灾害风险评分

        逻辑：
        - 对每种灾害类型，计算 min(距离 / (安全距离 * 2), 1.0)
        - 使用加权平均，高风险灾害权重更高
        - 生成风险提示

        Args:
            distances_to_hazards: 到各类灾害区的距离字典

        Returns:
            (风险评分, 风险提示列表)
        """
        warnings: List[str] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for hazard_type, distance in distances_to_hazards.items():
            if distance is None:
                continue

            # 获取安全距离和权重
            safe_dist = HAZARD_SAFE_DISTANCES.get(hazard_type, HAZARD_SAFE_DISTANCES["default"])
            weight = HAZARD_RISK_WEIGHTS.get(hazard_type, 0.5)

            # 计算该灾害类型的评分（2倍安全距离得满分）
            score = min(distance / (safe_dist * 2), 1.0)

            weighted_sum += score * weight
            weight_total += weight

            # 生成风险提示
            hazard_name = HAZARD_TYPE_NAMES.get(hazard_type, hazard_type)
            if distance < safe_dist:
                # 低于安全距离 - 严重警告
                warnings.append(f"⚠️ 距{hazard_name}仅{int(distance)}m，低于安全距离{safe_dist}m")
            elif distance < safe_dist * RISK_WARNING_THRESHOLDS["warning"]:
                # 1-1.5倍安全距离 - 警告
                warnings.append(f"⚡ 距{hazard_name}{int(distance)}m，接近安全边界")
            elif distance < safe_dist * RISK_WARNING_THRESHOLDS["caution"]:
                # 1.5-2倍安全距离 - 注意（仅对高风险灾害）
                if weight >= 0.8:
                    warnings.append(f"📍 距{hazard_name}{int(distance)}m，建议保持警惕")

        # 计算加权平均分
        if weight_total > 0:
            final_score = weighted_sum / weight_total
        else:
            # 没有任何灾害区域数据，采用保守策略（未知=高风险）
            # 依据安全原则：无法评估的区域应视为高风险
            final_score = 0.1
            warnings.append("⚠️ 缺少灾害区域数据，无法评估安全距离，建议现场勘察确认")
            logger.warning("[灾害风险评分] 没有灾害区域数据，采用保守评分0.1（高风险）")

        return final_score, warnings

    def _calc_terrain_score(
        self,
        slope_degree: Optional[float],
        ground_stability: Optional[str],
        elevation_m: Optional[float],
    ) -> Tuple[float, List[str]]:
        """
        计算地形安全评分

        子维度:
        - 坡度评分 (40%): ≤5°满分，>25°零分
        - 地面稳定性评分 (40%): excellent=1.0, good=0.8, moderate=0.5, poor=0.2
        - 高程评分 (20%): 避免过低（洪水）或过高（交通不便）

        Args:
            slope_degree: 坡度(度)
            ground_stability: 地面稳定性
            elevation_m: 高程(m)

        Returns:
            (地形评分, 风险提示列表)
        """
        warnings: List[str] = []

        # 坡度评分
        if slope_degree is not None:
            if slope_degree <= SLOPE_THRESHOLDS["excellent"]:
                slope_score = 1.0
            elif slope_degree <= SLOPE_THRESHOLDS["good"]:
                slope_score = 0.8
            elif slope_degree <= SLOPE_THRESHOLDS["acceptable"]:
                slope_score = 0.6
            elif slope_degree <= SLOPE_THRESHOLDS["poor"]:
                slope_score = 0.3
            else:
                slope_score = 0.0

            # 坡度风险提示
            if slope_degree > SLOPE_WARNING_THRESHOLDS["warning"]:
                warnings.append(f"📐 坡度{slope_degree:.1f}°，较陡峭")
            elif slope_degree > SLOPE_WARNING_THRESHOLDS["caution"]:
                warnings.append(f"📐 坡度{slope_degree:.1f}°，略高于理想值")
        else:
            slope_score = 0.5  # 未知坡度给予中等分数

        # 地面稳定性评分
        stability_score = GROUND_STABILITY_SCORES.get(
            ground_stability or "unknown",
            GROUND_STABILITY_SCORES["unknown"]
        )

        if ground_stability == "poor":
            warnings.append("🏗️ 地面稳定性较差")
        elif ground_stability == "moderate":
            warnings.append("🏗️ 地面稳定性一般")

        # 高程评分（简化处理，主要考虑是否过低）
        if elevation_m is not None:
            if elevation_m < 50:
                # 低海拔可能有洪水风险
                elevation_score = 0.6
                warnings.append(f"🌊 海拔较低({int(elevation_m)}m)，注意洪水风险")
            elif elevation_m > 3000:
                # 高海拔交通不便
                elevation_score = 0.7
            else:
                elevation_score = 1.0
        else:
            elevation_score = 0.7  # 未知高程给予中等偏上分数

        # 加权计算
        total_score = (
            TERRAIN_WEIGHTS["slope"] * slope_score +
            TERRAIN_WEIGHTS["ground_stability"] * stability_score +
            TERRAIN_WEIGHTS["elevation"] * elevation_score
        )

        return total_score, warnings

    def _calc_accessibility_score(
        self,
        distance_to_center_m: float,
        nearest_road_distance_m: Optional[float],
        nearest_supply_depot_m: Optional[float],
        nearest_medical_point_m: Optional[float],
    ) -> float:
        """
        计算可达性评分

        子维度:
        - 距搜索中心距离 (30%): 5-30km内满分，超过30km线性衰减
          注意：地震场景下，搜索中心通常是震中，不应奖励靠近震中的点位
        - 距道路距离 (30%): 500m内满分
        - 距补给点距离 (20%): 10km内线性衰减
        - 距医疗点距离 (20%): 5km内线性衰减

        Args:
            distance_to_center_m: 距搜索中心距离(m)
            nearest_road_distance_m: 距最近道路距离(m)
            nearest_supply_depot_m: 距最近补给点距离(m)
            nearest_medical_point_m: 距最近医疗点距离(m)

        Returns:
            可达性评分
        """
        # 距搜索中心评分
        # 地震场景下，搜索中心通常是震中，不应奖励靠近震中的点位
        # 5km以内的点位已被SQL WHERE子句过滤，这里只评估可达性
        # 5-30km内给予满分（既安全又可达），超过30km开始衰减
        ref_radius = DISTANCE_REFERENCE_VALUES["search_radius"]  # 30km
        min_safe_distance = 5000  # 5km，与seismic_red安全距离一致
        if distance_to_center_m <= min_safe_distance:
            # 太近震中的点位，可达性评分为0（危险）
            # 理论上已被SQL过滤，但作为双重保险
            center_score = 0.0
        elif distance_to_center_m <= ref_radius:
            # 5-30km内，满分
            center_score = 1.0
        else:
            # 超过30km，线性衰减到50km时为0
            max_distance = 50000  # 50km
            center_score = max(0, 1 - (distance_to_center_m - ref_radius) / (max_distance - ref_radius))

        # 距道路评分
        if nearest_road_distance_m is not None:
            ref_road = DISTANCE_REFERENCE_VALUES["nearest_road"]
            road_score = max(0, 1 - nearest_road_distance_m / (ref_road * 4))  # 2km内衰减
        else:
            road_score = 0.5  # 未知距离给予中等分数

        # 距补给点评分
        if nearest_supply_depot_m is not None:
            ref_supply = DISTANCE_REFERENCE_VALUES["nearest_supply"]
            supply_score = max(0, 1 - nearest_supply_depot_m / ref_supply)
        else:
            supply_score = 0.5

        # 距医疗点评分
        if nearest_medical_point_m is not None:
            ref_medical = DISTANCE_REFERENCE_VALUES["nearest_medical"]
            medical_score = max(0, 1 - nearest_medical_point_m / ref_medical)
        else:
            medical_score = 0.5

        # 加权计算
        total_score = (
            ACCESSIBILITY_WEIGHTS["distance_to_center"] * center_score +
            ACCESSIBILITY_WEIGHTS["nearest_road"] * road_score +
            ACCESSIBILITY_WEIGHTS["nearest_supply"] * supply_score +
            ACCESSIBILITY_WEIGHTS["nearest_medical"] * medical_score
        )

        return total_score

    def _calc_facility_score(
        self,
        has_water: bool,
        has_power: bool,
        can_helicopter: bool,
        area_m2: Optional[float],
    ) -> float:
        """
        计算设施条件评分

        子维度:
        - 水源 (30%): 有=1.0, 无=0.0
        - 电源 (25%): 有=1.0, 无=0.0
        - 直升机起降 (20%): 有=1.0, 无=0.0
        - 面积 (25%): ≥5000m²满分，≥2000m²=0.6，<2000m²=0.3

        Args:
            has_water: 是否有水源
            has_power: 是否有电源
            can_helicopter: 是否可直升机起降
            area_m2: 面积(m²)

        Returns:
            设施条件评分
        """
        water_score = 1.0 if has_water else 0.0
        power_score = 1.0 if has_power else 0.0
        helicopter_score = 1.0 if can_helicopter else 0.0

        # 面积评分
        if area_m2 is not None:
            if area_m2 >= AREA_THRESHOLDS["excellent"]:
                area_score = 1.0
            elif area_m2 >= AREA_THRESHOLDS["good"]:
                area_score = 0.8
            elif area_m2 >= AREA_THRESHOLDS["acceptable"]:
                area_score = 0.6
            elif area_m2 >= AREA_THRESHOLDS["minimum"]:
                area_score = 0.4
            else:
                area_score = 0.2
        else:
            area_score = 0.5  # 未知面积给予中等分数

        # 加权计算
        total_score = (
            FACILITY_WEIGHTS["water_supply"] * water_score +
            FACILITY_WEIGHTS["power_supply"] * power_score +
            FACILITY_WEIGHTS["helicopter"] * helicopter_score +
            FACILITY_WEIGHTS["area"] * area_score
        )

        return total_score

    def _calc_communication_score(
        self,
        network_type: Optional[str],
        signal_quality: Optional[str],
    ) -> float:
        """
        计算通信质量评分

        网络类型基础分:
        - 5g: 1.0, 4g_lte: 0.85, satellite: 0.7
        - 3g: 0.5, mesh: 0.6, shortwave: 0.4, none: 0.0

        信号质量修正:
        - excellent: ×1.0, good: ×0.9, fair: ×0.7, poor: ×0.4

        Args:
            network_type: 网络类型
            signal_quality: 信号质量

        Returns:
            通信质量评分
        """
        # 网络类型基础分
        base_score = NETWORK_TYPE_SCORES.get(
            network_type or "none",
            NETWORK_TYPE_SCORES["none"]
        )

        # 信号质量修正
        quality_multiplier = SIGNAL_QUALITY_MULTIPLIERS.get(
            signal_quality or "unknown",
            SIGNAL_QUALITY_MULTIPLIERS["unknown"]
        )

        return base_score * quality_multiplier

    # 保留旧的评分方法用于兼容
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
        """
        计算安全点位评分（旧版本，保留用于兼容）

        已废弃，请使用 _calculate_safe_point_score_v2
        """
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

    async def _ensure_poi_data(
        self,
        center_lon: float,
        center_lat: float,
        search_radius_m: float,
        scenario_id: Optional[UUID] = None,
        min_candidates: int = 10,
    ) -> None:
        """
        确保有足够的POI数据

        当数据库中候选点数量不足时，自动从高德API采集POI数据。

        Args:
            center_lon: 搜索中心经度
            center_lat: 搜索中心纬度
            search_radius_m: 搜索半径(m)
            scenario_id: 想定ID（可选）
            min_candidates: 最小候选点数量阈值
        """
        logger.debug(
            f"[安全点位搜索] _ensure_poi_data 入口: "
            f"center=({center_lon}, {center_lat}), radius={search_radius_m}m, "
            f"scenario_id={scenario_id}, min_candidates={min_candidates}"
        )

        try:
            from src.domains.staging_area.poi_service import POICollectionService

            service = POICollectionService(self._db)

            # collect_and_merge 内部会检查数据库数量，不足时才采集
            logger.debug("[安全点位搜索] 调用 POICollectionService.collect_and_merge()")
            _, new_count = await service.collect_and_merge(
                center_lon=center_lon,
                center_lat=center_lat,
                search_radius_m=search_radius_m,
                scenario_id=scenario_id,
                min_candidates=min_candidates,
                save_to_db=True,
            )

            if new_count > 0:
                logger.info(f"[安全点位搜索] POI采集完成: 新增 {new_count} 个候选点")
            else:
                logger.debug("[安全点位搜索] POI采集: 数据库数据充足，无需采集")

        except Exception as e:
            # POI采集失败不影响主流程，只记录警告
            logger.warning(f"[安全点位搜索] POI采集失败（不影响查询）: {e}", exc_info=True)
