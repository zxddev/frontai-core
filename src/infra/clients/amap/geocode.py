"""
高德地理编码API

提供地址转坐标、坐标转地址功能。
"""
from __future__ import annotations

import logging
from typing import Optional, Dict

import httpx

from src.infra.settings import load_settings

logger = logging.getLogger(__name__)

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_REGEO_URL = "https://restapi.amap.com/v3/geocode/regeo"


async def amap_geocode_async(address: str) -> Optional[Dict[str, float]]:
    """
    地址转坐标（异步）
    
    Args:
        address: 地址文本，如"北京市朝阳区"
        
    Returns:
        {"longitude": float, "latitude": float} 或 None
    """
    settings = load_settings()
    api_key = settings.amap_api_key
    
    if not api_key:
        logger.error("未配置高德API Key (AMAP_API_KEY)")
        return None
    
    params = {
        "key": api_key,
        "address": address,
        "output": "JSON",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(AMAP_GEOCODE_URL, params=params)
            data = response.json()
        
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0]["location"]  # "116.397128,39.916527"
            lng, lat = location.split(",")
            result = {
                "longitude": float(lng),
                "latitude": float(lat),
            }
            logger.info(f"地理编码成功: {address} -> {result}")
            return result
        
        logger.warning(f"地理编码失败: {address}, response={data}")
        return None
        
    except Exception as e:
        logger.error(f"地理编码异常: {address}, error={e}")
        return None


def amap_geocode(address: str) -> Optional[Dict[str, float]]:
    """
    地址转坐标（同步版本）
    
    Args:
        address: 地址文本
        
    Returns:
        {"longitude": float, "latitude": float} 或 None
    """
    settings = load_settings()
    api_key = settings.amap_api_key
    
    if not api_key:
        logger.error("未配置高德API Key (AMAP_API_KEY)")
        return None
    
    params = {
        "key": api_key,
        "address": address,
        "output": "JSON",
    }
    
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(AMAP_GEOCODE_URL, params=params)
            data = response.json()
        
        if data.get("status") == "1" and data.get("geocodes"):
            location = data["geocodes"][0]["location"]
            lng, lat = location.split(",")
            return {
                "longitude": float(lng),
                "latitude": float(lat),
            }
        
        logger.warning(f"地理编码失败: {address}, response={data}")
        return None
        
    except Exception as e:
        logger.error(f"地理编码异常: {address}, error={e}")
        return None


async def amap_regeo_async(longitude: float, latitude: float) -> Optional[str]:
    """
    逆地理编码：坐标转地址（异步）
    
    Args:
        longitude: 经度
        latitude: 纬度
        
    Returns:
        地址字符串，如"四川省阿坝藏族羌族自治州茂县凤仪镇"，失败返回 None
    """
    settings = load_settings()
    api_key = settings.amap_api_key
    
    if not api_key:
        logger.error("未配置高德API Key (AMAP_API_KEY)")
        return None
    
    params = {
        "key": api_key,
        "location": f"{longitude},{latitude}",
        "output": "JSON",
        "radius": 1000,
        "extensions": "base",
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(AMAP_REGEO_URL, params=params)
            data = response.json()
        
        if data.get("status") == "1" and data.get("regeocode"):
            address = data["regeocode"].get("formatted_address", "")
            if address:
                logger.debug(f"逆地理编码成功: ({longitude}, {latitude}) -> {address}")
                return address
        
        logger.warning(f"逆地理编码失败: ({longitude}, {latitude}), response={data}")
        return None
        
    except Exception as e:
        logger.error(f"逆地理编码异常: ({longitude}, {latitude}), error={e}")
        return None
