"""Frontend API router for unmanned initial reconnaissance planning.

Route prefix: ``/recon-plan`` under the main frontend router.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.reconnaissance import get_recon_agent
from src.agents.recon_scheduler import get_recon_scheduler_agent
from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.infra.config.algorithm_config_service import ConfigurationMissingError
from .scheduler_schemas import (
    ReconScheduleRequest,
    ReconScheduleResponse,
    FlightPlanItem,
    WaypointItem,
    FlightStatistics,
    TimelineItem,
    ExecutiveSummaryItem,
)
from .schemas import (
    DeviceAssignmentItem,
    MissionStepItem,
    ReconExecutionPlan,
    ReconMissionItem,
    ReconPlanRequest,
    ReconPlanResponse,
    ReconTargetItem,
)
from .analyze_schemas import (
    ReconTargetAnalysisRequest,
    ReconTargetAnalysisResponse,
    PrioritizedTarget,
    AnalysisReport,
    ResourceEstimate,
    TargetType,
    PriorityLevel,
    ScanPattern,
    DeviceType,
    LocationPoint,
    DeviceRecommendationDetail,
    ReconMethodDetail,
    RiskMitigationDetail,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recon-plan", tags=["前端-侦察规划"])

DEVICE_TYPE_MAP: Dict[str, str] = {
    "drone": "无人机",
    "dog": "机器狗",
    "ship": "无人艇",
    "robot": "机器人",
    "unknown": "未知设备",
}


def _format_plan_content(response: ReconPlanResponse) -> str:
    """将 ReconPlanResponse 转换为人类可读的文本格式。
    
    生成的文本用于存储在 recon_plans.plan_content 字段，供前端直接展示。
    """
    lines: List[str] = []
    recon_plan = response.reconPlan
    assignments = response.assignments

    lines.append("【侦察方案】")

    if recon_plan and recon_plan.summary:
        lines.append(recon_plan.summary)
        lines.append("")

    if recon_plan and recon_plan.missions:
        for idx, mission in enumerate(recon_plan.missions, 1):
            device_type_cn = DEVICE_TYPE_MAP.get(mission.deviceType, mission.deviceType)
            lines.append(f"{idx}. {mission.deviceName} (目标: {mission.targetName})")

            if mission.missionObjective:
                lines.append(f"   【任务目标】{mission.missionObjective}")
            if mission.reconMethod:
                lines.append(f"   【侦察方法】{mission.reconMethod}")
            if mission.routeDescription:
                lines.append(f"   【路线描述】{mission.routeDescription}")

            params: List[str] = []
            if mission.altitudeOrDepth:
                params.append(f"高度/深度: {mission.altitudeOrDepth}")
            if mission.estimatedDurationMinutes:
                params.append(f"预计耗时: {mission.estimatedDurationMinutes}分钟")
            if params:
                lines.append(f"   【作业参数】{', '.join(params)}")

            if mission.steps:
                lines.append("   【执行步骤】")
                for step in mission.steps:
                    lines.append(f"      - {step.stepName}: {step.description}")

            if mission.reconFocus:
                lines.append(f"   【侦察重点】{'、'.join(mission.reconFocus)}")
            if mission.coordinationNotes:
                lines.append(f"   【协同说明】{mission.coordinationNotes}")
            if mission.safetyNotes:
                lines.append("   【安全事项】")
                for note in mission.safetyNotes:
                    lines.append(f"      - {note}")
            if mission.abortConditions:
                lines.append("   【中止条件】")
                for cond in mission.abortConditions:
                    lines.append(f"      - {cond}")
            lines.append("")

    lines.append("【资源配置建议】")
    if assignments:
        type_count: Dict[str, int] = {}
        for item in assignments:
            type_cn = DEVICE_TYPE_MAP.get(item.deviceType, item.deviceType)
            type_count[type_cn] = type_count.get(type_cn, 0) + 1
        for type_name, count in type_count.items():
            lines.append(f"- {type_name}组：{count}台")
    lines.append("- 通信保障：建立临时通信基站，确保侦察设备实时回传")

    return "\n".join(lines)


async def _save_recon_plan(
    db: AsyncSession,
    scenario_id: str,
    event_id: Optional[str],
    response: ReconPlanResponse,
) -> str:
    """保存侦察方案到 recon_plans 表。
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        event_id: 事件ID（可空）
        response: 侦察方案响应对象
        
    Returns:
        生成的方案ID (plan_id)
        
    Raises:
        Exception: 数据库写入失败时抛出异常
    """
    plan_id = str(uuid.uuid4())
    
    recon_plan = response.reconPlan
    plan_title = "无人设备侦察方案"
    if recon_plan and recon_plan.summary:
        plan_title = recon_plan.summary[:200] if len(recon_plan.summary) > 200 else recon_plan.summary

    plan_content = _format_plan_content(response)

    plan_data_dict: Dict[str, Any] = {
        "plan_id": plan_id,
        "scenario_id": scenario_id,
        "event_id": event_id,
        "targets": [t.model_dump() for t in response.targets],
        "assignments": [a.model_dump() for a in response.assignments],
        "explanation": response.explanation,
        "risk_areas": response.riskAreas,
        "devices": response.devices,
        "recon_plan": recon_plan.model_dump() if recon_plan else None,
    }
    plan_data_json = json.dumps(plan_data_dict, ensure_ascii=False, default=str)

    device_count = len(response.assignments)
    target_count = len(response.targets)
    estimated_duration = recon_plan.totalDurationMinutes if recon_plan else None

    sql = text("""
        INSERT INTO operational_v2.recon_plans (
            plan_id, incident_id, plan_type, plan_subtype, plan_title,
            plan_content, plan_data, device_count, target_count,
            estimated_duration, status, created_by, created_at, updated_at
        ) VALUES (
            :plan_id, :incident_id, 'recon', 'initial_scan', :plan_title,
            :plan_content, CAST(:plan_data AS jsonb), :device_count, :target_count,
            :estimated_duration, 'draft', 'system', NOW(), NOW()
        )
    """)

    await db.execute(
        sql,
        {
            "plan_id": plan_id,
            "incident_id": event_id,
            "plan_title": plan_title,
            "plan_content": plan_content,
            "plan_data": plan_data_json,
            "device_count": device_count,
            "target_count": target_count,
            "estimated_duration": estimated_duration,
        },
    )
    await db.commit()

    logger.info(
        "[ReconAPI] 侦察方案已保存",
        extra={
            "plan_id": plan_id,
            "scenario_id": scenario_id,
            "event_id": event_id,
            "device_count": device_count,
            "target_count": target_count,
        },
    )

    return plan_id


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

    try:
        plan_id = await _save_recon_plan(
            db=db,
            scenario_id=scenario_id,
            event_id=request.eventId,
            response=response,
        )
        response.planId = plan_id
    except Exception as e:
        logger.exception("[ReconAPI] 保存侦察方案到数据库失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"侦察方案保存失败: {e}",
        )

    return ApiResponse.success(response)


def _parse_plan_data_to_response(plan_data: Dict[str, Any]) -> ReconPlanResponse:
    """将数据库中的 plan_data JSON 转换为 ReconPlanResponse 对象"""
    
    # 解析 targets
    targets: List[ReconTargetItem] = []
    for t in plan_data.get("targets", []):
        targets.append(
            ReconTargetItem(
                id=t.get("id", ""),
                riskAreaId=t.get("riskAreaId"),
                name=t.get("name", ""),
                priority=t.get("priority", "medium"),
                score=float(t.get("score", 0.0)),
                geometry=t.get("geometry", {}),
                features=t.get("features", {}),
                reasons=t.get("reasons", []) or [],
            )
        )
    
    # 解析 assignments
    assignments: List[DeviceAssignmentItem] = []
    for a in plan_data.get("assignments", []):
        assignments.append(
            DeviceAssignmentItem(
                deviceId=a.get("deviceId", ""),
                deviceName=a.get("deviceName", ""),
                deviceType=a.get("deviceType", ""),
                targetId=a.get("targetId", ""),
                targetName=a.get("targetName", ""),
                priority=a.get("priority", "medium"),
                reason=a.get("reason", ""),
            )
        )
    
    # 解析侦察执行方案
    recon_plan_data = plan_data.get("recon_plan")
    recon_plan = None
    if recon_plan_data:
        missions = []
        for m in recon_plan_data.get("missions", []):
            steps = []
            for s in m.get("steps", []):
                steps.append(
                    MissionStepItem(
                        stepName=s.get("stepName", ""),
                        description=s.get("description", ""),
                        durationMinutes=s.get("durationMinutes", 0),
                        keyActions=s.get("keyActions", []),
                    )
                )
            missions.append(
                ReconMissionItem(
                    missionId=m.get("missionId", ""),
                    deviceId=m.get("deviceId", ""),
                    deviceName=m.get("deviceName", ""),
                    deviceType=m.get("deviceType", ""),
                    targetId=m.get("targetId", ""),
                    targetName=m.get("targetName", ""),
                    priority=m.get("priority", "medium"),
                    missionObjective=m.get("missionObjective", ""),
                    reconFocus=m.get("reconFocus", []),
                    reconMethod=m.get("reconMethod", ""),
                    routeDescription=m.get("routeDescription", ""),
                    altitudeOrDepth=m.get("altitudeOrDepth", ""),
                    estimatedDurationMinutes=m.get("estimatedDurationMinutes", 0),
                    steps=steps,
                    coordinationNotes=m.get("coordinationNotes", ""),
                    safetyNotes=m.get("safetyNotes", []),
                    abortConditions=m.get("abortConditions", []),
                )
            )
        recon_plan = ReconExecutionPlan(
            planId=recon_plan_data.get("planId", ""),
            summary=recon_plan_data.get("summary", ""),
            totalDurationMinutes=recon_plan_data.get("totalDurationMinutes", 0),
            missions=missions,
            coordinationStrategy=recon_plan_data.get("coordinationStrategy", ""),
            communicationPlan=recon_plan_data.get("communicationPlan", ""),
            contingencyPlan=recon_plan_data.get("contingencyPlan", ""),
        )
    
    return ReconPlanResponse(
        planId=plan_data.get("plan_id", ""),
        scenarioId=plan_data.get("scenario_id", ""),
        eventId=plan_data.get("event_id"),
        targets=targets,
        assignments=assignments,
        explanation=plan_data.get("explanation", ""),
        riskAreas=plan_data.get("risk_areas", []),
        devices=plan_data.get("devices", []),
        reconPlan=recon_plan,
    )


@router.get("/latest", response_model=ApiResponse[ReconPlanResponse])
async def get_latest_recon_plan(
    scenario_id: Optional[str] = None,
    event_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ReconPlanResponse]:
    """获取最新的侦察方案（从数据库）
    
    优先查询数据库中已保存的侦察方案，用于避免重复调用 AI 生成。
    
    Args:
        scenario_id: 想定ID（可选，不传则使用当前生效的想定）
        event_id: 事件ID（可选）
        
    Returns:
        最新的侦察方案，如果没有则返回 404
    """
    
    if not scenario_id:
        try:
            scenario_id = await _get_active_scenario_id(db)
        except HTTPException:
            return ApiResponse.error(404, "没有找到生效的想定", data=None)
    
    logger.info(
        "[ReconAPI] get_latest_recon_plan called",
        extra={"scenario_id": scenario_id, "event_id": event_id},
    )
    
    # 查询最新方案（根据是否有 event_id 使用不同查询）
    if event_id:
        sql = text("""
            SELECT plan_id, plan_data, created_at 
            FROM operational_v2.recon_plans 
            WHERE plan_data->>'scenario_id' = :scenario_id
              AND incident_id = :event_id
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = await db.execute(sql, {"scenario_id": scenario_id, "event_id": event_id})
    else:
        sql = text("""
            SELECT plan_id, plan_data, created_at 
            FROM operational_v2.recon_plans 
            WHERE plan_data->>'scenario_id' = :scenario_id
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = await db.execute(sql, {"scenario_id": scenario_id})
    row = result.fetchone()
    
    if not row:
        logger.info("[ReconAPI] 未找到已保存的侦察方案")
        return ApiResponse.error(404, "暂无侦察方案", data=None)
    
    plan_id, plan_data, created_at = row
    logger.info(
        "[ReconAPI] 找到已保存的侦察方案",
        extra={"plan_id": plan_id, "created_at": str(created_at)},
    )
    
    try:
        response = _parse_plan_data_to_response(plan_data)
        response.planId = str(plan_id)
        return ApiResponse.success(response)
    except Exception as e:
        logger.exception("[ReconAPI] 解析侦察方案数据失败")
        return ApiResponse.error(500, f"解析方案数据失败: {e}", data=None)


@router.post("/schedule", response_model=ApiResponse[ReconScheduleResponse])
async def schedule_recon(
    request: ReconScheduleRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ReconScheduleResponse]:
    """调度侦察任务，生成航线规划
    
    使用ReconSchedulerAgent进行完整的侦察调度，包括：
    - 灾情分析
    - 环境评估
    - 资源分配
    - 航线规划（Z字形/螺旋/环形）
    - 风险评估
    
    Args:
        request: 调度请求，包含灾情类型、目标区域、天气条件
        
    Returns:
        完整的侦察计划，包含航线、时间线、KML文件
    """
    logger.info(
        "[ReconAPI] schedule_recon called",
        extra={
            "disaster_type": request.disasterType,
            "scenario_id": request.scenarioId,
            "event_id": request.eventId,
        },
    )
    
    agent = get_recon_scheduler_agent()
    
    # 构建天气参数
    weather = None
    if request.weather:
        weather = {
            "wind_speed_ms": request.weather.wind_speed_ms,
            "wind_direction_deg": request.weather.wind_direction_deg,
            "rain_level": request.weather.rain_level,
            "visibility_m": request.weather.visibility_m,
            "temperature_c": request.weather.temperature_c,
        }
    
    try:
        result = await agent.quick_schedule(
            disaster_type=request.disasterType,
            target_area=request.targetArea,
            weather=weather,
        )
    except Exception as e:
        logger.exception("[ReconAPI] ReconScheduler调度失败")
        return ApiResponse.error(500, f"侦察调度失败: {e}", data=None)
    
    if not result.get("success", False):
        error_msg = result.get("error", "未知错误")
        return ApiResponse.error(500, f"侦察调度失败: {error_msg}", data=None)
    
    # 转换结果
    recon_plan = result.get("recon_plan", {})
    # 生成UUID用于数据库存储，同时保留友好ID用于显示
    db_plan_id = str(uuid.uuid4())
    display_plan_id = recon_plan.get("plan_id", db_plan_id)
    plan_id = display_plan_id  # 返回给前端的ID
    
    # 转换航线计划
    flight_plans = []
    for fp in result.get("flight_files", []):
        waypoints = []
        for wp in fp.get("waypoints_json", []):
            waypoints.append(WaypointItem(
                seq=wp.get("seq", 0),
                lat=wp.get("lat", 0),
                lng=wp.get("lng", 0),
                alt_m=wp.get("alt_m", 0),
                action=wp.get("action", "waypoint"),
                speed_ms=wp.get("speed_ms"),
            ))
        
        # 从recon_plan中找到对应的flight_plan获取详细信息
        raw_fp = None
        for rfp in recon_plan.get("flight_plans", []):
            if rfp.get("device_id") == fp.get("device_id"):
                raw_fp = rfp
                break
        
        stats = raw_fp.get("statistics", {}) if raw_fp else {}
        flight_plans.append(FlightPlanItem(
            taskId=raw_fp.get("task_id", "") if raw_fp else "",
            taskName=raw_fp.get("task_name", "") if raw_fp else fp.get("device_name", ""),
            deviceId=fp.get("device_id", ""),
            deviceName=fp.get("device_name", ""),
            scanPattern=raw_fp.get("scan_pattern", "zigzag") if raw_fp else "zigzag",
            altitude_m=raw_fp.get("flight_parameters", {}).get("altitude_m", 100) if raw_fp else 100,
            waypoints=waypoints,
            statistics=FlightStatistics(
                total_distance_m=stats.get("total_distance_m", 0),
                total_duration_min=stats.get("total_duration_min", 0),
                waypoint_count=len(waypoints),
            ),
            kmlContent=fp.get("file_content"),
        ))
    
    # 转换时间线
    timeline = []
    gantt_data = recon_plan.get("timeline", {}).get("gantt_data", [])
    for bar in gantt_data:
        timeline.append(TimelineItem(
            taskName=bar.get("task_name", ""),
            deviceName=bar.get("device_name", ""),
            startMin=bar.get("start_min", 0),
            endMin=bar.get("end_min", 0),
            phase=bar.get("phase", 1),
        ))
    
    # 转换执行摘要
    exec_summary = recon_plan.get("executive_summary", {})
    executive_summary = None
    if exec_summary:
        executive_summary = ExecutiveSummaryItem(
            missionName=exec_summary.get("mission_name", ""),
            disasterType=exec_summary.get("disaster_type", request.disasterType),
            totalDevices=exec_summary.get("total_devices", 0),
            totalPhases=exec_summary.get("total_phases", 0),
            totalTasks=exec_summary.get("total_tasks", 0),
            estimatedDurationMin=exec_summary.get("estimated_duration_min", 0),
            overallRiskLevel=exec_summary.get("overall_risk_level", "medium"),
        )
    
    response = ReconScheduleResponse(
        planId=plan_id,
        success=True,
        executiveSummary=executive_summary,
        flightPlans=flight_plans,
        timeline=timeline,
        totalDurationMin=recon_plan.get("timeline", {}).get("total_duration_min", 0),
        flightCondition=recon_plan.get("environment_assessment", {}).get("flight_condition", "green"),
        riskLevel=recon_plan.get("risk_assessment", {}).get("overall_risk_level", "medium"),
        validationPassed=recon_plan.get("validation", {}).get("is_valid", False),
        errors=result.get("errors", []),
        warnings=result.get("warnings", []),
    )
    
    # 保存到数据库
    try:
        scenario_id = request.scenarioId
        if not scenario_id:
            try:
                scenario_id = await _get_active_scenario_id(db)
            except HTTPException:
                scenario_id = "default"
        
        plan_data_dict = {
            "plan_id": db_plan_id,  # UUID格式
            "display_plan_id": display_plan_id,  # 友好显示ID
            "scenario_id": scenario_id,
            "event_id": request.eventId,
            "disaster_type": request.disasterType,
            "target_area": request.targetArea,
            "recon_plan": recon_plan,
            "flight_files": result.get("flight_files", []),
        }
        plan_data_json = json.dumps(plan_data_dict, ensure_ascii=False, default=str)
        
        sql = text("""
            INSERT INTO operational_v2.recon_plans (
                plan_id, incident_id, plan_type, plan_subtype, plan_title,
                plan_content, plan_data, device_count, target_count,
                estimated_duration, status, created_by, created_at, updated_at
            ) VALUES (
                :plan_id, :incident_id, 'recon', 'scheduler', :plan_title,
                :plan_content, CAST(:plan_data AS jsonb), :device_count, :target_count,
                :estimated_duration, 'draft', 'system', NOW(), NOW()
            )
        """)
        
        await db.execute(
            sql,
            {
                "plan_id": db_plan_id,  # 使用UUID
                "incident_id": request.eventId,
                "plan_title": exec_summary.get("mission_name", "侦察调度计划") if exec_summary else "侦察调度计划",
                "plan_content": f"灾情类型: {request.disasterType}, 航线数: {len(flight_plans)}",
                "plan_data": plan_data_json,
                "device_count": len(flight_plans),
                "target_count": len(recon_plan.get("mission_phases", [])),
                "estimated_duration": int(response.totalDurationMin),
            },
        )
        await db.commit()
        
        logger.info(f"[ReconAPI] 侦察调度计划已保存: db_id={db_plan_id}, display_id={display_plan_id}")
        
    except Exception as e:
        logger.exception("[ReconAPI] 保存侦察调度计划失败")
        # 不影响返回结果，只记录警告
        response.warnings.append(f"计划保存失败: {e}")
    
    return ApiResponse.success(response)


@router.post("/analyze-targets", response_model=ApiResponse[ReconTargetAnalysisResponse])
async def analyze_recon_targets(
    request: ReconTargetAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ReconTargetAnalysisResponse]:
    """分析所有侦察目标，智能排优先级
    
    收集所有需要侦察的目标（事件、危险区域、重点目标、救援点），
    使用LLM分析并排优先级，返回给指挥员决策。
    
    Args:
        request: 分析请求参数
        
    Returns:
        优先级排序后的目标列表和分析报告
    """
    import os
    
    analysis_id: str = f"analysis-{uuid.uuid4().hex[:12]}"
    
    # 获取scenario_id
    scenario_id = request.scenario_id
    if not scenario_id:
        try:
            scenario_id = await _get_active_scenario_id(db)
        except HTTPException:
            return ApiResponse.error(404, "没有找到生效的想定", data=None)
    
    logger.info(f"[ReconAPI] 开始分析侦察目标: scenario_id={scenario_id}, use_crewai={request.use_crewai}")
    
    # 查询最新已有方案ID
    latest_plan_id: str | None = None
    try:
        sql = text("""
            SELECT plan_id::text FROM operational_v2.recon_plans 
            WHERE plan_data->>'scenario_id' = :scenario_id
            ORDER BY created_at DESC LIMIT 1
        """)
        result = await db.execute(sql, {"scenario_id": scenario_id})
        row = result.fetchone()
        if row:
            latest_plan_id = row[0]
    except Exception as e:
        logger.warning(f"[ReconAPI] 查询最新方案失败: {e}")
    
    # 收集所有侦察目标（不限制想定）
    all_targets: list[dict] = []
    
    # 1. 查询事件
    if request.include_events:
        events = await _query_events_for_analysis(db)
        all_targets.extend(events)
        logger.info(f"[ReconAPI] 收集到{len(events)}个事件目标")
    
    # 2. 查询危险区域
    if request.include_risk_areas:
        risk_areas = await _query_risk_areas_for_analysis(db)
        all_targets.extend(risk_areas)
        logger.info(f"[ReconAPI] 收集到{len(risk_areas)}个危险区域目标")
    
    # 3. 查询重点目标（POI）
    if request.include_pois:
        pois = await _query_pois_for_analysis(db)
        all_targets.extend(pois)
        logger.info(f"[ReconAPI] 收集到{len(pois)}个POI目标")
    
    # 4. 查询救援点
    if request.include_rescue_points:
        rescue_points = await _query_rescue_points_for_analysis(db)
        all_targets.extend(rescue_points)
        logger.info(f"[ReconAPI] 收集到{len(rescue_points)}个救援点目标")
    
    logger.info(f"[ReconAPI] 共收集{len(all_targets)}个侦察目标")
    
    # 执行优先级分析（直接根据请求参数决定是否使用CrewAI）
    if request.use_crewai and all_targets:
        from src.agents.recon_scheduler.crewai import TargetPriorityAnalysisCrew
        crew = TargetPriorityAnalysisCrew()
        analysis_result = await crew.analyze(all_targets)
    else:
        from src.agents.recon_scheduler.crewai import rule_based_priority_analysis
        analysis_result = rule_based_priority_analysis(all_targets)
    
    # 构建响应（处理Pydantic对象）
    prioritized_targets: list[PrioritizedTarget] = []
    for pt in analysis_result.prioritized_targets:
        # pt是TargetReconPlan对象
        target_id = pt.target_id
        
        # 查找原始目标信息
        original = next((t for t in all_targets if t.get("target_id") == target_id), {})
        
        # 转换设备推荐详情
        recommended_devices: list[DeviceRecommendationDetail] = []
        for dev in pt.recommended_devices:
            recommended_devices.append(DeviceRecommendationDetail(
                device_type=DeviceType(dev.device_type),
                reason=dev.reason,
                capabilities_needed=dev.capabilities_needed,
            ))
        
        # 转换侦察方法详情
        recon_method_detail: ReconMethodDetail | None = None
        if pt.recon_method:
            recon_method_detail = ReconMethodDetail(
                method_name=pt.recon_method.method_name,
                description=pt.recon_method.description,
                route_description=pt.recon_method.route_description,
                altitude_or_distance=pt.recon_method.altitude_or_distance,
                coverage_pattern=ScanPattern(pt.recon_method.coverage_pattern),
            )
        
        # 转换风险规避措施
        risk_mitigations: list[RiskMitigationDetail] = []
        for rm in pt.risk_mitigations:
            risk_mitigations.append(RiskMitigationDetail(
                risk_type=rm.risk_type,
                mitigation_measure=rm.mitigation_measure,
            ))
        
        prioritized_targets.append(PrioritizedTarget(
            target_id=target_id,
            target_type=TargetType(original.get("target_type", "event")),
            name=original.get("name", "未知目标"),
            location=LocationPoint(
                lat=original.get("lat", 0),
                lng=original.get("lng", 0),
            ) if original.get("lat") else None,
            geometry_wkt=original.get("geometry_wkt"),
            priority=PriorityLevel(pt.priority),
            priority_score=pt.priority_score,
            priority_reason=pt.priority_reason,
            # 详细设备推荐
            recommended_devices=recommended_devices,
            recommended_device_types=[DeviceType(d.device_type) for d in pt.recommended_devices],
            # 侦察方法
            recon_method=recon_method_detail,
            recon_focus=pt.recon_focus,
            recon_content=pt.recon_content,
            # 风险与安全
            risk_mitigations=risk_mitigations,
            safety_notes=pt.safety_notes,
            abort_conditions=pt.abort_conditions,
            coordination_notes=pt.coordination_notes,
            # 执行参数
            estimated_duration_min=pt.estimated_duration_min,
            source_table=original.get("source_table", ""),
            source_id=original.get("source_id", ""),
            # 原始数据
            estimated_victims=original.get("estimated_victims"),
            is_time_critical=original.get("is_time_critical", False),
            golden_hour_remaining_min=original.get("golden_hour_remaining_min"),
            risk_level=original.get("risk_level"),
            population=original.get("population"),
        ))
    
    response = ReconTargetAnalysisResponse(
        analysis_id=analysis_id,
        latest_plan_id=latest_plan_id,
        total_targets=len(all_targets),
        prioritized_targets=prioritized_targets,
        analysis_report=AnalysisReport(
            summary=analysis_result.analysis_summary,
            resource_estimate=ResourceEstimate(
                total_devices_needed=analysis_result.total_devices_needed,
                total_duration_min=analysis_result.total_duration_min,
                device_breakdown=analysis_result.device_breakdown,
            ),
            recommendations=analysis_result.recommendations,
            warnings=analysis_result.warnings,
        ),
    )
    
    logger.info(f"[ReconAPI] 侦察目标分析完成: {len(prioritized_targets)}个目标")
    
    return ApiResponse.success(response)


async def _query_events_for_analysis(db: AsyncSession) -> list[dict]:
    """查询需要侦察的事件（只查询pending状态，未分配任务的）"""
    sql = text("""
        SELECT 
            id::text as source_id,
            event_code,
            title as name,
            event_type,
            priority,
            estimated_victims,
            is_time_critical,
            golden_hour_deadline,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng,
            ST_AsText(affected_area) as geometry_wkt
        FROM operational_v2.events_v2
        WHERE status = 'pending'
        ORDER BY 
            CASE priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                ELSE 4 
            END,
            estimated_victims DESC NULLS LAST
    """)
    result = await db.execute(sql)
    rows = result.fetchall()
    
    events: list[dict] = []
    now = datetime.now(timezone.utc)
    
    for row in rows:
        golden_remaining: float | None = None
        if row.golden_hour_deadline:
            delta = row.golden_hour_deadline - now
            golden_remaining = max(0, delta.total_seconds() / 60)
        
        events.append({
            "target_id": f"event-{row.source_id}",
            "target_type": "event",
            "source_table": "events_v2",
            "source_id": row.source_id,
            "name": row.name or f"事件{row.event_code}",
            "event_type": row.event_type,
            "priority": row.priority,
            "estimated_victims": row.estimated_victims or 0,
            "is_time_critical": row.is_time_critical or False,
            "golden_hour_remaining_min": golden_remaining,
            "lat": row.lat,
            "lng": row.lng,
            "geometry_wkt": row.geometry_wkt,
        })
    
    return events


async def _query_risk_areas_for_analysis(db: AsyncSession) -> list[dict]:
    """查询需要侦察的危险区域（不限制想定）"""
    sql = text("""
        SELECT 
            id::text as source_id,
            name,
            area_type,
            severity,
            risk_level,
            passage_status,
            ST_Y(ST_Centroid(geometry::geometry)) as lat,
            ST_X(ST_Centroid(geometry::geometry)) as lng,
            ST_AsText(geometry::geometry) as geometry_wkt
        FROM operational_v2.disaster_affected_areas_v2
        WHERE reconnaissance_required = true OR passage_status = 'needs_reconnaissance'
        ORDER BY risk_level DESC, severity DESC
    """)
    result = await db.execute(sql)
    rows = result.fetchall()
    
    areas: list[dict] = []
    for row in rows:
        # 根据severity映射priority
        priority_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}
        priority = priority_map.get(row.severity, "medium")
        
        areas.append({
            "target_id": f"risk_area-{row.source_id}",
            "target_type": "risk_area",
            "source_table": "disaster_affected_areas_v2",
            "source_id": row.source_id,
            "name": row.name or f"{row.area_type}区域",
            "area_type": row.area_type,
            "priority": priority,
            "risk_level": row.risk_level,
            "passage_status": row.passage_status,
            "lat": row.lat,
            "lng": row.lng,
            "geometry_wkt": row.geometry_wkt,
        })
    
    return areas


async def _query_pois_for_analysis(db: AsyncSession) -> list[dict]:
    """查询需要侦察的重点目标（不限制想定）"""
    sql = text("""
        SELECT 
            id::text as source_id,
            name,
            poi_type,
            risk_level,
            reconnaissance_priority,
            estimated_population,
            vulnerable_population,
            status,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng
        FROM operational_v2.poi_v2
        WHERE in_affected_area = true OR reconnaissance_priority > 50
        ORDER BY reconnaissance_priority DESC, estimated_population DESC NULLS LAST
    """)
    result = await db.execute(sql)
    rows = result.fetchall()
    
    pois: list[dict] = []
    for row in rows:
        # 根据risk_level映射priority
        risk = row.risk_level or "medium"
        priority_map = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "unknown": "medium"}
        priority = priority_map.get(risk, "medium")
        
        pois.append({
            "target_id": f"poi-{row.source_id}",
            "target_type": "poi",
            "source_table": "poi_v2",
            "source_id": row.source_id,
            "name": row.name,
            "poi_type": row.poi_type,
            "priority": priority,
            "risk_level": {"critical": 10, "high": 8, "medium": 5, "low": 2, "unknown": 5}.get(risk, 5),
            "reconnaissance_priority": row.reconnaissance_priority,
            "population": row.estimated_population,
            "vulnerable_population": row.vulnerable_population,
            "status": row.status,
            "lat": row.lat,
            "lng": row.lng,
        })
    
    return pois


async def _query_rescue_points_for_analysis(db: AsyncSession) -> list[dict]:
    """查询需要侦察的救援点（不限制想定）"""
    sql = text("""
        SELECT 
            id::text as source_id,
            name,
            point_type,
            priority,
            estimated_victims,
            status,
            ST_Y(location::geometry) as lat,
            ST_X(location::geometry) as lng
        FROM operational_v2.rescue_points_v2
        WHERE status IN ('pending', 'in_progress')
        ORDER BY 
            CASE priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                ELSE 4 
            END,
            estimated_victims DESC
    """)
    result = await db.execute(sql)
    rows = result.fetchall()
    
    points: list[dict] = []
    for row in rows:
        points.append({
            "target_id": f"rescue_point-{row.source_id}",
            "target_type": "rescue_point",
            "source_table": "rescue_points_v2",
            "source_id": row.source_id,
            "name": row.name,
            "point_type": row.point_type,
            "priority": row.priority,
            "estimated_victims": row.estimated_victims or 0,
            "is_time_critical": row.priority == "critical",
            "status": row.status,
            "lat": row.lat,
            "lng": row.lng,
        })
    
    return points


__all__ = ["router"]
