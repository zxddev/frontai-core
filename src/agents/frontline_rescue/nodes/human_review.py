"""Human review node for FrontlineRescueAgent.

This node prepares a concise summary of prioritized events and
their allocated teams for commander review. It does not perform
any side effects; actual task dispatch remains a separate step.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.agents.frontline_rescue.state import FrontlineRescueState


logger = logging.getLogger(__name__)


def human_review_node(state: FrontlineRescueState) -> Dict[str, Any]:
    """Prepare review items summarizing the current frontline plan.

    For each prioritized event, we include its priority, score,
    and allocated teams to support human-in-the-loop assessment.
    """

    # 如果前序阶段已失败（例如硬规则否决），不覆盖失败状态
    if state.get("status") == "failed":
        return {}

    events = state.get("prioritized_events") or []
    allocations = state.get("event_allocations") or []
    alloc_by_event: Dict[str, Dict[str, Any]] = {
        str(a.get("event_id")): a for a in allocations if a.get("event_id")
    }

    review_items: List[Dict[str, Any]] = []

    for ev in events:
        ev_id = str(ev.get("id") or "")
        if not ev_id:
            continue

        alloc = alloc_by_event.get(ev_id) or {}
        teams = alloc.get("allocations") or []

        review_items.append(
            {
                "event_id": ev_id,
                "title": ev.get("title"),
                "priority_bucket": ev.get("priority_bucket") or ev.get("priority"),
                "score": ev.get("score"),
                "is_feasible": alloc.get("is_feasible", False),
                "coverage_rate": alloc.get("coverage_rate"),
                "max_eta_minutes": alloc.get("max_eta_minutes"),
                "teams": [
                    {
                        "team_id": t.get("team_id"),
                        "team_name": t.get("team_name"),
                        "eta_minutes": t.get("eta_minutes"),
                        "capabilities": t.get("assigned_capabilities"),
                    }
                    for t in teams
                ],
            }
        )

    logger.info(
        "[Frontline] Prepared human review items for %d events", len(review_items)
    )

    # 标记需要人工审核，但不改变任务执行逻辑
    return {
        "requires_human_review": len(review_items) > 0,
        "human_review_items": review_items,
        "current_phase": "human_review_completed",
        "status": "completed",
    }


__all__ = ["human_review_node"]
