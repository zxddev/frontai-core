"""
疏散安置点数据模型（Pydantic Schemas）

对应SQL表: public.evacuation_shelters_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ShelterType(str, Enum):
    """安置点类型枚举"""
    temporary = "temporary"          # 临时安置点
    permanent = "permanent"          # 固定安置点
    medical = "medical"              # 医疗救护点
    supply_depot = "supply_depot"    # 物资集散点
    command_post = "command_post"    # 指挥所
    helipad = "helipad"              # 直升机起降点
    staging_area = "staging_area"    # 集结区


class ShelterStatus(str, Enum):
    """安置点状态"""
    preparing = "preparing"    # 准备中
    open = "open"              # 开放
    full = "full"              # 已满
    limited = "limited"        # 限流
    closed = "closed"          # 关闭
    damaged = "damaged"        # 受损


class Location(BaseModel):
    """地理坐标"""
    longitude: float = Field(..., ge=-180, le=180, description="经度")
    latitude: float = Field(..., ge=-90, le=90, description="纬度")


class FacilitiesInfo(BaseModel):
    """设施配置"""
    medical: Optional[dict[str, Any]] = Field(None, description="医疗设施: {beds, doctors, nurses}")
    sanitation: Optional[dict[str, Any]] = Field(None, description="卫生设施: {toilets, showers}")
    food: Optional[dict[str, Any]] = Field(None, description="餐饮设施: {kitchen, capacity_per_meal}")
    water: Optional[dict[str, Any]] = Field(None, description="供水设施: {supply_type, daily_capacity_liters}")
    power: Optional[dict[str, Any]] = Field(None, description="供电设施: {source, backup_hours}")
    communication: Optional[dict[str, Any]] = Field(None, description="通信设施: {phone, internet}")


class AccessibilityInfo(BaseModel):
    """无障碍设施"""
    wheelchair_accessible: bool = Field(False, description="轮椅通道")
    sign_language: bool = Field(False, description="手语服务")
    medical_equipment: bool = Field(False, description="医疗设备")


class SpecialAccommodationsInfo(BaseModel):
    """特殊人群容纳能力"""
    elderly_capacity: int = Field(0, ge=0, description="老人容量")
    children_capacity: int = Field(0, ge=0, description="儿童容量")
    disabled_capacity: int = Field(0, ge=0, description="残障人士容量")
    medical_patients: int = Field(0, ge=0, description="病患容量")


class SupplyInventoryInfo(BaseModel):
    """物资储备"""
    water_bottles: int = Field(0, ge=0, description="饮用水瓶数")
    food_packages: int = Field(0, ge=0, description="食品包数")
    blankets: int = Field(0, ge=0, description="毛毯数量")
    medicine_kits: int = Field(0, ge=0, description="医药包数量")


class ShelterCreate(BaseModel):
    """创建安置点请求"""
    shelter_code: str = Field(..., max_length=50, description="安置点编号")
    name: str = Field(..., max_length=200, description="安置点名称")
    shelter_type: ShelterType = Field(..., description="安置点类型")
    
    # 关联想定
    scenario_id: Optional[UUID] = Field(None, description="所属想定ID，NULL表示常备安置点")
    
    # 位置信息
    location: Location = Field(..., description="安置点坐标")
    address: Optional[str] = Field(None, description="详细地址")
    
    # 容量
    total_capacity: int = Field(..., ge=1, description="总容量（人数）")
    
    # 联系人
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    contact_backup: Optional[str] = Field(None, max_length=50, description="备用电话")
    managing_organization: Optional[str] = Field(None, max_length=200, description="管理单位")
    
    # 设施配置
    facilities: Optional[dict[str, Any]] = Field(default_factory=dict, description="设施配置")
    accessibility: Optional[dict[str, Any]] = Field(default_factory=dict, description="无障碍设施")
    special_accommodations: Optional[dict[str, Any]] = Field(default_factory=dict, description="特殊人群容纳")
    supply_inventory: Optional[dict[str, Any]] = Field(default_factory=dict, description="物资储备")
    
    # 备注
    notes: Optional[str] = Field(None, description="备注")


class ShelterUpdate(BaseModel):
    """更新安置点请求"""
    name: Optional[str] = Field(None, max_length=200, description="安置点名称")
    
    # 位置信息
    location: Optional[Location] = Field(None, description="安置点坐标")
    address: Optional[str] = Field(None, description="详细地址")
    
    # 联系人
    contact_person: Optional[str] = Field(None, max_length=100, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=50, description="联系电话")
    contact_backup: Optional[str] = Field(None, max_length=50, description="备用电话")
    managing_organization: Optional[str] = Field(None, max_length=200, description="管理单位")
    
    # 设施配置
    facilities: Optional[dict[str, Any]] = Field(None, description="设施配置")
    accessibility: Optional[dict[str, Any]] = Field(None, description="无障碍设施")
    special_accommodations: Optional[dict[str, Any]] = Field(None, description="特殊人群容纳")
    supply_inventory: Optional[dict[str, Any]] = Field(None, description="物资储备")
    
    # 备注
    notes: Optional[str] = Field(None, description="备注")


class ShelterCapacityUpdate(BaseModel):
    """更新安置点容量"""
    total_capacity: Optional[int] = Field(None, ge=1, description="总容量")
    current_occupancy: Optional[int] = Field(None, ge=0, description="当前入住人数")


class ShelterStatusUpdate(BaseModel):
    """更新安置点状态"""
    status: ShelterStatus = Field(..., description="目标状态")


class ShelterResponse(BaseModel):
    """安置点响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    scenario_id: Optional[UUID]
    shelter_code: str
    name: str
    shelter_type: ShelterType
    
    # 位置
    location: Optional[Location]
    address: Optional[str]
    
    # 状态
    status: ShelterStatus
    
    # 容量
    total_capacity: int
    current_occupancy: int
    available_capacity: int
    occupancy_rate: float = Field(description="入住率百分比")
    
    # 设施配置
    facilities: dict[str, Any]
    accessibility: dict[str, Any]
    special_accommodations: dict[str, Any]
    supply_inventory: dict[str, Any]
    
    # 联系人
    contact_person: Optional[str]
    contact_phone: Optional[str]
    contact_backup: Optional[str]
    managing_organization: Optional[str]
    
    # 时间
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    
    # 关联
    entity_id: Optional[UUID]
    notes: Optional[str]
    
    # 时间戳
    created_at: datetime
    updated_at: datetime


class ShelterListResponse(BaseModel):
    """安置点列表响应"""
    items: list[ShelterResponse]
    total: int
    page: int
    page_size: int


class ShelterNearbyQuery(BaseModel):
    """查找最近安置点请求"""
    location: Location = Field(..., description="查询中心点")
    scenario_id: Optional[UUID] = Field(None, description="想定ID")
    required_capacity: int = Field(1, ge=1, description="需要的容量")
    limit: int = Field(5, ge=1, le=20, description="返回数量上限")


class ShelterNearbyResult(BaseModel):
    """附近安置点结果"""
    shelter_id: UUID
    name: str
    shelter_type: ShelterType
    distance_meters: float = Field(description="距离（米）")
    available_capacity: int
    facilities: dict[str, Any]
