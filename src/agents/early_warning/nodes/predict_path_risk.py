"""
路径风险预测节点

分析行进中队伍的路径风险，综合气象、灾害态势等因素。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..state import EarlyWarningState, RiskPrediction, RiskFactor
from src.domains.weather import WeatherService
from src.domains.routing import RoutePlanningService, Point, AvoidArea

logger = logging.getLogger(__name__)


def _calculate_risk_level(factors: List[RiskFactor]) -> str:
    """根据风险因素计算综合风险等级"""
    level_scores = {"red": 4, "orange": 3, "yellow": 2, "blue": 1}
    max_score = 1
    for factor in factors:
        score = level_scores.get(factor["risk_level"], 1)
        max_score = max(max_score, score)
    return {4: "red", 3: "orange", 2: "yellow", 1: "blue"}[max_score]


def _calculate_confidence(
    weather_available: bool,
    disaster_available: bool,
    route_available: bool,
) -> float:
    """计算置信度"""
    confidence = 0.6
    if weather_available:
        confidence += 0.15
    if disaster_available:
        confidence += 0.15
    if route_available:
        confidence += 0.1
    return min(confidence, 1.0)


async def predict_path_risk(state: EarlyWarningState) -> Dict[str, Any]:
    """
    路径风险预测节点
    
    输入：
        - prediction_request.origin: 起点
        - prediction_request.destination: 终点
        - prediction_request.team_id: 队伍ID
        - disaster_situation: 灾害态势（可选）
        
    输出：
        - risk_predictions: 添加路径风险预测
        - weather_context: 气象数据
    """
    logger.info(f"[路径风险预测] 开始 request_id={state['request_id']}")
    
    prediction_request = state.get("prediction_request", {})
    if not prediction_request:
        logger.warning("[路径风险预测] 无预测请求")
        return {
            "errors": state.get("errors", []) + ["无路径风险预测请求"],
            "current_phase": "predict_path_risk_skipped",
        }
    
    origin = prediction_request.get("origin", {})
    destination = prediction_request.get("destination", {})
    team_id = prediction_request.get("team_id")
    team_name = prediction_request.get("team_name") or "未知队伍"
    prediction_hours = prediction_request.get("prediction_hours", 6)
    
    if not origin or not destination:
        logger.warning("[路径风险预测] 缺少起终点")
        return {
            "errors": state.get("errors", []) + ["路径风险预测需要起终点"],
            "current_phase": "predict_path_risk_failed",
        }
    
    risk_factors: List[RiskFactor] = []
    weather_context = None
    route_available = False
    
    # 1. 获取气象数据（通过WeatherService）
    try:
        weather_service = WeatherService()
        weather_risk_obj = await weather_service.get_weather_risk_summary(
            lon=origin.get("lon", 0),
            lat=origin.get("lat", 0),
            hours=prediction_hours,
        )
        weather_risk = weather_risk_obj.to_dict()
        weather_context = weather_risk
        
        # 添加气象风险因素
        if weather_risk["wind_risk_level"] != "blue":
            risk_factors.append(RiskFactor(
                factor_type="wind",
                risk_level=weather_risk["wind_risk_level"],
                value=weather_risk["max_wind_speed_ms"],
                description=f"风速 {weather_risk['max_wind_speed_ms']:.1f}m/s",
            ))
        
        if weather_risk["precipitation_risk_level"] != "blue":
            risk_factors.append(RiskFactor(
                factor_type="precipitation",
                risk_level=weather_risk["precipitation_risk_level"],
                value=weather_risk["max_precipitation_mm"],
                description=f"降水 {weather_risk['max_precipitation_mm']:.1f}mm/h",
            ))
            
    except Exception as e:
        logger.warning(f"[路径风险预测] 气象数据获取失败: {e}")
        weather_context = {"error": str(e)}
    
    # 2. 分析灾害态势
    disaster = state.get("disaster_situation")
    if disaster:
        center = disaster.get("center_point", {})
        disaster_lon = center.get("lon", 0)
        disaster_lat = center.get("lat", 0)
        
        # 计算起点到灾害的距离（简化计算）
        origin_lon = origin.get("lon", 0)
        origin_lat = origin.get("lat", 0)
        import math
        dx = (disaster_lon - origin_lon) * 111000 * math.cos(math.radians(origin_lat))
        dy = (disaster_lat - origin_lat) * 111000
        distance_m = math.sqrt(dx*dx + dy*dy)
        
        # 根据距离判断风险
        if distance_m < 1000:
            risk_factors.append(RiskFactor(
                factor_type="disaster_proximity",
                risk_level="red",
                value=distance_m,
                description=f"距灾害中心 {distance_m:.0f}m（极近）",
            ))
        elif distance_m < 3000:
            risk_factors.append(RiskFactor(
                factor_type="disaster_proximity",
                risk_level="orange",
                value=distance_m,
                description=f"距灾害中心 {distance_m:.0f}m（较近）",
            ))
        elif distance_m < 5000:
            risk_factors.append(RiskFactor(
                factor_type="disaster_proximity",
                risk_level="yellow",
                value=distance_m,
                description=f"距灾害中心 {distance_m:.0f}m（中等）",
            ))
    
    # 3. 计算综合风险等级
    risk_level = _calculate_risk_level(risk_factors) if risk_factors else "blue"
    risk_score = {"red": 90, "orange": 70, "yellow": 50, "blue": 20}[risk_level]
    
    # 4. 生成建议
    recommendations = []
    if risk_level == "red":
        recommendations.append("建议暂停行进，等待风险降低")
        recommendations.append("联系指挥中心获取进一步指示")
    elif risk_level == "orange":
        recommendations.append("建议减速行驶，提高警惕")
        recommendations.append("准备备用路线")
    elif risk_level == "yellow":
        recommendations.append("正常行驶，注意观察路况")
    
    # 5. 生成解释
    explanation_parts = []
    if weather_context and not weather_context.get("error"):
        explanation_parts.append(f"气象分析：未来{prediction_hours}小时")
        for factor in weather_context.get("risk_factors", []):
            explanation_parts.append(f"  - {factor}")
    if disaster:
        explanation_parts.append(f"灾害态势：{disaster.get('disaster_type', '未知')}类型")
    if not risk_factors:
        explanation_parts.append("当前路径风险较低")
    
    explanation = "\n".join(explanation_parts) if explanation_parts else "无特殊风险"
    
    # 6. 构建预测结果
    confidence = _calculate_confidence(
        weather_available=weather_context is not None and not weather_context.get("error"),
        disaster_available=disaster is not None,
        route_available=route_available,
    )
    
    prediction = RiskPrediction(
        prediction_id=str(uuid.uuid4()),
        prediction_type="path_risk",
        target_type="team",
        target_id=team_id,
        target_name=team_name,
        risk_level=risk_level,
        risk_score=risk_score,
        confidence_score=confidence,
        risk_factors=risk_factors,
        recommendations=recommendations,
        explanation=explanation,
        prediction_horizon_hours=prediction_hours,
        requires_human_review=(risk_level == "red"),
        weather_data=weather_context,
        created_at=datetime.utcnow().isoformat(),
    )
    
    # 更新状态
    existing_predictions = state.get("risk_predictions", [])
    pending_reviews = state.get("pending_human_review", [])
    if prediction["requires_human_review"]:
        pending_reviews = pending_reviews + [prediction["prediction_id"]]
    
    logger.info(
        f"[路径风险预测] 完成 risk_level={risk_level} "
        f"confidence={confidence:.2f} factors={len(risk_factors)}"
    )
    
    return {
        "risk_predictions": existing_predictions + [prediction],
        "weather_context": weather_context,
        "pending_human_review": pending_reviews,
        "current_phase": "path_risk_predicted",
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["predict_path_risk"],
        },
    }
