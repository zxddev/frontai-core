"""Reconnaissance Agent

High-level wrapper around the Recon LangGraph workflow.

This agent exposes a simple async API that:
- Accepts ``scenario_id``/``event_id`` as input
- Invokes the LangGraph workflow that scores recon targets
- Returns a lightweight dict suitable for frontend APIs
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from .graph import get_recon_graph
from .state import ReconState


logger = logging.getLogger(__name__)


class ReconAgent:
    """Unmanned initial reconnaissance planning agent."""

    def __init__(self) -> None:
        self._graph = get_recon_graph()
        logger.info("[ReconAgent] Initialized")

    async def run(
        self,
        *,
        scenario_id: str,
        event_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute initial recon planning for the given scenario.

        Args:
            scenario_id: Disaster scenario identifier (想定ID)
            event_id: Optional event identifier

        Returns:
            Dictionary containing scored targets, device assignments and
            explanation text. This structure is intentionally simple so that
            routers can adapt it to different frontend DTOs.
        """

        start_ts = time.time()
        logger.info(
            "[ReconAgent] Running initial recon",
            extra={"scenario_id": scenario_id, "event_id": event_id},
        )

        initial_state: ReconState = {
            "scenario_id": scenario_id,
            "event_id": event_id,
            "risk_areas": [],
            "devices": [],
            "candidate_targets": [],
            "scored_targets": [],
            "assignments": [],
            "explanation": "",
            "errors": [],
            "trace": {},
            "current_phase": "score_targets_pending",
        }

        try:
            final_state = await self._graph.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[ReconAgent] Execution failed")
            elapsed_ms = int((time.time() - start_ts) * 1000)
            return {
                "success": False,
                "scenario_id": scenario_id,
                "event_id": event_id,
                "targets": [],
                "assignments": [],
                "explanation": "侦察计划生成失败，请检查后端日志。",
                "errors": [str(exc)],
                "execution_time_ms": elapsed_ms,
            }

        elapsed_ms = int((time.time() - start_ts) * 1000)

        return {
            "success": not final_state.get("errors"),
            "scenario_id": scenario_id,
            "event_id": event_id,
            "risk_areas": final_state.get("risk_areas", []),
            "devices": final_state.get("devices", []),
            "targets": final_state.get("scored_targets", []),
            "assignments": final_state.get("assignments", []),
            "explanation": final_state.get("explanation", ""),
            "recon_plan": final_state.get("recon_plan"),  # 侦察执行方案
            "trace": final_state.get("trace", {}),
            "errors": final_state.get("errors", []),
            "execution_time_ms": elapsed_ms,
        }


_agent_instance: Optional[ReconAgent] = None


def get_recon_agent() -> ReconAgent:
    """Return ReconAgent singleton instance."""

    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ReconAgent()
    return _agent_instance


__all__ = ["ReconAgent", "get_recon_agent"]
