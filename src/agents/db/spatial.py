"""
空间查询仓库

为语音指挥Agent提供PostGIS空间查询和Neo4j关系查询能力。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 默认查询超时（秒）
DEFAULT_QUERY_TIMEOUT = 10.0

# 实体类型到数据库表的映射
ENTITY_TYPE_MAP = {
    "TEAM": "rescue_teams_v2",
    "VEHICLE": "vehicles_v2",
    "DEVICE": "devices_v2",
    "DRONE": "devices_v2",
    "ROBOT_DOG": "devices_v2",
}

# 设备子类型映射
DEVICE_TYPE_MAP = {
    "DRONE": "drone",
    "ROBOT_DOG": "robot_dog",
}


class SpatialRepository:
    """
    空间查询仓库
    
    提供实体位置、最近邻、区域查询等空间操作。
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        Args:
            db: SQLAlchemy异步数据库session
        """
        self._db = db
    
    async def find_by_name_fuzzy(
        self,
        name: str,
        entity_type: Optional[str] = None,
        limit: int = 5,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """
        模糊名称匹配查询实体
        
        支持:
        - 精确匹配 (优先)
        - 模糊匹配（ILIKE）
        - 别名匹配（通过 properties->>'aliases'）
        
        Args:
            name: 实体名称或别名
            entity_type: 可选类型过滤，DRONE/ROBOT_DOG/TEAM/VEHICLE
            limit: 返回数量限制
            timeout: 查询超时时间
            
        Returns:
            匹配的实体列表
        """
        logger.info(f"模糊查询实体: name={name}, type={entity_type}")
        
        results: List[Dict[str, Any]] = []
        search_pattern = f"%{name}%"
        
        # 查询队伍
        if entity_type is None or entity_type == "TEAM":
            teams = await self._query_teams_fuzzy(name, search_pattern, limit, timeout)
            results.extend(teams)
        
        # 查询车辆
        if entity_type is None or entity_type == "VEHICLE":
            vehicles = await self._query_vehicles_fuzzy(name, search_pattern, limit, timeout)
            results.extend(vehicles)
        
        # 查询设备（无人机、机器狗）
        if entity_type is None or entity_type in ("DEVICE", "DRONE", "ROBOT_DOG"):
            device_type = DEVICE_TYPE_MAP.get(entity_type) if entity_type else None
            devices = await self._query_devices_fuzzy(name, search_pattern, device_type, limit, timeout)
            results.extend(devices)
        
        # 按相关度排序：精确匹配优先
        results.sort(key=lambda x: (
            0 if x["name"].lower() == name.lower() else 1,
            x["name"].lower()
        ))
        
        return results[:limit]
    
    async def _query_teams_fuzzy(
        self,
        name: str,
        pattern: str,
        limit: int,
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """查询队伍"""
        sql = """
            SELECT 
                id::text,
                name,
                'TEAM' AS entity_type,
                team_type AS sub_type,
                status,
                ST_X(COALESCE(current_location, base_location)::geometry) AS longitude,
                ST_Y(COALESCE(current_location, base_location)::geometry) AS latitude,
                base_address AS location_desc,
                properties AS metadata,
                available_personnel,
                capability_level
            FROM operational_v2.rescue_teams_v2
            WHERE 
                name ILIKE :pattern
                OR code ILIKE :pattern
                OR properties->>'aliases' ILIKE :pattern
            ORDER BY 
                CASE WHEN name ILIKE :exact_name THEN 0 ELSE 1 END,
                capability_level DESC
            LIMIT :limit
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), {
                    "pattern": pattern,
                    "exact_name": name,
                    "limit": limit,
                }),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"查询队伍失败: {e}")
            return []
    
    async def _query_vehicles_fuzzy(
        self,
        name: str,
        pattern: str,
        limit: int,
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """查询车辆"""
        sql = """
            SELECT 
                v.id::text,
                v.name,
                'VEHICLE' AS entity_type,
                v.vehicle_type::text AS sub_type,
                v.status,
                ST_X(v.current_location::geometry) AS longitude,
                ST_Y(v.current_location::geometry) AS latitude,
                v.code AS location_desc,
                NULL::jsonb AS metadata
            FROM operational_v2.vehicles_v2 v
            WHERE 
                v.name ILIKE :pattern
                OR v.code ILIKE :pattern
            ORDER BY 
                CASE WHEN v.name ILIKE :exact_name THEN 0 ELSE 1 END
            LIMIT :limit
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), {
                    "pattern": pattern,
                    "exact_name": name,
                    "limit": limit,
                }),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"查询车辆失败: {e}")
            return []
    
    async def _query_devices_fuzzy(
        self,
        name: str,
        pattern: str,
        device_type: Optional[str],
        limit: int,
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """查询设备"""
        type_filter = "AND d.device_type::text = :device_type" if device_type else ""
        sql = f"""
            SELECT 
                d.id::text,
                d.name,
                'DEVICE' AS entity_type,
                d.device_type::text AS sub_type,
                COALESCE(d.status, 'unknown') AS status,
                NULL::float AS longitude,
                NULL::float AS latitude,
                NULL AS location_desc,
                NULL::jsonb AS metadata
            FROM operational_v2.devices_v2 d
            WHERE 
                (d.name ILIKE :pattern OR d.code ILIKE :pattern)
                {type_filter}
            ORDER BY 
                CASE WHEN d.name ILIKE :exact_name THEN 0 ELSE 1 END
            LIMIT :limit
        """
        params: Dict[str, Any] = {
            "pattern": pattern,
            "exact_name": name,
            "limit": limit,
        }
        if device_type:
            params["device_type"] = device_type
            
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), params),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"查询设备失败: {e}")
            return []
    
    async def find_nearest_knn(
        self,
        point: Tuple[float, float],
        entity_type: str,
        limit: int = 1,
        status_filter: Optional[str] = None,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """
        KNN最近邻查询
        
        使用PostGIS的 <-> 操作符进行高效的最近邻查询。
        
        Args:
            point: 参考点坐标 (longitude, latitude)
            entity_type: 目标类型，TEAM/VEHICLE/DRONE/ROBOT_DOG
            limit: 返回数量
            status_filter: 可选状态过滤，如"standby"
            timeout: 查询超时
            
        Returns:
            最近的实体列表，包含 distance_meters
        """
        lon, lat = point
        logger.info(f"KNN查询: point={point}, type={entity_type}, limit={limit}")
        
        if entity_type == "TEAM":
            return await self._knn_teams(lon, lat, limit, status_filter, timeout)
        elif entity_type == "VEHICLE":
            return await self._knn_vehicles(lon, lat, limit, status_filter, timeout)
        else:
            logger.warning(f"KNN不支持设备类型: {entity_type}（设备无位置信息）")
            return []
    
    async def _knn_teams(
        self,
        lon: float,
        lat: float,
        limit: int,
        status_filter: Optional[str],
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """KNN查询队伍"""
        status_clause = "AND status = :status" if status_filter else ""
        sql = f"""
            SELECT 
                id::text,
                name,
                'TEAM' AS entity_type,
                team_type AS sub_type,
                status,
                ST_X(COALESCE(current_location, base_location)::geometry) AS longitude,
                ST_Y(COALESCE(current_location, base_location)::geometry) AS latitude,
                base_address AS location_desc,
                available_personnel,
                capability_level,
                ST_Distance(
                    COALESCE(current_location, base_location),
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM operational_v2.rescue_teams_v2
            WHERE 
                COALESCE(current_location, base_location) IS NOT NULL
                {status_clause}
            ORDER BY 
                COALESCE(current_location, base_location) <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT :limit
        """
        params: Dict[str, Any] = {"lon": lon, "lat": lat, "limit": limit}
        if status_filter:
            params["status"] = status_filter
            
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), params),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"KNN查询队伍失败: {e}")
            return []
    
    async def _knn_vehicles(
        self,
        lon: float,
        lat: float,
        limit: int,
        status_filter: Optional[str],
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """KNN查询车辆"""
        status_clause = "AND status = :status" if status_filter else ""
        sql = f"""
            SELECT 
                id::text,
                name,
                'VEHICLE' AS entity_type,
                vehicle_type AS sub_type,
                status,
                ST_X(current_location::geometry) AS longitude,
                ST_Y(current_location::geometry) AS latitude,
                plate_number AS location_desc,
                ST_Distance(
                    current_location,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_meters
            FROM operational_v2.vehicles_v2
            WHERE 
                current_location IS NOT NULL
                {status_clause}
            ORDER BY 
                current_location <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            LIMIT :limit
        """
        params: Dict[str, Any] = {"lon": lon, "lat": lat, "limit": limit}
        if status_filter:
            params["status"] = status_filter
            
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), params),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"KNN查询车辆失败: {e}")
            return []
    
    async def get_units_in_area(
        self,
        area_id: str,
        entity_types: Optional[List[str]] = None,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """
        查询区域内所有单位
        
        Args:
            area_id: 区域ID (想定affected_area或自定义区域)
            entity_types: 要查询的实体类型列表
            timeout: 查询超时
            
        Returns:
            区域内的单位列表
        """
        logger.info(f"查询区域内单位: area_id={area_id}")
        
        results: List[Dict[str, Any]] = []
        types = entity_types or ["TEAM", "VEHICLE"]
        
        # 获取区域几何
        area_sql = """
            SELECT affected_area 
            FROM operational_v2.scenarios_v2 
            WHERE id::text = :area_id
        """
        try:
            area_result = await asyncio.wait_for(
                self._db.execute(text(area_sql), {"area_id": area_id}),
                timeout=timeout,
            )
            area_row = area_result.fetchone()
            if not area_row or not area_row[0]:
                logger.warning(f"未找到区域: {area_id}")
                return []
        except Exception as e:
            logger.error(f"查询区域失败: {e}")
            return []
        
        # 查询队伍
        if "TEAM" in types:
            teams = await self._query_units_in_area_teams(area_id, timeout)
            results.extend(teams)
        
        # 查询车辆
        if "VEHICLE" in types:
            vehicles = await self._query_units_in_area_vehicles(area_id, timeout)
            results.extend(vehicles)
        
        return results
    
    async def _query_units_in_area_teams(
        self,
        area_id: str,
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """查询区域内队伍"""
        sql = """
            SELECT 
                t.id::text,
                t.name,
                'TEAM' AS entity_type,
                t.team_type AS sub_type,
                t.status,
                ST_X(COALESCE(t.current_location, t.base_location)::geometry) AS longitude,
                ST_Y(COALESCE(t.current_location, t.base_location)::geometry) AS latitude
            FROM operational_v2.rescue_teams_v2 t
            JOIN operational_v2.scenarios_v2 s ON s.id::text = :area_id
            WHERE 
                COALESCE(t.current_location, t.base_location) IS NOT NULL
                AND ST_Contains(
                    s.affected_area::geometry,
                    COALESCE(t.current_location, t.base_location)::geometry
                )
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), {"area_id": area_id}),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"查询区域内队伍失败: {e}")
            return []
    
    async def _query_units_in_area_vehicles(
        self,
        area_id: str,
        timeout: float,
    ) -> List[Dict[str, Any]]:
        """查询区域内车辆"""
        sql = """
            SELECT 
                v.id::text,
                v.name,
                'VEHICLE' AS entity_type,
                v.vehicle_type AS sub_type,
                v.status,
                ST_X(v.current_location::geometry) AS longitude,
                ST_Y(v.current_location::geometry) AS latitude
            FROM operational_v2.vehicles_v2 v
            JOIN operational_v2.scenarios_v2 s ON s.id::text = :area_id
            WHERE 
                v.current_location IS NOT NULL
                AND ST_Contains(
                    s.affected_area::geometry,
                    v.current_location::geometry
                )
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), {"area_id": area_id}),
                timeout=timeout,
            )
            return [self._row_to_dict(row, result.keys()) for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"查询区域内车辆失败: {e}")
            return []
    
    async def resolve_location_name(
        self,
        name: str,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> Optional[Tuple[float, float]]:
        """
        地名解析为坐标
        
        将人类可读的地名转换为经纬度坐标。
        支持查询：队伍驻地、想定位置、POI点。
        
        Args:
            name: 地名，如"东门"、"茂县消防大队"、"着火点"
            timeout: 查询超时
            
        Returns:
            坐标 (longitude, latitude)，未找到返回None
        """
        logger.info(f"解析地名: name={name}")
        
        # 1. 查询队伍驻地
        team_sql = """
            SELECT 
                ST_X(base_location::geometry) AS lon,
                ST_Y(base_location::geometry) AS lat
            FROM operational_v2.rescue_teams_v2
            WHERE 
                base_location IS NOT NULL
                AND (name ILIKE :pattern OR base_address ILIKE :pattern)
            LIMIT 1
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(team_sql), {"pattern": f"%{name}%"}),
                timeout=timeout,
            )
            row = result.fetchone()
            if row and row[0] is not None:
                return (row[0], row[1])
        except Exception as e:
            logger.warning(f"查询队伍地址失败: {e}")
        
        # 2. 查询想定位置
        scenario_sql = """
            SELECT 
                ST_X(location::geometry) AS lon,
                ST_Y(location::geometry) AS lat
            FROM operational_v2.scenarios_v2
            WHERE 
                location IS NOT NULL
                AND name ILIKE :pattern
            LIMIT 1
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(scenario_sql), {"pattern": f"%{name}%"}),
                timeout=timeout,
            )
            row = result.fetchone()
            if row and row[0] is not None:
                return (row[0], row[1])
        except Exception as e:
            logger.warning(f"查询想定位置失败: {e}")
        
        return None
    
    async def reverse_geocode(
        self,
        point: Tuple[float, float],
        max_distance_meters: float = 500.0,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> Optional[str]:
        """
        逆地理编码：坐标转位置描述
        
        将坐标转换为人类可读的位置描述。
        查找最近的已知地点（队伍驻地），并计算方位。
        
        Args:
            point: 坐标 (longitude, latitude)
            max_distance_meters: 最大搜索距离
            timeout: 查询超时
            
        Returns:
            位置描述，如"茂县消防大队附近"
        """
        lon, lat = point
        logger.info(f"逆地理编码: point={point}")
        
        sql = """
            SELECT 
                name,
                base_address,
                ST_Distance(
                    base_location,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) AS distance_m
            FROM operational_v2.rescue_teams_v2
            WHERE 
                base_location IS NOT NULL
                AND ST_DWithin(
                    base_location,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :max_dist
                )
            ORDER BY distance_m
            LIMIT 1
        """
        try:
            result = await asyncio.wait_for(
                self._db.execute(text(sql), {
                    "lon": lon,
                    "lat": lat,
                    "max_dist": max_distance_meters,
                }),
                timeout=timeout,
            )
            row = result.fetchone()
            if row:
                name, address, dist = row
                dist_m = int(dist) if dist else 0
                if dist_m < 50:
                    return f"{name}附近"
                else:
                    return f"{name}约{dist_m}米处"
        except Exception as e:
            logger.warning(f"逆地理编码失败: {e}")
        
        return None
    
    def _row_to_dict(self, row: Any, keys: Any) -> Dict[str, Any]:
        """将数据库行转换为字典"""
        return dict(zip(keys, row))


class TeamRelationRepository:
    """
    团队关系仓库
    
    提供Neo4j团队成员关系查询。
    """
    
    def __init__(self, neo4j_driver: Any = None) -> None:
        """
        Args:
            neo4j_driver: Neo4j驱动实例
        """
        self._driver = neo4j_driver
    
    async def get_team_members(
        self,
        team_name: str,
    ) -> List[Dict[str, Any]]:
        """
        获取团队成员
        
        查询团队下所有成员（人员、设备、车辆）。
        
        Args:
            team_name: 团队名称
            
        Returns:
            成员列表，每个包含:
            - id, name, type, role
        """
        logger.info(f"查询团队成员: team={team_name}")
        
        # TODO: Phase 2 实现
        # Cypher: MATCH (t:Team {name: $name})<-[:BELONGS_TO]-(m) RETURN m
        
        return []
    
    async def get_unit_team(
        self,
        unit_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取单位所属团队
        
        Args:
            unit_id: 单位ID
            
        Returns:
            团队信息，包含 id, name
        """
        logger.info(f"查询单位所属团队: unit_id={unit_id}")
        
        # TODO: Phase 2 实现
        # Cypher: MATCH (u {id: $id})-[:BELONGS_TO]->(t:Team) RETURN t
        
        return None
