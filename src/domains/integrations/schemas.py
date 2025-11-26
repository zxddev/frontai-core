"""
第三方接入数据模型

定义灾情上报、传感器告警、设备遥测、天气数据的请求响应模型。
所有模型使用Pydantic v2强类型定义。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# 通用枚举
# ============================================================================

class DisasterType(str, Enum):
    """灾情类型"""
    trapped_person = "trapped_person"
    fire = "fire"
    flood = "flood"
    landslide = "landslide"
    building_collapse = "building_collapse"
    road_damage = "road_damage"
    power_outage = "power_outage"
    communication_lost = "communication_lost"
    hazmat_leak = "hazmat_leak"
    epidemic = "epidemic"
    earthquake_secondary = "earthquake_secondary"
    other = "other"


class Priority(str, Enum):
    """优先级"""
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class ReporterType(str, Enum):
    """上报人类型"""
    witness = "witness"
    victim = "victim"
    official = "official"


class SensorType(str, Enum):
    """传感器类型"""
    seismometer = "seismometer"
    water_level_gauge = "water_level_gauge"
    smoke_detector = "smoke_detector"
    gas_detector = "gas_detector"
    temperature_sensor = "temperature_sensor"
    rain_gauge = "rain_gauge"
    displacement_sensor = "displacement_sensor"
    other = "other"


class AlertLevel(str, Enum):
    """告警级别"""
    info = "info"
    warning = "warning"
    critical = "critical"


class DeviceType(str, Enum):
    """设备类型"""
    uav = "uav"
    ugv = "ugv"
    usv = "usv"
    vehicle = "vehicle"


class TelemetryType(str, Enum):
    """遥测类型"""
    location = "location"
    battery = "battery"
    speed = "speed"
    altitude = "altitude"
    status = "status"
    sensor = "sensor"


class WeatherType(str, Enum):
    """天气类型"""
    sunny = "sunny"
    cloudy = "cloudy"
    overcast = "overcast"
    light_rain = "light_rain"
    moderate_rain = "moderate_rain"
    heavy_rain = "heavy_rain"
    rainstorm = "rainstorm"
    snow = "snow"
    fog = "fog"
    haze = "haze"
    thunderstorm = "thunderstorm"
    typhoon = "typhoon"
    sandstorm = "sandstorm"


class WeatherAlertLevel(str, Enum):
    """天气预警级别"""
    blue = "blue"
    yellow = "yellow"
    orange = "orange"
    red = "red"


# ============================================================================
# 通用模型
# ============================================================================

class Location(BaseModel):
    """位置信息"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    address: Optional[str] = Field(None, max_length=500, description="地址描述")
    accuracy_meters: Optional[float] = Field(None, ge=0, description="定位精度(米)")
    altitude_m: Optional[float] = Field(None, description="海拔高度(米)")


class Reporter(BaseModel):
    """上报人信息"""
    name: Optional[str] = Field(None, max_length=100, description="姓名")
    phone: Optional[str] = Field(None, max_length=20, description="电话")
    reporter_type: ReporterType = Field(default=ReporterType.witness, alias="type", description="上报人类型")


# ============================================================================
# 灾情上报
# ============================================================================

