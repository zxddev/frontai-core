"""
Phase 2: 环境约束评估节点

评估天气条件、空域限制、地形障碍、通信覆盖。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..state import (
    ReconSchedulerState,
    EnvironmentAssessment,
    WeatherCondition,
    NoFlyZone,
    Obstacle,
)
from ..config import get_weather_rules

logger = logging.getLogger(__name__)


async def environment_assessment_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    环境约束评估节点
    
    输入:
        - disaster_analysis: 灾情分析结果
        - target_area: 目标区域
    
    输出:
        - environment_assessment: 环境评估结果
        - flight_condition: 飞行条件等级 (green/yellow/red/black)
    """
    logger.info("Phase 2: 环境约束评估")
    
    disaster_analysis = state.get("disaster_analysis", {})
    target_area = state.get("target_area")
    disaster_context = state.get("disaster_context", {})
    
    # 加载天气规则
    weather_rules = get_weather_rules()
    
    # 获取或模拟天气条件
    weather = _get_weather_condition(disaster_context)
    
    # 评估飞行条件
    flight_condition, weather_risk_level, restrictions = _assess_flight_condition(
        weather, weather_rules
    )
    
    # 获取空域限制
    no_fly_zones = _get_no_fly_zones(target_area, disaster_context)
    restricted_zones = disaster_context.get("restricted_zones", [])
    
    # 获取地形障碍
    obstacles = _get_obstacles(target_area, disaster_context)
    terrain_elevation_range = disaster_context.get("terrain_elevation_range", {
        "min_m": 0,
        "max_m": 500,
        "avg_m": 100,
    })
    
    # 通信覆盖
    signal_coverage = disaster_context.get("signal_coverage", {
        "coverage_percent": 80,
        "weak_areas": [],
    })
    
    # 计算推荐高度范围
    recommended_altitude = _calculate_recommended_altitude(
        weather, terrain_elevation_range, obstacles, disaster_analysis
    )
    
    # 计算可用时间窗口
    time_window = _calculate_time_window(weather, weather_rules)
    
    # 构建评估结果
    environment_assessment: EnvironmentAssessment = {
        # 天气
        "weather": weather,
        "weather_forecast": [],  # 可以从天气API获取
        "weather_risk_level": weather_risk_level,
        
        # 空域
        "no_fly_zones": no_fly_zones,
        "restricted_zones": restricted_zones,
        
        # 地形
        "terrain_elevation_range": terrain_elevation_range,
        "obstacles": obstacles,
        
        # 通信
        "signal_coverage": signal_coverage,
        
        # 综合评估
        "flight_condition": flight_condition,
        "recommended_altitude_range": recommended_altitude,
        "time_window_hours": time_window,
        "restrictions": restrictions,
    }
    
    # 如果是禁飞条件，添加警告
    warnings = state.get("warnings", [])
    if flight_condition == "black":
        warnings.append(f"天气条件禁止飞行: {', '.join(restrictions)}")
    elif flight_condition == "red":
        warnings.append(f"天气条件危险，仅允许必要的大型固定翼任务: {', '.join(restrictions)}")
    elif flight_condition == "yellow":
        warnings.append(f"天气条件谨慎: {', '.join(restrictions)}")
    
    logger.info(f"环境评估完成: 飞行条件={flight_condition}, 风险等级={weather_risk_level}, "
                f"时间窗口={time_window:.1f}h")
    
    return {
        "environment_assessment": environment_assessment,
        "flight_condition": flight_condition,
        "warnings": warnings,
        "current_phase": "environment_assessment",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "environment_assessment",
            "timestamp": datetime.now().isoformat(),
            "flight_condition": flight_condition,
            "weather_risk_level": weather_risk_level,
        }],
    }


def _get_weather_condition(disaster_context: Dict[str, Any]) -> WeatherCondition:
    """获取天气条件"""
    # 从上下文获取
    if disaster_context.get("weather"):
        return disaster_context["weather"]
    
    # 默认良好天气（实际应从天气API获取）
    return {
        "wind_speed_ms": 5.0,
        "wind_direction_deg": 180,
        "rain_level": "none",
        "visibility_m": 10000,
        "temperature_c": 20,
        "humidity_percent": 60,
        "pressure_hpa": 1013,
    }


