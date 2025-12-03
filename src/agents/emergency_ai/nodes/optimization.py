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


# 硬规则和权重配置已迁移到数据库，通过ConfigService访问


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
    from src.agents.services.config_service import ConfigService
    
    logger.info("执行硬规则过滤节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取候选方案
    solutions = state.get("allocation_solutions", [])
    
    if not solutions:
        logger.warning("无候选方案，跳过硬规则过滤")
        return {"scheme_scores": []}
    
    # 从数据库获取硬规则配置
    hard_rules = await ConfigService.get_hard_rules()
    
    # 应用硬规则
    scheme_scores: List[SchemeScore] = []
    passed_count = 0
    
    for solution in solutions:
        violations = []
        
        for rule in hard_rules:
            try:
                if not rule.check(solution):
                    violations.append(f"{rule.rule_id}: {rule.message}")
            except Exception as e:
                logger.warning(f"硬规则检查异常: {rule.rule_id}", extra={"error": str(e)})
        
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
    trace["hard_rules_checked"] = len(hard_rules)
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
    
    # 获取权重配置（从数据库）
    from src.agents.services.config_service import ConfigService
    
    weights = state.get("optimization_weights", {})
    if not weights:
        disaster_type = parsed_disaster.get("disaster_type", "earthquake").lower()
        weights_config = await ConfigService.get_evaluation_weights(disaster_type)
        weights = weights_config.to_dict()
    
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
        
        # 打印5维评估详情
        logger.info(f"【5维评估】方案{score['scheme_id']}:")
        logger.info(f"  1. 成功率={success_rate_score:.3f} (权重0.35)")
        logger.info(f"  2. 响应时间={time_score:.3f} (原始={response_time:.0f}分钟, 权重0.30)")
        logger.info(f"  3. 覆盖率={coverage_score:.3f} (权重0.20)")
        logger.info(f"  4. 风险={risk_score:.3f} (权重0.05)")
        logger.info(f"  5. 冗余性={redundancy_score:.3f} (权重0.10)")
        logger.info(f"  → 加权总分={weighted_score:.3f}")
    
    # 排名
    passed_scores = [s for s in scheme_scores if s["hard_rule_passed"]]
    passed_scores.sort(key=lambda x: x["weighted_score"], reverse=True)
    for i, score in enumerate(passed_scores):
        score["rank"] = i + 1
    
    # 确定推荐方案
    recommended_scheme: AllocationSolution | None = None
    requires_reinforcement: bool = False
    reinforcement_message: str = ""
    
    if passed_scores:
        # 正常情况：选择得分最高的通过方案
        best_score = passed_scores[0]
        recommended_scheme = solution_map.get(best_score["scheme_id"])
    elif solutions:
        # 巨灾场景：所有方案都被硬规则否决，仍需输出最佳可用方案
        logger.warning("[巨灾模式] 所有方案被硬规则否决，启用紧急增援模式")
        requires_reinforcement = True
        
        # 【安全修复】尝试组合多个方案以提升覆盖率和容量
        best_solution = _try_combine_catastrophe_solutions(solutions, capability_requirements)
        recommended_scheme = best_solution
        
        # 为巨灾方案计算5维评分（即使硬规则未通过也需要评估）
        catastrophe_success_rate = _calculate_success_rate(best_solution, similar_cases)
        catastrophe_response_time = best_solution.get("response_time_min", 60)
        catastrophe_time_score = max(0, 1 - catastrophe_response_time / 120)
        catastrophe_coverage = best_solution.get("coverage_rate", 0)
        catastrophe_risk = 1 - best_solution.get("risk_level", 0)
        catastrophe_redundancy = _calculate_redundancy_rate(best_solution, capability_requirements)
        
        catastrophe_weighted = (
            catastrophe_success_rate * weights.get("success_rate", 0.35) +
            catastrophe_time_score * weights.get("response_time", 0.30) +
            catastrophe_coverage * weights.get("coverage_rate", 0.20) +
            catastrophe_risk * weights.get("risk", 0.05) +
            catastrophe_redundancy * weights.get("redundancy", 0.10)
        )
        
        # 更新该方案在scheme_scores中的评分
        for score in scheme_scores:
            if score["scheme_id"] == best_solution["solution_id"]:
                score["soft_rule_scores"] = {
                    "success_rate": round(catastrophe_success_rate, 3),
                    "response_time": round(catastrophe_time_score, 3),
                    "coverage_rate": round(catastrophe_coverage, 3),
                    "risk": round(catastrophe_risk, 3),
                    "redundancy": round(catastrophe_redundancy, 3),
                }
                score["weighted_score"] = round(catastrophe_weighted, 3)
                score["rank"] = 1  # 巨灾模式下为唯一推荐
                score["catastrophe_mode"] = True
                break
        
        logger.info(f"[巨灾模式] 方案5维评分: 综合={catastrophe_weighted:.3f}, 成功率={catastrophe_success_rate:.3f}")
        
        # 计算增援需求
        estimated_trapped = parsed_disaster.get("estimated_trapped", 0)
        current_capacity = best_solution.get("total_rescue_capacity", 0)
        capacity_gap = max(0, estimated_trapped - current_capacity)
        capacity_rate = current_capacity / estimated_trapped if estimated_trapped > 0 else 0
        
        # 生成增援建议
        if capacity_rate < 0.3:
            reinforcement_level = "国家级"
            reinforcement_message = (
                f"🚨🚨🚨 特大灾害！本地资源严重不足！\n"
                f"被困人数: {estimated_trapped}人\n"
                f"本地救援容量: {current_capacity}人（仅覆盖{capacity_rate*100:.1f}%）\n"
                f"容量缺口: {capacity_gap}人\n\n"
                f"⚡ 紧急建议:\n"
                f"1. 立即启动国家级应急响应\n"
                f"2. 请求国家救援队、武警部队增援\n"
                f"3. 协调周边省份救援力量跨区支援\n"
                f"4. 本方案仅为首批先遣力量，必须等待增援到位后扩大救援规模"
            )
        elif capacity_rate < 0.5:
            reinforcement_level = "省级"
            reinforcement_message = (
                f"🚨🚨 重大灾害！本地资源不足！\n"
                f"被困人数: {estimated_trapped}人\n"
                f"本地救援容量: {current_capacity}人（仅覆盖{capacity_rate*100:.1f}%）\n"
                f"容量缺口: {capacity_gap}人\n\n"
                f"⚡ 紧急建议:\n"
                f"1. 立即启动省级应急响应\n"
                f"2. 请求省级专业救援队增援\n"
                f"3. 协调相邻地市救援力量支援\n"
                f"4. 本方案为首批响应力量，需省级增援补充"
            )
        else:
            reinforcement_level = "市级"
            reinforcement_message = (
                f"⚠️ 灾害较重，建议申请增援\n"
                f"被困人数: {estimated_trapped}人\n"
                f"本地救援容量: {current_capacity}人（覆盖{capacity_rate*100:.1f}%）\n"
                f"容量缺口: {capacity_gap}人\n\n"
                f"建议: 向市级应急指挥部申请增援力量"
            )
        
        # 更新方案的容量警告
        if recommended_scheme:
            recommended_scheme["capacity_warning"] = reinforcement_message
            recommended_scheme["requires_reinforcement"] = True
            recommended_scheme["reinforcement_level"] = reinforcement_level
            recommended_scheme["capacity_gap"] = capacity_gap
        
        logger.warning(
            f"[巨灾模式] 需要{reinforcement_level}增援，容量缺口{capacity_gap}人",
            extra={"estimated_trapped": estimated_trapped, "current_capacity": current_capacity}
        )
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["score_soft_rules"]
    trace["soft_rules_weights"] = weights
    trace["requires_reinforcement"] = requires_reinforcement
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "软规则评分完成",
        extra={
            "scored_count": len(passed_scores),
            "best_score": passed_scores[0]["weighted_score"] if passed_scores else 0,
            "requires_reinforcement": requires_reinforcement,
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "scheme_scores": scheme_scores,
        "recommended_scheme": recommended_scheme,
        "requires_reinforcement": requires_reinforcement,
        "reinforcement_message": reinforcement_message,
        "trace": trace,
    }


async def explain_scheme(state: EmergencyAIState) -> Dict[str, Any]:
    """
    方案解释节点：使用LLM生成详细的方案解释
    
    为指挥员生成完整的救援方案说明，包括态势评估、
    资源部署、时间线、协调要点、风险缓解等。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行方案解释节点（详细版）", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取推荐方案和相关信息
    recommended_scheme = state.get("recommended_scheme")
    parsed_disaster = state.get("parsed_disaster", {})
    pareto_solutions = state.get("pareto_solutions", [])
    task_sequence = state.get("task_sequence", [])
    
    if not recommended_scheme:
        logger.warning("无推荐方案，跳过解释生成")
        return {"scheme_explanation": "无可用方案"}
    
    # 调用LLM生成详细解释
    try:
        explanation_result = await explain_scheme_async(
            scheme=recommended_scheme,
            disaster_info=parsed_disaster,
            alternatives=pareto_solutions[:3] if pareto_solutions else None,
            task_sequence=task_sequence,
        )
        
        # 构建完整的解释文本（Markdown格式）
        explanation_parts = [
            "# 救援方案详细说明",
            f"\n## 一、方案摘要\n{explanation_result.get('summary', '')}",
            f"\n## 二、态势评估\n{explanation_result.get('situation_assessment', '')}",
            f"\n## 三、方案选择理由\n{explanation_result.get('selection_reason', '')}",
        ]
        
        # 关键优势
        advantages = explanation_result.get("key_advantages", [])
        if advantages:
            explanation_parts.append("\n## 四、关键优势")
            for i, a in enumerate(advantages, 1):
                explanation_parts.append(f"{i}. {a}")
        
        # 资源部署
        deployments = explanation_result.get("resource_deployment", [])
        if deployments:
            explanation_parts.append("\n## 五、资源部署详情")
            for d in deployments:
                explanation_parts.append(f"- {d}")
        
        # 时间线
        timeline = explanation_result.get("timeline", [])
        if timeline:
            explanation_parts.append("\n## 六、行动时间线")
            for t in timeline:
                explanation_parts.append(f"- {t}")
        
        # 协调要点
        coordination = explanation_result.get("coordination_points", [])
        if coordination:
            explanation_parts.append("\n## 七、协调配合要点")
            for c in coordination:
                explanation_parts.append(f"- {c}")
        
        # 风险与缓解
        risks = explanation_result.get("potential_risks", [])
        mitigations = explanation_result.get("mitigation_measures", [])
        if risks:
            explanation_parts.append("\n## 八、潜在风险")
            for i, r in enumerate(risks, 1):
                explanation_parts.append(f"{i}. {r}")
        if mitigations:
            explanation_parts.append("\n## 九、风险缓解措施")
            for i, m in enumerate(mitigations, 1):
                explanation_parts.append(f"{i}. {m}")
        
        # 执行建议
        suggestions = explanation_result.get("execution_suggestions", [])
        if suggestions:
            explanation_parts.append("\n## 十、执行建议")
            for i, s in enumerate(suggestions, 1):
                explanation_parts.append(f"{i}. {s}")
        
        # 指挥员注意事项
        commander_notes = explanation_result.get("commander_notes", "")
        if commander_notes:
            explanation_parts.append(f"\n## 十一、指挥员特别注意事项\n{commander_notes}")
        
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
# 巨灾模式组合辅助函数
# ============================================================================

def _try_combine_catastrophe_solutions(
    solutions: List[AllocationSolution],
    capability_requirements: List[Dict[str, Any]],
) -> AllocationSolution:
    """
    【安全修复】巨灾模式下尝试组合多个方案
    
    在所有方案都被硬规则否决的情况下，尝试组合多个方案
    以提升能力覆盖率和总救援容量。
    
    组合策略：
    1. 首先选择容量最大的方案作为基础
    2. 然后按能力互补性添加其他方案的队伍
    3. 避免队伍重复
    
    Args:
        solutions: 所有候选方案
        capability_requirements: 能力需求列表
        
    Returns:
        组合后的最优方案
    """
    if not solutions:
        return None
    
    if len(solutions) == 1:
        return solutions[0]
    
    logger.info(f"[巨灾-组合] 尝试组合{len(solutions)}个方案")
    
    # 提取所有需求能力
    required_caps = {cap.get("capability_code") for cap in capability_requirements}
    
    # 选择容量最大的方案作为基础
    base_solution = max(solutions, key=lambda s: s.get("total_rescue_capacity", 0))
    
    # 收集基础方案的队伍ID和能力
    combined_allocations = list(base_solution.get("allocations", []))
    combined_team_ids = {a.get("resource_id") for a in combined_allocations}
    combined_caps = set()
    for alloc in combined_allocations:
        combined_caps.update(alloc.get("assigned_capabilities", []))
    
    total_capacity = base_solution.get("total_rescue_capacity", 0)
    max_eta = base_solution.get("response_time_min", 0)
    
    logger.info(f"[巨灾-组合] 基础方案: 容量={total_capacity}, 能力={combined_caps}")
    
    # 检查是否有缺失能力
    missing_caps = required_caps - combined_caps
    
    if missing_caps:
        logger.info(f"[巨灾-组合] 缺失能力: {missing_caps}，尝试从其他方案补充")
        
        # 从其他方案中找能提供缺失能力的队伍
        for solution in solutions:
            if solution.get("solution_id") == base_solution.get("solution_id"):
                continue
            
            for alloc in solution.get("allocations", []):
                team_id = alloc.get("resource_id")
                if team_id in combined_team_ids:
                    continue
                
                team_caps = set(alloc.get("assigned_capabilities", []))
                new_caps = team_caps.intersection(missing_caps)
                
                if new_caps:
                    # 这个队伍能提供缺失能力，加入组合
                    combined_allocations.append(alloc)
                    combined_team_ids.add(team_id)
                    combined_caps.update(team_caps)
                    total_capacity += alloc.get("rescue_capacity", 0)
                    max_eta = max(max_eta, alloc.get("eta_minutes", 0))
                    
                    logger.info(
                        f"[巨灾-组合] 添加队伍 {alloc.get('resource_name')}: "
                        f"补充能力={new_caps}, 新增容量={alloc.get('rescue_capacity', 0)}"
                    )
                    
                    missing_caps -= new_caps
                    
                    if not missing_caps:
                        break
            
            if not missing_caps:
                break
    
    # 构建组合方案
    combined_solution: AllocationSolution = {
        "solution_id": f"combined-{base_solution.get('solution_id', 'unknown')}",
        "allocations": combined_allocations,
        "total_score": base_solution.get("total_score", 0),
        "response_time_min": max_eta,
        "coverage_rate": len(combined_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0,
        "resource_scale": len(combined_allocations),
        "risk_level": base_solution.get("risk_level", 0),
        "total_rescue_capacity": total_capacity,
        "capacity_coverage_rate": base_solution.get("capacity_coverage_rate", 0),
        "capacity_warning": base_solution.get("capacity_warning"),
        "uncovered_capabilities": list(required_caps - combined_caps),
        "max_distance_km": max(a.get("distance_km", 0) for a in combined_allocations) if combined_allocations else 0,
        "teams_count": len(combined_allocations),
        "objectives": {
            "response_time": max_eta,
            "coverage_rate": len(combined_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0,
            "teams_count": len(combined_allocations),
        },
        "is_combined": True,  # 标记这是组合方案
    }
    
    logger.info(
        f"[巨灾-组合] 组合完成: 队伍数={len(combined_allocations)}, "
        f"总容量={total_capacity}, 覆盖能力={combined_caps}"
    )
    
    return combined_solution


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
