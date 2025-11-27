"""
装备调度数据模型

定义装备需求、库存、分配等数据结构。
强类型注解，确保类型安全。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EquipmentType(str, Enum):
    """装备类型"""
    DEVICE = "device"    # 无人设备（drone/dog/ship/robot）
    SUPPLY = "supply"    # 物资中的装备（is_consumable=false）


class EquipmentPriority(str, Enum):
    """装备需求优先级"""
    REQUIRED = "required"       # 必须
    RECOMMENDED = "recommended"  # 推荐
    OPTIONAL = "optional"       # 可选


class LocationType(str, Enum):
    """存放位置类型"""
    SHELTER = "shelter"      # 安置点/仓库
    TEAM = "team"            # 队伍自带
    VEHICLE = "vehicle"      # 车辆装载
    WAREHOUSE = "warehouse"  # 独立仓库


class EquipmentRequirement(BaseModel):
    """装备需求（从能力推断）"""
    model_config = ConfigDict(populate_by_name=True)

    capability_code: str = Field(..., description="能力编码")
    equipment_type: EquipmentType = Field(..., description="装备类型")
    equipment_code: str = Field(..., description="装备编码")
    equipment_name: str = Field("", description="装备名称")
    min_quantity: int = Field(1, ge=1, description="最少需求数量")
    max_quantity: Optional[int] = Field(None, description="最大需求数量")
    priority: EquipmentPriority = Field(EquipmentPriority.REQUIRED, description="优先级")
    description: str = Field("", description="说明")


@dataclass
class EquipmentCandidate:
    """候选装备"""
    equipment_id: UUID
    equipment_code: str
    equipment_name: str
    equipment_type: EquipmentType
    
    # 位置信息
    location_type: LocationType
    location_id: UUID
    location_name: str
    longitude: float
    latitude: float
    
    # 数量
    available_quantity: int
    
    # 距离（调度时计算）
    distance_km: float = 0.0
    
    # 能力（如果是设备，可能有多个能力）
    capabilities: List[str] = field(default_factory=list)


@dataclass
class EquipmentAllocation:
    """装备分配结果"""
    equipment_id: UUID
    equipment_code: str
    equipment_name: str
    equipment_type: EquipmentType
    
    # 来源
    source_type: LocationType
    source_id: UUID
    source_name: str
    
    # 分配数量
    allocated_quantity: int
    
    # 分配给的能力需求
    for_capability: str
    
    # 距离
    distance_km: float


@dataclass
class EquipmentSchedulingResult:
    """装备调度结果"""
    success: bool
    allocations: List[EquipmentAllocation]
    
    # 需求满足情况
    required_met: int       # 必须装备满足数
    required_total: int     # 必须装备总数
    recommended_met: int    # 推荐装备满足数
    recommended_total: int  # 推荐装备总数
    
    # 统计
    total_equipment_count: int
    elapsed_ms: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def fulfillment_rate(self) -> float:
        """必须装备满足率"""
        return self.required_met / self.required_total if self.required_total > 0 else 1.0


class SupplyRequirement(BaseModel):
    """物资需求（消耗品）"""
    model_config = ConfigDict(populate_by_name=True)

    supply_code: str = Field(..., description="物资编码")
    supply_name: str = Field("", description="物资名称")
    category: str = Field("", description="物资类别")
    quantity: float = Field(..., ge=0, description="需求数量")
    unit: str = Field(..., description="计量单位")
    priority: str = Field("medium", description="优先级")


@dataclass
class SupplyAllocation:
    """物资分配结果"""
    supply_code: str
    supply_name: str
    
    # 来源仓库
    warehouse_id: UUID
    warehouse_name: str
    
    # 分配数量
    allocated_quantity: float
    unit: str
    
    # 距离
    distance_km: float


@dataclass
class SupplySchedulingResult:
    """物资调度结果"""
    success: bool
    allocations: List[SupplyAllocation]
    
    # 需求满足情况
    total_required: Dict[str, float]    # {supply_code: quantity}
    total_allocated: Dict[str, float]   # {supply_code: quantity}
    
    # 统计
    fulfillment_rate: float
    elapsed_ms: int
    errors: List[str] = field(default_factory=list)
