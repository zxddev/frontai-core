"""
装备准备智能体状态定义
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from uuid import UUID


class DeviceRecommendation(TypedDict, total=False):
    """设备推荐"""
    device_id: str
    device_name: str
    device_type: str  # drone/dog/ship/robot
    modules: List[Dict[str, Any]]  # [{module_id, module_name, reason}]
    reason: str       # AI生成的选择理由
    priority: str     # critical/high/medium/low


class SupplyRecommendation(TypedDict, total=False):
    """物资推荐"""
    supply_id: str
    supply_name: str
    quantity: int
    unit: str
    reason: str
    priority: str


class ShortageAlert(TypedDict, total=False):
    """缺口告警"""
    item_type: str    # device/module/supply
    item_name: str
    required: int
    available: int
    shortage: int
    severity: str     # critical/warning
    suggestion: str   # 调配建议


class RequirementSpec(TypedDict, total=False):
    """需求规格"""
    required_capabilities: List[str]      # 所需能力列表
    required_device_types: List[str]      # 所需设备类型
    required_supply_categories: List[str] # 所需物资类别
    environment_factors: List[str]        # 环境因素
    estimated_personnel: int              # 预估救援人数需求
    special_requirements: List[str]       # 特殊要求


class WarehouseInventory(TypedDict, total=False):
    """仓库库存"""
    devices: List[Dict[str, Any]]   # 可用设备列表
    modules: List[Dict[str, Any]]   # 可用模块列表
    supplies: List[Dict[str, Any]]  # 物资库存列表


class LoadingPlanItem(TypedDict, total=False):
    """装载计划项"""
    vehicle_id: str
    vehicle_name: str
    devices: List[str]              # 设备ID列表
    supplies: List[Dict[str, Any]]  # [{supply_id, quantity}]
    weight_usage: float             # 载重利用率
    volume_usage: float             # 容积利用率


class EquipmentPreparationState(TypedDict, total=False):
    """装备准备智能体完整状态"""
    
    # ==================== 输入 ====================
    event_id: str                   # 关联事件ID
    disaster_description: str       # 灾情描述
    structured_input: Dict[str, Any]  # 结构化输入
    
    # ==================== 灾情分析（Phase 1）====================
    parsed_disaster: Optional[Dict[str, Any]]  # 灾情解析结果
    similar_cases: List[Dict[str, Any]]        # 相似案例
    understanding_summary: str                  # 理解摘要
    
    # ==================== 需求分析（Phase 2）====================
    requirement_spec: Optional[RequirementSpec]  # 需求规格
    
    # ==================== 仓库查询（Phase 3）====================
    warehouse_inventory: Optional[WarehouseInventory]  # 仓库库存
    
    # ==================== 匹配推荐（Phase 4）====================
    recommended_devices: List[DeviceRecommendation]   # 推荐设备
    recommended_supplies: List[SupplyRecommendation]  # 推荐物资
    
    # ==================== 缺口分析（Phase 5）====================
    shortage_alerts: List[ShortageAlert]  # 缺口告警
    
    # ==================== 装载方案（Phase 6）====================
    loading_plan: Dict[str, LoadingPlanItem]  # 装载方案
    
    # ==================== 追踪信息 ====================
    errors: List[str]
    trace: Dict[str, Any]
    current_phase: str
