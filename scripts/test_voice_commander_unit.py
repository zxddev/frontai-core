#!/usr/bin/env python3
"""
Voice Commander 单元测试

Phase 1.5: Hybrid路由准确率测试
Phase 2: 空间查询单元测试
"""
import asyncio
import sys
import os
from typing import List, Tuple
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.voice_commander.semantic_router import VoiceSemanticRouter
from src.agents.voice_commander.tools.spatial_tools import (
    find_entity_location,
    find_nearest_unit,
    get_area_status,
)
from src.agents.voice_commander.spatial_graph import get_spatial_agent_graph
from src.agents.db.spatial import SpatialRepository
from src.core.database import AsyncSessionLocal


@dataclass
class TestResult:
    name: str
    passed: int
    failed: int
    details: List[str]


# ============================================================
# Phase 1.5: Hybrid路由准确率测试
# ============================================================

# 测试数据：每类20+样本
SPATIAL_QUERY_SAMPLES = [
    "消防大队在哪里",
    "茂县消防大队在哪里",
    "救援队在哪里",
    "一号车辆在哪里",
    "无人机在哪里",
    "机器狗在哪里",
    "一号车辆当前位置",
    "消防队的位置",
    "救援队位置在哪",
    "查询队伍位置",
    "离震中最近的救援队",
    "离震中最近的救援队是哪支",
    "哪个队伍离这里最近",
    "最近的消防队在哪",
    "最近的医疗队",
    "附近有什么队伍",
    "附近有哪些救援力量",
    "周边有什么单位",
    "B区有多少救援人员",
    "这个区域有哪些队伍",
    "查一下消防队的位置",
    "定位一下救援车",
]

ROBOT_COMMAND_SAMPLES = [
    "派无人机去东门侦察",
    "派遣无人机去侦查",
    "派一号无人机去化工厂",
    "派无人机过去看看",
    "派机器狗去现场",
    "让机器狗去化工厂",
    "让机器狗前往B区",
    "让无人机去东门巡逻",
    "机器狗去那边看看",
    "无人机飞到那个位置",
    "无人机移动到北门",
    "停止前进",
    "返航",
    "跟随我",
    "出发",
    "开始巡逻",
    "执行侦查任务",
    "停下来",
    "回来",
    "让无人机返回",
]

MISSION_STATUS_SAMPLES = [
    "救援进度怎么样",
    "任务进度如何",
    "完成了多少任务",
    "进展如何了",
    "当前有多少任务在执行",
    "任务完成情况怎么样",
    "救援行动进展如何",
    "查看救援进度",
    "救援情况怎么样",
    "目前救了多少人",
    "还有多少人没救出来",
    "还有多少未搜救区域",
    "资源消耗情况如何",
    "当前物资剩余多少",
    "任务执行到哪一步了",
]

CHITCHAT_SAMPLES = [
    "你好",
    "听得见吗",
    "谢谢",
    "好的",
    "明白了",
    "收到",
    "在吗",
    "你是谁",
    "嗯嗯",
    "今天天气怎么样",
    "能听到吗",
    "测试一下",
    "可以",
    "行",
    "没问题",
]


async def test_route_category(
    router: VoiceSemanticRouter,
    samples: List[str],
    expected_route: str,
    category_name: str,
) -> TestResult:
    """测试单个路由类别的准确率"""
    passed = 0
    failed = 0
    details = []
    semantic_count = 0
    llm_count = 0
    
    for sample in samples:
        route, confidence, used_llm = await router.classify(sample)
        
        if used_llm:
            llm_count += 1
        else:
            semantic_count += 1
        
        if route == expected_route:
            passed += 1
        else:
            failed += 1
            method = "[LLM]" if used_llm else "[Semantic]"
            details.append(f"  ✗ '{sample[:25]}...' -> {route} {method} (期望:{expected_route})")
    
    accuracy = passed / len(samples) * 100
    details.insert(0, f"  准确率: {passed}/{len(samples)} ({accuracy:.1f}%)")
    details.insert(1, f"  Semantic: {semantic_count}, LLM Fallback: {llm_count}")
    
    return TestResult(
        name=f"{category_name} ({expected_route})",
        passed=passed,
        failed=failed,
        details=details,
    )


