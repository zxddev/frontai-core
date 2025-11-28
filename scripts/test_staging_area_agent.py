#!/usr/bin/env python3
"""
驻扎点选址智能体端到端测试

测试场景：
1. 完整Agent模式（6节点流程）
2. 纯算法模式（skip_llm_analysis=True）
3. 对比两种模式的结果差异

运行方式：
    cd /home/dev/gitcode/frontai/frontai-core
    .venv/bin/python scripts/test_staging_area_agent.py
"""
import asyncio
import logging
import os
import sys
import time
from uuid import UUID, uuid4

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# 测试数据
TEST_SCENARIO_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_TEAM_ID = UUID("22222222-2222-2222-2222-222222222222")

# 茂县叠溪镇震中坐标
EPICENTER_LON = 103.8537
EPICENTER_LAT = 31.6815
MAGNITUDE = 7.0

# 队伍驻地（假设在都江堰）
TEAM_BASE_LON = 103.6177
TEAM_BASE_LAT = 30.9884

# 救援目标（受灾村庄）
RESCUE_TARGETS = [
    {"id": str(uuid4()), "lon": 103.85, "lat": 31.70, "name": "叠溪镇中心", "priority": "critical"},
    {"id": str(uuid4()), "lon": 103.82, "lat": 31.65, "name": "松坪沟村", "priority": "high"},
    {"id": str(uuid4()), "lon": 103.88, "lat": 31.72, "name": "飞虹乡", "priority": "medium"},
]

# 灾情描述
DISASTER_DESCRIPTION = """
茂县叠溪镇发生7.0级地震，震源深度10公里。
地震造成多处建筑倒塌，国道213线多处被滑坡阻断。
目前已确认叠溪镇中心、松坪沟村、飞虹乡等区域有人员被困。
通信基站部分损毁，部分区域失联。
"""


async def test_agent_mode():
    """测试完整Agent模式"""
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.agent import StagingAreaAgent
    
    logger.info("=" * 60)
    logger.info("测试1: 完整Agent模式（6节点流程）")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        agent = StagingAreaAgent(db)
        
        start_time = time.perf_counter()
        result = await agent.recommend(
            scenario_id=TEST_SCENARIO_ID,
            epicenter_lon=EPICENTER_LON,
            epicenter_lat=EPICENTER_LAT,
            magnitude=MAGNITUDE,
            team_id=TEST_TEAM_ID,
            team_base_lon=TEAM_BASE_LON,
            team_base_lat=TEAM_BASE_LAT,
            rescue_targets=RESCUE_TARGETS,
            disaster_description=DISASTER_DESCRIPTION,
            team_name="四川消防救援总队",
            top_n=5,
            skip_llm_analysis=False,  # 启用LLM分析
        )
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    
    _print_result(result, elapsed_ms)
    return result


async def test_algorithm_mode():
    """测试纯算法模式"""
    from src.core.database import AsyncSessionLocal
    from src.agents.staging_area.agent import StagingAreaAgent
    
    logger.info("=" * 60)
    logger.info("测试2: 纯算法模式（skip_llm_analysis=True）")
    logger.info("=" * 60)
    
    async with AsyncSessionLocal() as db:
        agent = StagingAreaAgent(db)
        
        start_time = time.perf_counter()
        result = await agent.recommend(
            scenario_id=TEST_SCENARIO_ID,
            epicenter_lon=EPICENTER_LON,
            epicenter_lat=EPICENTER_LAT,
            magnitude=MAGNITUDE,
            team_id=TEST_TEAM_ID,
            team_base_lon=TEAM_BASE_LON,
            team_base_lat=TEAM_BASE_LAT,
            rescue_targets=RESCUE_TARGETS,
            disaster_description="",  # 无灾情描述
            team_name="四川消防救援总队",
            top_n=5,
            skip_llm_analysis=True,  # 跳过LLM分析
        )
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    
    _print_result(result, elapsed_ms)
    return result


