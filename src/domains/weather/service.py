"""
气象服务

封装 OpenMeteo 客户端，遵循架构规范：
- Service 层封装 External Client
- Agent Node 通过 Service 调用外部API
"""
from __future__ import annotations

import logging
from typing import Optional

from .schemas import CurrentWeather, WeatherForecast, WeatherRiskSummary
from src.infra.clients.openmeteo import get_weather_client, WeatherClient

logger = logging.getLogger(__name__)


class WeatherService:
    """
    气象服务
    
    提供气象数据查询和风险评估功能。
    封装 OpenMeteo 外部API调用。
    """
    
    def __init__(self, client: Optional[WeatherClient] = None):
        self._client = client or get_weather_client()
    
    async def get_current_weather(self, lon: float, lat: float) -> CurrentWeather:
        """
        获取当前天气
        
        Args:
            lon: 经度
            lat: 纬度
            
        Returns:
            当前天气数据
        """
        logger.info(f"[WeatherService] 获取当前天气: ({lon}, {lat})")
        
        data = await self._client.get_current_weather(lon, lat)
        
        return CurrentWeather(
            timestamp=data.timestamp,
            temperature_c=data.temperature_c,
            wind_speed_ms=data.wind_speed_ms,
            wind_direction_deg=data.wind_direction_deg,
            precipitation_mm=data.precipitation_mm,
            weather_code=data.weather_code,
            humidity_percent=data.humidity_percent,
        )
    
    async def get_weather_forecast(
        self, 
        lon: float, 
        lat: float, 
        hours: int = 24,
    ) -> WeatherForecast:
        """
        获取天气预报
        
        Args:
            lon: 经度
            lat: 纬度
            hours: 预报小时数
            
        Returns:
            天气预报数据
        """
        logger.info(f"[WeatherService] 获取天气预报: ({lon}, {lat}), {hours}h")
        
        data = await self._client.get_weather_forecast(lon, lat, hours)
        
        current = None
        if data.current:
            current = CurrentWeather(
                timestamp=data.current.timestamp,
                temperature_c=data.current.temperature_c,
                wind_speed_ms=data.current.wind_speed_ms,
                wind_direction_deg=data.current.wind_direction_deg,
                precipitation_mm=data.current.precipitation_mm,
                weather_code=data.current.weather_code,
                humidity_percent=data.current.humidity_percent,
            )
        
        hourly = [
            CurrentWeather(
                timestamp=h.timestamp,
                temperature_c=h.temperature_c,
                wind_speed_ms=h.wind_speed_ms,
                wind_direction_deg=h.wind_direction_deg,
                precipitation_mm=h.precipitation_mm,
                weather_code=h.weather_code,
                humidity_percent=h.humidity_percent,
            )
            for h in data.hourly
        ]
        
        return WeatherForecast(
            location=data.location,
            current=current,
            hourly=hourly,
            fetch_time=data.fetch_time,
        )
    
    async def get_weather_risk_summary(
        self,
        lon: float,
        lat: float,
        hours: int = 6,
    ) -> WeatherRiskSummary:
        """
        获取天气风险摘要
        
        综合分析未来N小时的气象风险。
        
        Args:
            lon: 经度
            lat: 纬度
            hours: 预测时间范围
            
        Returns:
            风险摘要
        """
        logger.info(f"[WeatherService] 获取风险摘要: ({lon}, {lat}), {hours}h")
        
        data = await self._client.get_weather_risk_summary(lon, lat, hours)
        
        return WeatherRiskSummary(
            max_wind_speed_ms=data["max_wind_speed_ms"],
            max_precipitation_mm=data["max_precipitation_mm"],
            wind_risk_level=data["wind_risk_level"],
            precipitation_risk_level=data["precipitation_risk_level"],
            overall_risk_level=data["overall_risk_level"],
            risk_factors=data["risk_factors"],
            forecast_hours=data["forecast_hours"],
        )


_weather_service: Optional[WeatherService] = None


def get_weather_service() -> WeatherService:
    """获取气象服务实例（单例）"""
    global _weather_service
    if _weather_service is None:
        _weather_service = WeatherService()
    return _weather_service
