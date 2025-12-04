"""
仓库查询节点

查询仓库中可用的设备、模块和物资。
使用 SupplyInventoryService 查询真实库存数据。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.domains.supplies.inventory_service import SupplyInventoryService
from ..state import EquipmentPreparationState, WarehouseInventory

logger = logging.getLogger(__name__)


async def query_warehouse(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    仓库查询节点
    
    查询：
    1. 可用设备（status='available'）
    2. 可用模块
    3. 物资库存
    """
    import time
    start_time = time.time()
    logger.info(f"[仓库查询] ========== 开始仓库查询 ==========")
    
    requirement_spec = state.get("requirement_spec")
    if not requirement_spec:
        logger.warning("[仓库查询] 无需求规格，跳过仓库查询")
        return {"warehouse_inventory": None}
    
    required_device_types = requirement_spec.get("required_device_types", [])
    required_capabilities = requirement_spec.get("required_capabilities", [])
    required_supply_categories = requirement_spec.get("required_supply_categories", [])
    
    logger.info(f"[仓库查询] 查询设备类型: {required_device_types}")
    logger.info(f"[仓库查询] 查询能力需求: {required_capabilities}")
    logger.info(f"[仓库查询] 查询物资类别: {required_supply_categories}")
    
    # 获取灾害类型用于物资过滤
    parsed_disaster = state.get("parsed_disaster", {})
    disaster_type = parsed_disaster.get("disaster_type") if parsed_disaster else None
    logger.info(f"[仓库查询] 灾害类型过滤: {disaster_type}")
    
    async with AsyncSessionLocal() as session:
        # 查询可用设备
        logger.info(f"[仓库查询] 查询可用设备...")
        devices = await _query_available_devices(
            session, 
            device_types=required_device_types
        )
        logger.info(f"[仓库查询] 找到{len(devices)}个设备")
        
        # 查询可用模块
        logger.info(f"[仓库查询] 查询可用模块...")
        modules = await _query_available_modules(
            session,
            capabilities=required_capabilities
        )
        logger.info(f"[仓库查询] 找到{len(modules)}个模块")
        
        # 查询物资库存（使用真实库存数据）
        logger.info(f"[仓库查询] 查询物资库存...")
        supplies = await _query_supplies(
            session,
            categories=required_supply_categories,
            disaster_type=disaster_type,
        )
        logger.info(f"[仓库查询] 找到{len(supplies)}种物资")
    
    warehouse_inventory: WarehouseInventory = {
        "devices": devices,
        "modules": modules,
        "supplies": supplies,
    }
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["query_warehouse"]
    
    total_time = int((time.time() - start_time) * 1000)
    logger.info(f"[仓库查询] ========== 仓库查询完成，耗时{total_time}ms ==========")
    logger.info(
        f"[仓库查询] 汇总: {len(devices)}设备, {len(modules)}模块, {len(supplies)}物资",
        extra={
            "devices_found": len(devices),
            "modules_found": len(modules),
            "supplies_found": len(supplies),
        }
    )
    
    return {
        "warehouse_inventory": warehouse_inventory,
        "current_phase": "warehouse_query",
        "trace": trace,
    }


async def _query_available_devices(
    session: AsyncSession,
    device_types: List[str],
) -> List[Dict[str, Any]]:
    """查询可用设备"""
    try:
        # 动态导入模型避免循环依赖
        from src.domains.resources.devices.models import Device
        
        # 构建查询条件
        conditions = [Device.status == 'available']
        if device_types:
            conditions.append(Device.device_type.in_(device_types))
        
        result = await session.execute(
            select(Device).where(and_(*conditions))
        )
        devices = result.scalars().all()
        
        return [
            {
                "id": str(d.id),
                "code": d.code,
                "name": d.name,
                "device_type": d.device_type,
                "env_type": d.env_type,
                "weight_kg": float(d.weight_kg) if d.weight_kg else 0,
                "volume_m3": float(d.volume_m3) if d.volume_m3 else 0,
                "module_slots": d.module_slots or 0,
                "base_capabilities": d.base_capabilities or [],
                "applicable_disasters": d.applicable_disasters or [],
                "status": d.status,
            }
            for d in devices
        ]
    except Exception as e:
        logger.error(f"查询设备失败: {e}")
        return []


