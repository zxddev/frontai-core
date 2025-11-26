"""
救援队伍数据提供者

为AI Agent提供从数据库查询救援队伍的功能
查询表: operational_v2.rescue_teams_v2 + operational_v2.team_capabilities_v2
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


class TeamDataProvider:
    """
    救援队伍数据提供者
    
    为RescueTeamSelector算法提供队伍数据
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        Args:
            db: SQLAlchemy异步数据库session
        """
        self._db = db
    
    async def get_available_teams(
        self,
        event_location: Optional[Tuple[float, float]] = None,
        disaster_type: Optional[str] = None,
        max_distance_km: float = 100.0,
        min_capability_level: int = 1,
        timeout: float = DEFAULT_QUERY_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """
        查询可用救援队伍
        
        Args:
            event_location: 事件位置 (latitude, longitude)
            disaster_type: 灾害类型（用于筛选适合的队伍类型）
            max_distance_km: 最大距离（公里）
            min_capability_level: 最小能力等级
            timeout: 查询超时时间（秒）
            
        Returns:
            RescueTeamSelector期望的队伍数据列表
            
        Raises:
            asyncio.TimeoutError: 查询超时
        """
        logger.info(f"查询可用队伍: location={event_location}, disaster={disaster_type}, max_dist={max_distance_km}km, timeout={timeout}s")
        
        # 构建SQL查询
        sql = self._build_teams_query(event_location, max_distance_km)
        
        params: Dict[str, Any] = {
            "min_capability_level": min_capability_level,
        }
        
        if event_location:
            params["event_lat"] = event_location[0]
            params["event_lng"] = event_location[1]
            params["max_distance_m"] = max_distance_km * 1000
        
        try:
            # 带超时的查询执行
            result = await asyncio.wait_for(
                self._db.execute(text(sql), params),
                timeout=timeout
            )
            rows = result.fetchall()
            columns = result.keys()
            
            teams = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                team = self._format_team_for_selector(row_dict, event_location)
                teams.append(team)
            
            logger.info(f"查询到{len(teams)}支可用队伍")
            return teams
            
        except asyncio.TimeoutError:
            logger.error(f"查询队伍超时: {timeout}s")
            raise
        except Exception as e:
            logger.error(f"查询队伍失败: {e}")
            raise
    
    def _build_teams_query(
        self,
        event_location: Optional[Tuple[float, float]],
        max_distance_km: float,
    ) -> str:
        """构建队伍查询SQL"""
        
        # 基础查询：队伍信息 + 能力聚合
        if event_location:
            # 有位置信息时，计算距离并排序
            sql = """
                SELECT 
                    t.id,
                    t.code,
                    t.name,
                    t.team_type,
                    ST_Y(t.base_location::geometry) AS base_lat,
                    ST_X(t.base_location::geometry) AS base_lng,
                    t.base_address,
                    t.total_personnel,
                    t.available_personnel,
                    t.capability_level,
                    t.response_time_minutes,
                    t.status,
                    t.properties,
                    COALESCE(
                        ARRAY_AGG(DISTINCT tc.capability_code) 
                        FILTER (WHERE tc.capability_code IS NOT NULL),
                        ARRAY[]::VARCHAR[]
                    ) AS capabilities,
                    ST_Distance(
                        t.base_location,
                        ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
                    ) AS distance_m
                FROM operational_v2.rescue_teams_v2 t
                LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
                WHERE t.status = 'standby'
                  AND t.capability_level >= :min_capability_level
                  AND t.base_location IS NOT NULL
                  AND ST_Distance(
                        t.base_location,
                        ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
                      ) <= :max_distance_m
                GROUP BY t.id
                ORDER BY distance_m ASC, t.capability_level DESC
                LIMIT 50
            """
        else:
            # 无位置信息时，按能力等级排序
            sql = """
                SELECT 
                    t.id,
                    t.code,
                    t.name,
                    t.team_type,
                    ST_Y(t.base_location::geometry) AS base_lat,
                    ST_X(t.base_location::geometry) AS base_lng,
                    t.base_address,
                    t.total_personnel,
                    t.available_personnel,
                    t.capability_level,
                    t.response_time_minutes,
                    t.status,
                    t.properties,
                    COALESCE(
                        ARRAY_AGG(DISTINCT tc.capability_code) 
                        FILTER (WHERE tc.capability_code IS NOT NULL),
                        ARRAY[]::VARCHAR[]
                    ) AS capabilities,
                    0 AS distance_m
                FROM operational_v2.rescue_teams_v2 t
                LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
                WHERE t.status = 'standby'
                  AND t.capability_level >= :min_capability_level
                GROUP BY t.id
                ORDER BY t.capability_level DESC, t.response_time_minutes ASC
                LIMIT 50
            """
        
        return sql
    
    def _format_team_for_selector(
        self,
        row: Dict[str, Any],
        event_location: Optional[Tuple[float, float]],
    ) -> Dict[str, Any]:
        """
        将数据库行格式化为RescueTeamSelector期望的格式
        
        RescueTeamSelector期望格式:
        {
            "id": "team-001",
            "name": "蓝天救援队",
            "type": "rescue_team",
            "capabilities": ["SEARCH_LIFE_DETECT", "RESCUE_STRUCTURAL"],
            "specialty": "earthquake_rescue",
            "location": {"lat": 30.5, "lng": 104.0},
            "personnel": 25,
            "equipment_level": "advanced",
            "status": "available"
        }
        """
        # 队伍类型映射到specialty
        team_type = row.get("team_type", "")
        specialty = self._map_team_type_to_specialty(team_type)
        
        # 能力等级映射到equipment_level
        capability_level = row.get("capability_level", 3)
        equipment_level = self._map_capability_to_equipment_level(capability_level)
        
        # 位置信息
        base_lat = row.get("base_lat")
        base_lng = row.get("base_lng")
        location = {"lat": base_lat, "lng": base_lng} if base_lat and base_lng else {"lat": 0, "lng": 0}
        
        # 能力列表
        capabilities = row.get("capabilities") or []
        if isinstance(capabilities, str):
            capabilities = [capabilities]
        
        return {
            "id": str(row.get("id", "")),
            "name": row.get("name", ""),
            "type": self._normalize_team_type(team_type),
            "capabilities": list(capabilities),
            "specialty": specialty,
            "location": location,
            "personnel": row.get("available_personnel") or row.get("total_personnel") or 10,
            "equipment_level": equipment_level,
            "status": "available",  # 查询条件已过滤为standby
            # 额外字段供后续使用
            "code": row.get("code"),
            "base_address": row.get("base_address"),
            "response_time_minutes": row.get("response_time_minutes") or 30,
            "distance_m": row.get("distance_m", 0),
        }
    
    def _map_team_type_to_specialty(self, team_type: str) -> str:
        """队伍类型映射到专业领域"""
        mapping = {
            "fire_rescue": "firefighting",
            "medical": "emergency_medical",
            "search_rescue": "search_rescue",
            "hazmat": "hazmat",
            "engineering": "building_collapse",
            "communication": "communication",
            "logistics": "logistics",
            "water_rescue": "water_rescue",
            "mountain_rescue": "mountain_rescue",
            "mine_rescue": "mine_rescue",
            "armed_police": "general",
            "volunteer": "general",
        }
        return mapping.get(team_type, "general")
    
    def _normalize_team_type(self, team_type: str) -> str:
        """标准化队伍类型名称"""
        mapping = {
            "fire_rescue": "fire_team",
            "medical": "medical_team",
            "search_rescue": "rescue_team",
            "hazmat": "hazmat_team",
            "engineering": "engineering_team",
            "communication": "support_team",
            "logistics": "support_team",
            "water_rescue": "water_rescue_team",
            "mountain_rescue": "rescue_team",
            "mine_rescue": "rescue_team",
            "armed_police": "armed_team",
            "volunteer": "volunteer_team",
        }
        return mapping.get(team_type, "rescue_team")
    
    def _map_capability_to_equipment_level(self, level: int) -> str:
        """能力等级映射到装备等级"""
        if level >= 5:
            return "advanced"
        elif level >= 3:
            return "standard"
        else:
            return "basic"
