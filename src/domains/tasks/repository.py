from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from uuid import UUID
from datetime import datetime

from .models import Task, TaskAssignment
from .schemas import TaskCreate, TaskUpdate, Location


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, data: TaskCreate, task_code: str, created_by: Optional[UUID] = None) -> Task:
        target_location_wkt = None
        if data.target_location:
            target_location_wkt = f"POINT({data.target_location.longitude} {data.target_location.latitude})"
        
        task = Task(
            scheme_id=data.scheme_id,
            scenario_id=data.scenario_id,
            event_id=data.event_id,
            task_code=task_code,
            task_type=data.task_type.value,
            title=data.title,
            description=data.description,
            priority=data.priority.value,
            target_location=target_location_wkt,
            target_address=data.target_address,
            planned_start_at=data.planned_start_at,
            planned_end_at=data.planned_end_at,
            estimated_duration_minutes=data.estimated_duration_minutes,
            instructions=data.instructions,
            requirements=data.requirements or {},
            created_by=created_by,
            status="created",
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)
        return task
    
    async def get_by_id(self, task_id: UUID) -> Optional[Task]:
        result = await self.db.execute(
            select(Task)
            .options(selectinload(Task.assignments))
            .where(Task.id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        scheme_id: Optional[UUID] = None,
        event_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> tuple[list[Task], int]:
        query = select(Task).options(selectinload(Task.assignments))
        count_query = select(func.count(Task.id))
        
        if scenario_id:
            query = query.where(Task.scenario_id == scenario_id)
            count_query = count_query.where(Task.scenario_id == scenario_id)
        
        if scheme_id:
            query = query.where(Task.scheme_id == scheme_id)
            count_query = count_query.where(Task.scheme_id == scheme_id)
        
        if event_id:
            query = query.where(Task.event_id == event_id)
            count_query = count_query.where(Task.event_id == event_id)
        
        if status:
            query = query.where(Task.status == status)
            count_query = count_query.where(Task.status == status)
        
        if priority:
            query = query.where(Task.priority == priority)
            count_query = count_query.where(Task.priority == priority)
        
        query = query.order_by(Task.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()
        
        return items, total
    
    async def get_my_tasks(
        self,
        assignee_type: str,
        assignee_id: UUID,
        status: Optional[str] = None,
    ) -> list[Task]:
        """获取执行者的任务"""
        assignment_query = select(TaskAssignment.task_id).where(
            TaskAssignment.assignee_type == assignee_type,
            TaskAssignment.assignee_id == assignee_id,
        )
        if status:
            assignment_query = assignment_query.where(TaskAssignment.status == status)
        
        result = await self.db.execute(
            select(Task)
            .options(selectinload(Task.assignments))
            .where(Task.id.in_(assignment_query))
            .order_by(Task.priority.desc(), Task.created_at.asc())
        )
        return list(result.scalars().all())
    
    async def update(self, task: Task, data: TaskUpdate) -> Task:
        update_data = data.model_dump(exclude_unset=True)
        
        if "target_location" in update_data and update_data["target_location"]:
            loc = update_data.pop("target_location")
            task.target_location = f"POINT({loc['longitude']} {loc['latitude']})"
        
        for key, value in update_data.items():
            if value is not None:
                setattr(task, key, value)
        
        await self.db.flush()
        await self.db.refresh(task)
        return task
    
    async def update_status(self, task: Task, status: str) -> Task:
        task.status = status
        if status == "in_progress" and not task.actual_start_at:
            task.actual_start_at = datetime.utcnow()
        elif status in ("completed", "failed"):
            task.actual_end_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(task)
        return task
    
    async def update_progress(self, task: Task, progress: int) -> Task:
        task.progress_percent = progress
        await self.db.flush()
        await self.db.refresh(task)
        return task
    
    async def delete(self, task: Task) -> None:
        await self.db.delete(task)
        await self.db.flush()
    
    async def get_next_task_code(self, scenario_id: UUID) -> str:
        result = await self.db.execute(
            select(func.count(Task.id)).where(Task.scenario_id == scenario_id)
        )
        count = result.scalar() or 0
        return f"TSK-{count + 1:04d}"
    
    async def add_assignment(
        self,
        task_id: UUID,
        assignee_type: str,
        assignee_id: UUID,
        assignee_name: str,
        assignment_reason: Optional[str] = None,
        assigned_by: Optional[UUID] = None,
        source: str = "human_assigned",
    ) -> TaskAssignment:
        assignment = TaskAssignment(
            task_id=task_id,
            assignee_type=assignee_type,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            assignment_reason=assignment_reason,
            assigned_by=assigned_by,
            assignment_source=source,
            status="pending",
        )
        self.db.add(assignment)
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def get_assignment(self, assignment_id: UUID) -> Optional[TaskAssignment]:
        result = await self.db.execute(
            select(TaskAssignment).where(TaskAssignment.id == assignment_id)
        )
        return result.scalar_one_or_none()
    
    async def get_task_assignment(self, task_id: UUID, assignee_type: str, assignee_id: UUID) -> Optional[TaskAssignment]:
        result = await self.db.execute(
            select(TaskAssignment).where(
                TaskAssignment.task_id == task_id,
                TaskAssignment.assignee_type == assignee_type,
                TaskAssignment.assignee_id == assignee_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def accept_assignment(self, assignment: TaskAssignment) -> TaskAssignment:
        assignment.status = "accepted"
        assignment.accepted_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def reject_assignment(self, assignment: TaskAssignment, reason: str) -> TaskAssignment:
        assignment.status = "rejected"
        assignment.rejection_reason = reason
        assignment.rejected_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def start_assignment(self, assignment: TaskAssignment) -> TaskAssignment:
        assignment.status = "executing"
        assignment.started_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def update_assignment_progress(self, assignment: TaskAssignment, progress: int, notes: Optional[str]) -> TaskAssignment:
        assignment.progress_percent = progress
        if notes:
            assignment.execution_notes = notes
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def complete_assignment(self, assignment: TaskAssignment, summary: str) -> TaskAssignment:
        assignment.status = "completed"
        assignment.progress_percent = 100
        assignment.completion_summary = summary
        assignment.completed_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def fail_assignment(self, assignment: TaskAssignment, reason: str) -> TaskAssignment:
        assignment.status = "failed"
        assignment.completion_summary = reason
        assignment.completed_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(assignment)
        return assignment
    
    async def get_subtasks(
        self,
        parent_task_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Task], int]:
        """获取子任务列表"""
        query = (
            select(Task)
            .options(selectinload(Task.assignments))
            .where(Task.parent_task_id == parent_task_id)
            .order_by(Task.created_at.asc())
        )
        
        count_query = select(func.count(Task.id)).where(Task.parent_task_id == parent_task_id)
        
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
