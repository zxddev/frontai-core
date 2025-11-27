"""
资源调度核心算法

基于OR-LLM-Agent学术研究的设计:
- 传统算法做优化求解（CSP + NSGA-II）
- 集成真实路径规划（DBRouteEngine）获取准确ETA
- LLM只用于理解和解释（不在本模块）

核心流程:
1. 查询候选资源（数据库）
2. 批量路径规划（DBRouteEngine）
3. 能力匹配（CSP约束满足）
4. 多目标优化（NSGA-II）
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.planning.algorithms.routing import (
    DatabaseRouteEngine,
    VehicleCapability,
    RouteResult,
    Point,
    InfeasiblePathError,
    load_vehicle_capability,
    get_team_primary_vehicle,
)

from .schemas import (
    CapabilityRequirement,
    SchedulingConstraints,
    SchedulingObjectives,
    ResourceCandidate,
    ResourceType,
    RouteInfo,
    ResourceAllocation,
    SchedulingSolution,
    SchedulingResult,
)

logger = logging.getLogger(__name__)


# 队伍类型到ResourceType的映射
TEAM_TYPE_MAPPING: Dict[str, ResourceType] = {
    "fire_rescue": ResourceType.FIRE_TEAM,
    "medical": ResourceType.MEDICAL_TEAM,
    "search_rescue": ResourceType.RESCUE_TEAM,
    "hazmat": ResourceType.HAZMAT_TEAM,
    "engineering": ResourceType.ENGINEERING_TEAM,
    "water_rescue": ResourceType.WATER_RESCUE_TEAM,
    "communication": ResourceType.SUPPORT_TEAM,
    "logistics": ResourceType.SUPPORT_TEAM,
    "mine_rescue": ResourceType.RESCUE_TEAM,
    "armed_police": ResourceType.RESCUE_TEAM,
    "volunteer": ResourceType.VOLUNTEER_TEAM,
}

# 默认车辆参数（队伍无关联车辆时使用）
DEFAULT_VEHICLE_PARAMS: Dict[str, Dict[str, Any]] = {
    "fire_rescue": {"max_speed_kmh": 60, "is_all_terrain": True},
    "medical": {"max_speed_kmh": 70, "is_all_terrain": False},
    "search_rescue": {"max_speed_kmh": 50, "is_all_terrain": True},
    "hazmat": {"max_speed_kmh": 55, "is_all_terrain": False},
    "engineering": {"max_speed_kmh": 45, "is_all_terrain": True},
    "water_rescue": {"max_speed_kmh": 50, "is_all_terrain": False},
    "default": {"max_speed_kmh": 40, "is_all_terrain": False},
}


class ResourceSchedulingCore:
    """
    资源调度核心算法
    
    纯计算模块，不包含LLM调用。
    集成真实路径规划，替代直线距离估算。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化调度核心
        
        Args:
            db: SQLAlchemy异步数据库会话
        """
        self._db = db
        self._route_engine = DatabaseRouteEngine(db)

    async def schedule(
        self,
        destination_lon: float,
        destination_lat: float,
        requirements: List[CapabilityRequirement],
        constraints: Optional[SchedulingConstraints] = None,
        objectives: Optional[SchedulingObjectives] = None,
    ) -> SchedulingResult:
        """
        执行资源调度
        
        Args:
            destination_lon: 目标点经度
            destination_lat: 目标点纬度
            requirements: 能力需求列表
            constraints: 调度约束（可选，使用默认值）
            objectives: 优化目标权重（可选，使用默认值）
            
        Returns:
            SchedulingResult 包含多个Pareto最优方案
        """
        start_time = time.perf_counter()
        logger.info(
            f"[资源调度] 开始 destination=({destination_lon:.4f},{destination_lat:.4f}) "
            f"requirements={len(requirements)}"
        )

        # 使用默认约束和目标
        if constraints is None:
            constraints = SchedulingConstraints()
        if objectives is None:
            objectives = SchedulingObjectives()

        errors: List[str] = []
        warnings: List[str] = []

        # 1. 查询候选资源
        candidates = await self._query_candidates(
            destination_lon=destination_lon,
            destination_lat=destination_lat,
            requirements=requirements,
            constraints=constraints,
        )
        
        if not candidates:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            errors.append("在搜索范围内未找到任何候选资源")
            return SchedulingResult(
                success=False,
                solutions=[],
                best_solution=None,
                candidates_total=0,
                candidates_with_route=0,
                candidates_reachable=0,
                elapsed_ms=elapsed_ms,
                algorithm_used="none",
                errors=errors,
            )

        logger.info(f"[资源调度] 查询到 {len(candidates)} 个候选资源")

        # 2. 批量路径规划
        candidates_with_route = await self._plan_routes_batch(
            candidates=candidates,
            destination_lon=destination_lon,
            destination_lat=destination_lat,
            constraints=constraints,
        )
        
        # 过滤不可达的资源
        reachable_candidates = [
            c for c in candidates_with_route
            if c.route is not None and not c.route.blocked_by_disaster
        ]
        
        logger.info(
            f"[资源调度] 路径规划完成: {len(candidates_with_route)}个有路径, "
            f"{len(reachable_candidates)}个可达"
        )

        if not reachable_candidates:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            errors.append("所有候选资源均无法到达目标点")
            return SchedulingResult(
                success=False,
                solutions=[],
                best_solution=None,
                candidates_total=len(candidates),
                candidates_with_route=len(candidates_with_route),
                candidates_reachable=0,
                elapsed_ms=elapsed_ms,
                algorithm_used="none",
                errors=errors,
            )

        # 3. 计算匹配分数
        required_caps = {req.capability_code for req in requirements}
        self._calculate_match_scores(
            candidates=reachable_candidates,
            required_caps=required_caps,
            max_eta_minutes=constraints.max_response_time_minutes,
        )

        # 4. 生成分配方案
        solutions, algorithm_used = self._generate_solutions(
            candidates=reachable_candidates,
            requirements=requirements,
            constraints=constraints,
            objectives=objectives,
        )

        # 选择最佳方案
        best_solution = None
        if solutions:
            # 按综合评分排序选择最佳方案
            feasible_solutions = [s for s in solutions if s.is_feasible]
            if feasible_solutions:
                best_solution = max(
                    feasible_solutions,
                    key=lambda s: (
                        s.coverage_rate * objectives.coverage_weight +
                        (1 - s.max_eta_minutes / constraints.max_response_time_minutes) * objectives.response_time_weight +
                        s.avg_match_score * 0.2
                    )
                )
            elif solutions:
                best_solution = solutions[0]

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            f"[资源调度] 完成: {len(solutions)}个方案, "
            f"算法={algorithm_used}, 耗时{elapsed_ms}ms"
        )

        return SchedulingResult(
            success=len(solutions) > 0,
            solutions=solutions,
            best_solution=best_solution,
            candidates_total=len(candidates),
            candidates_with_route=len(candidates_with_route),
            candidates_reachable=len(reachable_candidates),
            elapsed_ms=elapsed_ms,
            algorithm_used=algorithm_used,
            errors=errors,
            warnings=warnings,
        )

    async def _query_candidates(
        self,
        destination_lon: float,
        destination_lat: float,
        requirements: List[CapabilityRequirement],
        constraints: SchedulingConstraints,
    ) -> List[ResourceCandidate]:
        """
        从数据库查询候选资源
        
        根据能力需求和约束条件查询可用的队伍。
        使用PostGIS ST_Distance计算直线距离，进行初步过滤。
        """
        # 计算最大搜索距离（基于最大响应时间和默认速度）
        max_speed_kmh = 70  # 使用较高速度估算最大范围
        max_distance_km = (constraints.max_response_time_minutes / 60) * max_speed_kmh * 1.5

        # 构建能力过滤条件
        required_caps = [req.capability_code for req in requirements]
        
        # 构建排除资源条件
        excluded_ids = list(constraints.excluded_resource_ids) if constraints.excluded_resource_ids else []

        sql = text("""
            WITH team_vehicles AS (
                SELECT DISTINCT ON (tv.team_id)
                    tv.team_id,
                    v.id as vehicle_id,
                    v.code as vehicle_code,
                    v.max_speed_kmh,
                    v.is_all_terrain,
                    v.terrain_capabilities,
                    v.terrain_speed_factors,
                    v.max_gradient_percent,
                    v.max_wading_depth_m,
                    v.width_m,
                    v.height_m,
                    (v.self_weight_kg + v.max_weight_kg) as total_weight_kg
                FROM operational_v2.team_vehicles_v2 tv
                JOIN operational_v2.vehicles_v2 v ON tv.vehicle_id = v.id
                WHERE tv.status = 'available'
                ORDER BY tv.team_id, tv.is_primary DESC, tv.assigned_at ASC
            )
            SELECT 
                t.id,
                t.name,
                t.team_type::text,
                t.capability_level,
                ARRAY_AGG(DISTINCT tc.capability_code) as capabilities,
                ST_X(t.base_location::geometry) as base_lon,
                ST_Y(t.base_location::geometry) as base_lat,
                t.base_address,
                COALESCE(t.available_personnel, t.total_personnel, 10) as personnel_count,
                COALESCE(t.rescue_capacity, 0) as rescue_capacity,
                tv.vehicle_id,
                tv.vehicle_code,
                COALESCE(tv.max_speed_kmh, 50) as max_speed_kmh,
                COALESCE(tv.is_all_terrain, false) as is_all_terrain,
                tv.terrain_capabilities,
                tv.terrain_speed_factors,
                tv.max_gradient_percent,
                tv.max_wading_depth_m,
                tv.width_m,
                tv.height_m,
                tv.total_weight_kg,
                ST_Distance(
                    t.base_location::geography,
                    ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography
                ) / 1000.0 as distance_km
            FROM operational_v2.rescue_teams_v2 t
            JOIN operational_v2.team_capabilities_v2 tc ON t.id = tc.team_id
            LEFT JOIN team_vehicles tv ON t.id = tv.team_id
            WHERE t.status = 'available'
            AND ST_DWithin(
                t.base_location::geography,
                ST_SetSRID(ST_MakePoint(:dest_lon, :dest_lat), 4326)::geography,
                :max_distance_m
            )
            AND tc.capability_code = ANY(:required_caps)
            AND (CARDINALITY(:excluded_ids::uuid[]) = 0 OR t.id != ALL(:excluded_ids::uuid[]))
            GROUP BY t.id, t.name, t.team_type, t.capability_level,
                     t.base_location, t.base_address, t.available_personnel,
                     t.total_personnel, t.rescue_capacity,
                     tv.vehicle_id, tv.vehicle_code, tv.max_speed_kmh,
                     tv.is_all_terrain, tv.terrain_capabilities, tv.terrain_speed_factors,
                     tv.max_gradient_percent, tv.max_wading_depth_m,
                     tv.width_m, tv.height_m, tv.total_weight_kg
            ORDER BY distance_km ASC
            LIMIT :max_teams
        """)

        result = await self._db.execute(sql, {
            "dest_lon": destination_lon,
            "dest_lat": destination_lat,
            "max_distance_m": max_distance_km * 1000,
            "required_caps": required_caps,
            "excluded_ids": excluded_ids,
            "max_teams": constraints.max_resources * 3,  # 查询更多以供筛选
        })

        candidates: List[ResourceCandidate] = []
        for row in result.fetchall():
            team_type = row[2] or "default"
            resource_type = TEAM_TYPE_MAPPING.get(team_type, ResourceType.RESCUE_TEAM)
            
            # 获取默认车辆参数
            default_params = DEFAULT_VEHICLE_PARAMS.get(
                team_type,
                DEFAULT_VEHICLE_PARAMS["default"]
            )

            candidate = ResourceCandidate(
                resource_id=row[0],
                resource_name=row[1],
                resource_type=resource_type,
                capabilities=list(row[4] or []),
                capability_level=row[3] or 3,
                base_lon=row[5],
                base_lat=row[6],
                base_address=row[7] or "",
                personnel_count=row[8] or 0,
                rescue_capacity=row[9] or 0,
                vehicle_id=row[10],
                vehicle_code=row[11],
                max_speed_kmh=row[12] or default_params["max_speed_kmh"],
                is_all_terrain=row[13] if row[13] is not None else default_params["is_all_terrain"],
            )
            candidate.direct_distance_km = row[21]  # distance_km
            candidates.append(candidate)

        return candidates

    async def _plan_routes_batch(
        self,
        candidates: List[ResourceCandidate],
        destination_lon: float,
        destination_lat: float,
        constraints: SchedulingConstraints,
    ) -> List[ResourceCandidate]:
        """
        批量规划路径
        
        为每个候选资源规划从驻地到目标点的路径。
        使用并发加速，但限制并发数避免数据库压力。
        """
        destination = Point(lon=destination_lon, lat=destination_lat)
        
        async def plan_single_route(candidate: ResourceCandidate) -> ResourceCandidate:
            """为单个资源规划路径"""
            origin = Point(lon=candidate.base_lon, lat=candidate.base_lat)
            
            # 构建车辆能力参数
            vehicle = VehicleCapability(
                vehicle_id=candidate.vehicle_id or candidate.resource_id,
                vehicle_code=candidate.vehicle_code or f"team_{candidate.resource_id.hex[:8]}",
                max_speed_kmh=candidate.max_speed_kmh,
                is_all_terrain=candidate.is_all_terrain,
                terrain_capabilities=["mountain", "rural"] if candidate.is_all_terrain else ["urban", "suburban"],
                terrain_speed_factors={},
                max_gradient_percent=30 if candidate.is_all_terrain else 15,
                max_wading_depth_m=0.5 if candidate.is_all_terrain else 0.2,
                width_m=None,
                height_m=None,
                total_weight_kg=None,
            )

            try:
                route_result = await self._route_engine.plan_route(
                    start=origin,
                    end=destination,
                    vehicle=vehicle,
                    scenario_id=constraints.scenario_id if constraints.avoid_disaster_areas else None,
                    search_radius_km=max(100.0, candidate.direct_distance_km * 2),
                )
                
                candidate.route = RouteInfo(
                    origin_lon=origin.lon,
                    origin_lat=origin.lat,
                    destination_lon=destination.lon,
                    destination_lat=destination.lat,
                    distance_m=route_result.distance_m,
                    duration_seconds=route_result.duration_seconds,
                    path_edge_count=len(route_result.path_edges),
                    blocked_by_disaster=route_result.blocked_by_disaster,
                    warnings=route_result.warnings,
                )
            except InfeasiblePathError as e:
                logger.warning(
                    f"[路径规划] 资源 {candidate.resource_name} 无可行路径: {e}"
                )
                candidate.route = None
            except Exception as e:
                logger.error(
                    f"[路径规划] 资源 {candidate.resource_name} 路径规划失败: {e}"
                )
                candidate.route = None
            
            return candidate

        # 限制并发数
        semaphore = asyncio.Semaphore(5)
        
        async def limited_plan(candidate: ResourceCandidate) -> ResourceCandidate:
            async with semaphore:
                return await plan_single_route(candidate)

        # 并发执行路径规划
        tasks = [limited_plan(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_candidates: List[ResourceCandidate] = []
        for result in results:
            if isinstance(result, ResourceCandidate):
                valid_candidates.append(result)
            elif isinstance(result, Exception):
                logger.error(f"[路径规划] 异常: {result}")
        
        return valid_candidates

    def _calculate_match_scores(
        self,
        candidates: List[ResourceCandidate],
        required_caps: Set[str],
        max_eta_minutes: float,
    ) -> None:
        """
        计算候选资源的匹配分数
        
        评分维度:
        - 能力覆盖率 (50%)
        - 响应时间 (30%)
        - 能力等级 (20%)
        """
        for candidate in candidates:
            # 能力覆盖率
            matched_caps = set(candidate.capabilities) & required_caps
            capability_score = len(matched_caps) / len(required_caps) if required_caps else 0

            # 响应时间评分（ETA越短分数越高）
            eta = candidate.eta_minutes
            time_score = max(0, 1.0 - eta / max_eta_minutes) if max_eta_minutes > 0 else 0

            # 能力等级评分
            level_score = candidate.capability_level / 5.0

            # 综合得分
            candidate.match_score = round(
                capability_score * 0.50 +
                time_score * 0.30 +
                level_score * 0.20,
                3
            )

    def _generate_solutions(
        self,
        candidates: List[ResourceCandidate],
        requirements: List[CapabilityRequirement],
        constraints: SchedulingConstraints,
        objectives: SchedulingObjectives,
    ) -> Tuple[List[SchedulingSolution], str]:
        """
        生成分配方案
        
        尝试使用NSGA-II多目标优化，失败时退化为贪心策略。
        """
        required_caps = {req.capability_code for req in requirements}
        algorithm_used = "greedy"
        solutions: List[SchedulingSolution] = []

        # 尝试NSGA-II（候选资源>10时效果更好）
        if len(candidates) > 10:
            try:
                nsga_solutions = self._run_nsga2_optimization(
                    candidates=candidates,
                    required_caps=required_caps,
                    constraints=constraints,
                )
                if nsga_solutions:
                    solutions.extend(nsga_solutions)
                    algorithm_used = "nsga2"
                    logger.info(f"[NSGA-II] 生成 {len(nsga_solutions)} 个Pareto解")
            except Exception as e:
                logger.warning(f"[NSGA-II] 优化失败，使用贪心策略: {e}")

        # 贪心策略生成备选方案
        greedy_strategies = ["match_score", "eta", "capacity"]
        for strategy in greedy_strategies:
            solution = self._generate_greedy_solution(
                candidates=candidates,
                required_caps=required_caps,
                constraints=constraints,
                strategy=strategy,
            )
            if solution:
                solutions.append(solution)

        # 去重
        solutions = self._deduplicate_solutions(solutions)

        return solutions, algorithm_used

    def _run_nsga2_optimization(
        self,
        candidates: List[ResourceCandidate],
        required_caps: Set[str],
        constraints: SchedulingConstraints,
    ) -> List[SchedulingSolution]:
        """
        使用NSGA-II进行多目标优化
        
        优化目标:
        1. 最小化最大响应时间
        2. 最大化能力覆盖率
        3. 最小化资源数量（成本）
        """
        try:
            from pymoo.algorithms.moo.nsga2 import NSGA2
            from pymoo.operators.sampling.rnd import BinaryRandomSampling
            from pymoo.operators.crossover.sbx import SBX
            from pymoo.operators.mutation.pm import PM
            from pymoo.optimize import minimize
            from pymoo.core.problem import Problem
            import numpy as np
        except ImportError:
            logger.warning("[NSGA-II] pymoo未安装")
            raise ImportError("pymoo not installed")

        n_resources = len(candidates)

        class AllocationProblem(Problem):
            def __init__(prob_self):
                super().__init__(
                    n_var=n_resources,
                    n_obj=3,
                    n_constr=1,
                    xl=0,
                    xu=1,
                    vtype=int,
                )

            def _evaluate(prob_self, X, out, *args, **kwargs):
                F = []
                G = []
                
                for x in X:
                    selected = np.where(x > 0.5)[0]
                    
                    if len(selected) == 0:
                        F.append([1000, 0, 100])
                        G.append([1.0])
                        continue
                    
                    # 计算指标
                    max_eta = 0.0
                    covered: Set[str] = set()
                    
                    for idx in selected:
                        c = candidates[int(idx)]
                        max_eta = max(max_eta, c.eta_minutes)
                        covered.update(c.capabilities)
                    
                    coverage = len(covered & required_caps) / len(required_caps) if required_caps else 1.0
                    
                    F.append([max_eta, -coverage, len(selected)])
                    G.append([constraints.min_coverage_rate - coverage])
                
                out["F"] = np.array(F)
                out["G"] = np.array(G)

        problem = AllocationProblem()
        algorithm = NSGA2(
            pop_size=50,
            sampling=BinaryRandomSampling(),
            crossover=SBX(prob=0.9, eta=15),
            mutation=PM(eta=20),
            eliminate_duplicates=True,
        )

        result = minimize(
            problem,
            algorithm,
            termination=("n_gen", 50),
            seed=42,
            verbose=False,
        )

        if result.X is None or len(result.X) == 0:
            return []

        # 转换为SchedulingSolution
        solutions: List[SchedulingSolution] = []
        seen: Set[frozenset] = set()
        
        X_array = result.X if len(result.X.shape) == 2 else [result.X]
        
        for sol_idx, x in enumerate(X_array):
            selected = [int(i) for i in np.where(x > 0.5)[0]]
            if not selected:
                continue
            
            key = frozenset(selected)
            if key in seen:
                continue
            seen.add(key)
            
            solution = self._build_solution(
                candidates=[candidates[i] for i in selected],
                required_caps=required_caps,
                constraints=constraints,
                strategy=f"nsga2_{sol_idx}",
            )
            if solution:
                solutions.append(solution)

        return solutions

    def _generate_greedy_solution(
        self,
        candidates: List[ResourceCandidate],
        required_caps: Set[str],
        constraints: SchedulingConstraints,
        strategy: str,
    ) -> Optional[SchedulingSolution]:
        """
        使用贪心策略生成分配方案
        """
        # 按策略排序
        if strategy == "match_score":
            sorted_candidates = sorted(candidates, key=lambda x: x.match_score, reverse=True)
        elif strategy == "eta":
            sorted_candidates = sorted(candidates, key=lambda x: x.eta_minutes)
        elif strategy == "capacity":
            sorted_candidates = sorted(candidates, key=lambda x: x.rescue_capacity, reverse=True)
        else:
            sorted_candidates = list(candidates)

        # 贪心选择
        selected: List[ResourceCandidate] = []
        covered: Set[str] = set()
        total_capacity = 0

        for candidate in sorted_candidates:
            assignable = set(candidate.capabilities) & required_caps
            new_caps = assignable - covered
            
            # 选择条件: 有新能力 或 覆盖不足 或 容量不足
            should_select = (
                bool(new_caps) or
                len(covered) < len(required_caps) * constraints.min_coverage_rate or
                total_capacity < constraints.min_rescue_capacity
            )
            
            if should_select:
                selected.append(candidate)
                covered.update(assignable)
                total_capacity += candidate.rescue_capacity
            
            # 停止条件
            if (
                len(covered) >= len(required_caps) and
                total_capacity >= constraints.min_rescue_capacity and
                len(selected) >= 3  # 至少3个资源确保冗余
            ):
                break
            
            if len(selected) >= constraints.max_resources:
                break

        if not selected:
            return None

        return self._build_solution(
            candidates=selected,
            required_caps=required_caps,
            constraints=constraints,
            strategy=f"greedy_{strategy}",
        )

    def _build_solution(
        self,
        candidates: List[ResourceCandidate],
        required_caps: Set[str],
        constraints: SchedulingConstraints,
        strategy: str,
    ) -> SchedulingSolution:
        """
        构建调度方案
        """
        allocations: List[ResourceAllocation] = []
        covered: Set[str] = set()
        max_eta = 0.0
        total_eta = 0.0
        total_capacity = 0

        for candidate in candidates:
            assignable = set(candidate.capabilities) & required_caps
            new_caps = assignable - covered
            
            allocation = ResourceAllocation(
                resource_id=candidate.resource_id,
                resource_name=candidate.resource_name,
                resource_type=candidate.resource_type,
                assigned_capabilities=list(new_caps) if new_caps else list(assignable),
                direct_distance_km=candidate.direct_distance_km,
                road_distance_km=candidate.road_distance_km,
                eta_minutes=candidate.eta_minutes,
                match_score=candidate.match_score,
                rescue_capacity=candidate.rescue_capacity,
            )
            allocations.append(allocation)
            
            covered.update(assignable)
            max_eta = max(max_eta, candidate.eta_minutes)
            total_eta += candidate.eta_minutes
            total_capacity += candidate.rescue_capacity

        coverage_rate = len(covered & required_caps) / len(required_caps) if required_caps else 1.0
        avg_score = sum(a.match_score for a in allocations) / len(allocations) if allocations else 0

        # 判断是否可行
        is_feasible = (
            coverage_rate >= constraints.min_coverage_rate and
            max_eta <= constraints.max_response_time_minutes and
            total_capacity >= constraints.min_rescue_capacity
        )

        warnings: List[str] = []
        if coverage_rate < constraints.min_coverage_rate:
            warnings.append(f"覆盖率{coverage_rate:.1%}低于要求{constraints.min_coverage_rate:.1%}")
        if max_eta > constraints.max_response_time_minutes:
            warnings.append(f"响应时间{max_eta:.1f}分钟超过限制{constraints.max_response_time_minutes:.1f}分钟")

        return SchedulingSolution(
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            allocations=allocations,
            max_eta_minutes=round(max_eta, 1),
            total_eta_minutes=round(total_eta, 1),
            coverage_rate=round(coverage_rate, 3),
            total_capacity=total_capacity,
            resource_count=len(allocations),
            avg_match_score=round(avg_score, 3),
            strategy=strategy,
            is_feasible=is_feasible,
            warnings=warnings,
        )

    def _deduplicate_solutions(
        self,
        solutions: List[SchedulingSolution],
    ) -> List[SchedulingSolution]:
        """
        去重方案
        """
        seen: Set[frozenset] = set()
        unique: List[SchedulingSolution] = []
        
        for solution in solutions:
            key = frozenset(a.resource_id for a in solution.allocations)
            if key not in seen:
                seen.add(key)
                unique.append(solution)
        
        return unique

    @staticmethod
    def haversine_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        """计算两点间的球面距离（米）"""
        R = 6371000
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (
            math.sin(dlat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
