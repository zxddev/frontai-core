"""Prioritize frontline events using DB-backed scoring rules.

This node uses AlgorithmConfigService + PriorityScoringEngine
with the SCORING_FRONTLINE_EVENT_V1 rule stored in
config.algorithm_parameters.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.agents.frontline_rescue.state import FrontlineEvent, FrontlineRescueState, PrioritizedEvent
from src.agents.shared.priority_scoring import (
    EntityType,
    PriorityScoringEngine,
    ScoringContext,
)
from src.infra.config.algorithm_config_service import AlgorithmConfigService
from src.core.database import AsyncSessionLocal


logger = logging.getLogger(__name__)

RULE_CODE_FRONTLINE_EVENT = "SCORING_FRONTLINE_EVENT_V1"


def _priority_to_life_threat(priority: str) -> float:
    mapping = {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.5,
        "low": 0.3,
    }
    return mapping.get(priority, 0.5)


def _compute_time_urgency(
    event: FrontlineEvent,
    now: datetime,
) -> tuple[float, float]:
    """Compute time_urgency_score and golden_time_remaining_min.

    约定：
    - golden_hour_deadline 存在时，以剩余时间为核心；
    - 否则根据 is_time_critical 粗略赋值。
    """

    golden_deadline = event.get("golden_hour_deadline")
    is_time_critical = bool(event.get("is_time_critical"))

    remaining_min = 240.0
    score = 0.5

    if golden_deadline:
        try:
            deadline_dt = datetime.fromisoformat(golden_deadline)
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)
        except Exception:  # noqa: BLE001
            deadline_dt = None

        if deadline_dt is not None:
            delta = (deadline_dt - now).total_seconds() / 60.0
            remaining_min = max(delta, 0.0)

            if remaining_min <= 0:
                score = 1.0
            elif remaining_min <= 60:
                score = 0.9
            elif remaining_min <= 120:
                score = 0.7
            elif remaining_min <= 240:
                score = 0.5
            else:
                score = 0.3
    else:
        remaining_min = 240.0
        score = 0.8 if is_time_critical else 0.4

    return score, remaining_min


def _estimate_success_probability(event: FrontlineEvent) -> float:
    """粗略估计救援成功概率。

    目前采用简单启发式：优先级越高、预计受灾人数越少，成功概率越高。
    后续可以接入更精细的评估模型。
    """

    base = {
        "critical": 0.7,
        "high": 0.75,
        "medium": 0.8,
        "low": 0.85,
    }.get(event.get("priority", "medium"), 0.8)

    victims = int(event.get("estimated_victims") or 0)
    if victims > 200:
        base -= 0.15
    elif victims > 100:
        base -= 0.1
    elif victims > 50:
        base -= 0.05

    return max(0.1, min(base, 0.95))


async def prioritize_events_node(state: FrontlineRescueState) -> dict[str, Any]:
    """Score and prioritize pending frontline events.

    返回的 prioritized_events 已按 score 从高到低排序。
    """

    pending: List[FrontlineEvent] = list(state.get("pending_events", []))
    scenario_id = state.get("scenario_id", "")

    if not pending:
        logger.info("[Frontline] No pending events, skip prioritization")
        return {
            "prioritized_events": [],
            "current_phase": "prioritize_events_skipped",
        }

    logger.info("[Frontline] Prioritizing %d events for scenario %s", len(pending), scenario_id)

    # 构造 ScoringContext 列表
    now = datetime.now(tz=timezone.utc)
    contexts: List[ScoringContext] = []
    event_by_id: Dict[str, FrontlineEvent] = {}

    for ev in pending:
        ev_id = ev.get("id") or ""
        event_by_id[ev_id] = ev

        life_threat = _priority_to_life_threat(str(ev.get("priority", "medium")))
        time_urgency, remaining_min = _compute_time_urgency(ev, now)
        affected_population = int(ev.get("estimated_victims") or 0)
        success_prob = _estimate_success_probability(ev)

        features: Dict[str, Any] = {
            "life_threat_level": life_threat,
            "time_urgency_score": time_urgency,
            "affected_population": affected_population,
            "success_probability": success_prob,
            "golden_time_remaining_min": remaining_min,
        }

        ctx: ScoringContext = {
            "scenario_id": scenario_id,
            "event_id": ev_id,
            "entity_type": EntityType.TASK,
            "entity_id": ev_id,
            "features": features,
            "texts": [
                str(ev.get("title", "")),
                str(ev.get("description", "")),
            ],
            "tags": {
                "event_type": str(ev.get("event_type", "")),
                "priority": str(ev.get("priority", "")),
            },
        }
        contexts.append(ctx)

    # 调用 PriorityScoringEngine
    async with AsyncSessionLocal() as session:
        config_service = AlgorithmConfigService(session)
        scoring_engine = PriorityScoringEngine(config_service=config_service)
        scoring_results = await scoring_engine.score_many(contexts, RULE_CODE_FRONTLINE_EVENT)

    prioritized: List[PrioritizedEvent] = []
    for ctx, res in zip(contexts, scoring_results, strict=False):
        ev_id = ctx.get("entity_id") or ""
        base_ev = event_by_id.get(ev_id) or {}
        pe: PrioritizedEvent = PrioritizedEvent(**base_ev)  # type: ignore[arg-type]
        pe["score"] = float(res.get("score", 0.0) or 0.0)
        pe["priority_bucket"] = str(res.get("priority", base_ev.get("priority", "medium")))
        pe["reasons"] = list(res.get("reasons", []))
        prioritized.append(pe)

    prioritized.sort(key=lambda e: e.get("score", 0.0), reverse=True)

    logger.info(
        "[Frontline] Prioritization completed for scenario %s, events=%d",
        scenario_id,
        len(prioritized),
    )

    return {
        "prioritized_events": prioritized,
        "current_phase": "prioritize_events_completed",
    }


__all__ = ["prioritize_events_node"]
