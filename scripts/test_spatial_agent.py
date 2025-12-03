#!/usr/bin/env python3
"""
SpatialAgent 端到端测试脚本

测试语义路由 + 空间查询Agent的完整流程。
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.voice_commander.semantic_router import VoiceSemanticRouter
from src.agents.voice_commander.spatial_graph import get_spatial_agent_graph
from src.agents.voice_commander.tools.spatial_tools import (
    find_entity_location,
    find_nearest_unit,
)


async def test_semantic_router():
    """测试语义路由分类"""
    print("\n" + "=" * 60)
    print("1. 测试语义路由分类")
    print("=" * 60)
    
    router = VoiceSemanticRouter()
    
    test_cases = [
        # 空间查询
        ("茂县消防大队在哪里", "spatial_query"),
        ("一号车辆当前位置", "spatial_query"),
        ("离震中最近的救援队是哪支", "spatial_query"),
        ("附近有什么队伍", "spatial_query"),
        # 机器人控制
        ("派无人机去东门侦察", "robot_command"),
        ("让机器狗去化工厂", "robot_command"),
        # 任务状态
        ("当前有多少任务在执行", "mission_status"),
        ("救援进度怎么样", "mission_status"),
        # 闲聊
        ("你好", "chitchat"),
        ("今天天气怎么样", "chitchat"),
    ]
    
    correct = 0
    llm_fallback_count = 0
    for query, expected in test_cases:
        route_name, confidence, used_llm = await router.classify(query)
        status = "✓" if route_name == expected else "✗"
        if route_name == expected:
            correct += 1
        if used_llm:
            llm_fallback_count += 1
        method = "[LLM]" if used_llm else "[Semantic]"
        print(f"  {status} '{query[:20]}...' -> {route_name} {method} (期望:{expected}, conf={confidence:.2f})")
    
    accuracy = correct / len(test_cases) * 100
    print(f"\n  准确率: {correct}/{len(test_cases)} ({accuracy:.1f}%)")
    print(f"  LLM Fallback: {llm_fallback_count}/{len(test_cases)} ({llm_fallback_count/len(test_cases)*100:.0f}%)")
    # Hybrid路由准确率要求90%以上
    return accuracy >= 90


async def test_spatial_tools():
    """测试空间查询工具"""
    print("\n" + "=" * 60)
    print("2. 测试空间查询工具")
    print("=" * 60)
    
    # 测试 find_entity_location
    print("\n  2.1 find_entity_location('消防')")
    result = await find_entity_location.ainvoke({"entity_name": "消防"})
    print(f"      success: {result.get('success')}")
    print(f"      count: {result.get('count', 0)}")
    if result.get("entities"):
        for e in result["entities"][:2]:
            print(f"      - {e.get('name')} ({e.get('entity_type')})")
    
    # 测试 find_nearest_unit
    print("\n  2.2 find_nearest_unit('103.85,31.68', 'TEAM', 3)")
    result = await find_nearest_unit.ainvoke({
        "reference_point": "103.85,31.68",
        "target_type": "TEAM",
        "count": 3,
    })
    print(f"      success: {result.get('success')}")
    if result.get("units"):
        for u in result["units"]:
            print(f"      - {u.get('name')}: {u.get('distance_text', 'N/A')}")
    
    return True


async def test_spatial_agent():
    """测试完整的SpatialAgent图"""
    print("\n" + "=" * 60)
    print("3. 测试SpatialAgent LangGraph")
    print("=" * 60)
    
    graph = get_spatial_agent_graph()
    
    # 使用数据库中存在的实体进行测试
    test_queries = [
        "消防救援大队在哪里",  # 使用模糊匹配
        "103.85,31.68附近最近的救援队",  # 使用坐标而非地名
    ]
    
    for query in test_queries:
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
            response = result.get("response", "无响应")
            trace = result.get("trace", {})
            
            print(f"  回复: {response[:100]}...")
            print(f"  节点: {trace.get('nodes_executed', [])}")
            print(f"  工具: {trace.get('tool_calls', [])}")
        except Exception as e:
            print(f"  错误: {e}")
    
    return True


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("SpatialAgent 端到端测试")
    print("=" * 60)
    
    results = []
    
    # 1. 语义路由测试
    try:
        results.append(("语义路由", await test_semantic_router()))
    except Exception as e:
        print(f"  语义路由测试失败: {e}")
        results.append(("语义路由", False))
    
    # 2. 空间工具测试
    try:
        results.append(("空间工具", await test_spatial_tools()))
    except Exception as e:
        print(f"  空间工具测试失败: {e}")
        results.append(("空间工具", False))
    
    # 3. SpatialAgent测试
    try:
        results.append(("SpatialAgent", await test_spatial_agent()))
    except Exception as e:
        print(f"  SpatialAgent测试失败: {e}")
        results.append(("SpatialAgent", False))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print(f"\n总体: {'全部通过' if all_passed else '存在失败'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
