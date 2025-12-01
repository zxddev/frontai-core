"""Frontline Multi-Event Rescue Dispatch Agent.

This module exposes the FrontlineRescueAgent, which performs
multi-event frontline rescue prioritization and (in later phases)
resource allocation based on DB-backed rules.
"""
from __future__ import annotations

from .agent import FrontlineRescueAgent
from .state import FrontlineRescueState, FrontlineEvent

_frontline_agent: FrontlineRescueAgent | None = None


def get_frontline_rescue_agent() -> FrontlineRescueAgent:
    """Return a singleton instance of FrontlineRescueAgent.

    为了避免在每次请求中重复构建 LangGraph 和检查点器，
    这里使用简单的模块级单例模式。
    """
    global _frontline_agent
    if _frontline_agent is None:
        _frontline_agent = FrontlineRescueAgent()
    return _frontline_agent


__all__ = [
    "FrontlineRescueAgent",
    "FrontlineRescueState",
    "FrontlineEvent",
    "get_frontline_rescue_agent",
]
