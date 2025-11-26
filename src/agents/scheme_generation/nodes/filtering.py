"""
过滤和评分节点

硬规则过滤 + 软规则评分（TOPSIS）
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from ..state import (
    SchemeGenerationState,
    HardRuleResultState,
    SchemeScoreState,
    ParetoSolutionState,
)
from ...rules import TRRRuleEngine
from ..utils import track_node_time

logger = logging.getLogger(__name__)

# 软规则评分权重
SOFT_RULE_WEIGHTS = {
    "response_time": 0.35,
    "coverage_rate": 0.30,
    "cost": 0.15,
    "risk": 0.20,
}


@track_node_time("filter_hard_rules")
def filter_hard_rules(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    硬规则过滤节点
    
    对每个Pareto解进行硬规则检查，过滤不可行方案
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含hard_rule_results和feasible_schemes
    """
    logger.info("开始执行硬规则过滤节点")
    
    pareto_solutions = state.get("pareto_solutions", [])
    resource_allocations = state.get("resource_allocations", [])
    resource_candidates = state.get("resource_candidates", [])  # 包含完整能力
    capability_requirements = state.get("capability_requirements", [])
    event_analysis = state.get("event_analysis", {})
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    engine = TRRRuleEngine()
    
    all_hard_rule_results: List[HardRuleResultState] = []
    feasible_schemes: List[Dict[str, Any]] = []
    
    for solution in pareto_solutions:
        # 构造方案数据用于硬规则检查
        # 使用resource_candidates（包含完整能力）计算覆盖率
        scheme_data = _build_scheme_data_for_check(
            solution=solution,
            resource_candidates=resource_candidates,
            capability_requirements=capability_requirements,
            event_analysis=event_analysis,
        )
        
        # 执行硬规则检查
        results = engine.check_hard_rules(scheme_data)
        
        # 转换为状态格式
        rule_results: List[HardRuleResultState] = []
        for r in results:
            rule_result: HardRuleResultState = {
                "rule_id": r.rule_id,
                "rule_name": r.rule_name,
                "passed": r.passed,
                "action": r.action.value,
                "message": r.message,
                "severity": r.severity.value,
            }
            rule_results.append(rule_result)
        
        all_hard_rule_results.extend(rule_results)
        
        # 检查是否可行
        is_feasible = engine.is_scheme_feasible(results)
        
        if is_feasible:
            feasible_scheme = {
                "solution_id": solution["solution_id"],
                "objectives": solution["objectives"],
                "variables": solution["variables"],
                "hard_rule_results": rule_results,
                "warnings": [r for r in rule_results if not r["passed"] and r["action"] == "warn"],
            }
            feasible_schemes.append(feasible_scheme)
            logger.debug(f"方案{solution['solution_id']}通过硬规则检查")
        else:
            rejected_rules = [r for r in rule_results if not r["passed"] and r["action"] == "reject"]
            logger.info(f"方案{solution['solution_id']}被否决: {[r['rule_id'] for r in rejected_rules]}")
    
    logger.info(f"硬规则过滤完成: {len(feasible_schemes)}/{len(pareto_solutions)}个方案可行")
    
    # 更新追踪信息
    trace["hard_rules_checked"] = list(set(r["rule_id"] for r in all_hard_rule_results))
    trace["feasible_schemes_count"] = len(feasible_schemes)
    trace["rejected_schemes_count"] = len(pareto_solutions) - len(feasible_schemes)
    trace.setdefault("nodes_executed", []).append("filter_hard_rules")
    
    return {
        "hard_rule_results": all_hard_rule_results,
        "feasible_schemes": feasible_schemes,
        "trace": trace,
        "errors": errors,
    }


