"""
灾情评估节点

调用DisasterAssessment算法进行灾情等级评估
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from src.planning.algorithms import DisasterAssessment, AlgorithmStatus
from ..state import EventAnalysisState, AssessmentResult

logger = logging.getLogger(__name__)

# 灾情等级颜色映射
LEVEL_COLOR_MAP: Dict[str, str] = {
    "I": "红色",
    "II": "橙色",
    "III": "黄色",
    "IV": "蓝色",
}

# 灾情等级响应级别映射
LEVEL_RESPONSE_MAP: Dict[str, str] = {
    "I": "国家级",
    "II": "省级",
    "III": "市级",
    "IV": "县级",
}


def assess_disaster(state: EventAnalysisState) -> Dict[str, Any]:
    """
    灾情评估节点
    
    调用DisasterAssessment算法评估灾情等级、影响范围、预估伤亡
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    task_id = state.get("task_id", "unknown")
    disaster_type = state.get("disaster_type", "earthquake")
    
    logger.info(
        "开始灾情评估",
        extra={"task_id": task_id, "disaster_type": disaster_type},
    )
    
    # 构造算法输入
    location = state.get("location", {})
    initial_data = state.get("initial_data", {})
    context = state.get("context", {})
    
    # 构造epicenter/source_location
    epicenter = {
        "lat": location.get("latitude", 0),
        "lng": location.get("longitude", 0),
    }
    
    # 根据灾害类型构造参数
    params: Dict[str, Any] = {}
    
    if disaster_type == "earthquake":
        params = {
            "magnitude": initial_data.get("magnitude", 5.0),
            "depth_km": initial_data.get("depth_km", 10),
            "epicenter": epicenter,
            "population_density": context.get("population_density", 1000),
            "building_vulnerability": context.get("building_vulnerability", 0.5),
        }
    elif disaster_type == "flood":
        params = {
            "rainfall_mm": initial_data.get("rainfall_mm", 100),
            "duration_hours": initial_data.get("duration_hours", 6),
            "terrain_slope": context.get("terrain_slope", 1),
            "drainage_capacity": context.get("drainage_capacity", 30),
            "affected_area_km2": initial_data.get("affected_area_km2", 10),
            "population_density": context.get("population_density", 3000),
        }
    elif disaster_type == "hazmat":
        params = {
            "chemical_type": initial_data.get("chemical_type", "ammonia"),
            "leak_rate_kg_s": initial_data.get("leak_rate_kg_s", 1.0),
            "wind_speed_ms": initial_data.get("wind_speed_ms", 3.0),
            "wind_direction": initial_data.get("wind_direction", 0),
            "source_location": epicenter,
            "atmospheric_stability": initial_data.get("atmospheric_stability", "D"),
            "population_density": context.get("population_density", 2000),
        }
    else:
        # 默认使用地震参数模式
        params = {
            "magnitude": initial_data.get("magnitude", 5.0),
            "depth_km": initial_data.get("depth_km", 10),
            "epicenter": epicenter,
            "population_density": context.get("population_density", 1000),
            "building_vulnerability": context.get("building_vulnerability", 0.5),
        }
    
    # 调用算法
    assessor = DisasterAssessment()
    result = assessor.run({
        "disaster_type": disaster_type,
        "params": params,
    })
    
    # 处理结果
    trace = state.get("trace", {})
    trace.setdefault("algorithms_used", []).append("DisasterAssessment")
    trace.setdefault("nodes_executed", []).append("assess_disaster")
    
    errors = list(state.get("errors", []))
    
    if result.status != AlgorithmStatus.SUCCESS:
        error_msg = f"灾情评估失败: {result.message}"
        logger.error(error_msg, extra={"task_id": task_id})
        errors.append(error_msg)
        return {
            "assessment_result": None,
            "ai_confidence": 0.0,
            "trace": trace,
            "errors": errors,
        }
    
    # 解析算法输出
    solution = result.solution
    level_str = solution.level.value if hasattr(solution.level, "value") else str(solution.level)
    
    assessment_result: AssessmentResult = {
        "disaster_type": disaster_type,
        "disaster_level": level_str,
        "disaster_level_color": LEVEL_COLOR_MAP.get(level_str, "黄色"),
        "response_level": LEVEL_RESPONSE_MAP.get(level_str, "市级"),
        "affected_area_km2": solution.affected_area_km2,
        "affected_population": solution.affected_population,
        "estimated_casualties": solution.estimated_casualties,
        "intensity_map": solution.intensity_map,
        "risk_zones": solution.risk_zones,
        "confidence": solution.confidence,
    }
    
    logger.info(
        "灾情评估完成",
        extra={
            "task_id": task_id,
            "disaster_level": level_str,
            "affected_population": solution.affected_population,
            "confidence": solution.confidence,
        },
    )
    
    return {
        "assessment_result": assessment_result,
        "ai_confidence": solution.confidence,
        "trace": trace,
        "errors": errors,
    }
