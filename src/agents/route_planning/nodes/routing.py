"""
路径计算节点

纯算法层，调用DatabaseRouteEngine或VehicleRoutingPlanner进行路径计算。
不涉及LLM，属于"双频架构"中的高频层。
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.planning.algorithms.routing import (
    DatabaseRouteEngine,
    VehicleRoutingPlanner,
    load_vehicle_capability,
    VehicleCapability,
)
from src.planning.algorithms.routing.types import Point as RoutingPoint, InfeasiblePathError
from src.planning.algorithms.base import AlgorithmStatus

from ..state import (
    RoutePlanningState,
    SingleRouteResult,
    MultiVehicleRouteResult,
    RouteSegment,
    Point,
)

logger = logging.getLogger(__name__)


async def compute_route(
    state: RoutePlanningState,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    路径计算节点
    
    根据规划类型调用相应算法：
    - single: 调用DatabaseRouteEngine进行单车A*规划
    - multi: 调用VehicleRoutingPlanner进行多车VRP规划
    - replan: 根据上一次结果调整参数重新规划
    
    输入：
        - request_type: 规划类型
        - start/end: 起终点（单车）
        - vehicles/task_points: 车辆和任务点（多车）
        - strategy_selection: 策略配置
        - scenario_id: 想定ID（用于灾害区域）
        
    输出：
        - route_result: 单车路径结果
        - multi_route_result: 多车路径结果
        - algorithm_used: 使用的算法
        - computation_time_ms: 计算耗时
    """
    start_time = time.perf_counter()
    request_type = state["request_type"]
    logger.info(f"[路径计算] 开始 request_id={state['request_id']} type={request_type}")
    
    strategy = state.get("strategy_selection", {})
    algorithm_params = strategy.get("algorithm_params", {})
    
    try:
        if request_type == "single":
            result = await _compute_single_route(state, db, algorithm_params)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(
                f"[路径计算] 单车规划完成 距离={result['total_distance_m']/1000:.2f}km "
                f"耗时={elapsed_ms}ms"
            )
            return {
                "route_result": result,
                "multi_route_result": None,
                "algorithm_used": "DatabaseRouteEngine",
                "computation_time_ms": elapsed_ms,
                "current_phase": "route_computed",
                "trace": {
                    **state.get("trace", {}),
                    "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["compute_route"],
                    "algorithm_calls": state.get("trace", {}).get("algorithm_calls", 0) + 1,
                },
            }
            
        elif request_type == "multi":
            result = _compute_multi_route(state, algorithm_params)
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            logger.info(
                f"[路径计算] 多车规划完成 served={result['served_tasks']}/{result['total_tasks']} "
                f"耗时={elapsed_ms}ms"
            )
            return {
                "route_result": None,
                "multi_route_result": result,
                "algorithm_used": "VehicleRoutingPlanner",
                "computation_time_ms": elapsed_ms,
                "current_phase": "route_computed",
                "trace": {
                    **state.get("trace", {}),
                    "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["compute_route"],
                    "algorithm_calls": state.get("trace", {}).get("algorithm_calls", 0) + 1,
                },
            }
            
        elif request_type == "replan":
            # 重规划：根据上次失败原因调整参数
            replan_count = state.get("replan_count", 0)
            adjusted_params = _adjust_params_for_replan(algorithm_params, replan_count)
            
            if state.get("route_result") is None and state.get("multi_route_result") is None:
                # 首次规划作为单车处理
                result = await _compute_single_route(state, db, adjusted_params)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                return {
                    "route_result": result,
                    "multi_route_result": None,
                    "algorithm_used": "DatabaseRouteEngine",
                    "computation_time_ms": elapsed_ms,
                    "current_phase": "route_computed",
                    "replan_count": replan_count + 1,
                    "trace": {
                        **state.get("trace", {}),
                        "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["compute_route"],
                        "algorithm_calls": state.get("trace", {}).get("algorithm_calls", 0) + 1,
                        "replan_history": state.get("trace", {}).get("replan_history", []) + [
                            {"attempt": replan_count + 1, "params": adjusted_params}
                        ],
                    },
                }
            else:
                raise ValueError("重规划时必须指定原规划类型")
                
        else:
            raise ValueError(f"未知的规划类型: {request_type}")
            
    except InfeasiblePathError as e:
        logger.warning(f"[路径计算] 无法找到可行路径: {e}")
        return {
            "route_result": None,
            "multi_route_result": None,
            "algorithm_used": "DatabaseRouteEngine" if request_type == "single" else "VehicleRoutingPlanner",
            "computation_time_ms": int((time.perf_counter() - start_time) * 1000),
            "current_phase": "route_failed",
            "errors": state.get("errors", []) + [str(e)],
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["compute_route"],
                "algorithm_calls": state.get("trace", {}).get("algorithm_calls", 0) + 1,
            },
        }
    except Exception as e:
        logger.error(f"[路径计算] 算法执行失败: {e}")
        raise RuntimeError(f"路径计算失败: {e}") from e


