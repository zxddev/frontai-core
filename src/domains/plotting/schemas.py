"""
态势标绘数据模型

定义标绘请求/响应的强类型Schema。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlottingType(str, Enum):
    """标绘类型枚举 - 对应前端渲染效果"""
    # 点类
    event_point = "event_point"              # 事件点
    rescue_target = "rescue_target"          # 救援目标（波纹动画）
    situation_point = "situation_point"      # 态势标注（文字）
    resettle_point = "resettle_point"        # 安置点
    resource_point = "resource_point"        # 资源点
    
    # 圆形区域类
    danger_area = "danger_area"              # 危险区（橙色）
    safety_area = "safety_area"              # 安全区（绿色）
    command_post_candidate = "command_post_candidate"  # 指挥点（蓝色）
    
    # 多边形类
    investigation_area = "investigation_area"  # 侦查区域
    event_range = "event_range"              # 事件区域范围（三层多边形）
    
    # 路线类
    planned_route = "planned_route"          # 规划路线
    
    # 天气类
    weather_area = "weather_area"            # 天气区域（雨区）


class PlotPointRequest(BaseModel):
    """点标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    plotting_type: PlottingType = Field(..., description="标绘类型")
    name: str = Field(..., max_length=200, description="标绘名称")
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    description: Optional[str] = Field(None, description="描述内容")
    level: Optional[int] = Field(None, ge=1, le=5, description="严重等级1-5")
    extra_properties: Optional[Dict[str, Any]] = Field(None, description="额外属性")


class PlotCircleRequest(BaseModel):
    """圆形区域标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    plotting_type: PlottingType = Field(..., description="标绘类型: danger_area/safety_area/command_post_candidate")
    name: str = Field(..., max_length=200, description="区域名称")
    center_longitude: float = Field(..., ge=-180, le=180, description="中心经度")
    center_latitude: float = Field(..., ge=-90, le=90, description="中心纬度")
    radius_m: float = Field(..., gt=0, description="半径(米)")
    description: Optional[str] = Field(None, description="描述内容")
    is_selected: bool = Field(False, description="是否为已选中状态")


class PlotPolygonRequest(BaseModel):
    """多边形标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    plotting_type: PlottingType = Field(PlottingType.investigation_area, description="标绘类型")
    name: str = Field(..., max_length=200, description="区域名称")
    coordinates: List[List[float]] = Field(..., description="坐标数组 [[lng,lat], ...]")
    description: Optional[str] = Field(None, description="描述内容")


class PlotRouteRequest(BaseModel):
    """路线标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    name: str = Field(..., max_length=200, description="路线名称")
    coordinates: List[List[float]] = Field(..., description="路线点序列 [[lng,lat], ...]")
    device_type: str = Field("car", description="设备类型: car/uav/dog")
    is_selected: bool = Field(False, description="是否为选中路线")


class PlotEventRangeRequest(BaseModel):
    """事件区域范围标绘请求（三层多边形）"""
    scenario_id: UUID = Field(..., description="想定ID")
    name: str = Field(..., max_length=200, description="区域名称")
    outer_ring: List[List[float]] = Field(..., description="外圈坐标 [[lng,lat], ...]")
    middle_ring: List[List[float]] = Field(..., description="中圈坐标 [[lng,lat], ...]")
    inner_ring: List[List[float]] = Field(..., description="内圈坐标 [[lng,lat], ...]")
    description: Optional[str] = Field(None, description="描述内容")


class PlotWeatherAreaRequest(BaseModel):
    """天气区域标绘请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    name: str = Field(..., max_length=200, description="区域名称")
    min_longitude: float = Field(..., ge=-180, le=180, description="最小经度")
    min_latitude: float = Field(..., ge=-90, le=90, description="最小纬度")
    max_longitude: float = Field(..., ge=-180, le=180, description="最大经度")
    max_latitude: float = Field(..., ge=-90, le=90, description="最大纬度")
    description: Optional[str] = Field(None, description="描述内容")


class PlottingResponse(BaseModel):
    """标绘响应"""
    success: bool = Field(..., description="是否成功")
    entity_id: UUID = Field(..., description="创建的实体ID")
    entity_type: str = Field(..., description="实体类型")
    message: str = Field(..., description="结果消息")
