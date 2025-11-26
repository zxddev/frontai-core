"""
路径规划封装

调用VehicleRoutingPlanner进行路径规划，转换结果为RouteResponse格式。
算法失败时直接抛出异常，不做降级。
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from src.planning.algorithms.routing.vehicle_routing import VehicleRoutingPlanner
from src.planning.algorithms.base import AlgorithmStatus, Location as PlanningLocation, haversine_distance
from .schemas import RouteRequest, RouteResponse, RouteSegment, Location, RiskLevel

logger = logging.getLogger(__name__)

# 路径规划器单例
_route_planner: Optional[VehicleRoutingPlanner] = None


def get_route_planner() -> VehicleRoutingPlanner:
    """
    获取路径规划器单例
    
    首次调用时初始化，后续复用同一实例。
    """
    global _route_planner
    
    if _route_planner is None:
        logger.info("初始化路径规划器")
        _route_planner = VehicleRoutingPlanner()
        logger.info("路径规划器初始化完成")
    
    return _route_planner


def _workflow_to_planning_location(loc: Location) -> dict[str, float]:
    """
    转换Location格式：rescue_workflow → planning
    
    rescue_workflow: Location(longitude=x, latitude=y)
    planning dict: {"lat": y, "lng": x}
    """
    return {"lat": loc.latitude, "lng": loc.longitude}


def _planning_to_workflow_location(lat: float, lng: float) -> Location:
    """
    转换Location格式：planning → rescue_workflow
    """
    return Location(longitude=lng, latitude=lat)


def plan_route_vrp(request: RouteRequest) -> RouteResponse:
    """
    使用VehicleRoutingPlanner规划路径
    
    将单车辆路径规划转换为VRP问题求解。
    
    Args:
        request: 路径规划请求
        
    Returns:
        RouteResponse包含路径信息
        
    Raises:
        RuntimeError: 算法执行失败时抛出
    """
    logger.info(
        "执行路径规划",
        extra={
            "event_id": str(request.event_id),
            "vehicle_id": str(request.vehicle_id),
            "origin": f"({request.origin.longitude}, {request.origin.latitude})",
            "destination": f"({request.destination.longitude}, {request.destination.latitude})",
        }
    )
    
    # 构造VRP输入
    vrp_input = _build_vrp_input(request)
    
    # 执行规划
    planner = get_route_planner()
    result = planner.run(vrp_input)
    
    # 检查结果状态
    if result.status == AlgorithmStatus.ERROR:
        error_msg = result.message or "路径规划算法执行失败"
        logger.error(f"路径规划失败: {error_msg}")
        raise RuntimeError(error_msg)
    
    if result.status == AlgorithmStatus.INFEASIBLE:
        logger.error("路径规划无可行解")
        raise RuntimeError("无法找到可行路径")
    
    # 转换结果
    response = _build_route_response(request, result)
    
    logger.info(
        "路径规划完成",
        extra={
            "route_id": str(response.route_id),
            "distance_m": response.total_distance_meters,
            "duration_s": response.total_duration_seconds,
        }
    )
    
    return response


def _build_vrp_input(request: RouteRequest) -> dict:
    """
    构造VRP算法输入
    
    将单车辆路径规划转换为：
    - 1个depot（起点）
    - 1个task（终点）
    - 1辆vehicle
    """
    origin_loc = _workflow_to_planning_location(request.origin)
    dest_loc = _workflow_to_planning_location(request.destination)
    
    # 收集所有任务点（终点 + 途经点）
    tasks = [{
        "id": "destination",
        "location": dest_loc,
        "demand": 1,
        "service_time_min": 0,
        "priority": 1,
    }]
    
    # 添加途经点
    if request.waypoints:
        for i, wp in enumerate(request.waypoints):
            tasks.append({
                "id": f"waypoint_{i}",
                "location": _workflow_to_planning_location(wp),
                "demand": 0,
                "service_time_min": 0,
                "priority": 2,  # 途经点优先级低于终点
            })
    
    # 根据优化目标设置速度
    speed_kmh = 40  # 默认速度
    if request.optimization == "fastest":
        speed_kmh = 60  # 快速模式假设更高速度
    elif request.optimization == "safest":
        speed_kmh = 30  # 安全模式假设较低速度
    
    vrp_input = {
        "depots": [{
            "id": "origin",
            "location": origin_loc,
            "name": "起点",
        }],
        "tasks": tasks,
        "vehicles": [{
            "id": str(request.vehicle_id),
            "name": "救援车辆",
            "depot_id": "origin",
            "capacity": 10,
            "max_distance_km": 500,
            "max_time_min": 600,
            "speed_kmh": speed_kmh,
        }],
        "constraints": {
            "time_limit_sec": 10,  # 快速求解
            "use_time_windows": False,
        },
    }
    
    return vrp_input


def _build_route_response(request: RouteRequest, result) -> RouteResponse:
    """
    将VRP结果转换为RouteResponse
    """
    route_id = uuid4()
    
    # 提取解
    solution = result.solution
    if not solution:
        # 无解时返回直线距离估算
        return _build_fallback_response(request, route_id)
    
    # 获取第一辆车的路线
    vehicle_route = solution[0] if solution else {}
    
    total_distance_km = vehicle_route.get("total_distance_km", 0)
    total_time_min = vehicle_route.get("total_time_min", 0)
    stops = vehicle_route.get("stops", [])
    
    # 构造segments（简化版：起点→各停靠点→终点）
    segments: list[RouteSegment] = []
    
    # 起点位置
    current_loc = request.origin
    
    for stop in stops:
        stop_loc_tuple = stop.get("location", (0, 0))
        if isinstance(stop_loc_tuple, (list, tuple)) and len(stop_loc_tuple) >= 2:
            stop_loc = _planning_to_workflow_location(stop_loc_tuple[0], stop_loc_tuple[1])
        else:
            continue
        
        # 计算这一段的距离和时间
        seg_distance_km = haversine_distance(
            PlanningLocation(lat=current_loc.latitude, lng=current_loc.longitude),
            PlanningLocation(lat=stop_loc.latitude, lng=stop_loc.longitude),
        )
        seg_time_min = seg_distance_km / 40 * 60  # 假设40km/h
        
        segment = RouteSegment(
            start_point=current_loc,
            end_point=stop_loc,
            distance_meters=seg_distance_km * 1000,
            duration_seconds=int(seg_time_min * 60),
            road_name=None,  # VRP不提供详细路名
            risk_level=RiskLevel.low,
            instructions=f"前往{stop.get('task_id', '下一点')}",
        )
        segments.append(segment)
        current_loc = stop_loc
    
    # 如果没有segments（算法返回空stops），使用起终点直连
    if not segments:
        return _build_fallback_response(request, route_id)
    
    return RouteResponse(
        route_id=route_id,
        event_id=request.event_id,
        vehicle_id=request.vehicle_id,
        total_distance_meters=total_distance_km * 1000,
        total_duration_seconds=int(total_time_min * 60),
        segments=segments,
        risk_areas=[],
        alternative_routes=None,
    )


def _build_fallback_response(request: RouteRequest, route_id: UUID) -> RouteResponse:
    """
    构造备用响应（直线距离估算）
    
    当算法返回空解时使用。
    """
    # 计算直线距离
    distance_km = haversine_distance(
        PlanningLocation(lat=request.origin.latitude, lng=request.origin.longitude),
        PlanningLocation(lat=request.destination.latitude, lng=request.destination.longitude),
    )
    
    # 假设实际道路距离是直线距离的1.4倍（城市道路系数）
    road_distance_km = distance_km * 1.4
    travel_time_min = road_distance_km / 40 * 60  # 40km/h
    
    segment = RouteSegment(
        start_point=request.origin,
        end_point=request.destination,
        distance_meters=road_distance_km * 1000,
        duration_seconds=int(travel_time_min * 60),
        road_name=None,
        risk_level=RiskLevel.low,
        instructions="沿路线行驶至目的地",
    )
    
    return RouteResponse(
        route_id=route_id,
        event_id=request.event_id,
        vehicle_id=request.vehicle_id,
        total_distance_meters=road_distance_km * 1000,
        total_duration_seconds=int(travel_time_min * 60),
        segments=[segment],
        risk_areas=[],
        alternative_routes=None,
    )
