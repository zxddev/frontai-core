"""
高德地图路径规划API工具

提供普通路径规划和避障路径规划两个工具。
API文档: https://lbs.amap.com/api/webservice/guide/api/newroute
"""
from __future__ import annotations

import logging
import httpx
from typing import Dict, Any, List, Optional

from langchain_core.tools import tool

from src.infra.settings import load_settings

logger = logging.getLogger(__name__)

# API配置
AMAP_API_BASE_URL = "https://restapi.amap.com/v5/direction/driving"
DEFAULT_TIMEOUT = 30.0

# 缓存settings实例
_settings = None


def _get_amap_key() -> str:
    """从配置文件获取高德API Key"""
    global _settings
    if _settings is None:
        _settings = load_settings()
    key = _settings.amap_api_key
    if not key:
        raise ValueError("缺少 AMAP_API_KEY 配置，请在 config/private.yaml 中配置")
    return key


def _format_coordinate(lon: float, lat: float) -> str:
    """格式化经纬度坐标为高德API格式"""
    return f"{lon:.6f},{lat:.6f}"


def _format_avoidpolygons(polygons: List[List[tuple]]) -> str:
    """
    格式化避障多边形为高德API格式
    
    Args:
        polygons: 多边形列表，每个多边形是坐标点列表 [(lon1,lat1), (lon2,lat2), ...]
        
    Returns:
        格式化字符串，多边形用"|"分隔，点用";"分隔
    """
    formatted_polygons = []
    for polygon in polygons:
        points = [f"{lon:.6f},{lat:.6f}" for lon, lat in polygon]
        formatted_polygons.append(";".join(points))
    return "|".join(formatted_polygons)


def _parse_route_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """解析高德API返回的路径规划结果"""
    if data.get("status") != "1":
        error_info = data.get("info", "未知错误")
        error_code = data.get("infocode", "")
        raise RuntimeError(f"高德API返回错误: {error_info} (code: {error_code})")
    
    route = data.get("route", {})
    paths = route.get("paths", [])
    
    result = {
        "origin": route.get("origin"),
        "destination": route.get("destination"),
        "taxi_cost": route.get("taxi_cost"),
        "paths": [],
    }
    
    for path in paths:
        path_info = {
            "distance": int(path.get("distance", 0)),
            "duration": int(path.get("duration", 0)),
            "restriction": path.get("restriction", "0"),
            "steps": [],
        }
        
        # 提取路段信息
        for step in path.get("steps", []):
            step_info = {
                "instruction": step.get("instruction", ""),
                "road_name": step.get("road_name", ""),
                "step_distance": int(step.get("step_distance", 0)),
                "orientation": step.get("orientation", ""),
                "polyline": step.get("polyline", ""),  # 路径坐标点
            }
            path_info["steps"].append(step_info)
        
        result["paths"].append(path_info)
    
    return result


