from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from .repository import TaskRepository
from .schemas import (
    TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, MyTasksResponse,
    TaskAssign, TaskProgressUpdate, TaskComplete, TaskReject, TaskReassign,
    AssignmentResponse, Location
)
from src.core.exceptions import NotFoundError, ConflictError


class TaskService:
    def __init__(self, db: AsyncSession):
        self.repo = TaskRepository(db)
    
    async def create(self, data: TaskCreate, created_by: Optional[UUID] = None) -> TaskResponse:
        task_code = await self.repo.get_next_task_code(data.scenario_id)
        task = await self.repo.create(data, task_code, created_by)
        return self._to_response(task)
    
    async def get_by_id(self, task_id: UUID) -> TaskResponse:
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        return self._to_response(task)
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        scheme_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> TaskListResponse:
        items, total = await self.repo.list(scenario_id, scheme_id, event_id, page, page_size, status, priority)
        return TaskListResponse(
            items=[self._to_response(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def get_my_tasks(
        self,
        assignee_type: str,
        assignee_id: UUID,
        status: Optional[str] = None,
    ) -> MyTasksResponse:
        """获取执行者的任务列表"""
        items = await self.repo.get_my_tasks(assignee_type, assignee_id, status)
        return MyTasksResponse(
            items=[self._to_response(t) for t in items],
            total=len(items),
        )
    
    async def update(self, task_id: UUID, data: TaskUpdate) -> TaskResponse:
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        if task.status in ("completed", "failed", "cancelled"):
            raise ConflictError("TK4005", f"Cannot update task in status: {task.status}")
        
        task = await self.repo.update(task, data)
        return self._to_response(task)
    
    async def assign(self, task_id: UUID, data: TaskAssign, assigned_by: Optional[UUID] = None) -> TaskResponse:
        """分配任务"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        if task.status in ("completed", "failed", "cancelled"):
            raise ConflictError("TK4006", f"Cannot assign task in status: {task.status}")
        
        await self.repo.add_assignment(
            task_id=task_id,
            assignee_type=data.assignee_type.value,
            assignee_id=data.assignee_id,
            assignee_name=data.assignee_name,
            assignment_reason=data.assignment_reason,
            assigned_by=assigned_by,
        )
        
        if task.status == "created":
            task = await self.repo.update_status(task, "assigned")
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def accept(self, task_id: UUID, assignee_type: str, assignee_id: UUID) -> TaskResponse:
        """接受任务"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        assignment = await self.repo.get_task_assignment(task_id, assignee_type, assignee_id)
        if not assignment:
            raise NotFoundError("TaskAssignment", f"task={task_id}, assignee={assignee_id}")
        
        if assignment.status != "pending":
            raise ConflictError("TK4007", f"Assignment not in pending status: {assignment.status}")
        
        await self.repo.accept_assignment(assignment)
        
        if task.status == "assigned":
            task = await self.repo.update_status(task, "accepted")
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def reject(self, task_id: UUID, assignee_type: str, assignee_id: UUID, data: TaskReject) -> TaskResponse:
        """拒绝任务"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        assignment = await self.repo.get_task_assignment(task_id, assignee_type, assignee_id)
        if not assignment:
            raise NotFoundError("TaskAssignment", f"task={task_id}, assignee={assignee_id}")
        
        await self.repo.reject_assignment(assignment, data.reason)
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def start(self, task_id: UUID, assignee_type: str, assignee_id: UUID) -> TaskResponse:
        """开始执行任务"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        assignment = await self.repo.get_task_assignment(task_id, assignee_type, assignee_id)
        if not assignment:
            raise NotFoundError("TaskAssignment", f"task={task_id}, assignee={assignee_id}")
        
        if assignment.status != "accepted":
            raise ConflictError("TK4008", "Must accept task before starting")
        
        await self.repo.start_assignment(assignment)
        task = await self.repo.update_status(task, "in_progress")
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def update_progress(
        self, task_id: UUID, assignee_type: str, assignee_id: UUID, data: TaskProgressUpdate
    ) -> TaskResponse:
        """更新任务进度"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        assignment = await self.repo.get_task_assignment(task_id, assignee_type, assignee_id)
        if not assignment:
            raise NotFoundError("TaskAssignment", f"task={task_id}, assignee={assignee_id}")
        
        await self.repo.update_assignment_progress(assignment, data.progress_percent, data.notes)
        task = await self.repo.update_progress(task, data.progress_percent)
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def complete(
        self, task_id: UUID, assignee_type: str, assignee_id: UUID, data: TaskComplete
    ) -> TaskResponse:
        """完成任务（需要assignee信息）"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        assignment = await self.repo.get_task_assignment(task_id, assignee_type, assignee_id)
        if not assignment:
            raise NotFoundError("TaskAssignment", f"task={task_id}, assignee={assignee_id}")
        
        await self.repo.complete_assignment(assignment, data.completion_summary)
        
        if data.rescued_count is not None:
            task.rescued_count = (task.rescued_count or 0) + data.rescued_count
        
        task = await self.repo.update_status(task, "completed")
        task = await self.repo.update_progress(task, 100)
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def complete_direct(
        self, task_id: UUID, completion_summary: Optional[str] = None, rescued_count: Optional[int] = None
    ) -> TaskResponse:
        """
        直接完成任务（无需assignee信息）
        
        适用场景:
        - 准备任务完成（无明确执行者）
        - 系统自动完成的任务
        - 批量完成操作
        """
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        if task.status in ("completed", "cancelled"):
            raise ConflictError("TK4011", f"任务已处于终态: {task.status}")
        
        if rescued_count is not None:
            task.rescued_count = (task.rescued_count or 0) + rescued_count
        
        task = await self.repo.update_status(task, "completed")
        task = await self.repo.update_progress(task, 100)
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def cancel(self, task_id: UUID, reason: str) -> TaskResponse:
        """取消任务"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        if task.status in ("completed", "cancelled"):
            raise ConflictError("TK4009", f"Cannot cancel task in status: {task.status}")
        
        task = await self.repo.update_status(task, "cancelled")
        
        task = await self.repo.get_by_id(task_id)
        return self._to_response(task)
    
    async def get_subtasks(
        self,
        task_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> TaskListResponse:
        """获取子任务列表"""
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        items, total = await self.repo.get_subtasks(task_id, page, page_size)
        return TaskListResponse(
            items=[self._to_response(t) for t in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def delete(self, task_id: UUID) -> None:
        task = await self.repo.get_by_id(task_id)
        if not task:
            raise NotFoundError("Task", str(task_id))
        
        if task.status not in ("created", "cancelled"):
            raise ConflictError("TK4010", "Can only delete created or cancelled tasks")
        
        await self.repo.delete(task)
    
    def _to_response(self, task) -> TaskResponse:
        target_location = None
        if task.target_location:
            from shapely import wkb
            point = wkb.loads(bytes(task.target_location.data))
            target_location = Location(longitude=point.x, latitude=point.y)
        
        return TaskResponse(
            id=task.id,
            scheme_id=task.scheme_id,
            scenario_id=task.scenario_id,
            event_id=task.event_id,
            task_code=task.task_code,
            task_type=task.task_type,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            target_location=target_location,
            target_address=task.target_address,
            planned_start_at=task.planned_start_at,
            planned_end_at=task.planned_end_at,
            actual_start_at=task.actual_start_at,
            actual_end_at=task.actual_end_at,
            estimated_duration_minutes=task.estimated_duration_minutes,
            instructions=task.instructions,
            requirements=task.requirements,
            rescued_count=task.rescued_count,
            progress_percent=task.progress_percent or 0,
            created_at=task.created_at,
            updated_at=task.updated_at,
            assignments=[self._assignment_to_response(a) for a in (task.assignments or [])],
        )
    
    def _assignment_to_response(self, assignment) -> AssignmentResponse:
        return AssignmentResponse(
            id=assignment.id,
            task_id=assignment.task_id,
            assignee_type=assignment.assignee_type,
            assignee_id=assignment.assignee_id,
            assignee_name=assignment.assignee_name,
            assignment_source=assignment.assignment_source,
            assignment_reason=assignment.assignment_reason,
            status=assignment.status,
            rejection_reason=assignment.rejection_reason,
            progress_percent=assignment.progress_percent or 0,
            execution_notes=assignment.execution_notes,
            completion_summary=assignment.completion_summary,
            assigned_at=assignment.assigned_at,
            accepted_at=assignment.accepted_at,
            completed_at=assignment.completed_at,
        )
