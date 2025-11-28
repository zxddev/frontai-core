"""
缺口分析节点

对比推荐清单与库存，识别物资缺口并生成告警。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..state import EquipmentPreparationState, ShortageAlert

logger = logging.getLogger(__name__)


async def analyze_shortage(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    缺口分析节点
    
    1. 检查推荐设备是否可用
    2. 检查推荐模块是否足够
    3. 检查物资库存是否满足需求
    4. 生成缺口告警和调配建议
    """
    logger.info("执行缺口分析节点", extra={"event_id": state.get("event_id")})
    
    recommended_devices = state.get("recommended_devices", [])
    recommended_supplies = state.get("recommended_supplies", [])
    warehouse_inventory = state.get("warehouse_inventory", {})
    requirement_spec = state.get("requirement_spec", {})
    
    alerts: List[ShortageAlert] = []
    
    # 1. 检查设备缺口
    device_alerts = _check_device_shortage(
        recommended_devices=recommended_devices,
        available_devices=warehouse_inventory.get("devices", []),
        requirement_spec=requirement_spec,
    )
    alerts.extend(device_alerts)
    
    # 2. 检查模块缺口
    module_alerts = _check_module_shortage(
        recommended_devices=recommended_devices,
        available_modules=warehouse_inventory.get("modules", []),
    )
    alerts.extend(module_alerts)
    
    # 3. 检查物资缺口
    supply_alerts = _check_supply_shortage(
        recommended_supplies=recommended_supplies,
        available_supplies=warehouse_inventory.get("supplies", []),
    )
    alerts.extend(supply_alerts)
    
    # 按严重程度排序
    severity_order = {"critical": 0, "warning": 1}
    alerts.sort(key=lambda x: severity_order.get(x.get("severity", "warning"), 1))
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["analyze_shortage"]
    
    logger.info(
        "缺口分析完成",
        extra={
            "total_alerts": len(alerts),
            "critical_alerts": sum(1 for a in alerts if a.get("severity") == "critical"),
        }
    )
    
    return {
        "shortage_alerts": alerts,
        "current_phase": "shortage_analysis",
        "trace": trace,
    }


def _check_device_shortage(
    recommended_devices: List[Dict[str, Any]],
    available_devices: List[Dict[str, Any]],
    requirement_spec: Dict[str, Any],
) -> List[ShortageAlert]:
    """检查设备缺口"""
    alerts: List[ShortageAlert] = []
    
    required_device_types = requirement_spec.get("required_device_types", [])
    available_ids = {d["id"] for d in available_devices}
    available_by_type: Dict[str, int] = {}
    
    for d in available_devices:
        dtype = d.get("device_type", "unknown")
        available_by_type[dtype] = available_by_type.get(dtype, 0) + 1
    
    # 检查推荐的设备是否都可用
    for rec in recommended_devices:
        if rec["device_id"] not in available_ids:
            alerts.append({
                "item_type": "device",
                "item_name": rec["device_name"],
                "required": 1,
                "available": 0,
                "shortage": 1,
                "severity": "critical" if rec.get("priority") in ["critical", "high"] else "warning",
                "suggestion": f"推荐的{rec['device_name']}不可用，请检查设备状态或调配其他设备",
            })
    
    # 检查各类型设备是否足够
    recommended_by_type: Dict[str, int] = {}
    for rec in recommended_devices:
        dtype = rec.get("device_type", "unknown")
        recommended_by_type[dtype] = recommended_by_type.get(dtype, 0) + 1
    
    for dtype in required_device_types:
        required = recommended_by_type.get(dtype, 1)  # 至少需要1台
        available = available_by_type.get(dtype, 0)
        
        if available < required:
            shortage = required - available
            alerts.append({
                "item_type": "device",
                "item_name": f"{dtype}类型设备",
                "required": required,
                "available": available,
                "shortage": shortage,
                "severity": "critical" if dtype in ["drone"] else "warning",
                "suggestion": f"需要{required}台{dtype}设备，仓库仅有{available}台，建议从其他站点调配",
            })
    
    return alerts


