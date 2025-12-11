"""
POI数据采集服务

提供动态POI采集、坐标转换、数据入库等功能。
集成到StagingAreaAgent和find_safe_points接口中使用。

功能：
1. 从高德API动态采集POI
2. 坐标转换（GCJ02 → WGS84）
3. 与数据库已有数据合并去重
4. 自动保存新采集的POI到数据库
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.coord_transform import gcj02_to_wgs84
from src.infra.clients.amap.poi_search import (
    search_poi_around,
    STAGING_POI_TYPES,
    EXCLUDED_POI_TYPES,
    get_site_type_from_poi_code,
    POIResult,
)

logger = logging.getLogger(__name__)


@dataclass
class POICandidate:
    """POI候选点数据"""
    id: UUID
    site_code: str
    name: str
    site_type: str
    longitude: float      # WGS84
    latitude: float       # WGS84
    address: Optional[str]
    area_m2: Optional[float]
    elevation_m: Optional[float]
    slope_degree: Optional[float]
    ground_stability: str
    has_water_supply: bool
    has_power_supply: bool
    can_helicopter_land: bool
    primary_network_type: str
    signal_quality: str
    source: str           # 数据来源: amap_poi
    poi_id: Optional[str]  # 高德POI ID，用于去重


def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    计算两点间的距离（米）

    使用Haversine公式
    """
    R = 6371000  # 地球半径（米）
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))


