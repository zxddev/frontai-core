"""Load Context Node - 从数据库加载想定和资源数据

从scenarios_v2、events_v2、disaster_situations、rescue_teams_v2、
supply_inventory_v2等表加载数据，作为总体救灾方案生成的输入上下文。

业务模型层次:
  scenarios_v2 (想定) - 顶层容器，代表一次完整的救灾行动
  └── events_v2 (事件) - 想定下的次生灾害和救援任务
  └── disaster_situations - 灾情态势
  └── rescue_teams_v2 - 可用救援队伍
  └── supply_inventory_v2 - 可用物资
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.overall_plan.state import OverallPlanState
from src.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


class ContextLoadError(Exception):
    """上下文加载失败异常"""

    pass


async def load_context_node(state: OverallPlanState) -> dict[str, Any]:
    """从数据库加载想定上下文数据

    数据来源（按想定scenario_id加载）:
    - scenarios_v2: 想定基本信息
    - events_v2: 想定下的事件列表
    - disaster_situations: 灾情态势
    - rescue_teams_v2: 可用救援队伍
    - supply_inventory_v2 + supplies_v2: 可用物资
    - command_group_templates_v2: 工作组配置模板

    Args:
        state: 当前工作流状态，包含scenario_id或event_id

    Returns:
        包含加载数据的状态更新字典

    Raises:
        ContextLoadError: 必要数据加载失败时抛出
    """
    scenario_id = state.get("scenario_id")
    event_id = state.get("event_id")
    
    # 优先使用scenario_id，若无则从event_id反查
    if not scenario_id and not event_id:
        raise ContextLoadError("scenario_id or event_id is required")

    logger.info(f"Loading context for scenario={scenario_id}, event={event_id}")

    try:
        async with AsyncSessionLocal() as session:
            # 如果只有event_id，先查出scenario_id
            if not scenario_id and event_id:
                scenario_id = await _get_scenario_from_event(session, event_id)
                if not scenario_id:
                    raise ContextLoadError(f"Cannot find scenario for event: {event_id}")

            # 加载想定基本信息
            scenario_data = await _load_scenario_data(session, scenario_id)
            if not scenario_data:
                raise ContextLoadError(f"Scenario not found: {scenario_id}")

            # 加载想定下的所有事件
            events_data = await _load_events_for_scenario(session, scenario_id)

            # 加载灾情态势
            disaster_situations = await _load_disaster_situations(session, scenario_id)

            # 加载可用救援队伍
            available_teams = await _load_available_teams(session, scenario_id)

            # 加载可用物资
            available_supplies = await _load_available_supplies(session, scenario_id)

            # 加载工作组配置模板
            command_groups = await _load_command_groups(
                session, 
                disaster_type=scenario_data.get("scenario_type", "earthquake"),
                response_level=scenario_data.get("response_level", "II")
            )

        logger.info(
            f"Context loaded: scenario={scenario_data.get('name')}, "
            f"events={len(events_data)}, situations={len(disaster_situations)}, "
            f"teams={len(available_teams)}, supplies={len(available_supplies)}, "
            f"command_groups={len(command_groups)}"
        )

        return {
            "scenario_id": scenario_id,
            "scenario_data": scenario_data,
            "events_data": events_data,
            "disaster_situations": disaster_situations,
            "available_teams": available_teams,
            "available_supplies": available_supplies,
            "command_groups": command_groups,
            # 兼容旧字段
            "event_data": events_data[0] if events_data else None,
            "available_resources": available_teams,
            "status": "running",
            "current_phase": "load_context_completed",
            "errors": [],
        }

    except ContextLoadError:
        raise
    except Exception as e:
        logger.exception(f"Failed to load context for scenario {scenario_id}")
        raise ContextLoadError(f"Failed to load context: {e}") from e


async def _get_scenario_from_event(session: AsyncSession, event_id: str) -> str | None:
    """从event_id反查scenario_id

    Args:
        session: 数据库会话
        event_id: 事件ID

    Returns:
        想定ID字符串，未找到返回None
    """
    try:
        event_uuid = UUID(event_id)
    except ValueError:
        logger.error(f"Invalid event_id format: {event_id}")
        return None

    result = await session.execute(
        text("SELECT scenario_id FROM operational_v2.events_v2 WHERE id = :event_id"),
        {"event_id": event_uuid}
    )
    row = result.fetchone()
    
    if row and row[0]:
        return str(row[0])
    return None


async def _load_scenario_data(session: AsyncSession, scenario_id: str) -> dict[str, Any] | None:
    """从scenarios_v2表加载想定数据

    Args:
        session: 数据库会话
        scenario_id: 想定ID

    Returns:
        想定数据字典，未找到返回None
    """
    try:
        scenario_uuid = UUID(scenario_id)
    except ValueError:
        logger.error(f"Invalid scenario_id format: {scenario_id}")
        return None

    result = await session.execute(
        text("""
            SELECT id, name, scenario_type, response_level, status,
                   ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat,
                   started_at, ended_at, parameters,
                   affected_population, affected_area_km2, created_by, created_at
            FROM operational_v2.scenarios_v2
            WHERE id = :scenario_id
        """),
        {"scenario_id": scenario_uuid}
    )
    row = result.fetchone()

    if not row:
        logger.warning(f"Scenario not found: {scenario_id}")
        return None

    parameters = row[9] or {}
    
    return {
        "id": str(row[0]),
        "name": row[1],
        "scenario_type": row[2],
        "response_level": row[3],
        "status": row[4],
        "location": {"longitude": row[5], "latitude": row[6]} if row[5] else None,
        "started_at": row[7].isoformat() if row[7] else None,
        "ended_at": row[8].isoformat() if row[8] else None,
        "affected_population": row[10] or 0,
        "affected_area_km2": float(row[11]) if row[11] else 0,
        # 从parameters提取地震相关信息
        "magnitude": parameters.get("magnitude"),
        "depth_km": parameters.get("depth_km"),
        "intensity_max": parameters.get("intensity_max"),
        "aftershock_count": parameters.get("aftershock_count"),
        "parameters": parameters,
    }


async def _load_events_for_scenario(session: AsyncSession, scenario_id: str) -> list[dict[str, Any]]:
    """从events_v2加载想定下的所有事件

    Args:
        session: 数据库会话
        scenario_id: 想定ID

    Returns:
        事件列表
    """
    try:
        scenario_uuid = UUID(scenario_id)
    except ValueError:
        return []

    result = await session.execute(
        text("""
            SELECT id, event_code, event_type, source_type, source_detail,
                   title, description, address, priority, status,
                   estimated_victims, casualty_count, reported_at,
                   ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat
            FROM operational_v2.events_v2
            WHERE scenario_id = :scenario_id
            ORDER BY reported_at, event_code
        """),
        {"scenario_id": scenario_uuid}
    )
    rows = result.fetchall()

    events = []
    for row in rows:
        source_detail = row[4] or {}
        events.append({
            "id": str(row[0]),
            "event_code": row[1],
            "event_type": row[2],
            "source_type": row[3],
            "title": row[5],
            "description": row[6],
            "address": row[7],
            "priority": row[8],
            "status": row[9],
            "trapped": row[10] or 0,
            "casualties": row[11] or 0,
            "reported_at": row[12].isoformat() if row[12] else None,
            "location": {"longitude": row[13], "latitude": row[14]} if row[13] else None,
            # 从source_detail扩展字段
            "injuries": source_detail.get("injuries", 0),
            "missing": source_detail.get("missing", 0),
            "buildings_collapsed": source_detail.get("buildings_collapsed", 0),
            "buildings_damaged": source_detail.get("buildings_damaged", 0),
        })

    logger.info(f"Loaded {len(events)} events for scenario {scenario_id}")
    return events


async def _load_disaster_situations(session: AsyncSession, scenario_id: str) -> list[dict[str, Any]]:
    """从disaster_situations加载灾情态势

    Args:
        session: 数据库会话
        scenario_id: 想定ID

    Returns:
        灾情态势列表
    """
    try:
        scenario_uuid = UUID(scenario_id)
    except ValueError:
        return []

    result = await session.execute(
        text("""
            SELECT id, disaster_type, disaster_name, severity_level,
                   spread_direction, spread_speed_mps, buffer_distance_m,
                   ST_X(center_point::geometry) as lon, ST_Y(center_point::geometry) as lat
            FROM operational_v2.disaster_situations
            WHERE scenario_id = :scenario_id
        """),
        {"scenario_id": scenario_uuid}
    )
    rows = result.fetchall()

    situations = []
    for row in rows:
        situations.append({
            "id": str(row[0]),
            "disaster_type": row[1],
            "disaster_name": row[2],
            "severity_level": row[3],
            "spread_direction": row[4],
            "spread_speed_mps": float(row[5]) if row[5] else None,
            "buffer_distance_m": float(row[6]) if row[6] else None,
            "center_point": {"longitude": row[7], "latitude": row[8]} if row[7] else None,
        })

    logger.info(f"Loaded {len(situations)} disaster situations for scenario {scenario_id}")
    return situations


async def _load_available_teams(session: AsyncSession, scenario_id: str) -> list[dict[str, Any]]:
    """从rescue_teams_v2加载可用救援队伍

    优先加载该想定关联的队伍，若无则加载所有可用队伍

    Args:
        session: 数据库会话
        scenario_id: 想定ID

    Returns:
        可用队伍列表
    """
    # 查询所有可用（待命或可调度）的队伍
    result = await session.execute(
        text("""
            SELECT id, code, name, team_type, parent_org,
                   contact_person, contact_phone, base_address,
                   total_personnel, available_personnel,
                   capability_level, response_time_minutes, status
            FROM operational_v2.rescue_teams_v2
            WHERE status IN ('standby', 'available', 'active')
            ORDER BY team_type, name
        """)
    )
    rows = result.fetchall()

    teams = []
    for row in rows:
        teams.append({
            "id": str(row[0]),
            "code": row[1],
            "name": row[2],
            "team_type": row[3],
            "parent_org": row[4],
            "contact_person": row[5],
            "contact_phone": row[6],
            "base_address": row[7],
            "total_personnel": row[8] or 0,
            "available_personnel": row[9] or 0,
            "capability_level": row[10],
            "response_time_minutes": row[11],
            "status": row[12],
        })

    logger.info(f"Loaded {len(teams)} available rescue teams")
    return teams


async def _load_available_supplies(session: AsyncSession, scenario_id: str) -> list[dict[str, Any]]:
    """从supply_inventory_v2和supplies_v2加载可用物资

    Args:
        session: 数据库会话
        scenario_id: 想定ID

    Returns:
        可用物资列表（按类别汇总）
    """
    result = await session.execute(
        text("""
            SELECT s.id, s.code, s.name, s.category, s.sphere_category,
                   s.unit, s.weight_kg, s.is_consumable,
                   COALESCE(SUM(si.quantity - si.reserved_quantity), 0) as available_quantity
            FROM operational_v2.supplies_v2 s
            LEFT JOIN operational_v2.supply_inventory_v2 si ON s.id = si.supply_id
            GROUP BY s.id, s.code, s.name, s.category, s.sphere_category, 
                     s.unit, s.weight_kg, s.is_consumable
            HAVING COALESCE(SUM(si.quantity - si.reserved_quantity), 0) > 0
            ORDER BY s.category, s.name
        """)
    )
    rows = result.fetchall()

    supplies = []
    for row in rows:
        supplies.append({
            "id": str(row[0]),
            "code": row[1],
            "name": row[2],
            "category": row[3],
            "sphere_category": row[4],
            "unit": row[5],
            "weight_kg": float(row[6]) if row[6] else None,
            "is_consumable": row[7],
            "available_quantity": int(row[8]),
        })

    logger.info(f"Loaded {len(supplies)} available supplies")
    return supplies


async def _load_command_groups(
    session: AsyncSession, 
    disaster_type: str, 
    response_level: str
) -> list[dict[str, Any]]:
    """从command_group_templates_v2加载工作组配置

    优先匹配具体灾害类型和响应级别，若无则使用通用配置

    Args:
        session: 数据库会话
        disaster_type: 灾害类型（如earthquake）
        response_level: 响应级别（如I、II）

    Returns:
        工作组配置列表
    """
    # 查询匹配的工作组配置
    result = await session.execute(
        text("""
            SELECT group_code, group_name, lead_department, 
                   participating_units, responsibilities, sort_order, reference
            FROM config_v2.command_group_templates_v2
            WHERE is_active = TRUE
              AND (disaster_type = :disaster_type OR disaster_type = 'all')
              AND (response_level = :response_level OR response_level = 'all')
              AND region_code IS NULL
            ORDER BY sort_order
        """),
        {"disaster_type": disaster_type, "response_level": response_level}
    )
    rows = result.fetchall()

    groups = []
    for row in rows:
        groups.append({
            "group_code": row[0],
            "group_name": row[1],
            "lead_department": row[2],
            "participating_units": row[3] if isinstance(row[3], list) else [],
            "responsibilities": row[4],
            "sort_order": row[5],
            "reference": row[6],
        })

    logger.info(f"Loaded {len(groups)} command groups for {disaster_type}/{response_level}")
    return groups
