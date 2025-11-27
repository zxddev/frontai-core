"""
驻扎点选址服务简化测试（跳过路径验证）

测试核心逻辑：风险区域计算、候选点搜索、评分排序
"""
import asyncio
import logging
import sys
from uuid import uuid4, UUID
from dataclasses import replace

sys.path.insert(0, "/home/dev/gitcode/frontai/frontai-core")

from src.core.database import AsyncSessionLocal
from src.domains.staging_area.core import StagingAreaCore
from src.domains.staging_area.schemas import (
    EarthquakeParams,
    RescueTarget,
    TeamInfo,
    StagingConstraints,
    TargetPriority,
    CandidateWithRoutes,
    RouteToTarget,
)
from src.domains.staging_area.repository import StagingAreaRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TEST_SCENARIO_ID = UUID("550e8400-e29b-41d4-a716-446655440001")
EPICENTER = (103.85, 31.68)
MAGNITUDE = 6.8


async def test_risk_zones():
    """测试风险区域计算"""
    logger.info("=" * 60)
    logger.info("测试风险区域计算")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        core = StagingAreaCore(db)
        
        earthquake = EarthquakeParams(
            epicenter_lon=EPICENTER[0],
            epicenter_lat=EPICENTER[1],
            magnitude=MAGNITUDE,
        )
        
        zones = await core._calculate_risk_zones(TEST_SCENARIO_ID, earthquake)
        
        logger.info(f"计算出 {len(zones)} 个风险区域:")
        for z in zones:
            logger.info(f"  - {z.zone_type.value}: risk_level={z.risk_level}, passable={z.passable}")
        
        # 验证烈度半径计算
        red_radius = core._estimate_intensity_radius(MAGNITUDE, 8)
        orange_radius = core._estimate_intensity_radius(MAGNITUDE, 6)
        logger.info(f"烈度8红区半径: {red_radius:.1f}km")
        logger.info(f"烈度6橙区半径: {orange_radius:.1f}km")


async def test_candidate_search():
    """测试候选点搜索"""
    logger.info("=" * 60)
    logger.info("测试候选点搜索")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        repo = StagingAreaRepository(db)
        
        candidates = await repo.search_candidates(
            scenario_id=TEST_SCENARIO_ID,
            center_lon=EPICENTER[0],
            center_lat=EPICENTER[1],
            max_distance_m=100000,  # 100km范围
            min_buffer_from_danger_m=0,  # 无缓冲限制
            max_slope_deg=90,  # 无坡度限制
            max_results=20,
        )
        
        logger.info(f"找到 {len(candidates)} 个候选点:")
        for c in candidates:
            logger.info(
                f"  - {c.site_code}: {c.name} ({c.site_type.value})"
                f" @ ({c.longitude:.4f}, {c.latitude:.4f})"
            )
            logger.info(
                f"      水={c.has_water_supply}, 电={c.has_power_supply}, "
                f"直升机={c.can_helicopter_land}, 网络={c.primary_network_type.value}"
            )


async def test_evaluation_with_mock_routes():
    """测试评分逻辑（使用模拟路径数据）"""
    logger.info("=" * 60)
    logger.info("测试评分逻辑（模拟路径）")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        repo = StagingAreaRepository(db)
        core = StagingAreaCore(db)
        
        # 获取候选点
        candidates = await repo.search_candidates(
            scenario_id=TEST_SCENARIO_ID,
            center_lon=EPICENTER[0],
            center_lat=EPICENTER[1],
            max_distance_m=100000,
            min_buffer_from_danger_m=0,
            max_slope_deg=90,
            max_results=20,
        )
        
        if not candidates:
            logger.error("无候选点，测试中止")
            return
        
        # 定义救援目标
        targets = [
            RescueTarget(
                id=uuid4(),
                name="受灾点A",
                longitude=103.66,
                latitude=31.46,
                priority=TargetPriority.CRITICAL,
            ),
            RescueTarget(
                id=uuid4(),
                name="受灾点B",
                longitude=103.71,
                latitude=31.51,
                priority=TargetPriority.HIGH,
            ),
            RescueTarget(
                id=uuid4(),
                name="受灾点C",
                longitude=103.76,
                latitude=31.56,
                priority=TargetPriority.MEDIUM,
            ),
        ]
        
        # 模拟路径数据（基于直线距离估算）
        import math
        
        def haversine_distance(lon1, lat1, lon2, lat2):
            """计算两点间的球面距离(米)"""
            R = 6371000
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            delta_phi = math.radians(lat2 - lat1)
            delta_lambda = math.radians(lon2 - lon1)
            a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
            return 2 * R * math.asin(math.sqrt(a))
        
        team_lon, team_lat = 103.58, 31.48
        
        candidates_with_routes = []
        for c in candidates:
            # 模拟从驻地到候选点的路径（直线距离*1.3）
            dist_from_base = haversine_distance(team_lon, team_lat, c.longitude, c.latitude) * 1.3
            duration_from_base = dist_from_base / (50 * 1000 / 3600)  # 50km/h
            
            # 模拟到各目标的路径
            routes_to_targets = []
            for t in targets:
                dist_to_target = haversine_distance(c.longitude, c.latitude, t.longitude, t.latitude) * 1.3
                duration_to_target = dist_to_target / (50 * 1000 / 3600)
                routes_to_targets.append(RouteToTarget(
                    target_id=t.id,
                    target_name=t.name,
                    distance_m=dist_to_target,
                    duration_seconds=duration_to_target,
                    priority=t.priority,
                ))
            
            candidates_with_routes.append(CandidateWithRoutes(
                site=c,
                route_from_base_distance_m=dist_from_base,
                route_from_base_duration_s=duration_from_base,
                routes_to_targets=routes_to_targets,
                is_reachable=True,
            ))
        
        logger.info(f"模拟 {len(candidates_with_routes)} 个可达候选点")
        
        # 执行评分排序
        from src.domains.staging_area.schemas import EvaluationWeights
        
        ranked = core._evaluate_and_rank(
            candidates=candidates_with_routes,
            targets=targets,
            constraints=StagingConstraints(),
            weights=EvaluationWeights(),
        )
        
        logger.info("-" * 40)
        logger.info("推荐排序结果:")
        for i, site in enumerate(ranked[:5], 1):
            logger.info(f"#{i} {site.name} (总分: {site.total_score:.3f})")
            logger.info(f"    位置: ({site.longitude:.4f}, {site.latitude:.4f})")
            logger.info(f"    设施: 水={site.has_water_supply}, 电={site.has_power_supply}, 直升机={site.can_helicopter_land}")
            logger.info(f"    评分明细: {site.scores}")
            logger.info(f"    从驻地: {site.route_from_base_distance_m/1000:.1f}km")
            logger.info(f"    到目标平均响应: {site.avg_response_time_to_targets_s/60:.1f}min")


async def main():
    """主入口"""
    await test_risk_zones()
    await test_candidate_search()
    await test_evaluation_with_mock_routes()
    
    logger.info("=" * 60)
    logger.info("所有测试完成!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
