"""
统一路径规划请求/响应模型

用于 HTTP 接口层，与现有 dataclass 模型配合使用
"""
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PointRequest(BaseModel):
    """坐标点请求模型"""
    lon: float = Field(..., description="经度")
    lat: float = Field(..., description="纬度")


class AvoidAreaRequest(BaseModel):
    """避让区域请求模型"""
    polygon: List[PointRequest] = Field(..., description="多边形顶点列表")
    reason: str = Field(default="", description="避让原因")
    severity: str = Field(default="hard", description="严重程度: hard/soft")


class RoutePlanRequest(BaseModel):
    """路径规划请求"""
    device_id: UUID = Field(..., description="设备ID，用于确定规划类型")
    origin: PointRequest = Field(..., description="起点坐标")
    destination: PointRequest = Field(..., description="终点坐标")
    avoid_areas: List[AvoidAreaRequest] = Field(default_factory=list, description="避让区域列表（仅陆地规划有效）")


class PointResponse(BaseModel):
    """坐标点响应模型"""
    lon: float
    lat: float


class RouteSegmentResponse(BaseModel):
    """路径段响应模型"""
    from_point: PointResponse
    to_point: PointResponse
    distance_m: float
    duration_s: float
    instruction: str = ""
    road_name: str = ""


class RoutePlanResponse(BaseModel):
    """路径规划响应"""
    source: str = Field(..., description="规划来源: amap/internal/fallback/air_direct")
    success: bool = Field(..., description="是否成功")
    origin: PointResponse = Field(..., description="起点")
    destination: PointResponse = Field(..., description="终点")
    total_distance_m: float = Field(..., description="总距离（米）")
    total_duration_s: float = Field(..., description="总时间（秒）")
    segments: List[RouteSegmentResponse] = Field(default_factory=list, description="路径段列表")
    polyline: List[PointResponse] = Field(default_factory=list, description="路径点列表")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    env_type: Optional[str] = Field(default=None, description="设备环境类型: air/land/sea")


# ============================================================================
# 带风险检测的路径规划请求/响应模型
# ============================================================================

class RiskCheckRoutePlanRequest(BaseModel):
    """带风险检测的路径规划请求"""
    device_id: UUID = Field(..., description="设备ID")
    origin: PointRequest = Field(..., description="起点坐标")
    destination: PointRequest = Field(..., description="终点坐标")
    scenario_id: UUID = Field(..., description="场景ID，用于查询风险区域")
    task_id: Optional[UUID] = Field(default=None, description="任务ID（用于WS通知）")
    team_id: Optional[UUID] = Field(default=None, description="队伍ID（用于WS通知）")


class RiskAreaResponse(BaseModel):
    """风险区域信息"""
    id: UUID = Field(..., description="风险区域ID")
    name: str = Field(..., description="风险区域名称")
    risk_level: int = Field(..., description="风险等级 1-10")
    passage_status: str = Field(..., description="通行状态")
    area_type: str = Field(..., description="区域类型")
    description: Optional[str] = Field(default=None, description="描述")


class AlternativeRouteResponse(BaseModel):
    """绕行方案"""
    strategy: str = Field(..., description="方案标识: recommended/fastest/safest")
    strategy_name: str = Field(..., description="方案名称")
    distance_m: float = Field(..., description="距离（米）")
    duration_s: float = Field(..., description="时间（秒）")
    polyline: List[PointResponse] = Field(default_factory=list, description="路径点列表")
    description: str = Field(default="", description="方案描述")


class RiskCheckRoutePlanResponse(BaseModel):
    """带风险检测的路径规划响应"""
    # 最快路径（可能穿过风险区域）
    fastest_route: RoutePlanResponse = Field(..., description="最快路径")
    
    # 风险信息
    has_risk: bool = Field(..., description="是否存在风险")
    risk_areas: List[RiskAreaResponse] = Field(default_factory=list, description="途经的风险区域")
    
    # 绕行方案（仅当 has_risk=True 且为陆地设备时提供）
    alternative_routes: List[AlternativeRouteResponse] = Field(
        default_factory=list,
        description="绕行方案列表（最多3个）"
    )
    
    # 决策相关
    requires_decision: bool = Field(default=False, description="是否需要队长决策")
    available_actions: List[str] = Field(
        default_factory=list,
        description="可用操作: continue/detour_recommended/detour_fastest/detour_safest/standby"
    )
    
    # 环境类型
    env_type: str = Field(..., description="设备环境类型: air/land/sea")


