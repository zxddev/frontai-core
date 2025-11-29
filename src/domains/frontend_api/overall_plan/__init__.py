"""Overall Plan API endpoints.

This module provides the REST API for overall disaster plan generation,
including triggering generation, status queries, commander approval,
and document retrieval.
"""

from src.domains.frontend_api.overall_plan.router import router

__all__ = ["router"]
