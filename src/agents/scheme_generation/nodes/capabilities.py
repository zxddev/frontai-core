"""
能力提取节点

从规则触发结果中提取和合并能力需求
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..state import SchemeGenerationState, CapabilityRequirementState
from ..utils import track_node_time

logger = logging.getLogger(__name__)

# 优先级权重映射
PRIORITY_WEIGHTS = {
    "critical": 4.0,
    "high": 2.0,
    "medium": 1.0,
    "low": 0.5,
}


@track_node_time("extract_capabilities")
def extract_capabilities(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    能力提取节点
    
    从匹配的规则中提取能力需求，合并重复项，按优先级排序
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含capability_requirements
    """
    logger.info("开始执行能力提取节点")
    
    matched_rules = state.get("matched_rules", [])
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    # 能力需求字典: code -> CapabilityRequirementState
    capability_map: Dict[str, CapabilityRequirementState] = {}
    
    for rule in matched_rules:
        rule_id = rule["rule_id"]
        
        for cap_data in rule.get("required_capabilities", []):
            code = cap_data["code"]
            priority = cap_data["priority"]
            min_quantity = cap_data.get("min_quantity", 1)
            
            if code not in capability_map:
                # 新增能力需求
                capability_map[code] = {
                    "code": code,
                    "priority": priority,
                    "min_quantity": min_quantity,
                    "source_rule_id": rule_id,
                }
            else:
                # 合并能力需求：取更高优先级和更大数量
                existing = capability_map[code]
                existing_weight = PRIORITY_WEIGHTS.get(existing["priority"], 1.0)
                new_weight = PRIORITY_WEIGHTS.get(priority, 1.0)
                
                if new_weight > existing_weight:
                    existing["priority"] = priority
                
                if min_quantity > existing["min_quantity"]:
                    existing["min_quantity"] = min_quantity
    
    # 转换为列表并按优先级排序
    requirements = list(capability_map.values())
    requirements.sort(
        key=lambda r: PRIORITY_WEIGHTS.get(r["priority"], 1.0),
        reverse=True,
    )
    
    # 统计
    critical_count = sum(1 for r in requirements if r["priority"] == "critical")
    high_count = sum(1 for r in requirements if r["priority"] == "high")
    
    logger.info(
        f"能力提取完成: 共{len(requirements)}项能力需求, "
        f"其中critical={critical_count}, high={high_count}"
    )
    
    # 更新追踪信息
    trace["capability_codes"] = [r["code"] for r in requirements]
    trace.setdefault("nodes_executed", []).append("extract_capabilities")
    
    return {
        "capability_requirements": requirements,
        "trace": trace,
        "errors": errors,
    }
