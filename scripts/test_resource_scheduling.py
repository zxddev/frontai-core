#!/usr/bin/env python3
"""
资源调度模块测试脚本

测试内容:
1. 物资需求计算 (同步方法，无需数据库)
2. 装备需求推断 (数据模型)
3. 整合调度 (需要数据库连接)
"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.domains.resource_scheduling import (
    SupplyDemandCalculator,
    EquipmentScheduler,
    IntegratedResourceSchedulingCore,
    DisasterContext,
    IntegratedSchedulingRequest,
    EquipmentType,
    EquipmentPriority,
    EquipmentRequirement,
)


def test_supply_demand_calculation():
    """测试物资需求计算"""
    print("=" * 60)
    print("测试1: 物资需求计算 (同步方法)")
    print("=" * 60)
    
    calculator = SupplyDemandCalculator(db=None)
    
    # 测试不同灾害类型
    disasters = [
        ("earthquake", 1000, 3, 50),
        ("flood", 500, 5, 20),
        ("fire", 200, 1, 10),
        ("hazmat", 100, 2, 5),
    ]
    
    for disaster_type, affected, days, trapped in disasters:
        print(f"\n{disaster_type.upper()} - 受灾{affected}人, 被困{trapped}人, {days}天:")
        requirements = calculator.calculate_sync(
            disaster_type=disaster_type,
            affected_count=affected,
            duration_days=days,
            trapped_count=trapped,
        )
        for req in requirements:
            print(f"  - {req.supply_name}: {req.quantity} {req.unit} [{req.priority}]")
    
    print("\n物资需求计算测试通过!")
    return True


def test_equipment_schemas():
    """测试装备数据模型"""
    print("\n" + "=" * 60)
    print("测试2: 装备数据模型")
    print("=" * 60)
    
    # 测试装备需求模型
    req = EquipmentRequirement(
        capability_code="LIFE_DETECTION",
        equipment_type=EquipmentType.SUPPLY,
        equipment_code="SP-RESCUE-DETECTOR",
        equipment_name="雷达生命探测仪",
        min_quantity=2,
        priority=EquipmentPriority.REQUIRED,
    )
    print(f"\n装备需求: {req.equipment_name}")
    print(f"  - 能力编码: {req.capability_code}")
    print(f"  - 类型: {req.equipment_type.value}")
    print(f"  - 最少数量: {req.min_quantity}")
    print(f"  - 优先级: {req.priority.value}")
    
    print("\n装备数据模型测试通过!")
    return True


def test_disaster_context():
    """测试灾情上下文"""
    print("\n" + "=" * 60)
    print("测试3: 灾情上下文模型")
    print("=" * 60)
    
    context = DisasterContext(
        disaster_type="earthquake",
        center_lon=103.88,
        center_lat=30.79,
        affected_population=5000,
        trapped_count=200,
        injured_count=50,
        estimated_duration_days=7,
    )
    
    print(f"\n灾情: {context.disaster_type}")
    print(f"  - 位置: ({context.center_lon}, {context.center_lat})")
    print(f"  - 受灾人数: {context.affected_population}")
    print(f"  - 被困人数: {context.trapped_count}")
    print(f"  - 伤员人数: {context.injured_count}")
    print(f"  - 预计持续: {context.estimated_duration_days}天")
    
    print("\n灾情上下文测试通过!")
    return True


async def test_integrated_scheduling_mock():
    """测试整合调度 (模拟，不连接数据库)"""
    print("\n" + "=" * 60)
    print("测试4: 整合调度请求构建")
    print("=" * 60)
    
    context = DisasterContext(
        disaster_type="earthquake",
        center_lon=103.88,
        center_lat=30.79,
        affected_population=2000,
        trapped_count=100,
    )
    
    request = IntegratedSchedulingRequest(
        context=context,
        include_team_scheduling=True,
        include_equipment_scheduling=True,
        include_supply_calculation=True,
    )
    
    print(f"\n整合调度请求:")
    print(f"  - 灾害类型: {request.context.disaster_type}")
    print(f"  - 队伍调度: {request.include_team_scheduling}")
    print(f"  - 装备调度: {request.include_equipment_scheduling}")
    print(f"  - 物资计算: {request.include_supply_calculation}")
    
    # 测试能力需求推断（不连接数据库）
    from src.domains.resource_scheduling.integrated_core import IntegratedResourceSchedulingCore
    
    # 使用静态方法测试能力推断
    class MockDB:
        pass
    
    core = IntegratedResourceSchedulingCore.__new__(IntegratedResourceSchedulingCore)
    requirements = core._infer_capability_requirements(context)
    
    print(f"\n推断的能力需求:")
    for req in requirements:
        print(f"  - {req.capability_code}: 最少{req.min_count}个, 优先级{req.priority}")
    
    print("\n整合调度请求构建测试通过!")
    return True


def main():
    """运行所有测试"""
    print("资源调度模块测试")
    print("=" * 60)
    
    results = []
    
    # 运行同步测试
    results.append(("物资需求计算", test_supply_demand_calculation()))
    results.append(("装备数据模型", test_equipment_schemas()))
    results.append(("灾情上下文", test_disaster_context()))
    
    # 运行异步测试
    results.append(("整合调度请求", asyncio.run(test_integrated_scheduling_mock())))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + ("所有测试通过!" if all_passed else "存在失败的测试"))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
