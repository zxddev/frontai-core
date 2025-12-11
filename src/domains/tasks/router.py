from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from uuid import UUID
import logging

from src.core.database import get_db
from .service import TaskService
from .schemas import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, MyTasksResponse,
    TaskAssign, TaskProgressUpdate, TaskComplete, TaskReject,
    TaskDetailResponse, TeamRealtimeStatus, Location, EventBasedTaskResponse
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_service(db: AsyncSession = Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(
    data: TaskCreate,
    service: TaskService = Depends(get_service),
):
    """创建任务"""
    return await service.create(data)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    scenario_id: Optional[UUID] = None,
    scheme_id: Optional[UUID] = None,
    event_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    service: TaskService = Depends(get_service),
):
    """获取任务列表"""
    return await service.list(scenario_id, scheme_id, event_id, page, page_size, status, priority)


@router.get("/my-tasks", response_model=MyTasksResponse)
async def get_my_tasks(
    assignee_type: str = Query(..., description="执行者类型: team/vehicle/device/user"),
    assignee_id: UUID = Query(..., description="执行者ID"),
    status: Optional[str] = None,
    service: TaskService = Depends(get_service),
):
    """获取执行者的任务列表"""
    return await service.get_my_tasks(assignee_type, assignee_id, status)


@router.get("/by-event/{event_id}", response_model=EventBasedTaskResponse)
async def get_task_by_event(
    event_id: UUID,
    service: TaskService = Depends(get_service),
    db: AsyncSession = Depends(get_db),
) -> EventBasedTaskResponse:
    """
    通过事件ID查询任务或事件详情

    APP端从救援点列表进入详情页时使用此接口
    救援点列表返回的是事件ID，此接口会：
    1. 查询该事件是否已有关联任务
    2. 有任务则返回任务详情（含队伍实时状态）
    3. 无任务则返回事件基本信息

    Args:
        event_id: 事件ID（来自 multi-rescue-scheme 接口的 RescuePoint.id）

    Returns:
        EventBasedTaskResponse: 包含 has_task 标识和任务/事件详情
    """
    logger.info(f"[by-event] 查询事件关联任务: event_id={event_id}")

    # 查询事件基本信息
    event_sql = text("""
        SELECT
            id, event_code, event_type, title, description,
            address, status, priority, estimated_victims, reported_at,
            ST_X(location::geometry) as lng,
            ST_Y(location::geometry) as lat
        FROM operational_v2.events_v2
        WHERE id = :event_id
    """)
    event_result = await db.execute(event_sql, {"event_id": str(event_id)})
    event_row = event_result.fetchone()

    if not event_row:
        logger.warning(f"[by-event] 事件不存在: event_id={event_id}")
        raise HTTPException(status_code=404, detail="事件不存在")

    # 构建事件位置
    event_location: Optional[Location] = None
    if event_row.lng is not None and event_row.lat is not None:
        event_location = Location(longitude=event_row.lng, latitude=event_row.lat)

    # 查询关联任务（取最新的非取消/失败任务）
    task_sql = text("""
        SELECT id FROM operational_v2.tasks_v2
        WHERE event_id = :event_id
          AND status NOT IN ('cancelled', 'failed')
        ORDER BY created_at DESC
        LIMIT 1
    """)
    task_result = await db.execute(task_sql, {"event_id": str(event_id)})
    task_row = task_result.fetchone()

    if task_row:
        # 有关联任务，调用现有的任务详情逻辑
        task_id = UUID(str(task_row.id))
        logger.info(f"[by-event] 事件已有任务: event_id={event_id}, task_id={task_id}")

        base_response = await service.get_by_id(task_id)
        team_realtime: list[TeamRealtimeStatus] = []

        # 查询队伍实时状态（复用 get_task 的逻辑）
        try:
            realtime_sql = text("""
                SELECT
                    ta.assignee_id as team_id,
                    ta.assignee_name as team_name,
                    ta.mission_detail,
                    ms.id as session_id,
                    ST_X(ms.current_position::geometry) as lng,
                    ST_Y(ms.current_position::geometry) as lat,
                    ms.status as movement_status,
                    ms.eta,
                    ms.updated_at as last_update,
                    rt.status as team_status
                FROM operational_v2.task_assignments_v2 ta
                LEFT JOIN operational_v2.movement_sessions_v2 ms
                    ON ms.team_id = ta.assignee_id
                    AND ms.status IN ('active', 'paused')
                LEFT JOIN operational_v2.rescue_teams_v2 rt
                    ON rt.id = ta.assignee_id
                WHERE ta.task_id = :task_id
                    AND ta.assignee_type = 'team'
            """)
            realtime_result = await db.execute(realtime_sql, {"task_id": str(task_id)})
            realtime_rows = realtime_result.fetchall()

            for row in realtime_rows:
                location: Optional[Location] = None
                if row.lng is not None and row.lat is not None:
                    location = Location(longitude=row.lng, latitude=row.lat)

                eta_minutes = 0.0
                if row.eta:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    if row.eta > now:
                        eta_minutes = (row.eta - now).total_seconds() / 60

                communication_status = "online" if row.team_status == "deployed" else "unknown"
                movement_status = row.movement_status or "stationary"

                # 解析mission_detail（JSONB字段）
                mission_detail = None
                if row.mission_detail:
                    mission_detail = row.mission_detail if isinstance(row.mission_detail, dict) else None

                team_realtime.append(TeamRealtimeStatus(
                    team_id=row.team_id,
                    team_name=row.team_name or "",
                    location=location,
                    eta_minutes=eta_minutes,
                    communication_status=communication_status,
                    movement_status=movement_status,
                    last_update=row.last_update,
                    mission_detail=mission_detail,
                ))
        except Exception as e:
            logger.warning(f"[by-event] 查询队伍实时状态失败: task_id={task_id}, error={e}")

        task_detail = TaskDetailResponse(
            **base_response.model_dump(),
            team_realtime=team_realtime,
        )

        return EventBasedTaskResponse(
            has_task=True,
            task=task_detail,
            event_id=event_id,
            event_title=str(event_row.title or ""),
            event_description=event_row.description,
            event_type=str(event_row.event_type or "other"),
            event_status=str(event_row.status or "pending"),
            event_priority=str(event_row.priority or "medium"),
            event_address=event_row.address,
            event_location=event_location,
            estimated_victims=event_row.estimated_victims or 0,
            reported_at=event_row.reported_at,
        )

    # 无关联任务，返回事件信息
    logger.info(f"[by-event] 事件无关联任务: event_id={event_id}")
    return EventBasedTaskResponse(
        has_task=False,
        task=None,
        event_id=event_id,
        event_title=str(event_row.title or ""),
        event_description=event_row.description,
        event_type=str(event_row.event_type or "other"),
        event_status=str(event_row.status or "pending"),
        event_priority=str(event_row.priority or "medium"),
        event_address=event_row.address,
        event_location=event_location,
        estimated_victims=event_row.estimated_victims or 0,
        reported_at=event_row.reported_at,
    )


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    service: TaskService = Depends(get_service),
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务详情（含队伍实时状态）

    返回任务基本信息和分配队伍的实时位置、ETA、通信状态
    """
    base_response = await service.get_by_id(task_id)

    team_realtime: list[TeamRealtimeStatus] = []

    try:
        realtime_sql = text("""
            SELECT
                ta.assignee_id as team_id,
                ta.assignee_name as team_name,
                ta.mission_detail,
                ms.id as session_id,
                ST_X(ms.current_position::geometry) as lng,
                ST_Y(ms.current_position::geometry) as lat,
                ms.status as movement_status,
                ms.eta,
                ms.updated_at as last_update,
                rt.status as team_status
            FROM operational_v2.task_assignments_v2 ta
            LEFT JOIN operational_v2.movement_sessions_v2 ms
                ON ms.team_id = ta.assignee_id
                AND ms.status IN ('active', 'paused')
            LEFT JOIN operational_v2.rescue_teams_v2 rt
                ON rt.id = ta.assignee_id
            WHERE ta.task_id = :task_id
                AND ta.assignee_type = 'team'
        """)
        result = await db.execute(realtime_sql, {"task_id": str(task_id)})
        rows = result.fetchall()

        for row in rows:
            location = None
            if row.lng is not None and row.lat is not None:
                location = Location(longitude=row.lng, latitude=row.lat)

            eta_minutes = 0.0
            if row.eta:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                if row.eta > now:
                    eta_minutes = (row.eta - now).total_seconds() / 60

            communication_status = "online" if row.team_status == "deployed" else "unknown"
            movement_status = row.movement_status or "stationary"

            # 解析mission_detail（JSONB字段）
            mission_detail = None
            if row.mission_detail:
                mission_detail = row.mission_detail if isinstance(row.mission_detail, dict) else None

            team_realtime.append(TeamRealtimeStatus(
                team_id=row.team_id,
                team_name=row.team_name or "",
                location=location,
                eta_minutes=eta_minutes,
                communication_status=communication_status,
                movement_status=movement_status,
                last_update=row.last_update,
                mission_detail=mission_detail,
            ))

        logger.info(f"[TaskDetail] task_id={task_id}, 队伍实时状态数={len(team_realtime)}")

    except Exception as e:
        logger.warning(f"[TaskDetail] 查询队伍实时状态失败: task_id={task_id}, error={e}")

    return TaskDetailResponse(
        **base_response.model_dump(),
        team_realtime=team_realtime,
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    data: TaskUpdate,
    service: TaskService = Depends(get_service),
):
    """更新任务"""
    return await service.update(task_id, data)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: UUID,
    data: TaskAssign,
    service: TaskService = Depends(get_service),
):
    """分配任务给执行者"""
    return await service.assign(task_id, data)


@router.post("/{task_id}/accept", response_model=TaskResponse)
async def accept_task(
    task_id: UUID,
    assignee_type: str = Query(...),
    assignee_id: UUID = Query(...),
    service: TaskService = Depends(get_service),
):
    """接受任务"""
    return await service.accept(task_id, assignee_type, assignee_id)


@router.post("/{task_id}/reject", response_model=TaskResponse)
async def reject_task(
    task_id: UUID,
    data: TaskReject,
    assignee_type: str = Query(...),
    assignee_id: UUID = Query(...),
    service: TaskService = Depends(get_service),
):
    """拒绝任务"""
    return await service.reject(task_id, assignee_type, assignee_id, data)


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: UUID,
    assignee_type: str = Query(...),
    assignee_id: UUID = Query(...),
    service: TaskService = Depends(get_service),
):
    """开始执行任务"""
    return await service.start(task_id, assignee_type, assignee_id)


@router.post("/{task_id}/progress", response_model=TaskResponse)
async def update_task_progress(
    task_id: UUID,
    data: TaskProgressUpdate,
    assignee_type: str = Query(...),
    assignee_id: UUID = Query(...),
    service: TaskService = Depends(get_service),
):
    """更新任务进度"""
    return await service.update_progress(task_id, assignee_type, assignee_id, data)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    data: TaskComplete,
    assignee_type: str = Query(...),
    assignee_id: UUID = Query(...),
    service: TaskService = Depends(get_service),
):
    """完成任务"""
    return await service.complete(task_id, assignee_type, assignee_id, data)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: UUID,
    reason: str = Query(..., description="取消原因"),
    service: TaskService = Depends(get_service),
):
    """取消任务"""
    return await service.cancel(task_id, reason)


@router.get("/{task_id}/subtasks", response_model=TaskListResponse)
async def get_subtasks(
    task_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service: TaskService = Depends(get_service),
):
    """
    获取子任务列表
    
    返回指定任务的所有子任务（parent_task_id = task_id）。
    支持分页，默认按创建时间升序排列。
    """
    return await service.get_subtasks(task_id, page, page_size)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    service: TaskService = Depends(get_service),
):
    """删除任务（仅created/cancelled可删除）"""
    await service.delete(task_id)
