"""
路径规划节点

调用VehicleRoutingPlanner算法执行多车辆路径规划
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.planning.algorithms.routing import VehicleRoutingPlanner
from src.planning.algorithms.base import AlgorithmStatus

from ..state import (
    TaskDispatchState,
    PlannedRouteState,
    RouteStopState,
    LocationState,
    ScheduledTaskState,
)

logger = logging.getLogger(__name__)

# VRP规划器单例
_vrp_planner: VehicleRoutingPlanner | None = None


def _get_vrp_planner() -> VehicleRoutingPlanner:
    """获取VehicleRoutingPlanner单例"""
    global _vrp_planner
    if _vrp_planner is None:
        logger.info("初始化VehicleRoutingPlanner")
        _vrp_planner = VehicleRoutingPlanner()
    return _vrp_planner


def plan_routes(state: TaskDispatchState) -> Dict[str, Any]:
    """
    路径规划节点
    
    基于调度结果和资源位置，执行多车辆路径规划
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    scheduled_tasks = state.get("scheduled_tasks", [])
    available_resources = state.get("available_resources", [])
    decomposed_tasks = state.get("decomposed_tasks", [])
    dispatch_config = state.get("dispatch_config", {})
    
    logger.info(
        f"开始路径规划: {len(scheduled_tasks)} 个任务, {len(available_resources)} 个资源",
        extra={"event_id": state.get("event_id")}
    )
    
    if not scheduled_tasks:
        logger.warning("无调度任务，跳过路径规划")
        return {
            "planned_routes": [],
            "total_travel_distance_km": 0.0,
            "total_travel_time_min": 0,
            "trace": _update_trace(state, "plan_routes", {"status": "skipped", "reason": "no_tasks"}),
        }
    
    # 构建VRP输入
    vrp_input = _build_vrp_input(scheduled_tasks, decomposed_tasks, available_resources, dispatch_config)
    
    # 执行VRP规划
    planner = _get_vrp_planner()
    result = planner.run(vrp_input)
    
    logger.info(
        f"VehicleRoutingPlanner执行完成: status={result.status.value}",
        extra={"metrics": result.metrics}
    )
    
    # 处理结果
    if result.status == AlgorithmStatus.ERROR:
        error_msg = result.message or "路径规划算法执行失败"
        logger.error(f"路径规划失败: {error_msg}")
        # 不中断流程，使用直线距离估算
        return _fallback_direct_routes(state, scheduled_tasks, decomposed_tasks, available_resources, error_msg)
    
    if result.status == AlgorithmStatus.INFEASIBLE:
        logger.warning("VRP无可行解，使用直线距离估算")
        return _fallback_direct_routes(state, scheduled_tasks, decomposed_tasks, available_resources, "VRP无可行解")
    
    # 解析VRP结果
    solution = result.solution or {}
    routes_data = solution.get("routes", [])
    
    planned_routes = _parse_vrp_routes(routes_data)
    total_distance = sum(r["total_distance_km"] for r in planned_routes)
    total_time = sum(r["total_time_min"] for r in planned_routes)
    
    logger.info(
        f"路径规划成功: {len(planned_routes)} 条路线, "
        f"总距离 {total_distance:.1f} km, 总时间 {total_time} 分钟"
    )
    
    return {
        "planned_routes": planned_routes,
        "total_travel_distance_km": round(total_distance, 2),
        "total_travel_time_min": int(total_time),
        "trace": _update_trace(state, "plan_routes", {
            "status": "success",
            "route_count": len(planned_routes),
            "total_distance_km": round(total_distance, 2),
            "total_time_min": int(total_time),
        }),
    }


