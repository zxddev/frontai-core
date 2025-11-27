"""
预警决策节点

根据影响分析结果决定预警级别。
"""
import logging
from typing import Any, Dict, List
from datetime import datetime

from ..state import EarlyWarningState, WarningDecision, AffectedObject, WarningLevel

logger = logging.getLogger(__name__)

# 预警级别阈值（米）
WARNING_THRESHOLDS = {
    WarningLevel.RED.value: 1000,      # <1km
    WarningLevel.ORANGE.value: 3000,   # 1-3km
    WarningLevel.YELLOW.value: 5000,   # 3-5km
    WarningLevel.BLUE.value: float('inf'),  # >5km
}


def decide_warning(state: EarlyWarningState) -> Dict[str, Any]:
    """
    决定是否发出预警及预警级别
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段（warning_decisions）
    """
    logger.info(f"[decide] Making warning decisions for request {state['request_id']}")
    
    affected_vehicles = state.get("affected_vehicles", [])
    affected_teams = state.get("affected_teams", [])
    disaster = state.get("disaster_situation")
    
    if not disaster:
        return {
            "current_phase": "decide",
            "warning_decisions": [],
        }
    
    all_affected = affected_vehicles + affected_teams
    
    if not all_affected:
        logger.info("[decide] No affected objects, no warnings needed")
        return {
            "current_phase": "decide",
            "warning_decisions": [],
        }
    
    warning_decisions: List[WarningDecision] = []
    
    for affected in all_affected:
        decision = _make_decision(affected, disaster)
        if decision["should_warn"]:
            warning_decisions.append(decision)
    
    logger.info(f"[decide] Generated {len(warning_decisions)} warning decisions")
    
    # 更新trace
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["decide"]
    trace["decide_time"] = datetime.utcnow().isoformat()
    trace["warnings_decided"] = len(warning_decisions)
    
    return {
        "warning_decisions": warning_decisions,
        "current_phase": "decide",
        "trace": trace,
    }


def _make_decision(affected: AffectedObject, disaster: Dict) -> WarningDecision:
    """为单个受影响对象做出预警决策"""
    
    distance_m = affected.get("distance_to_disaster_m", 0)
    route_affected = affected.get("route_affected", False)
    
    # 确定预警级别
    warning_level = _determine_warning_level(distance_m)
    
    # 如果路径受影响但距离较远，提升预警级别
    if route_affected and warning_level == WarningLevel.BLUE.value:
        warning_level = WarningLevel.YELLOW.value
    
    # 生成预警标题和消息
    disaster_type = disaster.get("disaster_type", "灾害")
    disaster_name = disaster.get("disaster_name") or _get_disaster_type_name(disaster_type)
    obj_type = affected.get("object_type")
    obj_name = affected.get("object_name", "未知")
    estimated_minutes = affected.get("estimated_contact_minutes")
    
    # 预警标题
    level_name = _get_level_name(warning_level)
    if obj_type == "vehicle":
        title = f"【路径预警-{level_name}】车辆{obj_name}"
    else:
        title = f"【路径预警-{level_name}】救援队伍{obj_name}"
    
    # 预警消息
    message_parts = []
    
    if route_affected:
        message_parts.append(f"当前路径将穿过{disaster_name}预警区域")
    else:
        message_parts.append(f"当前位置距{disaster_name}区域{distance_m:.0f}米")
    
    if estimated_minutes:
        message_parts.append(f"预计{estimated_minutes}分钟后可能接触危险区域")
    
    message_parts.append("请及时处置")
    
    message = "，".join(message_parts)
    
    return WarningDecision(
        should_warn=True,
        warning_level=warning_level,
        affected_object=affected,
        warning_title=title,
        warning_message=message,
    )


def _determine_warning_level(distance_m: float) -> str:
    """根据距离确定预警级别"""
    if distance_m < WARNING_THRESHOLDS[WarningLevel.RED.value]:
        return WarningLevel.RED.value
    elif distance_m < WARNING_THRESHOLDS[WarningLevel.ORANGE.value]:
        return WarningLevel.ORANGE.value
    elif distance_m < WARNING_THRESHOLDS[WarningLevel.YELLOW.value]:
        return WarningLevel.YELLOW.value
    else:
        return WarningLevel.BLUE.value


def _get_level_name(level: str) -> str:
    """获取预警级别中文名"""
    names = {
        WarningLevel.RED.value: "红色",
        WarningLevel.ORANGE.value: "橙色",
        WarningLevel.YELLOW.value: "黄色",
        WarningLevel.BLUE.value: "蓝色",
    }
    return names.get(level, "黄色")


def _get_disaster_type_name(disaster_type: str) -> str:
    """获取灾害类型中文名"""
    names = {
        "fire": "火灾",
        "flood": "洪水",
        "chemical": "化学品泄漏",
        "landslide": "山体滑坡",
        "earthquake": "地震",
    }
    return names.get(disaster_type, "灾害")
