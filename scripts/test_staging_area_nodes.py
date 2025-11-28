#!/usr/bin/env python3
"""
驻扎点选址智能体节点测试

逐个测试 6 个节点的功能，不依赖路网验证。
用于在路网数据有问题时验证 Agent 逻辑。

运行方式：
    cd /home/dev/gitcode/frontai/frontai-core
    .venv/bin/python scripts/test_staging_area_nodes.py
"""
import asyncio
import logging
import os
import sys
import time
from uuid import UUID, uuid4

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# 测试数据：四川省内
TEST_SCENARIO_ID = UUID("11111111-1111-1111-1111-111111111111")
EPICENTER_LON = 103.8537  # 茂县叠溪镇
EPICENTER_LAT = 31.6815
MAGNITUDE = 7.0
TEAM_BASE_LON = 104.065  # 成都
TEAM_BASE_LAT = 30.659

DISASTER_DESCRIPTION = """
茂县叠溪镇发生7.0级地震，震源深度10公里。
地震造成多处建筑倒塌，国道213线多处被滑坡阻断。
目前已确认叠溪镇中心、松坪沟村、飞虹乡等区域有人员被困。
通信基站部分损毁，部分区域失联。
预计未来72小时内仍有5级以上余震风险。
"""

# 模拟候选点数据（用于测试分析节点）
MOCK_CANDIDATE_SITES = [
    {
        "site_id": str(uuid4()),
        "site_code": "STA001",
        "name": "叠溪镇中心广场",
        "site_type": "open_ground",
        "longitude": 103.67,
        "latitude": 31.45,
        "area_m2": 8000,
        "slope_degree": 5,
        "ground_stability": "good",
        "has_water_supply": True,
        "has_power_supply": True,
        "can_helicopter_land": True,
        "primary_network_type": "4g_lte",
        "signal_quality": "fair",
        "distance_to_danger_m": 800,
    },
    {
        "site_id": str(uuid4()),
        "site_code": "STA002",
        "name": "松坪沟游客停车场",
        "site_type": "parking_lot",
        "longitude": 103.70,
        "latitude": 31.50,
        "area_m2": 5000,
        "slope_degree": 8,
        "ground_stability": "moderate",
        "has_water_supply": False,
        "has_power_supply": False,
        "can_helicopter_land": False,
        "primary_network_type": "satellite",
        "signal_quality": "poor",
        "distance_to_danger_m": 500,
    },
    {
        "site_id": str(uuid4()),
        "site_code": "STA003",
        "name": "茂县体育中心",
        "site_type": "sports_field",
        "longitude": 103.85,
        "latitude": 31.70,
        "area_m2": 12000,
        "slope_degree": 2,
        "ground_stability": "excellent",
        "has_water_supply": True,
        "has_power_supply": True,
        "can_helicopter_land": True,
        "primary_network_type": "5g",
        "signal_quality": "good",
        "distance_to_danger_m": 1200,
    },
]


