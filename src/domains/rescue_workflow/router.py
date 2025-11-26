"""
救援业务流程路由

实现操作手册五阶段救援流程的HTTP接口
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from src.core.database import get_db
from .service import RescueWorkflowService
from .schemas import (
    IncidentNotification, EquipmentSuggestionRequest, EquipmentSuggestionResponse,
    PreparationTask, PreparationTaskComplete, DepartCommand, RouteRequest, RouteResponse,
    RiskPrediction, SafePoint, SafePointConfirm,
    CommandPostRecommendation, CommandPostConfirm, UAVClusterControl,
    RescuePointDetection, RescuePointConfirm, RescuePointCreate, RescuePointUpdate,
    RescuePointResponse, CoordinationTracking, CoordinationUpdate,
    EvaluationReportRequest, EvaluationReport,
    ManualRecommendation, ManualSearchRequest
)


router = APIRouter(prefix="/rescue-workflow", tags=["rescue-workflow"])


def get_service(db: AsyncSession = Depends(get_db)) -> RescueWorkflowService:
    return RescueWorkflowService(db)


# ============================================================================
# 阶段1: 接警通报
# ============================================================================

@router.post("/incidents/receive", status_code=201)
async def receive_incident(
    scenario_id: UUID,
    data: IncidentNotification,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    接收事件通报
    
    从外部系统（如119报警系统）接收事件通报，
    自动创建事件记录并触发后续处理流程。
    """
    return await service.receive_incident(scenario_id, data)