class ConfirmRouteRequest(BaseModel):
    """确认路径选择请求"""
    task_id: UUID = Field(..., description="任务ID")
    team_id: Optional[UUID] = Field(default=None, description="队伍ID")
    device_id: UUID = Field(..., description="设备ID")
    action: str = Field(..., description="选择的操作: continue/detour_recommended/detour_fastest/detour_safest/standby")
    route_polyline: Optional[List[PointRequest]] = Field(
        default=None,
        description="选择的路径（action为detour时必填）"
    )


class ConfirmRouteResponse(BaseModel):
    """确认路径选择响应"""
    success: bool = Field(..., description="是否成功")
    action: str = Field(..., description="执行的操作")
    message: str = Field(..., description="结果描述")


# ============================================================================
# 路径存储和查询相关模型
# ============================================================================

class PlanAndSaveRequest(BaseModel):
    """规划并存储路径请求"""
    device_id: UUID = Field(..., description="设备ID")
    origin: PointRequest = Field(..., description="起点坐标")
    destination: PointRequest = Field(..., description="终点坐标")
    task_id: Optional[UUID] = Field(default=None, description="任务ID（task_requirements_v2）")
    team_id: Optional[UUID] = Field(default=None, description="队伍ID")
    vehicle_id: Optional[UUID] = Field(default=None, description="车辆ID")
    scenario_id: Optional[UUID] = Field(default=None, description="场景ID（用于风险检测）")


class PlanAndSaveResponse(BaseModel):
    """规划并存储路径响应"""
    success: bool = Field(..., description="是否成功")
    route_id: Optional[str] = Field(default=None, description="路径ID")
    route: Optional[dict] = Field(default=None, description="路径信息")
    has_risk: bool = Field(default=False, description="是否存在风险")
    risk_areas: List[dict] = Field(default_factory=list, description="风险区域列表")
    error: Optional[str] = Field(default=None, description="错误信息")


class GenerateAlternativesRequest(BaseModel):
    """生成绕行方案请求"""
    task_id: UUID = Field(..., description="任务ID")
    origin: PointRequest = Field(..., description="起点坐标")
    destination: PointRequest = Field(..., description="终点坐标")
    risk_area_ids: List[UUID] = Field(..., description="需要避让的风险区域ID列表")
    team_id: Optional[UUID] = Field(default=None, description="队伍ID")
    vehicle_id: Optional[UUID] = Field(default=None, description="车辆ID")


class GenerateAlternativesResponse(BaseModel):
    """生成绕行方案响应"""
    success: bool = Field(..., description="是否成功")
    alternatives: List[dict] = Field(default_factory=list, description="绕行方案列表")
    alternative_count: int = Field(default=0, description="方案数量")
    error: Optional[str] = Field(default=None, description="错误信息")


class ConfirmRouteByIdRequest(BaseModel):
    """按ID确认路径请求"""
    route_id: UUID = Field(..., description="选中的路径ID")
    task_id: UUID = Field(..., description="任务ID")


class PlannedRouteResponse(BaseModel):
    """已存储的路径响应"""
    route_id: str = Field(..., description="路径ID")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    vehicle_id: Optional[str] = Field(default=None, description="车辆ID")
    team_id: Optional[str] = Field(default=None, description="队伍ID")
    total_distance_m: float = Field(..., description="总距离（米）")
    estimated_time_minutes: int = Field(..., description="预计时间（分钟）")
    risk_level: int = Field(default=1, description="风险等级 1-10")
    status: str = Field(..., description="状态: planned/active/completed/cancelled/alternative/replaced")
    planned_at: Optional[str] = Field(default=None, description="规划时间")
    properties: dict = Field(default_factory=dict, description="扩展属性")
    polyline: List[PointResponse] = Field(default_factory=list, description="路径点列表")


class PlannedRouteListResponse(BaseModel):
    """路径列表响应"""
    routes: List[PlannedRouteResponse] = Field(default_factory=list, description="路径列表")
    total: int = Field(default=0, description="总数")