async def test_understand_node():
    """测试灾情理解节点"""
    print("\n" + "="*60)
    print("测试1: 灾情理解节点 (understand_disaster)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.understand import understand_disaster
    from src.agents.staging_area.state import StagingAreaAgentState
    
    state: StagingAreaAgentState = {
        "disaster_description": DISASTER_DESCRIPTION,
        "scenario_id": TEST_SCENARIO_ID,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        result = await understand_disaster(state, db)
        elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.0f}ms")
    print(f"处理模式: {result.get('processing_mode')}")
    
    parsed = result.get("parsed_disaster")
    if parsed:
        print(f"✅ 成功解析灾情:")
        print(f"   - 灾害类型: {parsed.disaster_type}")
        print(f"   - 震级: {parsed.magnitude}")
        print(f"   - 约束条件数: {len(parsed.extracted_constraints)}")
        for c in parsed.extracted_constraints[:3]:
            print(f"     * {c.constraint_type}: {c.description[:50]}...")
    else:
        print(f"❌ 解析失败: {result.get('errors')}")
    
    return result


async def test_terrain_node():
    """测试地形分析节点"""
    print("\n" + "="*60)
    print("测试2: 地形分析节点 (analyze_terrain)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.terrain import analyze_terrain
    from src.agents.staging_area.state import StagingAreaAgentState
    
    state: StagingAreaAgentState = {
        "candidate_sites": MOCK_CANDIDATE_SITES,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        result = await analyze_terrain(state, db)
        elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.0f}ms")
    
    assessments = result.get("terrain_assessments", [])
    if assessments:
        print(f"✅ 成功分析 {len(assessments)} 个候选点:")
        for a in assessments:
            print(f"   - {a.site_name}: {a.terrain_suitability}")
            print(f"     坡度评估: {a.slope_assessment[:50]}...")
    else:
        print(f"⚠️ 无分析结果: {result.get('errors')}")
    
    return result


async def test_communication_node():
    """测试通信分析节点"""
    print("\n" + "="*60)
    print("测试3: 通信分析节点 (analyze_communication)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.communication import analyze_communication
    from src.agents.staging_area.state import StagingAreaAgentState
    
    state: StagingAreaAgentState = {
        "candidate_sites": MOCK_CANDIDATE_SITES,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        result = await analyze_communication(state, db)
        elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.0f}ms")
    
    assessments = result.get("communication_assessments", [])
    if assessments:
        print(f"✅ 成功分析 {len(assessments)} 个候选点:")
        for a in assessments:
            print(f"   - {a.site_name}: {a.primary_network_quality}")
            print(f"     备用方案: {a.backup_options[:3]}")
    else:
        print(f"⚠️ 无分析结果: {result.get('errors')}")
    
    return result


async def test_safety_node():
    """测试安全分析节点"""
    print("\n" + "="*60)
    print("测试4: 安全分析节点 (analyze_safety)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.safety import analyze_safety
    from src.agents.staging_area.state import StagingAreaAgentState
    
    state: StagingAreaAgentState = {
        "candidate_sites": MOCK_CANDIDATE_SITES,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        result = await analyze_safety(state, db)
        elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.0f}ms")
    
    assessments = result.get("safety_assessments", [])
    if assessments:
        print(f"✅ 成功分析 {len(assessments)} 个候选点:")
        for a in assessments:
            print(f"   - {a.site_name}: {a.safety_level}")
            if a.safety_warnings:
                print(f"     警告: {a.safety_warnings[0][:50]}...")
    else:
        print(f"⚠️ 无分析结果: {result.get('errors')}")
    
    return result


async def test_explain_node():
    """测试决策解释节点"""
    print("\n" + "="*60)
    print("测试5: 决策解释节点 (explain_decision)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.explain import explain_decision
    from src.agents.staging_area.state import StagingAreaAgentState
    
    # 模拟已排序的候选点
    ranked_sites = [
        {
            "site_id": MOCK_CANDIDATE_SITES[2]["site_id"],
            "site_code": "STA003",
            "name": "茂县体育中心",
            "site_type": "sports_field",
            "longitude": 103.85,
            "latitude": 31.70,
            "total_score": 0.85,
            "scores": {
                "response_time": 0.80,
                "safety": 0.90,
                "logistics": 0.85,
                "facility": 0.95,
                "communication": 0.70,
            },
            "route_from_base_distance_m": 95000,
            "route_from_base_duration_s": 7200,
            "avg_response_time_to_targets_s": 1800,
            "has_water_supply": True,
            "has_power_supply": True,
            "can_helicopter_land": True,
        },
        {
            "site_id": MOCK_CANDIDATE_SITES[0]["site_id"],
            "site_code": "STA001",
            "name": "叠溪镇中心广场",
            "site_type": "open_ground",
            "longitude": 103.67,
            "latitude": 31.45,
            "total_score": 0.78,
            "scores": {
                "response_time": 0.85,
                "safety": 0.70,
                "logistics": 0.80,
                "facility": 0.85,
                "communication": 0.65,
            },
            "route_from_base_distance_m": 85000,
            "route_from_base_duration_s": 6000,
            "avg_response_time_to_targets_s": 1200,
            "has_water_supply": True,
            "has_power_supply": True,
            "can_helicopter_land": True,
        },
    ]
    
    state: StagingAreaAgentState = {
        "disaster_description": DISASTER_DESCRIPTION,
        "ranked_sites": ranked_sites,
        "candidate_sites": MOCK_CANDIDATE_SITES,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        result = await explain_decision(state, db)
        elapsed = time.perf_counter() - start
    
    print(f"耗时: {elapsed*1000:.0f}ms")
    
    explanations = result.get("site_explanations", [])
    warnings = result.get("risk_warnings", [])
    summary = result.get("summary", "")
    
    if explanations:
        print(f"✅ 生成 {len(explanations)} 个推荐解释:")
        for e in explanations:
            print(f"   - [{e.rank}] {e.site_name}")
            print(f"     推荐理由: {e.recommendation_reason[:60]}...")
            print(f"     优势: {e.advantages[:2]}")
    else:
        print(f"⚠️ 无解释结果: {result.get('errors')}")
    
    if warnings:
        print(f"\n⚠️ 风险警示 ({len(warnings)} 条):")
        for w in warnings:
            print(f"   - [{w.severity}] {w.message[:60]}...")
    
    if summary:
        print(f"\n📝 总结: {summary[:100]}...")
    
    return result


async def test_all_nodes_parallel():
    """并行测试分析节点"""
    print("\n" + "="*60)
    print("测试6: 并行执行分析节点 (terrain + communication + safety)")
    print("="*60)
    
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.nodes.terrain import analyze_terrain
    from src.agents.staging_area.nodes.communication import analyze_communication
    from src.agents.staging_area.nodes.safety import analyze_safety
    from src.agents.staging_area.state import StagingAreaAgentState
    
    state: StagingAreaAgentState = {
        "candidate_sites": MOCK_CANDIDATE_SITES,
        "epicenter_lon": EPICENTER_LON,
        "epicenter_lat": EPICENTER_LAT,
        "magnitude": MAGNITUDE,
        "skip_llm_analysis": False,
        "errors": [],
        "timing": {},
    }
    
    async with AsyncSessionLocal() as db:
        start = time.perf_counter()
        
        # 并行执行
        results = await asyncio.gather(
            analyze_terrain(state, db),
            analyze_communication(state, db),
            analyze_safety(state, db),
            return_exceptions=True,
        )
        
        elapsed = time.perf_counter() - start
    
    print(f"并行执行总耗时: {elapsed*1000:.0f}ms")
    
    terrain_result, comm_result, safety_result = results
    
    success_count = 0
    if isinstance(terrain_result, dict) and terrain_result.get("terrain_assessments"):
        success_count += 1
        print(f"✅ 地形分析: {len(terrain_result['terrain_assessments'])} 个评估")
    else:
        print(f"❌ 地形分析失败: {terrain_result}")
    
    if isinstance(comm_result, dict) and comm_result.get("communication_assessments"):
        success_count += 1
        print(f"✅ 通信分析: {len(comm_result['communication_assessments'])} 个评估")
    else:
        print(f"❌ 通信分析失败: {comm_result}")
    
    if isinstance(safety_result, dict) and safety_result.get("safety_assessments"):
        success_count += 1
        print(f"✅ 安全分析: {len(safety_result['safety_assessments'])} 个评估")
    else:
        print(f"❌ 安全分析失败: {safety_result}")
    
    print(f"\n总计: {success_count}/3 成功")
    
    return results


async def main():
    print("="*60)
    print("驻扎点选址智能体节点功能测试")
    print("测试环境: 四川省（茂县叠溪镇地震场景）")
    print("="*60)
    
    try:
        # 测试各节点
        await test_understand_node()
        await test_terrain_node()
        await test_communication_node()
        await test_safety_node()
        await test_explain_node()
        await test_all_nodes_parallel()
        
        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
