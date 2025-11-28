"""
气象服务数据模型
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class CurrentWeather:
    """当前天气"""
    timestamp: datetime
    temperature_c: float
    wind_speed_ms: float
    wind_direction_deg: float
    precipitation_mm: float
    weather_code: int
    humidity_percent: Optional[float] = None
    
    @property
    def wind_speed_kmh(self) -> float:
        return self.wind_speed_ms * 3.6
    
    def get_wind_risk_level(self) -> str:
        if self.wind_speed_ms > 20:
            return "red"
        elif self.wind_speed_ms > 15:
            return "orange"
        elif self.wind_speed_ms > 10:
            return "yellow"
        return "blue"
    
    def get_precipitation_risk_level(self) -> str:
        if self.precipitation_mm > 50:
            return "red"
        elif self.precipitation_mm > 30:
            return "orange"
        elif self.precipitation_mm > 10:
            return "yellow"
        return "blue"


@dataclass
class WeatherForecast:
    """天气预报"""
    location: tuple[float, float]
    current: Optional[CurrentWeather]
    hourly: List[CurrentWeather]
    fetch_time: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WeatherRiskSummary:
    """天气风险摘要"""
    max_wind_speed_ms: float
    max_precipitation_mm: float
    wind_risk_level: str
    precipitation_risk_level: str
    overall_risk_level: str
    risk_factors: List[str]
    forecast_hours: int
    
    def to_dict(self) -> dict:
        return {
            "max_wind_speed_ms": self.max_wind_speed_ms,
            "max_precipitation_mm": self.max_precipitation_mm,
            "wind_risk_level": self.wind_risk_level,
            "precipitation_risk_level": self.precipitation_risk_level,
            "overall_risk_level": self.overall_risk_level,
            "risk_factors": self.risk_factors,
            "forecast_hours": self.forecast_hours,
        }
