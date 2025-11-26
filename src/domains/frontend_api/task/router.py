"""
前端任务API路由

接口路径: /tasks/*
对接前端任务相关操作
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.tasks.service import TaskService
from src.domains.frontend_api.common import ApiResponse
from src.domains.frontend_api.scheme.schemas import TaskSendRequest
from .schemas import (
    FrontendTask, TaskLogData, TaskLogCommitRequest,
    RescueTask, RescueDetailResponse, Location,
    RescuePoint, MultiRescueTaskDetail,
    UnitTask, EquipmentTask,
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


@router.post("/multi-rescue-scheme", response_model=ApiResponse[list[RescuePoint]])
async def multi_rescue_scheme(
    request: EventIdRequest,
) -> ApiResponse[list[RescuePoint]]:
    """
    一线救援行动方案
    
    获取多个救援点的汇总救援方案
    """
    logger.info(f"获取一线救援行动方案, eventId={request.eventId}")
    
    mock_points = [
        RescuePoint(
            level=1,
            title="居民楼倒塌救援点",
            origin="无人机侦察",
            time=datetime.now().isoformat(),
            locationName="新华路123号居民楼",
            location=Location(longitude=104.0657, latitude=30.6595),
            image="",
            schema_="立即调派消防救援队，携带生命探测仪、破拆工具进行搜救。预计被困人员5-10人。",
            description="6层居民楼部分倒塌，多人被困"
        ),
        RescuePoint(
            level=2,
            title="学校疏散救援点",
            origin="群众报告",
            time=datetime.now().isoformat(),
            locationName="阳光小学",
            location=Location(longitude=104.0667, latitude=30.6605),
            image="",
            schema_="调派救护车和医疗队，协助学校师生有序疏散。预计需疏散人员300人。",
            description="学校建筑受损，需协助疏散"
        ),
    ]
    
    return ApiResponse.success(mock_points)


@router.post("/multi-rescue-task", response_model=ApiResponse[list[MultiRescueTaskDetail]])
async def multi_rescue_task(
    request: EventIdRequest,
) -> ApiResponse[list[MultiRescueTaskDetail]]:
    """
    一线救援行动任务
    
    根据多个救援点的方案生成具体的执行任务
    """
    logger.info(f"生成一线救援行动任务, eventId={request.eventId}")
    
    mock_tasks = [
        MultiRescueTaskDetail(
            level=1,
            title="居民楼倒塌救援",
            rescueTask=[
                RescueTask(
                    units=[
                        UnitTask(
                            id="unit-1",
                            name="消防救援一中队",
                            description="负责搜救被困人员",
                            location=Location(longitude=104.0657, latitude=30.6595),
                            supplieList=["生命探测仪", "破拆工具", "担架"]
                        )
                    ],
                    equipmentList=[
                        EquipmentTask(
                            deviceName="搜救机器狗A",
                            deviceType="四足机器人",
                            carryingModule="生命探测+通信",
                            timeConsuming="60分钟",
                            searchRoute="倒塌区域逐层搜索"
                        )
                    ]
                )
            ]
        ),
        MultiRescueTaskDetail(
            level=2,
            title="学校疏散救援",
            rescueTask=[
                RescueTask(
                    units=[
                        UnitTask(
                            id="unit-2",
                            name="医疗救护队",
                            description="负责伤员救治和疏散",
                            location=Location(longitude=104.0667, latitude=30.6605),
                            supplieList=["急救包", "担架", "药品"]
                        )
                    ],
                    equipmentList=[]
                )
            ]
        ),
    ]
    
    return ApiResponse.success(mock_tasks)
