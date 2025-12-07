"""
应急AI工具集

包含LLM、RAG、KG、路径规划四类工具。
"""
from __future__ import annotations

from .llm_tools import (
    parse_disaster_description,
    reason_rescue_priority,
    explain_scheme,
)
from .rag_tools import (
    search_similar_cases,
)
from .kg_tools import (
    query_trr_rules,
    query_capability_mapping,
)
from .routing_tools import (
    calculate_team_eta_with_routing,
    batch_calculate_team_etas,
    get_disaster_avoid_areas,
    get_danger_area_avoid_areas,
    ETAResult,
)

__all__ = [
    # LLM工具
    "parse_disaster_description",
    "reason_rescue_priority",
    "explain_scheme",
    # RAG工具
    "search_similar_cases",
    # KG工具
    "query_trr_rules",
    "query_capability_mapping",
    # 路径规划工具
    "calculate_team_eta_with_routing",
    "batch_calculate_team_etas",
    "get_disaster_avoid_areas",
    "get_danger_area_avoid_areas",
    "ETAResult",
]
