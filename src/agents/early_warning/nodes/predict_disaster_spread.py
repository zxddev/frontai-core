"""
灾害扩散预测节点

预测灾害在未来1h/6h/24h的扩散范围。
使用简化模型：风向+速度+时间
"""
from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime
from typing import Dict, Any, List, Tuple

from ..state import EarlyWarningState, RiskPrediction, RiskFactor
from src.domains.weather import WeatherService

logger = logging.getLogger(__name__)


def _calculate_spread_distance(
    spread_speed_mps: float,
    hours: int,
    wind_speed_ms: float = 0,
    wind_factor: float = 0.3,
) -> float:
    """计算扩散距离（米）"""
    base_distance = spread_speed_mps * hours * 3600
    wind_contribution = wind_speed_ms * wind_factor * hours * 3600
    return base_distance + wind_contribution


def _wind_direction_to_radians(direction_deg: float) -> float:
    """风向角度转弧度（气象风向：风来自的方向）"""
    return math.radians((direction_deg + 180) % 360)


def _calculate_spread_polygon(
    center_lon: float,
    center_lat: float,
    distance_m: float,
    wind_direction_deg: float,
    spread_angle: float = 60,
) -> List[Tuple[float, float]]:
    """
    计算扩散多边形（简化扇形）
    
    Args:
        center_lon, center_lat: 中心点
        distance_m: 扩散距离
        wind_direction_deg: 风向（风去的方向）
        spread_angle: 扩散角度（度）
    
    Returns:
        多边形顶点列表 [(lon, lat), ...]
    """
    points = [(center_lon, center_lat)]
    
    meters_per_deg_lon = 111000 * math.cos(math.radians(center_lat))
    meters_per_deg_lat = 111000
    
    wind_rad = math.radians(wind_direction_deg)
    half_angle = math.radians(spread_angle / 2)
    
    for angle_offset in [-half_angle, 0, half_angle]:
        angle = wind_rad + angle_offset
        dx = distance_m * math.sin(angle) / meters_per_deg_lon
        dy = distance_m * math.cos(angle) / meters_per_deg_lat
        points.append((center_lon + dx, center_lat + dy))
    
    points.append(points[0])
    return points