async def _query_available_modules(
    session: AsyncSession,
    capabilities: List[str],
) -> List[Dict[str, Any]]:
    """查询可用模块"""
    query = """
        SELECT id, code, name, module_type, weight_kg, slots_required,
               compatible_device_types, provides_capability,
               applicable_disasters, status
        FROM operational_v2.modules_v2
        WHERE status = 'available'
    """
    result = await session.execute(text(query))
    rows = result.fetchall()
    
    modules = []
    for row in rows:
        module = {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "module_type": row.module_type,
            "capabilities": [row.provides_capability] if row.provides_capability else [],
            "weight_kg": float(row.weight_kg) if row.weight_kg else 0,
            "slots_required": row.slots_required or 1,
            "compatible_devices": list(row.compatible_device_types) if row.compatible_device_types else [],
            "applicable_disasters": list(row.applicable_disasters) if row.applicable_disasters else [],
            "status": row.status,
        }
        modules.append(module)
    
    # 如果指定了能力过滤（大小写不敏感匹配）
    if capabilities:
        capabilities_upper = [cap.upper() for cap in capabilities]
        modules = [
            m for m in modules 
            if any(
                mc.upper() in capabilities_upper 
                for mc in m["capabilities"]
            )
        ]
    
    logger.info(f"查询到 {len(modules)} 个可用模块")
    return modules


async def _query_supplies(
    session: AsyncSession,
    categories: List[str],
    disaster_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    查询物资库存（使用真实库存数据）
    
    通过 SupplyInventoryService 查询 supply_inventory_v2 表的真实库存。
    """
    try:
        inventory_service = SupplyInventoryService(session)
        
        # 查询仓库类型存放点的可用库存
        inventory_items = await inventory_service.get_available_inventory(
            depot_types=["warehouse", "team_base"],  # 出发前从仓库和队伍基地选择
            categories=categories if categories else None,
            disaster_type=disaster_type,
            min_available=1,
        )
        
        # 按物资ID聚合（同一物资可能在多个存放点有库存）
        supply_map: Dict[str, Dict[str, Any]] = {}
        for item in inventory_items:
            supply_id = str(item.supply_id)
            if supply_id not in supply_map:
                supply_map[supply_id] = {
                    "id": supply_id,
                    "code": item.supply_code,
                    "name": item.supply_name,
                    "category": item.category,
                    "weight_kg": item.weight_kg or 0,
                    "volume_m3": item.volume_m3 or 0,
                    "unit": item.unit,
                    "is_consumable": True,  # 默认为消耗品
                    "applicable_disasters": item.applicable_disasters or [],
                    "required_for_disasters": item.required_for_disasters or [],
                    "per_person_per_day": item.per_person_per_day or 1.0,
                    # 真实库存数据
                    "stock_quantity": item.available_quantity,
                    "total_quantity": item.quantity,
                    "reserved_quantity": item.reserved_quantity,
                    # 存放点信息（取第一个）
                    "depot_id": str(item.depot_id),
                    "depot_name": item.depot_name,
                    "depot_type": item.depot_type,
                    # 告警标记
                    "is_low_stock": item.is_low_stock,
                    "is_expired": item.is_expired,
                }
            else:
                # 累加可用量（同一物资在多个存放点）
                supply_map[supply_id]["stock_quantity"] += item.available_quantity
                supply_map[supply_id]["total_quantity"] += item.quantity
        
        supplies = list(supply_map.values())
        logger.info(f"查询到{len(supplies)}种物资，来自{len(inventory_items)}条库存记录")
        return supplies
        
    except Exception as e:
        logger.error(f"查询物资库存失败: {e}")
        return []



