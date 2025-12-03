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
