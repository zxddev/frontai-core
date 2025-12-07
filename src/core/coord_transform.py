"""
坐标系转换工具

WGS84 (地球坐标系) ↔ GCJ02 (火星坐标系/高德坐标系) 互转

- 数据库路网使用 WGS84 坐标系
- 前端高德地图使用 GCJ02 坐标系
"""
from __future__ import annotations

import math
from typing import Tuple, List

# 椭球参数
_A = 6378245.0  # 长半轴
_EE = 0.00669342162296594323  # 扁率


def _out_of_china(lng: float, lat: float) -> bool:
    """判断坐标是否在中国境外"""
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(lng: float, lat: float) -> float:
    """纬度转换"""
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + \
          0.1 * lng * lat + 0.2 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 *
            math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 *
            math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 *
            math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng: float, lat: float) -> float:
    """经度转换"""
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + \
          0.1 * lng * lat + 0.1 * math.sqrt(abs(lng))
    ret += (20.0 * math.sin(6.0 * lng * math.pi) + 20.0 *
            math.sin(2.0 * lng * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * math.pi) + 40.0 *
            math.sin(lng / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * math.pi) + 300.0 *
            math.sin(lng / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 坐标转 GCJ02 坐标（地球坐标系 → 火星坐标系）
    
    Args:
        lng: WGS84 经度
        lat: WGS84 纬度
        
    Returns:
        (gcj02_lng, gcj02_lat) GCJ02 坐标
    """
    if _out_of_china(lng, lat):
        return lng, lat
    
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    mglat = lat + dlat
    mglng = lng + dlng
    return mglng, mglat


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ02 坐标转 WGS84 坐标（火星坐标系 → 地球坐标系）
    
    使用迭代法进行逆向转换，精度约 0.5 米
    
    Args:
        lng: GCJ02 经度
        lat: GCJ02 纬度
        
    Returns:
        (wgs84_lng, wgs84_lat) WGS84 坐标
    """
    if _out_of_china(lng, lat):
        return lng, lat
    
    # 迭代逆向计算
    mglng, mglat = lng, lat
    for _ in range(10):  # 迭代10次足够精确
        tmp_lng, tmp_lat = wgs84_to_gcj02(mglng, mglat)
        mglng += lng - tmp_lng
        mglat += lat - tmp_lat
    
    return mglng, mglat


def wgs84_to_gcj02_list(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """批量转换 WGS84 → GCJ02"""
    return [wgs84_to_gcj02(lng, lat) for lng, lat in points]


def gcj02_to_wgs84_list(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """批量转换 GCJ02 → WGS84"""
    return [gcj02_to_wgs84(lng, lat) for lng, lat in points]


# ============================================================================
# UTM 坐标转换 (WGS84 ↔ UTM)
# ============================================================================

# UTM 参数
_UTM_K0 = 0.9996  # 比例因子
_UTM_E = 0.0818191908426  # 第一偏心率
_UTM_E2 = _UTM_E * _UTM_E
_UTM_E4 = _UTM_E2 * _UTM_E2
_UTM_E6 = _UTM_E4 * _UTM_E2
_UTM_EP2 = _UTM_E2 / (1 - _UTM_E2)
_UTM_A = 6378137.0  # WGS84 椭球长半轴


def get_utm_zone(lng: float, lat: float) -> Tuple[int, str]:
    """
    根据经纬度获取 UTM 区号和半球
    
    Args:
        lng: 经度 (WGS84)
        lat: 纬度 (WGS84)
        
    Returns:
        (zone, hemisphere) 区号(1-60) 和半球('N'或'S')
    """
    zone = int((lng + 180) / 6) + 1
    
    # 特殊区域处理 (挪威、斯瓦尔巴群岛)
    if 56.0 <= lat < 64.0 and 3.0 <= lng < 12.0:
        zone = 32
    if 72.0 <= lat < 84.0:
        if 0.0 <= lng < 9.0:
            zone = 31
        elif 9.0 <= lng < 21.0:
            zone = 33
        elif 21.0 <= lng < 33.0:
            zone = 35
        elif 33.0 <= lng < 42.0:
            zone = 37
    
    hemisphere = 'N' if lat >= 0 else 'S'
    return zone, hemisphere


def wgs84_to_utm(
    lng: float, lat: float
) -> Tuple[float, float, int, str]:
    """
    WGS84 坐标转 UTM 坐标
    
    Args:
        lng: 经度 (WGS84)
        lat: 纬度 (WGS84)
        
    Returns:
        (easting, northing, zone, hemisphere) UTM坐标和区号
        
    Precision: < 1m 水平精度
    """
    zone, hemisphere = get_utm_zone(lng, lat)
    
    # 中央子午线经度
    lon0 = (zone - 1) * 6 - 180 + 3
    
    # 转换为弧度
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lng)
    lon0_rad = math.radians(lon0)
    
    # 计算参数
    N = _UTM_A / math.sqrt(1 - _UTM_E2 * math.sin(lat_rad) ** 2)
    T = math.tan(lat_rad) ** 2
    C = _UTM_EP2 * math.cos(lat_rad) ** 2
    A = (lon_rad - lon0_rad) * math.cos(lat_rad)
    
    # 子午线弧长
    M = _UTM_A * (
        (1 - _UTM_E2 / 4 - 3 * _UTM_E4 / 64 - 5 * _UTM_E6 / 256) * lat_rad
        - (3 * _UTM_E2 / 8 + 3 * _UTM_E4 / 32 + 45 * _UTM_E6 / 1024) * math.sin(2 * lat_rad)
        + (15 * _UTM_E4 / 256 + 45 * _UTM_E6 / 1024) * math.sin(4 * lat_rad)
        - (35 * _UTM_E6 / 3072) * math.sin(6 * lat_rad)
    )
    
    # UTM 坐标
    easting = _UTM_K0 * N * (
        A + (1 - T + C) * A ** 3 / 6
        + (5 - 18 * T + T ** 2 + 72 * C - 58 * _UTM_EP2) * A ** 5 / 120
    ) + 500000.0
    
    northing = _UTM_K0 * (
        M + N * math.tan(lat_rad) * (
            A ** 2 / 2
            + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
            + (61 - 58 * T + T ** 2 + 600 * C - 330 * _UTM_EP2) * A ** 6 / 720
        )
    )
    
    # 南半球偏移
    if hemisphere == 'S':
        northing += 10000000.0
    
    return easting, northing, zone, hemisphere


def utm_to_wgs84(
    easting: float, northing: float, zone: int, hemisphere: str
) -> Tuple[float, float]:
    """
    UTM 坐标转 WGS84 坐标
    
    Args:
        easting: UTM 东坐标 (m)
        northing: UTM 北坐标 (m)
        zone: UTM 区号 (1-60)
        hemisphere: 半球 ('N' 或 'S')
        
    Returns:
        (lng, lat) WGS84 坐标
        
    Precision: < 1m 水平精度
    """
    # 南半球偏移
    if hemisphere == 'S':
        northing -= 10000000.0
    
    # 中央子午线经度
    lon0 = (zone - 1) * 6 - 180 + 3
    lon0_rad = math.radians(lon0)
    
    # 去除假东坐标
    x = easting - 500000.0
    y = northing
    
    # 计算 footprint latitude
    M = y / _UTM_K0
    mu = M / (_UTM_A * (1 - _UTM_E2 / 4 - 3 * _UTM_E4 / 64 - 5 * _UTM_E6 / 256))
    
    e1 = (1 - math.sqrt(1 - _UTM_E2)) / (1 + math.sqrt(1 - _UTM_E2))
    
    phi1 = mu + (
        (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
        + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
        + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
        + (1097 * e1 ** 4 / 512) * math.sin(8 * mu)
    )
    
    # 计算参数
    N1 = _UTM_A / math.sqrt(1 - _UTM_E2 * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = _UTM_EP2 * math.cos(phi1) ** 2
    R1 = _UTM_A * (1 - _UTM_E2) / ((1 - _UTM_E2 * math.sin(phi1) ** 2) ** 1.5)
    D = x / (N1 * _UTM_K0)
    
    # 纬度
    lat_rad = phi1 - (N1 * math.tan(phi1) / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * _UTM_EP2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * _UTM_EP2 - 3 * C1 ** 2) * D ** 6 / 720
    )
    
    # 经度
    lon_rad = lon0_rad + (
        D
        - (1 + 2 * T1 + C1) * D ** 3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * _UTM_EP2 + 24 * T1 ** 2) * D ** 5 / 120
    ) / math.cos(phi1)
    
    return math.degrees(lon_rad), math.degrees(lat_rad)


# ============================================================================
# 高程转换 (椭球高 ↔ 大地水准面高)
# ============================================================================

# EGM96 大地水准面模型 (简化版, 使用全球平均偏移 + 区域修正)
# 四川省区域平均值约 -30m
_EGM96_GLOBAL_OFFSET = -30.0

# 区域偏移表 (简化的分区修正)
_EGM96_REGIONAL_OFFSETS = {
    # (min_lat, max_lat, min_lng, max_lng): offset
    (26.0, 34.0, 97.0, 108.0): -32.0,  # 四川
    (30.0, 32.0, 103.0, 105.0): -31.0,  # 成都平原
    (31.0, 33.0, 103.0, 105.0): -33.0,  # 川北山区
}


def _get_egm96_offset(lat: float, lng: float) -> float:
    """获取 EGM96 大地水准面偏移 (简化实现)"""
    for (min_lat, max_lat, min_lng, max_lng), offset in _EGM96_REGIONAL_OFFSETS.items():
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return offset
    return _EGM96_GLOBAL_OFFSET


def ellipsoid_to_geoid(
    ellipsoid_height: float, lat: float, lng: float
) -> float:
    """
    椭球高转大地水准面高 (EGM96)
    
    Args:
        ellipsoid_height: 椭球高 (m), GPS 直接测量的高度
        lat: 纬度 (WGS84)
        lng: 经度 (WGS84)
        
    Returns:
        geoid_height: 大地水准面高 (m), 即海拔高度
        
    Note:
        geoid_height = ellipsoid_height - N
        其中 N 是大地水准面高 (geoid undulation)
        简化实现使用区域平均值，精度约 ±5m
        生产环境应使用完整 EGM96 网格数据
    """
    N = _get_egm96_offset(lat, lng)
    return ellipsoid_height - N


def geoid_to_ellipsoid(
    geoid_height: float, lat: float, lng: float
) -> float:
    """
    大地水准面高转椭球高 (EGM96)
    
    Args:
        geoid_height: 大地水准面高 (m), 海拔高度
        lat: 纬度 (WGS84)
        lng: 经度 (WGS84)
        
    Returns:
        ellipsoid_height: 椭球高 (m)
        
    Note:
        ellipsoid_height = geoid_height + N
        简化实现，精度约 ±5m
    """
    N = _get_egm96_offset(lat, lng)
    return geoid_height + N


def wgs84_to_utm_list(
    points: List[Tuple[float, float]]
) -> Tuple[List[Tuple[float, float]], int, str]:
    """
    批量转换 WGS84 → UTM (使用第一个点确定 UTM 区)
    
    Args:
        points: [(lng, lat), ...] WGS84 坐标列表
        
    Returns:
        (utm_points, zone, hemisphere)
        utm_points: [(easting, northing), ...]
    """
    if not points:
        return [], 0, 'N'
    
    # 使用第一个点确定区号
    first_lng, first_lat = points[0]
    zone, hemisphere = get_utm_zone(first_lng, first_lat)
    
    utm_points = []
    for lng, lat in points:
        e, n, _, _ = wgs84_to_utm(lng, lat)
        utm_points.append((e, n))
    
    return utm_points, zone, hemisphere


def utm_to_wgs84_list(
    points: List[Tuple[float, float]], zone: int, hemisphere: str
) -> List[Tuple[float, float]]:
    """
    批量转换 UTM → WGS84
    
    Args:
        points: [(easting, northing), ...] UTM 坐标列表
        zone: UTM 区号
        hemisphere: 半球
        
    Returns:
        [(lng, lat), ...] WGS84 坐标列表
    """
    return [utm_to_wgs84(e, n, zone, hemisphere) for e, n in points]
