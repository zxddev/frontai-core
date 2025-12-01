"""State definition for Frontline multi-event rescue dispatch.

The FrontlineRescueState is a lightweight LangGraph state used to:
- Load pending frontline events for a scenario
- Score and prioritize events using DB-backed scoring rules
- (Later phases) attach resource allocation and hard-rule check results
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict


class FrontlineEvent(TypedDict, total=False):
    """Single frontline event used as input to the frontline agent."""

    id: str
    scenario_id: str
    event_code: str
    event_type: str
    source_type: str | None
    title: str
    description: str
    address: str | None
    status: str
    priority: str
    estimated_victims: int
    is_time_critical: bool
    golden_hour_deadline: str | None
    reported_at: str | None
    longitude: float | None
    latitude: float | None


class PrioritizedEvent(FrontlineEvent, total=False):
    """Frontline event enriched with scoring results."""

    score: float
    priority_bucket: str
    reasons: list[str]


class AllocatedTeam(TypedDict, total=False):
    """Selected team for a single frontline event."""

    team_id: str
    team_name: str
    resource_type: str
    direct_distance_km: float
    road_distance_km: float
    eta_minutes: float
    match_score: float
    rescue_capacity: int
    assigned_capabilities: list[str]


class EventAllocation(TypedDict, total=False):
    """Allocation summary for a single event."""

    event_id: str
    solution_id: str
    is_feasible: bool
    coverage_rate: float
    max_eta_minutes: float
    total_eta_minutes: float
    resource_count: int
    allocations: list[AllocatedTeam]


class FrontlineRescueState(TypedDict, total=False):
    """State for Frontline multi-event rescue dispatch workflow."""

    # 输入
    scenario_id: str

    # 事件数据
    pending_events: list[FrontlineEvent]
    prioritized_events: list[PrioritizedEvent]

    # 资源分配结果（按事件）
    event_allocations: list[EventAllocation]

    # 硬规则检查结果（Frontline 专用硬规则）
    hard_rule_results: list[dict[str, Any]]

    # 工作流状态
    status: Literal["pending", "running", "completed", "failed"]
    current_phase: str
    errors: list[str]


__all__ = [
    "FrontlineEvent",
    "PrioritizedEvent",
    "AllocatedTeam",
    "EventAllocation",
    "FrontlineRescueState",
]
