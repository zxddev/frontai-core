"""
救援队伍位置查询业务服务层

职责: 数据库查询、坐标转换、业务逻辑
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.coord_transform import wgs84_to_gcj02
from src.domains.scenarios.repository import ScenarioRepository
from .schemas import (
    TeamLocationItem,
    TeamLocationListResponse,
    TeamLocationBatchResponse,
)

logger = logging.getLogger(__name__)

# 位置过期阈值：30分钟
LOCATION_STALE_MINUTES = 30


class TeamLocationService:
    """队伍位置查询服务"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_team_locations(
        self,
        scenario_id: Optional[str] = None,
        status: Optional[str] = None,
        team_type: Optional[str] = None,
        convert_to_gcj02: bool = True,
    ) -> TeamLocationListResponse:
        """
        查询队伍位置列表

        优先查询指定场景下的队伍，无场景ID时查询活动场景关联的队伍
        """
        resolved_scenario_id = await self._resolve_scenario_id(scenario_id)
        logger.info(
            f"查询队伍位置列表: scenario_id={resolved_scenario_id}, "
            f"status={status}, team_type={team_type}"
        )

        # 构建查询条件
        where_clauses: List[str] = []
        params: dict = {}

        if resolved_scenario_id:
            # 通过任务分配关联查询场景下的队伍
            where_clauses.append("""
                t.id IN (
                    SELECT DISTINCT ta.assignee_id 
                    FROM operational_v2.task_assignments_v2 ta
                    JOIN operational_v2.tasks_v2 tk ON ta.task_id = tk.id
                    JOIN operational_v2.events_v2 ev ON tk.event_id = ev.id
                    WHERE ev.scenario_id = :scenario_id
                      AND ta.assignee_type = 'team'
                )
            """)
            params["scenario_id"] = resolved_scenario_id

        if status:
            where_clauses.append("t.status = :status")
            params["status"] = status

        if team_type:
            where_clauses.append("t.team_type = :team_type")
            params["team_type"] = team_type

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = text(f"""
            SELECT 
                t.id::text AS team_id,
                t.name,
                t.team_type,
                t.status,
                ST_X(COALESCE(t.current_location, t.base_location)::geometry) AS longitude,
                ST_Y(COALESCE(t.current_location, t.base_location)::geometry) AS latitude,
                t.last_location_update,
                t.current_task_id::text
            FROM operational_v2.rescue_teams_v2 t
            WHERE {where_sql}
            ORDER BY t.name
        """)

        result = await self._db.execute(sql, params)
        rows = result.fetchall()

        items = self._build_location_items(rows, convert_to_gcj02)

        logger.info(f"查询队伍位置完成: 返回 {len(items)} 条记录")
        return TeamLocationListResponse(
            items=items,
            total=len(items),
            scenarioId=resolved_scenario_id,
        )

    async def batch_team_locations(
        self,
        team_ids: List[str],
        convert_to_gcj02: bool = True,
    ) -> TeamLocationBatchResponse:
        """
        批量查询指定队伍的位置
        """
        logger.info(f"批量查询队伍位置: {len(team_ids)} 个队伍")

        if not team_ids:
            return TeamLocationBatchResponse(
                items=[],
                total=0,
                requestedCount=0,
            )

        # 转换为UUID列表
        valid_uuids: List[UUID] = []
        for tid in team_ids:
            try:
                valid_uuids.append(UUID(tid))
            except ValueError:
                logger.warning(f"无效的队伍ID格式: {tid}")
                continue

        if not valid_uuids:
            return TeamLocationBatchResponse(
                items=[],
                total=0,
                requestedCount=len(team_ids),
            )

        sql = text("""
            SELECT 
                t.id::text AS team_id,
                t.name,
                t.team_type,
                t.status,
                ST_X(COALESCE(t.current_location, t.base_location)::geometry) AS longitude,
                ST_Y(COALESCE(t.current_location, t.base_location)::geometry) AS latitude,
                t.last_location_update,
                t.current_task_id::text
            FROM operational_v2.rescue_teams_v2 t
            WHERE t.id = ANY(:team_ids)
            ORDER BY t.name
        """)

        result = await self._db.execute(sql, {"team_ids": valid_uuids})
        rows = result.fetchall()

        items = self._build_location_items(rows, convert_to_gcj02)

        logger.info(f"批量查询队伍位置完成: 请求 {len(team_ids)}, 返回 {len(items)}")
        return TeamLocationBatchResponse(
            items=items,
            total=len(items),
            requestedCount=len(team_ids),
        )

    async def _resolve_scenario_id(self, scenario_id: Optional[str]) -> Optional[str]:
        """
        解析场景ID

        有传入则使用传入值，否则获取活动场景ID
        """
        if scenario_id:
            return scenario_id

        scenario_repo = ScenarioRepository(self._db)
        active_scenario = await scenario_repo.get_active()
        if active_scenario:
            return str(active_scenario.id)
        return None

    def _build_location_items(
        self,
        rows: list,
        convert_to_gcj02: bool,
    ) -> List[TeamLocationItem]:
        """
        将数据库查询结果转换为响应模型

        处理坐标转换和时效性判断
        """
        items: List[TeamLocationItem] = []
        now = datetime.now(timezone.utc)
        stale_threshold = now - timedelta(minutes=LOCATION_STALE_MINUTES)

        for row in rows:
            team_id = row[0]
            name = row[1]
            team_type = row[2]
            status = row[3]
            longitude = row[4]
            latitude = row[5]
            last_update = row[6]
            current_task_id = row[7]

            has_location = longitude is not None and latitude is not None

            # 坐标转换
            final_lon: Optional[float] = None
            final_lat: Optional[float] = None
            if has_location:
                if convert_to_gcj02:
                    final_lon, final_lat = wgs84_to_gcj02(longitude, latitude)
                else:
                    final_lon, final_lat = longitude, latitude

            # 位置时效性判断
            location_stale = False
            last_update_str: Optional[str] = None
            if last_update:
                # 确保时区感知
                if last_update.tzinfo is None:
                    last_update = last_update.replace(tzinfo=timezone.utc)
                last_update_str = last_update.isoformat()
                location_stale = last_update < stale_threshold

            items.append(TeamLocationItem(
                teamId=team_id,
                name=name,
                teamType=team_type,
                status=status,
                longitude=final_lon,
                latitude=final_lat,
                lastLocationUpdate=last_update_str,
                hasLocation=has_location,
                locationStale=location_stale,
                currentTaskId=current_task_id,
            ))

        return items
