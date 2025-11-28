"""
OpenMeteo 气象数据客户端

免费API，无需Key，全球覆盖，支持16天预报。
API文档: https://open-meteo.com/en/docs
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

OPENMETEO_API_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT = 30.0


@dataclass
class WeatherData:
    """天气数据"""
    timestamp: datetime
    temperature_c: float
    wind_speed_ms: float
    wind_direction_deg: float
    precipitation_mm: float
    weather_code: int
    humidity_percent: Optional[float] = None
    visibility_m: Optional[float] = None
    
    @property
    def wind_speed_kmh(self) -> float:
        """风速(km/h)"""
        return self.wind_speed_ms * 3.6
    
    def get_wind_risk_level(self) -> str:
        """根据风速评估风险等级"""
        if self.wind_speed_ms > 20:
            return "red"
        elif self.wind_speed_ms > 15:
            return "orange"
        elif self.wind_speed_ms > 10:
            return "yellow"
        return "blue"
    
    def get_precipitation_risk_level(self) -> str:
        """根据降水评估风险等级"""
        if self.precipitation_mm > 50:
            return "red"
        elif self.precipitation_mm > 30:
            return "orange"
        elif self.precipitation_mm > 10:
            return "yellow"
        return "blue"


@dataclass
class WeatherForecast:
    """天气预报结果"""
    location: tuple[float, float]
    current: Optional[WeatherData]
    hourly: List[WeatherData]
    fetch_time: datetime


class WeatherClient:
    """OpenMeteo气象客户端"""
    
    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self._timeout = timeout
    
    async def get_current_weather(self, lon: float, lat: float) -> WeatherData:
        """
        获取当前天气
        
        Args:
            lon: 经度
            lat: 纬度
            
        Returns:
            当前天气数据
        """
        logger.info(f"获取当前天气: lon={lon}, lat={lat}")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "timezone": "auto",
        }
        
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(OPENMETEO_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        current = data.get("current", {})
        
        weather = WeatherData(
            timestamp=datetime.fromisoformat(current.get("time", datetime.utcnow().isoformat())),
            temperature_c=current.get("temperature_2m", 0),
            wind_speed_ms=current.get("wind_speed_10m", 0) / 3.6,
            wind_direction_deg=current.get("wind_direction_10m", 0),
            precipitation_mm=current.get("precipitation", 0),
            weather_code=current.get("weather_code", 0),
            humidity_percent=current.get("relative_humidity_2m"),
        )
        
        logger.info(f"当前天气: temp={weather.temperature_c}°C, wind={weather.wind_speed_ms:.1f}m/s, precip={weather.precipitation_mm}mm")
        return weather
    
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
            hours: 预报小时数 (1-168)
            
        Returns:
            天气预报数据
        """
        logger.info(f"获取天气预报: lon={lon}, lat={lat}, hours={hours}")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "forecast_hours": min(hours, 168),
            "timezone": "auto",
        }
        
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(OPENMETEO_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
        
        current_data = data.get("current", {})
        current = WeatherData(
            timestamp=datetime.fromisoformat(current_data.get("time", datetime.utcnow().isoformat())),
            temperature_c=current_data.get("temperature_2m", 0),
            wind_speed_ms=current_data.get("wind_speed_10m", 0) / 3.6,
            wind_direction_deg=current_data.get("wind_direction_10m", 0),
            precipitation_mm=current_data.get("precipitation", 0),
            weather_code=current_data.get("weather_code", 0),
            humidity_percent=current_data.get("relative_humidity_2m"),
        ) if current_data else None
        
        hourly_data = data.get("hourly", {})
        times = hourly_data.get("time", [])
        temps = hourly_data.get("temperature_2m", [])
        winds = hourly_data.get("wind_speed_10m", [])
        wind_dirs = hourly_data.get("wind_direction_10m", [])
        precips = hourly_data.get("precipitation", [])
        codes = hourly_data.get("weather_code", [])
        humidities = hourly_data.get("relative_humidity_2m", [])
        
        hourly: List[WeatherData] = []
        for i in range(min(len(times), hours)):
            hourly.append(WeatherData(
                timestamp=datetime.fromisoformat(times[i]),
                temperature_c=temps[i] if i < len(temps) else 0,
                wind_speed_ms=(winds[i] if i < len(winds) else 0) / 3.6,
                wind_direction_deg=wind_dirs[i] if i < len(wind_dirs) else 0,
                precipitation_mm=precips[i] if i < len(precips) else 0,
                weather_code=codes[i] if i < len(codes) else 0,
                humidity_percent=humidities[i] if i < len(humidities) else None,
            ))
        
        forecast = WeatherForecast(
            location=(lon, lat),
            current=current,
            hourly=hourly,
            fetch_time=datetime.utcnow(),
        )
        
        logger.info(f"天气预报获取完成: {len(hourly)}小时数据")
        return forecast
    
    async def get_weather_risk_summary(
        self,
        lon: float,
        lat: float,
        hours: int = 6,
    ) -> dict:
        """
        获取天气风险摘要
        
        Args:
            lon: 经度
            lat: 纬度
            hours: 预测时间范围
            
        Returns:
            风险摘要 {
                "max_wind_speed_ms": float,
                "max_precipitation_mm": float,
                "wind_risk_level": str,
                "precipitation_risk_level": str,
                "overall_risk_level": str,
                "risk_factors": List[str],
            }
        """
        forecast = await self.get_weather_forecast(lon, lat, hours)
        
        max_wind = 0.0
        max_precip = 0.0
        risk_factors = []
        
        for w in forecast.hourly[:hours]:
            max_wind = max(max_wind, w.wind_speed_ms)
            max_precip = max(max_precip, w.precipitation_mm)
        
        if forecast.current:
            max_wind = max(max_wind, forecast.current.wind_speed_ms)
            max_precip = max(max_precip, forecast.current.precipitation_mm)
        
        wind_risk = "blue"
        if max_wind > 20:
            wind_risk = "red"
            risk_factors.append(f"强风预警: {max_wind:.1f}m/s")
        elif max_wind > 15:
            wind_risk = "orange"
            risk_factors.append(f"大风预警: {max_wind:.1f}m/s")
        elif max_wind > 10:
            wind_risk = "yellow"
            risk_factors.append(f"中等风速: {max_wind:.1f}m/s")
        
        precip_risk = "blue"
        if max_precip > 50:
            precip_risk = "red"
            risk_factors.append(f"暴雨预警: {max_precip:.1f}mm/h")
        elif max_precip > 30:
            precip_risk = "orange"
            risk_factors.append(f"大雨预警: {max_precip:.1f}mm/h")
        elif max_precip > 10:
            precip_risk = "yellow"
            risk_factors.append(f"中雨: {max_precip:.1f}mm/h")
        
        risk_levels = {"red": 4, "orange": 3, "yellow": 2, "blue": 1}
        overall_score = max(risk_levels[wind_risk], risk_levels[precip_risk])
        overall_risk = {4: "red", 3: "orange", 2: "yellow", 1: "blue"}[overall_score]
        
        return {
            "max_wind_speed_ms": max_wind,
            "max_precipitation_mm": max_precip,
            "wind_risk_level": wind_risk,
            "precipitation_risk_level": precip_risk,
            "overall_risk_level": overall_risk,
            "risk_factors": risk_factors,
            "forecast_hours": hours,
        }


_weather_client: Optional[WeatherClient] = None


def get_weather_client() -> WeatherClient:
    """获取全局WeatherClient实例（单例）"""
    global _weather_client
    if _weather_client is None:
        _weather_client = WeatherClient()
    return _weather_client
