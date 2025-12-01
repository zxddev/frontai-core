"""Frontend API router for unmanned initial reconnaissance planning.

Route prefix: ``/recon-plan`` under the main frontend router.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.reconnaissance import get_recon_agent
from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.infra.config.algorithm_config_service import ConfigurationMissingError
from .schemas import (
    DeviceAssignmentItem,
    MissionStepItem,
    ReconExecutionPlan,
    ReconMissionItem,
    ReconPlanRequest,
    ReconPlanResponse,
    ReconTargetItem,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recon-plan", tags=["前端-侦察规划"])


async def _get_active_scenario_id(db: AsyncSession) -> str:
    """获取当前生效的想定ID（status='active'）。

    与总体方案接口保持一致的行为：如果前端未显式传入scenarioId，
    则自动选择当前生效的想定。
    """

    result = await db.execute(
        text("SELECT id FROM operational_v2.scenarios_v2 WHERE status = 'active' LIMIT 1"),
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到生效的想定，请先创建或激活一个想定",
        )
    return str(row[0])


@router.post("/initial-scan", response_model=ApiResponse[ReconPlanResponse])
async def initial_scan(
    request: ReconPlanRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ReconPlanResponse]:
    """Run initial unmanned recon planning for the given scenario.

    The backend uses deterministic scoring rules for target priority and a
    greedy one-to-one device assignment. The response is a single-shot plan
    without side effects on the database.
    """

    agent = get_recon_agent()

    scenario_id = request.scenarioId
    if not scenario_id:
        scenario_id = await _get_active_scenario_id(db)

    logger.info(
        "[ReconAPI] initial_scan called",
        extra={"scenario_id": scenario_id, "event_id": request.eventId},
    )

    try:
        result = await agent.run(
            scenario_id=scenario_id,
            event_id=request.eventId,
        )
    except ConfigurationMissingError as e:
        # 必需的打分规则缺失，按照“无Fallback”原则直接报错，但以统一响应格式返回
        logger.exception("[ReconAPI] Missing required scoring configuration for recon")
        return ApiResponse.error(
            500,
            str(e),
            data=None,
        )
    except Exception as e:  # 防御性兜底，避免FastAPI二次校验错误
        logger.exception("[ReconAPI] Unexpected error during recon initial_scan")
        return ApiResponse.error(
            500,
            f"侦察规划内部错误: {e}",
            data=None,
        )

    if not result.get("success", False):
        # 失败时返回最小有效响应结构
        error_msg = "; ".join(result.get("errors", ["未知错误"]))
        fallback_response = ReconPlanResponse(
            scenarioId=scenario_id,
            eventId=request.eventId,
            targets=[],
            assignments=[],
            explanation=f"侦察规划失败: {error_msg}",
            riskAreas=[],
            devices=[],
            reconPlan=None,
        )
        return ApiResponse.error(
            500,
            f"侦察规划失败: {error_msg}",
            data=fallback_response,
        )

    targets: List[ReconTargetItem] = []
    for t in result.get("targets", []):
        targets.append(
            ReconTargetItem(
                id=t.get("target_id", ""),
                riskAreaId=t.get("risk_area_id"),
                name=t.get("name", ""),
                priority=t.get("priority", "medium"),
                score=float(t.get("score", 0.0)),
                geometry=t.get("geometry", {}),
                features=t.get("features", {}),
                reasons=t.get("reasons", []) or [],
            )
        )

    assignments: List[DeviceAssignmentItem] = []
    for a in result.get("assignments", []):
        assignments.append(
            DeviceAssignmentItem(
                deviceId=a.get("device_id", ""),
                deviceName=a.get("device_name", ""),
                deviceType=a.get("device_type", ""),
                targetId=a.get("target_id", ""),
                targetName=a.get("target_name", ""),
                priority=a.get("priority", "medium"),
                reason=a.get("reason", ""),
            )
        )

    # 转换侦察执行方案
    recon_plan_data = result.get("recon_plan")
    recon_plan = None
    if recon_plan_data:
        missions = []
        for m in recon_plan_data.get("missions", []):
            steps = []
            for s in m.get("steps", []):
                steps.append(
                    MissionStepItem(
                        stepName=s.get("step_name", ""),
                        description=s.get("description", ""),
                        durationMinutes=s.get("duration_minutes", 0),
                        keyActions=s.get("key_actions", []),
                    )
                )
            missions.append(
                ReconMissionItem(
                    missionId=m.get("mission_id", ""),
                    deviceId=m.get("device_id", ""),
                    deviceName=m.get("device_name", ""),
                    deviceType=m.get("device_type", ""),
                    targetId=m.get("target_id", ""),
                    targetName=m.get("target_name", ""),
                    priority=m.get("priority", "medium"),
                    missionObjective=m.get("mission_objective", ""),
                    reconFocus=m.get("recon_focus", []),
                    reconMethod=m.get("recon_method", ""),
                    routeDescription=m.get("route_description", ""),
                    altitudeOrDepth=m.get("altitude_or_depth", ""),
                    estimatedDurationMinutes=m.get("estimated_duration_minutes", 0),
                    steps=steps,
                    coordinationNotes=m.get("coordination_notes", ""),
                    safetyNotes=m.get("safety_notes", []),
                    abortConditions=m.get("abort_conditions", []),
                )
            )
        recon_plan = ReconExecutionPlan(
            planId=recon_plan_data.get("plan_id", ""),
            summary=recon_plan_data.get("summary", ""),
            totalDurationMinutes=recon_plan_data.get("total_duration_minutes", 0),
            missions=missions,
            coordinationStrategy=recon_plan_data.get("coordination_strategy", ""),
            communicationPlan=recon_plan_data.get("communication_plan", ""),
            contingencyPlan=recon_plan_data.get("contingency_plan", ""),
        )

    response = ReconPlanResponse(
        scenarioId=result.get("scenario_id", scenario_id),
        eventId=result.get("event_id", request.eventId),
        targets=targets,
        assignments=assignments,
        explanation=result.get("explanation", ""),
        riskAreas=result.get("risk_areas", []),
        devices=result.get("devices", []),
        reconPlan=recon_plan,
    )

    return ApiResponse.success(response)


__all__ = ["router"]
