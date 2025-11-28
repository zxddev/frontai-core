"""
需求分析节点

根据灾情分析结果确定所需装备类型和能力。
使用DisasterRequirementInferencer统一推断需求，替代硬编码MAP。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.domains.disaster import (
    DisasterRequirementInferencer,
    ResponsePhase,
)
from ..state import EquipmentPreparationState, RequirementSpec

logger = logging.getLogger(__name__)


# 环境因素识别
ENVIRONMENT_FACTORS: Dict[str, List[str]] = {
    "has_building_collapse": ["collapsed_building", "narrow_space", "unstable_structure"],
    "has_trapped_persons": ["life_threatening", "time_critical"],
    "has_secondary_fire": ["fire_hazard", "smoke"],
    "has_hazmat_leak": ["chemical_hazard", "contamination"],
    "has_road_damage": ["difficult_access", "off_road"],
}


async def analyze_requirements(state: EquipmentPreparationState) -> Dict[str, Any]:
    """
    需求分析节点
    
    根据灾情分析结果确定：
    1. 所需能力列表
    2. 所需设备类型
    3. 所需物资类别
    4. 环境因素
    5. 预估救援人数
    """
    logger.info("执行需求分析节点", extra={"event_id": state.get("event_id")})
    
    parsed_disaster = state.get("parsed_disaster")
    if not parsed_disaster:
        logger.warning("无灾情分析结果，使用默认需求")
        return {
            "requirement_spec": _get_default_requirements(),
            "current_phase": "requirement_analysis",
        }
    
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    
    # 使用统一推断器获取需求（替代硬编码MAP）
    inferencer = DisasterRequirementInferencer()
    
    # 确定所需能力（自动处理灾情特征）
    required_capabilities = inferencer.infer_capabilities(
        disaster_type=disaster_type,
        phase=ResponsePhase.IMMEDIATE,
        has_building_collapse=parsed_disaster.get("has_building_collapse", False),
        has_trapped_persons=parsed_disaster.get("has_trapped_persons", False),
        has_secondary_fire=parsed_disaster.get("has_secondary_fire", False),
        has_hazmat_leak=parsed_disaster.get("has_hazmat_leak", False),
    )
    
    # 确定所需设备类型
    required_device_types = inferencer.infer_device_types(disaster_type)
    
    # 确定所需物资类别
    required_supply_categories = inferencer.infer_supply_categories(disaster_type)
    
    # 识别环境因素
    environment_factors: List[str] = []
    for factor_key, factors in ENVIRONMENT_FACTORS.items():
        if parsed_disaster.get(factor_key):
            environment_factors.extend(factors)
    environment_factors = list(set(environment_factors))  # 去重
    
    # 预估救援人数需求（基于被困人数和受影响人口）
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0)
    affected_population = parsed_disaster.get("affected_population", 0)
    
    # 简单估算：每10名被困人员需要1组救援人员，最少1组
    estimated_personnel = max(1, estimated_trapped // 10 + 1)
    
    # 特殊要求
    special_requirements: List[str] = []
    severity = parsed_disaster.get("severity", "medium")
    if severity in ["critical", "high"]:
        special_requirements.append("priority_dispatch")  # 优先调度
    if parsed_disaster.get("has_hazmat_leak"):
        special_requirements.append("hazmat_certified")   # 需要危化品认证
    if environment_factors and "narrow_space" in environment_factors:
        special_requirements.append("small_form_factor")  # 小型设备优先
    
    requirement_spec: RequirementSpec = {
        "required_capabilities": required_capabilities,
        "required_device_types": required_device_types,
        "required_supply_categories": required_supply_categories,
        "environment_factors": environment_factors,
        "estimated_personnel": estimated_personnel,
        "special_requirements": special_requirements,
    }
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["analyze_requirements"]
    
    logger.info(
        "需求分析完成",
        extra={
            "capabilities": len(required_capabilities),
            "device_types": required_device_types,
            "supply_categories": len(required_supply_categories),
        }
    )
    
    return {
        "requirement_spec": requirement_spec,
        "current_phase": "requirement_analysis",
        "trace": trace,
    }


def _get_default_requirements() -> RequirementSpec:
    """获取默认需求规格"""
    return {
        "required_capabilities": ["aerial_reconnaissance", "life_detection"],
        "required_device_types": ["drone"],
        "required_supply_categories": ["medical", "rescue"],
        "environment_factors": [],
        "estimated_personnel": 1,
        "special_requirements": [],
    }
