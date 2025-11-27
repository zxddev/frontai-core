"""
整合资源调度核心

将人装物调度整合为统一的调度入口:
1. 人员调度 - ResourceSchedulingCore (队伍选择 + 路径规划)
2. 装备调度 - EquipmentScheduler (无人设备 + 传统装备)
3. 物资调度 - SupplyDemandCalculator + LogisticsScheduler

基于学术研究的三层架构:
- Layer 1: 纯算法层 (本模块)
- Layer 2: Service API层 (由调用方封装)
- Layer 3: Agent层 (可选，用于交互式对话)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .core import ResourceSchedulingCore
from .schemas import (
    CapabilityRequirement,
    SchedulingConstraints,
    SchedulingObjectives,
    SchedulingSolution,
    SchedulingResult,
    ResourceAllocation,
    PriorityLevel,
)
from .equipment_scheduler import EquipmentScheduler
from .equipment_schemas import (
    EquipmentSchedulingResult,
    EquipmentAllocation,
)
from .demand_calculator import SupplyDemandCalculator, DemandCalculationResult

logger = logging.getLogger(__name__)


@dataclass
class DisasterContext:
    """灾情上下文"""
    disaster_type: str           # 灾害类型
    disaster_subtype: Optional[str] = None  # 子类型
    scenario_id: Optional[UUID] = None       # 想定ID
    event_id: Optional[UUID] = None          # 事件ID
    
    # 位置
    center_lon: float = 0.0
    center_lat: float = 0.0
    
    # 人员情况
    affected_population: int = 0   # 受灾人数
    trapped_count: int = 0         # 被困人数
    injured_count: int = 0         # 伤员人数
    
    # 时间
    estimated_duration_days: int = 3   # 预计持续天数


@dataclass
class IntegratedSchedulingRequest:
    """整合调度请求"""
    context: DisasterContext
    
    # 能力需求（从灾情推断或直接指定）
    capability_requirements: Optional[List[CapabilityRequirement]] = None
    
    # 调度约束
    constraints: Optional[SchedulingConstraints] = None
    
    # 优化目标
    objectives: Optional[SchedulingObjectives] = None
    
    # 开关
    include_team_scheduling: bool = True    # 是否调度队伍
    include_equipment_scheduling: bool = True   # 是否调度装备
    include_supply_calculation: bool = True  # 是否计算物资需求


@dataclass
class IntegratedSchedulingResult:
    """整合调度结果"""
    success: bool
    
    # 队伍调度结果
    team_result: Optional[SchedulingResult] = None
    
    # 装备调度结果
    equipment_result: Optional[EquipmentSchedulingResult] = None
    
    # 物资需求计算结果
    supply_demand: Optional[DemandCalculationResult] = None
    
    # 统计
    total_elapsed_ms: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 汇总信息
    selected_teams: int = 0
    allocated_equipment: int = 0
    supply_types: int = 0
    
    @property
    def summary(self) -> Dict:
        """生成调度结果摘要"""
        return {
            "success": self.success,
            "teams": {
                "selected": self.selected_teams,
                "best_coverage": self.team_result.best_solution.coverage_rate if self.team_result and self.team_result.best_solution else 0,
                "best_eta_minutes": self.team_result.best_solution.max_eta_minutes if self.team_result and self.team_result.best_solution else 0,
            } if self.team_result else None,
            "equipment": {
                "allocated": self.allocated_equipment,
                "required_met": self.equipment_result.required_met if self.equipment_result else 0,
                "required_total": self.equipment_result.required_total if self.equipment_result else 0,
            } if self.equipment_result else None,
            "supplies": {
                "types": self.supply_types,
                "source": self.supply_demand.source if self.supply_demand else "none",
            } if self.supply_demand else None,
            "elapsed_ms": self.total_elapsed_ms,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class IntegratedResourceSchedulingCore:
    """
    整合资源调度核心
    
    统一入口，协调人装物调度流程。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化整合调度核心
        
        Args:
            db: SQLAlchemy异步数据库会话
        """
        self._db = db
        self._team_scheduler = ResourceSchedulingCore(db)
        self._equipment_scheduler = EquipmentScheduler(db)
        self._supply_calculator = SupplyDemandCalculator(db)

    async def schedule(
        self,
        request: IntegratedSchedulingRequest,
    ) -> IntegratedSchedulingResult:
        """
        执行整合调度
        
        Args:
            request: 整合调度请求
            
        Returns:
            IntegratedSchedulingResult
        """
        start_time = time.perf_counter()
        logger.info(
            f"[整合调度] 开始 disaster={request.context.disaster_type} "
            f"location=({request.context.center_lon:.4f},{request.context.center_lat:.4f}) "
            f"affected={request.context.affected_population}"
        )

        errors: List[str] = []
        warnings: List[str] = []
        
        team_result: Optional[SchedulingResult] = None
        equipment_result: Optional[EquipmentSchedulingResult] = None
        supply_demand: Optional[DemandCalculationResult] = None

        # 获取能力需求（如果未指定，从灾情推断）
        requirements = request.capability_requirements
        if requirements is None:
            requirements = self._infer_capability_requirements(request.context)
            logger.info(f"[整合调度] 推断能力需求: {[r.capability_code for r in requirements]}")

        # 1. 队伍调度（并行启动）
        team_task = None
        if request.include_team_scheduling and requirements:
            constraints = request.constraints or SchedulingConstraints()
            if request.context.scenario_id:
                constraints.scenario_id = request.context.scenario_id
            
            team_task = asyncio.create_task(
                self._team_scheduler.schedule(
                    destination_lon=request.context.center_lon,
                    destination_lat=request.context.center_lat,
                    requirements=requirements,
                    constraints=constraints,
                    objectives=request.objectives,
                )
            )

        # 2. 物资需求计算（并行执行）
        supply_task = None
        if request.include_supply_calculation:
            supply_task = asyncio.create_task(
                self._supply_calculator.calculate(
                    disaster_type=request.context.disaster_type,
                    affected_count=request.context.affected_population,
                    duration_days=request.context.estimated_duration_days,
                    trapped_count=request.context.trapped_count,
                )
            )

        # 等待队伍调度完成
        if team_task:
            try:
                team_result = await team_task
                errors.extend(team_result.errors)
                warnings.extend(team_result.warnings)
            except Exception as e:
                logger.error(f"[整合调度] 队伍调度失败: {e}")
                errors.append(f"队伍调度失败: {e}")

        # 3. 装备调度（需要从队伍调度结果获取能力列表）
        if request.include_equipment_scheduling:
            # 确定需要的能力
            capability_codes: List[str] = []
            if team_result and team_result.best_solution:
                # 从已分配的队伍获取能力
                for alloc in team_result.best_solution.allocations:
                    capability_codes.extend(alloc.assigned_capabilities)
                capability_codes = list(set(capability_codes))
            else:
                # 使用推断的能力需求
                capability_codes = [r.capability_code for r in requirements]

            if capability_codes:
                try:
                    equipment_result = await self._equipment_scheduler.schedule(
                        capability_codes=capability_codes,
                        destination_lon=request.context.center_lon,
                        destination_lat=request.context.center_lat,
                    )
                    errors.extend(equipment_result.errors)
                    warnings.extend(equipment_result.warnings)
                except Exception as e:
                    logger.error(f"[整合调度] 装备调度失败: {e}")
                    errors.append(f"装备调度失败: {e}")

        # 等待物资计算完成
        if supply_task:
            try:
                supply_demand = await supply_task
            except Exception as e:
                logger.error(f"[整合调度] 物资需求计算失败: {e}")
                errors.append(f"物资需求计算失败: {e}")

        # 构建结果
        total_elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        # 统计
        selected_teams = 0
        if team_result and team_result.best_solution:
            selected_teams = len(team_result.best_solution.allocations)
        
        allocated_equipment = 0
        if equipment_result:
            allocated_equipment = equipment_result.total_equipment_count
        
        supply_types = 0
        if supply_demand:
            supply_types = len(supply_demand.requirements)

        # 判断整体成功
        success = (
            (not request.include_team_scheduling or (team_result and team_result.success)) and
            (not request.include_equipment_scheduling or (equipment_result and equipment_result.success)) and
            (not request.include_supply_calculation or supply_demand is not None)
        )

        logger.info(
            f"[整合调度] 完成: success={success} "
            f"teams={selected_teams} equipment={allocated_equipment} supplies={supply_types} "
            f"elapsed={total_elapsed_ms}ms"
        )

        return IntegratedSchedulingResult(
            success=success,
            team_result=team_result,
            equipment_result=equipment_result,
            supply_demand=supply_demand,
            total_elapsed_ms=total_elapsed_ms,
            errors=errors,
            warnings=warnings,
            selected_teams=selected_teams,
            allocated_equipment=allocated_equipment,
            supply_types=supply_types,
        )

    def _infer_capability_requirements(
        self,
        context: DisasterContext,
    ) -> List[CapabilityRequirement]:
        """
        从灾情上下文推断能力需求
        
        基于灾害类型的默认能力映射。
        生产环境应使用TRR规则或知识图谱。
        """
        # 灾害类型 -> 能力需求映射 (capability_code, min_count, priority_level)
        DISASTER_CAPABILITY_MAP: Dict[str, List[Tuple[str, int, PriorityLevel]]] = {
            "earthquake": [
                ("LIFE_DETECTION", 2, PriorityLevel.CRITICAL),       # 生命探测
                ("STRUCTURAL_RESCUE", 3, PriorityLevel.CRITICAL),   # 结构救援
                ("MEDICAL_TRIAGE", 2, PriorityLevel.CRITICAL),      # 医疗分诊
                ("EMERGENCY_TREATMENT", 2, PriorityLevel.HIGH),     # 紧急救治
                ("COMMUNICATION", 1, PriorityLevel.HIGH),           # 通信保障
            ],
            "fire": [
                ("FIRE_SUPPRESSION", 3, PriorityLevel.CRITICAL),    # 火灾扑救
                ("EMERGENCY_TREATMENT", 2, PriorityLevel.CRITICAL), # 紧急救治
                ("RECONNAISSANCE", 1, PriorityLevel.HIGH),          # 侦察
            ],
            "flood": [
                ("WATER_RESCUE", 3, PriorityLevel.CRITICAL),        # 水域救援
                ("EVACUATION_COORDINATION", 2, PriorityLevel.CRITICAL),  # 疏散协调
                ("MEDICAL_TRIAGE", 1, PriorityLevel.HIGH),          # 医疗分诊
            ],
            "hazmat": [
                ("HAZMAT_RESPONSE", 3, PriorityLevel.CRITICAL),     # 危化品处置
                ("EMERGENCY_TREATMENT", 2, PriorityLevel.CRITICAL), # 紧急救治
                ("EVACUATION_COORDINATION", 1, PriorityLevel.HIGH), # 疏散协调
            ],
            "landslide": [
                ("STRUCTURAL_RESCUE", 2, PriorityLevel.CRITICAL),   # 结构救援
                ("LIFE_DETECTION", 2, PriorityLevel.CRITICAL),      # 生命探测
                ("MEDICAL_TRIAGE", 1, PriorityLevel.HIGH),          # 医疗分诊
            ],
        }

        capabilities = DISASTER_CAPABILITY_MAP.get(
            context.disaster_type,
            [("STRUCTURAL_RESCUE", 2, PriorityLevel.CRITICAL), ("MEDICAL_TRIAGE", 1, PriorityLevel.HIGH)]  # 默认
        )

        # 根据被困人数调整需求数量
        multiplier = 1.0
        if context.trapped_count > 50:
            multiplier = 2.0
        elif context.trapped_count > 20:
            multiplier = 1.5
        elif context.trapped_count > 10:
            multiplier = 1.2

        requirements: List[CapabilityRequirement] = []
        for cap_code, min_count, priority in capabilities:
            req = CapabilityRequirement(
                capability_code=cap_code,
                min_count=max(1, int(min_count * multiplier)),
                priority=priority,
            )
            requirements.append(req)

        return requirements

    async def quick_schedule_teams(
        self,
        destination_lon: float,
        destination_lat: float,
        capability_codes: List[str],
        max_response_time_minutes: float = 60.0,
        max_teams: int = 10,
    ) -> SchedulingResult:
        """
        快速队伍调度（简化接口）
        
        Args:
            destination_lon: 目标经度
            destination_lat: 目标纬度
            capability_codes: 所需能力编码列表
            max_response_time_minutes: 最大响应时间
            max_teams: 最大队伍数
            
        Returns:
            SchedulingResult
        """
        requirements = [
            CapabilityRequirement(capability_code=code, min_count=1, priority=1)
            for code in capability_codes
        ]
        
        constraints = SchedulingConstraints(
            max_response_time_minutes=max_response_time_minutes,
            max_resources=max_teams,
        )

        return await self._team_scheduler.schedule(
            destination_lon=destination_lon,
            destination_lat=destination_lat,
            requirements=requirements,
            constraints=constraints,
        )

    async def calculate_supply_demand(
        self,
        disaster_type: str,
        affected_count: int,
        duration_days: int = 3,
        trapped_count: int = 0,
    ) -> DemandCalculationResult:
        """
        计算物资需求（简化接口）
        """
        return await self._supply_calculator.calculate(
            disaster_type=disaster_type,
            affected_count=affected_count,
            duration_days=duration_days,
            trapped_count=trapped_count,
        )

    async def schedule_equipment(
        self,
        capability_codes: List[str],
        destination_lon: float,
        destination_lat: float,
        max_distance_km: float = 100.0,
    ) -> EquipmentSchedulingResult:
        """
        调度装备（简化接口）
        """
        return await self._equipment_scheduler.schedule(
            capability_codes=capability_codes,
            destination_lon=destination_lon,
            destination_lat=destination_lat,
            max_distance_km=max_distance_km,
        )
