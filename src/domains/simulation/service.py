"""
仿真推演服务

架构说明：
- 仿真使用真实数据表，启动时创建 SAVEPOINT
- 事件注入直接调用真实的 EventService
- 仿真结束后 ROLLBACK TO SAVEPOINT 还原数据
"""
from __future__ import annotations

import asyncio
import logging
import uuid as uuid_lib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, List
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError
from .schemas import (
    SimulationStatus, SimulationSourceType,
    SimulationScenarioCreate, SimulationScenarioResponse, SimulationListResponse,
    InjectionEventCreate, ScheduledInjection, InjectionQueueResponse,
    ImmediateInjectionRequest, EventTemplate,
    TimeScaleUpdateRequest, SimulationTimeResponse,
    AssessmentCreateRequest, AssessmentResponse, AssessmentResult, AssessmentGrade,
)
from .models import SimulationScenario, DrillAssessment
from .clock import SimulationClock

logger = logging.getLogger(__name__)


def _get_stomp_broker():
    """延迟导入避免循环依赖"""
    from src.core.stomp.broker import stomp_broker
    return stomp_broker


def _get_event_service(db: AsyncSession):
    """延迟导入避免循环依赖"""
    from src.domains.events.service import EventService
    return EventService(db)


class SimulationService:
    """
    仿真推演服务
    
    核心功能：
    1. 仿真场景CRUD
    2. 仿真生命周期管理（启动/暂停/恢复/停止）
    3. 时间控制（倍率调整）
    4. 事件注入（直接调用真实EventService）
    5. 评估生成
    
    关键架构：
    - 仿真启动时创建数据库 SAVEPOINT
    - 仿真期间所有操作（事件、任务等）直接写入真实表
    - 仿真结束后 ROLLBACK TO SAVEPOINT 还原数据
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        # 活跃仿真的时钟: simulation_id -> SimulationClock
        self._clocks: Dict[UUID, SimulationClock] = {}
        # 注入调度任务: simulation_id -> asyncio.Task
        self._injection_tasks: Dict[UUID, asyncio.Task] = {}
        # 预设注入事件（内存管理）: simulation_id -> List[ScheduledInjection]
        self._scheduled_injections: Dict[UUID, List[ScheduledInjection]] = {}
    
    # =========================================================================
    # 仿真场景管理
    # =========================================================================
    
    async def create_scenario(
        self,
        data: SimulationScenarioCreate,
    ) -> SimulationScenarioResponse:
        """创建仿真场景"""
        start_sim_time = data.start_simulation_time or datetime.utcnow()
        
        scenario = SimulationScenario(
            name=data.name,
            description=data.description,
            scenario_id=data.scenario_id,
            source_type=data.source_type.value,
            source_scenario_id=data.source_scenario_id,
            time_scale=data.time_scale,
            start_simulation_time=start_sim_time,
            current_simulation_time=start_sim_time,
            status='ready',
            participants=[p.model_dump() for p in data.participants],
        )
        
        self._db.add(scenario)
        await self._db.flush()
        
        # 将预设注入事件存入内存
        scheduled = []
        for inject in data.inject_events:
            scheduled.append(ScheduledInjection(
                id=str(uuid_lib.uuid4()),
                relative_time_min=inject.relative_time_min,
                event_template=inject.event_template,
                injected=False,
            ))
        if scheduled:
            self._scheduled_injections[scenario.id] = scheduled
        
        await self._db.commit()
        await self._db.refresh(scenario)
        
        logger.info(f"创建仿真场景: id={scenario.id}, name={data.name}")
        
        return self._to_scenario_response(scenario)
    
    async def get_scenario(self, simulation_id: UUID) -> SimulationScenarioResponse:
        """获取仿真场景"""
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        # 如果正在运行，更新当前仿真时间
        if simulation_id in self._clocks:
            clock = self._clocks[simulation_id]
            scenario.current_simulation_time = clock.current_simulation_time
        
        return self._to_scenario_response(scenario)
    
    async def list_scenarios(
        self,
        scenario_id: Optional[UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SimulationListResponse:
        """列出仿真场景"""
        query = select(SimulationScenario)
        
        if scenario_id:
            query = query.where(SimulationScenario.scenario_id == scenario_id)
        if status:
            query = query.where(SimulationScenario.status == status)
        
        query = query.order_by(SimulationScenario.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        scenarios = result.scalars().all()
        
        # 获取总数
        count_query = select(SimulationScenario.id)
        if scenario_id:
            count_query = count_query.where(SimulationScenario.scenario_id == scenario_id)
        if status:
            count_query = count_query.where(SimulationScenario.status == status)
        count_result = await self._db.execute(count_query)
        total = len(count_result.all())
        
        return SimulationListResponse(
            items=[self._to_scenario_response(s) for s in scenarios],
            total=total,
        )
    
    # =========================================================================
    # 仿真生命周期（核心：SAVEPOINT 事务管理）
    # =========================================================================
    
    async def start_simulation(self, simulation_id: UUID) -> SimulationScenarioResponse:
        """
        启动仿真
        
        关键操作：创建数据库 SAVEPOINT，用于仿真结束后还原
        """
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status not in ('ready', 'paused'):
            raise ConflictError(
                error_code="SI4002",
                message=f"仿真状态不允许启动: {scenario.status}"
            )
        
        # TODO: 首次启动时创建 SAVEPOINT（暂时禁用，后续启用）
        # if scenario.status == 'ready':
        #     savepoint_name = f"sim_{simulation_id.hex[:16]}_{int(datetime.utcnow().timestamp())}"
        #     await self._db.execute(text(f"SAVEPOINT {savepoint_name}"))
        #     scenario.savepoint_name = savepoint_name
        #     logger.info(f"创建仿真快照: {savepoint_name}")
        
        # 创建或恢复时钟
        if simulation_id not in self._clocks:
            clock = SimulationClock(
                simulation_start=scenario.start_simulation_time or datetime.utcnow(),
                time_scale=scenario.time_scale,
            )
            self._clocks[simulation_id] = clock
        else:
            clock = self._clocks[simulation_id]
        
        if scenario.status == 'ready':
            clock.start()
            scenario.started_at = datetime.utcnow()
        else:
            clock.resume()
        
        scenario.status = 'running'
        scenario.paused_at = None
        
        await self._db.commit()
        await self._db.refresh(scenario)
        
        # 启动注入调度
        self._start_injection_scheduler(simulation_id)
        
        # 广播仿真启动事件
        await self._broadcast_simulation_event(simulation_id, "started")
        
        logger.info(f"仿真启动: id={simulation_id}")
        
        return self._to_scenario_response(scenario)
    
    async def pause_simulation(self, simulation_id: UUID) -> SimulationScenarioResponse:
        """暂停仿真"""
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status != 'running':
            raise ConflictError(
                error_code="SI4002",
                message=f"仿真状态不允许暂停: {scenario.status}"
            )
        
        # 暂停时钟
        if simulation_id in self._clocks:
            clock = self._clocks[simulation_id]
            clock.pause()
            scenario.current_simulation_time = clock.current_simulation_time
            scenario.total_pause_duration_s = clock.total_pause_duration_seconds
        
        scenario.status = 'paused'
        scenario.paused_at = datetime.utcnow()
        
        await self._db.commit()
        await self._db.refresh(scenario)
        
        # 停止注入调度
        self._stop_injection_scheduler(simulation_id)
        
        # 广播仿真暂停事件
        await self._broadcast_simulation_event(simulation_id, "paused")
        
        logger.info(f"仿真暂停: id={simulation_id}")
        
        return self._to_scenario_response(scenario)
    
    async def resume_simulation(self, simulation_id: UUID) -> SimulationScenarioResponse:
        """恢复仿真"""
        return await self.start_simulation(simulation_id)
    
    async def stop_simulation(
        self,
        simulation_id: UUID,
        rollback: bool = True,
    ) -> SimulationScenarioResponse:
        """
        停止仿真
        
        关键操作：ROLLBACK TO SAVEPOINT 还原数据（如果 rollback=True）
        
        Args:
            simulation_id: 仿真ID
            rollback: 是否回滚数据，默认True。设为False则保留仿真期间的数据
        """
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status in ('completed', 'stopped'):
            raise ConflictError(
                error_code="SI4002",
                message=f"仿真已结束: {scenario.status}"
            )
        
        # 记录最终仿真时间
        if simulation_id in self._clocks:
            clock = self._clocks[simulation_id]
            scenario.current_simulation_time = clock.current_simulation_time
            scenario.total_pause_duration_s = clock.total_pause_duration_seconds
            del self._clocks[simulation_id]
        
        # TODO: 回滚数据库到快照（暂时禁用，后续启用）
        # if rollback and scenario.savepoint_name:
        #     await self._db.execute(text(f"ROLLBACK TO SAVEPOINT {scenario.savepoint_name}"))
        #     logger.info(f"回滚仿真数据到快照: {scenario.savepoint_name}")
        
        # TODO: 释放 SAVEPOINT（暂时禁用，后续启用）
        # if scenario.savepoint_name:
        #     try:
        #         await self._db.execute(text(f"RELEASE SAVEPOINT {scenario.savepoint_name}"))
        #     except Exception:
        #         pass  # 如果已经回滚，SAVEPOINT 可能已释放
        
        scenario.status = 'stopped'
        scenario.completed_at = datetime.utcnow()
        scenario.savepoint_name = None
        
        await self._db.commit()
        await self._db.refresh(scenario)
        
        # 停止注入调度
        self._stop_injection_scheduler(simulation_id)
        
        # 清理内存中的预设注入
        self._scheduled_injections.pop(simulation_id, None)
        
        # 广播仿真停止事件
        await self._broadcast_simulation_event(simulation_id, "stopped")
        
        logger.info(f"仿真停止: id={simulation_id}, rollback={rollback}")
        
        return self._to_scenario_response(scenario)
    
    # =========================================================================
    # 时间控制
    # =========================================================================
    
    async def update_time_scale(
        self,
        simulation_id: UUID,
        request: TimeScaleUpdateRequest,
    ) -> SimulationTimeResponse:
        """调整时间倍率"""
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status != 'running':
            raise ConflictError(
                error_code="SI4002",
                message=f"只能在运行中调整时间倍率: {scenario.status}"
            )
        
        # 更新时钟
        if simulation_id in self._clocks:
            clock = self._clocks[simulation_id]
            clock.set_time_scale(request.time_scale)
        
        # 更新数据库
        scenario.time_scale = request.time_scale
        await self._db.commit()
        
        logger.info(f"时间倍率调整: id={simulation_id}, scale={request.time_scale}")
        
        return self._get_time_response(simulation_id)
    
    def _get_time_response(self, simulation_id: UUID) -> SimulationTimeResponse:
        """获取时间响应"""
        clock = self._clocks.get(simulation_id)
        if clock:
            return SimulationTimeResponse(
                real_time=datetime.utcnow(),
                simulation_time=clock.current_simulation_time,
                time_scale=Decimal(str(clock.time_scale)),
                elapsed_real_seconds=clock.elapsed_real_seconds,
                elapsed_simulation_seconds=clock.elapsed_simulation_seconds,
            )
        else:
            return SimulationTimeResponse(
                real_time=datetime.utcnow(),
                simulation_time=datetime.utcnow(),
                time_scale=Decimal("1.0"),
                elapsed_real_seconds=0,
                elapsed_simulation_seconds=0,
            )
    
    # =========================================================================
    # 事件注入（直接调用真实 EventService）
    # =========================================================================
    
    async def inject_event(
        self,
        simulation_id: UUID,
        request: ImmediateInjectionRequest,
    ) -> UUID:
        """
        立即注入事件（调用真实 EventService）
        
        Returns:
            创建的真实事件ID
        """
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status != 'running':
            raise ConflictError(
                error_code="SI4002",
                message=f"只能在运行中注入事件: {scenario.status}"
            )
        
        # 调用真实 EventService 创建事件
        event_id = await self._create_real_event(scenario.scenario_id, request.event)
        
        # 广播注入事件
        await self._broadcast_injected_event(simulation_id, request.event, event_id)
        
        logger.info(f"事件注入: simulation={simulation_id}, event_id={event_id}")
        
        return event_id
    
    async def get_injection_queue(self, simulation_id: UUID) -> InjectionQueueResponse:
        """获取注入队列（从内存获取）"""
        await self._get_scenario_or_raise(simulation_id)
        
        scheduled = self._scheduled_injections.get(simulation_id, [])
        
        pending = [s for s in scheduled if not s.injected]
        injected = [s for s in scheduled if s.injected]
        
        return InjectionQueueResponse(
            pending=pending,
            injected=injected,
        )
    
    async def _create_real_event(self, scenario_id: UUID, template: EventTemplate) -> UUID:
        """
        调用真实 EventService 创建事件
        
        将 EventTemplate 转换为 EventCreate 并调用 EventService.create()
        """
        from src.domains.events.schemas import EventCreate, EventType, EventSourceType, EventPriority, Location
        
        # 转换事件类型
        try:
            event_type = EventType(template.event_type)
        except ValueError:
            event_type = EventType.other
        
        # 转换优先级
        try:
            priority = EventPriority(template.priority)
        except ValueError:
            priority = EventPriority.medium
        
        # 构建位置
        location = Location(longitude=0, latitude=0)
        if template.location:
            location = Location(
                longitude=template.location.get("longitude", 0),
                latitude=template.location.get("latitude", 0),
            )
        
        # 构建 EventCreate
        event_create = EventCreate(
            scenario_id=scenario_id,
            event_type=event_type,
            source_type=EventSourceType.system_inference,  # 标记为系统推断（仿真注入）
            source_detail={"simulation_injected": True},
            title=template.title,
            description=template.description,
            location=location,
            priority=priority,
            estimated_victims=template.estimated_victims,
        )
        
        # 调用真实服务
        event_service = _get_event_service(self._db)
        event = await event_service.create(event_create)
        
        return event.id
    
    def _start_injection_scheduler(self, simulation_id: UUID) -> None:
        """启动注入调度器"""
        if simulation_id in self._injection_tasks:
            return
        
        task = asyncio.create_task(
            self._injection_loop(simulation_id),
            name=f"injection-{simulation_id}"
        )
        self._injection_tasks[simulation_id] = task
    
    def _stop_injection_scheduler(self, simulation_id: UUID) -> None:
        """停止注入调度器"""
        task = self._injection_tasks.pop(simulation_id, None)
        if task and not task.done():
            task.cancel()
    
    async def _injection_loop(self, simulation_id: UUID) -> None:
        """注入调度循环"""
        try:
            while True:
                await asyncio.sleep(5)  # 每5秒检查一次
                
                clock = self._clocks.get(simulation_id)
                if not clock or clock.is_paused:
                    continue
                
                # 计算已过仿真时间（分钟）
                elapsed_min = clock.elapsed_simulation_seconds / 60
                
                # 获取预设注入列表
                scheduled = self._scheduled_injections.get(simulation_id, [])
                
                for injection in scheduled:
                    if injection.injected:
                        continue
                    
                    # 检查是否到达注入时间
                    if elapsed_min >= injection.relative_time_min:
                        try:
                            # 获取场景
                            scenario = await self._get_scenario_or_raise(simulation_id)
                            
                            # 创建真实事件
                            event_id = await self._create_real_event(
                                scenario.scenario_id,
                                injection.event_template,
                            )
                            
                            # 更新注入状态
                            injection.injected = True
                            injection.injected_event_id = event_id
                            injection.injected_at = datetime.utcnow()
                            
                            # 广播
                            await self._broadcast_injected_event(
                                simulation_id,
                                injection.event_template,
                                event_id,
                            )
                            
                            logger.info(
                                f"自动注入事件: simulation={simulation_id}, "
                                f"event_id={event_id}, at T+{injection.relative_time_min}min"
                            )
                        except Exception as e:
                            logger.error(f"注入事件失败: {e}", exc_info=True)
        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"注入调度异常: {e}", exc_info=True)
    
    # =========================================================================
    # 评估生成
    # =========================================================================
    
    async def create_assessment(
        self,
        simulation_id: UUID,
        request: AssessmentCreateRequest,
    ) -> AssessmentResponse:
        """生成评估报告"""
        scenario = await self._get_scenario_or_raise(simulation_id)
        
        if scenario.status not in ('completed', 'stopped'):
            raise ConflictError(
                error_code="SI4002",
                message=f"只能对已结束的仿真生成评估: {scenario.status}"
            )
        
        # 检查是否已有评估
        existing = await self._db.execute(
            select(DrillAssessment).where(DrillAssessment.simulation_id == simulation_id)
        )
        if existing.scalar():
            raise ConflictError(
                error_code="SI4002",
                message="该仿真已有评估报告"
            )
        
        # 生成评估
        assessment_result = await self._generate_assessment(scenario, request)
        
        # 保存评估
        assessment = DrillAssessment(
            simulation_id=simulation_id,
            overall_score=assessment_result.overall_score,
            response_time_score=assessment_result.grades.get(
                "response_time", AssessmentGrade(score=Decimal("0"), detail="")
            ).score,
            decision_score=assessment_result.grades.get(
                "decision_quality", AssessmentGrade(score=Decimal("0"), detail="")
            ).score,
            coordination_score=assessment_result.grades.get(
                "coordination", AssessmentGrade(score=Decimal("0"), detail="")
            ).score,
            resource_utilization_score=assessment_result.grades.get(
                "resource_utilization", AssessmentGrade(score=Decimal("0"), detail="")
            ).score,
            details={
                "grades": {k: v.model_dump() for k, v in assessment_result.grades.items()},
                "timeline_analysis": [t.model_dump() for t in assessment_result.timeline_analysis],
                "recommendations": assessment_result.recommendations,
            },
        )
        
        self._db.add(assessment)
        await self._db.commit()
        await self._db.refresh(assessment)
        
        logger.info(f"生成评估: simulation={simulation_id}, score={assessment.overall_score}")
        
        return AssessmentResponse(
            id=assessment.id,
            simulation_id=simulation_id,
            assessment=assessment_result,
            created_at=assessment.created_at,
        )
    
    async def get_assessment(self, simulation_id: UUID) -> AssessmentResponse:
        """获取评估报告"""
        result = await self._db.execute(
            select(DrillAssessment).where(DrillAssessment.simulation_id == simulation_id)
        )
        assessment = result.scalar()
        
        if not assessment:
            raise NotFoundError("DrillAssessment", str(simulation_id))
        
        # 重建 AssessmentResult
        details = assessment.details or {}
        grades = {
            k: AssessmentGrade(**v) 
            for k, v in details.get("grades", {}).items()
        }
        
        assessment_result = AssessmentResult(
            overall_score=assessment.overall_score,
            grades=grades,
            timeline_analysis=details.get("timeline_analysis", []),
            recommendations=details.get("recommendations", []),
        )
        
        return AssessmentResponse(
            id=assessment.id,
            simulation_id=simulation_id,
            assessment=assessment_result,
            created_at=assessment.created_at,
        )
    
    async def _generate_assessment(
        self,
        scenario: SimulationScenario,
        request: AssessmentCreateRequest,
    ) -> AssessmentResult:
        """生成评估结果（简化实现）"""
        # TODO: 接入更复杂的评估逻辑或AI分析
        
        # 计算仿真时长
        duration_min = 0
        if scenario.started_at and scenario.completed_at:
            duration = scenario.completed_at - scenario.started_at
            duration_min = duration.total_seconds() / 60
        
        # 基础评分
        grades = {
            "response_time": AssessmentGrade(
                score=Decimal("85"),
                detail=f"仿真持续 {duration_min:.1f} 分钟"
            ),
            "decision_quality": AssessmentGrade(
                score=Decimal("80"),
                detail="决策过程基本合理"
            ),
            "coordination": AssessmentGrade(
                score=Decimal("82"),
                detail="多队伍协同良好"
            ),
            "resource_utilization": AssessmentGrade(
                score=Decimal("78"),
                detail="资源利用率可优化"
            ),
        }
        
        overall = sum(g.score for g in grades.values()) / len(grades)
        
        timeline = []
        recommendations = []
        
        if request.include_timeline:
            timeline = [
                {"time": "T+0min", "event": "仿真启动", "evaluation": "正常", "benchmark": None},
            ]
        
        if request.include_recommendations:
            recommendations = [
                "建议提高资源调度效率",
                "可优化队伍间的通信协调",
            ]
        
        return AssessmentResult(
            overall_score=overall,
            grades=grades,
            timeline_analysis=timeline,
            recommendations=recommendations,
        )
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    async def _get_scenario_or_raise(self, simulation_id: UUID) -> SimulationScenario:
        """获取仿真场景"""
        result = await self._db.execute(
            select(SimulationScenario).where(SimulationScenario.id == simulation_id)
        )
        scenario = result.scalar()
        
        if not scenario:
            raise NotFoundError("SimulationScenario", str(simulation_id))
        
        return scenario
    
    def _to_scenario_response(self, scenario: SimulationScenario) -> SimulationScenarioResponse:
        """转换为响应模型"""
        return SimulationScenarioResponse(
            id=scenario.id,
            name=scenario.name,
            description=scenario.description,
            scenario_id=scenario.scenario_id,
            source_type=SimulationSourceType(scenario.source_type),
            source_scenario_id=scenario.source_scenario_id,
            time_scale=scenario.time_scale,
            start_simulation_time=scenario.start_simulation_time,
            current_simulation_time=scenario.current_simulation_time,
            status=SimulationStatus(scenario.status),
            participants=scenario.participants or [],
            created_at=scenario.created_at,
            started_at=scenario.started_at,
            completed_at=scenario.completed_at,
        )
    
    async def _broadcast_simulation_event(self, simulation_id: UUID, event_type: str) -> None:
        """广播仿真事件"""
        try:
            broker = _get_stomp_broker()
            await broker.broadcast(f"/topic/simulation.{event_type}", {
                "payload": {
                    "simulation_id": str(simulation_id),
                    "event_type": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            })
        except Exception as e:
            logger.warning(f"广播仿真事件失败: {e}")
    
    async def _broadcast_injected_event(
        self,
        simulation_id: UUID,
        template: EventTemplate,
        event_id: UUID,
    ) -> None:
        """广播注入的事件"""
        try:
            broker = _get_stomp_broker()
            await broker.broadcast("/topic/simulation.event_injected", {
                "payload": {
                    "simulation_id": str(simulation_id),
                    "event_id": str(event_id),
                    "event": template.model_dump(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            })
        except Exception as e:
            logger.warning(f"广播注入事件失败: {e}")
