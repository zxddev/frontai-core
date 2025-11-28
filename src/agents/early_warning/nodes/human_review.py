"""
人工审核门控节点

对红色风险预测实施Human-in-the-Loop审核机制。
使用LangGraph的interrupt_before实现。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any

from ..state import EarlyWarningState

logger = logging.getLogger(__name__)


async def human_review_gate(state: EarlyWarningState) -> Dict[str, Any]:
    """
    人工审核门控节点
    
    检查是否有需要人工审核的红色风险预测。
    如果有，此节点会被interrupt_before拦截，等待人工确认。
    
    输入：
        - pending_human_review: 待审核的预测ID列表
        - risk_predictions: 风险预测列表
        
    输出：
        - pending_human_review: 清空已审核的预测
        - current_phase: 审核状态
    """
    logger.info(f"[人工审核] 开始 request_id={state['request_id']}")
    
    pending_reviews = state.get("pending_human_review", [])
    
    if not pending_reviews:
        logger.info("[人工审核] 无需人工审核的预测")
        return {
            "current_phase": "human_review_not_required",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["human_review_skipped"],
            },
        }
    
    # 记录待审核的预测
    predictions = state.get("risk_predictions", [])
    pending_predictions = [
        p for p in predictions 
        if p.get("prediction_id") in pending_reviews
    ]
    
    logger.warning(
        f"[人工审核] 有 {len(pending_reviews)} 个红色风险预测需要人工确认！"
    )
    
    for pred in pending_predictions:
        logger.warning(
            f"  - 预测ID: {pred.get('prediction_id')}"
            f"  类型: {pred.get('prediction_type')}"
            f"  风险等级: {pred.get('risk_level')}"
            f"  目标: {pred.get('target_name')}"
        )
    
    return {
        "current_phase": "awaiting_human_review",
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["human_review_gate"],
            "human_review_required": True,
            "pending_review_count": len(pending_reviews),
            "pending_review_ids": pending_reviews,
        },
    }


def approve_prediction(
    state: EarlyWarningState,
    prediction_id: str,
    reviewer_id: str,
    notes: str = "",
) -> Dict[str, Any]:
    """
    批准预测（人工审核通过）
    
    Args:
        state: 当前状态
        prediction_id: 预测ID
        reviewer_id: 审核人ID
        notes: 审核备注
        
    Returns:
        状态更新
    """
    logger.info(f"[人工审核] 批准预测 prediction_id={prediction_id} reviewer={reviewer_id}")
    
    pending = state.get("pending_human_review", [])
    predictions = state.get("risk_predictions", [])
    
    # 更新预测记录
    updated_predictions = []
    for pred in predictions:
        if pred.get("prediction_id") == prediction_id:
            pred = {
                **pred,
                "review_decision": "approved",
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "review_notes": notes,
            }
        updated_predictions.append(pred)
    
    # 从待审核列表移除
    new_pending = [p for p in pending if p != prediction_id]
    
    return {
        "risk_predictions": updated_predictions,
        "pending_human_review": new_pending,
        "trace": {
            **state.get("trace", {}),
            "human_review_actions": state.get("trace", {}).get("human_review_actions", []) + [
                {
                    "action": "approved",
                    "prediction_id": prediction_id,
                    "reviewer_id": reviewer_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        },
    }


def reject_prediction(
    state: EarlyWarningState,
    prediction_id: str,
    reviewer_id: str,
    reason: str,
) -> Dict[str, Any]:
    """
    拒绝预测（人工审核不通过）
    
    Args:
        state: 当前状态
        prediction_id: 预测ID
        reviewer_id: 审核人ID
        reason: 拒绝原因
        
    Returns:
        状态更新
    """
    logger.info(f"[人工审核] 拒绝预测 prediction_id={prediction_id} reviewer={reviewer_id}")
    
    pending = state.get("pending_human_review", [])
    predictions = state.get("risk_predictions", [])
    
    # 更新预测记录
    updated_predictions = []
    for pred in predictions:
        if pred.get("prediction_id") == prediction_id:
            pred = {
                **pred,
                "review_decision": "rejected",
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "review_notes": reason,
                "risk_level": "blue",
            }
        updated_predictions.append(pred)
    
    new_pending = [p for p in pending if p != prediction_id]
    
    return {
        "risk_predictions": updated_predictions,
        "pending_human_review": new_pending,
        "trace": {
            **state.get("trace", {}),
            "human_review_actions": state.get("trace", {}).get("human_review_actions", []) + [
                {
                    "action": "rejected",
                    "prediction_id": prediction_id,
                    "reviewer_id": reviewer_id,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        },
    }


def modify_prediction(
    state: EarlyWarningState,
    prediction_id: str,
    reviewer_id: str,
    new_risk_level: str,
    notes: str,
) -> Dict[str, Any]:
    """
    修改预测（人工调整风险等级）
    
    Args:
        state: 当前状态
        prediction_id: 预测ID
        reviewer_id: 审核人ID
        new_risk_level: 修改后的风险等级
        notes: 修改说明
        
    Returns:
        状态更新
    """
    logger.info(
        f"[人工审核] 修改预测 prediction_id={prediction_id} "
        f"new_level={new_risk_level} reviewer={reviewer_id}"
    )
    
    pending = state.get("pending_human_review", [])
    predictions = state.get("risk_predictions", [])
    
    updated_predictions = []
    for pred in predictions:
        if pred.get("prediction_id") == prediction_id:
            original_level = pred.get("risk_level")
            pred = {
                **pred,
                "risk_level": new_risk_level,
                "review_decision": "modified",
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.utcnow().isoformat(),
                "review_notes": f"原等级{original_level}→{new_risk_level}。{notes}",
                "requires_human_review": False,
            }
        updated_predictions.append(pred)
    
    new_pending = [p for p in pending if p != prediction_id]
    
    return {
        "risk_predictions": updated_predictions,
        "pending_human_review": new_pending,
        "trace": {
            **state.get("trace", {}),
            "human_review_actions": state.get("trace", {}).get("human_review_actions", []) + [
                {
                    "action": "modified",
                    "prediction_id": prediction_id,
                    "reviewer_id": reviewer_id,
                    "new_risk_level": new_risk_level,
                    "notes": notes,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        },
    }
