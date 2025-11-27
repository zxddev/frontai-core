#!/usr/bin/env python3
"""
任务智能分发智能体测试脚本

测试两种模式：
- Mode 1: 初始分配
- Mode 2: 动态调整

注意：此测试使用数据库真实数据，需要确保数据库中有rescue_teams_v2记录
"""
import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.task_dispatch import (
    TaskDispatchAgent,
    get_task_dispatch_agent,
    DispatchEventType,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# 测试数据（使用数据库中真实的team_id）
# ============================================================================

# 模拟的方案任务（来自HTN分解）
MOCK_SCHEME_TASKS = [
    {
        "task_id": "EM06",
        "task_name": "埋压人员生命探测",
        "phase": "detect",
        "priority": "critical",
        "sequence": 1,
        "depends_on": [],
        "required_capabilities": ["life_detection", "acoustic_detection"],
        "duration_min": 45,
        "golden_hour": 72,
    },
    {
        "task_id": "EM10",
        "task_name": "被困人员救援",
        "phase": "execute",
        "priority": "critical",
        "sequence": 2,
        "depends_on": ["EM06"],
        "required_capabilities": ["rescue_operation", "heavy_equipment"],
        "duration_min": 120,
        "golden_hour": 72,
    },
    {
        "task_id": "EM14",
        "task_name": "伤员现场急救",
        "phase": "execute",
        "priority": "high",
        "sequence": 3,
        "depends_on": ["EM10"],
        "required_capabilities": ["emergency_medical", "triage"],
        "duration_min": 30,
    },
    {
        "task_id": "EM16",
        "task_name": "交通管制与道路抢通",
        "phase": "execute",
        "priority": "medium",
        "sequence": 4,
        "depends_on": [],
        "required_capabilities": ["traffic_control", "debris_clearance"],
        "duration_min": 60,
    },
]

# 使用数据库中真实的team_id
MOCK_ALLOCATED_TEAMS = [
    {
        "team_id": "72c767de-379d-421a-bbf5-7fb01abd7cc7",  # 茂县消防救援大队
        "team_name": "茂县消防救援大队",
        "type": "fire_rescue",
        "capabilities": ["fire_rescue", "search_rescue", "life_detection"],
        "personnel_count": 45,
        "eta_minutes": 15,
    },
    {
        "team_id": "ebef8b45-ee92-4d11-8ff1-c1ee2d7a2ab9",  # 茂县人民医院急救队
        "team_name": "茂县人民医院急救队",
        "type": "medical",
        "capabilities": ["emergency_medical", "triage", "medical_transport"],
        "personnel_count": 20,
        "eta_minutes": 20,
    },
    {
        "team_id": "f5876717-1a25-4c44-a220-16ec1c7ebde5",  # 成都特勤消防救援站
        "team_name": "成都特勤消防救援站",
        "type": "fire_rescue",
        "capabilities": ["heavy_equipment", "rescue_operation", "hazmat"],
        "personnel_count": 60,
        "eta_minutes": 45,
    },
]


# ============================================================================
# 测试函数
# ============================================================================

async def test_initial_dispatch():
    """测试Mode 1: 初始分配"""
    print("\n" + "=" * 60)
    print("测试 Mode 1: 初始分配")
    print("=" * 60)
    
    agent = get_task_dispatch_agent(use_checkpointer=False)
    
    result = await agent.initial_dispatch(
        event_id="evt-test-001",
        scheme_id="sch-test-001",
        scheme_tasks=MOCK_SCHEME_TASKS,
        allocated_teams=MOCK_ALLOCATED_TEAMS,
    )
    
    print(f"\n执行结果:")
    print(f"  成功: {result['success']}")
    print(f"  分配数: {len(result['assignments'])}")
    print(f"  调度指令数: {len(result['dispatch_orders'])}")
    print(f"  执行耗时: {result['execution_time_ms']}ms")
    
    if result['errors']:
        print(f"  错误: {result['errors']}")
    
    print(f"\n执行阶段: {result['trace'].get('phases_executed', [])}")
    print(f"使用算法: {result['trace'].get('algorithms_used', [])}")
    
    print("\n任务分配详情:")
    for assignment in result['assignments']:
        print(f"  - {assignment['task_name']} -> {assignment['executor_name']}")
        print(f"    优先级: {assignment['task_priority']}, 状态: {assignment['status']}")
        print(f"    计划时间: {assignment.get('scheduled_start')} - {assignment.get('scheduled_end')}")
    
    print("\n调度指令:")
    for order in result['dispatch_orders'][:3]:  # 只显示前3个
        print(f"  - [{order['priority']}] {order['task_name']}")
        print(f"    执行者: {order['executor_name']}")
        print(f"    指令: {order['instructions'][:100]}...")
    
    return result['success']


async def test_dynamic_adjustment():
    """测试Mode 2: 动态调整（需要启用checkpointer支持human-in-the-loop）"""
    print("\n" + "=" * 60)
    print("测试 Mode 2: 动态调整（任务拒绝场景）")
    print("=" * 60)
    
    # Mode 2需要checkpointer来支持interrupt
    agent = get_task_dispatch_agent(use_checkpointer=True)
    
    # 模拟当前分配状态（使用真实的team_id）
    current_assignments = [
        {
            "assignment_id": "assign-001",
            "task_id": "EM06",
            "task_name": "埋压人员生命探测",
            "task_priority": "critical",
            "executor_id": "72c767de-379d-421a-bbf5-7fb01abd7cc7",  # 茂县消防救援大队
            "executor_name": "茂县消防救援大队",
            "executor_type": "team",
            "status": "assigned",
            "scheduled_start": "T+15min",
            "scheduled_end": "T+60min",
            "instructions": "执行生命探测任务",
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00",
        },
    ]
    
    # 模拟任务被拒绝事件
    result = await agent.handle_event(
        event_id="evt-test-001",
        event_type=DispatchEventType.TASK_REJECTED.value,
        task_id="EM06",
        executor_id="72c767de-379d-421a-bbf5-7fb01abd7cc7",  # 茂县消防救援大队
        reason="设备故障，生命探测仪需要维修",
        details={"equipment": "life_detector", "repair_time_hours": 4},
        current_assignments=current_assignments,
    )
    
    print(f"\n执行结果:")
    print(f"  成功: {result['success']}")
    print(f"  采取行动: {result['action_taken']}")
    print(f"  需要人工确认: {result['requires_human_approval']}")
    print(f"  执行耗时: {result['execution_time_ms']}ms")
    
    if result['errors']:
        print(f"  错误: {result['errors']}")
    
    print(f"\n执行阶段: {result['trace'].get('phases_executed', [])}")
    
    if result['trace'].get('event_analysis'):
        analysis = result['trace']['event_analysis']
        print(f"\n事件分析:")
        print(f"  摘要: {analysis.get('event_summary', 'N/A')}")
        print(f"  影响级别: {analysis.get('impact_level', 'N/A')}")
        print(f"  紧急程度: {analysis.get('urgency', 'N/A')}")
        print(f"  建议行动: {analysis.get('recommended_action_type', 'N/A')}")
    
    if result.get('action_details'):
        action = result['action_details']
        print(f"\n决策详情:")
        print(f"  行动类型: {action.get('action_type')}")
        print(f"  置信度: {action.get('confidence')}")
        print(f"  理由: {action.get('reasoning')}")
    
    return result['success']


async def test_graph_structure():
    """测试图结构"""
    print("\n" + "=" * 60)
    print("测试 LangGraph 图结构")
    print("=" * 60)
    
    from src.agents.task_dispatch.graph import build_task_dispatch_graph
    
    graph = build_task_dispatch_graph()
    
    print(f"\n节点数: {len(graph.nodes)}")
    print("节点列表:")
    for node_name in graph.nodes.keys():
        print(f"  - {node_name}")
    
    print("\n边 (edges):")
    for edge in graph.edges:
        print(f"  {edge}")
    
    return True


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("任务智能分发智能体 (TaskDispatchAgent) 测试")
    print("=" * 60)
    
    results = []
    
    # 测试1: 图结构
    try:
        results.append(("图结构测试", await test_graph_structure()))
    except Exception as e:
        logger.exception(f"图结构测试失败: {e}")
        results.append(("图结构测试", False))
    
    # 测试2: 初始分配
    try:
        results.append(("初始分配测试", await test_initial_dispatch()))
    except Exception as e:
        logger.exception(f"初始分配测试失败: {e}")
        results.append(("初始分配测试", False))
    
    # 测试3: 动态调整（需要LLM，可能失败）
    try:
        results.append(("动态调整测试", await test_dynamic_adjustment()))
    except Exception as e:
        logger.warning(f"动态调整测试失败（可能是LLM未配置）: {e}")
        results.append(("动态调整测试", False))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, success in results:
        status = "✓ 通过" if success else "✗ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print(f"\n总体结果: {'全部通过' if all_passed else '部分失败'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
