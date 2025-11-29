"""Overall Plan API Router.

Implements the REST endpoints for overall disaster plan generation:
- GET /modules: Trigger plan generation (auto-detect active scenario)
- GET /status: Query generation status
- PUT /approve: Commander approval
- GET /document: Retrieve final document
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.overall_plan.agent import OverallPlanAgent
from src.agents.overall_plan.schemas import (
    ApproveRequest,
    ApproveResponse,
    DocumentResponse,
    PlanStatusResponse,
    TriggerPlanResponse,
)
from src.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/overall-plan", tags=["overall-plan"])

# Singleton agent instance
# TODO: Use proper dependency injection with checkpointer from app config
_agent: OverallPlanAgent | None = None


def get_agent() -> OverallPlanAgent:
    """Get or create the OverallPlanAgent instance."""
    global _agent
    if _agent is None:
        # TODO: Configure with PostgreSQL checkpointer
        _agent = OverallPlanAgent()
    return _agent


async def get_active_scenario_id(db: AsyncSession) -> str:
    """获取当前生效的想定ID（status='active'）
    
    使用 SQLAlchemy AsyncSession 执行原生 SQL，与项目其他模块保持一致。
    """
    result = await db.execute(
        text("SELECT id FROM operational_v2.scenarios_v2 WHERE status = 'active' LIMIT 1")
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到生效的想定，请先创建或激活一个想定",
        )
    return str(row[0])


@router.get(
    "/modules",
    response_model=TriggerPlanResponse,
    summary="Trigger plan generation",
    description="Start generating the overall disaster plan. "
    "Automatically uses the active scenario (status='active'). "
    "Returns a task_id for tracking the generation progress.",
)
async def trigger_plan_generation(
    db: AsyncSession = Depends(get_db),
    agent: OverallPlanAgent = Depends(get_agent),
) -> TriggerPlanResponse:
    """Trigger overall plan generation for the active scenario.

    业务模型说明：
    - 自动获取当前生效的想定（status='active'）
    - 一次只能有一个生效的想定
    - 总体救灾方案针对想定生成，包含多个事件、灾情态势、资源等
    
    This endpoint starts the hybrid agent workflow:
    1. Load context data (scenarios_v2, events_v2, resources, supplies)
    2. Run CrewAI for situational awareness (module 1: 灾情评估)
    3. Run resource calculation with SPHERE standards (modules 3-7)
    4. Pause for commander review

    The workflow runs asynchronously. Use GET /status to track progress.
    """
    scenario_id = await get_active_scenario_id(db)
    logger.info(f"Triggering plan generation for active scenario {scenario_id}")
    try:
        result = await agent.trigger(scenario_id=scenario_id, event_id="")
        return result
    except Exception as e:
        logger.exception(f"Failed to trigger plan generation for scenario {scenario_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger plan generation: {str(e)}",
        )


@router.get(
    "/{event_id}/status",
    response_model=PlanStatusResponse,
    summary="Get plan generation status",
    description="Query the current status of a plan generation task.",
)
async def get_plan_status(
    event_id: str,
    task_id: Annotated[str, Query(description="Task ID from trigger response")],
    agent: OverallPlanAgent = Depends(get_agent),
) -> PlanStatusResponse:
    """Get the current status of a plan generation task.

    Status values:
    - pending: Task created but not started
    - running: Workflow is executing
    - awaiting_approval: All modules generated, waiting for commander review
    - completed: Final document generated
    - failed: Workflow failed (check errors field)
    """
    logger.debug(f"Getting status for event {event_id}, task {task_id}")
    try:
        result = await agent.get_status(event_id, task_id)
        return result
    except Exception as e:
        logger.exception(f"Failed to get status for task {task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}",
        )


@router.put(
    "/{event_id}/approve",
    response_model=ApproveResponse,
    summary="Commander approval",
    description="Submit commander's approval or rejection of the generated plan.",
)
async def approve_plan(
    event_id: str,
    request: ApproveRequest,
    agent: OverallPlanAgent = Depends(get_agent),
) -> ApproveResponse:
    """Process commander's approval or rejection.

    If approved:
    - Applies any modifications to modules
    - Proceeds to document generation
    - Returns status "running" or "completed"

    If rejected:
    - Marks workflow as failed
    - Does NOT auto-retry
    - User must trigger a new generation with corrected data
    """
    logger.info(f"Processing approval for event {event_id}, task {request.task_id}")
    try:
        result = await agent.approve(
            event_id=event_id,
            task_id=request.task_id,
            decision=request.decision,
            feedback=request.feedback,
            modifications=request.modifications,
        )
        return result
    except Exception as e:
        logger.exception(f"Failed to process approval for task {request.task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}",
        )


@router.get(
    "/{event_id}/document",
    response_model=DocumentResponse,
    summary="Get final document",
    description="Retrieve the final generated document after commander approval.",
)
async def get_document(
    event_id: str,
    task_id: Annotated[str, Query(description="Task ID from trigger response")],
    agent: OverallPlanAgent = Depends(get_agent),
) -> DocumentResponse:
    """Get the final generated document.

    Returns the complete disaster plan document in markdown format.
    Only available after the workflow reaches "completed" status.
    """
    logger.debug(f"Getting document for event {event_id}, task {task_id}")
    try:
        result = await agent.get_document(event_id, task_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found. Ensure the workflow is completed.",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get document for task {task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}",
        )
