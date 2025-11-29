"""Situational Awareness Node - CrewAI wrapper for modules 0 and 5.

This node wraps CrewAI execution in a thread pool to avoid
asyncio event loop conflicts, and parses the output into state.
"""

import asyncio
import json
import logging
from functools import partial
from typing import Any

from crewai import LLM

from src.agents.overall_plan.crewai.crew import (
    SituationalAwarenessError,
    create_situational_awareness_crew,
    parse_crew_output,
)
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


async def situational_awareness_node(
    state: OverallPlanState,
    llm: LLM | None = None,
) -> dict[str, Any]:
    """Execute situational awareness analysis using CrewAI.

    This node generates modules 0 and 5 through flexible information
    synthesis by CrewAI agents.

    Args:
        state: Current workflow state
        llm: Optional LLM instance (will create default if not provided)

    Returns:
        State updates with modules 0 and 5

    Raises:
        SituationalAwarenessError: If CrewAI execution fails
    """
    event_id = state.get("event_id", "unknown")
    logger.info(f"Starting situational awareness for event {event_id}")

    try:
        # Create LLM if not provided
        if llm is None:
            llm = _create_default_llm()

        # Create the crew
        crew = create_situational_awareness_crew(llm)

        # Prepare inputs
        inputs = {
            "event_data": json.dumps(state.get("event_data", {}), ensure_ascii=False, indent=2),
            "ai_analysis": json.dumps(state.get("ai_analysis", {}), ensure_ascii=False, indent=2),
        }

        # Run CrewAI in thread pool to avoid event loop conflicts
        logger.debug("Running CrewAI in thread pool")
        loop = asyncio.get_event_loop()
        crew_output = await loop.run_in_executor(
            None,
            partial(crew.kickoff, inputs=inputs),
        )

        # Parse crew output
        module_0_data, module_5_data = parse_crew_output(crew_output)

        logger.info(f"Situational awareness completed for event {event_id}")

        return {
            "module_0_basic_disaster": module_0_data,
            "module_5_secondary_disaster": module_5_data,
            "current_phase": "situational_awareness_completed",
        }

    except SituationalAwarenessError:
        raise
    except Exception as e:
        logger.exception(f"Situational awareness failed for event {event_id}")
        raise SituationalAwarenessError(f"Situational awareness failed: {e}") from e


def _create_default_llm() -> LLM:
    """Create default LLM instance for CrewAI.

    Uses environment variables for configuration.
    """
    import os

    llm_model = os.environ.get("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "180"))

    return LLM(
        model=f"openai/{llm_model}",
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=request_timeout,
    )
