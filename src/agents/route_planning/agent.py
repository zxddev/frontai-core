"""
路径规划智能体入口

提供异步invoke接口，供router或其他模块调用。
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, Optional, Literal, List

from sqlalchemy.ext.asyncio import AsyncSession

from .state import (
    RoutePlanningState,
    Point,
    VehicleInfo,
    TaskPoint,
    RouteConstraint,
    DisasterContext,
    create_initial_state,
)
from .graph import get_route_planning_graph

logger = logging.getLogger(__name__)


async def invoke(
    request_type: Literal["single", "multi", "replan"],
    *,
    # 单车规划参数
    start: Optional[Dict[str, float]] = None,
    end: Optional[Dict[str, float]] = None,
    vehicle_id: Optional[str] = None,
    # 多车规划参数
    vehicles: Optional[List[Dict[str, Any]]] = None,
    task_points: Optional[List[Dict[str, Any]]] = None,
    depot_location: Optional[Dict[str, float]] = None,
    # 通用参数
    scenario_id: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None,
    disaster_context: Optional[Dict[str, Any]] = None,
    natural_language_request: Optional[str] = None,
    # 数据库连接（可选，用于加载路网和车辆能力）
    db: Optional[AsyncSession] = None,
    # 请求ID（可选，自动生成）
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    路径规划智能体入口函数
    
    支持三种规划类型：
    - single: 单车点对点规划
    - multi: 多车多点VRP规划
    - replan: 动态重规划
    
    Args:
        request_type: 规划类型
        start: 起点坐标 {"lon": float, "lat": float}
        end: 终点坐标 {"lon": float, "lat": float}
        vehicle_id: 车辆ID（单车规划）
        vehicles: 车辆列表（多车规划）
        task_points: 任务点列表（多车规划）
        depot_location: 车辆基地位置
        scenario_id: 想定ID（用于灾害区域）
        constraints: 约束条件
        disaster_context: 灾情上下文（触发LLM场景分析）
        natural_language_request: 自然语言请求（触发LLM理解）
        db: 数据库会话（可选）
        request_id: 请求ID（可选）
        
    Returns:
        规划结果，包含路径、解释、追踪信息
        
    Raises:
        ValueError: 参数校验失败
        RuntimeError: 规划执行失败
        
    示例:
        # 单车规划
        result = await invoke(
            request_type="single",
            start={"lon": 104.06, "lat": 30.67},
            end={"lon": 104.12, "lat": 30.72},
            vehicle_id="vehicle-001",
            disaster_context={"disaster_type": "earthquake", "severity": "high"},
        )
        
        # 多车规划
        result = await invoke(
            request_type="multi",
            vehicles=[...],
            task_points=[...],
            depot_location={"lon": 104.06, "lat": 30.67},
        )
    """
    start_time = time.perf_counter()
    req_id = request_id or str(uuid.uuid4())
    
    logger.info(f"[RoutePlanningAgent] 开始 request_id={req_id} type={request_type}")
    
    # 参数校验
    _validate_params(request_type, start, end, vehicle_id, vehicles, task_points)
    
    # 转换输入格式
    start_point: Optional[Point] = None
    end_point: Optional[Point] = None
    if start:
        start_point = Point(lon=start["lon"], lat=start["lat"])
    if end:
        end_point = Point(lon=end["lon"], lat=end["lat"])
    
    vehicle_infos: List[VehicleInfo] = []
    if vehicles:
        for v in vehicles:
            vehicle_infos.append(VehicleInfo(
                vehicle_id=v["vehicle_id"],
                vehicle_code=v.get("vehicle_code", v["vehicle_id"]),
                vehicle_type=v.get("vehicle_type", "unknown"),
                max_speed_kmh=v.get("max_speed_kmh", 60),
                is_all_terrain=v.get("is_all_terrain", False),
                capacity=v.get("capacity", 10),
                current_location=Point(
                    lon=v["current_location"]["lon"],
                    lat=v["current_location"]["lat"],
                ),
            ))
    
    task_point_list: List[TaskPoint] = []
    if task_points:
        for tp in task_points:
            task_point_list.append(TaskPoint(
                id=tp["id"],
                location=Point(lon=tp["location"]["lon"], lat=tp["location"]["lat"]),
                demand=tp.get("demand", 1),
                priority=tp.get("priority", 1),
                time_window_start=tp.get("time_window_start"),
                time_window_end=tp.get("time_window_end"),
                service_time_min=tp.get("service_time_min", 15),
            ))
    
    depot: Optional[Point] = None
    if depot_location:
        depot = Point(lon=depot_location["lon"], lat=depot_location["lat"])
    
    route_constraints: RouteConstraint = {}
    if constraints:
        route_constraints = RouteConstraint(**constraints)
    
    disaster_ctx: Optional[DisasterContext] = None
    if disaster_context:
        disaster_ctx = DisasterContext(**disaster_context)
    
    # 创建初始状态
    initial_state = create_initial_state(
        request_id=req_id,
        request_type=request_type,
        start=start_point,
        end=end_point,
        vehicle_id=vehicle_id,
        vehicles=vehicle_infos,
        task_points=task_point_list,
        depot_location=depot,
        scenario_id=scenario_id,
        constraints=route_constraints,
        disaster_context=disaster_ctx,
        natural_language_request=natural_language_request,
    )
    
    # 记录开始时间到trace
    initial_state["trace"]["start_time_ms"] = int(start_time * 1000)
    
    # 获取编译后的图
    graph = get_route_planning_graph()
    
    # 执行图（传入db用于路径计算节点）
    # LangGraph会自动调用各节点，compute_route节点需要db
    # 通过config传递db
    config = {"configurable": {"db": db}}
    
    try:
        # 执行状态图
        final_state = await graph.ainvoke(initial_state, config=config)
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        success = final_state.get("success", False)
        
        logger.info(
            f"[RoutePlanningAgent] 完成 request_id={req_id} "
            f"success={success} elapsed={elapsed_ms}ms "
            f"replan_count={final_state.get('replan_count', 0)}"
        )
        
        # 返回最终输出
        return final_state.get("final_output", {
            "request_id": req_id,
            "success": success,
            "error": "未生成最终输出",
        })
        
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"[RoutePlanningAgent] 失败 request_id={req_id} error={e} elapsed={elapsed_ms}ms")
        raise


