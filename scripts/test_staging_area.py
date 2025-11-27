"""
驻扎点选址服务集成测试

测试前需要：
1. 执行 sql/v8_rescue_staging_sites.sql 创建表
2. 导入测试数据
"""
import asyncio
import logging
import sys
from uuid import uuid4, UUID

sys.path.insert(0, "/home/dev/gitcode/frontai/frontai-core")

from src.core.database import AsyncSessionLocal
from src.domains.staging_area.core import StagingAreaCore
from src.domains.staging_area.schemas import (
    EarthquakeParams,
    RescueTarget,
    TeamInfo,
    StagingConstraints,
    TargetPriority,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# 测试数据：四川茂县地震场景
TEST_SCENARIO_ID = UUID("550e8400-e29b-41d4-a716-446655440001")  # 需替换为实际ID
EPICENTER = (103.85, 31.68)  # 茂县震中
MAGNITUDE = 6.8

# 救援队伍驻地（汶川方向，距离较近便于测试）
TEAM_BASE = (103.58, 31.48)  # 汶川物流中心附近

# 救援目标（使用已有驻扎点附近的位置作为测试目标）
RESCUE_TARGETS = [
    {"name": "叠溪镇受灾点", "location": (103.66, 31.46), "priority": "critical"},
    {"name": "松坪沟受灾点", "location": (103.71, 31.51), "priority": "high"},
    {"name": "黑虎乡受灾点", "location": (103.76, 31.56), "priority": "medium"},
]


async def test_recommend():
    """测试驻扎点推荐"""
    logger.info("=" * 60)
    logger.info("测试驻扎点推荐")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        core = StagingAreaCore(db)
        
        earthquake = EarthquakeParams(
            epicenter_lon=EPICENTER[0],
            epicenter_lat=EPICENTER[1],
            magnitude=MAGNITUDE,
            depth_km=10.0,
        )
        
        targets = [
            RescueTarget(
                id=uuid4(),
                name=t["name"],
                longitude=t["location"][0],
                latitude=t["location"][1],
                priority=TargetPriority(t["priority"]),
            )
            for t in RESCUE_TARGETS
        ]
        
        team = TeamInfo(
            team_id=uuid4(),
            team_name="成都消防支队",
            base_lon=TEAM_BASE[0],
            base_lat=TEAM_BASE[1],
            max_speed_kmh=60.0,
        )
        
        constraints = StagingConstraints(
            min_buffer_m=500,
            max_slope_deg=15,
            max_search_radius_m=50000,
            top_n=5,
        )
        
        logger.info(f"震中: {EPICENTER}, 震级: {MAGNITUDE}")
        logger.info(f"队伍驻地: {TEAM_BASE}")
        logger.info(f"救援目标数: {len(targets)}")
        
        result = await core.recommend(
            scenario_id=TEST_SCENARIO_ID,
            earthquake=earthquake,
            rescue_targets=targets,
            team=team,
            constraints=constraints,
        )
        
        logger.info("-" * 40)
        logger.info(f"推荐结果: success={result.success}")
        
        if not result.success:
            logger.error(f"推荐失败: {result.error}")
            return
        
        logger.info(f"风险区域数: {result.risk_zones_count}")
        logger.info(f"候选点总数: {result.candidates_total}")
        logger.info(f"可达候选点: {result.candidates_reachable}")
        logger.info(f"耗时: {result.elapsed_ms}ms")
        logger.info("-" * 40)
        
        for i, site in enumerate(result.recommended_sites, 1):
            logger.info(f"#{i} {site.name} (总分: {site.total_score:.3f})")
            logger.info(f"    位置: ({site.longitude:.4f}, {site.latitude:.4f})")
            logger.info(f"    类型: {site.site_type}")
            logger.info(f"    设施: 水={site.has_water_supply}, 电={site.has_power_supply}, 直升机={site.can_helicopter_land}")
            logger.info(f"    从驻地距离: {site.route_from_base_distance_m/1000:.1f}km, 时间: {site.route_from_base_duration_s/60:.1f}min")
            logger.info(f"    到目标平均响应: {site.avg_response_time_to_targets_s/60:.1f}min")
            logger.info(f"    评分: {site.scores}")
        
        logger.info("=" * 60)


async def test_repository():
    """测试数据仓库层"""
    logger.info("=" * 60)
    logger.info("测试数据仓库层")
    logger.info("=" * 60)
    
    from src.domains.staging_area.repository import StagingAreaRepository
    
    async with AsyncSessionLocal() as db:
        repo = StagingAreaRepository(db)
        
        # 搜索候选点
        candidates = await repo.search_candidates(
            scenario_id=TEST_SCENARIO_ID,
            center_lon=EPICENTER[0],
            center_lat=EPICENTER[1],
            max_distance_m=50000,
            min_buffer_from_danger_m=500,
            max_slope_deg=15,
            max_results=10,
        )
        
        logger.info(f"找到候选点: {len(candidates)}")
        for c in candidates[:5]:
            logger.info(f"  - {c.name}: ({c.longitude:.4f}, {c.latitude:.4f})")
        
        # 获取危险区域
        zones = await repo.get_danger_zones(TEST_SCENARIO_ID)
        logger.info(f"危险区域数: {len(zones)}")
        for z in zones[:3]:
            logger.info(f"  - {z['area_type']}: risk_level={z['risk_level']}")
        
        logger.info("=" * 60)


async def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="驻扎点选址服务测试")
    parser.add_argument("--test", choices=["recommend", "repository", "all"], default="all")
    args = parser.parse_args()
    
    if args.test in ("recommend", "all"):
        await test_recommend()
    
    if args.test in ("repository", "all"):
        await test_repository()


if __name__ == "__main__":
    asyncio.run(main())