async def predict_disaster_spread(state: EarlyWarningState) -> Dict[str, Any]:
    """
    灾害扩散预测节点
    
    输入：
        - disaster_situation: 灾害态势
        - prediction_request.prediction_hours: 预测时间范围
        
    输出：
        - risk_predictions: 添加扩散预测
    """
    logger.info(f"[灾害扩散预测] 开始 request_id={state['request_id']}")
    
    disaster = state.get("disaster_situation")
    if not disaster:
        logger.warning("[灾害扩散预测] 无灾害态势数据")
        return {
            "errors": state.get("errors", []) + ["灾害扩散预测需要灾害态势数据"],
            "current_phase": "predict_spread_skipped",
        }
    
    prediction_request = state.get("prediction_request", {})
    prediction_hours_list = prediction_request.get("prediction_hours_list", [1, 6, 24])
    
    # 过滤无效的hours值（必须为正整数）
    prediction_hours_list = [h for h in prediction_hours_list if isinstance(h, int) and h > 0]
    
    if not prediction_hours_list:
        logger.warning("[灾害扩散预测] 无有效的预测时间点")
        return {
            "errors": state.get("errors", []) + ["灾害扩散预测需要至少一个有效的预测时间点(正整数)"],
            "current_phase": "predict_spread_failed",
        }
    
    center = disaster.get("center_point", {})
    center_lon = center.get("lon", 0)
    center_lat = center.get("lat", 0)
    
    disaster_type = disaster.get("disaster_type", "unknown")
    spread_speed = disaster.get("spread_speed_mps", 0) or 0
    spread_direction = disaster.get("spread_direction")
    severity = disaster.get("severity_level", 3)
    
    # 默认扩散速度（根据灾害类型）
    default_speeds = {
        "fire": 0.5,
        "flood": 0.3,
        "chemical": 0.2,
        "landslide": 0.1,
        "earthquake": 0,
    }
    if spread_speed == 0:
        spread_speed = default_speeds.get(disaster_type, 0.1)
    
    risk_factors: List[RiskFactor] = []
    spread_predictions = []
    weather_context = None
    
    # 1. 获取气象数据（通过WeatherService）
    wind_speed_ms = 0
    wind_direction_deg = 0
    try:
        weather_service = WeatherService()
        forecast = await weather_service.get_weather_forecast(
            lon=center_lon,
            lat=center_lat,
            hours=max(prediction_hours_list),
        )
        weather_context = {
            "current": {
                "wind_speed_ms": forecast.current.wind_speed_ms if forecast.current else 0,
                "wind_direction_deg": forecast.current.wind_direction_deg if forecast.current else 0,
            }
        }
        if forecast.current:
            wind_speed_ms = forecast.current.wind_speed_ms
            wind_direction_deg = forecast.current.wind_direction_deg
            
    except Exception as e:
        logger.warning(f"[灾害扩散预测] 气象数据获取失败: {e}")
    
    # 使用灾害指定的扩散方向，否则使用风向
    if spread_direction:
        direction_map = {
            "N": 0, "NE": 45, "E": 90, "SE": 135,
            "S": 180, "SW": 225, "W": 270, "NW": 315,
        }
        effective_direction = direction_map.get(spread_direction.upper(), wind_direction_deg)
    else:
        effective_direction = wind_direction_deg
    
    # 2. 计算各时间尺度的扩散
    for hours in prediction_hours_list:
        # 计算扩散距离
        distance_m = _calculate_spread_distance(
            spread_speed_mps=spread_speed,
            hours=hours,
            wind_speed_ms=wind_speed_ms if disaster_type in ["fire", "chemical"] else 0,
        )
        
        # 计算扩散区域
        spread_polygon = _calculate_spread_polygon(
            center_lon=center_lon,
            center_lat=center_lat,
            distance_m=distance_m,
            wind_direction_deg=effective_direction,
            spread_angle=90 if disaster_type == "fire" else 60,
        )
        
        spread_predictions.append({
            "hours": hours,
            "distance_m": distance_m,
            "polygon": spread_polygon,
            "direction_deg": effective_direction,
        })
        
        # 评估风险
        if distance_m > 5000:
            risk_factors.append(RiskFactor(
                factor_type=f"spread_{hours}h",
                risk_level="red",
                value=distance_m,
                description=f"{hours}小时内可能扩散 {distance_m/1000:.1f}km",
            ))
        elif distance_m > 2000:
            risk_factors.append(RiskFactor(
                factor_type=f"spread_{hours}h",
                risk_level="orange",
                value=distance_m,
                description=f"{hours}小时内可能扩散 {distance_m/1000:.1f}km",
            ))
        elif distance_m > 500:
            risk_factors.append(RiskFactor(
                factor_type=f"spread_{hours}h",
                risk_level="yellow",
                value=distance_m,
                description=f"{hours}小时内可能扩散 {distance_m:.0f}m",
            ))
    
    # 3. 计算综合风险
    level_scores = {"red": 4, "orange": 3, "yellow": 2, "blue": 1}
    max_score = max((level_scores.get(f["risk_level"], 1) for f in risk_factors), default=1)
    risk_level = {4: "red", 3: "orange", 2: "yellow", 1: "blue"}[max_score]
    risk_score = {"red": 90, "orange": 70, "yellow": 50, "blue": 20}[risk_level]
    
    # 4. 生成建议
    recommendations = []
    if risk_level in ["red", "orange"]:
        recommendations.append("建议扩大警戒范围")
        recommendations.append("通知下风向区域人员疏散")
        recommendations.append("准备阻断扩散的措施")
    elif risk_level == "yellow":
        recommendations.append("密切监控灾害发展态势")
        recommendations.append("准备疏散预案")
    else:
        recommendations.append("灾害扩散速度较慢，持续监控")
    
    # 5. 生成解释
    explanation_parts = [
        f"灾害类型：{disaster_type}",
        f"当前扩散速度：{spread_speed:.2f} m/s",
        f"扩散方向：{effective_direction}°",
    ]
    if wind_speed_ms > 0:
        explanation_parts.append(f"风速影响：{wind_speed_ms:.1f} m/s")
    for sp in spread_predictions:
        explanation_parts.append(f"- {sp['hours']}h预测扩散：{sp['distance_m']:.0f}m")
    
    explanation = "\n".join(explanation_parts)
    
    # 6. 构建预测结果
    confidence = 0.5
    if weather_context:
        confidence += 0.2
    if spread_speed > 0:
        confidence += 0.15
    if spread_direction:
        confidence += 0.15
    
    prediction = RiskPrediction(
        prediction_id=str(uuid.uuid4()),
        prediction_type="disaster_spread",
        target_type="area",
        target_id=disaster.get("id"),
        target_name=disaster.get("disaster_name", f"{disaster_type}灾害"),
        risk_level=risk_level,
        risk_score=risk_score,
        confidence_score=min(confidence, 1.0),
        risk_factors=risk_factors,
        recommendations=recommendations,
        explanation=explanation,
        prediction_horizon_hours=max(prediction_hours_list),
        requires_human_review=(risk_level == "red"),
        weather_data={
            "spread_predictions": spread_predictions,
            "wind_speed_ms": wind_speed_ms,
            "wind_direction_deg": wind_direction_deg,
        },
        created_at=datetime.utcnow().isoformat(),
    )
    
    # 更新状态
    existing_predictions = state.get("risk_predictions", [])
    pending_reviews = state.get("pending_human_review", [])
    if prediction["requires_human_review"]:
        pending_reviews = pending_reviews + [prediction["prediction_id"]]
    
    logger.info(
        f"[灾害扩散预测] 完成 disaster_type={disaster_type} "
        f"risk_level={risk_level} spread_count={len(spread_predictions)}"
    )
    
    return {
        "risk_predictions": existing_predictions + [prediction],
        "weather_context": weather_context or state.get("weather_context"),
        "pending_human_review": pending_reviews,
        "current_phase": "spread_predicted",
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["predict_disaster_spread"],
        },
    }
