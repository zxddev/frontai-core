"""装载方案生成节点

根据推荐清单和车辆容量，生成装载方案。

设计约定：
- 车辆来源统一使用 operational_v2.vehicles_v2 中的真实车辆记录
- loading_plan 的 key 为车辆的 UUID 字符串（vehicles_v2.id）
- 设备优先分配到其专属车辆（vehicle_devices 关联表）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from sqlalchemy import text

from src.core.database import AsyncSessionLocal
from src.domains.resources.vehicles.repository import VehicleRepository

from ..state import EquipmentPreparationState, LoadingPlanItem

logger = logging.getLogger(__name__)


async def _load_vehicle_device_bindings(session) -> tuple[Dict[str, str], Dict[str, Set[str]]]:
    """
    加载设备-车辆绑定关系
    
    Returns:
        tuple:
            - Dict[device_id, vehicle_id]: 设备到专属车辆的映射
            - Dict[vehicle_id, Set[device_id]]: 车辆到其绑定设备的映射
    """
    result = await session.execute(
        text("""
            SELECT device_id::text, vehicle_id::text
            FROM operational_v2.vehicle_devices
            WHERE is_default = true
        """)
    )
    device_to_vehicle: Dict[str, str] = {}
    vehicle_to_devices: Dict[str, Set[str]] = {}
    
    for row in result.fetchall():
        device_to_vehicle[row.device_id] = row.vehicle_id
        if row.vehicle_id not in vehicle_to_devices:
            vehicle_to_devices[row.vehicle_id] = set()
        vehicle_to_devices[row.vehicle_id].add(row.device_id)
    
    return device_to_vehicle, vehicle_to_devices


async def generate_loading_plan(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    装载方案生成节点
    
    分配策略：
    1. 优先将设备分配到其专属车辆（vehicle_devices 关联表）
    2. 非专属设备按优先级使用贪心算法分配
    3. 考虑重量和体积约束
    4. 计算各车辆利用率
    """
    logger.info("执行装载方案生成节点", extra={"event_id": state.get("event_id")})
    
    recommended_devices = state.get("recommended_devices", [])
    recommended_supplies = state.get("recommended_supplies", [])
    warehouse_inventory = state.get("warehouse_inventory", {})
    
    # 获取设备详情（含重量体积）
    device_details = {d["id"]: d for d in warehouse_inventory.get("devices", [])}
    supply_details = {s["id"]: s for s in warehouse_inventory.get("supplies", [])}

    # 初始化车辆装载计划：优先使用数据库中的真实车辆
    loading_plan: Dict[str, LoadingPlanItem] = {}
    # 设备-车辆绑定关系
    device_to_vehicle: Dict[str, str] = {}  # {device_id -> vehicle_id}
    vehicle_to_devices: Dict[str, Set[str]] = {}  # {vehicle_id -> Set[device_id]}

    async with AsyncSessionLocal() as session:
        try:
            vehicle_repo = VehicleRepository(session)
            # 仅使用可用状态的车辆
            vehicles = await vehicle_repo.list_available(
                vehicle_type=None,
                min_weight_capacity=None,
                required_terrain=None,
            )
            # 加载设备-车辆绑定关系
            device_to_vehicle, vehicle_to_devices = await _load_vehicle_device_bindings(session)
            logger.info(f"加载了 {len(device_to_vehicle)} 条设备-车辆绑定关系")
        except Exception as e:
            logger.exception("查询车辆列表失败，将不会生成装载方案", extra={"event_id": state.get("event_id")})
            vehicles = []

        for v in vehicles:
            vid = str(v.id)
            max_weight = float(v.max_weight_kg or 0)
            max_volume = float(v.max_volume_m3 or 0)

            # 没有配置载重/容积的车辆跳过
            if max_weight <= 0 or max_volume <= 0:
                logger.warning(
                    "车辆缺少容量配置，跳过装载: id=%s, name=%s", vid, v.name
                )
                continue

            loading_plan[vid] = {
                "vehicle_id": vid,
                "vehicle_name": v.name,
                "devices": [],
                "supplies": [],
                "weight_usage": 0.0,
                "volume_usage": 0.0,
                "_remaining_weight": max_weight,
                "_remaining_volume": max_volume,
                "_max_weight": max_weight,
                "_max_volume": max_volume,
            }

    # 如果没有可用车辆（或查询失败），直接返回空装载方案
    if not loading_plan:
        logger.warning("未找到可用于装载的车辆，返回空装载方案", extra={"event_id": state.get("event_id")})
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_loading_plan"]
        return {
            "loading_plan": {},
            "current_phase": "loading_plan",
            "trace": trace,
        }
    
    # 按优先级排序设备
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_devices = sorted(
        recommended_devices,
        key=lambda x: priority_order.get(x.get("priority", "low"), 3)
    )
    
    # 分配设备到车辆
    # 策略：
    # 1. 有专属车辆的设备 → 只能分配到专属车辆
    # 2. 未绑定的设备 → 只能分配到没有绑定该设备的车辆（即不能占用其他车的专属设备位）
    for device_rec in sorted_devices:
        device_id = device_rec.get("device_id")
        device_info = device_details.get(device_id, {})
        
        weight = device_info.get("weight_kg", 5)
        volume = device_info.get("volume_m3", 0.1)
        
        assigned = False
        bound_vehicle_id = device_to_vehicle.get(device_id)
        
        if bound_vehicle_id:
            # 情况1：设备有专属车辆，只能分配到该车辆
            if bound_vehicle_id in loading_plan:
                plan = loading_plan[bound_vehicle_id]
                if plan["_remaining_weight"] >= weight and plan["_remaining_volume"] >= volume:
                    plan["devices"].append(device_id)
                    plan["_remaining_weight"] -= weight
                    plan["_remaining_volume"] -= volume
                    assigned = True
                    logger.debug(f"设备 {device_id} 分配到专属车辆 {plan['vehicle_name']}")
                else:
                    logger.warning(
                        f"设备 {device_id} 的专属车辆 {plan['vehicle_name']} 容量不足，无法分配"
                    )
            else:
                logger.warning(f"设备 {device_id} 的专属车辆 {bound_vehicle_id} 不在可用车辆列表中")
        else:
            # 情况2：设备未绑定，可以分配到任意有空间的车辆
            for vid, plan in loading_plan.items():
                if plan["_remaining_weight"] >= weight and plan["_remaining_volume"] >= volume:
                    plan["devices"].append(device_id)
                    plan["_remaining_weight"] -= weight
                    plan["_remaining_volume"] -= volume
                    assigned = True
                    logger.debug(f"设备 {device_id} 分配到 {plan['vehicle_name']}（未绑定设备）")
                    break
        
        if not assigned:
            logger.warning(f"设备 {device_id} 无法分配到任何车辆")
    
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