def _assess_flight_condition(
    weather: WeatherCondition,
    weather_rules: Dict[str, Any]
) -> tuple:
    """
    评估飞行条件
    
    Returns:
        (flight_condition, weather_risk_level, restrictions)
    """
    restrictions = []
    
    wind_speed = weather.get("wind_speed_ms", 0)
    rain_level = weather.get("rain_level", "none")
    visibility = weather.get("visibility_m", 10000)
    
    flight_conditions = weather_rules.get("flight_conditions", {})
    decision_matrix = weather_rules.get("decision_matrix", {})
    
    # 检查禁飞条件 (black)
    wind_rules = flight_conditions.get("wind", {}).get("multirotor", {})
    visibility_rules = flight_conditions.get("visibility", {})
    rain_rules = flight_conditions.get("rain", {})
    
    # 风速检查
    no_fly_wind = wind_rules.get("no_fly_above_ms", 15)
    caution_wind = wind_rules.get("caution_max_ms", 12)
    safe_wind = wind_rules.get("safe_max_ms", 8)
    
    # 能见度检查
    no_fly_visibility = visibility_rules.get("no_fly_below_m", 300)
    caution_visibility = visibility_rules.get("min_caution_m", 500)
    safe_visibility = visibility_rules.get("min_safe_m", 1000)
    
    # 降雨检查
    rain_config = rain_rules.get(rain_level, {})
    
    # 判断飞行条件
    condition = "green"
    risk_level = "low"
    
    # 检查禁飞 (black)
    if wind_speed > no_fly_wind:
        condition = "black"
        risk_level = "critical"
        restrictions.append(f"风速{wind_speed}m/s超过禁飞阈值{no_fly_wind}m/s")
    
    if visibility < no_fly_visibility:
        condition = "black"
        risk_level = "critical"
        restrictions.append(f"能见度{visibility}m低于禁飞阈值{no_fly_visibility}m")
    
    if rain_level == "storm":
        condition = "black"
        risk_level = "critical"
        restrictions.append("暴雨天气禁飞")
    
    if condition == "black":
        return condition, risk_level, restrictions
    
    # 检查危险 (red)
    danger_conditions = 0
    
    if wind_speed > caution_wind:
        danger_conditions += 1
        restrictions.append(f"风速{wind_speed}m/s超过谨慎阈值{caution_wind}m/s")
    
    if visibility < caution_visibility:
        danger_conditions += 1
        restrictions.append(f"能见度{visibility}m低于谨慎阈值{caution_visibility}m")
    
    if rain_level == "heavy":
        danger_conditions += 1
        restrictions.append("大雨天气，多旋翼禁飞")
    
    if danger_conditions >= 1:
        condition = "red"
        risk_level = "high"
        return condition, risk_level, restrictions
    
    # 检查谨慎 (yellow)
    caution_conditions = 0
    
    if wind_speed > safe_wind:
        caution_conditions += 1
        restrictions.append(f"风速{wind_speed}m/s超过安全阈值{safe_wind}m/s，需谨慎")
    
    if visibility < safe_visibility:
        caution_conditions += 1
        restrictions.append(f"能见度{visibility}m低于安全阈值{safe_visibility}m，需谨慎")
    
    if rain_level == "moderate":
        caution_conditions += 1
        restrictions.append("中雨天气，部分设备受限")
    elif rain_level == "light":
        restrictions.append("小雨天气，需防水设备")
    
    if caution_conditions >= 1:
        condition = "yellow"
        risk_level = "medium"
        return condition, risk_level, restrictions
    
    return condition, risk_level, restrictions


def _get_no_fly_zones(
    target_area: Dict[str, Any],
    disaster_context: Dict[str, Any]
) -> List[NoFlyZone]:
    """获取禁飞区"""
    zones = []
    
    # 从上下文获取
    context_zones = disaster_context.get("no_fly_zones", [])
    for zone in context_zones:
        zones.append({
            "zone_id": zone.get("zone_id", f"zone_{len(zones)+1}"),
            "zone_type": zone.get("zone_type", "temporary"),
            "geometry": zone.get("geometry", {}),
            "max_altitude_m": zone.get("max_altitude_m"),
            "description": zone.get("description", "禁飞区"),
        })
    
    return zones


def _get_obstacles(
    target_area: Dict[str, Any],
    disaster_context: Dict[str, Any]
) -> List[Obstacle]:
    """获取障碍物"""
    obstacles = []
    
    # 从上下文获取
    context_obstacles = disaster_context.get("obstacles", [])
    for obs in context_obstacles:
        obstacles.append({
            "obstacle_id": obs.get("obstacle_id", f"obs_{len(obstacles)+1}"),
            "obstacle_type": obs.get("obstacle_type", "building"),
            "location": obs.get("location", {}),
            "height_m": obs.get("height_m", 50),
            "buffer_m": obs.get("buffer_m", 20),
        })
    
    return obstacles


def _calculate_recommended_altitude(
    weather: WeatherCondition,
    terrain: Dict[str, float],
    obstacles: List[Obstacle],
    disaster_analysis: Dict[str, Any]
) -> Dict[str, float]:
    """计算推荐高度范围（相对地面高度AGL）"""
    min_altitude = 50  # 最低相对地面高度
    max_altitude = 500  # 法规限制（相对地面）
    
    # 注意：这里计算的是相对地面高度(AGL)，不是海拔高度(MSL)
    # 所以地形高度不应该加到最低高度上
    
    # 考虑障碍物（相对地面的高度）
    if obstacles:
        max_obstacle = max(obs.get("height_m", 0) for obs in obstacles)
        min_altitude = max(min_altitude, max_obstacle + 20)  # 高于障碍物20m
    
    # 考虑灾情类型
    disaster_type = disaster_analysis.get("disaster_type", "")
    if disaster_type == "fire":
        min_altitude = max(min_altitude, 200)  # 火灾保持高度
    elif disaster_type == "hazmat":
        min_altitude = max(min_altitude, 300)  # 危化品保持更高
    
    # 确保min不超过max
    min_altitude = min(min_altitude, max_altitude - 50)
    
    return {
        "min_m": min_altitude,
        "max_m": max_altitude,
        "recommended_m": (min_altitude + max_altitude) / 2,
    }


def _calculate_time_window(
    weather: WeatherCondition,
    weather_rules: Dict[str, Any]
) -> float:
    """计算可用时间窗口（小时）"""
    # 简化实现：基于当前天气估计
    # 实际应该使用天气预报
    
    wind_speed = weather.get("wind_speed_ms", 0)
    rain_level = weather.get("rain_level", "none")
    
    if rain_level in ["heavy", "storm"]:
        return 0.0
    elif rain_level == "moderate":
        return 2.0
    elif wind_speed > 12:
        return 2.0
    elif wind_speed > 8:
        return 4.0
    else:
        return 8.0  # 良好天气，较长窗口
