"""
阶段4: 方案优化节点

硬规则过滤、软规则评分、LLM方案解释。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import EmergencyAIState, SchemeScore, AllocationSolution
from ..tools.llm_tools import explain_scheme_async

logger = logging.getLogger(__name__)


# ============================================================================
# 硬规则定义
# ============================================================================

HARD_RULES = [
    {
        "rule_id": "HR-EM-001",
        "name": "救援人员安全红线",
        "check": lambda scheme: scheme.get("risk_level", 0) <= 0.15,
        "message": "救援人员伤亡风险超过15%，方案否决",
    },
    {
        "rule_id": "HR-EM-002",
        "name": "黄金救援时间",
        "check": lambda scheme: scheme.get("response_time_min", 0) <= 60,  # 1小时内响应
        "message": "预计响应时间超过黄金救援时间",
    },
    {
        "rule_id": "HR-EM-003",
        "name": "关键能力覆盖",
        "check": lambda scheme: scheme.get("coverage_rate", 0) >= 0.8,  # 至少80%覆盖
        "message": "关键能力覆盖率不足80%",
    },
]


# ============================================================================
# 5维评估权重配置（严格对齐军事版）
# ============================================================================

DEFAULT_WEIGHTS = {
    "success_rate": 0.35,     # 人命关天，最高权重
    "response_time": 0.30,    # 黄金救援期72小时
    "coverage_rate": 0.20,    # 全区域覆盖
    "risk": 0.05,             # 生命优先于风险规避
    "redundancy": 0.10,       # 备用资源保障
}

EARTHQUAKE_WEIGHTS = {
    "success_rate": 0.35,     # 地震救援成功率最优先
    "response_time": 0.35,    # 黄金72小时
    "coverage_rate": 0.15,    # 覆盖率
    "risk": 0.05,             # 风险
    "redundancy": 0.10,       # 冗余保障
}

FIRE_WEIGHTS = {
    "success_rate": 0.30,
    "response_time": 0.40,    # 火灾响应时间更关键
    "coverage_rate": 0.15,
    "risk": 0.05,
    "redundancy": 0.10,
}


async def filter_hard_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    硬规则过滤节点：一票否决不符合安全要求的方案
    
    对所有候选方案应用硬规则检查，过滤掉不满足
    基本安全要求的方案。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行硬规则过滤节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取候选方案
    solutions = state.get("allocation_solutions", [])
    
    if not solutions:
        logger.warning("无候选方案，跳过硬规则过滤")
        return {"scheme_scores": []}
    
    # 应用硬规则
    scheme_scores: List[SchemeScore] = []
    passed_count = 0
    
    for solution in solutions:
        violations = []
        
        for rule in HARD_RULES:
            try:
                if not rule["check"](solution):
                    violations.append(f"{rule['rule_id']}: {rule['message']}")
            except Exception as e:
                logger.warning(f"硬规则检查异常: {rule['rule_id']}", extra={"error": str(e)})
        
        score: SchemeScore = {
            "scheme_id": solution["solution_id"],
            "hard_rule_passed": len(violations) == 0,
            "hard_rule_violations": violations,
            "soft_rule_scores": {},
            "weighted_score": 0.0,
            "rank": 0,
        }
        scheme_scores.append(score)
        
        if len(violations) == 0:
            passed_count += 1
        else:
            logger.info(
                "方案被硬规则否决",
                extra={"scheme_id": solution["solution_id"], "violations": violations}
            )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["filter_hard_rules"]
    trace["hard_rules_checked"] = len(HARD_RULES)
    trace["schemes_passed"] = passed_count
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "硬规则过滤完成",
        extra={
            "total_schemes": len(solutions),
            "passed_count": passed_count,
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "scheme_scores": scheme_scores,
        "trace": trace,
        "current_phase": "optimization",
    }


async def score_soft_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    软规则评分节点：对通过硬规则的方案进行加权评分
    
    使用多维度软规则对方案进行综合评分，
    确定推荐方案。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行软规则评分节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取方案评分和原始方案
    scheme_scores = state.get("scheme_scores", [])
    solutions = state.get("allocation_solutions", [])
    parsed_disaster = state.get("parsed_disaster", {})
    capability_requirements = state.get("capability_requirements", [])
    
    # 获取权重配置
    weights = state.get("optimization_weights", {})
    if not weights:
        # 根据灾害类型选择权重
        disaster_type = parsed_disaster.get("disaster_type", "earthquake").lower()
        if disaster_type == "earthquake":
            weights = EARTHQUAKE_WEIGHTS
        elif disaster_type == "fire":
            weights = FIRE_WEIGHTS
        else:
            weights = DEFAULT_WEIGHTS
    
    # 获取相似案例用于计算成功率
    similar_cases = state.get("similar_cases", [])
    
    # 创建方案ID到方案的映射
    solution_map = {s["solution_id"]: s for s in solutions}
    
    # 计算软规则评分
    for score in scheme_scores:
        if not score["hard_rule_passed"]:
            # 未通过硬规则的方案不参与软规则评分
            score["weighted_score"] = 0.0
            continue
        
        solution = solution_map.get(score["scheme_id"])
        if not solution:
            continue
        
        # 计算5维评估得分（归一化到0-1）
        
        # 1. 成功率：基于历史案例相似度和能力匹配度（权重0.35）
        success_rate_score = _calculate_success_rate(solution, similar_cases)
        
        # 2. 响应时间：越短越好（权重0.30）
        response_time = solution.get("response_time_min", 60)
        time_score = max(0, 1 - response_time / 120)  # 120分钟为基准
        
        # 3. 覆盖率：越高越好（权重0.20）
        coverage_score = solution.get("coverage_rate", 0)
        
        # 4. 风险：越低越好（权重0.05）
        risk_score = 1 - solution.get("risk_level", 0)
        
        # 5. 冗余性：备用资源覆盖率（权重0.10）
        redundancy_score = _calculate_redundancy_rate(solution, capability_requirements)
        
        # 保存5维评估得分
        score["soft_rule_scores"] = {
            "success_rate": round(success_rate_score, 3),
            "response_time": round(time_score, 3),
            "coverage_rate": round(coverage_score, 3),
            "risk": round(risk_score, 3),
            "redundancy": round(redundancy_score, 3),
        }
        
        # 5维加权计算总分（严格对齐军事版）
        weighted_score = (
            success_rate_score * weights.get("success_rate", 0.35) +
            time_score * weights.get("response_time", 0.30) +
            coverage_score * weights.get("coverage_rate", 0.20) +
            risk_score * weights.get("risk", 0.05) +
            redundancy_score * weights.get("redundancy", 0.10)
        )
        score["weighted_score"] = round(weighted_score, 3)
    
    # 排名
    passed_scores = [s for s in scheme_scores if s["hard_rule_passed"]]
    passed_scores.sort(key=lambda x: x["weighted_score"], reverse=True)
    for i, score in enumerate(passed_scores):
        score["rank"] = i + 1
    
    # 确定推荐方案
    recommended_scheme: AllocationSolution | None = None
    if passed_scores:
        best_score = passed_scores[0]
        recommended_scheme = solution_map.get(best_score["scheme_id"])
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["score_soft_rules"]
    trace["soft_rules_weights"] = weights
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "软规则评分完成",
        extra={
            "scored_count": len(passed_scores),
            "best_score": passed_scores[0]["weighted_score"] if passed_scores else 0,
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "scheme_scores": scheme_scores,
        "recommended_scheme": recommended_scheme,
        "trace": trace,
    }


async def explain_scheme(state: EmergencyAIState) -> Dict[str, Any]:
    """
    方案解释节点：使用LLM生成方案解释
    
    为推荐方案生成自然语言解释，包括选择理由、
    优势、风险和执行建议。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行方案解释节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取推荐方案
    recommended_scheme = state.get("recommended_scheme")
    parsed_disaster = state.get("parsed_disaster", {})
    pareto_solutions = state.get("pareto_solutions", [])
    
    if not recommended_scheme:
        logger.warning("无推荐方案，跳过解释生成")
        return {"scheme_explanation": "无可用方案"}
    
    # 调用LLM生成解释
    try:
        explanation_result = await explain_scheme_async(
            scheme=recommended_scheme,
            disaster_info=parsed_disaster,
            alternatives=pareto_solutions[:3] if pareto_solutions else None,
        )
        
        # 构建解释文本
        explanation_parts = [
            f"## 方案摘要\n{explanation_result.get('summary', '')}",
            f"\n## 选择理由\n{explanation_result.get('selection_reason', '')}",
        ]
        
        advantages = explanation_result.get("key_advantages", [])
        if advantages:
            explanation_parts.append(f"\n## 关键优势\n" + "\n".join(f"- {a}" for a in advantages))
        
        risks = explanation_result.get("potential_risks", [])
        mitigations = explanation_result.get("mitigation_measures", [])
        if risks:
            explanation_parts.append(f"\n## 潜在风险\n" + "\n".join(f"- {r}" for r in risks))
        if mitigations:
            explanation_parts.append(f"\n## 风险缓解\n" + "\n".join(f"- {m}" for m in mitigations))
        
        suggestions = explanation_result.get("execution_suggestions", [])
        if suggestions:
            explanation_parts.append(f"\n## 执行建议\n" + "\n".join(f"- {s}" for s in suggestions))
        
        scheme_explanation = "\n".join(explanation_parts)
        
        # 更新追踪信息
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["explain_scheme"]
        trace["llm_calls"] = trace.get("llm_calls", 0) + 1
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info("方案解释生成完成", extra={"elapsed_ms": elapsed_ms})
        
        return {
            "scheme_explanation": scheme_explanation,
            "trace": trace,
        }
        
    except Exception as e:
        logger.warning("方案解释生成失败，使用简化解释", extra={"error": str(e)})
        
        # 简化解释
        simple_explanation = f"""## 方案摘要
推荐方案 {recommended_scheme.get('solution_id', '')}

## 方案指标
- 响应时间: {recommended_scheme.get('response_time_min', 0):.1f}分钟
- 能力覆盖: {recommended_scheme.get('coverage_rate', 0) * 100:.1f}%
- 风险等级: {recommended_scheme.get('risk_level', 0) * 100:.1f}%

## 资源分配
""" + "\n".join(
            f"- {a.get('resource_name', '')}: {', '.join(a.get('assigned_capabilities', []))}"
            for a in recommended_scheme.get("allocations", [])
        )
        
        return {"scheme_explanation": simple_explanation}


