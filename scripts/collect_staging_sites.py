"""
救援驻扎点候选数据采集脚本

从高德POI采集真实的候选点数据，仅限茂县区域。

使用方法:
    python scripts/collect_staging_sites.py --output scripts/staging_sites_data.sql
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ============== 茂县区域网格中心点 ==============
# 仅覆盖茂县及周边区域（GCJ02坐标系，用于高德API）
# 茂县县域范围大约: 经度 103.4-104.1, 纬度 31.4-32.2

MAOXIAN_GRID_CENTERS = [
    # 茂县县城及周边
    (103.853, 31.681),   # 茂县县城（凤仪镇）
    (103.820, 31.720),   # 县城北部
    (103.880, 31.650),   # 县城东南

    # 叠溪镇区域（地震遗址区）
    (103.667, 31.450),   # 叠溪镇中心
    (103.700, 31.480),   # 叠溪镇东北
    (103.630, 31.420),   # 叠溪镇西南

    # 其他主要乡镇
    (103.750, 31.550),   # 黑虎乡
    (103.900, 31.750),   # 南新镇
    (103.780, 31.600),   # 渭门乡
    (103.950, 31.800),   # 土门乡
    (103.600, 31.500),   # 太平乡
    (103.850, 31.850),   # 沟口乡
]


@dataclass
class StagingSiteCandidate:
    """驻扎点候选数据"""
    id: uuid.UUID
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


def deduplicate_candidates(
    candidates: List[StagingSiteCandidate],
    min_distance_m: float = 100,
) -> List[StagingSiteCandidate]:
    """
    基于距离的去重

    两个点距离小于min_distance_m时，保留第一个
    """
    unique = []
    for c in candidates:
        is_duplicate = False
        for u in unique:
            dist = haversine_distance(c.longitude, c.latitude, u.longitude, u.latitude)
            if dist < min_distance_m:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(c)

    return unique


async def collect_from_amap(
    grid_centers: List[Tuple[float, float]],
    search_radius_m: int = 8000,
) -> List[StagingSiteCandidate]:
    """
    从高德POI采集候选点

    Args:
        grid_centers: 网格中心点列表（GCJ02坐标）
        search_radius_m: 搜索半径（米）

    Returns:
        候选点列表
    """
    from src.infra.clients.amap.poi_search import (
        search_poi_around,
        STAGING_POI_TYPES,
        get_site_type_from_poi_code,
    )
    from src.core.coord_transform import gcj02_to_wgs84

    all_pois = []
    seen_ids = set()

    for i, (lon, lat) in enumerate(grid_centers):
        logger.info(f"[采集] 搜索网格 {i+1}/{len(grid_centers)}: ({lon:.3f}, {lat:.3f})")

        # 分页获取所有结果
        page = 1
        while page <= 10:  # 最多10页，避免无限循环
            pois = await search_poi_around(
                center_lon=lon,
                center_lat=lat,
                radius_m=search_radius_m,
                page_num=page,
            )

            if not pois:
                break

            for poi in pois:
                if poi.id not in seen_ids:
                    seen_ids.add(poi.id)
                    all_pois.append(poi)

            if len(pois) < 25:
                break

            page += 1
            await asyncio.sleep(0.2)  # 避免请求过快

        await asyncio.sleep(0.3)  # 网格间隔

    logger.info(f"[采集] 共获取 {len(all_pois)} 个唯一POI")

    # 转换为候选点
    candidates = []
    for poi in all_pois:
        # 坐标转换: GCJ02 → WGS84
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
        area_m2 = _estimate_area_by_type(site_type)

        candidates.append(StagingSiteCandidate(
            id=uuid.uuid4(),
            site_code=site_code,
            name=poi.name,
            site_type=site_type,
            longitude=round(wgs_lon, 6),
            latitude=round(wgs_lat, 6),
            address=poi.address,
            area_m2=area_m2,
            elevation_m=None,  # 后续从DEM补充
            slope_degree=None,  # 后续从DEM补充
            ground_stability="unknown",
            has_water_supply=has_water,
            has_power_supply=has_power,
            can_helicopter_land=can_helicopter,
            primary_network_type="4g_lte",  # 茂县县城有4G覆盖
            signal_quality="good",
            source="amap_poi",
        ))

    return candidates


def _estimate_area_by_type(site_type: str) -> Optional[float]:
    """
    根据场地类型估算面积

    这是一个粗略估算，实际面积需要从其他数据源获取
    """
    area_estimates = {
        "school_yard": 5000.0,      # 学校操场
        "sports_field": 8000.0,     # 体育场
        "parking_lot": 3000.0,      # 停车场
        "plaza": 4000.0,            # 广场
        "logistics_center": 6000.0, # 物流中心
        "open_ground": 2000.0,      # 空地
        "other": 1500.0,
    }
    return area_estimates.get(site_type, 1500.0)


def enrich_with_dem(
    candidates: List[StagingSiteCandidate],
) -> List[StagingSiteCandidate]:
    """
    使用DEM数据补充高程和坡度

    Args:
        candidates: 候选点列表

    Returns:
        补充后的候选点列表
    """
    try:
        from src.agents.recon_scheduler.terrain_checker import get_terrain_checker
        import math

        checker = get_terrain_checker(use_mock=False)
        enriched_count = 0

        for candidate in candidates:
            try:
                # 获取高程
                elevation = checker.get_elevation(
                    lat=candidate.latitude,
                    lng=candidate.longitude
                )
                candidate.elevation_m = round(elevation, 1)

                # 计算坡度（使用周边点估算）
                slope = _estimate_slope(
                    checker,
                    candidate.longitude,
                    candidate.latitude,
                    sample_distance_m=30
                )
                candidate.slope_degree = round(slope, 1)
                enriched_count += 1

            except Exception as e:
                logger.debug(f"[DEM] 获取地形数据失败: {candidate.name}, {e}")
                # 使用默认值
                candidate.elevation_m = 1500.0  # 茂县平均海拔约1500m
                candidate.slope_degree = 3.0

        logger.info(f"[DEM] 已补充 {enriched_count}/{len(candidates)} 个点的地形数据")

    except Exception as e:
        logger.warning(f"[DEM] DEM处理失败，使用估算数据: {e}")
        # 使用估算数据
        for candidate in candidates:
            # 茂县海拔范围约1200-4000m，根据纬度粗略估算
            base_elevation = 1400 + (candidate.latitude - 31.4) * 500
            candidate.elevation_m = round(base_elevation, 1)
            candidate.slope_degree = 3.0

    return candidates


def _estimate_slope(
    checker,
    lon: float,
    lat: float,
    sample_distance_m: float = 30,
) -> float:
    """
    估算坡度

    使用四个方向的高程差计算平均坡度
    """
    import math

    # 经纬度偏移量
    dlat = sample_distance_m / 111000
    dlon = sample_distance_m / (111000 * math.cos(math.radians(lat)))

    try:
        center_elev = checker.get_elevation(lat, lon)
    except:
        return 3.0  # 默认坡度

    slopes = []
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        try:
            neighbor_elev = checker.get_elevation(
                lat + dy * dlat,
                lon + dx * dlon
            )
            elev_diff = abs(neighbor_elev - center_elev)
            slope_rad = math.atan(elev_diff / sample_distance_m)
            slopes.append(math.degrees(slope_rad))
        except:
            pass

    return sum(slopes) / len(slopes) if slopes else 3.0


def validate_candidate(c: StagingSiteCandidate) -> List[str]:
    """验证候选点数据完整性"""
    errors = []

    # 必填字段
    if not c.name:
        errors.append("名称为空")
    if not c.site_type:
        errors.append("类型为空")

    # 坐标范围（茂县区域）
    if not (103.3 < c.longitude < 104.2):
        errors.append(f"经度超出茂县范围: {c.longitude}")
    if not (31.3 < c.latitude < 32.3):
        errors.append(f"纬度超出茂县范围: {c.latitude}")

    # 坡度合理性
    if c.slope_degree and c.slope_degree > 30:
        errors.append(f"坡度过大: {c.slope_degree}°")

    return errors


def generate_sql(
    candidates: List[StagingSiteCandidate],
    output_path: str,
) -> None:
    """
    生成SQL插入语句

    Args:
        candidates: 候选点列表
        output_path: 输出文件路径
    """
    sql_lines = [
        "-- ============================================================",
        "-- 救援驻扎点候选数据 - 茂县区域",
        "-- 自动生成，数据来源: 高德POI API",
        "-- ============================================================",
        "",
        "BEGIN;",
        "",
        "-- 清除旧的POI数据（保留手动添加的SS-开头数据）",
        "DELETE FROM operational_v2.rescue_staging_sites_v2",
        "WHERE site_code LIKE 'POI-%';",
        "",
    ]

    valid_count = 0
    for c in candidates:
        # 验证数据
        errors = validate_candidate(c)
        if errors:
            logger.warning(f"[验证] 跳过无效数据 {c.name}: {errors}")
            continue

        valid_count += 1

        # 处理NULL值和特殊字符
        area = f"{c.area_m2}" if c.area_m2 else "NULL"
        elevation = f"{c.elevation_m}" if c.elevation_m else "NULL"
        slope = f"{c.slope_degree}" if c.slope_degree else "NULL"

        # 转义单引号
        name = c.name.replace("'", "''") if c.name else ""
        address = c.address.replace("'", "''") if c.address else None
        address_sql = f"'{address}'" if address else "NULL"

        sql = f"""INSERT INTO operational_v2.rescue_staging_sites_v2 (
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
    'available', '{{"source": "{c.source}"}}'
);"""
        sql_lines.append(sql)

    sql_lines.append("")
    sql_lines.append("COMMIT;")
    sql_lines.append("")
    sql_lines.append(f"-- 共插入 {valid_count} 条记录")
    sql_lines.append("")

    # 添加验证查询
    sql_lines.append("-- 验证查询")
    sql_lines.append("-- SELECT COUNT(*) as total, site_type, COUNT(*) as count")
    sql_lines.append("-- FROM operational_v2.rescue_staging_sites_v2")
    sql_lines.append("-- GROUP BY site_type;")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    logger.info(f"[SQL] 已生成SQL文件: {output_path}, 共 {valid_count} 条记录")


async def main():
    parser = argparse.ArgumentParser(description="采集救援驻扎点候选数据（茂县区域）")
    parser.add_argument(
        "--radius",
        type=int,
        default=8000,
        help="搜索半径（米），默认8000"
    )
    parser.add_argument(
        "--output",
        default="scripts/staging_sites_data.sql",
        help="输出SQL文件路径"
    )
    parser.add_argument(
        "--skip-dem",
        action="store_true",
        help="跳过DEM数据补充"
    )
    parser.add_argument(
        "--min-distance",
        type=int,
        default=100,
        help="去重最小距离（米），默认100"
    )

    args = parser.parse_args()

    logger.info(f"[开始] 茂县区域数据采集, 半径: {args.radius}m, 网格数: {len(MAOXIAN_GRID_CENTERS)}")

    # 1. 从高德POI采集
    candidates = await collect_from_amap(
        grid_centers=MAOXIAN_GRID_CENTERS,
        search_radius_m=args.radius,
    )

    if not candidates:
        logger.error("[错误] 未采集到任何数据，请检查高德API Key配置")
        return

    logger.info(f"[采集] 原始数据: {len(candidates)} 个候选点")

    # 2. 去重
    candidates = deduplicate_candidates(candidates, min_distance_m=args.min_distance)
    logger.info(f"[去重] 去重后: {len(candidates)} 个候选点")

    # 3. 使用DEM补充地形数据
    if not args.skip_dem:
        candidates = enrich_with_dem(candidates)
    else:
        # 使用默认值
        for c in candidates:
            c.elevation_m = 1500.0
            c.slope_degree = 3.0

    # 4. 生成SQL
    generate_sql(candidates, args.output)

    # 5. 统计信息
    type_counts = {}
    for c in candidates:
        type_counts[c.site_type] = type_counts.get(c.site_type, 0) + 1

    logger.info("[统计] 按类型分布:")
    for site_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  - {site_type}: {count} 个")

    logger.info(f"[完成] 共采集 {len(candidates)} 个候选点，SQL文件: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
