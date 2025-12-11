"""
高德地图API客户端

提供路径规划、地理编码、POI搜索等服务。
"""
from .route_planning import (
    amap_route_planning,
    amap_route_planning_with_avoidance,
    amap_route_planning_async,
    amap_route_planning_with_avoidance_async,
)
from .geocode import amap_geocode, amap_geocode_async
from .poi_search import (
    search_poi_around,
    search_poi_polygon,
    search_poi_text,
    POIResult,
    STAGING_POI_TYPES,
    get_site_type_from_poi_code,
)

__all__ = [
    # 路径规划
    "amap_route_planning",
    "amap_route_planning_with_avoidance",
    "amap_route_planning_async",
    "amap_route_planning_with_avoidance_async",
    # 地理编码
    "amap_geocode",
    "amap_geocode_async",
    # POI搜索
    "search_poi_around",
    "search_poi_polygon",
    "search_poi_text",
    "POIResult",
    "STAGING_POI_TYPES",
    "get_site_type_from_poi_code",
]