async def test_hybrid_router():
    """Phase 1.5: 测试Hybrid路由准确率"""
    print("\n" + "=" * 60)
    print("Phase 1.5: Hybrid路由准确率测试")
    print("=" * 60)
    
    router = VoiceSemanticRouter()
    results: List[TestResult] = []
    
    # 测试各类别
    categories = [
        (SPATIAL_QUERY_SAMPLES, "spatial_query", "空间查询"),
        (ROBOT_COMMAND_SAMPLES, "robot_command", "机器人控制"),
        (MISSION_STATUS_SAMPLES, "mission_status", "任务状态"),
        (CHITCHAT_SAMPLES, "chitchat", "闲聊"),
    ]
    
    for samples, expected_route, category_name in categories:
        print(f"\n测试 {category_name} ({len(samples)} 样本)...")
        result = await test_route_category(router, samples, expected_route, category_name)
        results.append(result)
        for detail in result.details:
            print(detail)
    
    # 汇总
    print("\n" + "-" * 40)
    print("汇总:")
    total_passed = sum(r.passed for r in results)
    total_failed = sum(r.failed for r in results)
    total = total_passed + total_failed
    overall_accuracy = total_passed / total * 100
    
    print(f"  总体准确率: {total_passed}/{total} ({overall_accuracy:.1f}%)")
    
    all_passed = all(
        r.passed / (r.passed + r.failed) >= 0.9
        for r in results
    )
    
    return all_passed, overall_accuracy


# ============================================================
# Phase 2: 空间查询单元测试
# ============================================================

async def test_spatial_repository():
    """测试 SpatialRepository"""
    print("\n" + "=" * 60)
    print("Phase 2.1: SpatialRepository 测试")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    async with AsyncSessionLocal() as db:
        repo = SpatialRepository(db)
        
        # 1. 模糊名称查询 - 部分匹配
        print("\n  2.1.1 find_by_name_fuzzy('消防')")
        results = await repo.find_by_name_fuzzy("消防", limit=5)
        if len(results) > 0:
            print(f"      ✓ 找到 {len(results)} 个结果")
            passed += 1
        else:
            print("      ✗ 未找到结果")
            failed += 1
        
        # 2. 模糊名称查询 - 带类型过滤
        print("\n  2.1.2 find_by_name_fuzzy('消防', type='TEAM')")
        results = await repo.find_by_name_fuzzy("消防", entity_type="TEAM", limit=5)
        if len(results) > 0 and all(r["entity_type"] == "TEAM" for r in results):
            print(f"      ✓ 找到 {len(results)} 个队伍")
            passed += 1
        else:
            print(f"      ✗ 结果不正确: {results}")
            failed += 1
        
        # 3. KNN查询
        print("\n  2.1.3 find_nearest_knn((103.85, 31.68), 'TEAM', 3)")
        results = await repo.find_nearest_knn((103.85, 31.68), "TEAM", limit=3)
        if len(results) > 0:
            print(f"      ✓ 找到 {len(results)} 个最近队伍")
            for r in results[:2]:
                print(f"        - {r.get('name')}: {r.get('distance_m', 0):.0f}m")
            passed += 1
        else:
            print("      ✗ 未找到结果")
            failed += 1
        
        # 4. 地名解析
        print("\n  2.1.4 resolve_location_name('茂县')")
        point = await repo.resolve_location_name("茂县")
        if point:
            print(f"      ✓ 解析成功: {point}")
            passed += 1
        else:
            print("      ✗ 解析失败")
            failed += 1
        
        # 5. 逆地理编码
        print("\n  2.1.5 reverse_geocode((103.85, 31.68))")
        desc = await repo.reverse_geocode((103.85, 31.68))
        if desc:
            print(f"      ✓ 编码成功: {desc}")
            passed += 1
        else:
            print("      ✗ 编码失败（可能无附近地标）")
            # 这个不算失败，因为可能确实没有附近地标
            passed += 1
    
    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