# ============================================================================
# 5维评估辅助函数
# ============================================================================

def _calculate_success_rate(
    solution: AllocationSolution,
    similar_cases: List[Dict[str, Any]],
) -> float:
    """
    计算方案成功率
    
    基于历史案例相似度和资源能力匹配度计算预期成功率。
    
    成功率 = 0.6 × 历史案例成功率 + 0.4 × 能力匹配度
    
    Args:
        solution: 分配方案
        similar_cases: 相似历史案例
        
    Returns:
        成功率评分（0-1）
    """
    logger.info(f"[5维评估-成功率] 开始计算")
    
    # 历史案例成功率（如果有相似案例）
    case_success_rate = 0.8  # 默认基准成功率
    if similar_cases:
        logger.info(f"  - 相似案例数: {len(similar_cases)}")
        total_similarity = 0.0
        weighted_success = 0.0
        for i, case in enumerate(similar_cases[:3]):  # 取前3个最相似案例
            similarity = case.get("similarity_score", 0.5)
            # 假设历史案例都是成功的（可以从lessons_learned判断）
            success = 0.9 if case.get("lessons_learned") else 0.7
            weighted_success += similarity * success
            total_similarity += similarity
            logger.info(f"  - 案例{i+1}: 相似度={similarity:.3f}, 成功率={success}")
        if total_similarity > 0:
            case_success_rate = weighted_success / total_similarity
        logger.info(f"  - 案例加权成功率: {case_success_rate:.3f}")
    else:
        logger.info(f"  - 无相似案例，使用默认成功率: {case_success_rate}")
    
    # 能力匹配度（基于分配方案的覆盖率和匹配分数）
    coverage_rate = solution.get("coverage_rate", 0.8)
    avg_match_score = solution.get("total_score", 0.7)
    capability_match = (coverage_rate + avg_match_score) / 2
    logger.info(f"  - 覆盖率: {coverage_rate:.3f}, 匹配分: {avg_match_score:.3f}")
    logger.info(f"  - 能力匹配度: {capability_match:.3f}")
    
    # 综合成功率
    success_rate = 0.6 * case_success_rate + 0.4 * capability_match
    success_rate = min(1.0, max(0.0, success_rate))
    logger.info(f"  - 最终成功率: 0.6×{case_success_rate:.3f} + 0.4×{capability_match:.3f} = {success_rate:.3f}")
    
    return success_rate


