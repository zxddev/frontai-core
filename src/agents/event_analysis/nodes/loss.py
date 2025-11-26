"""
损失估算节点

调用LossEstimator算法估算经济损失和基础设施损毁
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from src.planning.algorithms import LossEstimator, AlgorithmStatus
from ..state import EventAnalysisState, LossEstimation

logger = logging.getLogger(__name__)


def estimate_loss(state: EventAnalysisState) -> Dict[str, Any]:
    """
    损失估算节点
    
    基于灾情评估结果，估算直接/间接经济损失和基础设施损毁
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    task_id = state.get("task_id", "unknown")
    disaster_type = state.get("disaster_type", "earthquake")
    assessment = state.get("assessment_result")
    
    logger.info(
        "开始损失估算",
        extra={"task_id": task_id, "disaster_type": disaster_type},
    )
    
    trace = state.get("trace", {})
    trace.setdefault("algorithms_used", []).append("LossEstimator")
    trace.setdefault("nodes_executed", []).append("estimate_loss")
    
    errors = list(state.get("errors", []))
    
    # 无评估结果时跳过估算
    if not assessment:
        logger.warning("无灾情评估结果，跳过损失估算", extra={"task_id": task_id})
        return {
            "loss_estimation": None,
            "trace": trace,
            "errors": errors,
        }
    
    # 构造算法输入（符合LossEstimator接口要求）
    location = state.get("location", {})
    initial_data = state.get("initial_data", {})
    context = state.get("context", {})
    
    # 获取烈度信息
    intensity_map = assessment.get("intensity_map", {})
    max_intensity = intensity_map.get("max_intensity", 6) if intensity_map else 6
    
    # 构造人口数据
    population_data = {
        "total": assessment.get("affected_population", 0),
        "density": context.get("population_density", 1000),
        "time_of_day": context.get("time_of_day", "day"),  # day/night
    }
    
    # 构造建筑清单（简化）
    building_inventory = context.get("building_inventory", [])
    if not building_inventory:
        # 根据建筑类型生成默认清单
        building_types = context.get("building_types", ["residential"])
        building_inventory = [
            {"type": bt, "count": 100, "age_years": 20}
            for bt in building_types
        ]
    
    problem = {
        "disaster_type": disaster_type,
        "intensity": max_intensity,
        "population_data": population_data,
        "building_inventory": building_inventory,
        "infrastructure": context.get("infrastructure", []),
        "economic_density": context.get("economic_density", 50000),  # 元/km²
    }
    
    # 调用算法
    estimator = LossEstimator()
    result = estimator.run(problem)
    
    if result.status != AlgorithmStatus.SUCCESS:
        error_msg = f"损失估算失败: {result.message}"
        logger.error(error_msg, extra={"task_id": task_id})
        errors.append(error_msg)
        return {
            "loss_estimation": None,
            "trace": trace,
            "errors": errors,
        }
    
    # 解析估算结果
    estimation = result.solution
    
    loss_estimation: LossEstimation = {
        "direct_economic_loss_yuan": estimation.get("direct_loss", 0),
        "indirect_economic_loss_yuan": estimation.get("indirect_loss", 0),
        "infrastructure_damage": estimation.get("infrastructure_damage", {}),
        "building_damage": estimation.get("building_damage", {}),
    }
    
    logger.info(
        "损失估算完成",
        extra={
            "task_id": task_id,
            "direct_loss": loss_estimation["direct_economic_loss_yuan"],
            "indirect_loss": loss_estimation["indirect_economic_loss_yuan"],
        },
    )
    
    return {
        "loss_estimation": loss_estimation,
        "trace": trace,
        "errors": errors,
    }
