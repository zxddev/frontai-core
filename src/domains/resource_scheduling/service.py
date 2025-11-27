"""
资源调度服务层

提供API封装、参数校验、日志记录。
可被FastAPI路由、EmergencyAI节点等调用。
"""
from __future__ import annotations

import logging
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal

from .core import ResourceSchedulingCore
from .schemas import (
    CapabilityRequirement,
    SchedulingConstraints,
    SchedulingObjectives,
    SchedulingResult,
    SchedulingSolution,
    PriorityLevel,
)

logger = logging.getLogger(__name__)


class ScheduleRequest(BaseModel):
    """调度请求"""
    destination_lon: float = Field(..., description="目标点经度")
    destination_lat: float = Field(..., description="目标点纬度")
    requirements: List[CapabilityRequirement] = Field(
        ..., min_length=1, description="能力需求列表"
    )
    constraints: Optional[SchedulingConstraints] = Field(
        None, description="调度约束（可选）"
    )
    objectives: Optional[SchedulingObjectives] = Field(
        None, description="优化目标权重（可选）"
    )


class ScheduleResponse(BaseModel):
    """调度响应"""
    success: bool
    best_solution: Optional[dict] = None
    solutions: List[dict] = Field(default_factory=list)
    candidates_total: int = 0
    candidates_reachable: int = 0
    elapsed_ms: int = 0
    algorithm_used: str = ""
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ResourceSchedulingService:
    """
    资源调度服务
    
    提供高层API，封装Core层的复杂逻辑。
    """

    @staticmethod
    async def schedule(
        request: ScheduleRequest,
        db: Optional[AsyncSession] = None,
    ) -> ScheduleResponse:
        """
        执行资源调度
        
        Args:
            request: 调度请求
            db: 数据库会话（可选，未提供时自动创建）
            
        Returns:
            ScheduleResponse 包含调度结果
        """
        logger.info(
            f"[ResourceSchedulingService] 开始调度 "
            f"destination=({request.destination_lon:.4f},{request.destination_lat:.4f}) "
            f"requirements={len(request.requirements)}"
        )

        async def _execute(session: AsyncSession) -> ScheduleResponse:
            core = ResourceSchedulingCore(session)
            result = await core.schedule(
                destination_lon=request.destination_lon,
                destination_lat=request.destination_lat,
                requirements=request.requirements,
                constraints=request.constraints,
                objectives=request.objectives,
            )
            return _convert_result_to_response(result)

        if db is not None:
            return await _execute(db)
        else:
            async with AsyncSessionLocal() as session:
                return await _execute(session)

    @staticmethod
    async def schedule_for_event(
        event_lon: float,
        event_lat: float,
        capability_codes: List[str],
        max_response_minutes: float = 120.0,
        scenario_id: Optional[UUID] = None,
        db: Optional[AsyncSession] = None,
    ) -> ScheduleResponse:
        """
        为事件调度资源（简化接口）
        
        Args:
            event_lon: 事件经度
            event_lat: 事件纬度
            capability_codes: 需要的能力编码列表
            max_response_minutes: 最大响应时间（分钟）
            scenario_id: 想定ID（用于灾害区域避障）
            db: 数据库会话
            
        Returns:
            ScheduleResponse
        """
        # 构建能力需求
        requirements = [
            CapabilityRequirement(
                capability_code=code,
                min_count=1,
                priority=PriorityLevel.MEDIUM,
            )
            for code in capability_codes
        ]

        # 构建约束
        constraints = SchedulingConstraints(
            max_response_time_minutes=max_response_minutes,
            scenario_id=scenario_id,
        )

        request = ScheduleRequest(
            destination_lon=event_lon,
            destination_lat=event_lat,
            requirements=requirements,
            constraints=constraints,
        )

        return await ResourceSchedulingService.schedule(request, db)


def _convert_result_to_response(result: SchedulingResult) -> ScheduleResponse:
    """将内部结果转换为API响应"""
    return ScheduleResponse(
        success=result.success,
        best_solution=_solution_to_dict(result.best_solution) if result.best_solution else None,
        solutions=[_solution_to_dict(s) for s in result.solutions],
        candidates_total=result.candidates_total,
        candidates_reachable=result.candidates_reachable,
        elapsed_ms=result.elapsed_ms,
        algorithm_used=result.algorithm_used,
        errors=result.errors,
        warnings=result.warnings,
    )


def _solution_to_dict(solution: SchedulingSolution) -> dict:
    """将方案转换为字典"""
    return {
        "solution_id": solution.solution_id,
        "allocations": [
            {
                "resource_id": str(a.resource_id),
                "resource_name": a.resource_name,
                "resource_type": a.resource_type.value,
                "assigned_capabilities": a.assigned_capabilities,
                "direct_distance_km": a.direct_distance_km,
                "road_distance_km": a.road_distance_km,
                "eta_minutes": a.eta_minutes,
                "match_score": a.match_score,
                "rescue_capacity": a.rescue_capacity,
            }
            for a in solution.allocations
        ],
        "max_eta_minutes": solution.max_eta_minutes,
        "total_eta_minutes": solution.total_eta_minutes,
        "coverage_rate": solution.coverage_rate,
        "total_capacity": solution.total_capacity,
        "resource_count": solution.resource_count,
        "avg_match_score": solution.avg_match_score,
        "strategy": solution.strategy,
        "is_feasible": solution.is_feasible,
        "warnings": solution.warnings,
    }
