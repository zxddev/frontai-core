"""
阶段3: 资源匹配节点

从数据库查询真实救援队伍，根据事件坐标计算距离和响应时间，
按时间约束过滤并进行能力匹配。
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from ..state import EmergencyAIState, ResourceCandidate, AllocationSolution

logger = logging.getLogger(__name__)

# 平均救援车辆行驶速度（km/h），用于计算响应时间
AVERAGE_SPEED_KMH: float = 40.0

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

    # 获取能力需求
    capability_requirements = state.get("capability_requirements", [])
    if not capability_requirements:
        logger.warning("[资源匹配] 无能力需求，跳过资源匹配")
        return {"resource_candidates": [], "trace": trace}

    required_caps = {cap["capability_code"] for cap in capability_requirements}
    logger.info(f"[资源匹配] 需要的能力: {required_caps}")

    # 获取约束条件
    constraints = state.get("constraints", {})
    
    # 获取灾害等级和队伍数量上限
    disaster_scale = _determine_disaster_scale(state)
    max_teams = constraints.get("max_teams", DISASTER_SCALE_LIMITS.get(disaster_scale, DEFAULT_MAX_TEAMS))
    logger.info(f"[资源匹配] 灾害等级: {disaster_scale}，队伍上限: {max_teams}")

    # 获取时间约束
    max_response_hours = constraints.get("max_response_time_hours", 2.0)
    initial_max_distance = max_response_hours * AVERAGE_SPEED_KMH
    logger.info(f"[资源匹配] 时间约束: {max_response_hours}小时，初始搜索距离: {initial_max_distance}km")

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

    # 计算匹配分数
    candidates = _calculate_match_scores(
        teams=teams,
        required_capabilities=required_caps,
        event_lat=event_lat,
        event_lng=event_lng,
        max_response_hours=max_response_hours,
    )

    # 按匹配分数排序
    candidates.sort(key=lambda x: x["match_score"], reverse=True)

    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_resources"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["database_query", "capability_matching"]
    trace["teams_queried"] = len(teams)
    trace["candidates_count"] = len(candidates)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[资源匹配] 完成，查询{len(teams)}支队伍，生成{len(candidates)}个候选，耗时{elapsed_ms}ms"
    )

    return {
        "resource_candidates": candidates,
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
        )
        if solution1:
            solutions.append(solution1)

        # 方案2: 最短响应时间优先（按距离排序）
        solution2 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="distance",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
        )
        if solution2:
            solutions.append(solution2)

        # 方案3: 最高可用性优先
        solution3 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="availability",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
        )
        if solution3:
            solutions.append(solution3)

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
) -> List[AllocationSolution]:
    """
    使用NSGA-II进行多目标优化
    
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
    logger.info(f"[NSGA-II] 开始多目标优化")
    logger.info(f"  - 候选资源数: {len(candidates)}")
    logger.info(f"  - 能力需求数: {len(capability_requirements)}")
    logger.info(f"  - 任务序列长度: {len(task_sequence)}")
    logger.info(f"  - 目标解数量: {n_solutions}")
    
    try:
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
        from pymoo.operators.sampling.rnd import BinaryRandomSampling
        from pymoo.optimize import minimize
        from pymoo.core.problem import Problem
        import numpy as np
        logger.info(f"[NSGA-II] pymoo库导入成功")
    except ImportError:
        logger.warning("[NSGA-II] pymoo未安装，使用贪心策略")
        raise ImportError("pymoo not installed")

    required_caps = {cap["capability_code"] for cap in capability_requirements}
    n_resources = len(candidates)
    logger.info(f"[NSGA-II] 需求能力: {required_caps}")
    
    if n_resources == 0:
        logger.warning("[NSGA-II] 无候选资源，返回空")
        return []

    class EmergencyAllocationProblem(Problem):
        """应急资源分配问题定义"""
        
        def __init__(self):
            # 决策变量：每个候选资源是否选中（0/1）
            super().__init__(
                n_var=n_resources,
                n_obj=3,  # 响应时间、覆盖率、队伍数量（成本代理）
                n_constr=1,  # 至少覆盖70%能力
                xl=0,
                xu=1,
                vtype=int,
            )
        
        def _evaluate(self, X, out, *args, **kwargs):
            F = []  # 目标函数值
            G = []  # 约束函数值
            
            for x in X:
                selected_indices = np.where(x > 0.5)[0]
                
                if len(selected_indices) == 0:
                    # 无选中资源，惩罚
                    F.append([1000, 0, 1000])
                    G.append([1.0])  # 违反约束
                    continue
                
                # 计算响应时间（最大ETA）
                max_eta = 0.0
                covered_caps: set = set()
                total_score = 0.0
                
                for idx in selected_indices:
                    cand = candidates[idx]
                    max_eta = max(max_eta, cand.get("eta_minutes", 0))
                    covered_caps.update(cand["capabilities"])
                    total_score += cand["match_score"]
                
                # 覆盖率（负值因为要最大化）
                coverage = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
                
                # 目标：响应时间（最小化）、-覆盖率（最小化以最大化覆盖）、队伍数量（最小化成本）
                F.append([max_eta, -coverage, len(selected_indices)])
                
                # 约束：覆盖率>=70%
                G.append([0.7 - coverage])
            
            out["F"] = np.array(F)
            out["G"] = np.array(G)

    problem = EmergencyAllocationProblem()
    
    logger.info(f"[NSGA-II] 配置算法参数:")
    logger.info(f"  - pop_size: 50 (种群大小)")
    logger.info(f"  - n_gen: 50 (迭代代数)")
    logger.info(f"  - n_var: {n_resources} (决策变量数)")
    logger.info(f"  - n_obj: 3 (目标数: 响应时间/覆盖率/队伍数)")
    logger.info(f"  - n_constr: 1 (约束: 覆盖率>=70%)")
    
    algorithm = NSGA2(
        pop_size=50,
        sampling=BinaryRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True,
    )
    
    logger.info(f"[NSGA-II] 开始优化迭代...")
    import time as time_module
    start_opt = time_module.time()
    
    result = minimize(
        problem,
        algorithm,
        termination=("n_gen", 50),
        seed=42,
        verbose=False,
    )
    
    elapsed_opt = int((time_module.time() - start_opt) * 1000)
    logger.info(f"[NSGA-II] 优化完成，耗时{elapsed_opt}ms")
    
    if result.X is None or len(result.X) == 0:
        logger.warning("[NSGA-II] 无可行解")
        return []
    
    logger.info(f"[NSGA-II] 找到Pareto前沿解")
    
    # 转换为AllocationSolution
    solutions: List[AllocationSolution] = []
    seen_solutions: set = set()
    
    # 处理结果（可能是单解或多解）
    X_array = result.X if len(result.X.shape) == 2 else [result.X]
    F_array = result.F if len(result.F.shape) == 2 else [result.F]
    
    for sol_idx, (x, f) in enumerate(zip(X_array, F_array)):
        selected_indices = np.where(x > 0.5)[0]
        if len(selected_indices) == 0:
            continue
        
        # 去重
        sol_key = frozenset(int(i) for i in selected_indices)
        if sol_key in seen_solutions:
            continue
        seen_solutions.add(sol_key)
        
        # 构建分配方案
        allocations: List[Dict[str, Any]] = []
        covered_caps: set = set()
        max_eta = 0.0
        
        for idx in selected_indices:
            cand = candidates[int(idx)]
            assignable_caps = set(cand["capabilities"]).intersection(required_caps) - covered_caps
            
            allocations.append({
                "resource_id": cand["resource_id"],
                "resource_name": cand["resource_name"],
                "resource_type": cand["resource_type"],
                "assigned_capabilities": list(assignable_caps) if assignable_caps else cand["capabilities"],
                "match_score": cand["match_score"],
                "distance_km": cand["distance_km"],
                "eta_minutes": cand.get("eta_minutes", 0),
            })
            covered_caps.update(cand["capabilities"])
            max_eta = max(max_eta, cand.get("eta_minutes", 0))
        
        coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
        avg_score = sum(a["match_score"] for a in allocations) / len(allocations) if allocations else 0
        
        solution: AllocationSolution = {
            "solution_id": f"nsga-{uuid.uuid4().hex[:8]}",
            "allocations": allocations,
            "total_score": round(avg_score, 3),
            "response_time_min": round(max_eta, 1),
            "coverage_rate": round(coverage_rate, 3),
            "cost_estimate": len(allocations) * 1000,
            "risk_level": round(1.0 - coverage_rate, 3),
            "teams_count": len(allocations),
            "objectives": {
                "response_time": round(float(f[0]), 1),
                "coverage_rate": round(-float(f[1]), 3),
                "teams_count": int(f[2]),
            },
        }
        solutions.append(solution)
        
        if len(solutions) >= n_solutions:
            break
    
    # 按覆盖率降序排序
    solutions.sort(key=lambda s: s["coverage_rate"], reverse=True)
    
    return solutions


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
    关联team_capabilities_v2获取能力列表。

    Args:
        db: 数据库会话
        event_lat: 事件纬度
        event_lng: 事件经度
        max_distance_km: 最大距离（公里）
        max_teams: 返回的最大队伍数量

    Returns:
        队伍列表，每个队伍包含id, name, type, capabilities, distance_m等
    """
    sql = text("""
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
            ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
            ) AS distance_m
        FROM operational_v2.rescue_teams_v2 t
        LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
        WHERE t.status = 'standby'
          AND t.base_location IS NOT NULL
          AND ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
              ) <= :max_distance_m
        GROUP BY t.id
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
            }
            teams.append(team)

        logger.info(f"[数据库查询] 查询到{len(teams)}支队伍")
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
) -> List[ResourceCandidate]:
    """
    计算每个队伍的匹配分数

    评分维度：
    - 能力覆盖率（50%）：队伍能力与需求的交集比例
    - 距离评分（30%）：距离越近分数越高
    - 能力等级（20%）：capability_level越高分数越高

    Args:
        teams: 队伍列表
        required_capabilities: 需要的能力集合
        event_lat: 事件纬度
        event_lng: 事件经度
        max_response_hours: 最大响应时间（小时）

    Returns:
        ResourceCandidate列表
    """
    candidates: List[ResourceCandidate] = []
    max_distance_km = max_response_hours * AVERAGE_SPEED_KMH

    for team in teams:
        team_caps = set(team.get("capabilities", []))
        matched_caps = team_caps.intersection(required_capabilities)

        # 无匹配能力则跳过
        if not matched_caps:
            continue

        # 能力覆盖率评分
        capability_score = len(matched_caps) / len(required_capabilities) if required_capabilities else 0

        # 距离评分（距离越近越好）
        distance_km = team.get("distance_km", 0)
        distance_score = max(0, 1.0 - distance_km / max_distance_km) if max_distance_km > 0 else 0

        # 能力等级评分（1-5映射到0.2-1.0）
        capability_level = team.get("capability_level", 3)
        level_score = capability_level / 5.0

        # 计算响应时间（分钟）
        eta_minutes = (distance_km / AVERAGE_SPEED_KMH) * 60 if distance_km > 0 else 0

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
            "capabilities": list(matched_caps),
            "distance_km": round(distance_km, 2),
            "availability_score": 1.0,  # 数据库查询已过滤standby状态
            "match_score": round(match_score, 3),
            # 扩展字段
            "eta_minutes": round(eta_minutes, 1),
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
    }
    return mapping.get(team_type, "RESCUE_TEAM")


