"""
前端任务API路由

接口路径: /tasks/*
对接前端任务相关操作
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.tasks.service import TaskService
from src.domains.frontend_api.common import ApiResponse
from src.agents import get_frontline_rescue_agent
from .schemas import (
    FrontendTask, TaskLogData, TaskLogCommitRequest,
    RescueTask, RescueDetailResponse, Location,
    RescuePoint, MultiRescueTaskDetail,
    UnitTask, EquipmentTask, TaskSendRequest,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["前端-任务"])


def get_task_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    """获取任务服务实例"""
    return TaskService(db)


STATUS_MAP_TO_FRONTEND = {
    "created": "PENDING",
    "assigned": "ASSIGNED",
    "accepted": "ASSIGNED",
    "in_progress": "IN_PROGRESS",
    "completed": "COMPLETED",
    "failed": "FAILED",
    "cancelled": "CANCELLED",
}

STATUS_MAP_FROM_FRONTEND = {
    "PENDING": "created",
    "ASSIGNED": "assigned",
    "IN_PROGRESS": "in_progress",
    "COMPLETED": "completed",
    "FAILED": "failed",
    "CANCELLED": "cancelled",
}


@router.post("/send", response_model=ApiResponse)
async def tasks_send(
    request: TaskSendRequest,
    service: TaskService = Depends(get_task_service),
) -> ApiResponse:
    """
    侦察任务指令下发
    
    将生成的侦察任务下发给相应设备执行
    """
    logger.info(f"任务下发, schemeId={request.id}, eventId={request.eventId}")
    
    task_count = sum(len(t.taskList) for t in request.task)
    logger.info(f"下发任务数量: {task_count}")
    
    return ApiResponse.success({"taskCount": task_count}, "任务下发成功")


@router.post("/task-list-detail", response_model=ApiResponse[list[FrontendTask]])
async def task_list_detail(
    service: TaskService = Depends(get_task_service),
) -> ApiResponse[list[FrontendTask]]:
    """
    获取任务列表 - 对接v2真实数据
    
    返回所有已下发任务的列表
    """
    logger.info("获取任务列表")
    
    try:
        tasks = await service.list(page=1, page_size=100)
        
        result = []
        for task in tasks.items:
            frontend_status = STATUS_MAP_TO_FRONTEND.get(task.status, "PENDING")
            
            # 构建任务日志
            log_list = [
                TaskLogData(
                    timestamp=task.created_at.isoformat() if task.created_at else "",
                    origin="系统",
                    description=f"任务创建: {task.title}"
                )
            ]
            
            # 添加分配日志
            if task.assignments:
                for assignment in task.assignments:
                    if assignment.assigned_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.assigned_at.isoformat(),
                            origin="调度员",
                            description=f"任务分配给: {assignment.assignee_name or '执行者'}"
                        ))
                    if assignment.accepted_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.accepted_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description="任务已接受"
                        ))
                    if assignment.started_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.started_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description="开始执行任务"
                        ))
                    if assignment.completed_at:
                        log_list.append(TaskLogData(
                            timestamp=assignment.completed_at.isoformat(),
                            origin=assignment.assignee_name or "执行者",
                            description=assignment.completion_summary or "任务已完成"
                        ))
            
            # 按时间排序日志
            log_list.sort(key=lambda x: x.timestamp)
            
            result.append(FrontendTask(
                id=str(task.id),
                title=task.title,
                description=task.description or "",
                status=frontend_status,
                createdAt=task.created_at.isoformat() if task.created_at else "",
                deadline=task.planned_end_at.isoformat() if task.planned_end_at else None,
                taskLogDataList=log_list,
            ))
        
        logger.info(f"返回任务数量: {len(result)}")
        return ApiResponse.success(result)
        
    except Exception as e:
        logger.exception(f"获取任务列表失败: {e}")
        return ApiResponse.success([])


@router.post("/task-log-commit", response_model=ApiResponse)
async def task_log_commit(
    request: TaskLogCommitRequest,
    service: TaskService = Depends(get_task_service),
) -> ApiResponse:
    """
    任务日志提交/状态更新
    
    记录任务状态变更，支持结束任务等操作
    """
    logger.info(f"任务状态更新, taskId={request.taskId}, status={request.status}")
    
    try:
        task_uuid = UUID(request.taskId)
        
        if request.status == "COMPLETED":
            await service.complete_direct(task_uuid, completion_summary=request.description)
            logger.info(f"任务完成, taskId={request.taskId}")
        elif request.status == "CANCELLED":
            await service.cancel(task_uuid, reason=request.description)
            logger.info(f"任务取消, taskId={request.taskId}")
        
        return ApiResponse.success(None, "操作成功")
        
    except ValueError as e:
        logger.warning(f"无效的任务ID: {e}")
        return ApiResponse.error(400, f"无效的任务ID: {str(e)}")
    except Exception as e:
        logger.exception(f"任务状态更新失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.post("/rescueTask", response_model=ApiResponse)
async def rescue_task(
    tasks: list[RescueTask],
    service: TaskService = Depends(get_task_service),
) -> ApiResponse:
    """
    救援任务指令下发
    
    将救援任务下发给相应单位和设备执行
    """
    logger.info(f"救援任务下发, 任务组数: {len(tasks)}")
    
    total_units = sum(len(t.units) for t in tasks)
    total_equipment = sum(len(t.equipmentList) for t in tasks)
    
    logger.info(f"救援单位数: {total_units}, 设备数: {total_equipment}")
    
    return ApiResponse.success({
        "unitCount": total_units,
        "equipmentCount": total_equipment,
    }, "救援任务下发成功")


class EventIdRequest(BaseModel):
    """事件ID请求"""
    eventId: str


# 优先级到level的映射
PRIORITY_LEVEL_MAP = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}

# 事件来源映射
SOURCE_TYPE_MAP = {
    "manual_report": "人工上报",
    "ai_detection": "AI识别",
    "sensor_alert": "传感器告警",
    "system_inference": "系统推演",
    "external_system": "外部系统",
}


@router.post("/multi-rescue-scheme", response_model=ApiResponse[list[RescuePoint]])
async def multi_rescue_scheme(
    scenarioId: str = Form(None),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[RescuePoint]]:
    """
    一线救援行动方案
    
    查询当前想定下所有未处理的事件（confirmed状态、无任务分配），并生成救援方案。
    
    业务逻辑：
    1. 查询所有confirmed状态且没有任务分配的事件
    2. 排除earthquake类型（地震主震信息）
    3. 对每个事件查询已有方案或生成默认方案描述
    4. 返回救援点列表供前端展示
    """
    logger.info(f"获取一线救援行动方案, scenarioId={scenarioId}")

    if not scenarioId:
        return ApiResponse.error(400, "scenarioId is required")

    try:
        agent = get_frontline_rescue_agent()
        result = await agent.plan(scenarioId)
    except Exception as e:  # noqa: BLE001
        logger.exception("获取一线救援行动方案失败")
        return ApiResponse.error(500, f"获取方案失败: {e}")

    if result.get("status") == "failed":
        errors = ", ".join(result.get("errors") or [])
        logger.error("FrontlineRescueAgent failed: %s", errors)
        return ApiResponse.error(500, f"前线救援调度失败: {errors or '未知错误'}")

    events = result.get("prioritized_events") or []
    if not events:
        logger.info("未找到待处理事件")
        return ApiResponse.success([])

    rescue_points: list[RescuePoint] = []

    for ev in events:
        lon = ev.get("longitude")
        lat = ev.get("latitude")
        if lon is None or lat is None:
            continue

        location = Location(longitude=float(lon), latitude=float(lat))

        bucket = str(ev.get("priority_bucket") or ev.get("priority") or "medium")
        level = PRIORITY_LEVEL_MAP.get(
            bucket,
            PRIORITY_LEVEL_MAP.get(str(ev.get("priority", "medium")), 3),
        )

        origin = SOURCE_TYPE_MAP.get(str(ev.get("source_type")), "系统")
        time_str = str(ev.get("reported_at") or datetime.now().isoformat())

        base_schema = _generate_default_scheme(
            event_type=str(ev.get("event_type", "other")),
            title=str(ev.get("title", "")),
            estimated_victims=int(ev.get("estimated_victims") or 0),
        )

        score = float(ev.get("score", 0.0) or 0.0)
        reasons = ev.get("reasons") or []
        header_lines = [f"[priority={bucket}, score={score:.2f}]"]
        if reasons:
            header_lines.append("原因:")
            header_lines.extend([f"- {r}" for r in reasons])
        schema_text = "\n".join(header_lines) + "\n\n" + base_schema

        rescue_point = RescuePoint(
            level=level,
            title=str(ev.get("title", "")),
            origin=origin,
            time=time_str,
            locationName=str(ev.get("address") or f"坐标({lon:.4f}, {lat:.4f})"),
            location=location,
            image="",
            schema_=schema_text,
            description=str(ev.get("description", "")),
        )
        rescue_points.append(rescue_point)

    logger.info(f"返回救援点数量: {len(rescue_points)}")
    return ApiResponse.success(rescue_points)


def _generate_default_scheme(event_type: str, title: str, estimated_victims: int) -> str:
    """根据事件类型生成默认救援方案描述"""
    schemes = {
        "trapped_person": f"立即调派搜救队携带生命探测仪进行搜救。预计被困{estimated_victims}人，需破拆工具和医疗支援。",
        "fire": "调派消防救援队进行灭火作业，同时组织人员疏散。注意防护装备和水源保障。",
        "flood": "调派水上救援队携带冲锋舟、救生设备进行救援。注意水流情况，确保救援人员安全。",
        "landslide": "调派搜救队和工程抢险队，使用生命探测仪搜索被埋人员。注意二次滑坡风险。",
        "building_collapse": f"调派消防救援队携带破拆工具、生命探测仪进行搜救。预计被困{estimated_victims}人。",
        "road_damage": "调派工程抢险队进行道路抢修，设置警示标志，引导车辆绕行。",
        "power_outage": "调派电力抢修队恢复供电，优先保障医院、指挥中心等重要设施。",
        "communication_lost": "调派通信保障队架设应急通信设备，恢复通信网络。",
        "hazmat_leak": "调派危化品处置队进行泄漏处置，划定警戒区域，组织群众疏散。",
        "epidemic": "调派医疗防疫队进行消杀处置，设置隔离区，做好人员防护。",
        "earthquake_secondary": f"调派综合救援力量处置次生灾害。预计受影响{estimated_victims}人。",
    }
    return schemes.get(event_type, f"针对{title}制定专项救援方案，调派相应救援力量。")


@router.post("/multi-rescue-task", response_model=ApiResponse[list[MultiRescueTaskDetail]])
async def multi_rescue_task(
    scenarioId: str = Form(None),
) -> ApiResponse[list[MultiRescueTaskDetail]]:
    """
    一线救援行动任务
    
    根据所有待处理事件的方案生成具体的执行任务
    """
    logger.info(f"生成一线救援行动任务, scenarioId={scenarioId}")

    if not scenarioId:
        return ApiResponse.error(400, "scenarioId is required")

    try:
        agent = get_frontline_rescue_agent()
        result = await agent.plan(scenarioId)
    except Exception as e:  # noqa: BLE001
        logger.exception("生成一线救援行动任务失败")
        return ApiResponse.error(500, f"生成任务失败: {e}")

    if result.get("status") == "failed":
        errors = ", ".join(result.get("errors") or [])
        logger.error("FrontlineRescueAgent failed: %s", errors)
        return ApiResponse.error(500, f"前线救援调度失败: {errors or '未知错误'}")

    events = result.get("prioritized_events") or []
    allocations = result.get("event_allocations") or []

    # 建立 event_id -> allocation 的索引，便于快速查找
    alloc_by_event: dict[str, Any] = {a.get("event_id"): a for a in allocations}

    details: list[MultiRescueTaskDetail] = []

    for ev in events:
        ev_id = str(ev.get("id") or "")
        if not ev_id:
            continue

        lon = ev.get("longitude")
        lat = ev.get("latitude")
        if lon is None or lat is None:
            continue

        location = Location(longitude=float(lon), latitude=float(lat))

        bucket = str(ev.get("priority_bucket") or ev.get("priority") or "medium")
        level = PRIORITY_LEVEL_MAP.get(
            bucket,
            PRIORITY_LEVEL_MAP.get(str(ev.get("priority", "medium")), 3),
        )

        alloc = alloc_by_event.get(ev_id) or {}
        teams = alloc.get("allocations") or []

        unit_tasks: list[UnitTask] = []
        for team in teams:
            eta = float(team.get("eta_minutes", 0.0) or 0.0)
            caps = ",".join(team.get("assigned_capabilities") or [])
            desc = f"执行针对“{ev.get('title', '')}”的救援任务，预计到达时间约{eta:.1f}分钟。能力: {caps or '未标明'}。"
            unit_tasks.append(
                UnitTask(
                    id=str(team.get("team_id", "")),
                    name=str(team.get("team_name", "")),
                    description=desc,
                    location=location,
                    supplieList=[],
                )
            )

        if not unit_tasks:
            # 没有分配到队伍时仍返回占位任务，供前端提示资源缺口
            unit_tasks.append(
                UnitTask(
                    id="",
                    name="暂无可用队伍",
                    description="当前未能为该事件找到满足约束条件的救援队伍，请指挥员人工调度或调整约束。",
                    location=location,
                    supplieList=[],
                )
            )

        detail = MultiRescueTaskDetail(
            level=level,
            title=str(ev.get("title", "")),
            rescueTask=[
                RescueTask(
                    units=unit_tasks,
                    equipmentList=[],
                )
            ],
        )
        details.append(detail)

    return ApiResponse.success(
        details,
        "多事件救援任务草案已生成，请指挥员在线下达指令前仔细审核，并通过 /tasks/rescueTask 接口明确下发执行任务。",
    )
