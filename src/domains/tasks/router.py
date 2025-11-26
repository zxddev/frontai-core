from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from src.core.database import get_db
from .service import TaskService
from .schemas import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, MyTasksResponse,
    TaskAssign, TaskProgressUpdate, TaskComplete, TaskReject
)


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


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    service: TaskService = Depends(get_service),
):
    """获取任务详情"""
    return await service.get_by_id(task_id)


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
