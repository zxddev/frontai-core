"""
数据接入节点

接收第三方灾情数据，存储灾害态势。
"""
import logging
from typing import Any, Dict
from uuid import uuid4
from datetime import datetime

from ..state import EarlyWarningState, DisasterSituation, Point, Polygon

logger = logging.getLogger(__name__)


def ingest_disaster(state: EarlyWarningState) -> Dict[str, Any]:
    """
    接收并处理灾害数据
    
    Args:
        state: 当前状态（包含disaster_input）
        
    Returns:
        更新的状态字段
    """
    logger.info(f"[ingest] Processing disaster data for request {state['request_id']}")
    
    disaster_input = state.get("disaster_input")
    if not disaster_input:
        logger.warning("[ingest] No disaster input provided")
        return {
            "current_phase": "ingest",
            "errors": state.get("errors", []) + ["No disaster input provided"],
        }
    
    try:
        # 解析边界数据
        boundary_data = disaster_input.get("boundary", {})
        if isinstance(boundary_data, dict):
            boundary = Polygon(
                type=boundary_data.get("type", "Polygon"),
                coordinates=boundary_data.get("coordinates", []),
            )
        else:
            boundary = Polygon(type="Polygon", coordinates=[])
        
        # 解析中心点
        center_data = disaster_input.get("center_point")
        if center_data:
            center_point = Point(
                lon=center_data.get("lon", 0),
                lat=center_data.get("lat", 0),
            )
        else:
            # 从边界计算中心点
            center_point = _calculate_center(boundary)
        
        # 构建灾害态势对象
        disaster_situation = DisasterSituation(
            id=disaster_input.get("id", str(uuid4())),
            scenario_id=state.get("scenario_id") or disaster_input.get("scenario_id"),
            disaster_type=disaster_input.get("disaster_type", "unknown"),
            disaster_name=disaster_input.get("disaster_name"),
            boundary=boundary,
            center_point=center_point,
            buffer_distance_m=disaster_input.get("buffer_distance_m", 3000),
            spread_direction=disaster_input.get("spread_direction"),
            spread_speed_mps=disaster_input.get("spread_speed_mps"),
            severity_level=disaster_input.get("severity_level", 3),
            status=disaster_input.get("status", "active"),
            source=disaster_input.get("source"),
        )
        
        logger.info(
            f"[ingest] Disaster situation created: type={disaster_situation['disaster_type']}, "
            f"buffer={disaster_situation['buffer_distance_m']}m"
        )
        
        # 更新trace
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["ingest"]
        trace["ingest_time"] = datetime.utcnow().isoformat()
        
        return {
            "disaster_situation": disaster_situation,
            "current_phase": "ingest",
            "trace": trace,
        }
        
    except Exception as e:
        logger.error(f"[ingest] Error processing disaster data: {e}")
        return {
            "current_phase": "ingest",
            "errors": state.get("errors", []) + [f"Ingest error: {str(e)}"],
        }


def _calculate_center(boundary: Polygon) -> Point:
    """从多边形计算中心点"""
    coords = boundary.get("coordinates", [])
    if not coords or not coords[0]:
        return Point(lon=0, lat=0)
    
    ring = coords[0]
    if not ring:
        return Point(lon=0, lat=0)
    
    total_lon = sum(p[0] for p in ring)
    total_lat = sum(p[1] for p in ring)
    n = len(ring)
    
    return Point(
        lon=total_lon / n if n > 0 else 0,
        lat=total_lat / n if n > 0 else 0,
    )
