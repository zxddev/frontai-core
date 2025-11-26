"""
数据库适配器 - 将V2表数据转换为算法模块所需的格式

V2表结构完全支持现有全地形A*算法进行任务派遣和路径规划，
本模块提供数据格式转换功能。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from ..algorithms.routing.types import CapabilityMetrics, Obstacle, Point


@dataclass
class TeamProfile:
    """救援队伍档案"""
    id: UUID
    code: str
    name: str
    team_type: str
    capabilities: List[str]
    base_location: Optional[Point]
    total_personnel: int
    available_personnel: int
    capability_level: str
    response_time_minutes: int
    status: str


@dataclass
class VehicleProfile:
    """车辆档案"""
    id: UUID
    code: str
    name: str
    vehicle_type: str
    current_location: Optional[Point]
    capability: CapabilityMetrics
    status: str
    max_weight_kg: int
    max_volume_m3: float
    current_weight_kg: float
    current_volume_m3: float


@dataclass
class TaskRequirement:
    """任务需求"""
    id: UUID
    task_type: str
    priority: str
    location: Optional[Point]
    required_capabilities: List[str]
    required_vehicle_capabilities: List[str]
    min_personnel: int
    deadline_at: Optional[datetime]
    disaster_features: Dict[str, Any]


class DatabaseAdapter:
    """
    数据库适配器
    
    将operational_v2 schema的表数据转换为算法模块所需的数据格式。
    """
    
    def __init__(self, conn):
        """
        Args:
            conn: psycopg2/asyncpg数据库连接
        """
        self._conn = conn
    
    @staticmethod
    def gradient_percent_to_slope_deg(percent: float) -> float:
        """坡度百分比转角度: 60% → 30.96°"""
        if percent is None or percent <= 0:
            return 0.0
        return math.atan(percent / 100.0) * 180.0 / math.pi
    
    @staticmethod
    def slope_deg_to_gradient_percent(deg: float) -> float:
        """坡度角度转百分比"""
        if deg is None or deg <= 0:
            return 0.0
        return math.tan(deg * math.pi / 180.0) * 100.0
    
    @staticmethod
    def vehicle_row_to_capability(row: Dict[str, Any]) -> CapabilityMetrics:
        """将vehicles_v2表行数据转换为CapabilityMetrics"""
        slope_deg = DatabaseAdapter.gradient_percent_to_slope_deg(
            row.get('max_gradient_percent') or 0
        )
        terrain_caps = row.get('terrain_capabilities') or []
        if isinstance(terrain_caps, str):
            terrain_caps = [terrain_caps]
        
        return CapabilityMetrics(
            width_m=float(row.get('width_m') or 0),
            height_m=float(row.get('height_m') or 0),
            weight_kg=float(row.get('self_weight_kg') or 0),
            turn_radius_m=float(row.get('min_turning_radius_m') or 0),
            slope_deg=slope_deg,
            wading_depth_m=float(row.get('max_wading_depth_m') or 0),
            range_km=float(row.get('range_km') or 0),
            payload_kg=float(row.get('max_weight_kg') or 0),
            skills=list(terrain_caps),
        )
    
    @staticmethod
    def disaster_area_to_obstacle(row: Dict[str, Any]) -> Obstacle:
        """将disaster_affected_areas_v2表行转换为Obstacle"""
        geometry = row.get('geometry')
        if isinstance(geometry, str):
            geometry = json.loads(geometry)
        
        severity = row.get('severity') or 'medium'
        is_hard = severity in ('critical', 'severe')
        
        return Obstacle(
            id=str(row.get('id') or row.get('code') or 'unknown'),
            type=row.get('disaster_type') or row.get('area_type') or 'unknown',
            hard=is_hard,
            geometry=geometry or {},
            severity=severity,
            source=row.get('source'),
            confidence=row.get('confidence'),
            metadata={
                'name': row.get('name'),
                'description': row.get('description'),
                'affected_level': row.get('affected_level'),
            }
        )
    
    @staticmethod
    def geography_to_point(geog: Any) -> Optional[Point]:
        """将PostGIS GEOGRAPHY类型转换为Point"""
        if geog is None:
            return None
        
        if isinstance(geog, str):
            if geog.startswith('POINT'):
                import re
                match = re.match(r'POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)', geog)
                if match:
                    lon, lat = float(match.group(1)), float(match.group(2))
                    return Point(lon=lon, lat=lat)
            return None
        
        if hasattr(geog, 'coords'):
            coords = list(geog.coords)
            if coords:
                return Point(lon=coords[0][0], lat=coords[0][1])
        
        return None
    
    @staticmethod
    def point_to_wkt(point: Point) -> str:
        """将Point转换为WKT格式"""
        return f"POINT({point.lon} {point.lat})"
    
    def get_available_teams(self, scenario_id: Optional[UUID] = None) -> List[TeamProfile]:
        """获取可用救援队伍"""
        sql = """
            SELECT 
                t.id, t.code, t.name, t.team_type,
                ST_AsText(t.base_location) AS base_location_wkt,
                t.total_personnel, t.available_personnel,
                t.capability_level, t.response_time_minutes, t.status,
                ARRAY_AGG(DISTINCT tc.capability_code) FILTER (WHERE tc.capability_code IS NOT NULL) AS capabilities
            FROM operational_v2.rescue_teams_v2 t
            LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
            WHERE t.status = 'available'
            GROUP BY t.id
            ORDER BY t.capability_level DESC, t.response_time_minutes ASC
        """
        cursor = self._conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        teams = []
        for row in rows:
            data = dict(zip(columns, row))
            base_loc = self.geography_to_point(data.get('base_location_wkt'))
            teams.append(TeamProfile(
                id=data['id'], code=data['code'], name=data['name'],
                team_type=data['team_type'], capabilities=data.get('capabilities') or [],
                base_location=base_loc, total_personnel=data['total_personnel'],
                available_personnel=data['available_personnel'],
                capability_level=data['capability_level'],
                response_time_minutes=data['response_time_minutes'],
                status=data['status'],
            ))
        return teams
    
    def get_available_vehicles(self, team_id: Optional[UUID] = None) -> List[VehicleProfile]:
        """获取可用车辆"""
        sql = """
            SELECT v.*, ST_AsText(COALESCE(v.current_location, t.base_location)) AS effective_location_wkt
            FROM operational_v2.vehicles_v2 v
            LEFT JOIN operational_v2.team_equipment_v2 te ON te.equipment_id = v.id AND te.equipment_type = 'vehicle'
            LEFT JOIN operational_v2.rescue_teams_v2 t ON t.id = te.team_id
            WHERE v.status = 'available'
        """
        params = []
        if team_id:
            sql += " AND te.team_id = %s"
            params.append(team_id)
        
        cursor = self._conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        vehicles = []
        for row in rows:
            data = dict(zip(columns, row))
            current_loc = self.geography_to_point(data.get('effective_location_wkt'))
            vehicles.append(VehicleProfile(
                id=data['id'], code=data['code'], name=data['name'],
                vehicle_type=data['vehicle_type'], current_location=current_loc,
                capability=self.vehicle_row_to_capability(data),
                status=data['status'], max_weight_kg=data['max_weight_kg'],
                max_volume_m3=float(data.get('max_volume_m3') or 0),
                current_weight_kg=float(data.get('current_weight_kg') or 0),
                current_volume_m3=float(data.get('current_volume_m3') or 0),
            ))
        return vehicles
    
    def get_disaster_obstacles(self, scenario_id: UUID) -> List[Obstacle]:
        """获取灾害影响区域作为障碍物"""
        sql = """
            SELECT id, code, name, disaster_type, severity,
                ST_AsGeoJSON(geometry)::json AS geometry,
                affected_level, source, confidence, description
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = %s AND is_active = true
            ORDER BY severity DESC
        """
        cursor = self._conn.cursor()
        cursor.execute(sql, [scenario_id])
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        return [self.disaster_area_to_obstacle(dict(zip(columns, row))) for row in rows]
    
    def save_planned_route(self, task_id: UUID, vehicle_id: UUID, route_points: List[Point],
                           distance_m: float, duration_s: float, route_type: str = 'primary',
                           metadata: Optional[Dict] = None) -> UUID:
        """保存规划路径到planned_routes_v2表"""
        linestring_wkt = "LINESTRING(" + ",".join(f"{p.lon} {p.lat}" for p in route_points) + ")"
        sql = """
            INSERT INTO operational_v2.planned_routes_v2 
            (task_id, vehicle_id, route_geometry, distance_m, estimated_duration_s, 
             route_type, waypoints_count, properties)
            VALUES (%s, %s, ST_GeomFromText(%s, 4326)::geography, %s, %s, %s, %s, %s)
            RETURNING id
        """
        cursor = self._conn.cursor()
        cursor.execute(sql, [task_id, vehicle_id, linestring_wkt, distance_m, duration_s,
                            route_type, len(route_points), json.dumps(metadata or {})])
        route_id = cursor.fetchone()[0]
        self._conn.commit()
        return route_id
    
    def update_vehicle_location(self, vehicle_id: UUID, location: Point) -> None:
        """更新车辆实时位置"""
        sql = """
            UPDATE operational_v2.vehicles_v2
            SET current_location = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                last_location_update = now()
            WHERE id = %s
        """
        cursor = self._conn.cursor()
        cursor.execute(sql, [location.lon, location.lat, vehicle_id])
        self._conn.commit()
