"""
灾害预案/应急预案模块

前端调用 /web-api/api/disaster-plan/{id}/modules 获取总体方案模块
此路由代理到 overall_plan agent 生成真实内容
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.agents.overall_plan.agent import OverallPlanAgent
from src.agents.overall_plan.schemas import TriggerPlanResponse, PlanStatusResponse
from ..common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/disaster-plan", tags=["灾害预案"])

# Agent单例
_agent: OverallPlanAgent | None = None


def get_agent() -> OverallPlanAgent:
    """获取或创建OverallPlanAgent实例"""
    global _agent
    if _agent is None:
        _agent = OverallPlanAgent()
    return _agent


@router.get("/{plan_id}/modules", response_model=ApiResponse)
async def get_plan_modules(
    plan_id: str,
    agent: OverallPlanAgent = Depends(get_agent),
):
    """
    获取预案模块列表（触发生成）

    此接口触发overall_plan agent生成9个模块的总体救灾方案。
    plan_id 即 event_id，用于关联事件数据。

    返回task_id用于后续轮询状态。
    """
    logger.info(f"Triggering plan generation for event {plan_id}")
    try:
        result = await agent.trigger(plan_id, scenario_id="")
        return ApiResponse(
            code=200,
            message="success",
            data={
                "planId": plan_id,
                "taskId": result.task_id,
                "status": result.status,
                "message": "方案生成已启动，请使用taskId轮询状态"
            }
        )
    except Exception as e:
        logger.exception(f"Failed to trigger plan generation for {plan_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"方案生成失败: {str(e)}",
        )


@router.get("/{plan_id}/modules/status", response_model=ApiResponse)
async def get_plan_modules_status(
    plan_id: str,
    task_id: str = Query(..., description="任务ID"),
    agent: OverallPlanAgent = Depends(get_agent),
):
    """
    查询方案生成状态

    状态值:
    - pending: 任务已创建，未开始
    - running: 正在生成
    - awaiting_approval: 已生成，等待指挥官审批
    - completed: 已完成
    - failed: 失败
    """
    logger.debug(f"Getting status for plan {plan_id}, task {task_id}")
    try:
        result = await agent.get_status(plan_id, task_id)
        return ApiResponse(
            code=200,
            message="success",
            data={
                "planId": plan_id,
                "taskId": task_id,
                "status": result.status,
                "currentPhase": result.current_phase,
                "modules": [m.model_dump() for m in result.modules] if result.modules else [],
                "errors": result.errors,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to get status for task {task_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}",
        )


@router.put("/{plan_id}/modules/save", response_model=ApiResponse)
async def save_plan_modules(
    plan_id: str,
    params: dict,
    agent: OverallPlanAgent = Depends(get_agent),
):
    """
    保存/审批方案模块

    指挥官审核后调用此接口提交审批决定
    """
    logger.info(f"Saving plan modules for {plan_id}")
    task_id = params.get("taskId", "")
    decision = params.get("decision", "approved")
    feedback = params.get("feedback")
    modifications = params.get("modifications")

    if not task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="taskId is required",
        )

    try:
        result = await agent.approve(
            event_id=plan_id,
            task_id=task_id,
            decision=decision,
            feedback=feedback,
            modifications=modifications,
        )
        return ApiResponse(
            code=200,
            message="success",
            data={
                "planId": plan_id,
                "taskId": task_id,
                "status": result.status,
            }
        )
    except Exception as e:
        logger.exception(f"Failed to save plan modules for {plan_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存失败: {str(e)}",
        )


@router.get("/{plan_id}", response_model=ApiResponse)
async def get_plan_detail(
    plan_id: str,
    task_id: Optional[str] = Query(None, description="任务ID"),
    agent: OverallPlanAgent = Depends(get_agent),
):
    """
    获取预案详情

    如果提供task_id，返回生成的完整文档；
    否则返回基本信息。
    """
    if task_id:
        try:
            doc = await agent.get_document(plan_id, task_id)
            if doc:
                return ApiResponse(
                    code=200,
                    message="success",
                    data={
                        "id": plan_id,
                        "taskId": task_id,
                        "documentMarkdown": doc.document_markdown,
                        "generatedAt": doc.generated_at,
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to get document: {e}")

    # 返回基本信息
    return ApiResponse(
        code=200,
        message="success",
        data={
            "id": plan_id,
            "name": "总体救灾方案",
            "type": "overall_plan",
            "status": "pending",
            "description": "使用 GET /{plan_id}/modules 触发生成",
        }
    )
