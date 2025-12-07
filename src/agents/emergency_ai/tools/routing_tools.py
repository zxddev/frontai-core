"""
路径规划工具

封装路径规划服务，为应急AI提供真实路径距离和行驶时间计算。
支持避障规划（绕过灾害区域、危险区域）。
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.domains.routing.service import RoutePlanningService
from src.domains.routing.schemas import Point, AvoidArea, RouteResult

logger = logging.getLogger(__name__)

# 路径规划超时时间（秒）
ROUTING_TIMEOUT_SECONDS = 10.0

# 默认车速（km/h），用于估算模式
DEFAULT_SPEED_KMH = 40.0

# ETA计算是否使用直线估算（跳过路径规划API，节省费用）
# 设置 ETA_USE_STRAIGHT_LINE=false 可启用真实路径规划
ETA_USE_STRAIGHT_LINE = os.environ.get("ETA_USE_STRAIGHT_LINE", "true").lower() == "true"


@dataclass
class ETAResult:
    """ETA 计算结果"""
    response_time_minutes: float      # 队伍集结时间
    travel_time_minutes: float        # 行驶时间
    eta_minutes: float                # 总到达时间
    route_distance_km: float          # 路径距离（km）
    route_source: str                 # 路径来源: amap/internal/estimate
    success: bool                     # 是否成功
    error_message: Optional[str] = None
    polyline: Optional[List[Point]] = None  # 路径坐标点（可选）
    avoided_areas: Optional[List[str]] = None  # 绕行的区域名称


async def calculate_team_eta_with_routing(
    team: Dict[str, Any],
    event_lat: float,
    event_lng: float,
    scenario_id: Optional[UUID] = None,
    avoid_areas: Optional[List[AvoidArea]] = None,
) -> ETAResult:
    """
    使用真实路径规划计算队伍 ETA
    
    流程:
    1. 获取队伍基地坐标
    2. 调用路径规划服务获取真实路径
    3. 计算: 总 ETA = 响应时间 + 路径行驶时间
    
    注意: 每次调用会创建独立的数据库会话，支持并发调用。
    
    Args:
        team: 队伍信息字典，需包含 base_lat, base_lng, response_time_minutes
        event_lat: 事件纬度
        event_lng: 事件经度
        scenario_id: 想定ID（用于查询灾害区域）
        avoid_areas: 额外的避让区域列表
        
    Returns:
        ETAResult: ETA 计算结果
    """
    team_name = team.get("name", "未知队伍")
    base_lat = team.get("base_lat")
    base_lng = team.get("base_lng")
    
    # 队伍响应时间（集结时间）
    response_time_minutes = float(team.get("response_time_minutes") or 5)
    
    # 验证坐标
    if not base_lat or not base_lng:
        logger.warning(f"[路径规划] 队伍 {team_name} 缺少基地坐标，使用估算模式")
        return _fallback_estimate(team, event_lat, event_lng, response_time_minutes, "缺少基地坐标")
    
    # 直线估算模式（跳过路径规划API，节省费用）
    if ETA_USE_STRAIGHT_LINE:
        logger.debug(f"[ETA估算] 队伍 {team_name} 使用直线估算模式")
        return _fallback_estimate(team, event_lat, event_lng, response_time_minutes, "直线估算模式")
    
    origin = Point(lon=base_lng, lat=base_lat)
    destination = Point(lon=event_lng, lat=event_lat)
    
    import time
    route_start_time = time.perf_counter()
    
    try:
        # 每个任务创建独立的数据库会话，避免并发时会话共享问题
        async with AsyncSessionLocal() as db:
            # 创建路径规划服务
            routing_service = RoutePlanningService(db)
            
            logger.debug(
                f"[路径规划] 开始 队伍={team_name} "
                f"起点=({base_lng:.4f},{base_lat:.4f}) 终点=({event_lng:.4f},{event_lat:.4f}) "
                f"超时={ROUTING_TIMEOUT_SECONDS}秒"
            )
            
            # 异步调用路径规划（带超时）
            if avoid_areas:
                route_task = routing_service.plan_route_with_avoidance(
                    origin=origin,
                    destination=destination,
                    avoid_areas=avoid_areas,
                )
            else:
                route_task = routing_service.plan_route(
                    origin=origin,
                    destination=destination,
                )
            
            route_result: RouteResult = await asyncio.wait_for(
                route_task,
                timeout=ROUTING_TIMEOUT_SECONDS,
            )
        
        elapsed_ms = (time.perf_counter() - route_start_time) * 1000
        
        if not route_result.success:
            logger.warning(
                f"[路径规划] 队伍 {team_name} 规划失败(耗时{elapsed_ms:.0f}ms): "
                f"{route_result.error_message}，使用估算模式"
            )
            return _fallback_estimate(team, event_lat, event_lng, response_time_minutes, route_result.error_message)
        
        # 从路径结果计算 ETA
        travel_time_minutes = route_result.total_duration_min
        route_distance_km = route_result.total_distance_km
        eta_minutes = response_time_minutes + travel_time_minutes
        
        logger.debug(
            f"[路径规划] {team_name} 成功(耗时{elapsed_ms:.0f}ms): 距离={route_distance_km:.2f}km, "
            f"行驶={travel_time_minutes:.1f}分钟, 响应={response_time_minutes:.1f}分钟, "
            f"总ETA={eta_minutes:.1f}分钟, 来源={route_result.source}"
        )
        
        return ETAResult(
            response_time_minutes=response_time_minutes,
            travel_time_minutes=travel_time_minutes,
            eta_minutes=eta_minutes,
            route_distance_km=route_distance_km,
            route_source=route_result.source,
            success=True,
            polyline=route_result.polyline if route_result.polyline else None,
        )
        
    except asyncio.TimeoutError:
        elapsed_ms = (time.perf_counter() - route_start_time) * 1000
        logger.warning(
            f"[路径规划] 队伍 {team_name} 规划超时(耗时{elapsed_ms:.0f}ms, 超时阈值{ROUTING_TIMEOUT_SECONDS}秒)，"
            f"起点=({base_lng:.4f},{base_lat:.4f}) 终点=({event_lng:.4f},{event_lat:.4f})，使用估算模式"
        )
        return _fallback_estimate(team, event_lat, event_lng, response_time_minutes, f"路径规划超时({elapsed_ms:.0f}ms)")
    except Exception as e:
        elapsed_ms = (time.perf_counter() - route_start_time) * 1000
        logger.warning(
            f"[路径规划] 队伍 {team_name} 规划异常(耗时{elapsed_ms:.0f}ms): {e}，使用估算模式"
        )
        return _fallback_estimate(team, event_lat, event_lng, response_time_minutes, str(e))


async def batch_calculate_team_etas(
    teams: List[Dict[str, Any]],
    event_lat: float,
    event_lng: float,
    scenario_id: Optional[UUID] = None,
    avoid_areas: Optional[List[AvoidArea]] = None,
    max_concurrent: int = 10,
) -> Dict[str, ETAResult]:
    """
    批量计算多个队伍的 ETA（并行请求）
    
    每个子任务会创建独立的数据库会话，避免并发时会话共享导致的事务问题。
    
    Args:
        teams: 队伍信息列表
        event_lat: 事件纬度
        event_lng: 事件经度
        scenario_id: 想定ID
        avoid_areas: 避让区域列表
        max_concurrent: 最大并发数
        
    Returns:
        Dict[team_id, ETAResult]: 队伍ID到ETA结果的映射
    """
    if not teams:
        return {}
    
    logger.info(f"[路径规划] 批量计算 {len(teams)} 个队伍的 ETA")
    
    # 使用信号量控制并发
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def calculate_with_semaphore(team: Dict[str, Any]) -> tuple[str, ETAResult]:
        async with semaphore:
            team_id = team.get("id", "unknown")
            # 每个子任务内部会创建独立的数据库会话
            result = await calculate_team_eta_with_routing(
                team=team,
                event_lat=event_lat,
                event_lng=event_lng,
                scenario_id=scenario_id,
                avoid_areas=avoid_areas,
            )
            return team_id, result
    
    # 并行执行
    tasks = [calculate_with_semaphore(team) for team in teams]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果
    eta_map: Dict[str, ETAResult] = {}
    success_count = 0
    fallback_count = 0
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            team = teams[i]
            team_id = team.get("id", "unknown")
            response_time = float(team.get("response_time_minutes") or 5)
            eta_map[team_id] = _fallback_estimate(
                team, event_lat, event_lng, response_time, str(result)
            )
            fallback_count += 1
        else:
            team_id, eta_result = result
            eta_map[team_id] = eta_result
            if eta_result.route_source == "estimate":
                fallback_count += 1
            else:
                success_count += 1
    
    logger.info(
        f"[路径规划] 批量计算完成: 成功={success_count}, 估算={fallback_count}"
    )
    
    return eta_map


def _fallback_estimate(
    team: Dict[str, Any],
    event_lat: float,
    event_lng: float,
    response_time_minutes: float,
    error_message: str,
) -> ETAResult:
    """
    降级估算模式：使用直线距离 × 道路系数估算
    
    当路径规划失败时使用此方法作为后备。
    """
    import math
    
    base_lat = team.get("base_lat")
    base_lng = team.get("base_lng")
    
    if not base_lat or not base_lng:
        # 无坐标，使用默认值
        return ETAResult(
            response_time_minutes=response_time_minutes,
            travel_time_minutes=10.0,  # 默认10分钟
            eta_minutes=response_time_minutes + 10.0,
            route_distance_km=0.0,
            route_source="estimate",
            success=False,
            error_message=error_message,
        )
    
    # Haversine 计算直线距离
    R = 6371  # 地球半径（km）
    lat1, lon1 = math.radians(base_lat), math.radians(base_lng)
    lat2, lon2 = math.radians(event_lat), math.radians(event_lng)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    straight_distance_km = R * c
    
    # 道路系数（山区使用较高系数）
    road_factor = 1.4
    road_distance_km = straight_distance_km * road_factor
    
    # 行驶时间估算
    speed_kmh = team.get("actual_speed_kmh") or DEFAULT_SPEED_KMH
    travel_time_minutes = (road_distance_km / speed_kmh) * 60
    
    eta_minutes = response_time_minutes + travel_time_minutes
    
    return ETAResult(
        response_time_minutes=response_time_minutes,
        travel_time_minutes=round(travel_time_minutes, 1),
        eta_minutes=round(eta_minutes, 1),
        route_distance_km=round(road_distance_km, 2),
        route_source="estimate",
        success=False,
        error_message=error_message,
    )


async def get_disaster_avoid_areas(
    db: AsyncSession,
    scenario_id: UUID,
) -> List[AvoidArea]:
    """
    获取想定关联的灾害区域作为避让区域
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        
    Returns:
        避让区域列表
    """
    from sqlalchemy import text
    
    sql = text("""
        SELECT 
            id,
            name,
            risk_level,
            passage_status,
            ST_AsGeoJSON(geometry)::json as geometry_json
        FROM operational_v2.disaster_affected_areas_v2
        WHERE scenario_id = :scenario_id
        AND (
            passage_status = 'confirmed_blocked'
            OR (passable = false AND COALESCE(passage_status, 'unknown') = 'unknown')
        )
        AND (estimated_end_at IS NULL OR estimated_end_at > now())
    """)
    
    try:
        result = await db.execute(sql, {"scenario_id": scenario_id})
        rows = result.fetchall()
        
        avoid_areas: List[AvoidArea] = []
        for row in rows:
            geometry_json = row.geometry_json
            if geometry_json and geometry_json.get("type") == "Polygon":
                coords = geometry_json.get("coordinates", [[]])[0]
                polygon_points = [Point(lon=c[0], lat=c[1]) for c in coords]
                avoid_areas.append(AvoidArea(
                    polygon=polygon_points,
                    reason=row.name or "灾害区域",
                    severity="hard",
                ))
        
        logger.info(f"[路径规划] 加载 {len(avoid_areas)} 个灾害避让区域")
        return avoid_areas
        
    except Exception as e:
        logger.error(f"[路径规划] 加载灾害区域失败: {e}")
        return []


async def get_danger_area_avoid_areas(
    db: AsyncSession,
) -> List[AvoidArea]:
    """
    获取前端绘制的危险区域作为避让区域
    
    Args:
        db: 数据库会话
        
    Returns:
        避让区域列表
    """
    from sqlalchemy import text
    
    sql = text("""
        SELECT 
            id,
            COALESCE(properties->>'name', '危险区域') as name,
            COALESCE((properties->>'risk_level')::int, 5) as risk_level,
            ST_AsGeoJSON(geometry)::json as geometry_json
        FROM operational_v2.entities_v2
        WHERE type = 'danger_area'
    """)
    
    try:
        result = await db.execute(sql)
        rows = result.fetchall()
        
        avoid_areas: List[AvoidArea] = []
        for row in rows:
            geometry_json = row.geometry_json
            if geometry_json and geometry_json.get("type") == "Polygon":
                coords = geometry_json.get("coordinates", [[]])[0]
                polygon_points = [Point(lon=c[0], lat=c[1]) for c in coords]
                avoid_areas.append(AvoidArea(
                    polygon=polygon_points,
                    reason=row.name or "危险区域",
                    severity="hard" if row.risk_level >= 4 else "soft",
                ))
        
        logger.info(f"[路径规划] 加载 {len(avoid_areas)} 个危险避让区域")
        return avoid_areas
        
    except Exception as e:
        logger.error(f"[路径规划] 加载危险区域失败: {e}")
        return []
