"""气象服务模块"""

from .service import WeatherService, get_weather_service
from .schemas import WeatherRiskSummary, CurrentWeather, WeatherForecast

__all__ = [
    "WeatherService",
    "get_weather_service",
    "WeatherRiskSummary",
    "CurrentWeather",
    "WeatherForecast",
]