async def _compute_single_route(
    state: RoutePlanningState,
    db: Optional[AsyncSession],
    params: Dict[str, Any],
) -> SingleRouteResult:
    """
    单车路径规划
    
    调用DatabaseRouteEngine进行A*规划。
    """
    start_point = state.get("start")
    end_point = state.get("end")
    vehicle_id = state.get("vehicle_id")
    scenario_id = state.get("scenario_id")
    
    if not start_point or not end_point:
        raise ValueError("单车规划必须指定起点和终点")
    
    # 转换坐标格式
    start = RoutingPoint(lon=start_point["lon"], lat=start_point["lat"])
    end = RoutingPoint(lon=end_point["lon"], lat=end_point["lat"])
    
    # 加载车辆能力（如果有db和vehicle_id）
    vehicle_capability: Optional[VehicleCapability] = None
    if db and vehicle_id:
        try:
            vehicle_capability = await load_vehicle_capability(db, UUID(vehicle_id))
            logger.info(f"[路径计算] 加载车辆能力 vehicle_code={vehicle_capability.vehicle_code if vehicle_capability else 'None'}")
        except Exception as e:
            logger.warning(f"[路径计算] 加载车辆能力失败: {e}，使用默认配置")
    
    # 无车辆能力时使用默认配置
    if not vehicle_capability:
        # 安全解析vehicle_id，非UUID格式时生成新UUID
        parsed_vehicle_id = uuid.uuid4()
        if vehicle_id:
            try:
                parsed_vehicle_id = UUID(vehicle_id)
            except ValueError:
                logger.info(f"[路径计算] vehicle_id非UUID格式，生成新UUID: {vehicle_id}")
                parsed_vehicle_id = uuid.uuid4()
        
        vehicle_capability = VehicleCapability(
            vehicle_id=parsed_vehicle_id,
            vehicle_code=vehicle_id or "DEFAULT",
            max_speed_kmh=60,
            is_all_terrain=False,
            terrain_capabilities=["urban", "suburban"],
            terrain_speed_factors={},
            max_gradient_percent=15,
            max_wading_depth_m=0.3,
            width_m=2.5,
            height_m=3.0,
            total_weight_kg=10000,
        )
    
    # 执行路径规划
    if db:
        engine = DatabaseRouteEngine(db)
        search_radius = params.get("search_radius_km", 80.0)
        route_result = await engine.plan_route(
            start=start,
            end=end,
            vehicle=vehicle_capability,
            scenario_id=UUID(scenario_id) if scenario_id else None,
            search_radius_km=search_radius,
        )
        
        # 转换为输出格式
        path_points: list[Point] = [
            {"lon": p.lon, "lat": p.lat} for p in route_result.path_points
        ]
        
        # 简化分段信息（DatabaseRouteEngine返回的是点序列，需要构造分段）
        segments: list[RouteSegment] = []
        for i in range(len(path_points) - 1):
            segments.append({
                "segment_id": f"seg_{i}",
                "from_point": path_points[i],
                "to_point": path_points[i + 1],
                "distance_m": route_result.distance_m / max(len(path_points) - 1, 1),
                "duration_seconds": route_result.duration_seconds / max(len(path_points) - 1, 1),
                "road_type": "unknown",
                "terrain_type": "unknown",
                "risk_level": "low",
            })
        
        return SingleRouteResult(
            route_id=str(uuid.uuid4()),
            vehicle_id=vehicle_id or str(vehicle_capability.vehicle_id),
            path_points=path_points,
            segments=segments,
            total_distance_m=route_result.distance_m,
            total_duration_seconds=route_result.duration_seconds,
            risk_score=0.3 if route_result.blocked_by_disaster else 0.1,
            warnings=route_result.warnings,
        )
    else:
        # 无数据库连接时，使用简化计算（仅返回直线距离估算）
        from src.planning.algorithms.base import haversine_distance, Location
        
        start_loc = Location(start_point["lat"], start_point["lon"])
        end_loc = Location(end_point["lat"], end_point["lon"])
        distance_km = haversine_distance(start_loc, end_loc)
        
        speed_kmh = vehicle_capability.max_speed_kmh * params.get("speed_factor", 1.0)
        duration_seconds = (distance_km / speed_kmh) * 3600
        
        return SingleRouteResult(
            route_id=str(uuid.uuid4()),
            vehicle_id=vehicle_id or str(vehicle_capability.vehicle_id),
            path_points=[start_point, end_point],
            segments=[{
                "segment_id": "seg_0",
                "from_point": start_point,
                "to_point": end_point,
                "distance_m": distance_km * 1000,
                "duration_seconds": duration_seconds,
                "road_type": "estimated",
                "terrain_type": "unknown",
                "risk_level": "unknown",
            }],
            total_distance_m=distance_km * 1000,
            total_duration_seconds=duration_seconds,
            risk_score=0.5,
            warnings=["无路网数据，使用直线距离估算"],
        )


