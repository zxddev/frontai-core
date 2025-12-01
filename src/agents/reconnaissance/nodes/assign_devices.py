"""CrewAI 设备分配节点

使用 CrewAI 专家系统进行智能设备筛选和任务分配。
可通过环境变量 RECON_USE_CREWAI=true 启用。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from src.agents.reconnaissance.state import (
    DeviceAssignment,
    DeviceInfo,
    ReconState,
)

logger = logging.getLogger(__name__)


def is_crewai_enabled() -> bool:
    """检查是否启用 CrewAI 设备分配"""
    return os.getenv("RECON_USE_CREWAI", "").lower() in ("true", "1", "yes")


async def assign_devices_with_crewai(state: ReconState) -> Dict[str, Any]:
    """使用 CrewAI 专家系统进行设备分配
    
    这个节点在 score_targets 之后运行，使用 CrewAI 的两个专家 Agent：
    1. 设备能力分析师：基于 base_capabilities 筛选侦察设备
    2. 任务分配专家：根据灾害类型和目标特征匹配设备
    
    输入：state 中的 devices（全部设备）和 scored_targets（已打分目标）
    输出：更新 devices（筛选后）、assignments、explanation
    """
    from src.agents.reconnaissance.crewai import run_device_assignment_crew
    
    scenario_id = state.get("scenario_id")
    targets = state.get("scored_targets", [])
    
    # 获取全部设备数据（需要从 trace 中获取，或重新查询）
    all_devices = state.get("trace", {}).get("all_devices", [])
    
    if not all_devices:
        logger.warning("[Recon-CrewAI] 无设备数据，跳过 CrewAI 分配")
        return {}
    
    if not targets:
        logger.info("[Recon-CrewAI] 无侦察目标，跳过 CrewAI 分配")
        return {}
    
    # 推断灾害类型（从目标的 area_type 中提取）
    disaster_type = _infer_disaster_type(targets)
    
    logger.info(
        "[Recon-CrewAI] 启动 CrewAI 设备分配",
        extra={
            "scenario_id": scenario_id,
            "devices_count": len(all_devices),
            "targets_count": len(targets),
            "disaster_type": disaster_type,
        },
    )
    
    try:
        recon_devices, assignments, explanation = await run_device_assignment_crew(
            devices=all_devices,
            targets=targets,
            disaster_type=disaster_type,
        )
        
        logger.info(
            "[Recon-CrewAI] CrewAI 分配完成",
            extra={
                "recon_devices": len(recon_devices),
                "assignments": len(assignments),
            },
        )
        
        return {
            "devices": recon_devices,
            "assignments": assignments,
            "explanation": explanation,
            "current_phase": "assign_devices_completed",
        }
        
    except Exception as e:
        logger.exception("[Recon-CrewAI] CrewAI 分配失败，回退到规则模式")
        errors = state.get("errors", [])
        errors.append(f"CrewAI 分配失败: {e}")
        return {
            "errors": errors,
            "current_phase": "assign_devices_fallback",
        }


def _infer_disaster_type(targets: List[Dict[str, Any]]) -> str:
    """从目标列表推断主要灾害类型"""
    type_counts: Dict[str, int] = {}
    
    for t in targets:
        area_type = t.get("_area_type", "")
        
        # 映射 area_type 到灾害类型
        if "flood" in area_type or "水" in t.get("name", ""):
            type_counts["flood"] = type_counts.get("flood", 0) + 1
        elif "landslide" in area_type or "滑坡" in t.get("name", ""):
            type_counts["landslide"] = type_counts.get("landslide", 0) + 1
        elif "seismic" in area_type or "地震" in t.get("name", ""):
            type_counts["earthquake"] = type_counts.get("earthquake", 0) + 1
        elif "fire" in area_type or "火" in t.get("name", ""):
            type_counts["fire"] = type_counts.get("fire", 0) + 1
        elif "contaminated" in area_type or "污染" in t.get("name", ""):
            type_counts["hazmat"] = type_counts.get("hazmat", 0) + 1
        else:
            type_counts["earthquake"] = type_counts.get("earthquake", 0) + 1
    
    if not type_counts:
        return "earthquake"
    
    return max(type_counts, key=type_counts.get)


__all__ = ["assign_devices_with_crewai", "is_crewai_enabled"]
