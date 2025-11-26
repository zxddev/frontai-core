"""
天气数据仓库层

职责: 天气数据CRUD操作
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_GeomFromGeoJSON

from .weather_models import WeatherCondition

logger = logging.getLogger(__name__)


class WeatherRepository:
    """天气数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(
        self,
        weather_type: str,
        temperature: Optional[float] = None,
        wind_speed: Optional[float] = None,
        wind_direction: Optional[int] = None,
        visibility: Optional[int] = None,
        precipitation: Optional[float] = None,
        humidity: Optional[int] = None,
        pressure: Optional[float] = None,
        coverage_area: Optional[dict[str, Any]] = None,
        area_id: Optional[str] = None,
        area_name: Optional[str] = None,
        scenario_id: Optional[UUID] = None,
        alerts: Optional[list[dict[str, Any]]] = None,
        forecast_data: Optional[dict[str, Any]] = None,
        data_source: str = "third_party",
        recorded_at: Optional[datetime] = None,
        valid_until: Optional[datetime] = None,
        uav_flyable: bool = True,
        uav_restriction_reason: Optional[str] = None,
        ground_operable: bool = True,
        ground_restriction_reason: Optional[str] = None,
    ) -> WeatherCondition:
        """
        创建天气记录
        
        Args:
            weather_type: 天气类型（sunny/cloudy/rainstorm等）
            temperature: 温度（摄氏度）
            wind_speed: 风速（m/s）
            wind_direction: 风向（0-360度）
            visibility: 能见度（米）
            precipitation: 降水量（mm/h）
            humidity: 湿度（%）
            pressure: 气压（hPa）
            coverage_area: 覆盖区域（GeoJSON Polygon）
            area_id: 区域标识
            area_name: 区域名称
            scenario_id: 所属想定ID
            alerts: 预警信息列表
            forecast_data: 预报数据
            data_source: 数据来源
            recorded_at: 记录时间
            valid_until: 有效期至
            uav_flyable: 是否适合无人机飞行
            uav_restriction_reason: 无人机限飞原因
            ground_operable: 是否适合地面行动
            ground_restriction_reason: 地面行动限制原因
        """
        # 处理覆盖区域几何
        coverage_geom = None
        if coverage_area:
            geojson_str = json.dumps(coverage_area)
            coverage_geom = ST_GeomFromGeoJSON(geojson_str)
        
        weather = WeatherCondition(
            weather_type=weather_type,
            temperature=Decimal(str(temperature)) if temperature is not None else None,
            wind_speed=Decimal(str(wind_speed)) if wind_speed is not None else None,
            wind_direction=wind_direction,
            visibility=visibility,
            precipitation=Decimal(str(precipitation)) if precipitation is not None else None,
            humidity=humidity,
            pressure=Decimal(str(pressure)) if pressure is not None else None,
            coverage_area=coverage_geom,
            area_id=area_id,
            area_name=area_name,
            scenario_id=scenario_id,
            alerts=alerts or [],
            forecast_data=forecast_data,
            data_source=data_source,
            recorded_at=recorded_at or datetime.utcnow(),
            valid_until=valid_until,
            uav_flyable=uav_flyable,
            uav_restriction_reason=uav_restriction_reason,
            ground_operable=ground_operable,
            ground_restriction_reason=ground_restriction_reason,
        )
        
        self._db.add(weather)
        await self._db.flush()
        await self._db.refresh(weather)
        
        logger.info(
            f"天气数据已入库: id={weather.id}, "
            f"type={weather_type}, area={area_id or area_name}"
        )
        return weather
    
    async def get_by_id(self, weather_id: UUID) -> Optional[WeatherCondition]:
        """根据ID查询天气记录"""
        result = await self._db.execute(
            select(WeatherCondition)
            .where(WeatherCondition.id == weather_id)
        )
        return result.scalar_one_or_none()
    
    async def get_latest_by_area(
        self,
        area_id: str,
        scenario_id: Optional[UUID] = None,
    ) -> Optional[WeatherCondition]:
        """
        获取指定区域最新天气数据
        
        Args:
            area_id: 区域标识
            scenario_id: 想定ID（NULL表示真实天气）
        """
        query = (
            select(WeatherCondition)
            .where(WeatherCondition.area_id == area_id)
            .order_by(WeatherCondition.recorded_at.desc())
            .limit(1)
        )
        
        if scenario_id:
            query = query.where(WeatherCondition.scenario_id == scenario_id)
        else:
            query = query.where(WeatherCondition.scenario_id.is_(None))
        
        result = await self._db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_recent(
        self,
        scenario_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> Sequence[WeatherCondition]:
        """
        查询最近的天气数据
        
        Args:
            scenario_id: 想定ID（NULL表示真实天气）
            limit: 返回数量限制
        """
        query = (
            select(WeatherCondition)
            .order_by(WeatherCondition.recorded_at.desc())
            .limit(limit)
        )
        
        if scenario_id:
            query = query.where(WeatherCondition.scenario_id == scenario_id)
        else:
            query = query.where(WeatherCondition.scenario_id.is_(None))
        
        result = await self._db.execute(query)
        return result.scalars().all()