def _compute_multi_route(
    state: RoutePlanningState,
    params: Dict[str, Any],
) -> MultiVehicleRouteResult:
    """
    多车路径规划
    
    调用VehicleRoutingPlanner进行VRP规划。
    """
    vehicles = state.get("vehicles", [])
    task_points = state.get("task_points", [])
    depot = state.get("depot_location")
    
    if not vehicles:
        raise ValueError("多车规划必须指定车辆列表")
    if not task_points:
        raise ValueError("多车规划必须指定任务点列表")
    
    # 构建VRP输入
    depots = []
    if depot:
        depots.append({
            "id": "depot_0",
            "location": {"lat": depot["lat"], "lng": depot["lon"]},
            "name": "主基地",
        })
    else:
        # 使用第一辆车的位置作为depot
        first_vehicle = vehicles[0]
        depots.append({
            "id": "depot_0",
            "location": {
                "lat": first_vehicle["current_location"]["lat"],
                "lng": first_vehicle["current_location"]["lon"],
            },
            "name": "车辆出发点",
        })
    
    tasks = []
    for tp in task_points:
        task = {
            "id": tp["id"],
            "location": {"lat": tp["location"]["lat"], "lng": tp["location"]["lon"]},
            "demand": tp.get("demand", 1),
            "service_time_min": tp.get("service_time_min", 15),
            "priority": tp.get("priority", 1),
        }
        if tp.get("time_window_start") is not None:
            task["time_window"] = {
                "start": tp["time_window_start"],
                "end": tp.get("time_window_end", tp["time_window_start"] + 120),
            }
        tasks.append(task)
    
    vrp_vehicles = []
    for v in vehicles:
        vrp_vehicles.append({
            "id": v["vehicle_id"],
            "name": v.get("vehicle_code", v["vehicle_id"]),
            "depot_id": "depot_0",
            "capacity": v.get("capacity", 10),
            "max_distance_km": params.get("max_distance_km", 200),
            "max_time_min": params.get("max_time_min", 480),
            "speed_kmh": v.get("max_speed_kmh", 40) * params.get("speed_factor", 1.0),
        })
    
    # 执行VRP规划
    planner = VehicleRoutingPlanner()
    vrp_result = planner.run({
        "depots": depots,
        "tasks": tasks,
        "vehicles": vrp_vehicles,
        "constraints": {
            "use_time_windows": any(tp.get("time_window_start") for tp in task_points),
            "time_limit_sec": params.get("time_limit_sec", 30),
        },
    })
    
    # 转换为输出格式
    routes: list[SingleRouteResult] = []
    for sol in vrp_result.solution:
        # 构建路径点
        path_points: list[Point] = []
        # 起点depot
        depot_loc = depots[0]["location"]
        path_points.append({"lon": depot_loc["lng"], "lat": depot_loc["lat"]})
        
        for stop in sol.get("stops", []):
            loc = stop.get("location", (0, 0))
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                path_points.append({"lon": loc[1], "lat": loc[0]})
        
        # 终点回depot
        path_points.append({"lon": depot_loc["lng"], "lat": depot_loc["lat"]})
        
        routes.append(SingleRouteResult(
            route_id=str(uuid.uuid4()),
            vehicle_id=sol.get("vehicle_id", ""),
            path_points=path_points,
            segments=[],
            total_distance_m=sol.get("total_distance_km", 0) * 1000,
            total_duration_seconds=sol.get("total_time_min", 0) * 60,
            risk_score=0.2,
            warnings=[],
        ))
    
    metrics = vrp_result.metrics
    return MultiVehicleRouteResult(
        solution_id=str(uuid.uuid4()),
        routes=routes,
        total_distance_m=metrics.get("total_distance_km", 0) * 1000,
        total_duration_seconds=max((r["total_duration_seconds"] for r in routes), default=0),
        served_tasks=metrics.get("served_tasks", 0),
        total_tasks=metrics.get("total_tasks", len(task_points)),
        coverage_rate=metrics.get("served_tasks", 0) / max(len(task_points), 1),
    )


def _adjust_params_for_replan(
    params: Dict[str, Any],
    replan_count: int,
) -> Dict[str, Any]:
    """
    重规划时调整参数
    
    每次重规划扩大搜索范围，降低约束严格度。
    """
    adjusted = params.copy()
    
    # 扩大搜索范围
    base_radius = params.get("search_radius_km", 80.0)
    adjusted["search_radius_km"] = base_radius * (1 + 0.5 * replan_count)
    
    # 提高风险容忍度
    base_risk = params.get("risk_tolerance", 0.5)
    adjusted["risk_tolerance"] = min(base_risk + 0.2 * replan_count, 0.9)
    
    # 延长时间限制
    base_time = params.get("time_limit_sec", 30)
    adjusted["time_limit_sec"] = base_time + 15 * replan_count
    
    logger.info(
        f"[路径计算] 重规划参数调整 attempt={replan_count+1} "
        f"radius={adjusted['search_radius_km']:.1f}km "
        f"risk_tolerance={adjusted['risk_tolerance']:.2f}"
    )
    
    return adjusted