def _calculate_redundancy_rate(
    solution: AllocationSolution,
    capability_requirements: List[Dict[str, Any]],
) -> float:
    """
    计算冗余性评分
    
    检查每个关键能力是否有备用资源覆盖。
    
    冗余率 = 有备用覆盖的能力数 / 总能力需求数
    
    Args:
        solution: 分配方案
        capability_requirements: 能力需求列表
        
    Returns:
        冗余性评分（0-1）
    """
    logger.info(f"[5维评估-冗余性] 开始计算")
    
    if not capability_requirements:
        logger.info(f"  - 无能力需求，返回1.0")
        return 1.0  # 无需求时认为完全冗余
    
    allocations = solution.get("allocations", [])
    if not allocations:
        logger.info(f"  - 无分配方案，返回0.0")
        return 0.0
    
    # 统计每个能力被多少资源覆盖
    capability_coverage: Dict[str, int] = {}
    for alloc in allocations:
        for cap in alloc.get("assigned_capabilities", []):
            capability_coverage[cap] = capability_coverage.get(cap, 0) + 1
    
    logger.info(f"  - 能力覆盖统计:")
    for cap, count in capability_coverage.items():
        logger.info(f"    {cap}: 被{count}个资源覆盖")
    
    # 计算有冗余（>=2个资源覆盖）的能力比例
    required_caps = {req["capability_code"] for req in capability_requirements}
    redundant_count = 0
    
    for cap in required_caps:
        if capability_coverage.get(cap, 0) >= 2:
            redundant_count += 1
    
    redundancy_rate = redundant_count / len(required_caps) if required_caps else 1.0
    logger.info(f"  - 有冗余的能力: {redundant_count}/{len(required_caps)} = {redundancy_rate:.3f}")
    
    # 考虑队伍数量的冗余（更多队伍意味着更高冗余）
    teams_count = solution.get("teams_count", len(allocations))
    min_teams = len(required_caps)  # 最少需要的队伍数
    team_redundancy = min(1.0, teams_count / (min_teams * 1.5)) if min_teams > 0 else 1.0
    logger.info(f"  - 队伍冗余: {teams_count}队/{min_teams*1.5:.1f}最小需求 = {team_redundancy:.3f}")
    
    # 综合冗余性
    final_redundancy = (redundancy_rate + team_redundancy) / 2
    logger.info(f"  - 最终冗余性: ({redundancy_rate:.3f} + {team_redundancy:.3f})/2 = {final_redundancy:.3f}")
    
    return final_redundancy
