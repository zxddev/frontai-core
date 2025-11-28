"""
移动仿真数据模型

定义移动会话、路径点、任务停靠点等核心数据结构
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MovementState(str, Enum):
    """移动状态枚举"""
    PENDING = "pending"                    # 等待开始
    MOVING = "moving"                      # 移动中
    PAUSED = "paused"                      # 暂停
    EXECUTING_TASK = "executing_task"      # 执行任务中
    COMPLETED = "completed"                # 已完成
    CANCELLED = "cancelled"                # 已取消


class EntityType(str, Enum):
    """可移动实体类型"""
    VEHICLE = "vehicle"
    TEAM = "team"
    UAV = "uav"
    ROBOTIC_DOG = "robotic_dog"
    USV = "usv"


class FormationType(str, Enum):
    """编队类型"""
    CONVOY = "convoy"          # 纵队：依次出发
    PARALLEL = "parallel"      # 并行：同时出发
    STAGGERED = "staggered"    # 交错：奇偶分组出发


# ============================================================================
# 基础几何类型
# ============================================================================

class Point(BaseModel):
    """地理坐标点"""
    lon: float = Field(..., ge=-180, le=180, description="经度")
    lat: float = Field(..., ge=-90, le=90, description="纬度")
    alt: Optional[float] = Field(None, description="高度（米），无人机专用")


class Waypoint(BaseModel):
    """任务停靠点"""
    point_index: int = Field(..., ge=0, description="路径中的点索引")
    task_type: str = Field(..., description="任务类型: rescue/investigation/supply_drop")
    task_duration_s: int = Field(..., ge=0, description="停靠时长（秒）")
    task_data: dict[str, Any] = Field(default_factory=dict, description="任务参数")
    
    executed: bool = Field(False, description="是否已执行")
    executed_at: Optional[datetime] = Field(None, description="执行时间")


# ============================================================================
# 移动会话
# ============================================================================

class MovementSession(BaseModel):
    """移动会话状态"""
    model_config = ConfigDict(from_attributes=True)
    
    session_id: str = Field(..., description="会话唯一标识")
    entity_id: UUID = Field(..., description="地图实体ID")
    entity_type: EntityType = Field(..., description="实体类型")
    resource_id: Optional[UUID] = Field(None, description="资源ID（车辆/队伍/设备）")
    
    # 路径信息
    route: list[Point] = Field(..., description="路径点序列")
    total_distance_m: float = Field(..., ge=0, description="总距离（米）")
    segment_distances: list[float] = Field(default_factory=list, description="各段距离")
    
    # 进度信息
    current_segment_index: int = Field(0, ge=0, description="当前路段索引")
    segment_progress: float = Field(0.0, ge=0, le=1, description="当前路段进度(0-1)")
    traveled_distance_m: float = Field(0.0, ge=0, description="已行驶距离（米）")
    
    # 速度和朝向
    speed_mps: float = Field(..., gt=0, description="速度（米/秒）")
    current_heading: float = Field(0.0, ge=0, lt=360, description="当前朝向角度")
    
    # 状态
    state: MovementState = Field(MovementState.PENDING, description="移动状态")
    
    # 任务停靠点
    waypoints: list[Waypoint] = Field(default_factory=list, description="任务停靠点")
    current_waypoint_index: int = Field(0, description="当前停靠点索引")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(None, description="开始移动时间")
    paused_at: Optional[datetime] = Field(None, description="暂停时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    last_update_at: Optional[datetime] = Field(None, description="最后更新时间")
    
    # 暂停累计时间（用于计算有效行驶时间）
    total_pause_duration_s: float = Field(0.0, description="累计暂停时长（秒）")


class BatchMovementSession(BaseModel):
    """批量移动会话"""
    batch_id: str = Field(..., description="批量会话ID")
    sessions: list[str] = Field(..., description="子会话ID列表")
    formation: FormationType = Field(FormationType.CONVOY, description="编队类型")
    interval_s: float = Field(5.0, ge=0, description="实体间隔时间（秒）")
    
    state: MovementState = Field(MovementState.PENDING, description="整体状态")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# API请求/响应模型
# ============================================================================

class MovementStartRequest(BaseModel):
    """启动移动请求"""
    entity_id: UUID = Field(..., description="地图实体ID")
    entity_type: EntityType = Field(..., description="实体类型")
    resource_id: Optional[UUID] = Field(None, description="资源ID（用于获取速度）")
    route: list[list[float]] = Field(..., min_length=2, description="路径 [[lng,lat], ...]")
    speed_mps: Optional[float] = Field(None, gt=0, description="覆盖速度（米/秒）")
    waypoints: list[Waypoint] = Field(default_factory=list, description="任务停靠点")


class MovementStartResponse(BaseModel):
    """启动移动响应"""
    session_id: str
    entity_id: UUID
    state: MovementState
    total_distance_m: float
    estimated_duration_s: float
    speed_mps: float


class BatchMovementStartRequest(BaseModel):
    """批量启动移动请求"""
    movements: list[MovementStartRequest] = Field(..., min_length=1, description="移动请求列表")
    formation: FormationType = Field(FormationType.CONVOY, description="编队类型")
    interval_s: float = Field(5.0, ge=0, description="间隔时间（秒）")
    shared_route: Optional[list[list[float]]] = Field(None, description="共享路径（覆盖各自路径）")


class BatchMovementStartResponse(BaseModel):
    """批量启动移动响应"""
    batch_id: str
    sessions: list[MovementStartResponse]
    formation: FormationType
    total_entities: int


class MovementStatusResponse(BaseModel):
    """移动状态响应"""
    session_id: str
    entity_id: UUID
    state: MovementState
    
    # 当前位置
    current_position: Point
    current_heading: float
    
    # 进度
    progress_percent: float = Field(..., ge=0, le=100)
    traveled_distance_m: float
    remaining_distance_m: float
    
    # 时间
    elapsed_time_s: float
    estimated_remaining_s: float
    
    # 任务停靠点
    next_waypoint: Optional[Waypoint] = None
    completed_waypoints: int


class ActiveSessionsResponse(BaseModel):
    """活跃会话列表响应"""
    total: int
    sessions: list[MovementStatusResponse]


# ============================================================================
# WebSocket事件载荷
# ============================================================================

class MovementEventPayload(BaseModel):
    """移动事件载荷（WebSocket推送）"""
    session_id: str
    entity_id: str
    entity_type: str
    event_type: str  # started/paused/resumed/completed/cancelled/waypoint_reached
    
    # 位置信息（部分事件包含）
    position: Optional[Point] = None
    heading: Optional[float] = None
    
    # 进度信息
    progress_percent: Optional[float] = None
    
    # 任务点信息（waypoint_reached事件）
    waypoint: Optional[Waypoint] = None
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class LocationUpdatePayload(BaseModel):
    """实时位置更新载荷（复用现有 /topic/realtime.location）"""
    id: str = Field(..., description="实体ID")
    type: str = Field(..., description="实体类型")
    location: dict = Field(..., description="位置 {longitude, latitude}")
    speed_kmh: Optional[float] = Field(None, description="速度 km/h")
    heading: Optional[int] = Field(None, description="朝向 0-360")
