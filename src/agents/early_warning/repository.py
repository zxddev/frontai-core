"""
预警监测数据访问层

职责: 数据库CRUD操作
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, Sequence, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON, ST_Buffer, ST_Distance

from .models import DisasterSituation, WarningRecord

logger = logging.getLogger(__name__)


class DisasterRepository:
    """灾害态势数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(
        self,
        disaster_type: str,
        boundary_geojson: Dict[str, Any],
        scenario_id: Optional[UUID] = None,
        disaster_name: Optional[str] = None,
        buffer_distance_m: int = 3000,
        spread_direction: Optional[str] = None,
        spread_speed_mps: Optional[float] = None,
        severity_level: int = 3,
        source: Optional[str] = None,
        properties: Optional[Dict] = None,
        needs_response: bool = True,
    ) -> DisasterSituation:
        """创建灾害态势记录"""
        
        # 计算中心点
        coords = boundary_geojson.get("coordinates", [[]])[0]
        if coords:
            center_lon = sum(p[0] for p in coords) / len(coords)
            center_lat = sum(p[1] for p in coords) / len(coords)
            center_geojson = {"type": "Point", "coordinates": [center_lon, center_lat]}
        else:
            center_geojson = None
        
        disaster = DisasterSituation(
            scenario_id=scenario_id,
            disaster_type=disaster_type,
            disaster_name=disaster_name,
            boundary=func.ST_GeomFromGeoJSON(json.dumps(boundary_geojson)),
            center_point=func.ST_GeomFromGeoJSON(json.dumps(center_geojson)) if center_geojson else None,
            buffer_distance_m=buffer_distance_m,
            spread_direction=spread_direction,
            spread_speed_mps=spread_speed_mps,
            severity_level=severity_level,
            source=source,
            properties=properties or {},
            needs_response=needs_response,
        )
        
        self._db.add(disaster)
        await self._db.flush()
        await self._db.refresh(disaster)
        
        logger.info(f"创建灾害态势: type={disaster_type}, id={disaster.id}")
        return disaster
    
    async def get_by_id(self, disaster_id: UUID) -> Optional[DisasterSituation]:
        """根据ID查询灾害态势"""
        result = await self._db.execute(
            select(DisasterSituation).where(DisasterSituation.id == disaster_id)
        )
        return result.scalar_one_or_none()
    
    async def get_boundary_geojson(self, disaster_id: UUID) -> Optional[Dict[str, Any]]:
        """获取灾害边界的GeoJSON"""
        result = await self._db.execute(
            select(ST_AsGeoJSON(DisasterSituation.boundary))
            .where(DisasterSituation.id == disaster_id)
        )
        geojson_str = result.scalar_one_or_none()
        if geojson_str:
            return json.loads(geojson_str)
        return None
    
    async def get_active_disasters(self, scenario_id: Optional[UUID] = None) -> Sequence[DisasterSituation]:
        """获取活跃的灾害态势"""
        query = select(DisasterSituation).where(DisasterSituation.status == "active")
        if scenario_id:
            query = query.where(DisasterSituation.scenario_id == scenario_id)
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def update_status(self, disaster_id: UUID, status: str) -> bool:
        """更新灾害状态"""
        result = await self._db.execute(
            update(DisasterSituation)
            .where(DisasterSituation.id == disaster_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        return result.rowcount > 0


class WarningRepository:
    """预警记录数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(
        self,
        disaster_id: UUID,
        affected_type: str,
        affected_id: UUID,
        affected_name: str,
        notify_target_type: str,
        warning_level: str,
        distance_m: float,
        scenario_id: Optional[UUID] = None,
        notify_target_id: Optional[UUID] = None,
        notify_target_name: Optional[str] = None,
        estimated_contact_minutes: Optional[int] = None,
        route_affected: bool = False,
        warning_title: Optional[str] = None,
        warning_message: Optional[str] = None,
        properties: Optional[Dict] = None,
    ) -> WarningRecord:
        """创建预警记录"""
        
        warning = WarningRecord(
            disaster_id=disaster_id,
            scenario_id=scenario_id,
            affected_type=affected_type,
            affected_id=affected_id,
            affected_name=affected_name,
            notify_target_type=notify_target_type,
            notify_target_id=notify_target_id,
            notify_target_name=notify_target_name,
            warning_level=warning_level,
            distance_m=distance_m,
            estimated_contact_minutes=estimated_contact_minutes,
            route_affected=route_affected,
            warning_title=warning_title,
            warning_message=warning_message,
            properties=properties or {},
        )
        
        self._db.add(warning)
        await self._db.flush()
        await self._db.refresh(warning)
        
        logger.info(f"创建预警记录: id={warning.id}, affected={affected_type}/{affected_id}")
        return warning
    
    async def get_by_id(self, warning_id: UUID) -> Optional[WarningRecord]:
        """根据ID查询预警记录"""
        result = await self._db.execute(
            select(WarningRecord).where(WarningRecord.id == warning_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        scenario_id: Optional[UUID] = None,
        status: Optional[str] = None,
        affected_type: Optional[str] = None,
    ) -> tuple[Sequence[WarningRecord], int]:
        """分页查询预警列表"""
        query = select(WarningRecord)
        count_query = select(func.count(WarningRecord.id))
        
        if scenario_id:
            query = query.where(WarningRecord.scenario_id == scenario_id)
            count_query = count_query.where(WarningRecord.scenario_id == scenario_id)
        
        if status:
            query = query.where(WarningRecord.status == status)
            count_query = count_query.where(WarningRecord.status == status)
        
        if affected_type:
            query = query.where(WarningRecord.affected_type == affected_type)
            count_query = count_query.where(WarningRecord.affected_type == affected_type)
        
        # 分页
        query = query.order_by(WarningRecord.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def acknowledge(self, warning_id: UUID) -> bool:
        """确认收到预警"""
        result = await self._db.execute(
            update(WarningRecord)
            .where(WarningRecord.id == warning_id)
            .where(WarningRecord.status == "pending")
            .values(status="acknowledged", acknowledged_at=datetime.utcnow())
        )
        return result.rowcount > 0
    
    async def respond(
        self,
        warning_id: UUID,
        action: str,
        reason: Optional[str] = None,
    ) -> bool:
        """响应预警"""
        values = {
            "status": "responded",
            "response_action": action,
            "response_reason": reason,
            "responded_at": datetime.utcnow(),
        }
        
        # 如果是continue或standby，直接标记为resolved
        if action in ("continue", "standby"):
            values["status"] = "resolved"
            values["resolved_at"] = datetime.utcnow()
        
        result = await self._db.execute(
            update(WarningRecord)
            .where(WarningRecord.id == warning_id)
            .values(**values)
        )
        return result.rowcount > 0
    
    async def confirm_detour(
        self,
        warning_id: UUID,
        route_id: str,
    ) -> bool:
        """确认绕行路线"""
        result = await self._db.execute(
            update(WarningRecord)
            .where(WarningRecord.id == warning_id)
            .values(
                status="resolved",
                selected_route_id=route_id,
                resolved_at=datetime.utcnow(),
            )
        )
        return result.rowcount > 0
    
    async def cancel_by_disaster(self, disaster_id: UUID) -> int:
        """取消灾害相关的未处理预警"""
        result = await self._db.execute(
            update(WarningRecord)
            .where(WarningRecord.disaster_id == disaster_id)
            .where(WarningRecord.status.in_(["pending", "acknowledged"]))
            .values(status="cancelled")
        )
        return result.rowcount
