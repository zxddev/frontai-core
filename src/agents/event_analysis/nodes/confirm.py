"""
确认评分和状态决策节点

调用ConfirmationScorer算法计算确认评分并决定事件状态
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.planning.algorithms import ConfirmationScorer, AlgorithmStatus
from ..state import EventAnalysisState, ConfirmationDecision

logger = logging.getLogger(__name__)

# 推荐行动模板
RECOMMENDED_ACTIONS: Dict[str, List[str]] = {
    "I": [
        "立即启动I级(特别重大)应急响应",
        "请求国家级救援力量支援",
        "启动跨区域协调机制",
        "建立现场指挥部",
    ],
    "II": [
        "立即启动II级(重大)应急响应",
        "请求省级救援力量支援",
        "派遣专业救援队",
        "开展人员疏散",
    ],
    "III": [
        "立即启动III级(较大)应急响应",
        "派遣市级救援队伍",
        "启动现场救援",
        "做好物资调配",
    ],
    "IV": [
        "启动IV级(一般)应急响应",
        "派遣县级救援力量",
        "开展灾情核查",
        "做好后勤保障",
    ],
}

# 灾害类型专用行动
DISASTER_SPECIFIC_ACTIONS: Dict[str, List[str]] = {
    "earthquake": ["派遣USAR地震搜救队", "部署生命探测仪", "准备破拆设备"],
    "flood": ["准备冲锋舟和救生设备", "疏散低洼地区群众", "加强堤坝巡查"],
    "hazmat": ["划定警戒区域", "准备防化装备", "疏散下风向群众"],
    "fire": ["派遣消防救援队", "准备高压水枪", "疏散周边群众"],
    "landslide": ["暂停区域通行", "部署无人机勘察", "安排地质专家"],
}


def calculate_confirmation(state: EventAnalysisState) -> Dict[str, Any]:
    """
    确认评分节点
    
    调用ConfirmationScorer算法计算确认评分
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    task_id = state.get("task_id", "unknown")
    
    logger.info("开始确认评分计算", extra={"task_id": task_id})
    
    trace = state.get("trace", {})
    trace.setdefault("algorithms_used", []).append("ConfirmationScorer")
    trace.setdefault("nodes_executed", []).append("calculate_confirmation")
    
    errors = list(state.get("errors", []))
    
    # 获取AI置信度（来自灾情评估）
    ai_confidence = state.get("ai_confidence", 0.5)
    
    # 构造评分输入
    problem = {
        "ai_confidence": ai_confidence,
        "source_trust_level": state.get("source_trust_level", 0.5),
        "source_system": state.get("source_system", "unknown"),
        "source_type": state.get("source_type", "manual_report"),
        "is_urgent": state.get("is_urgent", False),
        "estimated_victims": state.get("estimated_victims", 0),
        "priority": state.get("priority", "medium"),
        "event_location": state.get("location"),
        "reported_at": state.get("started_at", datetime.utcnow()).isoformat(),
        "nearby_events": state.get("nearby_events", []),
    }
    
    # 调用算法
    scorer = ConfirmationScorer()
    result = scorer.run(problem)
    
    if result.status != AlgorithmStatus.SUCCESS:
        error_msg = f"确认评分计算失败: {result.message}"
        logger.error(error_msg, extra={"task_id": task_id})
        errors.append(error_msg)
        
        # 失败时使用默认决策
        default_decision: ConfirmationDecision = {
            "confirmation_score": 0.0,
            "score_breakdown": {},
            "matched_auto_confirm_rules": [],
            "recommended_status": "pending",
            "auto_confirmed": False,
            "rationale": f"评分计算失败: {result.message}，默认待人工确认",
        }
        
        return {
            "confirmation_decision": default_decision,
            "trace": trace,
            "errors": errors,
        }
    
    # 解析评分结果
    solution = result.solution
    
    confirmation_decision: ConfirmationDecision = {
        "confirmation_score": solution.confirmation_score,
        "score_breakdown": solution.score_breakdown,
        "matched_auto_confirm_rules": solution.matched_rules,
        "recommended_status": solution.recommended_status,
        "auto_confirmed": solution.auto_confirmed,
        "rationale": solution.rationale,
    }
    
    logger.info(
        "确认评分计算完成",
        extra={
            "task_id": task_id,
            "confirmation_score": solution.confirmation_score,
            "matched_rules": solution.matched_rules,
            "recommended_status": solution.recommended_status,
            "auto_confirmed": solution.auto_confirmed,
        },
    )
    
    return {
        "confirmation_decision": confirmation_decision,
        "trace": trace,
        "errors": errors,
    }


def decide_status(state: EventAnalysisState) -> Dict[str, Any]:
    """
    状态决策节点
    
    基于确认评分决定事件状态，生成推荐行动
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    task_id = state.get("task_id", "unknown")
    disaster_type = state.get("disaster_type", "earthquake")
    
    logger.info("开始状态决策", extra={"task_id": task_id})
    
    trace = state.get("trace", {})
    trace.setdefault("nodes_executed", []).append("decide_status")
    
    # 获取评估和确认决策
    assessment = state.get("assessment_result", {})
    confirmation = state.get("confirmation_decision", {})
    
    # 确定灾情等级
    disaster_level = assessment.get("disaster_level", "III")
    
    # 生成推荐行动
    recommended_actions: List[str] = []
    
    # 添加等级对应的通用行动
    level_actions = RECOMMENDED_ACTIONS.get(disaster_level, RECOMMENDED_ACTIONS["III"])
    recommended_actions.extend(level_actions)
    
    # 添加灾害类型专用行动
    disaster_actions = DISASTER_SPECIFIC_ACTIONS.get(disaster_type, [])
    recommended_actions.extend(disaster_actions)
    
    # 计算紧急度评分（基于灾情等级和被困人数）
    urgency_base = {"I": 1.0, "II": 0.8, "III": 0.6, "IV": 0.4}.get(disaster_level, 0.5)
    victims = state.get("estimated_victims", 0)
    victim_factor = min(1.0, victims / 50)  # 50人以上满分
    urgency_score = urgency_base * 0.7 + victim_factor * 0.3
    
    # 记录执行时间
    trace["execution_time_ms"] = 0  # 由Agent层计算
    trace["model_version"] = "v2.0"
    
    logger.info(
        "状态决策完成",
        extra={
            "task_id": task_id,
            "recommended_status": confirmation.get("recommended_status", "pending"),
            "urgency_score": urgency_score,
            "action_count": len(recommended_actions),
        },
    )
    
    return {
        "recommended_actions": recommended_actions,
        "urgency_score": round(urgency_score, 2),
        "trace": trace,
    }
