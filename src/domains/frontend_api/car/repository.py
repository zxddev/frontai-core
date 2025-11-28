"""
装备准备调度 Repository

管理 equipment_preparation_dispatch_v2 表的CRUD操作
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PreparationDispatchRepository:
    """装备准备调度数据访问层"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_dispatch(
        self,
        event_id: UUID,
        vehicle_id: UUID,
        device_ids: List[str],
        supplies: List[Dict[str, Any]],
        recommendation_id: Optional[UUID] = None,
        dispatched_by: Optional[UUID] = None,
    ) -> UUID:
        """创建调度记录"""
        result = await self.db.execute(
            text("""
                INSERT INTO operational_v2.equipment_preparation_dispatch_v2 
                (event_id, recommendation_id, vehicle_id, assigned_device_ids, 
                 assigned_supplies, status, dispatched_by, dispatched_at)
                VALUES (:event_id, :recommendation_id, :vehicle_id, :device_ids,
                        :supplies, 'dispatched', :dispatched_by, NOW())
                ON CONFLICT (event_id, vehicle_id) DO UPDATE SET
                    assigned_device_ids = :device_ids,
                    assigned_supplies = :supplies,
                    status = 'dispatched',
                    dispatched_by = :dispatched_by,
                    dispatched_at = NOW(),
                    updated_at = NOW()
                RETURNING id
            """),
            {
                "event_id": str(event_id),
                "recommendation_id": str(recommendation_id) if recommendation_id else None,
                "vehicle_id": str(vehicle_id),
                "device_ids": device_ids,
                "supplies": json.dumps(supplies, ensure_ascii=False),
                "dispatched_by": str(dispatched_by) if dispatched_by else None,
            }
        )
        dispatch_id = result.fetchone()[0]
        await self.db.commit()
        return dispatch_id
    
    async def get_by_event(self, event_id: UUID) -> List[Dict[str, Any]]:
        """获取事件的所有调度记录"""
        result = await self.db.execute(
            text("""
                SELECT 
                    d.id, d.event_id, d.recommendation_id, d.vehicle_id,
                    d.assigned_device_ids, d.assigned_supplies,
                    d.status, d.assignee_user_id, d.dispatched_by,
                    d.dispatched_at, d.confirmed_at, d.ready_at,
                    d.created_at, d.updated_at,
                    v.name as vehicle_name,
                    u.real_name as assignee_name
                FROM operational_v2.equipment_preparation_dispatch_v2 d
                LEFT JOIN operational_v2.vehicles_v2 v ON d.vehicle_id = v.id
                LEFT JOIN operational_v2.users_v2 u ON d.assignee_user_id = u.id
                WHERE d.event_id = :event_id
                ORDER BY d.created_at
            """),
            {"event_id": str(event_id)}
        )
        rows = result.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    async def get_by_vehicle(
        self, 
        event_id: UUID, 
        vehicle_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """获取特定车辆的调度记录"""
        result = await self.db.execute(
            text("""
                SELECT 
                    d.id, d.event_id, d.recommendation_id, d.vehicle_id,
                    d.assigned_device_ids, d.assigned_supplies,
                    d.status, d.assignee_user_id, d.dispatched_by,
                    d.dispatched_at, d.confirmed_at, d.ready_at,
                    d.created_at, d.updated_at,
                    v.name as vehicle_name
                FROM operational_v2.equipment_preparation_dispatch_v2 d
                LEFT JOIN operational_v2.vehicles_v2 v ON d.vehicle_id = v.id
                WHERE d.event_id = :event_id AND d.vehicle_id = :vehicle_id
            """),
            {"event_id": str(event_id), "vehicle_id": str(vehicle_id)}
        )
        row = result.fetchone()
        return self._row_to_dict(row) if row else None
    
    async def update_status(
        self,
        event_id: UUID,
        vehicle_id: UUID,
        status: str,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """更新调度状态"""
        update_fields = ["status = :status", "updated_at = NOW()"]
        params: Dict[str, Any] = {
            "event_id": str(event_id),
            "vehicle_id": str(vehicle_id),
            "status": status,
        }
        
        if status == "confirmed":
            update_fields.append("confirmed_at = NOW()")
            if user_id:
                update_fields.append("assignee_user_id = :user_id")
                params["user_id"] = str(user_id)
        elif status == "ready":
            update_fields.append("ready_at = NOW()")
        
        sql = f"""
            UPDATE operational_v2.equipment_preparation_dispatch_v2 
            SET {', '.join(update_fields)}
            WHERE event_id = :event_id AND vehicle_id = :vehicle_id
        """
        
        result = await self.db.execute(text(sql), params)
        await self.db.commit()
        return result.rowcount > 0
    
    async def get_dispatch_summary(self, event_id: UUID) -> Dict[str, Any]:
        """获取调度汇总统计"""
        result = await self.db.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status IN ('confirmed', 'preparing', 'ready') THEN 1 END) as confirmed_count,
                    COUNT(CASE WHEN status = 'ready' THEN 1 END) as ready_count
                FROM operational_v2.equipment_preparation_dispatch_v2
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        return {
            "total": row.total or 0,
            "confirmed_count": row.confirmed_count or 0,
            "ready_count": row.ready_count or 0,
        }
    
    async def check_all_ready(self, event_id: UUID) -> bool:
        """检查是否所有车辆都已准备完成"""
        result = await self.db.execute(
            text("""
                SELECT 
                    COUNT(*) = COUNT(CASE WHEN status = 'ready' THEN 1 END) as all_ready
                FROM operational_v2.equipment_preparation_dispatch_v2
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        return row.all_ready if row else False
    
    async def get_vehicle_users(self, vehicle_id: UUID) -> List[Dict[str, Any]]:
        """获取车辆关联的用户（从seat_assignments_v2）"""
        result = await self.db.execute(
            text("""
                SELECT 
                    sa.user_id,
                    u.real_name,
                    u.username,
                    sa.seat_role
                FROM operational_v2.seat_assignments_v2 sa
                JOIN operational_v2.users_v2 u ON sa.user_id = u.id
                WHERE sa.vehicle_id = :vehicle_id 
                  AND sa.status IN ('assigned', 'active')
                  AND sa.user_id IS NOT NULL
            """),
            {"vehicle_id": str(vehicle_id)}
        )
        rows = result.fetchall()
        return [
            {
                "user_id": str(row.user_id),
                "real_name": row.real_name,
                "username": row.username,
                "seat_role": row.seat_role,
            }
            for row in rows
        ]
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "id": row.id,
            "event_id": row.event_id,
            "recommendation_id": row.recommendation_id,
            "vehicle_id": row.vehicle_id,
            "assigned_device_ids": row.assigned_device_ids or [],
            "assigned_supplies": row.assigned_supplies or [],
            "status": row.status,
            "assignee_user_id": row.assignee_user_id,
            "dispatched_by": row.dispatched_by,
            "dispatched_at": row.dispatched_at,
            "confirmed_at": row.confirmed_at,
            "ready_at": row.ready_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "vehicle_name": getattr(row, 'vehicle_name', None),
            "assignee_name": getattr(row, 'assignee_name', None),
        }


class ModuleRepository:
    """模块数据访问层"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, module_id: UUID) -> Optional[Dict[str, Any]]:
        """根据ID获取模块"""
        result = await self.db.execute(
            text("""
                SELECT 
                    id, code, name, module_type,
                    weight_kg, slots_required,
                    compatible_device_types,
                    provides_capability, capability_params,
                    applicable_disasters,
                    created_at, updated_at
                FROM operational_v2.modules_v2
                WHERE id = :module_id
            """),
            {"module_id": str(module_id)}
        )
        row = result.fetchone()
        return self._row_to_dict(row) if row else None
    
    async def list_by_device_type(self, device_type: str) -> List[Dict[str, Any]]:
        """获取适配指定设备类型的模块"""
        result = await self.db.execute(
            text("""
                SELECT 
                    id, code, name, module_type,
                    weight_kg, slots_required,
                    compatible_device_types,
                    provides_capability, capability_params,
                    applicable_disasters,
                    created_at, updated_at
                FROM operational_v2.modules_v2
                WHERE :device_type = ANY(compatible_device_types)
                ORDER BY name
            """),
            {"device_type": device_type}
        )
        rows = result.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    async def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取所有模块"""
        result = await self.db.execute(
            text("""
                SELECT 
                    id, code, name, module_type,
                    weight_kg, slots_required,
                    compatible_device_types,
                    provides_capability, capability_params,
                    applicable_disasters,
                    exclusive_to_device_id,
                    created_at, updated_at
                FROM operational_v2.modules_v2
                ORDER BY name
                LIMIT :limit
            """),
            {"limit": limit}
        )
        rows = result.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "module_type": row.module_type,
            "weight_kg": float(row.weight_kg) if row.weight_kg else 0,
            "slots_required": row.slots_required or 1,
            "compatible_device_types": row.compatible_device_types or [],
            "provides_capability": row.provides_capability,
            "capability_params": row.capability_params or {},
            "applicable_disasters": row.applicable_disasters or [],
            "exclusive_to_device_id": str(row.exclusive_to_device_id) if row.exclusive_to_device_id else None,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
