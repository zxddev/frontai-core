"""
装备推荐 Schemas
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ModuleRecommendationSchema(BaseModel):
    """模块推荐"""
    module_id: str = Field(..., description="模块ID")
    module_name: str = Field(..., description="模块名称")
    reason: str = Field(default="", description="配置理由")


class DeviceRecommendationSchema(BaseModel):
    """设备推荐"""
    device_id: str = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    device_type: str = Field(..., description="设备类型")
    modules: List[ModuleRecommendationSchema] = Field(default_factory=list, description="推荐模块")
    reason: str = Field(..., description="选择理由")
    priority: str = Field(..., description="优先级: critical/high/medium/low")


class SupplyRecommendationSchema(BaseModel):
    """物资推荐"""
    supply_id: str = Field(..., description="物资ID")
    supply_name: str = Field(..., description="物资名称")
    quantity: int = Field(..., description="推荐数量")
    unit: str = Field(default="piece", description="单位")
    reason: str = Field(..., description="选择理由")
    priority: str = Field(..., description="优先级")


class ShortageAlertSchema(BaseModel):
    """缺口告警"""
    item_type: str = Field(..., description="类型: device/module/supply")
    item_name: str = Field(..., description="物品名称")
    required: int = Field(..., description="需求量")
    available: int = Field(..., description="可用量")
    shortage: int = Field(..., description="缺口量")
    severity: str = Field(..., description="严重程度: critical/warning")
    suggestion: str = Field(..., description="调配建议")


class LoadingPlanItemSchema(BaseModel):
    """装载计划项"""
    vehicle_id: str = Field(..., description="车辆ID")
    vehicle_name: str = Field(..., description="车辆名称")
    devices: List[str] = Field(default_factory=list, description="设备ID列表")
    supplies: List[Dict[str, Any]] = Field(default_factory=list, description="物资列表")
    weight_usage: float = Field(..., description="载重利用率")
    volume_usage: float = Field(..., description="容积利用率")


class EquipmentRecommendationResponse(BaseModel):
    """装备推荐响应"""
    id: UUID = Field(..., description="推荐ID")
    event_id: UUID = Field(..., description="关联事件ID")
    status: str = Field(..., description="状态: pending/ready/confirmed/cancelled")
    
    # 灾情分析
    disaster_analysis: Optional[Dict[str, Any]] = Field(None, description="灾情分析结果")
    requirement_analysis: Optional[Dict[str, Any]] = Field(None, description="需求分析结果")
    
    # 推荐清单
    recommended_devices: List[DeviceRecommendationSchema] = Field(
        default_factory=list, description="推荐设备列表"
    )
    recommended_supplies: List[SupplyRecommendationSchema] = Field(
        default_factory=list, description="推荐物资列表"
    )
    
    # 缺口告警
    shortage_alerts: List[ShortageAlertSchema] = Field(
        default_factory=list, description="缺口告警列表"
    )
    
    # 装载方案
    loading_plan: Optional[Dict[str, LoadingPlanItemSchema]] = Field(
        None, description="装载方案"
    )
    
    # 确认信息
    confirmed_devices: Optional[List[str]] = Field(None, description="已确认设备ID列表")
    confirmed_supplies: Optional[List[Dict[str, Any]]] = Field(None, description="已确认物资列表")
    confirmation_note: Optional[str] = Field(None, description="确认备注")
    
    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    ready_at: Optional[datetime] = Field(None, description="就绪时间")
    confirmed_at: Optional[datetime] = Field(None, description="确认时间")
    
    class Config:
        from_attributes = True


class EquipmentRecommendationConfirm(BaseModel):
    """确认装备推荐请求"""
    device_ids: List[str] = Field(..., description="确认的设备ID列表")
    supplies: List[Dict[str, Any]] = Field(
        ..., 
        description="确认的物资列表 [{supply_id, quantity}]"
    )
    note: Optional[str] = Field(None, description="确认备注")


class EquipmentRecommendationBrief(BaseModel):
    """装备推荐简要信息（用于WebSocket通知）"""
    recommendation_id: UUID = Field(..., description="推荐ID")
    event_id: UUID = Field(..., description="关联事件ID")
    event_code: str = Field(..., description="事件编码")
    event_title: str = Field(..., description="事件标题")
    
    # 统计信息
    total_devices: int = Field(..., description="推荐设备数量")
    total_supplies: int = Field(..., description="推荐物资数量")
    critical_alerts: int = Field(default=0, description="严重缺口数量")
    warning_alerts: int = Field(default=0, description="警告缺口数量")
    
    # 关键设备（前3个）
    key_devices: List[str] = Field(default_factory=list, description="关键设备名称")
    
    # 时间
    ready_at: datetime = Field(..., description="就绪时间")