def _generate_greedy_solution(
    candidates: List[ResourceCandidate],
    capability_requirements: List[Dict[str, Any]],
    strategy: str,
    solution_id: str,
) -> Optional[AllocationSolution]:
    """
    使用贪心策略生成分配方案

    Args:
        candidates: 候选资源列表
        capability_requirements: 能力需求列表
        strategy: 策略 (match_score/distance/availability)
        solution_id: 方案ID

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

    # 贪心分配
    required_caps = {cap["capability_code"] for cap in capability_requirements}
    covered_caps: set = set()
    allocations: List[Dict[str, Any]] = []
    max_eta = 0.0
    total_distance = 0.0

    for candidate in sorted_candidates:
        candidate_caps = set(candidate["capabilities"])
        new_caps = candidate_caps - covered_caps
        assignable_caps = new_caps.intersection(required_caps)

        if assignable_caps:
            allocations.append({
                "resource_id": candidate["resource_id"],
                "resource_name": candidate["resource_name"],
                "resource_type": candidate["resource_type"],
                "assigned_capabilities": list(assignable_caps),
                "match_score": candidate["match_score"],
                "distance_km": candidate["distance_km"],
                "eta_minutes": candidate.get("eta_minutes", 0),
            })
            covered_caps.update(assignable_caps)
            max_eta = max(max_eta, candidate.get("eta_minutes", 0))
            total_distance = max(total_distance, candidate["distance_km"])

        # 所有能力都已覆盖
        if covered_caps.issuperset(required_caps):
            break

    if not allocations:
        return None

    # 计算方案指标
    coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
    avg_score = sum(a["match_score"] for a in allocations) / len(allocations)

    # 未覆盖的能力
    uncovered = required_caps - covered_caps

    solution: AllocationSolution = {
        "solution_id": solution_id,
        "allocations": allocations,
        "total_score": round(avg_score, 3),
        "response_time_min": round(max_eta, 1),
        "coverage_rate": round(coverage_rate, 3),
        "cost_estimate": len(allocations) * 1000,
        "risk_level": round(1.0 - coverage_rate, 3),
        # 扩展字段
        "uncovered_capabilities": list(uncovered) if uncovered else [],
        "max_distance_km": round(total_distance, 2),
        "teams_count": len(allocations),
    }

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
