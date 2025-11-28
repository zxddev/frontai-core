"""
装载方案生成节点

根据推荐清单和车辆容量，生成装载方案。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..state import EquipmentPreparationState, LoadingPlanItem

logger = logging.getLogger(__name__)

# 默认车辆配置（实际应从数据库查询）
DEFAULT_VEHICLES = [
    {
        "id": "vehicle-001",
        "name": "消防指挥车-01",
        "max_weight_kg": 500,
        "max_volume_m3": 2.0,
        "vehicle_type": "command",
    },
    {
        "id": "vehicle-002", 
        "name": "装备运输车-01",
        "max_weight_kg": 2000,
        "max_volume_m3": 8.0,
        "vehicle_type": "transport",
    },
    {
        "id": "vehicle-003",
        "name": "救援作业车-01",
        "max_weight_kg": 1500,
        "max_volume_m3": 6.0,
        "vehicle_type": "rescue",
    },
]


async def generate_loading_plan(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    装载方案生成节点
    
    使用贪心算法将设备和物资分配到车辆：
    1. 优先分配高优先级设备
    2. 考虑重量和体积约束
    3. 计算各车辆利用率
    """
    logger.info("执行装载方案生成节点", extra={"event_id": state.get("event_id")})
    
    recommended_devices = state.get("recommended_devices", [])
    recommended_supplies = state.get("recommended_supplies", [])
    warehouse_inventory = state.get("warehouse_inventory", {})
    
    # 获取设备详情（含重量体积）
    device_details = {d["id"]: d for d in warehouse_inventory.get("devices", [])}
    supply_details = {s["id"]: s for s in warehouse_inventory.get("supplies", [])}
    
    # 初始化车辆装载计划
    vehicles = DEFAULT_VEHICLES.copy()
    loading_plan: Dict[str, LoadingPlanItem] = {}
    
    for v in vehicles:
        loading_plan[v["id"]] = {
            "vehicle_id": v["id"],
            "vehicle_name": v["name"],
            "devices": [],
            "supplies": [],
            "weight_usage": 0.0,
            "volume_usage": 0.0,
            "_remaining_weight": v["max_weight_kg"],
            "_remaining_volume": v["max_volume_m3"],
            "_max_weight": v["max_weight_kg"],
            "_max_volume": v["max_volume_m3"],
        }
    
    # 按优先级排序设备
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_devices = sorted(
        recommended_devices,
        key=lambda x: priority_order.get(x.get("priority", "low"), 3)
    )
    
    # 分配设备到车辆
    for device_rec in sorted_devices:
        device_id = device_rec.get("device_id")
        device_info = device_details.get(device_id, {})
        
        weight = device_info.get("weight_kg", 5)
        volume = device_info.get("volume_m3", 0.1)
        
        # 找到合适的车辆
        assigned = False
        for vid, plan in loading_plan.items():
            if plan["_remaining_weight"] >= weight and plan["_remaining_volume"] >= volume:
                plan["devices"].append(device_id)
                plan["_remaining_weight"] -= weight
                plan["_remaining_volume"] -= volume
                assigned = True
                logger.debug(f"设备 {device_id} 分配到 {plan['vehicle_name']}")
                break
        
        if not assigned:
            logger.warning(f"设备 {device_id} 无法分配到任何车辆（容量不足）")
    
    # 分配物资到车辆
    sorted_supplies = sorted(
        recommended_supplies,
        key=lambda x: priority_order.get(x.get("priority", "low"), 3)
    )
    
    for supply_rec in sorted_supplies:
        supply_id = supply_rec.get("supply_id")
        quantity = supply_rec.get("quantity", 1)
        supply_info = supply_details.get(supply_id, {})
        
        weight_per_unit = supply_info.get("weight_kg", 0.5)
        volume_per_unit = supply_info.get("volume_m3", 0.01)
        
        total_weight = weight_per_unit * quantity
        total_volume = volume_per_unit * quantity
        
        # 尝试找到合适的车辆
        remaining_qty = quantity
        for vid, plan in loading_plan.items():
            if remaining_qty <= 0:
                break
            
            # 计算这辆车能装多少
            max_by_weight = int(plan["_remaining_weight"] / weight_per_unit) if weight_per_unit > 0 else remaining_qty
            max_by_volume = int(plan["_remaining_volume"] / volume_per_unit) if volume_per_unit > 0 else remaining_qty
            can_load = min(max_by_weight, max_by_volume, remaining_qty)
            
            if can_load > 0:
                plan["supplies"].append({
                    "supply_id": supply_id,
                    "quantity": can_load,
                })
                plan["_remaining_weight"] -= weight_per_unit * can_load
                plan["_remaining_volume"] -= volume_per_unit * can_load
                remaining_qty -= can_load
        
        if remaining_qty > 0:
            logger.warning(f"物资 {supply_id} 有 {remaining_qty} 无法分配（容量不足）")
    
    # 计算利用率并清理内部字段
    for vid, plan in loading_plan.items():
        max_weight = plan.pop("_max_weight")
        max_volume = plan.pop("_max_volume")
        remaining_weight = plan.pop("_remaining_weight")
        remaining_volume = plan.pop("_remaining_volume")
        
        plan["weight_usage"] = round(1 - remaining_weight / max_weight, 2) if max_weight > 0 else 0
        plan["volume_usage"] = round(1 - remaining_volume / max_volume, 2) if max_volume > 0 else 0
    
    # 移除空车辆
    loading_plan = {
        vid: plan for vid, plan in loading_plan.items()
        if plan["devices"] or plan["supplies"]
    }
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_loading_plan"]
    
    logger.info(
        "装载方案生成完成",
        extra={"vehicles_used": len(loading_plan)}
    )
    
    return {
        "loading_plan": loading_plan,
        "current_phase": "loading_plan",
        "trace": trace,
    }