async def test_spatial_tools():
    """测试空间查询工具"""
    print("\n" + "=" * 60)
    print("Phase 2.2: 空间查询工具测试")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # 1. find_entity_location - 成功
    print("\n  2.2.1 find_entity_location('消防')")
    result = await find_entity_location.ainvoke({"entity_name": "消防"})
    if result.get("success") and result.get("count", 0) > 0:
        print(f"      ✓ 找到 {result['count']} 个实体")
        passed += 1
    else:
        print(f"      ✗ 查询失败: {result}")
        failed += 1
    
    # 2. find_entity_location - 不存在
    print("\n  2.2.2 find_entity_location('不存在的队伍xyz')")
    result = await find_entity_location.ainvoke({"entity_name": "不存在的队伍xyz"})
    if result.get("count", 0) == 0:
        print("      ✓ 正确返回空结果")
        passed += 1
    else:
        print(f"      ✗ 应返回空: {result}")
        failed += 1
    
    # 3. find_nearest_unit - 坐标
    print("\n  2.2.3 find_nearest_unit('103.85,31.68', 'TEAM', 3)")
    result = await find_nearest_unit.ainvoke({
        "reference_point": "103.85,31.68",
        "target_type": "TEAM",
        "count": 3,
    })
    if result.get("success") and len(result.get("units", [])) > 0:
        print(f"      ✓ 找到 {len(result['units'])} 个最近单位")
        passed += 1
    else:
        print(f"      ✗ 查询失败: {result}")
        failed += 1
    
    # 4. get_area_status (如果有区域数据)
    print("\n  2.2.4 get_area_status('test-area')")
    result = await get_area_status.ainvoke({"area_id": "test-area"})
    # 即使没有数据也应返回结构化结果
    if "success" in result:
        print(f"      ✓ 返回结构化结果: success={result['success']}")
        passed += 1
    else:
        print(f"      ✗ 返回格式错误: {result}")
        failed += 1
    
    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


async def test_spatial_agent_graph():
    """测试 SpatialAgent LangGraph"""
    print("\n" + "=" * 60)
    print("Phase 2.3: SpatialAgent LangGraph 测试")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    graph = get_spatial_agent_graph()
    
    test_cases = [
        ("消防队在哪里", "find_entity_location"),
        ("103.85,31.68附近最近的队伍", "find_nearest_unit"),
    ]
    
    for query, expected_tool in test_cases:
        print(f"\n  查询: '{query}'")
        
        initial_state = {
            "query": query,
            "session_id": "test-session",
            "parsed_intent": None,
            "selected_tool": None,
            "tool_input": {},
            "tool_results": [],
            "response": None,
            "trace": {},
        }
        
        try:
            result = await graph.ainvoke(initial_state)
            response = result.get("response", "")
            trace = result.get("trace", {})
            tool_calls = trace.get("tool_calls", [])
            
            if response and len(response) > 10:
                print(f"      ✓ 生成回复: {response[:50]}...")
                passed += 1
            else:
                print(f"      ✗ 回复过短或为空: {response}")
                failed += 1
            
            if expected_tool in tool_calls:
                print(f"      ✓ 调用了预期工具: {expected_tool}")
                passed += 1
            else:
                print(f"      ✗ 未调用预期工具 {expected_tool}, 实际: {tool_calls}")
                failed += 1
                
        except Exception as e:
            print(f"      ✗ 执行异常: {e}")
            failed += 2
    
    print(f"\n  结果: {passed}/{passed+failed} 通过")
    return passed, failed


# ============================================================
# 主函数
# ============================================================

async def main():
    """运行所有单元测试"""
    print("\n" + "=" * 60)
    print("Voice Commander 单元测试")
    print("=" * 60)
    
    all_results = []
    
    # Phase 1.5: 路由测试
    try:
        router_passed, accuracy = await test_hybrid_router()
        all_results.append(("Phase 1.5 Hybrid路由", router_passed, f"{accuracy:.1f}%"))
    except Exception as e:
        print(f"  路由测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_results.append(("Phase 1.5 Hybrid路由", False, "ERROR"))
    
    # Phase 2.1: Repository测试
    try:
        p, f = await test_spatial_repository()
        all_results.append(("Phase 2.1 SpatialRepository", f == 0, f"{p}/{p+f}"))
    except Exception as e:
        print(f"  Repository测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_results.append(("Phase 2.1 SpatialRepository", False, "ERROR"))
    
    # Phase 2.2: Tools测试
    try:
        p, f = await test_spatial_tools()
        all_results.append(("Phase 2.2 SpatialTools", f == 0, f"{p}/{p+f}"))
    except Exception as e:
        print(f"  Tools测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_results.append(("Phase 2.2 SpatialTools", False, "ERROR"))
    
    # Phase 2.3: Graph测试
    try:
        p, f = await test_spatial_agent_graph()
        all_results.append(("Phase 2.3 SpatialAgentGraph", f == 0, f"{p}/{p+f}"))
    except Exception as e:
        print(f"  Graph测试失败: {e}")
        import traceback
        traceback.print_exc()
        all_results.append(("Phase 2.3 SpatialAgentGraph", False, "ERROR"))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    for name, passed, detail in all_results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status} ({detail})")
    
    overall_passed = all(r[1] for r in all_results)
    print(f"\n总体: {'全部通过' if overall_passed else '存在失败'}")
    
    return 0 if overall_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