def _validate_params(
    request_type: str,
    start: Optional[Dict],
    end: Optional[Dict],
    vehicle_id: Optional[str],
    vehicles: Optional[List],
    task_points: Optional[List],
) -> None:
    """参数校验"""
    if request_type == "single":
        if not start:
            raise ValueError("单车规划必须指定起点(start)")
        if not end:
            raise ValueError("单车规划必须指定终点(end)")
        if "lon" not in start or "lat" not in start:
            raise ValueError("起点格式错误，需要 {lon, lat}")
        if "lon" not in end or "lat" not in end:
            raise ValueError("终点格式错误，需要 {lon, lat}")
            
    elif request_type == "multi":
        if not vehicles or len(vehicles) == 0:
            raise ValueError("多车规划必须指定车辆列表(vehicles)")
        if not task_points or len(task_points) == 0:
            raise ValueError("多车规划必须指定任务点列表(task_points)")
        for i, v in enumerate(vehicles):
            if "vehicle_id" not in v:
                raise ValueError(f"vehicles[{i}] 缺少 vehicle_id")
            if "current_location" not in v:
                raise ValueError(f"vehicles[{i}] 缺少 current_location")
        for i, tp in enumerate(task_points):
            if "id" not in tp:
                raise ValueError(f"task_points[{i}] 缺少 id")
            if "location" not in tp:
                raise ValueError(f"task_points[{i}] 缺少 location")
                
    elif request_type == "replan":
        # 重规划可以不指定参数，使用上次的配置
        pass
    else:
        raise ValueError(f"未知的规划类型: {request_type}")
