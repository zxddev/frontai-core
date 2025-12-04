"""
规划路径数据访问层

存储和查询 planned_routes_v2 表
外键：task_id → task_requirements_v2(id)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point

logger = logging.getLogger(__name__)


@dataclass
class PlannedRouteRecord:
    """规划路径记录"""
    id: UUID
    task_id: Optional[UUID]
    vehicle_id: Optional[UUID]
    team_id: Optional[UUID]
    total_distance_m: float
    estimated_time_minutes: int
    risk_level: int
    status: str
    planned_at: datetime
    properties: Dict[str, Any]
    # 路径点（从 route_geometry 解析）
    polyline: List[Point]


class PlannedRouteRepository:
    """
    规划路径数据仓库
    
    对应表：operational_v2.planned_routes_v2
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(
        self,
        task_id: Optional[UUID],
        vehicle_id: Optional[UUID],
        team_id: Optional[UUID],
        polyline: List[Point],
        total_distance_m: float,
        estimated_time_minutes: int,
        start_location: Optional[Point] = None,
        end_location: Optional[Point] = None,
        risk_level: int = 1,
        status: str = "active",
        properties: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """
        创建规划路径记录
        
        Args:
            task_id: 关联任务ID（task_requirements_v2）
            vehicle_id: 关联车辆ID
            team_id: 关联队伍ID
            polyline: 路径点列表
            total_distance_m: 总距离（米）
            estimated_time_minutes: 预计时间（分钟）
            start_location: 起点
            end_location: 终点
            risk_level: 风险等级 1-10
            status: 状态 planned/active/completed/cancelled/alternative/replaced
            properties: 扩展属性（如 strategy, source 等）
            
        Returns:
            新创建的路径ID
        """
        # 构建 LINESTRING WKT
        if len(polyline) < 2:
            raise ValueError("路径至少需要2个点")
        
        linestring_wkt = "LINESTRING(" + ",".join(f"{p.lon} {p.lat}" for p in polyline) + ")"
        
        # 起终点 WKT
        start_wkt = f"POINT({start_location.lon} {start_location.lat})" if start_location else None
        end_wkt = f"POINT({end_location.lon} {end_location.lat})" if end_location else None
        
        # 如果没有指定起终点，从 polyline 获取
        if not start_wkt and polyline:
            start_wkt = f"POINT({polyline[0].lon} {polyline[0].lat})"
        if not end_wkt and polyline:
            end_wkt = f"POINT({polyline[-1].lon} {polyline[-1].lat})"
        
        sql = text("""
            INSERT INTO operational_v2.planned_routes_v2 (
                task_id, vehicle_id, team_id,
                route_geometry, start_location, end_location,
                total_distance_m, estimated_time_minutes,
                risk_level, status, properties
            ) VALUES (
                :task_id, :vehicle_id, :team_id,
                CAST(ST_GeomFromText(:linestring_wkt, 4326) AS geography),
                CAST(ST_GeomFromText(:start_wkt, 4326) AS geography),
                CAST(ST_GeomFromText(:end_wkt, 4326) AS geography),
                :total_distance_m, :estimated_time_minutes,
                :risk_level, :status, CAST(:properties AS jsonb)
            )
            RETURNING id
        """)
        
        import json
        result = await self._db.execute(sql, {
            "task_id": str(task_id) if task_id else None,
            "vehicle_id": str(vehicle_id) if vehicle_id else None,
            "team_id": str(team_id) if team_id else None,
            "linestring_wkt": linestring_wkt,
            "start_wkt": start_wkt,
            "end_wkt": end_wkt,
            "total_distance_m": total_distance_m,
            "estimated_time_minutes": estimated_time_minutes,
            "risk_level": risk_level,
            "status": status,
            "properties": json.dumps(properties or {}),
        })
        
        route_id = result.scalar_one()
        # 注意：不在此处 commit，由调用方控制事务
        # 如果调用方需要立即持久化，应在外层调用 commit
        
        logger.info(f"创建规划路径: id={route_id}, task_id={task_id}, status={status}")
        return route_id
    
    async def get_by_id(self, route_id: UUID) -> Optional[PlannedRouteRecord]:
        """根据ID查询路径"""
        sql = text("""
            SELECT 
                id, task_id, vehicle_id, team_id,
                total_distance_m, estimated_time_minutes,
                risk_level, status, planned_at, properties,
                ST_AsText(route_geometry) as route_wkt
            FROM operational_v2.planned_routes_v2
            WHERE id = :route_id
        """)
        
        result = await self._db.execute(sql, {"route_id": str(route_id)})
        row = result.fetchone()
        
        if not row:
            return None
        
        return self._row_to_record(row)
    
    async def get_by_task_id(
        self,
        task_id: UUID,
        status: Optional[str] = None,
    ) -> List[PlannedRouteRecord]:
        """
        根据任务ID查询路径
        
        Args:
            task_id: 任务ID（task_requirements_v2）
            status: 可选状态筛选
            
        Returns:
            路径列表
        """
        sql_str = """
            SELECT 
                id, task_id, vehicle_id, team_id,
                total_distance_m, estimated_time_minutes,
                risk_level, status, planned_at, properties,
                ST_AsText(route_geometry) as route_wkt
            FROM operational_v2.planned_routes_v2
            WHERE task_id = :task_id
        """
        
        params: Dict[str, Any] = {"task_id": str(task_id)}
        
        if status:
            sql_str += " AND status = :status"
            params["status"] = status
        
        sql_str += " ORDER BY planned_at DESC"
        
        result = await self._db.execute(text(sql_str), params)
        rows = result.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    async def list_active_routes(
        self,
        scenario_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None,
        vehicle_id: Optional[UUID] = None,
    ) -> List[PlannedRouteRecord]:
        """
        查询活跃路径列表
        
        Args:
            scenario_id: 场景ID筛选
            team_id: 队伍ID筛选
            vehicle_id: 车辆ID筛选
            
        Returns:
            活跃路径列表
        """
        sql_str = """
            SELECT 
                pr.id, pr.task_id, pr.vehicle_id, pr.team_id,
                pr.total_distance_m, pr.estimated_time_minutes,
                pr.risk_level, pr.status, pr.planned_at, pr.properties,
                ST_AsText(pr.route_geometry) as route_wkt
            FROM operational_v2.planned_routes_v2 pr
        """
        
        conditions = ["pr.status = 'active'"]
        params: Dict[str, Any] = {}
        
        # 如果需要按场景筛选，JOIN task_requirements_v2
        if scenario_id:
            sql_str += " JOIN operational_v2.task_requirements_v2 tr ON pr.task_id = tr.id"
            conditions.append("tr.scenario_id = :scenario_id")
            params["scenario_id"] = str(scenario_id)
        
        if team_id:
            conditions.append("pr.team_id = :team_id")
            params["team_id"] = str(team_id)
        
        if vehicle_id:
            conditions.append("pr.vehicle_id = :vehicle_id")
            params["vehicle_id"] = str(vehicle_id)
        
        sql_str += " WHERE " + " AND ".join(conditions)
        sql_str += " ORDER BY pr.planned_at DESC"
        
        result = await self._db.execute(text(sql_str), params)
        rows = result.fetchall()
        
        return [self._row_to_record(row) for row in rows]
    
    async def update_status(
        self,
        route_id: UUID,
        status: str,
    ) -> bool:
        """更新路径状态"""
        sql = text("""
            UPDATE operational_v2.planned_routes_v2
            SET status = :status
            WHERE id = :route_id
        """)
        
        result = await self._db.execute(sql, {
            "route_id": str(route_id),
            "status": status,
        })
        await self._db.commit()
        
        updated = result.rowcount > 0
        if updated:
            logger.info(f"更新路径状态: id={route_id}, status={status}")
        
        return updated
    
    async def update_risk_level(
        self,
        route_id: UUID,
        risk_level: int,
    ) -> bool:
        """更新路径风险等级"""
        sql = text("""
            UPDATE operational_v2.planned_routes_v2
            SET risk_level = :risk_level
            WHERE id = :route_id
        """)
        
        result = await self._db.execute(sql, {
            "route_id": str(route_id),
            "risk_level": risk_level,
        })
        await self._db.commit()
        
        return result.rowcount > 0
    
    def _row_to_record(self, row: Any) -> PlannedRouteRecord:
        """将数据库行转换为记录对象"""
        polyline = self._parse_linestring_wkt(row.route_wkt) if row.route_wkt else []
        
        return PlannedRouteRecord(
            id=row.id,
            task_id=row.task_id,
            vehicle_id=row.vehicle_id,
            team_id=row.team_id,
            total_distance_m=float(row.total_distance_m or 0),
            estimated_time_minutes=int(row.estimated_time_minutes or 0),
            risk_level=int(row.risk_level or 1),
            status=row.status or "planned",
            planned_at=row.planned_at,
            properties=row.properties or {},
            polyline=polyline,
        )
    
    @staticmethod
    def _parse_linestring_wkt(wkt: str) -> List[Point]:
        """
        解析 WKT LINESTRING 字符串为坐标列表
        
        Args:
            wkt: WKT 格式字符串，如 "LINESTRING(lon1 lat1, lon2 lat2, ...)"
            
        Returns:
            坐标点列表
        """
        if not wkt or not wkt.startswith("LINESTRING"):
            return []
        
        try:
            # 提取坐标部分：LINESTRING(x1 y1, x2 y2, ...)
            coords_str = wkt.replace("LINESTRING(", "").replace(")", "")
            
            points = []
            for point_str in coords_str.split(","):
                parts = point_str.strip().split()
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    points.append(Point(lon=lon, lat=lat))
            
            return points
        except Exception:
            return []
