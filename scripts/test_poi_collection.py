"""
POI采集集成功能测试脚本

测试内容：
1. POICollectionService 直接测试
2. collect_poi_candidates 节点测试
3. find_safe_points 接口测试（含POI采集）

使用方法:
    python scripts/test_poi_collection.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置日志 - DEBUG级别以查看详细信息
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# 降低第三方库日志级别
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# 测试配置 - 茂县地震场景
TEST_SCENARIO_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
EPICENTER_LON = 103.85  # 茂县叠溪镇
EPICENTER_LAT = 31.68
MAGNITUDE = 6.8
SEARCH_RADIUS_M = 30000  # 30km


async def test_poi_service_direct():
    """
    测试1: 直接测试POICollectionService

    验证:
    - 数据库候选点数量查询
    - 高德API采集（如果数据不足）
    - 去重逻辑
    - 数据库保存
    """
    logger.info("=" * 60)
    logger.info("测试1: POICollectionService 直接测试")
    logger.info("=" * 60)

    from src.core.database import AsyncSessionLocal
    from src.domains.staging_area.poi_service import POICollectionService

    async with AsyncSessionLocal() as db:
        service = POICollectionService(db)

        logger.info(f"测试参数: center=({EPICENTER_LON}, {EPICENTER_LAT}), radius={SEARCH_RADIUS_M}m")

        # 调用采集服务
        poi_candidates, new_count = await service.collect_and_merge(
            center_lon=EPICENTER_LON,
            center_lat=EPICENTER_LAT,
            search_radius_m=SEARCH_RADIUS_M,
            scenario_id=TEST_SCENARIO_ID,
            min_candidates=10,
            save_to_db=True,
        )

        logger.info(f"采集结果: 新增 {new_count} 个POI, 返回 {len(poi_candidates)} 个候选点")

        # 打印前3个候选点详情
        for i, poi in enumerate(poi_candidates[:3]):
            logger.info(f"  候选点{i+1}: {poi.get('name')} ({poi.get('site_type')}) @ ({poi.get('longitude')}, {poi.get('latitude')})")

        return poi_candidates, new_count


async def test_poi_collection_node():
    """
    测试2: 测试collect_poi_candidates节点

    验证:
    - 节点参数解析
    - 搜索半径计算
    - 服务调用
    - 状态更新
    """
    logger.info("=" * 60)
    logger.info("测试2: collect_poi_candidates 节点测试")
    logger.info("=" * 60)

    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.poi_collection import collect_poi_candidates

    # 构造Agent状态
    state = {
        "scenario_id": TEST_SCENARIO_ID,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "timing": {},
        "errors": [],
    }

    logger.info(f"输入状态: scenario_id={TEST_SCENARIO_ID}, epicenter=({EPICENTER_LON}, {EPICENTER_LAT}), magnitude={MAGNITUDE}")

    async with AsyncSessionLocal() as db:
        result = await collect_poi_candidates(state, db)

        logger.info(f"节点输出:")
        logger.info(f"  - poi_candidates: {len(result.get('poi_candidates', []))} 个")
        logger.info(f"  - poi_collection_count: {result.get('poi_collection_count')}")
        logger.info(f"  - poi_collection_enabled: {result.get('poi_collection_enabled')}")
        logger.info(f"  - timing.poi_collection_ms: {result.get('timing', {}).get('poi_collection_ms')}ms")

        if result.get("errors"):
            logger.warning(f"  - errors: {result.get('errors')}")

        return result


async def test_find_safe_points():
    """
    测试3: 测试find_safe_points接口（含POI采集）

    验证:
    - _ensure_poi_data 调用
    - 完整查询流程
    - 评分和排序
    """
    logger.info("=" * 60)
    logger.info("测试3: find_safe_points 接口测试")
    logger.info("=" * 60)

    from src.core.database import AsyncSessionLocal
    from src.domains.staging_area.repository import StagingAreaRepository

    async with AsyncSessionLocal() as db:
        repo = StagingAreaRepository(db)

        logger.info(f"测试参数: scenario_id={TEST_SCENARIO_ID}, center=({EPICENTER_LON}, {EPICENTER_LAT})")
        logger.info(f"  search_radius={SEARCH_RADIUS_M}m, enable_poi_collection=True")

        # 调用find_safe_points
        sites = await repo.find_safe_points(
            scenario_id=TEST_SCENARIO_ID,
            center_lon=EPICENTER_LON,
            center_lat=EPICENTER_LAT,
            search_radius_m=SEARCH_RADIUS_M,
            min_buffer_m=500,
            max_slope_deg=15,
            top_n=5,
            enable_poi_collection=True,
            min_candidates_for_poi=10,
        )

        logger.info(f"查询结果: 返回 {len(sites)} 个安全点位")

        # 打印详细结果
        for i, site in enumerate(sites):
            logger.info(f"  #{i+1} {site['name']} ({site['site_type']})")
            logger.info(f"      位置: ({site['longitude']}, {site['latitude']})")
            logger.info(f"      评分: {site['score']:.3f}")
            logger.info(f"      评分详情: {site.get('score_breakdown', {})}")
            if site.get('risk_warnings'):
                logger.info(f"      风险提示: {site['risk_warnings']}")

        return sites


async def test_db_candidate_count():
    """
    辅助测试: 检查数据库中的候选点数量
    """
    logger.info("=" * 60)
    logger.info("辅助测试: 数据库候选点数量检查")
    logger.info("=" * 60)

    from sqlalchemy import text
    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # 查询总数
        result = await db.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE site_code LIKE 'POI-%') as poi_count,
                   COUNT(*) FILTER (WHERE site_code LIKE 'SS-%') as manual_count
            FROM operational_v2.rescue_staging_sites_v2
        """))
        row = result.fetchone()
        logger.info(f"数据库总记录: {row[0]} 条 (POI: {row[1]}, 手动: {row[2]})")

        # 查询指定范围内的数量
        result = await db.execute(text("""
            SELECT COUNT(*)
            FROM operational_v2.rescue_staging_sites_v2
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography,
                :search_radius_m
            )
        """), {
            "center_lon": EPICENTER_LON,
            "center_lat": EPICENTER_LAT,
            "search_radius_m": SEARCH_RADIUS_M,
        })
        count = result.scalar()
        logger.info(f"搜索范围内({SEARCH_RADIUS_M/1000}km): {count} 条")

        # 按类型统计
        result = await db.execute(text("""
            SELECT site_type, COUNT(*) as count
            FROM operational_v2.rescue_staging_sites_v2
            WHERE ST_DWithin(
                location,
                ST_SetSRID(ST_Point(:center_lon, :center_lat), 4326)::geography,
                :search_radius_m
            )
            GROUP BY site_type
            ORDER BY count DESC
        """), {
            "center_lon": EPICENTER_LON,
            "center_lat": EPICENTER_LAT,
            "search_radius_m": SEARCH_RADIUS_M,
        })
        logger.info("按类型分布:")
        for row in result.fetchall():
            logger.info(f"  - {row[0]}: {row[1]} 条")

        return count


async def main():
    """主测试流程"""
    logger.info("=" * 60)
    logger.info("POI采集集成功能测试")
    logger.info("=" * 60)

    try:
        # 0. 先检查数据库状态
        await test_db_candidate_count()

        # 1. 测试POI服务
        await test_poi_service_direct()

        # 2. 测试Agent节点
        await test_poi_collection_node()

        # 3. 测试find_safe_points接口
        await test_find_safe_points()

        logger.info("=" * 60)
        logger.info("所有测试完成!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