@tool
def amap_route_planning(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    strategy: int = 32,
    waypoints: Optional[List[tuple]] = None,
    plate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    高德地图普通路径规划。
    
    根据起终点坐标规划驾车路线，返回最优路径方案。
    
    Args:
        origin_lon: 起点经度
        origin_lat: 起点纬度
        dest_lon: 终点经度
        dest_lat: 终点纬度
        strategy: 算路策略
            32: 默认(高德推荐)
            33: 躲避拥堵
            34: 高速优先
            35: 不走高速
            36: 少收费
            38: 速度最快
        waypoints: 途经点列表 [(lon1,lat1), (lon2,lat2), ...]，最多16个
        plate: 车牌号(如"京AHA322")，用于限行规避
        
    Returns:
        路径规划结果：
        - origin: 起点坐标
        - destination: 终点坐标
        - taxi_cost: 预计打车费用(元)
        - paths: 路径方案列表
            - distance: 距离(米)
            - duration: 耗时(秒)
            - restriction: 限行状态(0=无限行, 1=有限行)
            - steps: 路段详情列表
    """
    logger.info(
        "调用高德普通路径规划",
        extra={
            "origin": f"{origin_lon},{origin_lat}",
            "destination": f"{dest_lon},{dest_lat}",
            "strategy": strategy,
        }
    )
    
    params = {
        "key": _get_amap_key(),
        "origin": _format_coordinate(origin_lon, origin_lat),
        "destination": _format_coordinate(dest_lon, dest_lat),
        "strategy": str(strategy),
        "show_fields": "cost,polyline",
    }
    
    if waypoints:
        wp_str = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in waypoints[:16]])
        params["waypoints"] = wp_str
    
    if plate:
        params["plate"] = plate
    
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(AMAP_API_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error("高德API请求失败", extra={"error": str(e)})
        raise RuntimeError(f"高德API请求失败: {e}") from e
    
    result = _parse_route_response(data)
    logger.info(
        "高德路径规划完成",
        extra={
            "paths_count": len(result["paths"]),
            "distance": result["paths"][0]["distance"] if result["paths"] else 0,
        }
    )
    return result


@tool
def amap_route_planning_with_avoidance(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    avoid_polygons: List[List[tuple]],
    strategy: int = 32,
    waypoints: Optional[List[tuple]] = None,
    plate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    高德地图避障路径规划。
    
    根据起终点坐标和避障区域规划驾车路线，自动规避指定的危险区域。
    
    Args:
        origin_lon: 起点经度
        origin_lat: 起点纬度
        dest_lon: 终点经度
        dest_lat: 终点纬度
        avoid_polygons: 避让区域列表，每个区域是多边形坐标点列表
            格式: [[(lon1,lat1), (lon2,lat2), ...], [...]]
            - 最多支持32个避让区域
            - 每个区域最多16个顶点
            - 每个区域不能超过81平方公里
        strategy: 算路策略
            32: 默认(高德推荐)
            33: 躲避拥堵
            34: 高速优先
            35: 不走高速
            36: 少收费
            38: 速度最快
        waypoints: 途经点列表 [(lon1,lat1), (lon2,lat2), ...]，最多16个
        plate: 车牌号(如"京AHA322")，用于限行规避
        
    Returns:
        路径规划结果：
        - origin: 起点坐标
        - destination: 终点坐标
        - taxi_cost: 预计打车费用(元)
        - paths: 路径方案列表
            - distance: 距离(米)
            - duration: 耗时(秒)
            - restriction: 限行状态(0=无限行, 1=有限行)
            - steps: 路段详情列表
    """
    logger.info(
        "调用高德避障路径规划",
        extra={
            "origin": f"{origin_lon},{origin_lat}",
            "destination": f"{dest_lon},{dest_lat}",
            "avoid_polygons_count": len(avoid_polygons),
            "strategy": strategy,
        }
    )
    
    # 验证避障区域数量
    if len(avoid_polygons) > 32:
        logger.warning("避障区域超过32个，截取前32个")
        avoid_polygons = avoid_polygons[:32]
    
    params = {
        "key": _get_amap_key(),
        "origin": _format_coordinate(origin_lon, origin_lat),
        "destination": _format_coordinate(dest_lon, dest_lat),
        "strategy": str(strategy),
        "show_fields": "cost,polyline",
    }
    
    # 添加避障区域
    if avoid_polygons:
        params["avoidpolygons"] = _format_avoidpolygons(avoid_polygons)
    
    if waypoints:
        wp_str = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in waypoints[:16]])
        params["waypoints"] = wp_str
    
    if plate:
        params["plate"] = plate
    
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(AMAP_API_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error("高德API请求失败", extra={"error": str(e)})
        raise RuntimeError(f"高德API请求失败: {e}") from e
    
    result = _parse_route_response(data)
    logger.info(
        "高德避障路径规划完成",
        extra={
            "paths_count": len(result["paths"]),
            "distance": result["paths"][0]["distance"] if result["paths"] else 0,
        }
    )
    return result


# 异步版本供智能体节点直接调用

async def amap_route_planning_async(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    strategy: int = 32,
    waypoints: Optional[List[tuple]] = None,
    plate: Optional[str] = None,
) -> Dict[str, Any]:
    """异步版本的高德普通路径规划"""
    logger.info(
        "调用高德普通路径规划(异步)",
        extra={
            "origin": f"{origin_lon},{origin_lat}",
            "destination": f"{dest_lon},{dest_lat}",
        }
    )
    
    params = {
        "key": _get_amap_key(),
        "origin": _format_coordinate(origin_lon, origin_lat),
        "destination": _format_coordinate(dest_lon, dest_lat),
        "strategy": str(strategy),
        "show_fields": "cost,polyline",
    }
    
    if waypoints:
        wp_str = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in waypoints[:16]])
        params["waypoints"] = wp_str
    
    if plate:
        params["plate"] = plate
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(AMAP_API_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error("高德API请求失败", extra={"error": str(e)})
        raise RuntimeError(f"高德API请求失败: {e}") from e
    
    return _parse_route_response(data)


async def amap_route_planning_with_avoidance_async(
    origin_lon: float,
    origin_lat: float,
    dest_lon: float,
    dest_lat: float,
    avoid_polygons: List[List[tuple]],
    strategy: int = 32,
    waypoints: Optional[List[tuple]] = None,
    plate: Optional[str] = None,
) -> Dict[str, Any]:
    """异步版本的高德避障路径规划"""
    logger.info(
        "调用高德避障路径规划(异步)",
        extra={
            "origin": f"{origin_lon},{origin_lat}",
            "destination": f"{dest_lon},{dest_lat}",
            "avoid_polygons_count": len(avoid_polygons),
        }
    )
    
    if len(avoid_polygons) > 32:
        avoid_polygons = avoid_polygons[:32]
    
    params = {
        "key": _get_amap_key(),
        "origin": _format_coordinate(origin_lon, origin_lat),
        "destination": _format_coordinate(dest_lon, dest_lat),
        "strategy": str(strategy),
        "show_fields": "cost,polyline",
    }
    
    if avoid_polygons:
        params["avoidpolygons"] = _format_avoidpolygons(avoid_polygons)
    
    if waypoints:
        wp_str = ";".join([f"{lon:.6f},{lat:.6f}" for lon, lat in waypoints[:16]])
        params["waypoints"] = wp_str
    
    if plate:
        params["plate"] = plate
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(AMAP_API_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.error("高德API请求失败", extra={"error": str(e)})
        raise RuntimeError(f"高德API请求失败: {e}") from e
    
    return _parse_route_response(data)
