"""
战略层节点: 运力瓶颈检查

检查投送能力是否满足模块部署需求。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from sqlalchemy import text

from ..state import EmergencyAIState, TransportPlan

logger = logging.getLogger(__name__)


async def check_transport(state: EmergencyAIState) -> Dict[str, Any]:
    """
    运力检查节点：检查投送能力是否满足需求
    
    1. 计算推荐模块的总人员/装备运输需求
    2. 从PostgreSQL查询运力参数
    3. 评估运力缺口并生成警告
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 transport_plans, transport_warnings
    """
    event_id = state["event_id"]
    recommended_modules = state.get("recommended_modules", [])
    
    logger.info(
        "【运力检查】开始执行",
        extra={
            "event_id": event_id,
            "modules_count": len(recommended_modules),
        }
    )
    start_time = time.time()
    
    if not recommended_modules:
        logger.warning(
            "【运力检查】无推荐模块，跳过运力检查",
            extra={"event_id": event_id}
        )
        trace = dict(state.get("trace", {}))
        trace["phases_executed"] = trace.get("phases_executed", []) + ["check_transport"]
        trace["transport_check_skipped"] = True
        return {
            "transport_plans": [],
            "transport_warnings": [],
            "trace": trace,
        }
    
    # 计算总人员需求
    total_personnel = sum(m.get("personnel", 0) for m in recommended_modules)
    total_vehicles = sum(m.get("vehicles", 0) for m in recommended_modules)
    
    logger.info(
        "【运力检查】计算运输需求",
        extra={
            "total_personnel": total_personnel,
            "total_vehicles": total_vehicles,
        }
    )
    
    # 从PostgreSQL查询运力参数
    from src.core.database import AsyncSessionLocal
    
    query = text("""
        SELECT transport_type, name, capacity_per_unit, capacity_unit, 
               speed_kmh, max_distance_km, constraints
        FROM config.transport_capacity
        WHERE is_active = TRUE
        ORDER BY capacity_per_unit DESC
    """)
    
    logger.info("【PostgreSQL】查询运力参数", extra={"query": str(query)})
    
    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(query)
        transport_rows = result.fetchall()
    
    logger.info(
        "【PostgreSQL】查询结果",
        extra={"count": len(transport_rows)}
    )
    
    if not transport_rows:
        raise ValueError(f"【运力检查】PostgreSQL未找到运力配置，event_id={event_id}")
    
    # 评估运力
    transport_plans: List[TransportPlan] = []
    transport_warnings: List[str] = []
    
    # 获取灾情信息判断约束条件
    parsed_disaster = state.get("parsed_disaster", {})
    has_road_damage = parsed_disaster.get("has_road_damage", False) if parsed_disaster else False
    
    remaining_personnel = total_personnel
    
    for row in transport_rows:
        transport_type = row.transport_type
        capacity = row.capacity_per_unit
        constraints = row.constraints or {}
        
        # 检查约束条件
        if transport_type in ("road_truck", "road_bus") and has_road_damage:
            logger.info(
                "【运力检查】道路受损，跳过公路运输",
                extra={"transport_type": transport_type}
            )
            transport_warnings.append(f"道路受损，{row.name}运输受限")
            continue
        
        # 计算该运输方式能承担的运力
        if remaining_personnel > 0:
            units_needed = (remaining_personnel + capacity - 1) // capacity
            can_transport = min(remaining_personnel, units_needed * capacity)
            gap = max(0, remaining_personnel - can_transport)
            
            # 估算到达时间（假设平均距离100km）
            avg_distance = 100
            eta_hours = avg_distance / row.speed_kmh if row.speed_kmh > 0 else 0
            
            transport_plans.append(TransportPlan(
                transport_type=transport_type,
                capacity=units_needed * capacity,
                required=remaining_personnel,
                gap=gap,
                eta_hours=round(eta_hours, 2),
            ))
            
            remaining_personnel = gap
    
    # 检查是否有运力缺口
    if remaining_personnel > 0:
        warning = f"运力缺口：{remaining_personnel}人无法投送，需协调更多运输资源"
        transport_warnings.append(warning)
        logger.warning(
            "【运力检查】运力不足",
            extra={"gap": remaining_personnel}
        )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["check_transport"]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【运力检查】执行完成",
        extra={
            "event_id": event_id,
            "transport_plans_count": len(transport_plans),
            "warnings_count": len(transport_warnings),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "transport_plans": transport_plans,
        "transport_warnings": transport_warnings,
        "trace": trace,
        "current_phase": "strategic_transport",
    }
