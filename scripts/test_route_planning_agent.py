#!/usr/bin/env python3
"""
路径规划智能体测试脚本

测试内容：
1. 模块导入测试
2. 状态创建测试
3. 图构建测试
4. 单车规划测试（无LLM，使用默认配置）
5. 完整流程测试（需要LLM服务）
"""
import asyncio
import logging
import sys
import os

# 设置项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_import():
    """测试模块导入"""
    print("\n" + "="*60)
    print("测试1: 模块导入")
    print("="*60)
    
    try:
        from src.agents.route_planning import (
            invoke,
            RoutePlanningState,
            Point,
            VehicleInfo,
            TaskPoint,
            create_initial_state,
            get_route_planning_graph,
        )
        print("[PASS] 模块导入成功")
        print(f"  - invoke: {invoke}")
        print(f"  - RoutePlanningState: {RoutePlanningState}")
        print(f"  - get_route_planning_graph: {get_route_planning_graph}")
        return True
    except Exception as e:
        print(f"[FAIL] 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_creation():
    """测试状态创建"""
    print("\n" + "="*60)
    print("测试2: 状态创建")
    print("="*60)
    
    try:
        from src.agents.route_planning.state import create_initial_state, Point
        
        state = create_initial_state(
            request_id="test-001",
            request_type="single",
            start=Point(lon=104.06, lat=30.67),
            end=Point(lon=104.12, lat=30.72),
            vehicle_id="vehicle-001",
            disaster_context={
                "disaster_type": "earthquake",
                "severity": "high",
                "urgency_level": "critical",
            },
        )
        
        print("[PASS] 状态创建成功")
        print(f"  - request_id: {state['request_id']}")
        print(f"  - request_type: {state['request_type']}")
        print(f"  - start: {state['start']}")
        print(f"  - end: {state['end']}")
        print(f"  - current_phase: {state['current_phase']}")
        print(f"  - replan_count: {state['replan_count']}")
        print(f"  - disaster_context: {state['disaster_context']}")
        return True
    except Exception as e:
        print(f"[FAIL] 状态创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_build():
    """测试图构建"""
    print("\n" + "="*60)
    print("测试3: LangGraph图构建")
    print("="*60)
    
    try:
        from src.agents.route_planning.graph import build_route_planning_graph, get_route_planning_graph
        
        # 构建图
        graph = build_route_planning_graph()
        print(f"[PASS] 图构建成功")
        print(f"  - 节点数: {len(graph.nodes)}")
        print(f"  - 节点列表: {list(graph.nodes.keys())}")
        
        # 编译图
        compiled = get_route_planning_graph()
        print(f"[PASS] 图编译成功")
        print(f"  - 类型: {type(compiled)}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 图构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_single_route_no_llm():
    """测试单车规划（无LLM，使用默认配置）"""
    print("\n" + "="*60)
    print("测试4: 单车规划（无LLM）")
    print("="*60)
    
    try:
        from src.agents.route_planning.state import create_initial_state, Point
        from src.agents.route_planning.nodes.routing import compute_route
        
        # 创建最小状态
        state = create_initial_state(
            request_id="test-routing-001",
            request_type="single",
            start=Point(lon=104.06, lat=30.67),
            end=Point(lon=104.12, lat=30.72),
            vehicle_id="vehicle-001",
        )
        
        # 设置策略（跳过LLM节点）
        state["strategy_selection"] = {
            "primary_strategy": "balanced",
            "optimization_weights": {"time": 0.4, "safety": 0.3, "distance": 0.2, "fuel": 0.1},
            "algorithm_params": {"search_radius_km": 80.0, "speed_factor": 1.0, "risk_tolerance": 0.5},
            "fallback_strategy": None,
        }
        
        # 执行路径计算（无数据库连接，使用直线距离估算）
        result = await compute_route(state, db=None)
        
        print("[PASS] 路径计算成功")
        route = result.get("route_result")
        if route:
            print(f"  - route_id: {route['route_id']}")
            print(f"  - total_distance_m: {route['total_distance_m']:.2f}")
            print(f"  - total_duration_seconds: {route['total_duration_seconds']:.2f}")
            print(f"  - path_points: {len(route['path_points'])}个点")
            print(f"  - warnings: {route.get('warnings', [])}")
        print(f"  - algorithm_used: {result.get('algorithm_used')}")
        print(f"  - computation_time_ms: {result.get('computation_time_ms')}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 路径计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_flow_with_llm():
    """测试完整流程（需要LLM服务）"""
    print("\n" + "="*60)
    print("测试5: 完整流程（需要LLM服务）")
    print("="*60)
    
    # 检查LLM服务是否可用
    llm_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    print(f"  LLM服务地址: {llm_base_url}")
    
    try:
        from src.agents.route_planning import invoke
        
        result = await invoke(
            request_type="single",
            start={"lon": 104.06, "lat": 30.67},
            end={"lon": 104.12, "lat": 30.72},
            vehicle_id="vehicle-001",
            disaster_context={
                "disaster_type": "earthquake",
                "severity": "high",
                "urgency_level": "critical",
            },
            natural_language_request="紧急救援任务，尽快到达现场",
        )
        
        print("[PASS] 完整流程执行成功")
        print(f"  - request_id: {result.get('request_id')}")
        print(f"  - success: {result.get('success')}")
        
        if result.get("route"):
            route = result["route"]
            print(f"  - route_id: {route.get('route_id')}")
            print(f"  - distance: {route.get('total_distance_m', 0)/1000:.2f}km")
            print(f"  - duration: {route.get('total_duration_seconds', 0)/60:.1f}min")
        
        if result.get("explanation"):
            exp = result["explanation"]
            print(f"  - summary: {exp.get('summary', '')[:100]}...")
        
        trace = result.get("trace", {})
        print(f"  - phases_executed: {trace.get('phases_executed', [])}")
        print(f"  - llm_calls: {trace.get('llm_calls', 0)}")
        print(f"  - algorithm_calls: {trace.get('algorithm_calls', 0)}")
        print(f"  - replan_count: {trace.get('replan_count', 0)}")
        
        return True
    except Exception as e:
        print(f"[WARN] 完整流程执行失败（可能是LLM服务不可用）: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multi_vehicle():
    """测试多车规划"""
    print("\n" + "="*60)
    print("测试6: 多车VRP规划")
    print("="*60)
    
    try:
        from src.agents.route_planning.state import create_initial_state, Point, VehicleInfo, TaskPoint
        from src.agents.route_planning.nodes.routing import compute_route
        
        # 创建多车状态
        state = create_initial_state(
            request_id="test-multi-001",
            request_type="multi",
            vehicles=[
                VehicleInfo(
                    vehicle_id="v1",
                    vehicle_code="消防车1",
                    vehicle_type="fire_truck",
                    max_speed_kmh=80,
                    is_all_terrain=False,
                    capacity=5,
                    current_location=Point(lon=104.06, lat=30.67),
                ),
                VehicleInfo(
                    vehicle_id="v2",
                    vehicle_code="救护车1",
                    vehicle_type="ambulance",
                    max_speed_kmh=100,
                    is_all_terrain=False,
                    capacity=3,
                    current_location=Point(lon=104.06, lat=30.67),
                ),
            ],
            task_points=[
                TaskPoint(
                    id="t1",
                    location=Point(lon=104.08, lat=30.69),
                    demand=2,
                    priority=5,
                    time_window_start=None,
                    time_window_end=None,
                    service_time_min=30,
                ),
                TaskPoint(
                    id="t2",
                    location=Point(lon=104.10, lat=30.70),
                    demand=1,
                    priority=3,
                    time_window_start=None,
                    time_window_end=None,
                    service_time_min=20,
                ),
                TaskPoint(
                    id="t3",
                    location=Point(lon=104.12, lat=30.72),
                    demand=2,
                    priority=4,
                    time_window_start=None,
                    time_window_end=None,
                    service_time_min=25,
                ),
            ],
            depot_location=Point(lon=104.06, lat=30.67),
        )
        
        # 设置策略
        state["strategy_selection"] = {
            "primary_strategy": "balanced",
            "optimization_weights": {"time": 0.4, "safety": 0.3, "distance": 0.2, "fuel": 0.1},
            "algorithm_params": {"search_radius_km": 80.0, "speed_factor": 1.0, "risk_tolerance": 0.5},
            "fallback_strategy": None,
        }
        
        # 执行VRP计算
        result = await compute_route(state, db=None)
        
        print("[PASS] 多车规划成功")
        multi_result = result.get("multi_route_result")
        if multi_result:
            print(f"  - solution_id: {multi_result['solution_id']}")
            print(f"  - total_distance_m: {multi_result['total_distance_m']:.2f}")
            print(f"  - served_tasks: {multi_result['served_tasks']}/{multi_result['total_tasks']}")
            print(f"  - coverage_rate: {multi_result['coverage_rate']:.0%}")
            print(f"  - routes: {len(multi_result['routes'])}条")
            for i, route in enumerate(multi_result['routes']):
                print(f"    - 车辆{i+1}: {route['vehicle_id']}, 距离{route['total_distance_m']/1000:.2f}km")
        print(f"  - algorithm_used: {result.get('algorithm_used')}")
        
        return True
    except Exception as e:
        print(f"[FAIL] 多车规划失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# 路径规划智能体测试")
    print("#"*60)
    
    results = []
    
    # 测试1: 模块导入
    results.append(("模块导入", test_import()))
    
    # 测试2: 状态创建
    results.append(("状态创建", test_state_creation()))
    
    # 测试3: 图构建
    results.append(("图构建", test_graph_build()))
    
    # 测试4: 单车规划（无LLM）
    results.append(("单车规划(无LLM)", await test_single_route_no_llm()))
    
    # 测试5: 多车规划
    results.append(("多车VRP规划", await test_multi_vehicle()))
    
    # 测试6: 完整流程（需要LLM）
    results.append(("完整流程(需LLM)", await test_full_flow_with_llm()))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed}通过, {failed}失败")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
