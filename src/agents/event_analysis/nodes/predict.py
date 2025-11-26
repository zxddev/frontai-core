"""
次生灾害预测节点

调用SecondaryHazardPredictor算法预测次生灾害风险
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.planning.algorithms import SecondaryHazardPredictor, AlgorithmStatus
from ..state import EventAnalysisState, SecondaryHazard

logger = logging.getLogger(__name__)


def predict_hazards(state: EventAnalysisState) -> Dict[str, Any]:
    """
    次生灾害预测节点
    
    基于灾情评估结果，预测可能发生的次生灾害（火灾、滑坡、余震等）
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    task_id = state.get("task_id", "unknown")
    disaster_type = state.get("disaster_type", "earthquake")
    assessment = state.get("assessment_result")
    
    logger.info(
        "开始次生灾害预测",
        extra={"task_id": task_id, "disaster_type": disaster_type},
    )
    
    trace = state.get("trace", {})
    trace.setdefault("algorithms_used", []).append("SecondaryHazardPredictor")
    trace.setdefault("nodes_executed", []).append("predict_hazards")
    
    errors = list(state.get("errors", []))
    
    # 无评估结果时跳过预测
    if not assessment:
        logger.warning("无灾情评估结果，跳过次生灾害预测", extra={"task_id": task_id})
        return {
            "secondary_hazards": [],
            "trace": trace,
            "errors": errors,
        }
    
    # 构造算法输入（符合SecondaryHazardPredictor接口要求）
    location = state.get("location", {})
    initial_data = state.get("initial_data", {})
    context = state.get("context", {})
    
    # 获取烈度信息
    intensity_map = assessment.get("intensity_map", {})
    max_intensity = intensity_map.get("max_intensity", 6) if intensity_map else 6
    
    # 构造params（根据灾害类型）
    params: Dict[str, Any] = {
        "intensity": max_intensity,
        "magnitude": initial_data.get("magnitude", 5.0),
        "gas_pipeline_density": context.get("gas_pipeline_density", 0.3),
        "building_age_years": context.get("building_age_years", 15),
        "slope_angle": context.get("slope_angle", 10),
        "soil_saturation": context.get("soil_saturation", 0.5),
        "rainfall_mm": initial_data.get("rainfall_mm", 0),
    }
    
    # 根据灾害类型选择预测的次生灾害
    hazard_types: List[str] = []
    if disaster_type == "earthquake":
        hazard_types = ["fire", "landslide", "aftershock"]
    elif disaster_type == "flood":
        hazard_types = ["landslide"]
    elif disaster_type == "hazmat":
        hazard_types = ["fire"]
    else:
        hazard_types = ["fire"]
    
    problem = {
        "primary_disaster": disaster_type,
        "params": params,
        "hazard_types": hazard_types,
    }
    
    # 调用算法
    predictor = SecondaryHazardPredictor()
    result = predictor.run(problem)
    
    if result.status != AlgorithmStatus.SUCCESS:
        error_msg = f"次生灾害预测失败: {result.message}"
        logger.error(error_msg, extra={"task_id": task_id})
        errors.append(error_msg)
        return {
            "secondary_hazards": [],
            "trace": trace,
            "errors": errors,
        }
    
    # 解析预测结果（SecondaryHazardPredictor返回SecondaryHazardRisk dataclass列表）
    predictions = result.solution
    secondary_hazards: List[SecondaryHazard] = []
    
    if isinstance(predictions, list):
        for pred in predictions:
            # 处理dataclass对象
            if hasattr(pred, "hazard_type"):
                hazard: SecondaryHazard = {
                    "type": pred.hazard_type,
                    "probability": pred.probability,
                    "risk_level": pred.severity,
                    "predicted_locations": [],
                    "trigger_conditions": "",
                }
            elif isinstance(pred, dict):
                hazard = {
                    "type": pred.get("type", "unknown"),
                    "probability": pred.get("probability", 0),
                    "risk_level": pred.get("risk_level", "low"),
                    "predicted_locations": pred.get("predicted_locations", []),
                    "trigger_conditions": pred.get("trigger_conditions", ""),
                }
            else:
                continue
            secondary_hazards.append(hazard)
    elif hasattr(predictions, "hazard_type"):
        # 单个dataclass结果
        hazard: SecondaryHazard = {
            "type": predictions.hazard_type,
            "probability": predictions.probability,
            "risk_level": predictions.severity,
            "predicted_locations": [],
            "trigger_conditions": "",
        }
        secondary_hazards.append(hazard)
    elif isinstance(predictions, dict):
        # 单个字典结果
        hazard = {
            "type": predictions.get("type", "unknown"),
            "probability": predictions.get("probability", 0),
            "risk_level": predictions.get("risk_level", "low"),
            "predicted_locations": predictions.get("predicted_locations", []),
            "trigger_conditions": predictions.get("trigger_conditions", ""),
        }
        secondary_hazards.append(hazard)
    
    logger.info(
        "次生灾害预测完成",
        extra={
            "task_id": task_id,
            "hazard_count": len(secondary_hazards),
            "hazard_types": [h["type"] for h in secondary_hazards],
        },
    )
    
    return {
        "secondary_hazards": secondary_hazards,
        "trace": trace,
        "errors": errors,
    }