def _check_module_shortage(
    recommended_devices: List[Dict[str, Any]],
    available_modules: List[Dict[str, Any]],
) -> List[ShortageAlert]:
    """检查模块缺口"""
    alerts: List[ShortageAlert] = []
    
    # 统计所需模块
    required_modules: Dict[str, int] = {}
    for device in recommended_devices:
        for module in device.get("modules", []):
            module_id = module.get("module_id", "")
            module_name = module.get("module_name", "")
            key = f"{module_id}:{module_name}"
            required_modules[key] = required_modules.get(key, 0) + 1
    
    # 统计可用模块
    available_module_counts: Dict[str, int] = {}
    module_names: Dict[str, str] = {}
    for m in available_modules:
        mid = m.get("id", "")
        mname = m.get("name", "")
        key = f"{mid}:{mname}"
        available_module_counts[key] = available_module_counts.get(key, 0) + 1
        module_names[key] = mname
    
    # 检查缺口
    for key, required in required_modules.items():
        available = available_module_counts.get(key, 0)
        if available < required:
            shortage = required - available
            _, module_name = key.split(":", 1)
            alerts.append({
                "item_type": "module",
                "item_name": module_name,
                "required": required,
                "available": available,
                "shortage": shortage,
                "severity": "warning",
                "suggestion": f"{module_name}不足，建议从备用库调配或使用替代模块",
            })
    
    return alerts


def _check_supply_shortage(
    recommended_supplies: List[Dict[str, Any]],
    available_supplies: List[Dict[str, Any]],
) -> List[ShortageAlert]:
    """
    检查物资缺口
    
    使用 supply_code 作为匹配键，支持从推荐清单中直接获取缺口信息。
    """
    alerts: List[ShortageAlert] = []
    
    # 建立库存映射（使用 code 作为 key）
    stock_map: Dict[str, Dict[str, Any]] = {}
    for s in available_supplies:
        code = s.get("code", s.get("id", ""))
        stock_map[code] = s
    
    # 检查每个推荐物资
    for rec in recommended_supplies:
        # 优先使用 supply_code，兼容 supply_id
        supply_code = rec.get("supply_code", rec.get("supply_id", ""))
        required = rec.get("required_quantity", rec.get("quantity", 0))
        priority = rec.get("priority", "medium")
        
        # 如果推荐清单已经标记了缺口（来自 _match_supplies）
        if rec.get("is_shortage"):
            stock_available = rec.get("stock_available", 0)
            shortage = required - stock_available
            alerts.append({
                "item_type": "supply",
                "item_name": rec.get("supply_name", "unknown"),
                "supply_code": supply_code,
                "required": required,
                "available": stock_available,
                "shortage": shortage,
                "severity": "critical" if priority in ["critical", "high"] else "warning",
                "suggestion": f"库存{stock_available}，需求{required}，缺口{shortage}，建议从临近站点调配",
            })
            continue
        
        # 从库存映射中查找
        stock_info = stock_map.get(supply_code)
        if not stock_info:
            alerts.append({
                "item_type": "supply",
                "item_name": rec.get("supply_name", "unknown"),
                "supply_code": supply_code,
                "required": required,
                "available": 0,
                "shortage": required,
                "severity": "critical" if priority == "critical" else "warning",
                "suggestion": f"{rec.get('supply_name')}无库存，请紧急采购或调配",
            })
            continue
        
        available = stock_info.get("stock_quantity", 0)
        if available < required:
            shortage = required - available
            
            alerts.append({
                "item_type": "supply",
                "item_name": rec.get("supply_name", "unknown"),
                "supply_code": supply_code,
                "required": required,
                "available": available,
                "shortage": shortage,
                "severity": "critical" if priority in ["critical", "high"] else "warning",
                "suggestion": f"库存{available}，需求{required}，缺口{shortage}，建议从临近站点调配",
            })
    
    return alerts
