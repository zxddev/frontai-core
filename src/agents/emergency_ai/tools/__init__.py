"""
应急AI工具集

包含LLM、RAG、KG三类工具。
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
]
