"""
救援流程数据访问层

提供RescuePoint和EvaluationReport的CRUD和聚合查询操作
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import RescuePoint, RescuePointTeamAssignment, RescuePointProgress, EvaluationReport


logger = logging.getLogger(__name__)


class RescuePointRepository:
    """救援点数据访问"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    # ==================== 基础CRUD ====================
    
    async def create(
        self,
        scenario_id: UUID,
        event_id: UUID,
        name: str,
        point_type: str,
        location_lng: float,
        location_lat: float,
        priority: str = "medium",
        description: Optional[str] = None,
        address: Optional[str] = None,
        estimated_victims: int = 0,
        detection_id: Optional[UUID] = None,
        detection_confidence: Optional[float] = None,
        detection_source: str = "manual",
        source_image_url: Optional[str] = None,
        reported_by: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> RescuePoint:
        """创建救援点"""
        location_wkt = f"POINT({location_lng} {location_lat})"
        
        rescue_point = RescuePoint(
            scenario_id=scenario_id,
            event_id=event_id,
            name=name,
            point_type=point_type,
            priority=priority,
            description=description,
            location=location_wkt,
            address=address,
            estimated_victims=estimated_victims,
            rescued_count=0,
            status="pending",
            detection_id=detection_id,
            detection_confidence=detection_confidence,
            detection_source=detection_source,
            source_image_url=source_image_url,
            reported_by=reported_by,
            notes=notes,
        )
        
        self._db.add(rescue_point)
        await self._db.flush()
        await self._db.refresh(rescue_point)
        
        logger.info(f"创建救援点: id={rescue_point.id}, name={name}, event_id={event_id}")
        return rescue_point
    
    async def get_by_id(self, point_id: UUID) -> Optional[RescuePoint]:
        """根据ID获取救援点"""
        result = await self._db.execute(
            select(RescuePoint)
            .options(selectinload(RescuePoint.team_assignments))
            .where(RescuePoint.id == point_id)
        )
        return result.scalar_one_or_none()
    
    async def update(
        self,
        rescue_point: RescuePoint,
        status: Optional[str] = None,
        rescued_count: Optional[int] = None,
        notes: Optional[str] = None,
        recorded_by: Optional[UUID] = None,
    ) -> RescuePoint:
        """更新救援点"""
        # 记录变更前的值，用于进度追踪
        old_status = rescue_point.status
        old_rescued_count = rescue_point.rescued_count
        
        if status is not None:
            rescue_point.status = status
        if rescued_count is not None:
            rescue_point.rescued_count = rescued_count
        if notes is not None:
            rescue_point.notes = notes
        
        await self._db.flush()
        await self._db.refresh(rescue_point)
        
        logger.info(f"更新救援点: id={rescue_point.id}, status={old_status}->{status}, rescued={old_rescued_count}->{rescued_count}")
        return rescue_point
    
    async def delete(self, rescue_point: RescuePoint) -> None:
        """删除救援点"""
        await self._db.delete(rescue_point)
        await self._db.flush()
        logger.info(f"删除救援点: id={rescue_point.id}")
    
    # ==================== 查询方法 ====================
    
    async def list_by_event(
        self,
        event_id: UUID,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> list[RescuePoint]:
        """按事件ID查询救援点列表"""
        query = (
            select(RescuePoint)
            .options(selectinload(RescuePoint.team_assignments))
            .where(RescuePoint.event_id == event_id)
        )
        
        if status:
            query = query.where(RescuePoint.status == status)
        if priority:
            query = query.where(RescuePoint.priority == priority)
        
        query = query.order_by(
            # 按优先级排序: critical > high > medium > low
            func.case(
                (RescuePoint.priority == "critical", 1),
                (RescuePoint.priority == "high", 2),
                (RescuePoint.priority == "medium", 3),
                else_=4
            ),
            RescuePoint.created_at.asc()
        )
        
        result = await self._db.execute(query)
        return list(result.scalars().all())
    
    async def list_by_scenario(
        self,
        scenario_id: UUID,
        status: Optional[str] = None,
    ) -> list[RescuePoint]:
        """按想定ID查询救援点列表"""
        query = (
            select(RescuePoint)
            .options(selectinload(RescuePoint.team_assignments))
            .where(RescuePoint.scenario_id == scenario_id)
        )
        
        if status:
            query = query.where(RescuePoint.status == status)
        
        query = query.order_by(RescuePoint.created_at.desc())
        
        result = await self._db.execute(query)
        return list(result.scalars().all())
    
    # ==================== 队伍指派 ====================
    
    async def assign_team(
        self,
        rescue_point_id: UUID,
        team_id: UUID,
        assigned_by: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> RescuePointTeamAssignment:
        """指派队伍到救援点"""
        assignment = RescuePointTeamAssignment(
            rescue_point_id=rescue_point_id,
            team_id=team_id,
            assigned_by=assigned_by,
            notes=notes,
        )
        self._db.add(assignment)
        await self._db.flush()
        
        logger.info(f"指派队伍: rescue_point={rescue_point_id}, team={team_id}")
        return assignment
    
    async def unassign_team(
        self,
        rescue_point_id: UUID,
        team_id: UUID,
    ) -> None:
        """取消队伍指派"""
        result = await self._db.execute(
            select(RescuePointTeamAssignment).where(
                and_(
                    RescuePointTeamAssignment.rescue_point_id == rescue_point_id,
                    RescuePointTeamAssignment.team_id == team_id,
                )
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment:
            await self._db.delete(assignment)
            await self._db.flush()
            logger.info(f"取消队伍指派: rescue_point={rescue_point_id}, team={team_id}")
    
    async def get_assigned_teams(self, rescue_point_id: UUID) -> list[UUID]:
        """获取救援点已指派的队伍ID列表"""
        result = await self._db.execute(
            select(RescuePointTeamAssignment.team_id)
            .where(RescuePointTeamAssignment.rescue_point_id == rescue_point_id)
        )
        return [row[0] for row in result.fetchall()]
    
    # ==================== 进度记录 ====================
    
    async def add_progress_record(
        self,
        rescue_point_id: UUID,
        progress_type: str,
        previous_value: Optional[dict[str, Any]] = None,
        new_value: Optional[dict[str, Any]] = None,
        recorded_by: Optional[UUID] = None,
    ) -> RescuePointProgress:
        """添加进度记录"""
        record = RescuePointProgress(
            rescue_point_id=rescue_point_id,
            progress_type=progress_type,
            previous_value=previous_value,
            new_value=new_value,
            recorded_by=recorded_by,
        )
        self._db.add(record)
        await self._db.flush()
        await self._db.refresh(record)
        
        logger.info(f"添加进度记录: rescue_point={rescue_point_id}, type={progress_type}")
        return record
    
    async def get_progress_records(
        self,
        rescue_point_id: UUID,
        limit: int = 50,
    ) -> list[RescuePointProgress]:
        """获取救援点进度记录"""
        result = await self._db.execute(
            select(RescuePointProgress)
            .where(RescuePointProgress.rescue_point_id == rescue_point_id)
            .order_by(RescuePointProgress.recorded_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    # ==================== 统计查询 ====================
    
    async def get_statistics_by_event(self, event_id: UUID) -> dict[str, Any]:
        """获取事件的救援点统计"""
        # 总数
        total_result = await self._db.execute(
            select(func.count(RescuePoint.id))
            .where(RescuePoint.event_id == event_id)
        )
        total = total_result.scalar() or 0
        
        # 按状态统计
        status_counts: dict[str, int] = {}
        for status in ["pending", "in_progress", "completed", "cancelled"]:
            result = await self._db.execute(
                select(func.count(RescuePoint.id))
                .where(and_(
                    RescuePoint.event_id == event_id,
                    RescuePoint.status == status
                ))
            )
            status_counts[status] = result.scalar() or 0
        
        # 按优先级统计
        priority_counts: dict[str, int] = {}
        for priority in ["low", "medium", "high", "critical"]:
            result = await self._db.execute(
                select(func.count(RescuePoint.id))
                .where(and_(
                    RescuePoint.event_id == event_id,
                    RescuePoint.priority == priority
                ))
            )
            priority_counts[priority] = result.scalar() or 0
        
        # 人员统计
        victims_result = await self._db.execute(
            select(
                func.sum(RescuePoint.estimated_victims),
                func.sum(RescuePoint.rescued_count)
            ).where(RescuePoint.event_id == event_id)
        )
        victims_row = victims_result.fetchone()
        total_estimated = victims_row[0] or 0 if victims_row else 0
        total_rescued = victims_row[1] or 0 if victims_row else 0
        
        # 计算进度百分比
        progress_percent = 0.0
        if total_estimated > 0:
            progress_percent = round(total_rescued / total_estimated * 100, 2)
        
        return {
            "total_points": total,
            "by_status": status_counts,
            "by_priority": priority_counts,
            "total_estimated_victims": total_estimated,
            "total_rescued": total_rescued,
            "rescue_progress_percent": progress_percent,
        }


class EvaluationReportRepository:
    """评估报告数据访问"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(
        self,
        event_id: UUID,
        scenario_id: UUID,
        report_data: dict[str, Any],
        generated_by: str = "ai_generated",
        generated_at: Optional[datetime] = None,
    ) -> EvaluationReport:
        """创建评估报告"""
        report = EvaluationReport(
            event_id=event_id,
            scenario_id=scenario_id,
            report_data=report_data,
            generated_by=generated_by,
            generated_at=generated_at or datetime.utcnow(),
        )
        self._db.add(report)
        await self._db.flush()
        await self._db.refresh(report)
        
        logger.info(f"创建评估报告: id={report.id}, event_id={event_id}")
        return report
    
    async def get_by_event_id(self, event_id: UUID) -> Optional[EvaluationReport]:
        """根据事件ID获取评估报告"""
        result = await self._db.execute(
            select(EvaluationReport).where(EvaluationReport.event_id == event_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, report_id: UUID) -> Optional[EvaluationReport]:
        """根据报告ID获取评估报告"""
        result = await self._db.execute(
            select(EvaluationReport).where(EvaluationReport.id == report_id)
        )
        return result.scalar_one_or_none()
    
    async def update(
        self,
        report: EvaluationReport,
        report_data: Optional[dict[str, Any]] = None,
        generated_by: Optional[str] = None,
    ) -> EvaluationReport:
        """更新评估报告"""
        if report_data is not None:
            report.report_data = report_data
        if generated_by is not None:
            report.generated_by = generated_by
        
        await self._db.flush()
        await self._db.refresh(report)
        
        logger.info(f"更新评估报告: id={report.id}")
        return report
    
    async def upsert(
        self,
        event_id: UUID,
        scenario_id: UUID,
        report_data: dict[str, Any],
        generated_by: str = "ai_generated",
    ) -> EvaluationReport:
        """创建或更新评估报告"""
        existing = await self.get_by_event_id(event_id)
        if existing:
            return await self.update(existing, report_data, generated_by)
        return await self.create(event_id, scenario_id, report_data, generated_by)
