"""CrewAI Crew assembly for situational awareness.

This module creates and configures the Crew that performs
situational awareness analysis for modules 0 and 5.
"""

import json
import logging
from typing import Any

from crewai import Crew, LLM, Process

from src.agents.overall_plan.crewai.agents import (
    create_disaster_analyst,
    create_intel_chief,
)
from src.agents.overall_plan.crewai.tasks import (
    create_basic_disaster_task,
    create_secondary_disaster_task,
)

logger = logging.getLogger(__name__)


class SituationalAwarenessError(Exception):
    """Raised when situational awareness processing fails."""

    pass


def create_situational_awareness_crew(llm: LLM) -> Crew:
    """Create the situational awareness Crew.

    This Crew handles modules 0 (Basic Disaster Situation) and
    5 (Secondary Disaster Prevention) using flexible information synthesis.

    Args:
        llm: Language model instance to use for agents

    Returns:
        Configured Crew ready for execution
    """
    intel_chief = create_intel_chief(llm)
    disaster_analyst = create_disaster_analyst(llm)

    task_basic = create_basic_disaster_task(intel_chief)
    task_secondary = create_secondary_disaster_task(disaster_analyst, context_task=task_basic)

    return Crew(
        agents=[intel_chief, disaster_analyst],
        tasks=[task_basic, task_secondary],
        process=Process.sequential,
        verbose=True,
    )


def parse_crew_output(
    crew_output: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse Crew output into structured module data.

    Args:
        crew_output: Raw output from Crew.kickoff()

    Returns:
        Tuple of (module_0_data, module_5_data)

    Raises:
        SituationalAwarenessError: If output cannot be parsed
    """
    try:
        tasks_output = crew_output.tasks_output if hasattr(crew_output, "tasks_output") else []

        if len(tasks_output) < 2:
            raise SituationalAwarenessError(
                f"Expected 2 task outputs, got {len(tasks_output)}"
            )

        # Parse Module 0 output - check for pydantic first
        task_0 = tasks_output[0]
        if hasattr(task_0, "pydantic") and task_0.pydantic is not None:
            module_0_data = task_0.pydantic.model_dump()
        elif hasattr(task_0, "json_dict") and task_0.json_dict is not None:
            module_0_data = task_0.json_dict
        elif hasattr(task_0, "raw"):
            module_0_raw = task_0.raw
            if isinstance(module_0_raw, dict):
                module_0_data = module_0_raw
            else:
                module_0_data = _parse_json_output(str(module_0_raw), "module_0")
        else:
            module_0_data = _parse_json_output(str(task_0), "module_0")

        # Parse Module 5 output - check for pydantic first
        task_5 = tasks_output[1]
        if hasattr(task_5, "pydantic") and task_5.pydantic is not None:
            module_5_data = task_5.pydantic.model_dump()
        elif hasattr(task_5, "json_dict") and task_5.json_dict is not None:
            module_5_data = task_5.json_dict
        elif hasattr(task_5, "raw"):
            module_5_raw = task_5.raw
            if isinstance(module_5_raw, dict):
                module_5_data = module_5_raw
            else:
                module_5_data = _parse_json_output(str(module_5_raw), "module_5")
        else:
            module_5_data = _parse_json_output(str(task_5), "module_5")

        # Validate required fields
        _validate_module_0(module_0_data)
        _validate_module_5(module_5_data)

        return module_0_data, module_5_data

    except SituationalAwarenessError:
        raise
    except Exception as e:
        logger.exception("Failed to parse crew output")
        raise SituationalAwarenessError(f"Failed to parse crew output: {e}") from e


def _parse_json_output(raw: str, module_name: str) -> dict[str, Any]:
    """Parse JSON from raw string output.

    Handles cases where LLM output contains markdown code blocks.
    """
    text = raw.strip()

    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Find first and last ``` lines
        start_idx = 0
        end_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("```") and i == 0:
                start_idx = 1
            elif line.startswith("```"):
                end_idx = i
                break
        text = "\n".join(lines[start_idx:end_idx])

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SituationalAwarenessError(
            f"Invalid JSON in {module_name} output: {e}\nRaw output: {raw[:500]}"
        ) from e


def _validate_module_0(data: dict[str, Any]) -> None:
    """Validate Module 0 has required fields."""
    required_fields = ["disaster_type", "affected_area"]
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        raise SituationalAwarenessError(
            f"Module 0 missing required fields: {missing}"
        )


def _validate_module_5(data: dict[str, Any]) -> None:
    """Validate Module 5 has required structure."""
    if "risks" not in data:
        raise SituationalAwarenessError("Module 5 missing 'risks' field")
    if not isinstance(data["risks"], list):
        raise SituationalAwarenessError("Module 5 'risks' must be a list")
