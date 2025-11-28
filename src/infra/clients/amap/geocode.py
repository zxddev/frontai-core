"""
高德地理编码API

提供地址转坐标功能。
"""
from __future__ import annotations

import logging
from typing import Optional, Dict

import httpx

from src.infra.settings import load_settings

logger = logging.getLogger(__name__)

AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


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
