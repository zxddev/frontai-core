"""
高德POI搜索客户端

用于采集救援驻扎点候选数据。
支持周边搜索和多边形区域搜索。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from src.infra.settings import load_settings

logger = logging.getLogger(__name__)

# 高德POI搜索API（V5版本）
AMAP_POI_AROUND_URL = "https://restapi.amap.com/v5/place/around"
AMAP_POI_POLYGON_URL = "https://restapi.amap.com/v5/place/polygon"
AMAP_POI_TEXT_URL = "https://restapi.amap.com/v5/place/text"

# 适合作为驻扎点的POI类型（开阔场地）
# 参考高德POI分类编码表: https://lbs.amap.com/api/webservice/download
# 依据GB 51143-2015《防灾避难场所设计规范》，应选择开阔场地，远离建筑物
STAGING_POI_TYPES: Dict[str, str] = {
    # 科教文化服务 - 仅保留大学和中学（通常有较大操场）
    # 排除幼儿园(141207)和小学(141201)，场地较小且建筑密集
    "141202": "school_yard",      # 中学（通常有400m跑道操场）
    "141203": "school_yard",      # 高等院校（通常有大型运动场）
    # 体育休闲服务（开阔场地，优先选择）
    "080100": "sports_field",     # 体育场馆
    "080101": "sports_field",     # 体育场
    "080102": "sports_field",     # 综合体育馆
    "080103": "sports_field",     # 足球场
    "080104": "sports_field",     # 篮球场
    "080105": "sports_field",     # 网球场
    "080106": "sports_field",     # 羽毛球馆
    "080107": "sports_field",     # 乒乓球馆
    "080300": "sports_field",     # 运动场所
    # 交通设施服务 - 停车场（硬化地面，适合车辆）
    "150900": "parking_lot",      # 停车场
    "150901": "parking_lot",      # 停车场入口
    "150902": "parking_lot",      # 停车场出口
    "150904": "parking_lot",      # 露天停车场
    "150905": "parking_lot",      # 公共停车场
    # 商务住宅 - 广场（开阔场地）
    "110100": "plaza",            # 广场
    "110101": "plaza",            # 城市广场
    "110102": "plaza",            # 商业广场
    # 物流速递（大面积场地，有仓储设施）
    "150500": "logistics_center", # 物流速递
    "150501": "logistics_center", # 物流公司
    "150502": "logistics_center", # 快递公司
    # 公共设施
    "170000": "open_ground",      # 公共设施
    "170100": "open_ground",      # 公用事业
    # 公园广场（开阔绿地）
    "110200": "plaza",            # 公园
    "110201": "plaza",            # 综合公园
    "110202": "plaza",            # 主题公园
    "110203": "plaza",            # 儿童公园
    "110204": "plaza",            # 植物园
}


# 不适合作为驻扎点的POI类型（建筑物，地震后可能倒塌）
# 依据GB 51143-2015，安全距离应为建筑物高度的1.5倍
EXCLUDED_POI_TYPES: Dict[str, str] = {
    # 教育机构 - 小型建筑密集
    "141201": "小学",             # 小学场地较小，建筑密集
    "141204": "成人教育",         # 通常是建筑物内
    "141205": "科研机构",         # 通常是建筑物内
    "141206": "培训机构",         # 通常是建筑物内
    "141207": "幼儿园",           # 场地小，建筑为主
    # 住宅区
    "120000": "住宅区",           # 建筑物
    "120100": "住宅小区",         # 建筑物
    "120200": "宿舍",             # 建筑物
    # 商业建筑
    "060000": "商务住宅",         # 建筑物
    "060100": "写字楼",           # 高层建筑
    "060200": "商住两用",         # 建筑物
}


@dataclass
class POIResult:
    """POI搜索结果"""
    id: str                       # 高德POI ID
    name: str                     # 名称
    type_code: str                # 类型代码
    type_name: str                # 类型名称
    longitude: float              # 经度（GCJ02坐标系）
    latitude: float               # 纬度（GCJ02坐标系）
    address: Optional[str]        # 地址
    city: Optional[str]           # 城市
    district: Optional[str]       # 区县
    province: Optional[str]       # 省份


async def search_poi_around(
    center_lon: float,
    center_lat: float,
    radius_m: int = 5000,
    poi_types: Optional[List[str]] = None,
    page_size: int = 25,
    page_num: int = 1,
) -> List[POIResult]:
    """
    周边POI搜索

    使用高德地图V5版本API，在指定中心点周边搜索POI。

    Args:
        center_lon: 中心点经度（GCJ02坐标系，即高德坐标系）
        center_lat: 中心点纬度
        radius_m: 搜索半径（米），最大50000
        poi_types: POI类型代码列表，默认使用STAGING_POI_TYPES中定义的类型
        page_size: 每页数量，最大25
        page_num: 页码，从1开始

    Returns:
        POI结果列表

    Raises:
        RuntimeError: 未配置高德API Key时抛出
    """
    settings = load_settings()
    if not settings.amap_api_key:
        raise RuntimeError("未配置高德API Key (AMAP_API_KEY)")

    if poi_types is None:
        poi_types = list(STAGING_POI_TYPES.keys())

    params = {
        "key": settings.amap_api_key,
        "location": f"{center_lon},{center_lat}",
        "radius": min(radius_m, 50000),
        "types": "|".join(poi_types),
        "page_size": min(page_size, 25),
        "page_num": page_num,
        "show_fields": "business",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(AMAP_POI_AROUND_URL, params=params)
            data = response.json()

        if data.get("status") != "1":
            error_info = data.get("info", "未知错误")
            error_code = data.get("infocode", "")
            logger.error(f"[POI搜索] API错误: {error_info} (code: {error_code})")
            return []

        results = _parse_poi_response(data)
        logger.info(
            f"[POI搜索] 周边搜索完成: center=({center_lon:.4f}, {center_lat:.4f}), "
            f"radius={radius_m}m, page={page_num}, 找到 {len(results)} 个POI"
        )
        return results

    except httpx.TimeoutException:
        logger.error(f"[POI搜索] 请求超时: center=({center_lon}, {center_lat})")
        return []
    except Exception as e:
        logger.error(f"[POI搜索] 请求失败: {e}")
        return []


async def search_poi_polygon(
    polygon: List[tuple[float, float]],
    poi_types: Optional[List[str]] = None,
    page_size: int = 25,
    page_num: int = 1,
) -> List[POIResult]:
    """
    多边形区域POI搜索

    在指定的多边形区域内搜索POI。

    Args:
        polygon: 多边形顶点列表 [(lon, lat), ...]，GCJ02坐标系
                 顶点数量需在3-50之间
        poi_types: POI类型代码列表
        page_size: 每页数量，最大25
        page_num: 页码，从1开始

    Returns:
        POI结果列表

    Raises:
        RuntimeError: 未配置高德API Key时抛出
        ValueError: 多边形顶点数量不符合要求时抛出
    """
    if len(polygon) < 3:
        raise ValueError("多边形至少需要3个顶点")
    if len(polygon) > 50:
        raise ValueError("多边形顶点数量不能超过50个")

    settings = load_settings()
    if not settings.amap_api_key:
        raise RuntimeError("未配置高德API Key (AMAP_API_KEY)")

    if poi_types is None:
        poi_types = list(STAGING_POI_TYPES.keys())

    # 构建多边形字符串: lon1,lat1|lon2,lat2|...
    polygon_str = "|".join([f"{lon},{lat}" for lon, lat in polygon])

    params = {
        "key": settings.amap_api_key,
        "polygon": polygon_str,
        "types": "|".join(poi_types),
        "page_size": min(page_size, 25),
        "page_num": page_num,
        "show_fields": "business",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(AMAP_POI_POLYGON_URL, params=params)
            data = response.json()

        if data.get("status") != "1":
            error_info = data.get("info", "未知错误")
            error_code = data.get("infocode", "")
            logger.error(f"[POI搜索] API错误: {error_info} (code: {error_code})")
            return []

        results = _parse_poi_response(data)
        logger.info(
            f"[POI搜索] 多边形搜索完成: 顶点数={len(polygon)}, "
            f"page={page_num}, 找到 {len(results)} 个POI"
        )
        return results

    except httpx.TimeoutException:
        logger.error("[POI搜索] 多边形搜索请求超时")
        return []
    except Exception as e:
        logger.error(f"[POI搜索] 多边形搜索请求失败: {e}")
        return []


async def search_poi_text(
    keywords: str,
    city: Optional[str] = None,
    poi_types: Optional[List[str]] = None,
    page_size: int = 25,
    page_num: int = 1,
) -> List[POIResult]:
    """
    关键词POI搜索

    根据关键词搜索POI，可限定城市范围。

    Args:
        keywords: 搜索关键词
        city: 城市名称或城市编码，如"成都"或"510100"
        poi_types: POI类型代码列表
        page_size: 每页数量，最大25
        page_num: 页码，从1开始

    Returns:
        POI结果列表
    """
    settings = load_settings()
    if not settings.amap_api_key:
        raise RuntimeError("未配置高德API Key (AMAP_API_KEY)")

    if poi_types is None:
        poi_types = list(STAGING_POI_TYPES.keys())

    params = {
        "key": settings.amap_api_key,
        "keywords": keywords,
        "types": "|".join(poi_types),
        "page_size": min(page_size, 25),
        "page_num": page_num,
        "show_fields": "business",
    }

    if city:
        params["city"] = city
        params["city_limit"] = "true"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(AMAP_POI_TEXT_URL, params=params)
            data = response.json()

        if data.get("status") != "1":
            error_info = data.get("info", "未知错误")
            error_code = data.get("infocode", "")
            logger.error(f"[POI搜索] API错误: {error_info} (code: {error_code})")
            return []

        results = _parse_poi_response(data)
        logger.info(
            f"[POI搜索] 关键词搜索完成: keywords='{keywords}', "
            f"city={city}, page={page_num}, 找到 {len(results)} 个POI"
        )
        return results

    except httpx.TimeoutException:
        logger.error(f"[POI搜索] 关键词搜索请求超时: keywords='{keywords}'")
        return []
    except Exception as e:
        logger.error(f"[POI搜索] 关键词搜索请求失败: {e}")
        return []


def _parse_poi_response(data: dict) -> List[POIResult]:
    """
    解析高德POI API响应

    Args:
        data: API响应JSON数据

    Returns:
        解析后的POI结果列表
    """
    results = []
    for poi in data.get("pois", []):
        location = poi.get("location", "")
        if not location or "," not in location:
            continue

        try:
            lon_str, lat_str = location.split(",")
            longitude = float(lon_str)
            latitude = float(lat_str)
        except (ValueError, TypeError):
            logger.warning(f"[POI搜索] 无效的坐标格式: {location}")
            continue

        results.append(POIResult(
            id=poi.get("id", ""),
            name=poi.get("name", ""),
            type_code=poi.get("typecode", ""),
            type_name=poi.get("type", ""),
            longitude=longitude,
            latitude=latitude,
            address=poi.get("address") if poi.get("address") else None,
            city=poi.get("cityname") if poi.get("cityname") else None,
            district=poi.get("adname") if poi.get("adname") else None,
            province=poi.get("pname") if poi.get("pname") else None,
        ))

    return results


def get_site_type_from_poi_code(type_code: str) -> str:
    """
    根据POI类型代码获取驻扎点类型

    Args:
        type_code: 高德POI类型代码

    Returns:
        驻扎点类型字符串，未匹配时返回"other"
    """
    return STAGING_POI_TYPES.get(type_code, "other")
