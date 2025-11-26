"""
物资数据模型（Pydantic Schemas）

对应SQL表: operational_v2.supplies_v2
强类型注解，完整字段匹配
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class SupplyCategory(str, Enum):
    """物资类别枚举"""
    medical = "medical"              # 医疗物资
    protection = "protection"        # 防护装备
    rescue = "rescue"                # 救援器材
    communication = "communication"  # 通信设备
    life = "life"                    # 生活物资
    tool = "tool"                    # 工具


class SupplyUnit(str, Enum):
    """计量单位枚举"""
    piece = "piece"    # 件
    box = "box"        # 箱
    kg = "kg"          # 公斤
    set = "set"        # 套


class SupplyCreate(BaseModel):
    """创建物资请求"""
    code: str = Field(..., max_length=50, description="物资编号，如SP-MED-001")
    name: str = Field(..., max_length=200, description="物资名称")
    category: SupplyCategory = Field(..., description="物资类别")
    
    # 物理属性
    weight_kg: Decimal = Field(..., ge=0, description="单件重量（公斤）")
    volume_m3: Optional[Decimal] = Field(None, ge=0, description="单件体积（立方米）")
    unit: SupplyUnit = Field(SupplyUnit.piece, description="计量单位")
    
    # 灾害适用性
    applicable_disasters: Optional[list[str]] = Field(None, description="适用灾害类型")
    required_for_disasters: Optional[list[str]] = Field(None, description="必须携带的灾害类型")
    
    # 消耗属性
    is_consumable: bool = Field(True, description="是否消耗品")
    shelf_life_days: Optional[int] = Field(None, ge=0, description="保质期（天）")
    
    # 扩展
    properties: dict[str, Any] = Field(default_factory=dict, description="扩展属性")


class SupplyUpdate(BaseModel):
    """更新物资请求"""
    name: Optional[str] = Field(None, max_length=200, description="物资名称")
    category: Optional[SupplyCategory] = Field(None, description="物资类别")
    
    # 物理属性
    weight_kg: Optional[Decimal] = Field(None, ge=0, description="单件重量（公斤）")
    volume_m3: Optional[Decimal] = Field(None, ge=0, description="单件体积（立方米）")
    unit: Optional[SupplyUnit] = Field(None, description="计量单位")
    
    # 灾害适用性
    applicable_disasters: Optional[list[str]] = Field(None, description="适用灾害类型")
    required_for_disasters: Optional[list[str]] = Field(None, description="必须携带的灾害类型")
    
    # 消耗属性
    is_consumable: Optional[bool] = Field(None, description="是否消耗品")
    shelf_life_days: Optional[int] = Field(None, ge=0, description="保质期（天）")
    
    # 扩展
    properties: Optional[dict[str, Any]] = Field(None, description="扩展属性")


class SupplyResponse(BaseModel):
    """物资响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    category: SupplyCategory
    
    # 物理属性
    weight_kg: Decimal
    volume_m3: Optional[Decimal]
    unit: SupplyUnit
    
    # 灾害适用性
    applicable_disasters: Optional[list[str]]
    required_for_disasters: Optional[list[str]]
    
    # 消耗属性
    is_consumable: bool
    shelf_life_days: Optional[int]
    
    # 扩展
    properties: dict[str, Any]
    
    # 时间戳
    created_at: datetime


class SupplyListResponse(BaseModel):
    """物资列表响应"""
    items: list[SupplyResponse]
    total: int
    page: int
    page_size: int


class SupplyStockInfo(BaseModel):
    """物资库存信息（用于车辆装载查询）"""
    supply_id: UUID
    supply_code: str
    supply_name: str
    category: SupplyCategory
    loaded_quantity: int = Field(description="装载数量")
    weight_kg: Decimal
    unit: SupplyUnit