def _print_result(result: dict, elapsed_ms: int):
    """打印测试结果"""
    logger.info(f"处理模式: {result.get('processing_mode', 'unknown')}")
    logger.info(f"总耗时: {elapsed_ms}ms")
    logger.info(f"成功: {result.get('success', False)}")
    
    if result.get("errors"):
        logger.warning(f"错误: {result['errors']}")
    
    recommended_sites = result.get("recommended_sites", [])
    logger.info(f"推荐数量: {len(recommended_sites)}")
    
    for i, site in enumerate(recommended_sites[:3], 1):
        logger.info(f"  [{i}] {site.get('name', '未知')} - 总分: {site.get('total_score', 0):.3f}")
        scores = site.get("scores", {})
        logger.info(f"      响应时间: {scores.get('response_time', 0):.3f}, 安全: {scores.get('safety', 0):.3f}")
    
    site_explanations = result.get("site_explanations", [])
    if site_explanations:
        logger.info(f"解释数量: {len(site_explanations)}")
        for exp in site_explanations[:2]:
            if isinstance(exp, dict):
                logger.info(f"  - {exp.get('site_name', '未知')}: {exp.get('recommendation_reason', '')[:50]}...")
    
    risk_warnings = result.get("risk_warnings", [])
    if risk_warnings:
        logger.info(f"风险警示: {len(risk_warnings)}")
        for warn in risk_warnings[:2]:
            if isinstance(warn, dict):
                logger.info(f"  - [{warn.get('severity', 'unknown')}] {warn.get('message', '')[:50]}...")
    
    timing = result.get("timing", {})
    if timing:
        logger.info(f"各阶段耗时: {timing}")


async def compare_results():
    """对比Agent模式和纯算法模式的结果"""
    logger.info("=" * 60)
    logger.info("对比分析: Agent模式 vs 纯算法模式")
    logger.info("=" * 60)
    
    agent_result = await test_agent_mode()
    algo_result = await test_algorithm_mode()
    
    logger.info("\n" + "=" * 60)
    logger.info("对比总结")
    logger.info("=" * 60)
    
    agent_sites = agent_result.get("recommended_sites", [])
    algo_sites = algo_result.get("recommended_sites", [])
    
    if agent_sites and algo_sites:
        agent_top = agent_sites[0].get("name", "")
        algo_top = algo_sites[0].get("name", "")
        
        if agent_top == algo_top:
            logger.info(f"首选推荐一致: {agent_top}")
        else:
            logger.info(f"首选推荐不同:")
            logger.info(f"  Agent模式: {agent_top}")
            logger.info(f"  算法模式: {algo_top}")
        
        # 比较排名变化
        agent_names = [s.get("name") for s in agent_sites]
        algo_names = [s.get("name") for s in algo_sites]
        
        rank_changes = []
        for i, name in enumerate(agent_names):
            if name in algo_names:
                algo_rank = algo_names.index(name)
                if i != algo_rank:
                    rank_changes.append(f"{name}: Agent#{i+1} vs Algo#{algo_rank+1}")
        
        if rank_changes:
            logger.info("排名变化:")
            for change in rank_changes:
                logger.info(f"  - {change}")
    
    # 比较解释质量
    agent_explanations = len(agent_result.get("site_explanations", []))
    algo_explanations = len(algo_result.get("site_explanations", []))
    logger.info(f"解释数量: Agent={agent_explanations}, 算法={algo_explanations}")
    
    # 比较风险警示
    agent_warnings = len(agent_result.get("risk_warnings", []))
    algo_warnings = len(algo_result.get("risk_warnings", []))
    logger.info(f"风险警示: Agent={agent_warnings}, 算法={algo_warnings}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="驻扎点选址智能体测试")
    parser.add_argument("--mode", choices=["agent", "algo", "compare"], default="compare",
                        help="测试模式: agent=完整Agent, algo=纯算法, compare=对比测试")
    args = parser.parse_args()
    
    try:
        if args.mode == "agent":
            await test_agent_mode()
        elif args.mode == "algo":
            await test_algorithm_mode()
        else:
            await compare_results()
        
        logger.info("\n测试完成!")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
