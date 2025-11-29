"""CrewAI Situational Awareness Sub-graph

Handles modules 0 (Basic Disaster Situation) and 5 (Secondary Disaster Prevention)
using flexible, non-structured information synthesis.
"""

from src.agents.overall_plan.crewai.crew import create_situational_awareness_crew

__all__ = ["create_situational_awareness_crew"]
