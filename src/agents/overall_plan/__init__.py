"""Overall Disaster Plan Generation Agent - Hybrid Architecture

This module implements a hybrid agent architecture combining:
- CrewAI: Situational awareness (modules 0, 5)
- MetaGPT: Resource calculation (modules 1-4, 6-8) and document generation
- LangGraph: Workflow orchestration with HITL support

Note: Requires crewai and metagpt dependencies to be installed.
"""

from src.agents.overall_plan.state import OverallPlanState

# Lazy import to handle missing dependencies gracefully
OverallPlanAgent = None

try:
    from src.agents.overall_plan.agent import OverallPlanAgent
except ImportError:
    pass  # Dependencies not installed

__all__ = ["OverallPlanAgent", "OverallPlanState"]
