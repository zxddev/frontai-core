"""
救援队伍数据模型（Pydantic Schemas）

对应SQL表: operational_v2.rescue_teams_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class TeamType(str, Enum):
    """队伍类型枚举"""
    fire_rescue = "fire_rescue"          # 消防救援队
    medical = "medical"                  # 医疗救护队
    search_rescue = "search_rescue"      # 搜救队
    hazmat = "hazmat"                    # 危化品处置队
    engineering = "engineering"          # 工程抢险队
    communication = "communication"      # 通信保障队
    logistics = "logistics"              # 后勤保障队
    evacuation = "evacuation"            # 疏散转移队
    water_rescue = "water_rescue"        # 水上救援队
    mountain_rescue = "mountain_rescue"  # 山地救援队
    mine_rescue = "mine_rescue"          # 矿山救护队
    armed_police = "armed_police"        # 武警部队
    militia = "militia"                  # 民兵预备役
    volunteer = "volunteer"              # 志愿者队伍


class TeamStatus(str, Enum):
    """队伍状态"""
    standby = "standby"          # 待命
    deployed = "deployed"        # 已部署
    resting = "resting"          # 休整中
    unavailable = "unavailable"  # 不可用


class Location(BaseModel):
    """地理坐标"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class TeamCreate(BaseModel):
    """创建队伍请求"""
    code: str = Field(..., max_length=50, description="队伍编号，如RT-FR-001")
    name: str = Field(..., max_length=200, description="队伍名称")
    team_type: TeamType = Field(..., description="队伍类型")
    
    # 组织信息
    parent_org: Optional[str] = Field(None, max_length=200, description="上级单位名称")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人姓名")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    
    # 位置信息
    base_location: Optional[Location] = Field(None, description="驻地坐标")
    base_address: Optional[str] = Field(None, max_length=300, description="驻地详细地址")
    
    # 人员配置
    total_personnel: int = Field(0, ge=0, description="队伍总人数")
    available_personnel: int = Field(0, ge=0, description="当前可用人数")
    
    # 能力等级
    capability_level: int = Field(3, ge=1, le=5, description="能力等级1-5")
    certification_level: Optional[str] = Field(None, max_length=50, description="资质等级")
    
    # 响应能力
    response_time_minutes: Optional[int] = Field(None, ge=0, description="平均响应时间（分钟）")
    max_deployment_hours: int = Field(72, ge=1, description="最大连续部署时长（小时）")
    
    # 扩展
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class TeamUpdate(BaseModel):
    """更新队伍请求"""
    name: Optional[str] = Field(None, max_length=200, description="队伍名称")
    
    # 组织信息
    parent_org: Optional[str] = Field(None, max_length=200, description="上级单位名称")
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人姓名")
    contact_phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    
    # 位置信息
    base_location: Optional[Location] = Field(None, description="驻地坐标")
    base_address: Optional[str] = Field(None, max_length=300, description="驻地详细地址")
    
    # 人员配置
    total_personnel: Optional[int] = Field(None, ge=0, description="队伍总人数")
    available_personnel: Optional[int] = Field(None, ge=0, description="当前可用人数")
    
    # 能力等级
    capability_level: Optional[int] = Field(None, ge=1, le=5, description="能力等级1-5")
    certification_level: Optional[str] = Field(None, max_length=50, description="资质等级")
    
    # 响应能力
    response_time_minutes: Optional[int] = Field(None, ge=0, description="平均响应时间（分钟）")
    max_deployment_hours: Optional[int] = Field(None, ge=1, description="最大连续部署时长（小时）")
    
    # 状态
    status: Optional[TeamStatus] = Field(None, description="队伍状态")
    
    # 扩展
    properties: Optional[dict[str, Any]] = Field(None, description="扩展属性")


class TeamResponse(BaseModel):
    """队伍响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    team_type: TeamType
    
    # 组织信息
    parent_org: Optional[str]
    contact_person: Optional[str]
    contact_phone: Optional[str]
    
    # 位置信息
    base_location: Optional[Location]
    base_address: Optional[str]
    
    # 人员配置
    total_personnel: int
    available_personnel: int
    
    # 能力等级
    capability_level: int
    certification_level: Optional[str]
    
    # 响应能力
    response_time_minutes: Optional[int]
    max_deployment_hours: int
    
    # 状态
    status: TeamStatus
    current_task_id: Optional[UUID]
    
    # 扩展
    properties: dict[str, Any]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime


class TeamListResponse(BaseModel):
    """队伍列表响应"""
    items: list[TeamResponse]
    total: int
    page: int
    page_size: int


class TeamAvailabilityCheck(BaseModel):
    """队伍可用性检查结果"""
    team_id: UUID
    is_available: bool
    available_personnel: int
    status: TeamStatus
    current_task_id: Optional[UUID]
    message: Optional[str] = None


class TeamLocationUpdate(BaseModel):
    """队伍位置更新请求"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")
    heading: Optional[float] = Field(None, ge=0, lt=360, description="航向角(度)")
    source: str = Field("gps", description="位置来源: gps/manual/simulation")


class TeamLocationResponse(BaseModel):
    """队伍位置响应"""
    team_id: UUID
    longitude: float
    latitude: float
    last_update: datetime
    message: str
