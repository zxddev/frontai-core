"""
作业风险评估节点

分析现场救援作业的风险，综合气象、危险源等因素。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List

from ..state import EarlyWarningState, RiskPrediction, RiskFactor
from src.domains.weather import WeatherService

logger = logging.getLogger(__name__)


def _calculate_risk_level(factors: List[RiskFactor]) -> str:
    """根据风险因素计算综合风险等级"""
    level_scores = {"red": 4, "orange": 3, "yellow": 2, "blue": 1}
    max_score = 1
    for factor in factors:
        score = level_scores.get(factor["risk_level"], 1)
        max_score = max(max_score, score)
    return {4: "red", 3: "orange", 2: "yellow", 1: "blue"}[max_score]


async def predict_operation_risk(state: EarlyWarningState) -> Dict[str, Any]:
    """
    作业风险评估节点
    
    输入：
        - prediction_request.location: 作业位置
        - prediction_request.operation_type: 作业类型
        - disaster_situation: 灾害态势
        
    输出：
        - risk_predictions: 添加作业风险预测
    """
    logger.info(f"[作业风险评估] 开始 request_id={state['request_id']}")
    
    prediction_request = state.get("prediction_request", {})
    if not prediction_request:
        logger.warning("[作业风险评估] 无预测请求")
        return {
            "errors": state.get("errors", []) + ["无作业风险评估请求"],
            "current_phase": "predict_operation_risk_skipped",
        }
    
    location = prediction_request.get("location", {})
    operation_type = prediction_request.get("operation_type", "rescue")
    team_id = prediction_request.get("team_id")
    team_name = prediction_request.get("team_name") or "未知队伍"
    
    if not location:
        logger.warning("[作业风险评估] 缺少作业位置")
        return {
            "errors": state.get("errors", []) + ["作业风险评估需要位置"],
            "current_phase": "predict_operation_risk_failed",
        }
    
    risk_factors: List[RiskFactor] = []
    weather_available = False
    
    # 1. 获取气象数据（通过WeatherService）
    try:
        weather_service = WeatherService()
        current_weather = await weather_service.get_current_weather(
            lon=location.get("lon", 0),
            lat=location.get("lat", 0),
        )
        weather_available = True
        
        # 气象风险评估
        wind_risk = current_weather.get_wind_risk_level()
        if wind_risk != "blue":
            risk_factors.append(RiskFactor(
                factor_type="wind",
                risk_level=wind_risk,
                value=current_weather.wind_speed_ms,
                description=f"当前风速 {current_weather.wind_speed_ms:.1f}m/s，影响高空作业安全",
            ))
        
        precip_risk = current_weather.get_precipitation_risk_level()
        if precip_risk != "blue":
            risk_factors.append(RiskFactor(
                factor_type="precipitation",
                risk_level=precip_risk,
                value=current_weather.precipitation_mm,
                description=f"当前降水 {current_weather.precipitation_mm:.1f}mm，地面湿滑",
            ))
            
    except Exception as e:
        logger.warning(f"[作业风险评估] 气象数据获取失败: {e}")
    
    # 2. 分析灾害态势对作业的影响
    disaster = state.get("disaster_situation")
    if disaster:
        disaster_type = disaster.get("disaster_type", "unknown")
        severity = disaster.get("severity_level", 3)
        
        # 根据灾害类型评估作业风险
        type_risks = {
            "fire": ("燃烧蔓延风险", "orange" if severity >= 3 else "yellow"),
            "flood": ("水位上涨风险", "orange" if severity >= 3 else "yellow"),
            "chemical": ("化学品泄漏风险", "red" if severity >= 3 else "orange"),
            "landslide": ("二次滑坡风险", "red" if severity >= 4 else "orange"),
            "earthquake": ("余震风险", "orange"),
        }
        
        if disaster_type in type_risks:
            desc, level = type_risks[disaster_type]
            risk_factors.append(RiskFactor(
                factor_type="disaster_secondary",
                risk_level=level,
                value=severity,
                description=f"{desc}，灾害严重程度 {severity}/5",
            ))
    
    # 3. 根据作业类型评估固有风险
    operation_risks = {
        "rescue": [("confined_space", "yellow", "密闭空间作业风险")],
        "firefighting": [("heat_exposure", "orange", "高温暴露风险")],
        "hazmat": [("chemical_exposure", "red", "化学品接触风险")],
        "height_work": [("fall_risk", "orange", "高空坠落风险")],
        "demolition": [("collapse_risk", "orange", "结构坍塌风险")],
    }
    
    if operation_type in operation_risks:
        for factor_type, level, desc in operation_risks[operation_type]:
            risk_factors.append(RiskFactor(
                factor_type=factor_type,
                risk_level=level,
                value=1.0,
                description=desc,
            ))
    else:
        # 未知作业类型，添加警告
        logger.warning(f"[作业风险评估] 未知作业类型: {operation_type}")
        risk_factors.append(RiskFactor(
            factor_type="unknown_operation",
            risk_level="yellow",
            value=1.0,
            description=f"未知作业类型({operation_type})，建议人工评估风险",
        ))
    
    # 4. 计算综合风险
    risk_level = _calculate_risk_level(risk_factors) if risk_factors else "blue"
    risk_score = {"red": 90, "orange": 70, "yellow": 50, "blue": 20}[risk_level]
    
    # 5. 生成安全建议
    recommendations = []
    if risk_level == "red":
        recommendations.append("建议暂停作业，评估安全措施")
        recommendations.append("确保所有人员穿戴完整防护装备")
        recommendations.append("设置安全监护人员")
    elif risk_level == "orange":
        recommendations.append("加强安全监护，缩短轮换周期")
        recommendations.append("确认撤离路线畅通")
    elif risk_level == "yellow":
        recommendations.append("正常作业，注意安全规程")
        recommendations.append("保持通讯畅通")
    else:
        recommendations.append("作业环境安全，按规程操作")
    
    # 6. 生成解释
    explanation_parts = [f"作业类型：{operation_type}"]
    if disaster:
        explanation_parts.append(f"灾害环境：{disaster.get('disaster_type', '未知')}，严重程度 {disaster.get('severity_level', 3)}/5")
    for factor in risk_factors:
        explanation_parts.append(f"- {factor['description']}")
    
    explanation = "\n".join(explanation_parts)
    
    # 7. 构建预测结果
    confidence = 0.6
    if weather_available:
        confidence += 0.2
    if disaster:
        confidence += 0.2
    
    prediction = RiskPrediction(
        prediction_id=str(uuid.uuid4()),
        prediction_type="operation_risk",
        target_type="team",
        target_id=team_id,
        target_name=team_name,
        risk_level=risk_level,
        risk_score=risk_score,
        confidence_score=min(confidence, 1.0),
        risk_factors=risk_factors,
        recommendations=recommendations,
        explanation=explanation,
        prediction_horizon_hours=1,
        requires_human_review=(risk_level == "red"),
        weather_data=None,
        created_at=datetime.utcnow().isoformat(),
    )
    
    # 更新状态
    existing_predictions = state.get("risk_predictions", [])
    pending_reviews = state.get("pending_human_review", [])
    if prediction["requires_human_review"]:
        pending_reviews = pending_reviews + [prediction["prediction_id"]]
    
    logger.info(
        f"[作业风险评估] 完成 operation_type={operation_type} "
        f"risk_level={risk_level} factors={len(risk_factors)}"
    )
    
    return {
        "risk_predictions": existing_predictions + [prediction],
        "pending_human_review": pending_reviews,
        "current_phase": "operation_risk_predicted",
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["predict_operation_risk"],
        },
    }
