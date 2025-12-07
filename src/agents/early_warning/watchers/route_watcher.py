"""
路网状态监控器

监听道路状态变化，检测影响救援队伍的路段阻断。
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.core.database import AsyncSessionLocal
from .base_watcher import BaseWatcher, Alert, AlertLevel

logger = logging.getLogger(__name__)


class RouteWatcher(BaseWatcher):
    """
    路网状态监控器
    
    监控内容：
    1. 道路状态变化（通行 -> 阻断）
    2. 新增危险区域影响已规划路线
    3. 路网损毁事件（地震次生灾害等）
    """
    
    def __init__(self, task_id: str, scenario_id: Optional[str] = None):
        super().__init__(name="RouteWatcher")
        self.task_id = task_id
        self.scenario_id = scenario_id
        self._known_blocked_roads: set = set()
        self._known_danger_zones: set = set()
    
    async def check(self) -> List[Alert]:
        """检查路网状态"""
        alerts = []
        
        try:
            # 1. 检查道路阻断状态
            road_alerts = await self._check_blocked_roads()
            alerts.extend(road_alerts)
            
            # 2. 检查危险区域
            danger_alerts = await self._check_danger_zones()
            alerts.extend(danger_alerts)
            
            # 3. 检查路网损毁事件
            damage_alerts = await self._check_road_damage_events()
            alerts.extend(damage_alerts)
            
        except Exception as e:
            logger.error(f"[RouteWatcher] 检查失败: {e}")
            alerts.append(Alert(
                type="route_watcher_error",
                level=AlertLevel.WARNING,
                title="路网监控异常",
                message=str(e),
                data={"task_id": self.task_id, "error": str(e)},
            ))
        
        return alerts
    
    async def _check_blocked_roads(self) -> List[Alert]:
        """检查道路阻断"""
        alerts = []
        
        async with AsyncSessionLocal() as session:
            # 查询新增的道路阻断（基于 map_entities 或路网状态表）
            result = await session.execute(
                text("""
                    SELECT 
                        me.id::text,
                        me.name,
                        me.entity_type,
                        me.properties->>'block_reason' as block_reason,
                        ST_AsText(me.geometry) as geometry_wkt,
                        me.created_at
                    FROM operational_v2.map_entities_v2 me
                    WHERE me.entity_type IN ('road_block', 'road_damage', 'bridge_collapse')
                      AND me.created_at > :last_check
                      AND (me.scenario_id = :scenario_id OR :scenario_id IS NULL)
                    ORDER BY me.created_at
                """),
                {
                    "last_check": self.last_check_time or datetime(2000, 1, 1),
                    "scenario_id": self.scenario_id,
                }
            )
            rows = result.fetchall()
            
            for row in rows:
                entity_id = row[0]
                if entity_id in self._known_blocked_roads:
                    continue
                
                self._known_blocked_roads.add(entity_id)
                
                # 检查是否影响当前任务的队伍路线
                affected_teams = await self._find_affected_teams(entity_id)
                
                if affected_teams:
                    alerts.append(Alert(
                        type="route_blocked",
                        level=AlertLevel.CRITICAL,
                        title="道路阻断影响救援路线",
                        message=f"路段 {row[1]} 阻断，影响 {len(affected_teams)} 支队伍",
                        data={
                            "task_id": self.task_id,
                            "blocked_road_id": entity_id,
                            "road_name": row[1],
                            "block_type": row[2],
                            "block_reason": row[3],
                            "affected_teams": affected_teams,
                        },
                        recommendation="建议立即为受影响队伍重新规划路线",
                    ))
                else:
                    # 即使不影响当前队伍，也发送信息级别告警
                    alerts.append(Alert(
                        type="route_blocked_info",
                        level=AlertLevel.INFO,
                        title="新增道路阻断",
                        message=f"路段 {row[1]} ({row[2]}) 已阻断",
                        data={
                            "blocked_road_id": entity_id,
                            "road_name": row[1],
                            "block_type": row[2],
                            "block_reason": row[3],
                        },
                    ))
        
        return alerts
    
    async def _check_danger_zones(self) -> List[Alert]:
        """检查危险区域"""
        alerts = []
        
        async with AsyncSessionLocal() as session:
            # 查询新增的危险区域
            result = await session.execute(
                text("""
                    SELECT 
                        me.id::text,
                        me.name,
                        me.properties->>'danger_type' as danger_type,
                        me.properties->>'danger_level' as danger_level,
                        ST_AsText(me.geometry) as geometry_wkt,
                        me.created_at
                    FROM operational_v2.map_entities_v2 me
                    WHERE me.entity_type = 'danger_zone'
                      AND me.created_at > :last_check
                      AND (me.scenario_id = :scenario_id OR :scenario_id IS NULL)
                    ORDER BY me.created_at
                """),
                {
                    "last_check": self.last_check_time or datetime(2000, 1, 1),
                    "scenario_id": self.scenario_id,
                }
            )
            rows = result.fetchall()
            
            for row in rows:
                zone_id = row[0]
                if zone_id in self._known_danger_zones:
                    continue
                
                self._known_danger_zones.add(zone_id)
                
                # 检查是否有队伍在危险区域内或路线经过
                affected_teams = await self._find_teams_in_danger_zone(zone_id)
                
                level = AlertLevel.CRITICAL if row[3] in ("high", "critical") else AlertLevel.WARNING
                
                alerts.append(Alert(
                    type="danger_zone_detected",
                    level=level,
                    title="新增危险区域",
                    message=f"危险区域 {row[1]} ({row[2]}) 已标记，危险等级: {row[3]}",
                    data={
                        "task_id": self.task_id,
                        "danger_zone_id": zone_id,
                        "zone_name": row[1],
                        "danger_type": row[2],
                        "danger_level": row[3],
                        "affected_teams": affected_teams,
                    },
                    recommendation="请确保救援队伍避开该区域" if affected_teams else None,
                ))
        
        return alerts
    
    async def _check_road_damage_events(self) -> List[Alert]:
        """检查路网损毁事件"""
        alerts = []
        
        async with AsyncSessionLocal() as session:
            # 查询道路损毁类型的事件
            result = await session.execute(
                text("""
                    SELECT 
                        e.id::text,
                        e.event_code,
                        e.title,
                        e.event_type,
                        e.priority,
                        ST_X(e.location::geometry) as lon,
                        ST_Y(e.location::geometry) as lat,
                        e.created_at
                    FROM operational_v2.events_v2 e
                    WHERE e.event_type IN ('road_damage', 'bridge_collapse', 'landslide', 'rockfall')
                      AND e.status NOT IN ('resolved', 'cancelled')
                      AND e.created_at > :last_check
                      AND (e.scenario_id = :scenario_id OR :scenario_id IS NULL)
                    ORDER BY e.created_at
                """),
                {
                    "last_check": self.last_check_time or datetime(2000, 1, 1),
                    "scenario_id": self.scenario_id,
                }
            )
            rows = result.fetchall()
            
            for row in rows:
                event_id = row[0]
                
                # 检查事件位置是否影响已规划路线
                affected_teams = await self._find_teams_near_event(
                    lon=row[5], lat=row[6], radius_m=500
                )
                
                if affected_teams:
                    alerts.append(Alert(
                        type="road_damage_event",
                        level=AlertLevel.CRITICAL,
                        title="路网损毁事件",
                        message=f"事件 {row[1]}: {row[2]} 可能影响 {len(affected_teams)} 支队伍路线",
                        data={
                            "task_id": self.task_id,
                            "event_id": event_id,
                            "event_code": row[1],
                            "event_title": row[2],
                            "event_type": row[3],
                            "priority": row[4],
                            "location": {"lon": row[5], "lat": row[6]},
                            "affected_teams": affected_teams,
                        },
                        recommendation="建议检查受影响队伍的路线并考虑绕行",
                    ))
        
        return alerts
    
    async def _find_affected_teams(self, blocked_road_id: str) -> List[Dict[str, Any]]:
        """查找受道路阻断影响的队伍"""
        # 简化实现：查询与任务关联且正在移动的队伍
        # 实际应该检查队伍路线是否经过该路段
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        ms.entity_id::text as team_id,
                        rt.name as team_name,
                        ms.state,
                        ms.traveled_distance_m,
                        ms.total_distance_m
                    FROM operational_v2.movement_sessions ms
                    JOIN operational_v2.rescue_teams_v2 rt ON ms.entity_id = rt.id
                    JOIN operational_v2.task_assignments_v2 ta ON ta.assignee_id = rt.id
                    JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
                    WHERE t.id = :task_id
                      AND ms.state IN ('moving', 'paused')
                    -- TODO: 添加路线与阻断点的空间相交判断
                """),
                {"task_id": self.task_id}
            )
            rows = result.fetchall()
            
            return [
                {
                    "team_id": row[0],
                    "team_name": row[1],
                    "movement_state": row[2],
                    "progress_percent": (row[3] / row[4] * 100) if row[4] else 0,
                }
                for row in rows
            ]
    
    async def _find_teams_in_danger_zone(self, zone_id: str) -> List[Dict[str, Any]]:
        """查找在危险区域内或路线经过的队伍"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        rt.id::text as team_id,
                        rt.name as team_name,
                        ST_X(COALESCE(rt.current_location, rt.base_location)::geometry) as lon,
                        ST_Y(COALESCE(rt.current_location, rt.base_location)::geometry) as lat
                    FROM operational_v2.rescue_teams_v2 rt
                    JOIN operational_v2.task_assignments_v2 ta ON ta.assignee_id = rt.id
                    JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
                    JOIN operational_v2.map_entities_v2 me ON me.id = :zone_id
                    WHERE t.id = :task_id
                      AND ST_Contains(
                          me.geometry::geometry,
                          COALESCE(rt.current_location, rt.base_location)::geometry
                      )
                """),
                {"task_id": self.task_id, "zone_id": zone_id}
            )
            rows = result.fetchall()
            
            return [
                {
                    "team_id": row[0],
                    "team_name": row[1],
                    "current_location": {"lon": row[2], "lat": row[3]},
                }
                for row in rows
            ]
    
    async def _find_teams_near_event(
        self, lon: float, lat: float, radius_m: float
    ) -> List[Dict[str, Any]]:
        """查找事件附近的队伍"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        rt.id::text as team_id,
                        rt.name as team_name,
                        ST_Distance(
                            COALESCE(rt.current_location, rt.base_location),
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                        ) as distance_m
                    FROM operational_v2.rescue_teams_v2 rt
                    JOIN operational_v2.task_assignments_v2 ta ON ta.assignee_id = rt.id
                    JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
                    WHERE t.id = :task_id
                      AND ST_DWithin(
                          COALESCE(rt.current_location, rt.base_location),
                          ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                          :radius_m
                      )
                """),
                {
                    "task_id": self.task_id,
                    "lon": lon,
                    "lat": lat,
                    "radius_m": radius_m,
                }
            )
            rows = result.fetchall()
            
            return [
                {
                    "team_id": row[0],
                    "team_name": row[1],
                    "distance_m": row[2],
                }
                for row in rows
            ]
