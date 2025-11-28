"""
装备推荐 Repository
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EquipmentRecommendationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_event_id(self, event_id: UUID) -> Optional[Dict[str, Any]]:
        """根据事件ID获取推荐"""
        result = await self.db.execute(
            text("""
                SELECT 
                    id, event_id, status,
                    disaster_analysis, requirement_analysis,
                    recommended_devices, recommended_supplies,
                    shortage_alerts, loading_plan,
                    confirmed_devices, confirmed_supplies, confirmation_note,
                    agent_trace,
                    created_at, ready_at, confirmed_at, confirmed_by, updated_at
                FROM operational_v2.equipment_recommendations_v2
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        if not row:
            return None
        
        return self._row_to_dict(row)
    
    async def get_by_id(self, rec_id: UUID) -> Optional[Dict[str, Any]]:
        """根据推荐ID获取"""
        result = await self.db.execute(
            text("""
                SELECT 
                    id, event_id, status,
                    disaster_analysis, requirement_analysis,
                    recommended_devices, recommended_supplies,
                    shortage_alerts, loading_plan,
                    confirmed_devices, confirmed_supplies, confirmation_note,
                    agent_trace,
                    created_at, ready_at, confirmed_at, confirmed_by, updated_at
                FROM operational_v2.equipment_recommendations_v2
                WHERE id = :rec_id
            """),
            {"rec_id": str(rec_id)}
        )
        row = result.fetchone()
        if not row:
            return None
        
        return self._row_to_dict(row)
    
    async def confirm(
        self,
        rec_id: UUID,
        device_ids: List[str],
        supplies: List[Dict[str, Any]],
        note: Optional[str],
        confirmed_by: Optional[UUID],
    ) -> Dict[str, Any]:
        """确认推荐"""
        await self.db.execute(
            text("""
                UPDATE operational_v2.equipment_recommendations_v2 SET
                    status = 'confirmed',
                    confirmed_devices = :devices,
                    confirmed_supplies = :supplies,
                    confirmation_note = :note,
                    confirmed_at = NOW(),
                    confirmed_by = :confirmed_by,
                    updated_at = NOW()
                WHERE id = :rec_id
            """),
            {
                "rec_id": str(rec_id),
                "devices": json.dumps(device_ids),
                "supplies": json.dumps(supplies, ensure_ascii=False),
                "note": note,
                "confirmed_by": str(confirmed_by) if confirmed_by else None,
            }
        )
        await self.db.commit()
        
        return await self.get_by_id(rec_id)
    
    async def cancel(self, rec_id: UUID) -> None:
        """取消推荐"""
        await self.db.execute(
            text("""
                UPDATE operational_v2.equipment_recommendations_v2 SET
                    status = 'cancelled',
                    updated_at = NOW()
                WHERE id = :rec_id
            """),
            {"rec_id": str(rec_id)}
        )
        await self.db.commit()
    
    async def create_pending(self, event_id: UUID) -> UUID:
        """创建待处理推荐记录"""
        result = await self.db.execute(
            text("""
                INSERT INTO operational_v2.equipment_recommendations_v2 (event_id, status)
                VALUES (:event_id, 'pending')
                RETURNING id
            """),
            {"event_id": str(event_id)}
        )
        rec_id = result.fetchone()[0]
        await self.db.commit()
        return rec_id
    
    async def list_by_status(
        self, 
        status: str, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """按状态列出推荐"""
        result = await self.db.execute(
            text("""
                SELECT 
                    r.id, r.event_id, r.status,
                    r.disaster_analysis, r.requirement_analysis,
                    r.recommended_devices, r.recommended_supplies,
                    r.shortage_alerts, r.loading_plan,
                    r.confirmed_devices, r.confirmed_supplies, r.confirmation_note,
                    r.agent_trace,
                    r.created_at, r.ready_at, r.confirmed_at, r.confirmed_by, r.updated_at,
                    e.event_code, e.title as event_title
                FROM operational_v2.equipment_recommendations_v2 r
                JOIN operational_v2.events_v2 e ON r.event_id = e.id
                WHERE r.status = :status
                ORDER BY r.created_at DESC
                LIMIT :limit
            """),
            {"status": status, "limit": limit}
        )
        rows = result.fetchall()
        return [self._row_to_dict(row, include_event=True) for row in rows]
    
    def _row_to_dict(self, row, include_event: bool = False) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        data = {
            "id": row.id,
            "event_id": row.event_id,
            "status": row.status,
            "disaster_analysis": row.disaster_analysis,
            "requirement_analysis": row.requirement_analysis,
            "recommended_devices": row.recommended_devices or [],
            "recommended_supplies": row.recommended_supplies or [],
            "shortage_alerts": row.shortage_alerts or [],
            "loading_plan": row.loading_plan,
            "confirmed_devices": row.confirmed_devices,
            "confirmed_supplies": row.confirmed_supplies,
            "confirmation_note": row.confirmation_note,
            "agent_trace": row.agent_trace,
            "created_at": row.created_at,
            "ready_at": row.ready_at,
            "confirmed_at": row.confirmed_at,
            "confirmed_by": row.confirmed_by,
            "updated_at": row.updated_at,
        }
        
        if include_event and hasattr(row, 'event_code'):
            data["event_code"] = row.event_code
            data["event_title"] = row.event_title
        
        return data
