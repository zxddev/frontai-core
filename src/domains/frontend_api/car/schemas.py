"""
前端车辆装备模块数据结构
"""

from typing import Any, Optional, Literal
from pydantic import BaseModel, Field


class ModuleData(BaseModel):
    """模块数据（Level 3）"""
    id: str
    name: str
    moduleType: str = ""  # sensor/communication/utility/power
    isSelected: int = 0
    aiReason: Optional[str] = None
    exclusiveToDeviceId: Optional[str] = None  # 专属设备ID，非NULL只能被该设备使用


class ItemData(BaseModel):
    """装备/物资数据（Level 2）"""
    id: str
    name: str
    model: str = ""
    type: Literal["device", "supply"] = "device"
    isSelected: int = 0
    aiReason: Optional[str] = None
    priority: Optional[str] = None
    assignedToVehicle: Optional[str] = None  # AI分配到哪辆车（车辆ID）
    assignedToVehicleName: Optional[str] = None  # AI分配到哪辆车（车辆名称）
    exclusiveToVehicleId: Optional[str] = None  # 专属车辆ID，非NULL只能被该车辆选择
    exclusiveToVehicleName: Optional[str] = None  # 专属车辆名称
    hasModules: bool = False
    modules: list[ModuleData] = Field(default_factory=list)
    # 展示字段
    image: Optional[str] = None              # 设备图片URL
    description: Optional[str] = None        # 设备描述
    manufacturer: Optional[str] = None       # 生产厂家
    specifications: Optional[dict] = None    # 规格参数


class ShortageAlertData(BaseModel):
    """缺口告警数据"""
    itemType: str
    itemName: str
    required: int
    available: int
    shortage: int
    severity: str
    suggestion: str


class CarItem(BaseModel):
    """车辆数据（Level 1）"""
    id: str
    code: Optional[str] = None  # 车辆编号，如 VH-001
    name: str
    status: Literal["available", "preparing", "ready"] = "available"
    isSelected: bool = False  # AI推荐的车辆标记True
    isBelongsToThisCar: int = 0
    itemDataList: list[ItemData] = Field(default_factory=list)


class CarListData(BaseModel):
    """车辆列表响应"""
    carItemDataList: list[CarItem] = Field(default_factory=list)
    carQuestStatus: Literal["pending", "dispatched", "ready", "departed"] = "pending"
    recommendationId: Optional[str] = None
    recommendationStatus: Optional[str] = None
    shortageAlerts: Optional[list[ShortageAlertData]] = None


class ItemProperty(BaseModel):
    """装备属性"""
    key: str
    value: str


class ItemDetail(BaseModel):
    """装备详情"""
    image: str = ""
    properties: list[ItemProperty] = Field(default_factory=list)


class ItemDetailResponse(BaseModel):
    """装备详情响应"""
    itemDetail: str  # JSON字符串


class CarItemSelect(BaseModel):
    """车辆装备选择"""
    carId: str
    deviceIdList: list[str] = Field(default_factory=list)
    supplyIdList: list[str] = Field(default_factory=list)


class SupplyAssignment(BaseModel):
    """物资分配"""
    supplyId: str
    quantity: int
    supplyName: Optional[str] = None


class CarItemSelectV2(BaseModel):
    """车辆装备选择（V2版本，支持物资数量）"""
    carId: str
    deviceIds: list[str] = Field(default_factory=list)
    supplies: list[SupplyAssignment] = Field(default_factory=list)


class EquipmentDispatchRequest(BaseModel):
    """装备清单下发请求"""
    eventId: str
    assignments: list[CarItemSelectV2]


class UserPreparingRequest(BaseModel):
    """用户确认收到请求"""
    eventId: str
    carId: str
    userId: str


class CarReadyRequest(BaseModel):
    """车辆准备完成请求"""
    eventId: str
    carId: str
    userId: str