@router.post("/incidents/equipment-suggestion", response_model=EquipmentSuggestionResponse)
async def get_equipment_suggestion(
    data: EquipmentSuggestionRequest,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取AI装备建议
    
    根据事件类型、预估受困人数、地形等因素，
    AI推荐所需装备、车辆和队伍配置。
    """
    return await service.get_equipment_suggestion(data)


@router.post("/incidents/{event_id}/preparation-tasks")
async def create_preparation_tasks(
    scenario_id: UUID,
    event_id: UUID,
    tasks: list[PreparationTask],
    service: RescueWorkflowService = Depends(get_service),
):
    """
    创建准备任务
    
    创建出发前的准备任务：装备检查、车辆准备、人员集结、任务简报等。
    """
    return await service.create_preparation_tasks(scenario_id, event_id, tasks)


@router.post("/incidents/preparation-tasks/{task_id}/complete")
async def complete_preparation_task(
    task_id: UUID,
    data: PreparationTaskComplete,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    提交准备任务完成状态
    
    准备任务执行者上报完成状态，包括已完成项、人员到位、燃油状态等。
    """
    return await service.complete_preparation_task(task_id, data)


@router.post("/incidents/depart-command")
async def issue_depart_command(
    scenario_id: UUID,
    data: DepartCommand,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    发布出发指令
    
    指挥员确认准备完成后，发布出发指令。
    系统自动通知相关队伍和车辆。
    """
    return await service.issue_depart_command(scenario_id, data)


# ============================================================================
# 阶段2: 途中导航
# ============================================================================

@router.post("/navigation/route", response_model=RouteResponse)
async def plan_route(
    data: RouteRequest,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    规划路径
    
    AI路径规划，考虑道路状况、风险区域、交通状况等因素，
    返回最优路径和备选路径。
    """
    return await service.plan_route(data)


@router.post("/navigation/route/{route_id}/switch")
async def switch_route(
    route_id: UUID,
    new_route_index: int = Query(..., ge=0, description="备选路径索引"),
    service: RescueWorkflowService = Depends(get_service),
):
    """
    切换备选路径
    
    途中遇到障碍时，切换到备选路径。
    """
    return await service.switch_route(route_id, new_route_index)


@router.get("/navigation/{event_id}/risks", response_model=list[RiskPrediction])
async def get_risk_predictions(
    event_id: UUID,
    min_lng: float = Query(...),
    min_lat: float = Query(...),
    max_lng: float = Query(...),
    max_lat: float = Query(...),
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取风险预测
    
    AI预测指定区域内的风险（道路损毁、次生灾害等）。
    """
    area = {
        "min_lng": min_lng, "min_lat": min_lat,
        "max_lng": max_lng, "max_lat": max_lat,
    }
    return await service.get_risk_predictions(event_id, area)


@router.get("/navigation/{event_id}/safe-points", response_model=list[SafePoint])
async def get_safe_points(
    event_id: UUID,
    route_id: UUID = Query(...),
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取沿途安全点
    
    返回路径沿途的安全点（休息区、医疗站、物资点等）。
    """
    return await service.get_safe_points(event_id, route_id)


@router.post("/navigation/safe-points/confirm")
async def confirm_safe_point(
    data: SafePointConfirm,
    service: RescueWorkflowService = Depends(get_service),
):
    """确认安全点"""
    return await service.confirm_safe_point(data)


# ============================================================================
# 阶段3: 现场指挥
# ============================================================================

@router.get("/command/{event_id}/post-recommendation", response_model=CommandPostRecommendation)
async def get_command_post_recommendation(
    event_id: UUID,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取指挥所选址推荐
    
    AI根据地形、安全性、通信条件等推荐指挥所位置。
    """
    return await service.get_command_post_recommendation(event_id)


@router.post("/command/post/confirm")
async def confirm_command_post(
    scenario_id: UUID,
    data: CommandPostConfirm,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    确认指挥所位置
    
    指挥员确认并建立现场指挥所。
    """
    return await service.confirm_command_post(scenario_id, data)


@router.post("/command/uav-cluster")
async def control_uav_cluster(
    data: UAVClusterControl,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    无人机集群控制
    
    部署、召回、重新定位无人机集群，或设置搜索模式。
    """
    return await service.control_uav_cluster(data)


@router.get("/command/{event_id}/rescue-detections", response_model=list[RescuePointDetection])
async def get_rescue_point_detections(
    event_id: UUID,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取AI救援点识别结果
    
    获取AI从无人机图像等来源识别出的潜在救援点。
    """
    return await service.get_rescue_point_detections(event_id)


@router.post("/command/rescue-detections/confirm")
async def confirm_rescue_point_detection(
    scenario_id: UUID,
    data: RescuePointConfirm,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    确认救援点识别结果
    
    人工确认或否定AI识别的救援点。
    """
    return await service.confirm_rescue_point_detection(scenario_id, data)


# ============================================================================
# 阶段4: 救援作业
# ============================================================================

@router.post("/rescue/points", response_model=RescuePointResponse, status_code=201)
async def create_rescue_point(
    scenario_id: UUID,
    data: RescuePointCreate,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    手动添加救援点
    
    现场人员发现新的救援点时，手动创建。
    """
    return await service.create_rescue_point(scenario_id, data)


@router.put("/rescue/points/{point_id}", response_model=RescuePointResponse)
async def update_rescue_point(
    point_id: UUID,
    data: RescuePointUpdate,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    更新救援点状态
    
    更新救援进度、已救人数等信息。
    """
    return await service.update_rescue_point(point_id, data)


@router.get("/rescue/{event_id}/overview", response_model=CoordinationTracking)
async def get_coordination_overview(
    event_id: UUID,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取协同总览图
    
    返回所有救援点、队伍位置、车辆位置的汇总信息。
    """
    return await service.get_coordination_overview(event_id)


@router.post("/rescue/coordination")
async def update_coordination(
    scenario_id: UUID,
    data: CoordinationUpdate,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    更新协同状态
    
    上报队伍抵达、救援完成、资源请求等协同信息。
    """
    return await service.update_coordination(scenario_id, data)


# ============================================================================
# 阶段5: 评估总结
# ============================================================================

@router.post("/evaluation/generate", response_model=EvaluationReport)
async def generate_evaluation_report(
    data: EvaluationReportRequest,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    生成评估报告
    
    AI自动生成救援行动评估报告，包括时间线、资源使用、救援成果、经验教训等。
    """
    return await service.generate_evaluation_report(data)


@router.get("/evaluation/{event_id}/report", response_model=EvaluationReport)
async def get_evaluation_report(
    event_id: UUID,
    service: RescueWorkflowService = Depends(get_service),
):
    """获取评估报告"""
    report = await service.get_evaluation_report(event_id)
    if not report:
        from src.core.exceptions import NotFoundError
        raise NotFoundError("EvaluationReport", str(event_id))
    return report


# ============================================================================
# 操作手册
# ============================================================================

@router.get("/manuals/{event_id}/recommendations", response_model=list[ManualRecommendation])
async def get_manual_recommendations(
    event_id: UUID,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    获取相关操作手册推荐
    
    根据事件类型，AI推荐相关的操作手册。
    """
    return await service.get_manual_recommendations(event_id)


@router.post("/manuals/search", response_model=list[ManualRecommendation])
async def search_manuals(
    data: ManualSearchRequest,
    service: RescueWorkflowService = Depends(get_service),
):
    """
    搜索操作手册
    
    关键词搜索操作手册内容。
    """
    return await service.search_manuals(data)
