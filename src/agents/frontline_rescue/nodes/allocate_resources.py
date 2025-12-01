"""Allocate rescue teams for prioritized frontline events.

This node uses ResourceSchedulingCore and DB-backed allocation
constraints (FRONTLINE_ALLOCATION_CONSTRAINTS_V1) to select
teams for each prioritized event, ensuring that each team is
assigned to at most one event (by using excluded_resource_ids).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Set
from uuid import UUID

from src.agents.frontline_rescue.state import (
    AllocatedTeam,
    EventAllocation,
    FrontlineRescueState,
)
from src.core.database import AsyncSessionLocal
from src.domains.resource_scheduling.core import ResourceSchedulingCore
from src.domains.resource_scheduling.schemas import (
    CapabilityRequirement,
    SchedulingConstraints,
    SchedulingObjectives,
)
from src.domains.resource_scheduling.integrated_core import (
    DisasterContext,
    IntegratedResourceSchedulingCore,
)
from src.infra.config.algorithm_config_service import AlgorithmConfigService


logger = logging.getLogger(__name__)


async def allocate_resources_node(state: FrontlineRescueState) -> Dict[str, Any]:
    """Allocate teams for each prioritized event in order.

    约定：
    - 按优先级得分排序的事件依次调度，先分配的事件优先使用队伍；
    - 每支队伍最多服务一个事件，通过 SchedulingConstraints.excluded_resource_ids 强制互斥；
    - 约束参数全部来自 config.algorithm_parameters(category='allocation', code='FRONTLINE_ALLOCATION_CONSTRAINTS_V1')。
    """

    scenario_id = state.get("scenario_id") or ""
    prioritized = list(state.get("prioritized_events", []))

    if not scenario_id or not prioritized:
        logger.info("[Frontline] No scenario or prioritized events, skip allocation")
        return {
            "event_allocations": [],
            "current_phase": "allocate_resources_skipped",
        }

    logger.info(
        "[Frontline] Allocating resources for %d events, scenario=%s",
        len(prioritized),
        scenario_id,
    )

    errors: List[str] = list(state.get("errors", []))
    event_allocations: List[EventAllocation] = []
    used_team_ids: Set[UUID] = set()

    try:
        scenario_uuid = UUID(scenario_id)
    except (TypeError, ValueError):  # noqa: BLE001
        scenario_uuid = None

    async with AsyncSessionLocal() as session:
        config_service = AlgorithmConfigService(session)

        # 从DB加载约束配置（无则抛异常，交由上层处理）
        params = await config_service.get_or_raise(
            category="allocation",
            code="FRONTLINE_ALLOCATION_CONSTRAINTS_V1",
        )

        base_constraints = SchedulingConstraints(
            max_response_time_minutes=float(params.get("max_response_time_minutes", 180.0)),
            max_resources=int(params.get("max_resources", 20)),
            min_coverage_rate=float(params.get("min_coverage_rate", 0.7)),
            avoid_disaster_areas=True,
        )
        if scenario_uuid is not None:
            base_constraints.scenario_id = scenario_uuid

        objectives = SchedulingObjectives()
        team_scheduler = ResourceSchedulingCore(session)
        integrated_core = IntegratedResourceSchedulingCore(session)

        for ev in prioritized:
            ev_id = str(ev.get("id") or "")
            lon = ev.get("longitude")
            lat = ev.get("latitude")
            if not ev_id or lon is None or lat is None:
                continue

            try:
                event_uuid = UUID(ev_id)
            except (TypeError, ValueError):  # noqa: BLE001
                event_uuid = None

            # 使用整合调度核心的逻辑，从灾情上下文推断能力需求
            context = DisasterContext(
                disaster_type=str(ev.get("event_type", "earthquake")),
                scenario_id=scenario_uuid,
                event_id=event_uuid,
                center_lon=float(lon),
                center_lat=float(lat),
                affected_population=int(ev.get("estimated_victims") or 0),
                trapped_count=0,
                injured_count=0,
                estimated_duration_days=3,
            )

            requirements: List[CapabilityRequirement] = integrated_core._infer_capability_requirements(  # type: ignore[attr-defined]
                context
            )

            if not requirements:
                logger.warning("[Frontline] No capability requirements inferred for event %s", ev_id)
                continue

            constraints = base_constraints.model_copy(deep=True)
            constraints.excluded_resource_ids = set(used_team_ids)

            try:
                result = await team_scheduler.schedule(
                    destination_lon=float(lon),
                    destination_lat=float(lat),
                    requirements=requirements,
                    constraints=constraints,
                    objectives=objectives,
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"allocate_resources(event={ev_id}) failed: {exc}"
                logger.exception("[Frontline] %s", msg)
                errors.append(msg)
                continue

            best = result.best_solution
            if not result.success or best is None:
                errors.extend(result.errors)
                event_allocations.append(
                    EventAllocation(
                        event_id=ev_id,
                        solution_id="",
                        is_feasible=False,
                        coverage_rate=0.0,
                        max_eta_minutes=0.0,
                        total_eta_minutes=0.0,
                        resource_count=0,
                        allocations=[],
                    )
                )
                continue

            teams: List[AllocatedTeam] = []
            for alloc in best.allocations:
                used_team_ids.add(alloc.resource_id)
                teams.append(
                    AllocatedTeam(
                        team_id=str(alloc.resource_id),
                        team_name=alloc.resource_name,
                        resource_type=alloc.resource_type.value,
                        direct_distance_km=alloc.direct_distance_km,
                        road_distance_km=alloc.road_distance_km,
                        eta_minutes=alloc.eta_minutes,
                        match_score=alloc.match_score,
                        rescue_capacity=alloc.rescue_capacity,
                        assigned_capabilities=list(alloc.assigned_capabilities),
                    )
                )

            event_allocations.append(
                EventAllocation(
                    event_id=ev_id,
                    solution_id=best.solution_id,
                    is_feasible=best.is_feasible,
                    coverage_rate=best.coverage_rate,
                    max_eta_minutes=best.max_eta_minutes,
                    total_eta_minutes=best.total_eta_minutes,
                    resource_count=best.resource_count,
                    allocations=teams,
                )
            )

    return {
        "event_allocations": event_allocations,
        "errors": errors,
        "current_phase": "allocate_resources_completed",
    }


__all__ = ["allocate_resources_node"]
