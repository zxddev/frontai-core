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
        
        # 阶段3: 资源匹配
        "matching": {
            "candidates_count": len(state.get("resource_candidates", [])),
            "solutions_count": len(state.get("allocation_solutions", [])),
            "pareto_solutions_count": len(state.get("pareto_solutions", [])),
        },
        
        # 阶段4: 方案优化
        "optimization": {
            "scheme_scores": [
                {
                    "scheme_id": s.get("scheme_id"),
                    "passed": s.get("hard_rule_passed"),
                    "violations": s.get("hard_rule_violations", []),
                    "weighted_score": s.get("weighted_score"),
                    "rank": s.get("rank"),
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
