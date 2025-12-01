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
    
    async def get_quest_status(self, event_id: UUID) -> str:
        """
        从数据库推断任务状态
        
        状态逻辑:
        - pending: 没有调度记录
        - dispatched: 有调度记录但未全部准备完成
        - ready: 所有车辆准备完成
        - departed: 有车辆已出发
        """
        result = await self.db.execute(
            text("""
                SELECT 
                    CASE 
                        WHEN COUNT(*) = 0 THEN 'pending'
                        WHEN COUNT(CASE WHEN status = 'departed' THEN 1 END) > 0 THEN 'departed'
                        WHEN COUNT(CASE WHEN status = 'ready' THEN 1 END) = COUNT(*) THEN 'ready'
                        WHEN COUNT(CASE WHEN status IN ('dispatched', 'confirmed', 'preparing', 'ready') THEN 1 END) > 0 THEN 'dispatched'
                        ELSE 'pending'
                    END as quest_status
                FROM operational_v2.equipment_preparation_dispatch_v2
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        return row.quest_status if row else "pending"
    
    async def mark_departed(self, event_id: UUID) -> bool:
        """标记已出发（更新所有车辆状态为departed）"""
        # 注意: 当前表没有departed状态，这里将所有ready状态标记为departed
        # 实际实现可能需要添加新的状态或字段
        result = await self.db.execute(
            text("""
                UPDATE operational_v2.equipment_preparation_dispatch_v2
                SET status = 'departed', updated_at = NOW()
                WHERE event_id = :event_id AND status = 'ready'
            """),
            {"event_id": str(event_id)}
        )
        await self.db.commit()
        return result.rowcount > 0
    
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


class CarItemAssignmentRepository:
    """车辆装备分配数据访问层"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def clear_by_event(self, event_id: UUID) -> int:
        """
        清理指定事件的所有装备分配记录
        
        用于重新调用装备推荐智能体前清理旧数据，确保推荐结果不受历史数据影响。
        """
        result = await self.db.execute(
            text("""
                DELETE FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        await self.db.commit()
        logger.info(f"已清理事件 {event_id} 的装备分配记录，共 {result.rowcount} 条")
        return result.rowcount
    
    async def add_item(
        self,
        event_id: UUID,
        car_id: UUID,
        item_id: UUID,
        item_type: str,
        quantity: int = 1,
        parent_device_id: Optional[UUID] = None,
        is_exclusive: bool = False,
        assigned_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加装备到车辆"""
        result = await self.db.execute(
            text("""
                INSERT INTO operational_v2.car_item_assignment 
                (event_id, car_id, item_id, item_type, quantity, parent_device_id, 
                 is_exclusive, is_selected, assigned_by, assigned_at)
                VALUES (:event_id, :car_id, :item_id, :item_type, :quantity, :parent_device_id,
                        :is_exclusive, true, :assigned_by, NOW())
                ON CONFLICT (event_id, car_id, item_id) DO UPDATE SET
                    is_selected = true,
                    quantity = :quantity,
                    assigned_by = :assigned_by,
                    assigned_at = NOW(),
                    updated_at = NOW()
                RETURNING id, assigned_at
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "item_id": str(item_id),
                "item_type": item_type,
                "quantity": quantity,
                "parent_device_id": str(parent_device_id) if parent_device_id else None,
                "is_exclusive": is_exclusive,
                "assigned_by": assigned_by,
            }
        )
        row = result.fetchone()
        await self.db.commit()
        return {"id": row.id, "assigned_at": row.assigned_at}
    
    async def remove_item(
        self,
        event_id: UUID,
        car_id: UUID,
        item_id: UUID,
    ) -> bool:
        """从车辆移除装备"""
        result = await self.db.execute(
            text("""
                DELETE FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id AND car_id = :car_id AND item_id = :item_id
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "item_id": str(item_id),
            }
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def toggle_item(
        self,
        event_id: UUID,
        car_id: UUID,
        item_id: UUID,
        is_selected: bool,
    ) -> bool:
        """切换装备选中状态"""
        result = await self.db.execute(
            text("""
                UPDATE operational_v2.car_item_assignment
                SET is_selected = :is_selected, updated_at = NOW()
                WHERE event_id = :event_id AND car_id = :car_id AND item_id = :item_id
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "item_id": str(item_id),
                "is_selected": is_selected,
            }
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def update_modules_selection(
        self,
        event_id: UUID,
        car_id: UUID,
        device_id: UUID,
        selected_module_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """批量更新模块选中状态"""
        # 获取该设备下的所有模块分配
        result = await self.db.execute(
            text("""
                SELECT id, item_id FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id AND car_id = :car_id 
                  AND parent_device_id = :device_id AND item_type = 'module'
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "device_id": str(device_id),
            }
        )
        modules = result.fetchall()
        
        # 更新选中状态
        updated_modules = []
        for mod in modules:
            is_selected = str(mod.item_id) in selected_module_ids
            await self.db.execute(
                text("""
                    UPDATE operational_v2.car_item_assignment
                    SET is_selected = :is_selected, updated_at = NOW()
                    WHERE id = :id
                """),
                {"id": mod.id, "is_selected": is_selected}
            )
            updated_modules.append({
                "id": str(mod.item_id),
                "isSelected": is_selected,
            })
        
        await self.db.commit()
        return updated_modules
    
    async def get_by_event_car(
        self,
        event_id: UUID,
        car_id: UUID,
    ) -> List[Dict[str, Any]]:
        """获取车辆的装备分配列表"""
        result = await self.db.execute(
            text("""
                SELECT id, event_id, car_id, item_id, item_type, parent_device_id,
                       is_selected, is_exclusive, quantity, assigned_by, assigned_at
                FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id AND car_id = :car_id
                ORDER BY assigned_at
            """),
            {"event_id": str(event_id), "car_id": str(car_id)}
        )
        rows = result.fetchall()
        return [
            {
                "id": str(row.id),
                "event_id": str(row.event_id),
                "car_id": str(row.car_id),
                "item_id": str(row.item_id),
                "item_type": row.item_type,
                "parent_device_id": str(row.parent_device_id) if row.parent_device_id else None,
                "is_selected": row.is_selected,
                "is_exclusive": row.is_exclusive,
                "quantity": row.quantity,
                "assigned_by": row.assigned_by,
                "assigned_at": row.assigned_at,
            }
            for row in rows
        ]
    
    async def get_all_by_event(self, event_id: UUID) -> List[Dict[str, Any]]:
        """获取事件的所有用户装备分配记录（用于 get_car_list 读取用户手动分配）"""
        result = await self.db.execute(
            text("""
                SELECT car_id, item_id, is_selected
                FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        rows = result.fetchall()
        return [
            {"car_id": str(r.car_id), "item_id": str(r.item_id), "is_selected": r.is_selected}
            for r in rows
        ]
    
    async def check_item_assigned(
        self,
        event_id: UUID,
        item_id: UUID,
        exclude_car_id: Optional[UUID] = None,
    ) -> Optional[str]:
        """检查装备是否已分配给其他车辆，返回车辆ID"""
        params = {
            "event_id": str(event_id),
            "item_id": str(item_id),
        }
        sql = """
            SELECT car_id FROM operational_v2.car_item_assignment
            WHERE event_id = :event_id AND item_id = :item_id AND is_selected = true
        """
        if exclude_car_id:
            sql += " AND car_id != :exclude_car_id"
            params["exclude_car_id"] = str(exclude_car_id)
        
        result = await self.db.execute(text(sql), params)
        row = result.fetchone()
        return str(row.car_id) if row else None
    
    async def ensure_exclusive_item(
        self,
        event_id: UUID,
        car_id: UUID,
        item_id: UUID,
        item_type: str = "device",
    ) -> None:
        """确保专属装备存在分配记录（用于toggle操作）"""
        await self.db.execute(
            text("""
                INSERT INTO operational_v2.car_item_assignment 
                (event_id, car_id, item_id, item_type, is_exclusive, is_selected)
                VALUES (:event_id, :car_id, :item_id, :item_type, true, false)
                ON CONFLICT (event_id, car_id, item_id) DO NOTHING
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "item_id": str(item_id),
                "item_type": item_type,
            }
        )
        await self.db.commit()
    
    async def mark_deselected(
        self,
        event_id: UUID,
        car_id: UUID,
        item_id: UUID,
        item_type: str = "device",
    ) -> None:
        """标记装备为未选中（用于移除AI推荐的装备）"""
        await self.db.execute(
            text("""
                INSERT INTO operational_v2.car_item_assignment 
                (event_id, car_id, item_id, item_type, is_exclusive, is_selected)
                VALUES (:event_id, :car_id, :item_id, :item_type, false, false)
                ON CONFLICT (event_id, car_id, item_id) DO UPDATE SET
                    is_selected = false,
                    updated_at = NOW()
            """),
            {
                "event_id": str(event_id),
                "car_id": str(car_id),
                "item_id": str(item_id),
                "item_type": item_type,
            }
        )
        await self.db.commit()


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


class MyEquipmentRepository:
    """
    车辆成员装备查询数据访问层
    
    用于车辆成员查看和修改自己车辆被分配的装备。
    数据来源是指挥员分配的结果（car_item_assignment），不是AI推荐。
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_vehicle(self, user_id: UUID, event_id: UUID) -> Optional[Dict[str, Any]]:
        """
        获取用户所属的车辆
        
        通过 event_id 找到 scenario_id，再通过 seat_assignments_v2 找到用户所属车辆。
        """
        result = await self.db.execute(
            text("""
                SELECT 
                    v.id AS vehicle_id,
                    v.code AS vehicle_code,
                    v.name AS vehicle_name,
                    v.vehicle_type,
                    sa.seat_role,
                    COALESCE(d.status, 'pending') AS dispatch_status,
                    d.dispatched_at,
                    du.real_name AS dispatched_by_name
                FROM operational_v2.events_v2 e
                JOIN operational_v2.seat_assignments_v2 sa ON sa.scenario_id = e.scenario_id
                JOIN operational_v2.vehicles_v2 v ON sa.vehicle_id = v.id
                LEFT JOIN operational_v2.equipment_preparation_dispatch_v2 d 
                    ON d.event_id = e.id AND d.vehicle_id = v.id
                LEFT JOIN operational_v2.users_v2 du ON d.dispatched_by = du.id
                WHERE e.id = :event_id 
                  AND sa.user_id = :user_id
                  AND sa.status IN ('assigned', 'active')
                LIMIT 1
            """),
            {"event_id": str(event_id), "user_id": str(user_id)}
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "vehicle_id": str(row.vehicle_id),
            "vehicle_code": row.vehicle_code,
            "vehicle_name": row.vehicle_name,
            "vehicle_type": row.vehicle_type,
            "seat_role": row.seat_role,
            "dispatch_status": row.dispatch_status,
            "dispatched_at": row.dispatched_at.isoformat() if row.dispatched_at else None,
            "dispatched_by_name": row.dispatched_by_name,
        }
    
    async def get_vehicle_assigned_items(
        self, 
        event_id: UUID, 
        vehicle_id: UUID
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取车辆被分配的装备（指挥员分配的，is_selected=true）
        
        返回设备、物资、模块三个列表。
        """
        # 查询设备
        devices_result = await self.db.execute(
            text("""
                SELECT 
                    ca.item_id,
                    ca.quantity,
                    d.name,
                    d.code,
                    d.device_type,
                    d.model,
                    d.manufacturer,
                    d.properties
                FROM operational_v2.car_item_assignment ca
                JOIN operational_v2.devices_v2 d ON ca.item_id = d.id
                WHERE ca.event_id = :event_id 
                  AND ca.car_id = :vehicle_id
                  AND ca.item_type = 'device'
                  AND ca.is_selected = true
            """),
            {"event_id": str(event_id), "vehicle_id": str(vehicle_id)}
        )
        devices = []
        for r in devices_result.fetchall():
            props = r.properties or {}
            devices.append({
                "id": str(r.item_id),
                "name": r.name,
                "code": r.code,
                "device_type": r.device_type,
                "model": r.model or "",
                "quantity": r.quantity,
                "manufacturer": r.manufacturer or "",
                "image": props.get("image"),
                "description": props.get("description"),
                "specifications": props.get("specifications"),
            })
        
        # 查询物资
        supplies_result = await self.db.execute(
            text("""
                SELECT 
                    ca.item_id,
                    ca.quantity,
                    s.name,
                    s.code,
                    s.category
                FROM operational_v2.car_item_assignment ca
                JOIN operational_v2.supplies_v2 s ON ca.item_id = s.id
                WHERE ca.event_id = :event_id 
                  AND ca.car_id = :vehicle_id
                  AND ca.item_type = 'supply'
                  AND ca.is_selected = true
            """),
            {"event_id": str(event_id), "vehicle_id": str(vehicle_id)}
        )
        supplies = [
            {
                "id": str(r.item_id),
                "name": r.name,
                "code": r.code,
                "category": r.category or "",
                "quantity": r.quantity,
            }
            for r in supplies_result.fetchall()
        ]
        
        # 查询模块（按父设备分组）
        modules_result = await self.db.execute(
            text("""
                SELECT 
                    ca.item_id,
                    ca.parent_device_id,
                    ca.is_selected,
                    m.name,
                    m.code,
                    m.module_type
                FROM operational_v2.car_item_assignment ca
                JOIN operational_v2.modules_v2 m ON ca.item_id = m.id
                WHERE ca.event_id = :event_id 
                  AND ca.car_id = :vehicle_id
                  AND ca.item_type = 'module'
            """),
            {"event_id": str(event_id), "vehicle_id": str(vehicle_id)}
        )
        modules = [
            {
                "id": str(r.item_id),
                "name": r.name,
                "code": r.code,
                "module_type": r.module_type or "",
                "parent_device_id": str(r.parent_device_id) if r.parent_device_id else None,
                "is_selected": r.is_selected,
            }
            for r in modules_result.fetchall()
        ]
        
        return {
            "devices": devices,
            "supplies": supplies,
            "modules": modules,
        }
    
    async def toggle_item_selection(
        self,
        event_id: UUID,
        vehicle_id: UUID,
        item_id: UUID,
        is_selected: bool,
        updated_by: str,
    ) -> bool:
        """
        切换装备选中状态
        
        由车辆成员调用，修改指挥员分配的装备。
        """
        result = await self.db.execute(
            text("""
                UPDATE operational_v2.car_item_assignment
                SET is_selected = :is_selected, 
                    assigned_by = :updated_by,
                    updated_at = NOW()
                WHERE event_id = :event_id 
                  AND car_id = :vehicle_id 
                  AND item_id = :item_id
            """),
            {
                "event_id": str(event_id),
                "vehicle_id": str(vehicle_id),
                "item_id": str(item_id),
                "is_selected": is_selected,
                "updated_by": updated_by,
            }
        )
        await self.db.commit()
        return result.rowcount > 0
