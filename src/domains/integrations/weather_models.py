"""
天气数据ORM模型

对应SQL表: weather_conditions_v2
参考: sql/v2_environment_model.sql
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM
from geoalchemy2 import Geometry

from src.core.database import Base


# 天气类型枚举
WeatherTypeEnum = ENUM(
    'sunny',          # 晴
    'cloudy',         # 多云
    'overcast',       # 阴
    'light_rain',     # 小雨
    'moderate_rain',  # 中雨
    'heavy_rain',     # 大雨
    'rainstorm',      # 暴雨
    'snow',           # 雪
    'fog',            # 雾
    'haze',           # 霾
    'thunderstorm',   # 雷暴
    'typhoon',        # 台风
    'sandstorm',      # 沙尘暴
    name='weather_type_v2',
    create_type=False,
)


class WeatherCondition(Base):
    """
    天气状况表 ORM 模型
    
    业务说明:
    - 记录各区域的天气状况
    - 用于评估救援行动可行性
    - 影响无人机飞行和地面行动决策
    
    对应SQL表: weather_conditions_v2
    """
    __tablename__ = "weather_conditions_v2"
    
    # ==================== 主键 ====================
    id: UUID = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid_lib.uuid4,
        comment="天气记录ID"
    )
    
    # ==================== 关联 ====================
    scenario_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True),
        index=True,
        comment="所属想定ID（NULL表示真实天气）"
    )
    
    # ==================== 区域标识 ====================
    area_id: Optional[str] = Column(
        String(100),
        index=True,
        comment="区域标识"
    )
    area_name: Optional[str] = Column(
        String(200),
        comment="区域名称"
    )
    
    # ==================== 覆盖区域 ====================
    coverage_area = Column(
        Geometry("POLYGON", srid=4326),
        comment="覆盖区域（GeoJSON Polygon）"
    )
    
    # ==================== 天气参数 ====================
    weather_type: str = Column(
        WeatherTypeEnum,
        nullable=False,
        index=True,
        comment="天气类型"
    )
    temperature: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="温度（摄氏度）"
    )
    feels_like: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="体感温度"
    )
    wind_speed: Optional[Decimal] = Column(
        Numeric(5, 2),
        comment="风速（m/s）"
    )
    wind_direction: Optional[int] = Column(
        Integer,
        comment="风向（0-360度）"
    )
    wind_scale: Optional[int] = Column(
        Integer,
        comment="风力等级（0-17级）"
    )
    visibility: Optional[int] = Column(
        Integer,
        comment="能见度（米）"
    )
    precipitation: Optional[Decimal] = Column(
        Numeric(6, 2),
        comment="降水量（mm/h）"
    )
    humidity: Optional[int] = Column(
        Integer,
        comment="湿度（%）"
    )
    pressure: Optional[Decimal] = Column(
        Numeric(6, 1),
        comment="气压（hPa）"
    )
    
    # ==================== 行动限制 ====================
    uav_flyable: bool = Column(
        Boolean,
        default=True,
        comment="是否适合无人机飞行"
    )
    uav_restriction_reason: Optional[str] = Column(
        Text,
        comment="无人机限飞原因"
    )
    ground_operable: bool = Column(
        Boolean,
        default=True,
        comment="是否适合地面行动"
    )
    ground_restriction_reason: Optional[str] = Column(
        Text,
        comment="地面行动限制原因"
    )
    
    # ==================== 预警和预报 ====================
    alerts: list[dict[str, Any]] = Column(
        JSONB,
        default=[],
        comment="预警信息列表"
    )
    forecast_data: Optional[dict[str, Any]] = Column(
        JSONB,
        comment="未来N小时预报数据"
    )
    
    # ==================== 数据来源和时间 ====================
    data_source: Optional[str] = Column(
        String(100),
        comment="数据来源: meteorological_bureau/sensor/manual/third_party"
    )
    recorded_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="数据记录时间"
    )
    valid_until: Optional[datetime] = Column(
        DateTime(timezone=True),
        comment="数据有效期至"
    )
    
    # ==================== 时间戳 ====================
    created_at: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="创建时间"
    )