class DisasterReportRequest(BaseModel):
    """灾情上报请求"""
    # 必填字段
    disaster_type: DisasterType = Field(..., description="灾情类型")
    location: Location = Field(..., description="灾情位置")
    description: str = Field(..., min_length=1, max_length=2000, description="灾情描述")
    source_system: str = Field(..., max_length=100, description="来源系统标识")
    source_event_id: str = Field(..., max_length=100, description="来源系统事件ID")
    
    # 可选字段
    priority: Priority = Field(default=Priority.medium, description="优先级")
    estimated_victims: int = Field(default=0, ge=0, description="预估受困人数")
    affected_radius_meters: Optional[float] = Field(None, ge=0, description="影响半径(米)")
    occurred_at: Optional[datetime] = Field(None, description="事件发生时间")
    media_urls: list[str] = Field(default_factory=list, description="媒体附件URL")
    reporter: Optional[Reporter] = Field(None, description="上报人信息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class DisasterReportResponse(BaseModel):
    """灾情上报响应"""
    success: bool
    event_id: UUID
    event_code: str
    status: str = Field(description="pending/confirmed/duplicate")
    message: str
    entity_id: Optional[UUID] = None
    created_at: datetime
    duplicate_of: Optional[UUID] = Field(None, description="重复上报时返回原事件ID")


# ============================================================================
# 传感器告警
# ============================================================================

class SensorAlertRequest(BaseModel):
    """传感器告警请求"""
    sensor_id: str = Field(..., max_length=100, description="传感器ID")
    sensor_type: SensorType = Field(..., description="传感器类型")
    alert_type: str = Field(..., max_length=50, description="告警类型")
    alert_level: AlertLevel = Field(..., description="告警级别")
    location: Location = Field(..., description="传感器位置")
    readings: dict[str, Any] = Field(..., description="传感器读数")
    triggered_at: datetime = Field(..., description="触发时间")
    
    # 可选字段
    source_system: Optional[str] = Field(None, max_length=100, description="来源系统")
    raw_data: Optional[str] = Field(None, description="原始数据(Base64)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class SensorAlertResponse(BaseModel):
    """传感器告警响应"""
    success: bool
    alert_id: UUID
    event_id: Optional[UUID] = Field(None, description="关联的事件ID")
    action_taken: str = Field(description="event_created/merged/ignored/logged")
    message: str


# ============================================================================
# 设备遥测
# ============================================================================

class TelemetryPayload(BaseModel):
    """遥测载荷"""
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    altitude: Optional[float] = Field(None, description="高度(米)")
    heading: Optional[float] = Field(None, ge=0, le=360, description="航向(度)")
    ground_speed: Optional[float] = Field(None, ge=0, description="地速(m/s)")
    accuracy: Optional[float] = Field(None, ge=0, description="定位精度(米)")
    battery_level: Optional[int] = Field(None, ge=0, le=100, description="电量(%)")
    voltage: Optional[float] = Field(None, description="电压(V)")
    temperature: Optional[float] = Field(None, description="温度(°C)")
    status: Optional[str] = Field(None, description="设备状态")
    mode: Optional[str] = Field(None, description="工作模式")
    errors: list[str] = Field(default_factory=list, description="错误列表")


class TelemetryItem(BaseModel):
    """单条遥测数据"""
    device_id: str = Field(..., max_length=100, description="设备ID")
    device_type: DeviceType = Field(..., description="设备类型")
    telemetry_type: TelemetryType = Field(default=TelemetryType.location, description="遥测类型")
    payload: TelemetryPayload = Field(..., description="遥测载荷")
    device_timestamp: datetime = Field(..., description="设备时间戳")
    sequence_no: Optional[int] = Field(None, ge=0, description="序列号")


class TelemetryBatchRequest(BaseModel):
    """批量遥测请求"""
    batch: list[TelemetryItem] = Field(..., min_length=1, max_length=100, description="遥测数据列表")


class TelemetryEntityUpdate(BaseModel):
    """遥测实体更新结果"""
    device_id: str
    entity_id: Optional[UUID] = None
    success: bool
    error: Optional[str] = None


class TelemetryResponse(BaseModel):
    """遥测响应"""
    success: bool
    received_count: int
    processed_count: int
    entity_updates: list[TelemetryEntityUpdate]


# ============================================================================
# 天气数据
# ============================================================================

class WeatherAlert(BaseModel):
    """天气预警"""
    alert_type: str = Field(..., max_length=50, description="预警类型")
    level: WeatherAlertLevel = Field(..., description="预警级别")
    message: str = Field(..., max_length=500, description="预警消息")
    issued_at: datetime = Field(..., description="发布时间")
    valid_until: datetime = Field(..., description="有效截止时间")


class WeatherForecast(BaseModel):
    """天气预报"""
    hour: int = Field(..., ge=1, le=72, description="预报小时数")
    weather_type: WeatherType = Field(..., description="天气类型")
    temperature: Optional[float] = Field(None, description="温度")
    wind_speed: Optional[float] = Field(None, ge=0, description="风速(m/s)")
    precipitation: Optional[float] = Field(None, ge=0, description="降水量(mm/h)")


class GeoJsonPolygon(BaseModel):
    """GeoJSON多边形"""
    type: str = Field(default="Polygon")
    coordinates: list[list[list[float]]] = Field(..., description="坐标数组")


class WeatherDataRequest(BaseModel):
    """天气数据请求"""
    area_id: str = Field(..., max_length=50, description="区域编码")
    area_name: str = Field(..., max_length=200, description="区域名称")
    coverage_area: Optional[GeoJsonPolygon] = Field(None, description="覆盖区域GeoJSON")
    weather_type: WeatherType = Field(..., description="天气类型")
    
    # 气象数据
    temperature: Optional[float] = Field(None, description="温度(°C)")
    wind_speed: Optional[float] = Field(None, ge=0, description="风速(m/s)")
    wind_direction: Optional[int] = Field(None, ge=0, le=360, description="风向(度)")
    visibility: Optional[int] = Field(None, ge=0, description="能见度(米)")
    precipitation: Optional[float] = Field(None, ge=0, description="降水量(mm/h)")
    humidity: Optional[int] = Field(None, ge=0, le=100, description="湿度(%)")
    pressure: Optional[float] = Field(None, description="气压(hPa)")
    
    # 预警和预报
    alerts: list[WeatherAlert] = Field(default_factory=list, description="预警信息")
    forecast: list[WeatherForecast] = Field(default_factory=list, description="预报数据")
    
    # 时间和来源
    recorded_at: datetime = Field(..., description="记录时间")
    valid_until: datetime = Field(..., description="有效截止时间")
    data_source: str = Field(default="meteorological_bureau", max_length=100, description="数据来源")


class WeatherDataResponse(BaseModel):
    """天气数据响应"""
    success: bool
    weather_id: UUID
    uav_flyable: bool = Field(description="是否适合无人机飞行")
    uav_restriction_reason: Optional[str] = Field(None, description="限飞原因")
    active_alerts_count: int


# ============================================================================
# 位置更新（车辆/队伍通用）
# ============================================================================

class LocationUpdateRequest(BaseModel):
    """位置更新请求"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    altitude_m: Optional[float] = Field(None, description="海拔高度(米)")
    heading: Optional[float] = Field(None, ge=0, le=360, description="航向(度)")
    speed_kmh: Optional[float] = Field(None, ge=0, description="速度(km/h)")
    accuracy_m: Optional[float] = Field(None, ge=0, description="定位精度(米)")
    timestamp: Optional[datetime] = Field(None, description="位置时间戳")


class LocationUpdateResponse(BaseModel):
    """位置更新响应"""
    success: bool
    resource_id: UUID
    entity_id: Optional[UUID] = Field(None, description="关联的地图实体ID")
    updated_at: datetime


# ============================================================================
# 设备遥测（单设备）
# ============================================================================

class DeviceTelemetryRequest(BaseModel):
    """设备遥测请求（单设备）"""
    timestamp: datetime = Field(..., description="时间戳")
    location: Optional[Location] = Field(None, description="位置信息")
    battery_level: Optional[int] = Field(None, ge=0, le=100, description="电量(%)")
    speed_kmh: Optional[float] = Field(None, ge=0, description="速度(km/h)")
    heading: Optional[float] = Field(None, ge=0, le=360, description="航向(度)")
    status: Optional[str] = Field(None, max_length=50, description="设备状态")
    mode: Optional[str] = Field(None, max_length=50, description="工作模式")
    sensor_data: dict[str, Any] = Field(default_factory=dict, description="传感器数据")


class DeviceTelemetryResponse(BaseModel):
    """设备遥测响应"""
    success: bool
    device_id: UUID
    entity_id: Optional[UUID] = None
    updated_at: datetime


# ============================================================================
# 外部系统回调
# ============================================================================

class CallbackType(str, Enum):
    """回调类型"""
    task_completed = "task_completed"
    task_failed = "task_failed"
    resource_status = "resource_status"
    system_event = "system_event"
    acknowledgment = "acknowledgment"


class CallbackRequest(BaseModel):
    """外部系统回调请求"""
    callback_type: CallbackType = Field(..., description="回调类型")
    reference_id: UUID = Field(..., description="关联的资源ID（任务/事件/设备等）")
    reference_type: str = Field(..., max_length=50, description="关联资源类型: task/event/device/team/vehicle")
    payload: dict[str, Any] = Field(default_factory=dict, description="回调载荷数据")
    status: str = Field(..., max_length=50, description="状态")
    message: Optional[str] = Field(None, max_length=500, description="回调消息")
    timestamp: datetime = Field(..., description="回调时间戳")
    source_system: str = Field(..., max_length=100, description="来源系统")


class CallbackResponse(BaseModel):
    """外部系统回调响应"""
    success: bool
    callback_id: UUID
    action_taken: str = Field(description="processed/queued/ignored")
    message: str