def _build_vrp_input(
    scheduled_tasks: List[ScheduledTaskState],
    decomposed_tasks: List[Dict[str, Any]],
    resources: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """构建VRP输入格式"""
    # 建立任务ID到位置的映射
    task_location_map: Dict[str, LocationState] = {}
    for task in decomposed_tasks:
        task_location_map[task["task_id"]] = task.get("location", {"latitude": 31.2, "longitude": 121.5})
    
    # 构建depot（资源出发点）
    depots = []
    for idx, res in enumerate(resources):
        location = res.get("location", res.get("base_location", {}))
        if not location:
            location = {"latitude": 31.2, "longitude": 121.5}
        
        depots.append({
            "id": f"depot-{idx}",
            "location": {"lat": location.get("latitude", 31.2), "lng": location.get("longitude", 121.5)},
            "name": res.get("name", f"出发点-{idx}"),
        })
    
    # 如果没有depot，使用默认
    if not depots:
        depots = [{
            "id": "depot-default",
            "location": {"lat": 31.2, "lng": 121.5},
            "name": "默认出发点",
        }]
    
    # 构建任务节点
    tasks = []
    for task in scheduled_tasks:
        loc = task_location_map.get(task["task_id"], {"latitude": 31.2, "longitude": 121.5})
        tasks.append({
            "id": task["task_id"],
            "location": {"lat": loc.get("latitude", 31.2), "lng": loc.get("longitude", 121.5)},
            "demand": 1,
            "service_time_min": 30,  # 默认服务时间
            "priority": task.get("priority", 3),
        })
    
    # 构建车辆
    vehicles = []
    for idx, res in enumerate(resources):
        depot_id = f"depot-{idx}" if idx < len(depots) else "depot-default"
        vehicles.append({
            "id": res.get("id", f"vehicle-{idx}"),
            "name": res.get("name", f"车辆-{idx}"),
            "depot_id": depot_id,
            "capacity": config.get("vehicle_capacity", 10),
            "max_distance_km": config.get("max_distance_km", 100),
            "max_time_min": config.get("max_time_min", 480),
            "speed_kmh": config.get("speed_kmh", 40),
        })
    
    # 如果没有车辆，使用默认
    if not vehicles:
        vehicles = [{
            "id": "vehicle-default",
            "name": "默认车辆",
            "depot_id": "depot-default",
            "capacity": 10,
            "max_distance_km": 100,
            "max_time_min": 480,
            "speed_kmh": 40,
        }]
    
    return {
        "depots": depots,
        "tasks": tasks,
        "vehicles": vehicles,
    }


def _parse_vrp_routes(routes_data: List[Dict[str, Any]]) -> List[PlannedRouteState]:
    """解析VRP路线结果"""
    planned_routes: List[PlannedRouteState] = []
    
    for route in routes_data:
        stops = []
        for stop in route.get("stops", []):
            loc = stop.get("location", {})
            stops.append(RouteStopState(
                stop_id=stop.get("task_id", ""),
                stop_name=stop.get("name", ""),
                location=LocationState(
                    latitude=loc.get("lat", 31.2),
                    longitude=loc.get("lng", 121.5),
                ),
                arrival_time_min=stop.get("arrival_time_min", 0),
                departure_time_min=stop.get("departure_time_min", 0),
                service_duration_min=stop.get("service_time_min", 0),
                task_id=stop.get("task_id"),
            ))
        
        depot_loc = route.get("depot_location", {})
        planned_routes.append(PlannedRouteState(
            vehicle_id=route.get("vehicle_id", ""),
            vehicle_name=route.get("vehicle_name", ""),
            depot_location=LocationState(
                latitude=depot_loc.get("lat", 31.2),
                longitude=depot_loc.get("lng", 121.5),
            ),
            stops=stops,
            total_distance_km=route.get("total_distance_km", 0),
            total_time_min=route.get("total_time_min", 0),
            route_geometry=None,
        ))
    
    return planned_routes


def _fallback_direct_routes(
    state: TaskDispatchState,
    scheduled_tasks: List[ScheduledTaskState],
    decomposed_tasks: List[Dict[str, Any]],
    resources: List[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    """使用直线距离估算路线（VRP失败时的后备方案）"""
    logger.warning(f"使用直线距离估算路线: {reason}")
    
    # 简化处理：每个资源负责其分配的任务
    task_location_map = {t["task_id"]: t.get("location", {}) for t in decomposed_tasks}
    
    planned_routes: List[PlannedRouteState] = []
    total_distance = 0.0
    total_time = 0
    
    # 分配任务到资源
    task_resource_map: Dict[str, str] = {}
    for task in scheduled_tasks:
        for rid in task.get("assigned_resource_ids", []):
            task_resource_map[task["task_id"]] = rid
            break
    
    # 按资源分组任务
    resource_tasks: Dict[str, List[ScheduledTaskState]] = {}
    for task in scheduled_tasks:
        rid = task_resource_map.get(task["task_id"], "default")
        if rid not in resource_tasks:
            resource_tasks[rid] = []
        resource_tasks[rid].append(task)
    
    # 为每个资源生成路线
    for rid, tasks in resource_tasks.items():
        res = next((r for r in resources if r.get("id") == rid), None)
        res_name = res.get("name", rid) if res else rid
        
        stops = []
        for task in tasks:
            loc = task_location_map.get(task["task_id"], {"latitude": 31.2, "longitude": 121.5})
            stops.append(RouteStopState(
                stop_id=task["task_id"],
                stop_name=task["task_name"],
                location=LocationState(
                    latitude=loc.get("latitude", 31.2),
                    longitude=loc.get("longitude", 121.5),
                ),
                arrival_time_min=task["start_time_min"],
                departure_time_min=task["end_time_min"],
                service_duration_min=task["end_time_min"] - task["start_time_min"],
                task_id=task["task_id"],
            ))
        
        # 估算距离和时间
        est_distance = len(stops) * 5.0  # 假设每个任务点5km
        est_time = len(stops) * 15  # 假设每个任务点15分钟路程
        
        planned_routes.append(PlannedRouteState(
            vehicle_id=rid,
            vehicle_name=res_name,
            depot_location=LocationState(latitude=31.2, longitude=121.5),
            stops=stops,
            total_distance_km=est_distance,
            total_time_min=est_time,
            route_geometry=None,
        ))
        
        total_distance += est_distance
        total_time += est_time
    
    return {
        "planned_routes": planned_routes,
        "total_travel_distance_km": round(total_distance, 2),
        "total_travel_time_min": int(total_time),
        "errors": state.get("errors", []) + [f"路径规划降级: {reason}"],
        "trace": _update_trace(state, "plan_routes", {
            "status": "fallback",
            "reason": reason,
            "route_count": len(planned_routes),
        }),
    }


def _update_trace(
    state: TaskDispatchState,
    node_name: str,
    node_result: Dict[str, Any],
) -> Dict[str, Any]:
    """更新追踪信息"""
    trace = state.get("trace", {}).copy()
    nodes_executed = trace.get("nodes_executed", [])
    nodes_executed.append(node_name)
    trace["nodes_executed"] = nodes_executed
    trace[node_name] = node_result
    return trace
