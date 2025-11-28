"""
风险区域数据库操作层

基于 disaster_affected_areas_v2 表的 CRUD 操作
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
    RiskAreaCreateRequest,
    RiskAreaUpdateRequest,
    PassageStatusUpdateRequest,
    GeoJsonPolygon,
)


logger = logging.getLogger(__name__)


class RiskAreaRepository:
    """风险区域数据仓库"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, request: RiskAreaCreateRequest) -> dict:
        """创建风险区域"""
        polygon_wkt = self._geojson_to_wkt(request.geometry)

        sql = text("""
            INSERT INTO operational_v2.disaster_affected_areas_v2 (
                scenario_id, name, area_type, geometry, severity, risk_level,
                passable, passable_vehicle_types, speed_reduction_percent,
                passage_status, reconnaissance_required,
                description, estimated_end_at
            ) VALUES (
                :scenario_id, :name, :area_type, ST_GeogFromText(:geometry),
                :severity, :risk_level, :passable, :passable_vehicle_types,
                :speed_reduction_percent, :passage_status, :reconnaissance_required,
                :description, :estimated_end_at
            )
            RETURNING id, created_at, updated_at
        """)

        result = await self.db.execute(sql, {
            "scenario_id": str(request.scenario_id),
            "name": request.name,
            "area_type": request.area_type.value,
            "geometry": polygon_wkt,
            "severity": request.severity.value,
            "risk_level": request.risk_level,
            "passable": request.passable,
            "passable_vehicle_types": request.passable_vehicle_types or None,
            "speed_reduction_percent": request.speed_reduction_percent,
            "passage_status": request.passage_status.value,
            "reconnaissance_required": request.reconnaissance_required,
            "description": request.description,
            "estimated_end_at": request.estimated_end_at,
        })

        row = result.fetchone()
        await self.db.commit()

        logger.info(f"风险区域已创建: id={row.id}, name={request.name}")
        return await self.get_by_id(row.id)

    async def get_by_id(self, area_id: UUID) -> Optional[dict]:
        """根据ID获取风险区域"""
        sql = text("""
            SELECT
                id, scenario_id, name, area_type,
                ST_AsGeoJSON(geometry::geometry)::jsonb as geometry_geojson,
                severity, risk_level, passable, passable_vehicle_types,
                speed_reduction_percent, passage_status, reconnaissance_required,
                description, started_at, estimated_end_at,
                last_verified_at, verified_by,
                created_at, updated_at
            FROM operational_v2.disaster_affected_areas_v2
            WHERE id = :area_id
        """)

        result = await self.db.execute(sql, {"area_id": str(area_id)})
        row = result.fetchone()

        if not row:
            return None

        return self._row_to_dict(row)

    async def list_by_scenario(
        self,
        scenario_id: UUID,
        area_type: Optional[str] = None,
        min_risk_level: Optional[int] = None,
        passage_status: Optional[str] = None,
    ) -> list[dict]:
        """获取想定下的风险区域列表"""
        conditions = ["scenario_id = :scenario_id"]
        params: dict = {"scenario_id": str(scenario_id)}

        if area_type:
            conditions.append("area_type = :area_type")
            params["area_type"] = area_type

        if min_risk_level is not None:
            conditions.append("risk_level >= :min_risk_level")
            params["min_risk_level"] = min_risk_level

        if passage_status:
            conditions.append("passage_status = :passage_status")
            params["passage_status"] = passage_status

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT
                id, scenario_id, name, area_type,
                ST_AsGeoJSON(geometry::geometry)::jsonb as geometry_geojson,
                severity, risk_level, passable, passable_vehicle_types,
                speed_reduction_percent, passage_status, reconnaissance_required,
                description, started_at, estimated_end_at,
                last_verified_at, verified_by,
                created_at, updated_at
            FROM operational_v2.disaster_affected_areas_v2
            WHERE {where_clause}
            ORDER BY risk_level DESC, created_at DESC
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [self._row_to_dict(row) for row in rows]

    async def update(self, area_id: UUID, request: RiskAreaUpdateRequest) -> Optional[dict]:
        """更新风险区域"""
        update_fields = []
        params: dict = {"area_id": str(area_id)}

        if request.name is not None:
            update_fields.append("name = :name")
            params["name"] = request.name

        if request.risk_level is not None:
            update_fields.append("risk_level = :risk_level")
            params["risk_level"] = request.risk_level

        if request.severity is not None:
            update_fields.append("severity = :severity")
            params["severity"] = request.severity.value

        if request.passage_status is not None:
            update_fields.append("passage_status = :passage_status")
            params["passage_status"] = request.passage_status.value

        if request.passable is not None:
            update_fields.append("passable = :passable")
            params["passable"] = request.passable

        if request.passable_vehicle_types is not None:
            update_fields.append("passable_vehicle_types = :passable_vehicle_types")
            params["passable_vehicle_types"] = request.passable_vehicle_types or None

        if request.speed_reduction_percent is not None:
            update_fields.append("speed_reduction_percent = :speed_reduction_percent")
            params["speed_reduction_percent"] = request.speed_reduction_percent

        if request.reconnaissance_required is not None:
            update_fields.append("reconnaissance_required = :reconnaissance_required")
            params["reconnaissance_required"] = request.reconnaissance_required

        if request.description is not None:
            update_fields.append("description = :description")
            params["description"] = request.description

        if request.estimated_end_at is not None:
            update_fields.append("estimated_end_at = :estimated_end_at")
            params["estimated_end_at"] = request.estimated_end_at

        if not update_fields:
            return await self.get_by_id(area_id)

        update_fields.append("updated_at = now()")
        set_clause = ", ".join(update_fields)

        sql = text(f"""
            UPDATE operational_v2.disaster_affected_areas_v2
            SET {set_clause}
            WHERE id = :area_id
            RETURNING id
        """)

        result = await self.db.execute(sql, params)
        row = result.fetchone()

        if not row:
            return None

        await self.db.commit()
        logger.info(f"风险区域已更新: id={area_id}")
        return await self.get_by_id(area_id)

    async def update_passage_status(
        self,
        area_id: UUID,
        request: PassageStatusUpdateRequest,
    ) -> Optional[dict]:
        """更新通行状态"""
        sql = text("""
            UPDATE operational_v2.disaster_affected_areas_v2
            SET
                passage_status = :passage_status,
                last_verified_at = now(),
                verified_by = :verified_by,
                updated_at = now()
            WHERE id = :area_id
            RETURNING id
        """)

        result = await self.db.execute(sql, {
            "area_id": str(area_id),
            "passage_status": request.passage_status.value,
            "verified_by": str(request.verified_by) if request.verified_by else None,
        })

        row = result.fetchone()
        if not row:
            return None

        await self.db.commit()
        logger.info(f"风险区域通行状态已更新: id={area_id}, status={request.passage_status.value}")
        return await self.get_by_id(area_id)

    async def delete(self, area_id: UUID) -> bool:
        """删除风险区域"""
        sql = text("""
            DELETE FROM operational_v2.disaster_affected_areas_v2
            WHERE id = :area_id
            RETURNING id
        """)

        result = await self.db.execute(sql, {"area_id": str(area_id)})
        row = result.fetchone()

        if not row:
            return False

        await self.db.commit()
        logger.info(f"风险区域已删除: id={area_id}")
        return True

    @staticmethod
    def _geojson_to_wkt(geometry: GeoJsonPolygon) -> str:
        """将 GeoJSON Polygon 转换为 WKT 格式"""
        coords = geometry.coordinates[0]
        points = ", ".join(f"{lng} {lat}" for lng, lat in coords)
        return f"POLYGON(({points}))"

    @staticmethod
    def _row_to_dict(row) -> dict:
        """将数据库行转换为字典"""
        return {
            "id": row.id,
            "scenario_id": row.scenario_id,
            "name": row.name,
            "area_type": row.area_type,
            "geometry_geojson": row.geometry_geojson,
            "severity": row.severity,
            "risk_level": row.risk_level,
            "passable": row.passable,
            "passable_vehicle_types": row.passable_vehicle_types,
            "speed_reduction_percent": row.speed_reduction_percent,
            "passage_status": row.passage_status or "unknown",
            "reconnaissance_required": row.reconnaissance_required or False,
            "description": row.description,
            "started_at": row.started_at,
            "estimated_end_at": row.estimated_end_at,
            "last_verified_at": row.last_verified_at,
            "verified_by": row.verified_by,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
