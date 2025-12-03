"""
阶段3: 资源匹配节点

从数据库查询真实救援队伍，根据事件坐标计算距离和响应时间，
按时间约束过滤并进行能力匹配。

改进：
- 基于队伍类型推断车辆速度和全地形能力
- 考虑道路系数计算真实行驶距离
- 支持危险区域避障（查询disaster_affected_areas_v2）
- 山区/复杂地形自动降速
- 整合人装物调度（IntegratedResourceSchedulingCore）
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.domains.resource_scheduling import (
    IntegratedResourceSchedulingCore,
    DisasterContext,
    IntegratedSchedulingRequest,
    CapabilityRequirement,
    SchedulingConstraints,
    PriorityLevel,
)
from src.domains.resource_scheduling.sphere_demand_calculator import SphereDemandCalculator
from src.domains.supplies.inventory_service import SupplyInventoryService
from src.infra.config.algorithm_config_service import AlgorithmConfigService
from src.domains.disaster import (
    ResponsePhase,
    ClimateType,
    CasualtyEstimator,
    DisasterType as DisasterTypeEnum,
)
from src.domains.disaster.casualty_estimator import CasualtyEstimate
from ..state import EmergencyAIState, ResourceCandidate, AllocationSolution
from src.planning.algorithms.optimization.pymoo_optimizer import PymooOptimizer
from src.planning.algorithms.base import AlgorithmStatus

logger = logging.getLogger(__name__)


# ============================================================================
# 车辆参数配置（基于队伍类型推断）
# ============================================================================

@dataclass
class VehicleProfile:
    """车辆参数配置"""
    speed_kmh: float           # 正常道路速度(km/h)
    mountain_speed_kmh: float  # 山区道路速度(km/h)
    is_all_terrain: bool       # 是否全地形车辆
    road_factor: float         # 道路系数（直线距离→实际距离）


# 队伍类型→车辆参数映射
TEAM_VEHICLE_PROFILES: Dict[str, VehicleProfile] = {
    "fire_rescue": VehicleProfile(
        speed_kmh=60.0,           # 消防车在城市道路
        mountain_speed_kmh=35.0,  # 山区道路降速
        is_all_terrain=True,      # 消防车通常有越野能力
        road_factor=1.3,          # 城市道路系数
    ),
    "medical": VehicleProfile(
        speed_kmh=70.0,           # 救护车速度较快
        mountain_speed_kmh=40.0,
        is_all_terrain=False,     # 标准救护车非全地形
        road_factor=1.25,
    ),
    "search_rescue": VehicleProfile(
        speed_kmh=50.0,           # 搜救车辆中等速度
        mountain_speed_kmh=30.0,
        is_all_terrain=True,
        road_factor=1.4,
    ),
    "hazmat": VehicleProfile(
        speed_kmh=55.0,           # 危化品车辆谨慎驾驶
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.35,
    ),
    "engineering": VehicleProfile(
        speed_kmh=45.0,           # 工程车辆速度较慢
        mountain_speed_kmh=25.0,
        is_all_terrain=True,      # 工程车辆通常能越野
        road_factor=1.4,
    ),
    "water_rescue": VehicleProfile(
        speed_kmh=50.0,           # 带冲锋舟运输车
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.35,
    ),
    "communication": VehicleProfile(
        speed_kmh=60.0,           # 通信保障车
        mountain_speed_kmh=35.0,
        is_all_terrain=False,
        road_factor=1.3,
    ),
    "mine_rescue": VehicleProfile(
        speed_kmh=50.0,           # 矿山救护车
        mountain_speed_kmh=28.0,
        is_all_terrain=True,
        road_factor=1.45,
    ),
    "armed_police": VehicleProfile(
        speed_kmh=70.0,           # 武警车辆较快
        mountain_speed_kmh=40.0,
        is_all_terrain=True,
        road_factor=1.25,
    ),
    "volunteer": VehicleProfile(
        speed_kmh=50.0,           # 志愿者车辆（普通车）
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.4,
    ),
    "command": VehicleProfile(
        speed_kmh=65.0,           # 指挥车辆
        mountain_speed_kmh=35.0,
        is_all_terrain=False,
        road_factor=1.3,
    ),
}

# 默认车辆参数
DEFAULT_VEHICLE_PROFILE = VehicleProfile(
    speed_kmh=40.0,
    mountain_speed_kmh=25.0,
    is_all_terrain=False,
    road_factor=1.4,
)

# 地形类型配置
TERRAIN_SPEED_FACTORS: Dict[str, float] = {
    "urban": 1.0,       # 城市道路正常
    "suburban": 0.9,    # 郊区略慢
    "rural": 0.8,       # 乡村道路
    "mountain": 0.5,    # 山区大幅降速
    "highway": 1.2,     # 高速公路加速
}


# ============================================================================
# 原有配置
# ============================================================================

# 默认最大搜索距离（km）
DEFAULT_MAX_DISTANCE_KM: float = 100.0

# 扩大搜索范围的步长（km）
DISTANCE_EXPAND_STEP_KM: float = 50.0

# 最大搜索距离上限（km）
MAX_SEARCH_DISTANCE_KM: float = 300.0

# 默认队伍查询上限（支持大规模救援场景）
DEFAULT_MAX_TEAMS: int = 200

# 灾害等级对应的队伍数量上限
DISASTER_SCALE_LIMITS: Dict[str, int] = {
    "small": 50,      # 小型灾害（社区级）
    "medium": 100,    # 中型灾害（区县级）
    "large": 200,     # 大型灾害（城市级）
    "catastrophic": 500,  # 特大灾害（地震级）
}


async def match_resources(state: EmergencyAIState) -> Dict[str, Any]:
    """
    资源匹配节点：从数据库查询真实队伍并匹配

    根据事件坐标从rescue_teams_v2表查询可用队伍，
    计算距离和响应时间，按能力需求进行匹配评分。

    Args:
        state: 当前状态，必须包含structured_input.location

    Returns:
        更新的状态字段，包含resource_candidates

    Raises:
        ValueError: structured_input.location缺失或无效
    """
    logger.info(f"[资源匹配] 开始执行，event_id={state['event_id']}")
    start_time = time.time()

    errors: List[str] = list(state.get("errors", []))
    trace: Dict[str, Any] = dict(state.get("trace", {}))

    # 获取事件坐标（必须从structured_input获取）
    event_location = _extract_event_location(state)
    if event_location is None:
        error_msg = "structured_input.location缺失或无效，必须提供事件坐标(longitude/latitude)"
        logger.error(f"[资源匹配] {error_msg}")
        errors.append(error_msg)
        return {
            "resource_candidates": [],
            "errors": errors,
            "trace": trace,
        }

    event_lat, event_lng = event_location
    logger.info(f"[资源匹配] 事件坐标: lat={event_lat}, lng={event_lng}")

    # 获取能力需求（合并规则推理和任务需求）
    capability_requirements = state.get("capability_requirements", [])
    task_sequence = state.get("task_sequence", [])
    
    # 从规则推理获取能力
    rule_caps = {cap["capability_code"] for cap in capability_requirements}
    
    # 从任务序列获取能力（确保包含所有任务需要的能力）
    task_caps = set()
    for task in task_sequence:
        task_caps.update(task.get("required_capabilities", []))
    
    # 合并两个来源的能力需求
    required_caps = rule_caps | task_caps
    
    if not required_caps:
        logger.warning("[资源匹配] 无能力需求，跳过资源匹配")
        return {"resource_candidates": [], "trace": trace}

    logger.info(f"[资源匹配] 需要的能力({len(required_caps)}种): 规则{len(rule_caps)}种 + 任务{len(task_caps)}种 = {required_caps}")

    # 获取约束条件
    constraints = state.get("constraints", {})
    
    # 获取灾害等级和队伍数量上限
    disaster_scale = _determine_disaster_scale(state)
    max_teams = constraints.get("max_teams", DISASTER_SCALE_LIMITS.get(disaster_scale, DEFAULT_MAX_TEAMS))
    logger.info(f"[资源匹配] 灾害等级: {disaster_scale}，队伍上限: {max_teams}")

    # 获取时间约束，使用默认车辆速度计算初始搜索距离
    max_response_hours: float = constraints.get("max_response_time_hours", 2.0)
    initial_max_distance: float = max_response_hours * DEFAULT_VEHICLE_PROFILE.speed_kmh
    logger.info(f"[资源匹配] 时间约束: {max_response_hours}小时，初始搜索距离: {initial_max_distance}km（默认速度{DEFAULT_VEHICLE_PROFILE.speed_kmh}km/h）")

    # 从数据库查询队伍
    teams: List[Dict[str, Any]] = []
    search_distance = initial_max_distance
    search_expanded = False

    async with AsyncSessionLocal() as db:
        # 第一次查询：按时间约束范围
        teams = await _query_teams_from_db(
            db=db,
            event_lat=event_lat,
            event_lng=event_lng,
            max_distance_km=search_distance,
            max_teams=max_teams,
        )
        logger.info(f"[资源匹配] 初始查询: 距离<={search_distance}km, 上限{max_teams}支, 找到{len(teams)}支队伍")

        # 检查能力覆盖
        covered_caps = _get_covered_capabilities(teams)
        missing_caps = required_caps - covered_caps

        # 如果能力覆盖不足，扩大搜索范围
        while missing_caps and search_distance < MAX_SEARCH_DISTANCE_KM:
            search_distance += DISTANCE_EXPAND_STEP_KM
            search_expanded = True
            logger.warning(
                f"[资源匹配] 能力覆盖不足，缺失: {missing_caps}，扩大搜索范围至{search_distance}km"
            )

            teams = await _query_teams_from_db(
                db=db,
                event_lat=event_lat,
                event_lng=event_lng,
                max_distance_km=search_distance,
                max_teams=max_teams,
            )
            covered_caps = _get_covered_capabilities(teams)
            missing_caps = required_caps - covered_caps

    if not teams:
        error_msg = f"在{search_distance}km范围内未找到任何可用队伍"
        logger.error(f"[资源匹配] {error_msg}")
        errors.append(error_msg)
        return {
            "resource_candidates": [],
            "errors": errors,
            "trace": trace,
        }

    # 记录搜索范围扩大的情况
    if search_expanded:
        expand_msg = f"搜索范围从{initial_max_distance}km扩大至{search_distance}km以覆盖所需能力"
        logger.warning(f"[资源匹配] {expand_msg}")
        trace["search_expanded"] = True
        trace["initial_distance_km"] = initial_max_distance
        trace["final_distance_km"] = search_distance

    # 检查最终能力覆盖
    if missing_caps:
        missing_msg = f"以下能力在{search_distance}km范围内无队伍具备: {missing_caps}"
        logger.warning(f"[资源匹配] {missing_msg}")
        errors.append(missing_msg)
        trace["missing_capabilities"] = list(missing_caps)

    # 获取道路损坏信息用于动态调整ETA
    parsed_disaster_for_road = state.get("parsed_disaster", {})
    has_road_damage: bool = parsed_disaster_for_road.get("has_road_damage", False) if parsed_disaster_for_road else False

    # 从数据库获取道路系数参数（缺失则报错，无Fallback）
    async with AsyncSessionLocal() as config_db:
        config_service = AlgorithmConfigService(config_db)
        base_road_config = await config_service.get_or_raise("emergency_ai", "BASE_ROAD_FACTOR")
        damaged_road_config = await config_service.get_or_raise("emergency_ai", "DAMAGED_ROAD_FACTOR")
    
    base_road_factor: float = float(base_road_config["value"])
    damaged_road_factor: float = float(damaged_road_config["value"])
    logger.info(f"[资源匹配] 道路系数配置: base={base_road_factor}, damaged={damaged_road_factor}")

    # 计算匹配分数
    candidates = _calculate_match_scores(
        teams=teams,
        required_capabilities=required_caps,
        event_lat=event_lat,
        event_lng=event_lng,
        max_response_hours=max_response_hours,
        has_road_damage=has_road_damage,
        base_road_factor=base_road_factor,
        damaged_road_factor=damaged_road_factor,
    )

    # 按匹配分数排序
    candidates.sort(key=lambda x: x["match_score"], reverse=True)

    # ========================================================================
    # 整合调度：装备调度 + 物资需求计算 + 前线库存缺口分析
    # ========================================================================
    equipment_allocations: List[Dict[str, Any]] = []
    supply_requirements: List[Dict[str, Any]] = []
    supply_shortages: List[Dict[str, Any]] = []
    
    # 获取灾情信息
    parsed_disaster = state.get("parsed_disaster", {})
    disaster_type = parsed_disaster.get("disaster_type", "earthquake") if parsed_disaster else "earthquake"
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0) if parsed_disaster else 0
    affected_population = parsed_disaster.get("affected_population", 0) if parsed_disaster else 0
    
    # 如果没有受影响人口数据，基于被困人数估算
    if affected_population == 0 and estimated_trapped > 0:
        affected_population = estimated_trapped * 5  # 假设受灾人口是被困人数的5倍
    
    try:
        async with AsyncSessionLocal() as db:
            integrated_core = IntegratedResourceSchedulingCore(db)
            
            # 1. 装备调度（基于能力需求）
            capability_codes = list(required_caps)
            if capability_codes:
                logger.info(f"[资源匹配] 开始装备调度，能力需求: {capability_codes}")
                equipment_result = await integrated_core.schedule_equipment(
                    capability_codes=capability_codes,
                    destination_lon=event_lng,
                    destination_lat=event_lat,
                    max_distance_km=search_distance,
                )
                
                # 总是添加已分配的装备（即使未满足所有必须需求）
                for alloc in equipment_result.allocations:
                    equipment_allocations.append({
                        "equipment_id": str(alloc.equipment_id),
                        "equipment_code": alloc.equipment_code,
                        "equipment_name": alloc.equipment_name,
                        "equipment_type": alloc.equipment_type.value,
                        "source_name": alloc.source_name,
                        "allocated_quantity": alloc.allocated_quantity,
                        "for_capability": alloc.for_capability,
                        "distance_km": alloc.distance_km,
                    })
                logger.info(
                    f"[资源匹配] 装备调度完成: {len(equipment_allocations)}件装备，"
                    f"必须满足{equipment_result.required_met}/{equipment_result.required_total}"
                )
                if not equipment_result.success:
                    logger.warning(f"[资源匹配] 装备调度未能满足所有必须需求: {equipment_result.warnings}")
                
                trace["equipment_scheduling"] = {
                    "success": equipment_result.success,
                    "required_met": equipment_result.required_met,
                    "required_total": equipment_result.required_total,
                    "total_count": equipment_result.total_equipment_count,
                    "elapsed_ms": equipment_result.elapsed_ms,
                }
            
            # 2. 物资需求计算 - 使用SphereDemandCalculator
            if affected_population > 0:
                logger.info(f"[资源匹配] 开始物资需求计算(Sphere): 灾害类型={disaster_type}, 受灾人数={affected_population}")
                
                # 构造伤亡估算
                estimator = CasualtyEstimator()
                severity = parsed_disaster.get("severity", "medium") if parsed_disaster else "medium"
                severity_score = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}.get(severity, 0.5)
                
                try:
                    dt = DisasterTypeEnum(disaster_type)
                except ValueError:
                    dt = DisasterTypeEnum.EARTHQUAKE
                
                casualty = estimator.estimate_generic(
                    disaster_type=dt,
                    severity=severity_score,
                    population=affected_population,
                )
                
                # 打印伤亡估算结果
                logger.info(f"【伤亡估算-输入】灾害类型={disaster_type}, 严重程度={severity}({severity_score}), 受灾人口={affected_population}")
                logger.info(f"【伤亡估算-输出】死亡={casualty.fatalities}, 重伤={casualty.severe_injuries}, 轻伤={casualty.minor_injuries}, 被困={casualty.trapped}")
                
                # 如果有明确被困人数，覆盖估算值
                if estimated_trapped > 0:
                    logger.info(f"【伤亡估算-覆盖】使用实际被困人数{estimated_trapped}覆盖估算值{casualty.trapped}")
                    casualty = CasualtyEstimate(
                        fatalities=casualty.fatalities,
                        severe_injuries=casualty.severe_injuries,
                        minor_injuries=casualty.minor_injuries,
                        trapped=estimated_trapped,
                        displaced=casualty.displaced,
                        affected=affected_population,
                        confidence=casualty.confidence,
                        methodology=casualty.methodology,
                    )
                
                config_service = AlgorithmConfigService(db)
                sphere_calculator = SphereDemandCalculator(db, config_service)
                supply_result = await sphere_calculator.calculate(
                    phase=ResponsePhase.IMMEDIATE,
                    casualty_estimate=casualty,
                    duration_days=3,
                    climate=ClimateType.TEMPERATE,
                )
                
                for req in supply_result.requirements:
                    supply_requirements.append({
                        "supply_code": req.supply_code,
                        "supply_name": req.supply_name,
                        "category": req.category,
                        "quantity": req.quantity,
                        "unit": req.unit,
                        "priority": req.priority,
                    })
                
                logger.info(
                    f"[资源匹配] 物资需求计算完成(Sphere): {len(supply_requirements)}种物资，"
                    f"耗时={supply_result.elapsed_ms}ms"
                )
                
                trace["supply_calculation"] = {
                    "disaster_type": disaster_type,
                    "affected_count": affected_population,
                    "duration_days": 3,
                    "supply_types": len(supply_requirements),
                    "source": "SphereDemandCalculator",
                    "elapsed_ms": supply_result.elapsed_ms,
                }
            
            # 3. 查询前线可用库存并计算缺口
            scenario_id_raw = state.get("scenario_id")
            scenario_uuid: Optional[UUID] = None
            
            # 验证并转换scenario_id为UUID
            if scenario_id_raw and supply_requirements:
                scenario_uuid = await _resolve_scenario_id(db, scenario_id_raw)
                if scenario_uuid is None:
                    logger.warning(
                        f"[资源匹配] scenario_id '{scenario_id_raw}' 无法解析为有效UUID，跳过库存查询"
                    )
            
            if scenario_uuid and supply_requirements:
                logger.info(f"[资源匹配] 查询前线可用库存，scenario_id={scenario_uuid}")
                inventory_service = SupplyInventoryService(db)
                
                # 查询前线所有depot的库存（field_depot/vehicle/team_base）
                field_inventory = await inventory_service.get_field_available_supplies(
                    scenario_id=scenario_uuid
                )
                
                # 计算缺口
                supply_shortages = await inventory_service.calculate_shortage(
                    requirements=supply_requirements,
                    available=field_inventory,
                )
                
                logger.info(
                    f"[资源匹配] 前线库存查询完成: {len(field_inventory)}条库存，"
                    f"{len(supply_shortages)}种物资存在缺口"
                )
                
                trace["field_inventory"] = {
                    "scenario_id": str(scenario_uuid),
                    "inventory_count": len(field_inventory),
                    "shortage_count": len(supply_shortages),
                }
                
                # 将缺口信息添加到返回值
                if supply_shortages:
                    for shortage in supply_shortages:
                        # 标记需要从后方调拨的物资
                        shortage["needs_transfer"] = True
                        shortage["transfer_suggestion"] = (
                            f"前线缺口{shortage['shortage']}，建议从后方仓库调拨"
                        )
                
    except Exception as e:
        logger.error(f"[资源匹配] 整合调度失败: {e}")
        errors.append(f"整合调度失败: {e}")
        supply_shortages = []

    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_resources"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["database_query", "capability_matching", "integrated_scheduling"]
    trace["teams_queried"] = len(teams)
    trace["candidates_count"] = len(candidates)
    trace["equipment_count"] = len(equipment_allocations)
    trace["supply_types_count"] = len(supply_requirements)
    trace["supply_shortages_count"] = len(supply_shortages)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[资源匹配] 完成，查询{len(teams)}支队伍，生成{len(candidates)}个候选，"
        f"调度{len(equipment_allocations)}件装备，计算{len(supply_requirements)}种物资需求，"
        f"缺口{len(supply_shortages)}种，耗时{elapsed_ms}ms"
    )

    return {
        "resource_candidates": candidates,
        "equipment_allocations": equipment_allocations,
        "supply_requirements": supply_requirements,
        "supply_shortages": supply_shortages,
        "trace": trace,
        "errors": errors,
        "current_phase": "matching",
    }


async def optimize_allocation(state: EmergencyAIState) -> Dict[str, Any]:
    """
    分配优化节点：基于候选资源生成多个分配方案

    使用NSGA-II多目标优化生成Pareto最优解集。
    如果候选资源较少（<=10），退化为贪心策略以提高效率。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段，包含allocation_solutions和pareto_solutions
    """
    logger.info(f"[分配优化] 开始执行，event_id={state['event_id']}")
    start_time = time.time()

    candidates = state.get("resource_candidates", [])
    capability_requirements = state.get("capability_requirements", [])
    task_sequence = state.get("task_sequence", [])  # HTN分解后的任务序列
    constraints = state.get("constraints", {})
    trace: Dict[str, Any] = dict(state.get("trace", {}))
    errors: List[str] = list(state.get("errors", []))
    
    # 合并能力需求：规则推理阶段 + 任务实际需求
    # 确保NSGA-II优化时考虑所有任务需要的能力
    rule_caps = {cap["capability_code"] for cap in capability_requirements}
    task_caps = set()
    for task in task_sequence:
        task_caps.update(task.get("required_capabilities", []))
    all_required_caps = rule_caps | task_caps
    
    # 如果任务需要的能力超出规则推理的范围，扩展capability_requirements
    missing_caps = task_caps - rule_caps
    if missing_caps:
        logger.info(f"[分配优化] 任务需要额外{len(missing_caps)}种能力: {missing_caps}")
        for cap_code in missing_caps:
            capability_requirements.append({
                "capability_code": cap_code,
                "capability_name": cap_code,  # 临时名称
                "source": "task_required",
            })
    
    # 获取被困人数用于计算救援容量需求
    parsed_disaster = state.get("parsed_disaster", {})
    estimated_trapped: int = parsed_disaster.get("estimated_trapped", 0) if parsed_disaster else 0
    logger.info(f"[分配优化] 被困人数: {estimated_trapped}")

    # 从数据库获取容量安全系数（缺失则报错，无Fallback）
    async with AsyncSessionLocal() as config_db:
        config_service = AlgorithmConfigService(config_db)
        capacity_config = await config_service.get_or_raise("emergency_ai", "CAPACITY_SAFETY_FACTOR")
    capacity_safety_factor: float = float(capacity_config["value"])
    logger.info(f"[分配优化] 容量安全系数: {capacity_safety_factor}")

    if not candidates:
        logger.warning("[分配优化] 无候选资源，无法生成方案")
        return {
            "allocation_solutions": [],
            "pareto_solutions": [],
            "trace": trace,
            "errors": errors,
        }

    # 获取生成方案数量
    n_alternatives = constraints.get("n_alternatives", 5)
    
    solutions: List[AllocationSolution] = []
    algorithm_used = "greedy"  # 默认贪心

    # 尝试使用NSGA-II（候选资源>10时效果更好）
    if len(candidates) > 10:
        try:
            nsga_solutions = _run_nsga2_optimization(
                candidates=candidates,
                capability_requirements=capability_requirements,
                task_sequence=task_sequence,
                n_solutions=n_alternatives,
                estimated_trapped=estimated_trapped,
            )
            if nsga_solutions:
                solutions = nsga_solutions
                algorithm_used = "NSGA-II"
                logger.info(f"[分配优化] NSGA-II生成{len(solutions)}个Pareto解")
        except Exception as e:
            logger.warning(f"[分配优化] NSGA-II失败，退化为贪心策略: {e}")
            errors.append(f"NSGA-II优化失败: {e}")

    # 如果NSGA-II未生成方案，使用贪心策略
    if not solutions:
        # 方案1: 最高匹配分数优先
        solution1 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="match_score",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
        )
        if solution1:
            solutions.append(solution1)

        # 方案2: 最短响应时间优先（按距离排序）
        solution2 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="distance",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
        )
        if solution2:
            solutions.append(solution2)

        # 方案3: 最高可用性优先
        solution3 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="availability",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
        )
        if solution3:
            solutions.append(solution3)

    # 为每个方案生成任务-资源分配序列
    if task_sequence and solutions:
        for solution in solutions:
            task_assignments, execution_path = _assign_tasks_to_resources(
                task_sequence=task_sequence,
                selected_resources=solution.get("allocations", []),
                capability_requirements=capability_requirements,
            )
            solution["task_assignments"] = task_assignments
            solution["execution_path"] = execution_path
    else:
        # 无任务序列时，填充空值
        for solution in solutions:
            solution["task_assignments"] = []
            solution["execution_path"] = ""

    # Pareto最优解
    pareto_solutions = _deduplicate_solutions(solutions)[:n_alternatives]

    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["optimize_allocation"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + [algorithm_used]
    trace["solutions_generated"] = len(solutions)
    trace["optimization_algorithm"] = algorithm_used

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[分配优化] 完成，算法={algorithm_used}，生成{len(solutions)}个方案，Pareto解{len(pareto_solutions)}个，耗时{elapsed_ms}ms"
    )

    return {
        "allocation_solutions": solutions,
        "pareto_solutions": pareto_solutions,
        "trace": trace,
        "errors": errors,
    }


def _run_nsga2_optimization(
    candidates: List[ResourceCandidate],
    capability_requirements: List[Dict[str, Any]],
    task_sequence: List[Dict[str, Any]],
    n_solutions: int = 5,
    estimated_trapped: int = 0,
) -> List[AllocationSolution]:
    """
    使用NSGA-II进行多目标优化 (调用统一算法库)
    
    优化目标（5维评估）：
    1. 最大化成功率（权重0.35）
    2. 最小化响应时间（权重0.30）
    3. 最大化覆盖率（权重0.20）
    4. 最小化风险（权重0.05）
    5. 最大化冗余性（权重0.10）
    
    Args:
        candidates: 候选资源
        capability_requirements: 能力需求
        task_sequence: HTN任务序列
        n_solutions: 生成方案数量
        
    Returns:
        Pareto最优解列表
    """
    logger.info(f"[NSGA-II] 开始多目标优化 (使用 PymooOptimizer)")
    
    # 检查候选资源
    n_resources = len(candidates)
    if n_resources == 0:
        return []
        
    required_caps = {cap["capability_code"] for cap in capability_requirements}
    
    # 定义问题类 (继承自pymoo ElementwiseProblem)
    # 注意：这里我们需要在运行时定义，因为依赖闭包变量(candidates)
    try:
        from pymoo.core.problem import ElementwiseProblem
        import numpy as np
    except ImportError:
        logger.warning("[NSGA-II] pymoo未安装，无法执行优化")
        return []

    class EmergencyAllocationProblem(ElementwiseProblem):
        def __init__(self):
            super().__init__(
                n_var=n_resources,
                n_obj=3,  # 响应时间、覆盖率(负)、队伍数
                n_constr=1,  # 覆盖率约束
                xl=0,
                xu=1,
                vtype=int,
            )
        
        def _evaluate(self, x, out, *args, **kwargs):
            selected_indices = np.where(x > 0.5)[0]
            
            if len(selected_indices) == 0:
                out["F"] = [1e5, 0, 1e5]
                out["G"] = [1.0]
                return
            
            max_eta = 0.0
            covered_caps = set()
            
            for idx in selected_indices:
                cand = candidates[idx]
                max_eta = max(max_eta, cand.get("eta_minutes", 0))
                covered_caps.update(cand["capabilities"])
            
            coverage = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
            
            # 目标: [min时间, max覆盖(转min), min数量(降低权重)]
            # 队伍数权重降低到0.5，允许更多队伍以提高能力覆盖
            out["F"] = [max_eta, -coverage, len(selected_indices) * 0.5]
            # 约束: 覆盖率 >= 95%（提高要求以确保能力充分覆盖）
            out["G"] = [0.95 - coverage]

    # 调用统一算法优化器
    optimizer = PymooOptimizer()
    result = optimizer.run({
        "problem": EmergencyAllocationProblem(),
        "pop_size": 50,
        "n_generations": 50,
        "algorithm": "nsga2",
        "verbose": False,
        "seed": 42
    })
    
    if result.status != AlgorithmStatus.SUCCESS or not result.solution:
        logger.warning(f"[NSGA-II] 优化未找到可行解: {result.message}")
        return []
        
    # 解析结果并构建 AllocationSolution
    solutions: List[AllocationSolution] = []
    seen_solutions: set = set()
    
    for sol in result.solution:
        # PymooOptimizer返回的variables是列表
        x = np.array(sol["variables"])
        objectives = sol["objectives"]
        
        selected_indices = np.where(x > 0.5)[0]
        if len(selected_indices) == 0:
            continue
            
        # 去重
        sol_key = frozenset(int(i) for i in selected_indices)
        if sol_key in seen_solutions:
            continue
        seen_solutions.add(sol_key)
        
        # 构建方案详情
        allocations: List[Dict[str, Any]] = []
        covered_caps = set()
        max_eta = 0.0
        max_distance = 0.0
        total_capacity = 0
        
        for idx in selected_indices:
            cand = candidates[int(idx)]
            # 计算该资源贡献的新能力
            assignable_caps = set(cand["capabilities"]).intersection(required_caps) - covered_caps
            cand_capacity = cand.get("rescue_capacity", 0)
            
            allocations.append({
                "resource_id": cand["resource_id"],
                "resource_name": cand["resource_name"],
                "resource_type": cand["resource_type"],
                "assigned_capabilities": list(assignable_caps) if assignable_caps else cand["capabilities"],
                "match_score": cand["match_score"],
                "distance_km": cand["distance_km"],
                "eta_minutes": cand.get("eta_minutes", 0),
                "rescue_capacity": cand_capacity,
            })
            covered_caps.update(cand["capabilities"])
            max_eta = max(max_eta, cand.get("eta_minutes", 0))
            max_distance = max(max_distance, cand["distance_km"])
            total_capacity += cand_capacity
            
        # 计算综合指标
        coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
        avg_score = sum(a["match_score"] for a in allocations) / len(allocations) if allocations else 0
        
        # 容量分析
        capacity_coverage = total_capacity / estimated_trapped if estimated_trapped > 0 else 1.0
        capacity_warning = None
        if estimated_trapped > 0 and capacity_coverage < 0.8:
            capacity_warning = f"⚠️ 救援容量不足 (覆盖率{capacity_coverage*100:.1f}%)"
            
        allocation_sol: AllocationSolution = {
            "solution_id": f"nsga-{uuid.uuid4().hex[:8]}",
            "allocations": allocations,
            "total_score": round(avg_score, 3),
            "response_time_min": round(max_eta, 1),
            "coverage_rate": round(coverage_rate, 3),
            "resource_scale": len(allocations),
            "risk_level": round(1.0 - coverage_rate, 3),
            "total_rescue_capacity": total_capacity,
            "capacity_coverage_rate": round(capacity_coverage, 3),
            "capacity_warning": capacity_warning,
            "uncovered_capabilities": list(required_caps - covered_caps),
            "max_distance_km": round(max_distance, 2),
            "teams_count": len(allocations),
            "objectives": {
                "response_time": round(objectives.get("f0", 0), 1),
                "coverage_rate": round(-objectives.get("f1", 0), 3), # 负转正
                "teams_count": int(objectives.get("f2", 0)),
            }
        }
        solutions.append(allocation_sol)
        
        if len(solutions) >= n_solutions:
            break
            
    # 按覆盖率排序
    solutions.sort(key=lambda s: s["coverage_rate"], reverse=True)
    logger.info(f"[NSGA-II] 生成 {len(solutions)} 个Pareto解")
    
    return solutions


async def _resolve_scenario_id(
    db: AsyncSession,
    scenario_id_raw: Any,
) -> Optional[UUID]:
    """
    解析scenario_id为UUID
    
    支持以下输入格式：
    1. 已经是UUID对象 -> 直接返回
    2. 有效的UUID字符串 -> 转换为UUID
    3. scenario名称 -> 从数据库查找对应的UUID
    4. 无效输入 -> 返回None
    
    Args:
        db: 数据库会话
        scenario_id_raw: 原始scenario_id（可能是UUID、字符串或其他）
        
    Returns:
        有效的UUID，或None表示无法解析
    """
    if scenario_id_raw is None:
        return None
    
    # 已经是UUID对象
    if isinstance(scenario_id_raw, UUID):
        return scenario_id_raw
    
    # 尝试转换为UUID字符串
    if isinstance(scenario_id_raw, str):
        # 尝试直接解析为UUID
        try:
            return UUID(scenario_id_raw)
        except ValueError:
            pass
        
        # 不是有效UUID格式，尝试按名称查找
        try:
            sql = text("""
                SELECT id FROM operational_v2.scenarios_v2
                WHERE name ILIKE :name_pattern
                LIMIT 1
            """)
            result = await db.execute(sql, {"name_pattern": f"%{scenario_id_raw}%"})
            row = result.fetchone()
            if row:
                logger.info(f"[scenario解析] 按名称'{scenario_id_raw}'找到scenario: {row[0]}")
                return row[0]
            else:
                logger.warning(f"[scenario解析] 未找到名称匹配'{scenario_id_raw}'的scenario")
                return None
        except Exception as e:
            logger.warning(f"[scenario解析] 查询失败: {e}")
            return None
    
    # 其他类型，尝试转换为字符串再解析
    try:
        return UUID(str(scenario_id_raw))
    except (ValueError, TypeError):
        return None


def _extract_event_location(state: EmergencyAIState) -> Optional[Tuple[float, float]]:
    """
    从state中提取事件坐标

    优先从structured_input.location获取，
    支持{longitude, latitude}或{lng, lat}格式。

    Returns:
        (latitude, longitude)元组，或None表示无效
    """
    structured_input = state.get("structured_input", {})
    if not structured_input:
        return None

    location = structured_input.get("location", {})
    if not location:
        return None

    # 支持多种字段名
    lat = location.get("latitude") or location.get("lat")
    lng = location.get("longitude") or location.get("lng")

    if lat is None or lng is None:
        return None

    try:
        lat_float = float(lat)
        lng_float = float(lng)
        # 基本有效性检查
        if not (-90 <= lat_float <= 90 and -180 <= lng_float <= 180):
            return None
        return (lat_float, lng_float)
    except (TypeError, ValueError):
        return None


def _determine_disaster_scale(state: EmergencyAIState) -> str:
    """
    根据灾情判断灾害等级
    
    Args:
        state: 当前状态
        
    Returns:
        灾害等级: small/medium/large/catastrophic
    """
    parsed_disaster = state.get("parsed_disaster")
    if parsed_disaster is None:
        logger.info("[匹配-灾害等级] 无灾情数据，使用默认等级: medium")
        return "medium"
    
    # 根据受影响人口判断
    affected_pop = parsed_disaster.get("affected_population", 0)
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0)
    severity = parsed_disaster.get("severity", "medium")
    disaster_type = parsed_disaster.get("disaster_type", "").lower()
    
    logger.info(f"[匹配-灾害等级] 判断输入参数:")
    logger.info(f"  - disaster_type: {disaster_type}")
    logger.info(f"  - severity: {severity}")
    logger.info(f"  - affected_population: {affected_pop}")
    logger.info(f"  - estimated_trapped: {estimated_trapped}")
    
    # 地震/特大灾害
    if disaster_type == "earthquake" or severity == "critical":
        if affected_pop > 10000 or estimated_trapped > 100:
            logger.info(f"[匹配-灾害等级] 判断: 地震/特大灾害 + (人口>{10000}或被困>{100}) -> catastrophic")
            return "catastrophic"
        logger.info(f"[匹配-灾害等级] 判断: 地震/严重灾害 -> large")
        return "large"
    
    # 根据被困人数
    if estimated_trapped > 50:
        logger.info(f"[匹配-灾害等级] 判断: 被困人数{estimated_trapped} > 50 -> large")
        return "large"
    elif estimated_trapped > 10:
        logger.info(f"[匹配-灾害等级] 判断: 被困人数{estimated_trapped} > 10 -> medium")
        return "medium"
    
    # 根据严重程度
    severity_mapping = {
        "critical": "large",
        "high": "medium",
        "medium": "medium",
        "low": "small",
    }
    result = severity_mapping.get(severity, "medium")
    logger.info(f"[匹配-灾害等级] 判断: 按严重程度{severity} -> {result}")
    return result


async def _query_teams_from_db(
    db: AsyncSession,
    event_lat: float,
    event_lng: float,
    max_distance_km: float,
    max_teams: int = DEFAULT_MAX_TEAMS,
) -> List[Dict[str, Any]]:
    """
    从数据库查询指定范围内的可用队伍

    使用PostGIS ST_Distance计算球面距离，
    关联team_capabilities_v2获取能力列表，
    关联team_vehicles_v2和vehicles_v2获取主力车辆参数。

    Args:
        db: 数据库会话
        event_lat: 事件纬度
        event_lng: 事件经度
        max_distance_km: 最大距离（公里）
        max_teams: 返回的最大队伍数量

    Returns:
        队伍列表，包含id, name, type, capabilities, distance_m, vehicle_speed_kmh等
    """
    # 使用子查询获取每个队伍的主力车辆（按is_primary DESC, assigned_at ASC取第一辆）
    sql = text("""
        WITH primary_vehicles AS (
            SELECT DISTINCT ON (tv.team_id) 
                tv.team_id,
                tv.vehicle_id,
                v.max_speed_kmh,
                v.is_all_terrain,
                v.code as vehicle_code,
                v.name as vehicle_name
            FROM operational_v2.team_vehicles_v2 tv
            JOIN operational_v2.vehicles_v2 v ON v.id = tv.vehicle_id
            WHERE tv.status = 'available'
            ORDER BY tv.team_id, tv.is_primary DESC, tv.assigned_at ASC
        )
        SELECT 
            t.id,
            t.code,
            t.name,
            t.team_type,
            ST_Y(t.base_location::geometry) AS base_lat,
            ST_X(t.base_location::geometry) AS base_lng,
            t.base_address,
            t.total_personnel,
            t.available_personnel,
            t.capability_level,
            t.response_time_minutes,
            t.status,
            COALESCE(
                ARRAY_AGG(DISTINCT tc.capability_code) 
                FILTER (WHERE tc.capability_code IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) AS capabilities,
            COALESCE(SUM(tc.max_capacity), 0) AS total_rescue_capacity,
            ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
            ) AS distance_m,
            pv.max_speed_kmh AS vehicle_speed_kmh,
            pv.is_all_terrain AS vehicle_is_all_terrain,
            pv.vehicle_code,
            pv.vehicle_name
        FROM operational_v2.rescue_teams_v2 t
        LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
        LEFT JOIN primary_vehicles pv ON pv.team_id = t.id
        WHERE t.status = 'standby'
          AND t.base_location IS NOT NULL
          AND ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
              ) <= :max_distance_m
        GROUP BY t.id, pv.max_speed_kmh, pv.is_all_terrain, pv.vehicle_code, pv.vehicle_name
        ORDER BY distance_m ASC, t.capability_level DESC
        LIMIT :max_teams
    """)

    params = {
        "event_lat": event_lat,
        "event_lng": event_lng,
        "max_distance_m": max_distance_km * 1000,
        "max_teams": max_teams,
    }

    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
        columns = result.keys()

        teams: List[Dict[str, Any]] = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            
            # 救援容量：优先使用数据库值，否则按类型估算
            db_capacity = row_dict.get("total_rescue_capacity", 0) or 0
            team_type = row_dict["team_type"]
            available = row_dict["available_personnel"] or 0
            
            if db_capacity > 0:
                rescue_capacity = int(db_capacity)
            else:
                # 按队伍类型估算救援容量（72小时内可救援人数）
                capacity_multipliers = {
                    "fire_rescue": 2.0,       # 消防队每人可救2人
                    "search_rescue": 1.5,     # 搜救队每人可救1.5人
                    "medical": 5.0,           # 医疗队每人可处理5伤员
                    "hazmat": 0.5,            # 危化品队不直接救人
                    "engineering": 0.0,       # 工程队不直接救人
                    "volunteer": 1.0,         # 志愿者每人可救1人
                }
                multiplier = capacity_multipliers.get(team_type, 1.0)
                rescue_capacity = int(available * multiplier)
                if rescue_capacity == 0 and available > 0:
                    rescue_capacity = available  # 兜底：至少等于可用人数
                logger.debug(f"[救援容量估算] {row_dict['name']} 无max_capacity，按类型{team_type}估算: {available}人×{multiplier}={rescue_capacity}")
            
            # 车辆速度：优先使用数据库值，否则使用默认配置
            vehicle_speed: int = row_dict.get("vehicle_speed_kmh") or 0
            vehicle_is_all_terrain: bool = row_dict.get("vehicle_is_all_terrain") or False
            vehicle_code: Optional[str] = row_dict.get("vehicle_code")
            vehicle_name: Optional[str] = row_dict.get("vehicle_name")
            
            # 无车辆数据时，使用队伍类型默认配置
            if vehicle_speed == 0:
                profile = TEAM_VEHICLE_PROFILES.get(team_type, DEFAULT_VEHICLE_PROFILE)
                vehicle_speed = int(profile.speed_kmh)
                vehicle_is_all_terrain = profile.is_all_terrain
                logger.debug(f"[车辆参数] {row_dict['name']} 无关联车辆，使用默认配置: {vehicle_speed}km/h, 全地形={vehicle_is_all_terrain}")
            
            team = {
                "id": str(row_dict["id"]),
                "code": row_dict["code"],
                "name": row_dict["name"],
                "team_type": row_dict["team_type"],
                "base_lat": row_dict["base_lat"],
                "base_lng": row_dict["base_lng"],
                "base_address": row_dict["base_address"],
                "total_personnel": row_dict["total_personnel"],
                "available_personnel": row_dict["available_personnel"],
                "capability_level": row_dict["capability_level"],
                "response_time_minutes": row_dict["response_time_minutes"],
                "status": row_dict["status"],
                "capabilities": list(row_dict["capabilities"] or []),
                "distance_m": row_dict["distance_m"],
                "distance_km": row_dict["distance_m"] / 1000.0 if row_dict["distance_m"] else 0,
                "rescue_capacity": rescue_capacity,
                # 车辆参数（用于ETA计算）
                "vehicle_speed_kmh": vehicle_speed,
                "vehicle_is_all_terrain": vehicle_is_all_terrain,
                "vehicle_code": vehicle_code,
                "vehicle_name": vehicle_name,
            }
            teams.append(team)

        total_capacity = sum(t["rescue_capacity"] for t in teams)
        teams_with_vehicle = sum(1 for t in teams if t.get("vehicle_code"))
        logger.info(f"【数据库-队伍查询】找到{len(teams)}支队伍，{teams_with_vehicle}支有关联车辆，总救援容量{total_capacity}人:")
        for t in teams[:10]:  # 打印前10支
            logger.info(f"  - {t['name']}: 能力={t['capabilities']}, 距离={t['distance_km']:.1f}km, 容量={t['rescue_capacity']}人")
        if len(teams) > 10:
            logger.info(f"  ... 还有{len(teams)-10}支队伍")
        return teams

    except Exception as e:
        logger.error(f"[数据库查询] 查询队伍失败: {e}")
        raise


def _get_covered_capabilities(teams: List[Dict[str, Any]]) -> set:
    """获取所有队伍覆盖的能力集合"""
    covered: set = set()
    for team in teams:
        covered.update(team.get("capabilities", []))
    return covered


def _calculate_match_scores(
    teams: List[Dict[str, Any]],
    required_capabilities: set,
    event_lat: float,
    event_lng: float,
    max_response_hours: float,
    terrain_type: str = "mountain",
    has_road_damage: bool = False,
    base_road_factor: float = 1.4,
    damaged_road_factor: float = 2.8,
) -> List[ResourceCandidate]:
    """
    计算每个队伍的匹配分数

    评分维度：
    - 能力覆盖率（50%）：队伍能力与需求的交集比例
    - 距离评分（30%）：距离越近分数越高
    - 能力等级（20%）：capability_level越高分数越高

    ETA计算：
    - 使用队伍关联车辆的max_speed_kmh（无车辆时使用队伍类型默认速度）
    - 道路系数：直线距离×1.4（山区道路迂回）
    - 地形降速：非全地形车辆在山区降速50%

    Args:
        teams: 队伍列表（含vehicle_speed_kmh, vehicle_is_all_terrain）
        required_capabilities: 需要的能力集合
        event_lat: 事件纬度
        event_lng: 事件经度
        max_response_hours: 最大响应时间（小时）
        terrain_type: 地形类型，影响ETA计算（默认mountain山区）

    Returns:
        ResourceCandidate列表
    """
    candidates: List[ResourceCandidate] = []
    
    # 道路系数：根据道路是否受损动态调整（参数从数据库获取）
    road_factor: float = damaged_road_factor if has_road_damage else base_road_factor
    if has_road_damage:
        logger.warning(f"[匹配-道路] 检测到道路受损，ETA系数={road_factor}（正常={base_road_factor}）")
    terrain_speed_factor: float = TERRAIN_SPEED_FACTORS.get(terrain_type, 0.5)
    
    # 使用默认速度计算最大搜索距离（用于距离评分归一化）
    default_speed: float = DEFAULT_VEHICLE_PROFILE.speed_kmh
    max_distance_km: float = max_response_hours * default_speed

    for team in teams:
        team_caps = set(team.get("capabilities", []))
        matched_caps = team_caps.intersection(required_capabilities)

        # 无匹配能力则跳过
        if not matched_caps:
            continue

        # 能力覆盖率评分
        capability_score = len(matched_caps) / len(required_capabilities) if required_capabilities else 0

        # 距离评分（距离越近越好）
        distance_km: float = team.get("distance_km", 0)
        distance_score = max(0, 1.0 - distance_km / max_distance_km) if max_distance_km > 0 else 0

        # 能力等级评分（1-5映射到0.2-1.0）
        capability_level: int = team.get("capability_level", 3)
        level_score = capability_level / 5.0

        # 获取车辆参数
        vehicle_speed_kmh: int = team.get("vehicle_speed_kmh", int(default_speed))
        vehicle_is_all_terrain: bool = team.get("vehicle_is_all_terrain", False)
        
        # 获取队伍类型对应的山区速度限制
        team_type = team.get("team_type", "")
        profile = TEAM_VEHICLE_PROFILES.get(team_type, DEFAULT_VEHICLE_PROFILE)
        mountain_speed_limit = profile.mountain_speed_kmh
        
        # 计算实际道路距离（使用动态道路系数，考虑道路损坏情况）
        road_distance_km: float = distance_km * road_factor
        
        # 计算实际行驶速度（考虑地形和山区限速）
        # 即使是全地形车辆，在山区也要受山区道路限速约束
        if vehicle_is_all_terrain:
            # 全地形车辆：取车辆速度和山区限速的较小值
            actual_speed_kmh: float = min(float(vehicle_speed_kmh), mountain_speed_limit)
        else:
            # 非全地形车辆：车辆速度降速后，再取与山区限速的较小值
            reduced_speed = float(vehicle_speed_kmh) * terrain_speed_factor
            actual_speed_kmh = min(reduced_speed, mountain_speed_limit)
        
        # 最低速度保护（防止除零和不合理值）
        actual_speed_kmh = max(actual_speed_kmh, 10.0)
        
        # 计算响应时间（分钟）= 道路距离 / 实际速度 × 60
        eta_minutes: float = (road_distance_km / actual_speed_kmh) * 60 if road_distance_km > 0 else 0

        # 综合得分
        match_score = (
            capability_score * 0.50 +
            distance_score * 0.30 +
            level_score * 0.20
        )

        # 队伍类型映射
        resource_type = _map_team_type(team.get("team_type", ""))

        candidate: ResourceCandidate = {
            "resource_id": team["id"],
            "resource_name": team["name"],
            "resource_type": resource_type,
            # 保存队伍的全部能力，而不是只保存与当前需求匹配的能力
            # 这样在分配优化阶段可以考虑任务的所有能力需求
            "capabilities": list(team_caps),
            "distance_km": round(distance_km, 2),
            "road_distance_km": round(road_distance_km, 2),  # 实际道路距离
            "availability_score": 1.0,
            "match_score": round(match_score, 3),
            "rescue_capacity": team.get("rescue_capacity", 0),
            # ETA相关
            "eta_minutes": round(eta_minutes, 1),
            "vehicle_speed_kmh": vehicle_speed_kmh,
            "actual_speed_kmh": round(actual_speed_kmh, 1),
            "vehicle_is_all_terrain": vehicle_is_all_terrain,
            "vehicle_code": team.get("vehicle_code"),
            "vehicle_name": team.get("vehicle_name"),
            "capability_level": capability_level,
            "base_address": team.get("base_address", ""),
            "personnel": team.get("available_personnel") or team.get("total_personnel", 0),
        }
        candidates.append(candidate)

    return candidates


def _map_team_type(team_type: str) -> str:
    """队伍类型映射到标准资源类型"""
    mapping = {
        "fire_rescue": "FIRE_TEAM",
        "medical": "MEDICAL_TEAM",
        "search_rescue": "RESCUE_TEAM",
        "hazmat": "HAZMAT_TEAM",
        "engineering": "ENGINEERING_TEAM",
        "communication": "SUPPORT_TEAM",
        "logistics": "SUPPORT_TEAM",
        "water_rescue": "WATER_RESCUE_TEAM",
        "mountain_rescue": "RESCUE_TEAM",
        "mine_rescue": "RESCUE_TEAM",
        "armed_police": "ARMED_TEAM",
        "evacuation": "EVACUATION_TEAM",
        "volunteer": "VOLUNTEER_TEAM",
        "command": "COMMAND_TEAM",
    }
    return mapping.get(team_type, "RESCUE_TEAM")


# ============================================================================
# 任务-资源分配（对齐杀伤链路径概念）
# ============================================================================


def _assign_tasks_to_resources(
    task_sequence: List[Dict[str, Any]],
    selected_resources: List[Dict[str, Any]],
    capability_requirements: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    """
    为任务序列分配最佳资源
    
    对齐参考系统的杀伤链路径概念：
    - 输入：任务序列 + 候选资源列表
    - 输出：任务-资源分配序列 + 执行路径字符串
    
    分配策略：
    1. 对每个任务，找出具备所需能力的资源
    2. 优先选择匹配度高、距离近的资源
    3. 尽量让同类任务由同一资源执行（减少协调开销）
    4. 生成执行路径字符串，如 "探测(队A)→支撑(队B)→救治(队C)"
    
    Args:
        task_sequence: HTN分解后的任务序列
        selected_resources: 已选中的资源列表
        capability_requirements: 能力需求列表
        
    Returns:
        (task_assignments, execution_path_str)
    """
    logger.info(f"【任务分配-输入】开始为{len(task_sequence)}个任务分配资源")
    logger.info(f"  - 任务列表: {[t.get('task_id') for t in task_sequence]}")
    logger.info(f"  - 候选资源: {len(selected_resources)}支队伍")
    for r in selected_resources[:5]:
        logger.info(f"    {r.get('resource_name')}: 能力={r.get('capabilities', [])}")
    if len(selected_resources) > 5:
        logger.info(f"    ... 还有{len(selected_resources)-5}支队伍")
    
    if not task_sequence or not selected_resources:
        return [], ""
    
    # 构建能力→任务映射
    cap_to_tasks: Dict[str, List[str]] = {}
    for cap in capability_requirements:
        cap_code = cap.get("capability_code", "")
        if cap_code:
            cap_to_tasks[cap_code] = cap_to_tasks.get(cap_code, [])
    
    # 构建资源ID→资源信息映射
    resource_map: Dict[str, Dict[str, Any]] = {
        r.get("resource_id", ""): r for r in selected_resources
    }
    
    task_assignments: List[Dict[str, Any]] = []
    resource_task_count: Dict[str, int] = {}  # 每个资源分配的任务数
    
    for seq_idx, task in enumerate(task_sequence, start=1):
        task_id = task.get("task_id", f"TASK-{seq_idx}")
        task_name = task.get("task_name", "未知任务")
        task_phase = task.get("phase", "execute")
        
        # 获取任务所需的能力（从Neo4j MetaTask节点查询得到）
        # 转换为大写格式以匹配资源能力代码（Neo4j用小写蛇形，PostgreSQL用大写下划线）
        raw_caps = task.get("required_capabilities", [])
        required_caps = set(cap.upper().replace("-", "_") for cap in raw_caps)
        if not required_caps:
            logger.warning(
                f"[任务分配] 任务{task_id}无required_capabilities，"
                "请检查Neo4j中MetaTask节点的数据"
            )
        
        # 寻找最佳匹配资源
        best_resource: Optional[Dict[str, Any]] = None
        best_score = -1.0
        match_reason = "默认分配"
        
        for resource in selected_resources:
            # 兼容两种字段名：candidates用capabilities，allocations用assigned_capabilities
            resource_caps = set(resource.get("capabilities", []) or resource.get("assigned_capabilities", []))
            resource_id = resource.get("resource_id", "")
            
            # 计算能力匹配度
            if required_caps:
                matched_caps = resource_caps.intersection(required_caps)
                cap_match_rate = len(matched_caps) / len(required_caps) if required_caps else 0
            else:
                # 无特定要求时，看资源是否有任何相关能力
                cap_match_rate = 0.5 if resource_caps else 0.1
            
            # 综合评分 = 能力匹配度(60%) + 原始匹配分(30%) + 负载均衡(10%)
            base_score = resource.get("match_score", 0.5)
            load_factor = 1.0 / (1 + resource_task_count.get(resource_id, 0))  # 任务越少越好
            
            score = cap_match_rate * 0.6 + base_score * 0.3 + load_factor * 0.1
            
            if score > best_score:
                best_score = score
                best_resource = resource
                if matched_caps if required_caps else resource_caps:
                    caps_str = "、".join(list(matched_caps)[:2]) if required_caps and matched_caps else "综合能力"
                    match_reason = f"具备{caps_str}能力，匹配度{cap_match_rate*100:.0f}%"
        
        # 如果找不到匹配资源，使用第一个可用资源
        if best_resource is None and selected_resources:
            best_resource = selected_resources[0]
            match_reason = "无最佳匹配，使用首选资源"
        
        if best_resource:
            resource_id = best_resource.get("resource_id", "")
            resource_task_count[resource_id] = resource_task_count.get(resource_id, 0) + 1
            
            assignment = {
                "task_id": task_id,
                "task_name": task_name,
                "resource_id": resource_id,
                "resource_name": best_resource.get("resource_name", "未知队伍"),
                "resource_type": best_resource.get("resource_type", "RESCUE_TEAM"),
                "execution_sequence": seq_idx,
                "phase": task_phase,
                "eta_minutes": best_resource.get("eta_minutes", 0),
                "match_score": round(best_score, 3),
                "match_reason": match_reason,
            }
            task_assignments.append(assignment)
            
            logger.info(
                f"【任务分配】{task_name}({task_id}) → {best_resource.get('resource_name')} "
                f"(分数={best_score:.3f}, 原因: {match_reason})"
            )
    
    # 生成执行路径字符串
    path_parts = []
    for assignment in task_assignments:
        short_name = assignment["task_name"][:4]  # 取前4个字符
        resource_short = assignment["resource_name"][:6]  # 取前6个字符
        path_parts.append(f"{short_name}({resource_short})")
    
    execution_path = " → ".join(path_parts) if path_parts else "无执行路径"
    
    logger.info(f"【任务分配-输出】完成，{len(task_assignments)}个任务已分配:")
    for a in task_assignments:
        logger.info(f"  {a['execution_sequence']}. {a['task_name']} → {a['resource_name']} (分数={a['match_score']:.3f})")
    logger.info(f"【执行路径】{execution_path}")
    
    return task_assignments, execution_path


def _generate_greedy_solution(
    candidates: List[ResourceCandidate],
    capability_requirements: List[Dict[str, Any]],
    strategy: str,
    solution_id: str,
    estimated_trapped: int = 0,
    capacity_safety_factor: float = 1.2,
) -> Optional[AllocationSolution]:
    """
    使用贪心策略生成分配方案
    
    修复版本：同时考虑能力覆盖和救援容量，不会在能力覆盖100%时就停止

    Args:
        candidates: 候选资源列表
        capability_requirements: 能力需求列表
        strategy: 策略 (match_score/distance/availability)
        solution_id: 方案ID
        estimated_trapped: 被困人数，用于计算最低救援容量需求

    Returns:
        分配方案或None
    """
    if not candidates or not capability_requirements:
        return None

    # 按策略排序
    if strategy == "match_score":
        sorted_candidates = sorted(candidates, key=lambda x: x["match_score"], reverse=True)
    elif strategy == "distance":
        sorted_candidates = sorted(candidates, key=lambda x: x["distance_km"])
    elif strategy == "availability":
        sorted_candidates = sorted(candidates, key=lambda x: x["availability_score"], reverse=True)
    else:
        sorted_candidates = list(candidates)

    # 计算最低救援容量需求（使用数据库配置的容量安全系数）
    min_capacity_required: int = int(estimated_trapped * capacity_safety_factor) if estimated_trapped > 0 else 0
    logger.info(f"[贪心-容量] 被困人数={estimated_trapped}，目标容量={min_capacity_required}（系数={capacity_safety_factor}）")

    # 贪心分配
    required_caps = {cap["capability_code"] for cap in capability_requirements}
    covered_caps: set = set()
    allocations: List[Dict[str, Any]] = []
    max_eta = 0.0
    total_distance = 0.0
    total_capacity = 0  # 累计救援容量
    capability_covered = False  # 标记能力是否已全覆盖
    selected_ids: set = set()  # 已选择的队伍ID，避免重复

    for candidate in sorted_candidates:
        if candidate["resource_id"] in selected_ids:
            continue
            
        candidate_caps = set(candidate["capabilities"])
        new_caps = candidate_caps - covered_caps
        assignable_caps = new_caps.intersection(required_caps)
        candidate_capacity = candidate.get("rescue_capacity", 0)

        # 决策逻辑：
        # 1. 如果有新能力可覆盖，必须选择
        # 2. 如果能力已全覆盖但容量不足，也要选择（只要有救援容量）
        should_select = False
        select_reason = ""
        
        if assignable_caps:
            should_select = True
            select_reason = f"新增能力{assignable_caps}"
        elif capability_covered and total_capacity < min_capacity_required and candidate_capacity > 0:
            should_select = True
            select_reason = f"容量不足({total_capacity}<{min_capacity_required})，增加容量{candidate_capacity}"

        if should_select:
            # 容量补充队伍：使用队伍与需求的交集能力（而非空列表）
            effective_caps = assignable_caps if assignable_caps else candidate_caps.intersection(required_caps)
            allocations.append({
                "resource_id": candidate["resource_id"],
                "resource_name": candidate["resource_name"],
                "resource_type": candidate["resource_type"],
                "assigned_capabilities": list(effective_caps),
                "match_score": candidate["match_score"],
                "distance_km": candidate["distance_km"],
                "eta_minutes": candidate.get("eta_minutes", 0),
                "rescue_capacity": candidate_capacity,
            })
            selected_ids.add(candidate["resource_id"])
            covered_caps.update(assignable_caps)
            max_eta = max(max_eta, candidate.get("eta_minutes", 0))
            total_distance = max(total_distance, candidate["distance_km"])
            total_capacity += candidate_capacity
            
            logger.info(f"【贪心-选择】{candidate['resource_name']}: {select_reason}，累计容量={total_capacity}，已覆盖能力={len(covered_caps)}/{len(required_caps)}")

        # 检查能力是否全覆盖
        if covered_caps.issuperset(required_caps):
            if not capability_covered:
                logger.info(f"[贪心-能力] 能力已全覆盖，当前容量={total_capacity}，需求={min_capacity_required}")
            capability_covered = True
            
            # 终止条件：能力全覆盖 AND 容量足够
            if estimated_trapped == 0 or total_capacity >= min_capacity_required:
                logger.info(f"[贪心-完成] 能力覆盖100%且容量足够，总容量={total_capacity}")
                break

    if not allocations:
        return None
    
    # === 冗余性增强阶段 ===
    # 统计每个能力被多少队伍覆盖
    capability_coverage_count: Dict[str, int] = {cap: 0 for cap in required_caps}
    for alloc in allocations:
        for cap in alloc.get("assigned_capabilities", []):
            if cap in capability_coverage_count:
                capability_coverage_count[cap] += 1
    
    # 找出低冗余能力（只有1个队伍覆盖）
    low_redundancy_caps = {cap for cap, count in capability_coverage_count.items() if count <= 1}
    
    if low_redundancy_caps:
        logger.info(f"[贪心-冗余] 低冗余能力: {low_redundancy_caps}，尝试增加备份队伍")
        
        # 最多额外添加2支队伍提高冗余性
        max_redundancy_teams = 2
        added_for_redundancy = 0
        
        for candidate in sorted_candidates:
            if added_for_redundancy >= max_redundancy_teams:
                break
            if candidate["resource_id"] in selected_ids:
                continue
            
            candidate_caps = set(candidate["capabilities"])
            # 检查是否能为低冗余能力提供备份
            can_backup = candidate_caps.intersection(low_redundancy_caps)
            
            if can_backup:
                allocations.append({
                    "resource_id": candidate["resource_id"],
                    "resource_name": candidate["resource_name"],
                    "resource_type": candidate["resource_type"],
                    "assigned_capabilities": list(can_backup),
                    "match_score": candidate["match_score"],
                    "distance_km": candidate["distance_km"],
                    "eta_minutes": candidate.get("eta_minutes", 0),
                    "rescue_capacity": candidate.get("rescue_capacity", 0),
                })
                selected_ids.add(candidate["resource_id"])
                total_capacity += candidate.get("rescue_capacity", 0)
                max_eta = max(max_eta, candidate.get("eta_minutes", 0))
                total_distance = max(total_distance, candidate["distance_km"])
                added_for_redundancy += 1
                
                # 更新覆盖计数
                for cap in can_backup:
                    capability_coverage_count[cap] += 1
                
                # 重新计算低冗余能力
                low_redundancy_caps = {cap for cap, count in capability_coverage_count.items() if count <= 1}
                
                logger.info(f"[贪心-冗余] 添加备份队伍: {candidate['resource_name']}，为能力{can_backup}提供备份")
        
        if added_for_redundancy > 0:
            logger.info(f"[贪心-冗余] 冗余增强完成，额外添加{added_for_redundancy}支队伍")

    if not allocations:
        return None

    # 计算方案指标
    coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
    avg_score = sum(a["match_score"] for a in allocations) / len(allocations)
    capacity_coverage = total_capacity / estimated_trapped if estimated_trapped > 0 else 1.0

    # 未覆盖的能力
    uncovered = required_caps - covered_caps
    
    # 生成容量警告（分级）
    capacity_warning: Optional[str] = None
    if estimated_trapped > 0:
        capacity_gap = estimated_trapped - total_capacity
        if capacity_coverage < 0.5:
            # 严重不足：覆盖率<50%
            capacity_warning = (
                f"🚨 救援容量严重不足！被困{estimated_trapped}人，"
                f"派出队伍总容量仅{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。必须紧急请求国家级增援！"
            )
            logger.error(f"[贪心-严重警告] {capacity_warning}")
        elif capacity_coverage < 0.8:
            # 不足：覆盖率50%-80%
            capacity_warning = (
                f"⚠️ 救援容量不足！被困{estimated_trapped}人，"
                f"派出队伍总容量{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。建议紧急请求省级增援！"
            )
            logger.warning(f"[贪心-警告] {capacity_warning}")
        elif capacity_coverage < 1.0:
            # 轻度不足：覆盖率80%-100%
            capacity_warning = (
                f"⚠ 救援容量存在缺口。被困{estimated_trapped}人，"
                f"派出队伍总容量{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。建议申请额外增援以确保全员获救。"
            )
            logger.warning(f"[贪心-提示] {capacity_warning}")

    solution: AllocationSolution = {
        "solution_id": solution_id,
        "allocations": allocations,
        "total_score": round(avg_score, 3),
        "response_time_min": round(max_eta, 1),
        "coverage_rate": round(coverage_rate, 3),
        "resource_scale": len(allocations),
        "risk_level": round(1.0 - coverage_rate, 3),
        "total_rescue_capacity": total_capacity,
        "capacity_coverage_rate": round(capacity_coverage, 3),
        "capacity_warning": capacity_warning,
        # 扩展字段
        "uncovered_capabilities": list(uncovered) if uncovered else [],
        "max_distance_km": round(total_distance, 2),
        "teams_count": len(allocations),
    }

    # 打印贪心方案汇总
    logger.info(f"【贪心方案-输出】{solution_id} (策略={strategy}):")
    logger.info(f"  - 队伍数: {len(allocations)}支")
    logger.info(f"  - 总救援容量: {total_capacity}人 (覆盖率={capacity_coverage*100:.1f}%)")
    logger.info(f"  - 能力覆盖率: {coverage_rate*100:.1f}%")
    logger.info(f"  - 最大响应时间: {max_eta:.0f}分钟")
    logger.info(f"  - 队伍列表:")
    for a in allocations:
        logger.info(f"    {a['resource_name']}: 能力={a['assigned_capabilities']}, 容量={a.get('rescue_capacity', 0)}")

    return solution


def _deduplicate_solutions(solutions: List[AllocationSolution]) -> List[AllocationSolution]:
    """去重方案（基于分配的队伍ID集合）"""
    seen: set = set()
    unique: List[AllocationSolution] = []

    for sol in solutions:
        team_ids = frozenset(a["resource_id"] for a in sol["allocations"])
        if team_ids not in seen:
            seen.add(team_ids)
            unique.append(sol)

    return unique