class DispatchStatusItem(BaseModel):
    """调度状态项"""
    vehicleId: str
    vehicleName: str
    status: str
    assigneeUserId: Optional[str] = None
    assigneeName: Optional[str] = None
    dispatchedAt: Optional[str] = None
    confirmedAt: Optional[str] = None
    readyAt: Optional[str] = None


class DispatchStatusResponse(BaseModel):
    """调度状态响应"""
    eventId: str
    totalVehicles: int
    confirmedCount: int
    readyCount: int
    items: list[DispatchStatusItem]


class EventIdForm(BaseModel):
    """事件ID表单"""
    eventId: str


# ==================== 装备分配相关 Schema ====================

class CarItemAddRequest(BaseModel):
    """添加装备到车辆请求"""
    eventId: str
    carId: str
    itemId: str
    itemType: Literal["device", "supply", "module"]
    quantity: int = 1
    parentDeviceId: Optional[str] = None


class CarItemAddResponse(BaseModel):
    """添加装备响应"""
    carId: str
    itemId: str
    assignedAt: str


class CarItemRemoveRequest(BaseModel):
    """从车辆移除装备请求"""
    eventId: str
    carId: str
    itemId: str
    itemType: Literal["device", "supply", "module"]


class CarItemRemoveResponse(BaseModel):
    """移除装备响应"""
    carId: str
    itemId: str
    returnedToWarehouse: bool = True


class CarItemToggleRequest(BaseModel):
    """切换专属装备选中状态请求"""
    eventId: str
    carId: str
    itemId: str
    isSelected: bool


class ModuleToggleItem(BaseModel):
    """模块选中状态项"""
    id: str
    isSelected: bool


class CarItemToggleResponse(BaseModel):
    """切换装备响应"""
    carId: str
    itemId: str
    isSelected: bool
    modules: list[ModuleToggleItem] = Field(default_factory=list)


class CarModuleUpdateRequest(BaseModel):
    """批量更新模块选中状态请求"""
    eventId: str
    carId: str
    deviceId: str
    moduleIds: list[str]


class CarModuleUpdateResponse(BaseModel):
    """模块更新响应"""
    deviceId: str
    modules: list[ModuleToggleItem]


# ==================== 车辆成员装备查看/修改 Schema ====================

class MyEquipmentModule(BaseModel):
    """我的装备-模块"""
    id: str
    name: str
    moduleType: str = ""
    isSelected: bool = True


class MyEquipmentDevice(BaseModel):
    """我的装备-设备"""
    id: str
    name: str
    model: str = ""
    deviceType: str = ""
    quantity: int = 1
    modules: list[MyEquipmentModule] = Field(default_factory=list)
    # 展示字段
    image: Optional[str] = None              # 设备图片URL
    description: Optional[str] = None        # 设备描述
    manufacturer: Optional[str] = None       # 生产厂家
    specifications: Optional[dict] = None    # 规格参数


class MyEquipmentSupply(BaseModel):
    """我的装备-物资"""
    id: str
    name: str
    category: str = ""
    quantity: int = 1


class MyEquipmentData(BaseModel):
    """我的车辆装备清单数据"""
    vehicleId: str
    vehicleName: str
    vehicleCode: Optional[str] = None
    vehicleStatus: str = "preparing"
    devices: list[MyEquipmentDevice] = Field(default_factory=list)
    supplies: list[MyEquipmentSupply] = Field(default_factory=list)
    dispatchedAt: Optional[str] = None
    dispatchedBy: Optional[str] = None


class MyEquipmentToggleRequest(BaseModel):
    """车辆成员切换装备选中状态请求"""
    eventId: str
    userId: str
    itemId: str
    itemType: Literal["device", "supply", "module"] = "device"
    isSelected: bool


class MyEquipmentToggleResponse(BaseModel):
    """车辆成员切换装备响应"""
    vehicleId: str
    itemId: str
    isSelected: bool
    updatedBy: str
