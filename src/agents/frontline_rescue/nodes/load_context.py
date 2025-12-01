"""Load context for Frontline multi-event rescue dispatch.

This node loads all pending frontline events for a given scenario
from the operational_v2.events_v2 table:
- status = 'confirmed'
- no associated task in tasks_v2
- exclude main earthquake event_type
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.frontline_rescue.state import FrontlineEvent, FrontlineRescueState
from src.core.database import AsyncSessionLocal


logger = logging.getLogger(__name__)


class FrontlineContextError(Exception):
    """Raised when frontline context loading fails."""


async def load_context_node(state: FrontlineRescueState) -> dict[str, Any]:
    """Load pending frontline events for the given scenario.

    Business rules:
    - Only events with status = 'confirmed'
    - Exclude main earthquake entries (event_type != 'earthquake')
    - Exclude events that already have tasks in tasks_v2
    """

    scenario_id = state.get("scenario_id")
    if not scenario_id:
        raise FrontlineContextError("scenario_id is required for frontline dispatch")

    logger.info("[Frontline] Loading pending events for scenario %s", scenario_id)

    try:
        async with AsyncSessionLocal() as session:
            events = await _load_pending_events(session, scenario_id)

        logger.info("[Frontline] Loaded %d pending events", len(events))

        return {
            "scenario_id": scenario_id,
            "pending_events": events,
            "status": "running",
            "current_phase": "load_context_completed",
            "errors": [],
        }
    except FrontlineContextError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Frontline] Failed to load context for scenario %s", scenario_id)
        raise FrontlineContextError(f"Failed to load frontline context: {exc}") from exc


async def _load_pending_events(session: AsyncSession, scenario_id: str) -> list[FrontlineEvent]:
    """Query all confirmed events without assigned tasks for a scenario."""

    try:
        scenario_uuid = UUID(scenario_id)
    except ValueError as exc:  # noqa: BLE001
        raise FrontlineContextError(f"Invalid scenario_id format: {scenario_id}") from exc

    sql = text(
        """
        SELECT 
            e.id,
            e.scenario_id,
            e.event_code,
            e.event_type,
            e.source_type,
            e.title,
            e.description,
            e.address,
            e.status,
            e.priority,
            e.estimated_victims,
            e.is_time_critical,
            e.golden_hour_deadline,
            e.reported_at,
            ST_X(e.location::geometry) AS lon,
            ST_Y(e.location::geometry) AS lat
        FROM operational_v2.events_v2 e
        LEFT JOIN operational_v2.tasks_v2 t
            ON t.event_id = e.id
        WHERE e.status = 'confirmed'
          AND e.event_type != 'earthquake'
          AND t.id IS NULL
          AND e.scenario_id = :scenario_id
        ORDER BY 
            CASE e.priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
            END,
            e.reported_at ASC
        """
    )

    result = await session.execute(sql, {"scenario_id": scenario_uuid})
    rows = result.fetchall()

    events: list[FrontlineEvent] = []
    for row in rows:
        events.append(
            FrontlineEvent(
                id=str(row.id),
                scenario_id=str(row.scenario_id),
                event_code=row.event_code,
                event_type=row.event_type,
                source_type=row.source_type,
                title=row.title,
                description=row.description or "",
                address=row.address,
                status=row.status,
                priority=row.priority,
                estimated_victims=row.estimated_victims or 0,
                is_time_critical=bool(row.is_time_critical),
                golden_hour_deadline=row.golden_hour_deadline.isoformat()
                if row.golden_hour_deadline
                else None,
                reported_at=row.reported_at.isoformat() if row.reported_at else None,
                longitude=float(row.lon) if row.lon is not None else None,
                latitude=float(row.lat) if row.lat is not None else None,
            )
        )

    return events


__all__ = ["load_context_node"]