def _build_scheme_data_for_check(
    solution: ParetoSolutionState,
    resource_candidates: List[Dict[str, Any]],
    capability_requirements: List[Dict[str, Any]],
    event_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构造用于硬规则检查的方案数据
    
    使用resource_candidates（包含队伍完整能力）计算覆盖率
    """
    objectives = solution.get("objectives", {})
    
    # 计算能力覆盖率：基于队伍的完整capabilities字段
    critical_caps = {r["code"] for r in capability_requirements if r.get("priority") == "critical"}
    high_caps = {r["code"] for r in capability_requirements if r.get("priority") == "high"}
    
    # 收集所有队伍的完整能力
    covered_caps = set()
    for candidate in resource_candidates:
        caps = candidate.get("capabilities", [])
        covered_caps.update(caps)
    
    # 计算覆盖率
    critical_covered = critical_caps & covered_caps
    high_covered = high_caps & covered_caps
    
    critical_coverage = len(critical_covered) / len(critical_caps) if critical_caps else 1.0
    high_coverage = len(high_covered) / len(high_caps) if high_caps else 1.0
    
    logger.debug(f"能力覆盖率: critical={critical_coverage:.0%} ({len(critical_covered)}/{len(critical_caps)}), high={high_coverage:.0%} ({len(high_covered)}/{len(high_caps)})")
    
    # 构造数据
    data = {
        # 风险指标
        "rescue_risk": objectives.get("risk", 0.05),
        
        # 时间指标
        "response_time_minutes": objectives.get("response_time", 15),
        "golden_hour_minutes": 60,
        "first_arrival_minutes": objectives.get("response_time", 15),
        
        # 能力覆盖
        "critical_capability_coverage": min(1.0, critical_coverage),
        "high_capability_coverage": min(1.0, high_coverage),
        
        # 资源可用性
        "unavailable_critical_resources": 0,
        "max_resource_distance_km": 20,
        
        # 搜救能力
        "has_trapped": event_analysis.get("assessment", {}).get("estimated_casualties", {}).get("trapped", 0) > 0,
        "has_search_rescue_capability": any(
            "rescue" in c.get("resource_type", "").lower() or "RESCUE" in str(c.get("capabilities", []))
            for c in resource_candidates
        ),
        
        # 环境条件
        "main_road_accessible": True,
        "is_night_operation": event_analysis.get("is_night_operation", False),
        "has_lighting": True,
    }
    
    return data


@track_node_time("score_soft_rules")
def score_soft_rules(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    软规则评分节点
    
    使用TOPSIS方法对可行方案进行综合评分排序
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含scheme_scores和recommended_scheme
    """
    logger.info("开始执行软规则评分节点")
    
    feasible_schemes = state.get("feasible_schemes", [])
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    if not feasible_schemes:
        logger.warning("无可行方案，跳过评分")
        return {
            "scheme_scores": [],
            "recommended_scheme": None,
            "trace": trace,
            "errors": errors,
        }
    
    # TOPSIS评分
    scheme_scores = _topsis_scoring(feasible_schemes)
    
    # 排序
    scheme_scores.sort(key=lambda s: s["total_score"], reverse=True)
    for idx, score in enumerate(scheme_scores):
        score["rank"] = idx + 1
    
    # 推荐得分最高的方案
    recommended = scheme_scores[0] if scheme_scores else None
    
    logger.info(f"软规则评分完成: 推荐方案{recommended['scheme_id'] if recommended else 'None'}")
    
    # 更新追踪信息
    trace["scoring_method"] = "TOPSIS"
    trace["top_scheme_score"] = recommended["total_score"] if recommended else 0
    trace.setdefault("nodes_executed", []).append("score_soft_rules")
    
    return {
        "scheme_scores": scheme_scores,
        "recommended_scheme": recommended,
        "trace": trace,
        "errors": errors,
    }


def _topsis_scoring(
    feasible_schemes: List[Dict[str, Any]],
) -> List[SchemeScoreState]:
    """
    TOPSIS多准则决策评分
    
    1. 标准化决策矩阵
    2. 加权标准化
    3. 确定正负理想解
    4. 计算到理想解的距离
    5. 计算相对接近度
    """
    if not feasible_schemes:
        return []
    
    # 提取目标值矩阵
    objectives_matrix = []
    for scheme in feasible_schemes:
        obj = scheme.get("objectives", {})
        row = [
            obj.get("response_time", 15),
            obj.get("coverage_rate", 0.9),
            obj.get("cost", 100000),
            obj.get("risk", 0.05),
        ]
        objectives_matrix.append(row)
    
    n_schemes = len(objectives_matrix)
    n_objectives = 4
    
    # 标准化（向量标准化）
    normalized = [[0.0] * n_objectives for _ in range(n_schemes)]
    
    for j in range(n_objectives):
        col_sum_sq = sum(objectives_matrix[i][j] ** 2 for i in range(n_schemes))
        col_norm = math.sqrt(col_sum_sq) if col_sum_sq > 0 else 1
        
        for i in range(n_schemes):
            normalized[i][j] = objectives_matrix[i][j] / col_norm
    
    # 加权
    weights = [
        SOFT_RULE_WEIGHTS["response_time"],
        SOFT_RULE_WEIGHTS["coverage_rate"],
        SOFT_RULE_WEIGHTS["cost"],
        SOFT_RULE_WEIGHTS["risk"],
    ]
    
    weighted = [[0.0] * n_objectives for _ in range(n_schemes)]
    for i in range(n_schemes):
        for j in range(n_objectives):
            weighted[i][j] = normalized[i][j] * weights[j]
    
    # 确定正负理想解
    # response_time, cost, risk: 越小越好（负向指标）
    # coverage_rate: 越大越好（正向指标）
    is_benefit = [False, True, False, False]  # [time, coverage, cost, risk]
    
    ideal_positive = []
    ideal_negative = []
    
    for j in range(n_objectives):
        col = [weighted[i][j] for i in range(n_schemes)]
        if is_benefit[j]:
            ideal_positive.append(max(col))
            ideal_negative.append(min(col))
        else:
            ideal_positive.append(min(col))
            ideal_negative.append(max(col))
    
    # 计算到理想解的距离
    dist_positive = []
    dist_negative = []
    
    for i in range(n_schemes):
        dp = math.sqrt(sum((weighted[i][j] - ideal_positive[j]) ** 2 for j in range(n_objectives)))
        dn = math.sqrt(sum((weighted[i][j] - ideal_negative[j]) ** 2 for j in range(n_objectives)))
        dist_positive.append(dp)
        dist_negative.append(dn)
    
    # 计算相对接近度（TOPSIS得分）
    scores: List[SchemeScoreState] = []
    
    for i, scheme in enumerate(feasible_schemes):
        dp = dist_positive[i]
        dn = dist_negative[i]
        
        closeness = dn / (dp + dn) if (dp + dn) > 0 else 0.5
        
        score: SchemeScoreState = {
            "scheme_id": scheme.get("solution_id", f"scheme-{i}"),
            "total_score": round(closeness * 100, 2),
            "dimension_scores": {
                "response_time": round((1 - normalized[i][0]) * 100, 2),
                "coverage_rate": round(normalized[i][1] * 100, 2),
                "cost": round((1 - normalized[i][2]) * 100, 2),
                "risk": round((1 - normalized[i][3]) * 100, 2),
            },
            "rank": 0,  # 后续排序时设置
        }
        scores.append(score)
    
    return scores