class POICollectionService:
    """
    POI数据采集服务

    提供动态POI采集、与数据库数据合并、自动入库等功能。
    """

    # 最小候选点数量阈值，低于此值时触发POI采集
    MIN_CANDIDATES_THRESHOLD = 10

    # 去重距离阈值（米）
    DEDUP_DISTANCE_M = 100

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def collect_and_merge(
        self,
        center_lon: float,
        center_lat: float,
        search_radius_m: float,
        scenario_id: Optional[UUID] = None,
        min_candidates: int = 10,
        save_to_db: bool = True,
    ) -> Tuple[List[Dict], int]:
        """
        采集POI并与数据库数据合并

        流程:
        1. 查询数据库中已有的候选点
        2. 如果数量不足，调用高德API动态采集
        3. 合并去重
        4. 可选：将新采集的POI保存到数据库

        Args:
            center_lon: 搜索中心经度（WGS84）
            center_lat: 搜索中心纬度（WGS84）
            search_radius_m: 搜索半径（米）
            scenario_id: 想定ID（可选）
            min_candidates: 最小候选点数量，低于此值时触发POI采集
            save_to_db: 是否将新采集的POI保存到数据库

        Returns:
            (合并后的候选点列表, 新采集的POI数量)
        """
        logger.debug(
            f"[POI采集] collect_and_merge 入口: "
            f"center=({center_lon}, {center_lat}), radius={search_radius_m}m, "
            f"scenario_id={scenario_id}, min_candidates={min_candidates}, save_to_db={save_to_db}"
        )

        # 1. 查询数据库中已有的候选点数量
        db_count = await self._count_db_candidates(
            center_lon=center_lon,
            center_lat=center_lat,
            search_radius_m=search_radius_m,
        )

        logger.info(
            f"[POI采集] 数据库已有 {db_count} 个候选点, "
            f"阈值={min_candidates}, 搜索半径={search_radius_m}m"
        )

        # 2. 如果数据库数据充足，直接返回
        if db_count >= min_candidates:
            logger.info("[POI采集] 数据库数据充足，跳过POI采集")
            logger.debug(f"[POI采集] collect_and_merge 出口: 返回空列表, new_count=0")
            return [], 0

        logger.debug(f"[POI采集] 数据库数据不足({db_count} < {min_candidates})，开始调用高德API")

        # 3. 调用高德API采集POI
        poi_candidates = await self.collect_from_amap(
            center_lon=center_lon,
            center_lat=center_lat,
            search_radius_m=search_radius_m,
        )

        logger.debug(f"[POI采集] 高德API返回 {len(poi_candidates)} 个POI")

        if not poi_candidates:
            logger.warning("[POI采集] 未采集到任何POI")
            logger.debug(f"[POI采集] collect_and_merge 出口: 返回空列表, new_count=0")
            return [], 0

        # 4. 与数据库已有数据去重
        logger.debug(f"[POI采集] 开始去重，待去重数量: {len(poi_candidates)}")
        new_candidates = await self._deduplicate_with_db(
            poi_candidates,
            center_lon=center_lon,
            center_lat=center_lat,
            search_radius_m=search_radius_m,
        )

        logger.info(
            f"[POI采集] 采集 {len(poi_candidates)} 个POI, "
            f"去重后新增 {len(new_candidates)} 个"
        )

        # 5. 保存到数据库
        if save_to_db and new_candidates:
            logger.debug(f"[POI采集] 开始保存 {len(new_candidates)} 个新POI到数据库")
            saved_count = await self.save_poi_to_db(new_candidates, scenario_id)
            logger.info(f"[POI采集] 已保存 {saved_count} 个新POI到数据库")
        else:
            logger.debug(f"[POI采集] 跳过保存: save_to_db={save_to_db}, new_candidates={len(new_candidates)}")

        # 6. 转换为dict列表返回
        result = []
        for c in new_candidates:
            result.append({
                "site_id": str(c.id),
                "site_code": c.site_code,
                "name": c.name,
                "site_type": c.site_type,
                "longitude": c.longitude,
                "latitude": c.latitude,
                "address": c.address,
                "area_m2": c.area_m2,
                "slope_degree": c.slope_degree,
                "ground_stability": c.ground_stability,
                "has_water_supply": c.has_water_supply,
                "has_power_supply": c.has_power_supply,
                "can_helicopter_land": c.can_helicopter_land,
                "primary_network_type": c.primary_network_type,
                "signal_quality": c.signal_quality,
                "source": c.source,
            })

        logger.debug(f"[POI采集] collect_and_merge 出口: 返回 {len(result)} 个候选点, new_count={len(new_candidates)}")
        return result, len(new_candidates)

    async def collect_from_amap(
        self,
        center_lon: float,
        center_lat: float,
        search_radius_m: float,
        max_pages: int = 10,
    ) -> List[POICandidate]:
        """
        从高德API采集POI

        Args:
            center_lon: 搜索中心经度（WGS84，会自动转换为GCJ02）
            center_lat: 搜索中心纬度
            search_radius_m: 搜索半径（米）
            max_pages: 最大分页数

        Returns:
            POI候选点列表
        """
        import asyncio
        from src.core.coord_transform import wgs84_to_gcj02

        logger.debug(
            f"[POI采集] collect_from_amap 入口: "
            f"center=({center_lon}, {center_lat}), radius={search_radius_m}m, max_pages={max_pages}"
        )

        # WGS84 → GCJ02（高德使用GCJ02坐标系）
        gcj_lon, gcj_lat = wgs84_to_gcj02(center_lon, center_lat)
        logger.debug(f"[POI采集] 坐标转换: WGS84({center_lon}, {center_lat}) → GCJ02({gcj_lon}, {gcj_lat})")

        all_pois: List[POIResult] = []
        seen_ids = set()

        # 分页获取
        page = 1
        actual_radius = int(min(search_radius_m, 50000))
        logger.debug(f"[POI采集] 实际搜索半径: {actual_radius}m (高德API最大50km)")

        while page <= max_pages:
            try:
                logger.debug(f"[POI采集] 请求高德API: page={page}")
                pois = await search_poi_around(
                    center_lon=gcj_lon,
                    center_lat=gcj_lat,
                    radius_m=actual_radius,
                    page_num=page,
                )

                logger.debug(f"[POI采集] 高德API响应: page={page}, 返回 {len(pois) if pois else 0} 个POI")

                if not pois:
                    logger.debug(f"[POI采集] 高德API返回空，停止分页")
                    break

                for poi in pois:
                    if poi.id not in seen_ids:
                        seen_ids.add(poi.id)
                        all_pois.append(poi)

                if len(pois) < 25:
                    logger.debug(f"[POI采集] 本页POI数量({len(pois)}) < 25，停止分页")
                    break

                page += 1
                await asyncio.sleep(0.2)  # 避免请求过快

            except Exception as e:
                logger.error(f"[POI采集] 高德API请求失败: {e}", exc_info=True)
                break

        logger.info(f"[POI采集] 从高德API获取 {len(all_pois)} 个POI")

        # 转换为POICandidate，过滤不适合的类型
        candidates = []
        excluded_count = 0
        for poi in all_pois:
            # 检查是否为排除类型（建筑物等不适合驻扎的POI）
            if poi.type_code in EXCLUDED_POI_TYPES:
                excluded_count += 1
                logger.debug(
                    f"[POI采集] 排除不适合类型: {poi.name} "
                    f"({EXCLUDED_POI_TYPES[poi.type_code]}, code={poi.type_code})"
                )
                continue

            # GCJ02 → WGS84
            wgs_lon, wgs_lat = gcj02_to_wgs84(poi.longitude, poi.latitude)

            # 映射POI类型
            site_type = get_site_type_from_poi_code(poi.type_code)

            # 生成编号
            site_code = f"POI-{poi.id[:8].upper()}"

            # 根据类型推断设施
            has_water = site_type in ("school_yard", "sports_field", "logistics_center")
            has_power = site_type in ("school_yard", "sports_field", "logistics_center", "parking_lot")
            can_helicopter = site_type in ("sports_field", "plaza", "open_ground")

            # 根据类型估算面积
            area_m2 = self._estimate_area_by_type(site_type)

            candidates.append(POICandidate(
                id=uuid.uuid4(),
                site_code=site_code,
                name=poi.name,
                site_type=site_type,
                longitude=round(wgs_lon, 6),
                latitude=round(wgs_lat, 6),
                address=poi.address,
                area_m2=area_m2,
                elevation_m=None,
                slope_degree=3.0,  # 默认坡度
                ground_stability="unknown",
                has_water_supply=has_water,
                has_power_supply=has_power,
                can_helicopter_land=can_helicopter,
                primary_network_type="4g_lte",
                signal_quality="good",
                source="amap_poi",
                poi_id=poi.id,
            ))

        if excluded_count > 0:
            logger.info(
                f"[POI采集] 排除 {excluded_count} 个不适合类型（建筑物等），"
                f"保留 {len(candidates)} 个开阔场地类型"
            )

        logger.debug(f"[POI采集] collect_from_amap 出口: 返回 {len(candidates)} 个POICandidate")
        return candidates

    async def save_poi_to_db(
        self,
        candidates: List[POICandidate],
        scenario_id: Optional[UUID] = None,
    ) -> int:
        """
        将POI数据保存到数据库

        Args:
            candidates: POI候选点列表
            scenario_id: 想定ID（可选，POI数据通常不绑定想定）

        Returns:
            成功保存的数量
        """
        if not candidates:
            return 0

        saved_count = 0

        for c in candidates:
            try:
                # 转义单引号
                name = c.name.replace("'", "''") if c.name else ""
                address = c.address.replace("'", "''") if c.address else None
                address_sql = f"'{address}'" if address else "NULL"
                area = f"{c.area_m2}" if c.area_m2 else "NULL"
                elevation = f"{c.elevation_m}" if c.elevation_m else "NULL"
                slope = f"{c.slope_degree}" if c.slope_degree else "NULL"

                sql = text(f"""
                    INSERT INTO operational_v2.rescue_staging_sites_v2 (
                        id, site_code, name, site_type,
                        location, address, area_m2, elevation_m, slope_degree,
                        ground_stability, has_water_supply, has_power_supply,
                        can_helicopter_land, primary_network_type, signal_quality,
                        status, properties
                    ) VALUES (
                        '{c.id}', '{c.site_code}', '{name}', '{c.site_type}',
                        ST_SetSRID(ST_MakePoint({c.longitude}, {c.latitude}), 4326),
                        {address_sql}, {area}, {elevation}, {slope},
                        '{c.ground_stability}', {str(c.has_water_supply).lower()}, {str(c.has_power_supply).lower()},
                        {str(c.can_helicopter_land).lower()}, '{c.primary_network_type}', '{c.signal_quality}',
                        'available', '{{"source": "{c.source}", "poi_id": "{c.poi_id}"}}'
                    )
                    ON CONFLICT (site_code) DO NOTHING
                """)

                await self._db.execute(sql)
                saved_count += 1

            except Exception as e:
                logger.warning(f"[POI采集] 保存POI失败: {c.name}, {e}")

        # 提交事务
        await self._db.commit()

        return saved_count

    async def _count_db_candidates(
        self,
        center_lon: float,
        center_lat: float,
        search_radius_m: float,
    ) -> int:
        """查询数据库中指定范围内的候选点数量"""
        sql = text("""
            SELECT COUNT(*)
            FROM operational_v2.rescue_staging_sites_v2
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography,
                :search_radius_m
            )
        """)

        result = await self._db.execute(sql, {
            "center_lon": center_lon,
            "center_lat": center_lat,
            "search_radius_m": search_radius_m,
        })

        row = result.fetchone()
        return row[0] if row else 0

    async def _deduplicate_with_db(
        self,
        candidates: List[POICandidate],
        center_lon: float,
        center_lat: float,
        search_radius_m: float,
    ) -> List[POICandidate]:
        """
        与数据库已有数据去重

        基于坐标距离去重，100米内视为同一点
        """
        # 查询数据库中已有的候选点坐标
        sql = text("""
            SELECT
                ST_X(location::geometry) as longitude,
                ST_Y(location::geometry) as latitude
            FROM operational_v2.rescue_staging_sites_v2
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography,
                :search_radius_m
            )
        """)

        result = await self._db.execute(sql, {
            "center_lon": center_lon,
            "center_lat": center_lat,
            "search_radius_m": search_radius_m,
        })

        db_coords = [(row[0], row[1]) for row in result.fetchall()]

        # 去重
        new_candidates = []
        for c in candidates:
            is_duplicate = False
            for db_lon, db_lat in db_coords:
                dist = haversine_distance(c.longitude, c.latitude, db_lon, db_lat)
                if dist < self.DEDUP_DISTANCE_M:
                    is_duplicate = True
                    break

            if not is_duplicate:
                new_candidates.append(c)

        return new_candidates

    @staticmethod
    def _estimate_area_by_type(site_type: str) -> Optional[float]:
        """根据场地类型估算面积"""
        area_estimates = {
            "school_yard": 5000.0,
            "sports_field": 8000.0,
            "parking_lot": 3000.0,
            "plaza": 4000.0,
            "logistics_center": 6000.0,
            "open_ground": 2000.0,
            "other": 1500.0,
        }
        return area_estimates.get(site_type, 1500.0)


def calculate_search_radius(magnitude: float) -> float:
    """
    根据震级计算搜索半径

    Args:
        magnitude: 震级

    Returns:
        搜索半径（米）
    """
    # 5级30km，每增加1级增加10km
    base_radius_km = 30 + (magnitude - 5) * 10
    return max(base_radius_km, 20) * 1000  # 最小20km
