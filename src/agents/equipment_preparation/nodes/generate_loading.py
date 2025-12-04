"""装载方案生成节点

根据推荐清单和车辆容量，生成装载方案。

设计约定：
- 车辆来源统一使用 operational_v2.vehicles_v2 中的真实车辆记录
- loading_plan 的 key 为车辆的 UUID 字符串（vehicles_v2.id）
- 设备优先分配到其专属车辆（vehicle_devices 关联表）
- 无专属绑定时，按设备类型匹配适合的车辆类型
"""
from __future__ import annotations

# 设备类型到优先车辆类型的映射（包含所有车辆类型以确保每辆车都能分配到设备）
DEVICE_VEHICLE_TYPE_MAPPING: dict[str, list[str]] = {
    "drone": ["drone_transport", "reconnaissance", "command", "logistics", "medical", "ship_transport"],
    "dog": ["reconnaissance", "command", "logistics", "medical", "drone_transport", "ship_transport"],
    "ship": ["ship_transport", "logistics", "reconnaissance", "command", "medical", "drone_transport"],
    "robot": ["reconnaissance", "command", "logistics", "medical", "drone_transport", "ship_transport"],
}

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
    import time
    start_time = time.time()
    logger.info(f"[装载分配] ========== 开始装载方案生成 ==========")
    
    recommended_devices = state.get("recommended_devices", [])
    recommended_supplies = state.get("recommended_supplies", [])
    warehouse_inventory = state.get("warehouse_inventory", {})
    
    logger.info(f"[装载分配] 待分配设备: {len(recommended_devices)}个")
    logger.info(f"[装载分配] 待分配物资: {len(recommended_supplies)}种")
    
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
                "vehicle_type": v.vehicle_type,  # 保存车辆类型用于设备匹配
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
        logger.warning("[装载分配] 未找到可用车辆，返回空装载方案")
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_loading_plan"]
        return {
            "loading_plan": {},
            "current_phase": "loading_plan",
            "trace": trace,
        }
    
    # 打印可用车辆
    logger.info(f"[装载分配] 可用车辆: {len(loading_plan)}辆")
    for vid, plan in loading_plan.items():
        logger.info(f"[装载分配]   - {plan['vehicle_name']} ({plan.get('vehicle_type', '未知类型')})")
    
    # 每辆车推荐的设备数量上限
    MAX_DEVICES_PER_VEHICLE = 3
    logger.info(f"[装载分配] 每车设备上限: {MAX_DEVICES_PER_VEHICLE}个")
    
    # 计算设备对车辆的适配分数
    def calc_device_score(device_rec: dict, vehicle_type: str) -> float:
        """
        计算设备对车辆的适配分数
        分数越高越适配
        """
        device_type = device_rec.get("device_type", "")
        priority = device_rec.get("priority", "low")
        
        # 基础分数：根据优先级
        priority_scores = {"critical": 100, "high": 80, "medium": 60, "low": 40}
        score = priority_scores.get(priority, 40)
        
        # 适配分数：设备类型与车辆类型的匹配度
        preferred_types = DEVICE_VEHICLE_TYPE_MAPPING.get(device_type, [])
        if vehicle_type in preferred_types:
            # 排名越靠前分数越高
            rank = preferred_types.index(vehicle_type)
            score += (len(preferred_types) - rank) * 20
        
        return score
    
    # 已分配的设备ID集合
    assigned_device_ids: Set[str] = set()
    
    # 第一轮：分配专属设备到专属车辆
    for device_rec in recommended_devices:
        device_id = device_rec.get("device_id")
        bound_vehicle_id = device_to_vehicle.get(device_id)
        
        if bound_vehicle_id and bound_vehicle_id in loading_plan:
            plan = loading_plan[bound_vehicle_id]
            device_info = device_details.get(device_id, {})
            weight = device_info.get("weight_kg", 5)
            volume = device_info.get("volume_m3", 0.1)
            
            if plan["_remaining_weight"] >= weight and plan["_remaining_volume"] >= volume:
                plan["devices"].append(device_id)
                plan["_remaining_weight"] -= weight
                plan["_remaining_volume"] -= volume
                assigned_device_ids.add(device_id)
                logger.debug(f"设备 {device_id} 分配到专属车辆 {plan['vehicle_name']}")
    
    # 第二轮：为每辆车选择最适配的设备（每车最多3个）
    logger.info(f"[装载分配] 开始为每辆车分配最适配的设备...")
    for vid, plan in loading_plan.items():
        current_count = len(plan["devices"])
        if current_count >= MAX_DEVICES_PER_VEHICLE:
            continue
        
        vehicle_type = plan.get("vehicle_type", "")
        vehicle_name = plan.get("vehicle_name", vid)
        
        # 计算所有未分配设备的适配分数
        candidates: List[tuple[float, dict]] = []
        for device_rec in recommended_devices:
            device_id = device_rec.get("device_id")
            
            # 跳过已分配的设备
            if device_id in assigned_device_ids:
                continue
            
            # 跳过有专属车辆绑定（且不是当前车辆）的设备
            bound_vid = device_to_vehicle.get(device_id)
            if bound_vid and bound_vid != vid:
                continue
            
            score = calc_device_score(device_rec, vehicle_type)
            candidates.append((score, device_rec))
        
        # 按分数排序，选择最适配的设备
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        assigned_to_vehicle = []
        for score, device_rec in candidates:
            if current_count >= MAX_DEVICES_PER_VEHICLE:
                break
            
            device_id = device_rec.get("device_id")
            device_info = device_details.get(device_id, {})
            weight = device_info.get("weight_kg", 5)
            volume = device_info.get("volume_m3", 0.1)
            
            if plan["_remaining_weight"] >= weight and plan["_remaining_volume"] >= volume:
                plan["devices"].append(device_id)
                plan["_remaining_weight"] -= weight
                plan["_remaining_volume"] -= volume
                assigned_device_ids.add(device_id)
                current_count += 1
                device_name = device_info.get("name", device_id[:8])
                assigned_to_vehicle.append(f"{device_name}({device_rec.get('device_type')})")
        
        if assigned_to_vehicle:
            logger.info(f"[装载分配] {vehicle_name}: 分配{len(assigned_to_vehicle)}个设备")
    
    # 统计未分配的设备
    unassigned = [d for d in recommended_devices if d.get("device_id") not in assigned_device_ids]
    if unassigned:
        logger.info(f"[装载分配] 有{len(unassigned)}个设备未分配（容量不足或设备已分完）")
    
    # 分配物资到车辆
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
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
        plan.pop("vehicle_type", None)  # 移除内部使用的车辆类型字段
        
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
    
    # 打印最终分配结果
    total_time = int((time.time() - start_time) * 1000)
    total_devices = sum(len(p.get("devices", [])) for p in loading_plan.values())
    total_supplies = sum(len(p.get("supplies", [])) for p in loading_plan.values())
    
    logger.info(f"[装载分配] ========== 装载方案生成完成 ==========")
    logger.info(f"[装载分配] 耗时: {total_time}ms")
    logger.info(f"[装载分配] 装载车辆: {len(loading_plan)}辆")
    logger.info(f"[装载分配] 分配设备: {total_devices}个")
    logger.info(f"[装载分配] 分配物资: {total_supplies}种")
    
    # 打印每辆车的分配情况
    for vid, plan in loading_plan.items():
        vehicle_name = plan.get("vehicle_name", vid)
        device_count = len(plan.get("devices", []))
        supply_count = len(plan.get("supplies", []))
        weight_usage = plan.get("weight_usage", 0) * 100
        logger.info(f"[装载分配]   {vehicle_name}: {device_count}设备, {supply_count}物资, 载重{weight_usage:.0f}%")
    
    return {
        "loading_plan": loading_plan,
        "current_phase": "loading_plan",
        "trace": trace,
    }
