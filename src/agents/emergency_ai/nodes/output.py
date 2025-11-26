"""
输出节点

生成最终输出结果。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any
from datetime import datetime

from ..state import EmergencyAIState

logger = logging.getLogger(__name__)


async def generate_output(state: EmergencyAIState) -> Dict[str, Any]:
    """
    输出生成节点：构建最终输出结果
    
    整合所有阶段的结果，生成结构化的最终输出。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info("执行输出生成节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 判断是否成功
    errors = state.get("errors", [])
    recommended_scheme = state.get("recommended_scheme")
    
    success = len(errors) == 0 and recommended_scheme is not None
    
    # 构建输出
    final_output: Dict[str, Any] = {
        "success": success,
        "event_id": state["event_id"],
        "scenario_id": state["scenario_id"],
        "status": "completed" if success else "failed",
        "completed_at": datetime.utcnow().isoformat() + "Z",
        
        # 阶段1: 灾情理解
        "understanding": {
            "parsed_disaster": state.get("parsed_disaster"),
            "similar_cases_count": len(state.get("similar_cases", [])),
            "summary": state.get("understanding_summary", ""),
        },
        
        # 阶段2: 规则推理
        "reasoning": {
            "matched_rules": [
                {
                    "rule_id": r.get("rule_id"),
                    "rule_name": r.get("rule_name"),
                    "priority": r.get("priority"),
                    "match_reason": r.get("match_reason"),
                }
                for r in state.get("matched_rules", [])
            ],
            "task_requirements": state.get("task_requirements", []),
            "capability_requirements": [
                {
                    "code": c.get("capability_code"),
                    "name": c.get("capability_name"),
                    "provided_by": c.get("provided_by", []),
                }
                for c in state.get("capability_requirements", [])
            ],
        },
        
        # 阶段2.5: HTN任务分解
        "htn_decomposition": {
            "scene_codes": state.get("scene_codes", []),
            "task_sequence": [
                {
                    "task_id": t.get("task_id"),
                    "task_name": t.get("task_name"),
                    "sequence": t.get("sequence"),
                    "depends_on": t.get("depends_on", []),
                    "golden_hour": t.get("golden_hour"),
                    "phase": t.get("phase"),
                    "is_parallel": t.get("is_parallel"),
                    "parallel_group_id": t.get("parallel_group_id"),
                }
                for t in state.get("task_sequence", [])
            ],
            "parallel_tasks": [
                {
                    "group_id": g.get("group_id"),
                    "task_ids": g.get("task_ids", []),
                    "reason": g.get("reason"),
                }
                for g in state.get("parallel_tasks", [])
            ],
        },
        
        # 阶段3: 资源匹配（详细信息）
        "matching": {
            "candidates_count": len(state.get("resource_candidates", [])),
            "solutions_count": len(state.get("allocation_solutions", [])),
            "pareto_solutions_count": len(state.get("pareto_solutions", [])),
            # 详细的候选资源列表
            "candidates_detail": [
                {
                    "resource_id": c.get("resource_id"),
                    "resource_name": c.get("resource_name"),
                    "resource_type": c.get("resource_type"),
                    "capabilities": c.get("capabilities", []),
                    "distance_km": round(c.get("distance_km", 0), 1),
                    "eta_minutes": round(c.get("eta_minutes", 0)),
                    "match_score": round(c.get("match_score", 0), 3),
                    "rescue_capacity": c.get("rescue_capacity", 0),  # 救援容量
                }
                for c in state.get("resource_candidates", [])[:20]  # 最多显示20个
            ],
        },
        
        # 阶段4: 方案优化（5维评估）
        "optimization": {
            "scheme_scores": [
                {
                    "scheme_id": s.get("scheme_id"),
                    "passed": s.get("hard_rule_passed"),
                    "violations": s.get("hard_rule_violations", []),
                    "total_score": s.get("weighted_score"),
                    "rank": s.get("rank"),
                    "dimension_scores": s.get("soft_rule_scores", {}),
                }
                for s in state.get("scheme_scores", [])
            ],
        },
        
        # 推荐方案
        "recommended_scheme": recommended_scheme,
        
        # 方案解释
        "scheme_explanation": state.get("scheme_explanation", ""),
        
        # 追踪信息
        "trace": state.get("trace", {}),
        
        # 错误信息
        "errors": errors,
    }
    
    # 计算总执行时间
    trace = state.get("trace", {})
    elapsed_ms = int((time.time() - start_time) * 1000)
    total_time = state.get("execution_time_ms", 0) + elapsed_ms
    
    final_output["execution_time_ms"] = total_time
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_output"]
    
    logger.info(
        "输出生成完成",
        extra={
            "success": success,
            "total_time_ms": total_time,
            "phases_count": len(trace.get("phases_executed", [])),
        }
    )
    
    return {
        "final_output": final_output,
        "trace": trace,
        "current_phase": "completed",
        "execution_time_ms": total_time,
    }
