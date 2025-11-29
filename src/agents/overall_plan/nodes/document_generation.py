"""Document Generation Node - Final document assembly.

This node uses the OfficialScribe role to generate the final
formal document after commander approval.
"""

import logging
from typing import Any

from langchain_openai import ChatOpenAI

from src.agents.overall_plan.metagpt.scribe import DocumentGenerationError, OfficialScribe
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


async def document_generation_node(
    state: OverallPlanState,
    llm: ChatOpenAI | None = None,
) -> dict[str, Any]:
    """Generate the final formal document.

    This node is executed only after commander approval.
    It assembles all 9 modules into a formal document.

    Args:
        state: Current workflow state with approved modules
        llm: Optional LLM instance

    Returns:
        State updates with final document

    Raises:
        DocumentGenerationError: If document generation fails
    """
    event_id = state.get("event_id", "unknown")
    task_id = state.get("task_id", "unknown")
    logger.info(f"Starting document generation for event {event_id}, task {task_id}")

    # Verify approval
    if not state.get("approved"):
        raise DocumentGenerationError("Cannot generate document without commander approval")

    try:
        # Create LLM if not provided
        if llm is None:
            llm = _create_default_llm()

        # Generate document using OfficialScribe
        scribe = OfficialScribe(llm)
        document = await scribe.generate_document(state)

        logger.info(f"Document generation completed for task {task_id}")

        return {
            "final_document": document,
            "status": "completed",
            "current_phase": "document_generation_completed",
        }

    except DocumentGenerationError:
        raise
    except Exception as e:
        logger.exception(f"Document generation failed for task {task_id}")
        raise DocumentGenerationError(f"Document generation failed: {e}") from e


def _create_default_llm() -> ChatOpenAI:
    """Create default LLM instance."""
    import os

    llm_model = os.environ.get("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "180"))

    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=request_timeout,
    )
