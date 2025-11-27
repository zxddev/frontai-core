"""
消息生成节点

生成预警记录并准备存储。
"""
import logging
from typing import Any, Dict, List
from uuid import uuid4
from datetime import datetime

from ..state import EarlyWarningState, WarningRecord, WarningDecision

logger = logging.getLogger(__name__)


def generate_message(state: EarlyWarningState) -> Dict[str, Any]:
    """
    生成预警记录
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段（warning_records）
    """
    logger.info(f"[generate] Generating warning records for request {state['request_id']}")
    
    warning_decisions = state.get("warning_decisions", [])
    disaster = state.get("disaster_situation")
    
    if not warning_decisions:
        logger.info("[generate] No warning decisions to process")
        return {
            "current_phase": "generate",
            "warning_records": [],
        }
    
    warning_records: List[WarningRecord] = []
    
    for decision in warning_decisions:
        record = _create_warning_record(decision, disaster, state)
        warning_records.append(record)
    
    logger.info(f"[generate] Generated {len(warning_records)} warning records")
    
    # 更新trace
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate"]
    trace["generate_time"] = datetime.utcnow().isoformat()
    trace["records_generated"] = len(warning_records)
    
    return {
        "warning_records": warning_records,
        "current_phase": "generate",
        "trace": trace,
    }


def _create_warning_record(
    decision: WarningDecision,
    disaster: Dict,
    state: EarlyWarningState,
) -> WarningRecord:
    """创建单条预警记录"""
    
    affected = decision.get("affected_object", {})
    
    return WarningRecord(
        id=str(uuid4()),
        disaster_id=disaster.get("id", "") if disaster else "",
        scenario_id=state.get("scenario_id"),
        affected_type=affected.get("object_type", ""),
        affected_id=affected.get("object_id", ""),
        affected_name=affected.get("object_name", ""),
        warning_level=decision.get("warning_level", "yellow"),
        distance_m=affected.get("distance_to_disaster_m", 0),
        estimated_contact_minutes=affected.get("estimated_contact_minutes"),
        route_affected=affected.get("route_affected", False),
        warning_title=decision.get("warning_title", ""),
        warning_message=decision.get("warning_message", ""),
        status="pending",
        notify_target_type=affected.get("notify_target_type", ""),
        notify_target_id=affected.get("notify_target_id"),
        created_at=datetime.utcnow().isoformat(),
    )
