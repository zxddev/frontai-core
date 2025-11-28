"""
保存结果节点

将推荐结果保存到数据库。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from ..state import EquipmentPreparationState

logger = logging.getLogger(__name__)


async def save_result(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    保存结果节点
    
    将装备推荐结果保存到 equipment_recommendations_v2 表。
    """
    logger.info("执行保存结果节点", extra={"event_id": state.get("event_id")})
    
    event_id = state.get("event_id")
    if not event_id:
        logger.error("无事件ID，无法保存结果")
        errors = list(state.get("errors", []))
        errors.append("保存失败：无事件ID")
        return {"errors": errors}
    
    start_time = time.time()
    
    async with AsyncSessionLocal() as session:
        try:
            # 检查是否已存在记录
            existing = await session.execute(
                text("""
                    SELECT id FROM operational_v2.equipment_recommendations_v2 
                    WHERE event_id = :event_id
                """),
                {"event_id": event_id}
            )
            existing_row = existing.fetchone()
            
            if existing_row:
                # 更新现有记录
                await _update_recommendation(session, state, existing_row[0])
            else:
                # 插入新记录
                await _insert_recommendation(session, state)
            
            await session.commit()
            
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"保存结果完成，耗时{elapsed}ms")
            
        except Exception as e:
            await session.rollback()
            logger.exception("保存推荐结果失败")
            errors = list(state.get("errors", []))
            errors.append(f"保存失败：{str(e)}")
            return {"errors": errors}
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["save_result"]
    trace["total_time_ms"] = trace.get("total_time_ms", 0) + int((time.time() - start_time) * 1000)
    
    return {
        "current_phase": "save_result",
        "trace": trace,
    }


async def _insert_recommendation(
    session: AsyncSession,
    state: EquipmentPreparationState,
) -> None:
    """插入新推荐记录"""
    import json
    
    await session.execute(
        text("""
            INSERT INTO operational_v2.equipment_recommendations_v2 (
                event_id,
                status,
                disaster_analysis,
                requirement_analysis,
                recommended_devices,
                recommended_supplies,
                shortage_alerts,
                loading_plan,
                agent_trace,
                ready_at
            ) VALUES (
                :event_id,
                'ready',
                :disaster_analysis,
                :requirement_analysis,
                :recommended_devices,
                :recommended_supplies,
                :shortage_alerts,
                :loading_plan,
                :agent_trace,
                NOW()
            )
        """),
        {
            "event_id": state.get("event_id"),
            "disaster_analysis": json.dumps(state.get("parsed_disaster") or {}, ensure_ascii=False),
            "requirement_analysis": json.dumps(state.get("requirement_spec") or {}, ensure_ascii=False),
            "recommended_devices": json.dumps(state.get("recommended_devices", []), ensure_ascii=False),
            "recommended_supplies": json.dumps(state.get("recommended_supplies", []), ensure_ascii=False),
            "shortage_alerts": json.dumps(state.get("shortage_alerts", []), ensure_ascii=False),
            "loading_plan": json.dumps(state.get("loading_plan") or {}, ensure_ascii=False),
            "agent_trace": json.dumps(state.get("trace", {}), ensure_ascii=False),
        }
    )


async def _update_recommendation(
    session: AsyncSession,
    state: EquipmentPreparationState,
    rec_id: UUID,
) -> None:
    """更新现有推荐记录"""
    import json
    
    await session.execute(
        text("""
            UPDATE operational_v2.equipment_recommendations_v2 SET
                status = 'ready',
                disaster_analysis = :disaster_analysis,
                requirement_analysis = :requirement_analysis,
                recommended_devices = :recommended_devices,
                recommended_supplies = :recommended_supplies,
                shortage_alerts = :shortage_alerts,
                loading_plan = :loading_plan,
                agent_trace = :agent_trace,
                ready_at = NOW(),
                updated_at = NOW()
            WHERE id = :rec_id
        """),
        {
            "rec_id": str(rec_id),
            "disaster_analysis": json.dumps(state.get("parsed_disaster") or {}, ensure_ascii=False),
            "requirement_analysis": json.dumps(state.get("requirement_spec") or {}, ensure_ascii=False),
            "recommended_devices": json.dumps(state.get("recommended_devices", []), ensure_ascii=False),
            "recommended_supplies": json.dumps(state.get("recommended_supplies", []), ensure_ascii=False),
            "shortage_alerts": json.dumps(state.get("shortage_alerts", []), ensure_ascii=False),
            "loading_plan": json.dumps(state.get("loading_plan") or {}, ensure_ascii=False),
            "agent_trace": json.dumps(state.get("trace", {}), ensure_ascii=False),
        }
    )
