"""
路径规划 HTTP 接口

提供统一路径规划 API，根据设备类型自动分发到对应规划器
支持风险区域检测和绕行方案生成
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.stomp.broker import stomp_broker
from .schemas import Point, AvoidArea
from .unified_schemas import (
    RoutePlanRequest,
    RoutePlanResponse,
    PointResponse,
    RouteSegmentResponse,
    RiskCheckRoutePlanRequest,
    RiskCheckRoutePlanResponse,
    RiskAreaResponse,
    AlternativeRouteResponse,
    ConfirmRouteRequest,
    ConfirmRouteResponse,
    PlanAndSaveRequest,
    PlanAndSaveResponse,
    GenerateAlternativesRequest,
    GenerateAlternativesResponse,
    ConfirmRouteByIdRequest,
    PlannedRouteResponse,
    PlannedRouteListResponse,
)
from .unified_service import UnifiedRoutePlanningService
from .risk_detection import RiskDetectionService
from .alternative_routes import AlternativeRoutesService
from .planned_route_service import PlannedRouteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/routing", tags=["routing"])


def get_service(db: AsyncSession = Depends(get_db)) -> UnifiedRoutePlanningService:
    """依赖注入：获取统一路径规划服务"""
    return UnifiedRoutePlanningService(db)


@router.post("/plan", response_model=RoutePlanResponse)
async def plan_route(
    request: RoutePlanRequest,
    service: UnifiedRoutePlanningService = Depends(get_service),
) -> RoutePlanResponse:
    """
    统一路径规划接口
    
    根据设备 env_type 自动选择规划策略：
    - air: 空中直线飞行
    - land: 陆地路径规划（高德API + 内部引擎）
    - sea: 水上路径规划（暂未实现）
    """
    logger.info(f"路径规划请求: device_id={request.device_id}")
    
    # 转换请求参数
    origin = Point(lon=request.origin.lon, lat=request.origin.lat)
    destination = Point(lon=request.destination.lon, lat=request.destination.lat)
    
    avoid_areas: List[AvoidArea] = []
    for area in request.avoid_areas:
        polygon = [Point(lon=p.lon, lat=p.lat) for p in area.polygon]
        avoid_areas.append(AvoidArea(
            polygon=polygon,
            reason=area.reason,
            severity=area.severity,  # type: ignore
        ))
    
    try:
        result = await service.plan_route(
            device_id=request.device_id,
            origin=origin,
            destination=destination,
            avoid_areas=avoid_areas if avoid_areas else None,
        )
    except ValueError as e:
        logger.error(f"路径规划失败: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        logger.error(f"路径规划失败: {e}")
        raise HTTPException(status_code=501, detail=str(e))
    
    # 转换响应
    return RoutePlanResponse(
        source=result.source,
        success=result.success,
        origin=PointResponse(lon=result.origin.lon, lat=result.origin.lat),
        destination=PointResponse(lon=result.destination.lon, lat=result.destination.lat),
        total_distance_m=result.total_distance_m,
        total_duration_s=result.total_duration_s,
        segments=[
            RouteSegmentResponse(
                from_point=PointResponse(lon=s.from_point.lon, lat=s.from_point.lat),
                to_point=PointResponse(lon=s.to_point.lon, lat=s.to_point.lat),
                distance_m=s.distance_m,
                duration_s=s.duration_s,
                instruction=s.instruction,
                road_name=s.road_name,
            )
            for s in result.segments
        ],
        polyline=[
            PointResponse(lon=p.lon, lat=p.lat)
            for p in result.polyline
        ],
        error_message=result.error_message,
    )


@router.post("/plan-with-risk-check", response_model=RiskCheckRoutePlanResponse)
async def plan_route_with_risk_check(
    request: RiskCheckRoutePlanRequest,
    db: AsyncSession = Depends(get_db),
) -> RiskCheckRoutePlanResponse:
    """
    带风险检测的路径规划接口
    
    1. 先规划最快路径
    2. 检测是否穿过风险区域
    3. 如有风险，生成绕行方案并通过 WS 通知队长
    """
    logger.info(
        f"带风险检测的路径规划: device_id={request.device_id}, "
        f"scenario_id={request.scenario_id}"
    )
    
    # 初始化服务
    unified_service = UnifiedRoutePlanningService(db)
    risk_service = RiskDetectionService(db)
    alt_service = AlternativeRoutesService(db)
    
    origin = Point(lon=request.origin.lon, lat=request.origin.lat)
    destination = Point(lon=request.destination.lon, lat=request.destination.lat)
    
    # 1. 规划最快路径（不避障）
    try:
        fastest_result = await unified_service.plan_route(
            device_id=request.device_id,
            origin=origin,
            destination=destination,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    
    # 获取设备环境类型
    from src.domains.resources.devices.repository import DeviceRepository
    device_repo = DeviceRepository(db)
    device = await device_repo.get_by_id(request.device_id)
    env_type = device.env_type if device else "unknown"
    
    # 转换最快路径为响应格式
    fastest_route = RoutePlanResponse(
        source=fastest_result.source,
        success=fastest_result.success,
        origin=PointResponse(lon=fastest_result.origin.lon, lat=fastest_result.origin.lat),
        destination=PointResponse(lon=fastest_result.destination.lon, lat=fastest_result.destination.lat),
        total_distance_m=fastest_result.total_distance_m,
        total_duration_s=fastest_result.total_duration_s,
        segments=[
            RouteSegmentResponse(
                from_point=PointResponse(lon=s.from_point.lon, lat=s.from_point.lat),
                to_point=PointResponse(lon=s.to_point.lon, lat=s.to_point.lat),
                distance_m=s.distance_m,
                duration_s=s.duration_s,
                instruction=s.instruction,
                road_name=s.road_name,
            )
            for s in fastest_result.segments
        ],
        polyline=[
            PointResponse(lon=p.lon, lat=p.lat)
            for p in fastest_result.polyline
        ],
        error_message=fastest_result.error_message,
        env_type=env_type,
    )
    
    # 2. 检测风险区域
    risk_areas_info = await risk_service.detect_risk_areas(
        polyline=fastest_result.polyline,
        scenario_id=request.scenario_id,
    )
    
    has_risk = len(risk_areas_info) > 0
    risk_areas = [
        RiskAreaResponse(
            id=ra.id,
            name=ra.name,
            risk_level=ra.risk_level,
            passage_status=ra.passage_status,
            area_type=ra.area_type,
            description=ra.description,
        )
        for ra in risk_areas_info
    ]
    
    # 3. 如果无风险，直接返回
    if not has_risk:
        return RiskCheckRoutePlanResponse(
            fastest_route=fastest_route,
            has_risk=False,
            risk_areas=[],
            alternative_routes=[],
            requires_decision=False,
            available_actions=[],
            env_type=env_type,
        )
    
    # 4. 有风险，生成绕行方案（仅陆地设备）
    alternative_routes: List[AlternativeRouteResponse] = []
    available_actions = ["continue", "standby"]
    
    if env_type == "land":
        # 生成绕行方案
        risk_area_ids = [ra.id for ra in risk_areas_info]
        alternatives = await alt_service.generate_alternatives(
            origin=origin,
            destination=destination,
            risk_area_ids=risk_area_ids,
        )
        
        for alt in alternatives:
            alternative_routes.append(AlternativeRouteResponse(
                strategy=alt.strategy,
                strategy_name=alt.strategy_name,
                distance_m=alt.distance_m,
                duration_s=alt.duration_s,
                polyline=[PointResponse(lon=p.lon, lat=p.lat) for p in alt.polyline],
                description=alt.description,
            ))
            available_actions.append(f"detour_{alt.strategy}")
    
    # 判断是否需要决策
    max_risk_level = max(ra.risk_level for ra in risk_areas_info)
    requires_decision = max_risk_level >= 5 or any(
        ra.passage_status == "confirmed_blocked" for ra in risk_areas_info
    )
    
    # 5. 发送 STOMP 消息通知队长
    if requires_decision and request.team_id:
        try:
            await stomp_broker.broadcast_alert(
                alert_data={
                    "event_type": "route_risk_warning",
                    "task_id": str(request.task_id) if request.task_id else None,
                    "team_id": str(request.team_id),
                    "device_id": str(request.device_id),
                    "env_type": env_type,
                    "fastest_route": {
                        "distance_m": fastest_route.total_distance_m,
                        "duration_s": fastest_route.total_duration_s,
                    },
                    "risk_areas": [
                        {
                            "id": str(ra.id),
                            "name": ra.name,
                            "risk_level": ra.risk_level,
                            "passage_status": ra.passage_status,
                        }
                        for ra in risk_areas
                    ],
                    "alternative_routes": [
                        {
                            "strategy": ar.strategy,
                            "strategy_name": ar.strategy_name,
                            "distance_m": ar.distance_m,
                            "duration_s": ar.duration_s,
                        }
                        for ar in alternative_routes
                    ],
                    "available_actions": available_actions,
                    "requires_decision": requires_decision,
                },
                scenario_id=request.scenario_id,
            )
            logger.info(f"已发送路径风险预警 STOMP 消息: team_id={request.team_id}")
        except Exception as e:
            logger.error(f"发送 WS 消息失败: {e}", exc_info=True)
    
    return RiskCheckRoutePlanResponse(
        fastest_route=fastest_route,
        has_risk=True,
        risk_areas=risk_areas,
        alternative_routes=alternative_routes,
        requires_decision=requires_decision,
        available_actions=available_actions,
        env_type=env_type,
    )


@router.post("/confirm-route", response_model=ConfirmRouteResponse)
async def confirm_route(
    request: ConfirmRouteRequest,
    db: AsyncSession = Depends(get_db),
) -> ConfirmRouteResponse:
    """
    确认路径选择接口
    
    队长决策后调用此接口确认使用哪条路径
    """
    logger.info(
        f"确认路径选择: task_id={request.task_id}, action={request.action}"
    )
    
    action = request.action
    
    if action == "standby":
        return ConfirmRouteResponse(
            success=True,
            action=action,
            message="已选择原地待命，等待进一步指令",
        )
    
    if action == "continue":
        return ConfirmRouteResponse(
            success=True,
            action=action,
            message="已确认继续原路径（穿过风险区域）",
        )
    
    if action.startswith("detour_"):
        strategy = action.replace("detour_", "")
        strategy_names = {
            "recommended": "推荐绕行",
            "fastest": "最快绕行",
            "safest": "安全绕行",
        }
        strategy_name = strategy_names.get(strategy, strategy)
        
        return ConfirmRouteResponse(
            success=True,
            action=action,
            message=f"已确认使用「{strategy_name}」方案",
        )
    
    raise HTTPException(
        status_code=400,
        detail=f"无效的操作: {action}"
    )


# ============================================================================
# 路径存储和查询接口
# ============================================================================

def get_planned_route_service(db: AsyncSession = Depends(get_db)) -> PlannedRouteService:
    """依赖注入：获取规划路径服务"""
    return PlannedRouteService(db)


@router.post(
    "/plan-and-save",
    response_model=PlanAndSaveResponse,
    summary="规划并存储路径",
    description="规划路径并存储到数据库，可选进行风险检测",
)
async def plan_and_save_route(
    request: PlanAndSaveRequest,
    service: PlannedRouteService = Depends(get_planned_route_service),
) -> PlanAndSaveResponse:
    """
    规划并存储路径接口
    
    - 根据设备类型自动选择规划策略
    - 存储路径到 planned_routes_v2 表
    - 如提供 scenario_id，进行风险检测
    """
    logger.info(f"规划并存储路径: device_id={request.device_id}")
    
    origin = Point(lon=request.origin.lon, lat=request.origin.lat)
    destination = Point(lon=request.destination.lon, lat=request.destination.lat)
    
    try:
        result = await service.plan_and_save(
            device_id=request.device_id,
            origin=origin,
            destination=destination,
            task_id=request.task_id,
            team_id=request.team_id,
            vehicle_id=request.vehicle_id,
            scenario_id=request.scenario_id,
        )
        return PlanAndSaveResponse(**result)
    except ValueError as e:
        # 设备不存在等业务错误
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        # 水上路径规划暂未实现
        raise HTTPException(status_code=501, detail=str(e))


@router.post(
    "/alternative-routes",
    response_model=GenerateAlternativesResponse,
    summary="生成绕行方案",
    description="生成3个绕行方案并存储到数据库",
)
async def generate_alternative_routes(
    request: GenerateAlternativesRequest,
    service: PlannedRouteService = Depends(get_planned_route_service),
) -> GenerateAlternativesResponse:
    """
    生成绕行方案接口
    
    - 推荐绕行（综合最优）
    - 最快绕行（时间优先）
    - 安全绕行（远离风险区域）
    """
    logger.info(
        f"生成绕行方案: task_id={request.task_id}, "
        f"避让区域数={len(request.risk_area_ids)}"
    )
    
    origin = Point(lon=request.origin.lon, lat=request.origin.lat)
    destination = Point(lon=request.destination.lon, lat=request.destination.lat)
    
    result = await service.generate_and_save_alternatives(
        task_id=request.task_id,
        origin=origin,
        destination=destination,
        risk_area_ids=request.risk_area_ids,
        team_id=request.team_id,
        vehicle_id=request.vehicle_id,
    )
    
    return GenerateAlternativesResponse(**result)


@router.post(
    "/confirm-route-by-id",
    response_model=ConfirmRouteResponse,
    summary="按ID确认路径",
    description="确认使用某条路径，将其他路径设为已替换或已取消",
)
async def confirm_route_by_id(
    request: ConfirmRouteByIdRequest,
    service: PlannedRouteService = Depends(get_planned_route_service),
) -> ConfirmRouteResponse:
    """
    按ID确认路径接口
    
    确认使用某条路径后：
    - 选中的路径设为 active
    - 原有 active 路径设为 replaced
    - 其他 alternative 路径设为 cancelled
    """
    logger.info(f"确认路径: route_id={request.route_id}, task_id={request.task_id}")
    
    result = await service.confirm_route(
        route_id=request.route_id,
        task_id=request.task_id,
    )
    
    return ConfirmRouteResponse(
        success=result["success"],
        action="confirm_by_id",
        message=result.get("message", result.get("error", "")),
    )


@router.get(
    "/routes/{task_id}",
    response_model=PlannedRouteListResponse,
    summary="查询任务路径",
    description="查询任务的所有路径，包括活跃路径和绕行方案",
)
async def get_routes_by_task(
    task_id: str,
    include_alternatives: bool = True,
    service: PlannedRouteService = Depends(get_planned_route_service),
) -> PlannedRouteListResponse:
    """
    查询任务路径接口
    
    返回任务关联的所有路径，支持筛选是否包含绕行方案
    """
    from uuid import UUID
    
    logger.info(f"查询任务路径: task_id={task_id}")
    
    routes = await service.get_routes_by_task(
        task_id=UUID(task_id),
        include_alternatives=include_alternatives,
    )
    
    route_responses = []
    for route in routes:
        polyline = [
            PointResponse(lon=p["lon"], lat=p["lat"])
            for p in route.get("polyline", [])
        ]
        route_responses.append(PlannedRouteResponse(
            route_id=route["route_id"],
            task_id=route.get("task_id"),
            vehicle_id=route.get("vehicle_id"),
            team_id=route.get("team_id"),
            total_distance_m=route["total_distance_m"],
            estimated_time_minutes=route["estimated_time_minutes"],
            risk_level=route.get("risk_level", 1),
            status=route["status"],
            planned_at=route.get("planned_at"),
            properties=route.get("properties", {}),
            polyline=polyline,
        ))
    
    return PlannedRouteListResponse(
        routes=route_responses,
        total=len(route_responses),
    )


@router.get(
    "/routes/{task_id}/active",
    response_model=PlannedRouteResponse,
    summary="获取任务活跃路径",
    description="获取任务当前活跃（正在使用）的路径",
)
async def get_active_route(
    task_id: str,
    service: PlannedRouteService = Depends(get_planned_route_service),
) -> PlannedRouteResponse:
    """
    获取任务活跃路径接口
    
    返回任务当前活跃的路径（status=active）
    """
    from uuid import UUID
    
    logger.info(f"获取活跃路径: task_id={task_id}")
    
    route = await service.get_active_route(UUID(task_id))
    
    if not route:
        raise HTTPException(
            status_code=404,
            detail=f"任务 {task_id} 没有活跃路径",
        )
    
    polyline = [
        PointResponse(lon=p["lon"], lat=p["lat"])
        for p in route.get("polyline", [])
    ]
    
    return PlannedRouteResponse(
        route_id=route["route_id"],
        task_id=route.get("task_id"),
        vehicle_id=route.get("vehicle_id"),
        team_id=route.get("team_id"),
        total_distance_m=route["total_distance_m"],
        estimated_time_minutes=route["estimated_time_minutes"],
        risk_level=route.get("risk_level", 1),
        status=route["status"],
        planned_at=route.get("planned_at"),
        properties=route.get("properties", {}),
        polyline=polyline,
    )
