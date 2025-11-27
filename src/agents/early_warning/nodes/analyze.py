"""
影响分析节点

检测车辆和救援队伍是否在预警范围内或路径受影响。
"""
import logging
import math
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..state import EarlyWarningState, AffectedObject, Point, Polygon

logger = logging.getLogger(__name__)

# 地球半径（米）
EARTH_RADIUS_M = 6371000


def analyze_impact(state: EarlyWarningState) -> Dict[str, Any]:
    """
    分析灾害对车辆和队伍的影响
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段（affected_vehicles, affected_teams）
    """
    logger.info(f"[analyze] Analyzing impact for request {state['request_id']}")
    
    disaster = state.get("disaster_situation")
    if not disaster:
        logger.warning("[analyze] No disaster situation to analyze")
        return {
            "current_phase": "analyze",
            "affected_vehicles": [],
            "affected_teams": [],
        }
    
    scenario_id = state.get("scenario_id") or disaster.get("scenario_id")
    buffer_distance_m = disaster.get("buffer_distance_m", 3000)
    
    affected_vehicles: List[AffectedObject] = []
    affected_teams: List[AffectedObject] = []
    
    try:
        # 获取车辆和队伍数据（这里使用模拟数据，实际应查询数据库）
        vehicles = _get_vehicles_in_scenario(scenario_id)
        teams = _get_teams_in_scenario(scenario_id)
        
        # 分析车辆
        for vehicle in vehicles:
            affected = _analyze_object_impact(
                obj_type="vehicle",
                obj_id=vehicle["id"],
                obj_name=vehicle["name"],
                obj_location=vehicle["location"],
                obj_route=vehicle.get("planned_route"),
                disaster=disaster,
                buffer_distance_m=buffer_distance_m,
                notify_target_type="commander",
                notify_target_id=vehicle.get("commander_id"),
                notify_target_name=vehicle.get("commander_name"),
            )
            if affected:
                affected_vehicles.append(affected)
        
        # 分析队伍
        for team in teams:
            affected = _analyze_object_impact(
                obj_type="team",
                obj_id=team["id"],
                obj_name=team["name"],
                obj_location=team["location"],
                obj_route=team.get("planned_route"),
                disaster=disaster,
                buffer_distance_m=buffer_distance_m,
                notify_target_type="team_leader",
                notify_target_id=team.get("leader_id"),
                notify_target_name=team.get("leader_name"),
            )
            if affected:
                affected_teams.append(affected)
        
        logger.info(
            f"[analyze] Found {len(affected_vehicles)} affected vehicles, "
            f"{len(affected_teams)} affected teams"
        )
        
        # 更新trace
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["analyze"]
        trace["analyze_time"] = datetime.utcnow().isoformat()
        trace["vehicles_checked"] = len(vehicles)
        trace["teams_checked"] = len(teams)
        
        return {
            "affected_vehicles": affected_vehicles,
            "affected_teams": affected_teams,
            "current_phase": "analyze",
            "trace": trace,
        }
        
    except Exception as e:
        logger.error(f"[analyze] Error analyzing impact: {e}")
        return {
            "current_phase": "analyze",
            "affected_vehicles": [],
            "affected_teams": [],
            "errors": state.get("errors", []) + [f"Analyze error: {str(e)}"],
        }


def _analyze_object_impact(
    obj_type: str,
    obj_id: str,
    obj_name: str,
    obj_location: Point,
    obj_route: Optional[List[Point]],
    disaster: Dict,
    buffer_distance_m: int,
    notify_target_type: str,
    notify_target_id: Optional[str],
    notify_target_name: Optional[str],
) -> Optional[AffectedObject]:
    """分析单个对象是否受影响"""
    
    # 计算到灾害中心的距离
    center = disaster.get("center_point", {})
    distance_m = _haversine_distance(
        obj_location.get("lon", 0),
        obj_location.get("lat", 0),
        center.get("lon", 0),
        center.get("lat", 0),
    )
    
    # 检查是否在缓冲区内
    in_buffer = distance_m <= buffer_distance_m
    
    # 检查路径是否穿过灾害区域
    route_affected = False
    route_intersection = None
    if obj_route:
        route_affected, route_intersection = _check_route_intersection(
            obj_route, disaster.get("boundary", {})
        )
    
    # 如果在缓冲区内或路径受影响，则为受影响对象
    if in_buffer or route_affected:
        # 计算预计接触时间（假设平均速度30km/h）
        estimated_minutes = None
        if distance_m > 0:
            speed_mps = 30 * 1000 / 3600  # 30km/h转m/s
            estimated_minutes = int(distance_m / speed_mps / 60)
        
        return AffectedObject(
            object_type=obj_type,
            object_id=obj_id,
            object_name=obj_name,
            current_location=obj_location,
            distance_to_disaster_m=distance_m,
            estimated_contact_minutes=estimated_minutes,
            route_affected=route_affected,
            route_intersection_point=route_intersection,
            notify_target_type=notify_target_type,
            notify_target_id=notify_target_id,
            notify_target_name=notify_target_name,
        )
    
    return None


def _haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    计算两点间的距离（米）- Haversine公式
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_M * c


def _check_route_intersection(
    route: List[Point],
    boundary: Polygon,
) -> tuple[bool, Optional[Point]]:
    """
    检查路径是否与灾害边界相交
    
    简化实现：检查路径点是否在多边形内
    实际应使用Shapely等库进行精确计算
    """
    coords = boundary.get("coordinates", [])
    if not coords or not coords[0]:
        return False, None
    
    polygon = coords[0]
    
    for point in route:
        lon = point.get("lon", 0)
        lat = point.get("lat", 0)
        if _point_in_polygon(lon, lat, polygon):
            return True, Point(lon=lon, lat=lat)
    
    return False, None


def _point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
    """
    射线法判断点是否在多边形内
    """
    n = len(polygon)
    inside = False
    
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    
    return inside


def _get_vehicles_in_scenario(scenario_id: Optional[str]) -> List[Dict]:
    """
    获取场景中的车辆数据（同步查询）
    
    注：车辆位置数据暂未完善，返回空列表
    """
    # 车辆需要关联map_entities表获取位置，当前数据不完整
    return []


def _get_teams_in_scenario(scenario_id: Optional[str]) -> List[Dict]:
    """
    获取场景中的救援队伍数据（同步查询）
    """
    import asyncio
    from sqlalchemy import text
    from src.core.database import AsyncSessionLocal
    
    async def _query():
        async with AsyncSessionLocal() as session:
            # 查询有位置信息的队伍
            result = await session.execute(text('''
                SELECT 
                    t.id::text,
                    t.name,
                    t.code,
                    t.contact_person,
                    ST_X(t.base_location::geometry) as lon,
                    ST_Y(t.base_location::geometry) as lat
                FROM operational_v2.rescue_teams_v2 t
                WHERE t.base_location IS NOT NULL
                LIMIT 100
            '''))
            rows = result.fetchall()
            
            teams = []
            for row in rows:
                teams.append({
                    "id": row[0],
                    "name": row[1] or row[2],
                    "location": {"lon": float(row[4]) if row[4] else 0, "lat": float(row[5]) if row[5] else 0},
                    "leader_id": None,
                    "leader_name": row[3] or "负责人",
                })
            return teams
    
    try:
        loop = asyncio.get_running_loop()
        return []
    except RuntimeError:
        return asyncio.run(_query())
