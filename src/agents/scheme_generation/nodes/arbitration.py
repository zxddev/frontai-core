"""
场景仲裁节点

处理多事件场景的优先级仲裁和资源冲突消解
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..state import SchemeGenerationState, ScenePriorityState
from ..utils import track_node_time

logger = logging.getLogger(__name__)


@track_node_time("arbitrate_scenes")
def arbitrate_scenes(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    场景仲裁节点
    
    当存在多个事件场景时，进行优先级仲裁和资源冲突消解
    单事件场景时直接跳过
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含scene_priorities和conflict_resolutions
    """
    logger.info("开始执行场景仲裁节点")
    
    event_analysis = state.get("event_analysis", {})
    resource_allocations = state.get("resource_allocations", [])
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    # 检查是否为多场景
    related_events = event_analysis.get("related_events", [])
    
    if not related_events:
        # 单事件场景，生成默认优先级
        scene_priorities = [_create_default_priority(event_analysis)]
        conflict_resolutions: List[Dict[str, Any]] = []
        logger.info("单事件场景，跳过仲裁")
    else:
        # 多事件场景，执行仲裁
        try:
            scene_priorities, conflict_resolutions = _arbitrate_multiple_scenes(
                main_event=event_analysis,
                related_events=related_events,
                resource_allocations=resource_allocations,
            )
            logger.info(f"多场景仲裁完成: {len(scene_priorities)}个场景")
        except Exception as e:
            logger.error(f"场景仲裁失败: {e}")
            errors.append(f"场景仲裁失败: {e}")
            scene_priorities = [_create_default_priority(event_analysis)]
            conflict_resolutions = []
    
    # 更新追踪信息
    trace["scene_count"] = len(scene_priorities)
    trace["conflict_count"] = len(conflict_resolutions)
    trace.setdefault("nodes_executed", []).append("arbitrate_scenes")
    
    return {
        "scene_priorities": scene_priorities,
        "conflict_resolutions": conflict_resolutions,
        "trace": trace,
        "errors": errors,
    }


def _create_default_priority(event_analysis: Dict[str, Any]) -> ScenePriorityState:
    """为单事件创建默认优先级"""
    event_id = event_analysis.get("event_id", "unknown")
    
    # 从事件分析提取优先级因素
    assessment = event_analysis.get("assessment", {})
    casualties = assessment.get("estimated_casualties", {})
    
    trapped = casualties.get("trapped", 0)
    deaths = casualties.get("deaths", 0)
    injuries = casualties.get("injuries", 0)
    
    # 计算生命威胁分数
    life_threat = min(1.0, (trapped * 0.5 + deaths * 0.3 + injuries * 0.2) / 100)
    
    # 时间紧迫性（基于灾害类型）
    disaster_type = event_analysis.get("disaster_type", "unknown")
    urgency_map = {
        "earthquake": 0.9,
        "fire": 0.95,
        "hazmat": 0.85,
        "flood": 0.7,
        "landslide": 0.8,
    }
    time_urgency = urgency_map.get(disaster_type, 0.5)
    
    # 综合得分
    priority_score = life_threat * 0.4 + time_urgency * 0.3 + 0.3
    
    return {
        "scene_id": str(event_id),
        "scene_name": event_analysis.get("title", "主要事件"),
        "priority_score": round(priority_score, 3),
        "rank": 1,
        "dimension_scores": {
            "life_threat": round(life_threat, 3),
            "time_urgency": round(time_urgency, 3),
            "resource_availability": 1.0,
        },
    }


def _arbitrate_multiple_scenes(
    main_event: Dict[str, Any],
    related_events: List[Dict[str, Any]],
    resource_allocations: List[Dict[str, Any]],
) -> tuple[List[ScenePriorityState], List[Dict[str, Any]]]:
    """
    多场景仲裁
    
    调用SceneArbitrator算法进行优先级排序和资源分配
    """
    try:
        from src.planning.algorithms.arbitration import SceneArbitrator
        
        # 构造所有场景
        all_events = [main_event] + related_events
        
        scenes = []
        for event in all_events:
            assessment = event.get("assessment", {})
            casualties = assessment.get("estimated_casualties", {})
            
            scene = {
                "id": str(event.get("event_id", "")),
                "name": event.get("title", ""),
                "scene_type": "primary" if event == main_event else "secondary",
                "affected_population": casualties.get("trapped", 0) + casualties.get("injuries", 0),
                "life_threat_level": 0.8,
                "golden_time_remaining_min": 60,
                "disaster_spread_rate": 0.3,
                "rescue_difficulty": 0.5,
                "success_probability": 0.7,
                "resource_requirements": {},
            }
            scenes.append(scene)
        
        # 调用算法
        arbitrator = SceneArbitrator()
        result = arbitrator.run({"scenes": scenes})
        
        if result.status.value == "success" and result.solution:
            return _parse_arbitration_result(result.solution)
        else:
            raise Exception(f"仲裁算法失败: {result.status}")
            
    except ImportError:
        logger.warning("SceneArbitrator不可用，使用简单排序")
        return _simple_priority_sort(main_event, related_events)
    except Exception as e:
        logger.warning(f"仲裁算法异常: {e}，使用简单排序")
        return _simple_priority_sort(main_event, related_events)


def _parse_arbitration_result(
    solution: Any,
) -> tuple[List[ScenePriorityState], List[Dict[str, Any]]]:
    """解析仲裁算法结果"""
    priorities: List[ScenePriorityState] = []
    conflicts: List[Dict[str, Any]] = []
    
    if isinstance(solution, list):
        for idx, item in enumerate(solution):
            if hasattr(item, "scene_id"):
                priority: ScenePriorityState = {
                    "scene_id": item.scene_id,
                    "scene_name": item.scene_name,
                    "priority_score": item.priority_score,
                    "rank": item.rank,
                    "dimension_scores": item.dimension_scores,
                }
                priorities.append(priority)
    
    return priorities, conflicts


def _simple_priority_sort(
    main_event: Dict[str, Any],
    related_events: List[Dict[str, Any]],
) -> tuple[List[ScenePriorityState], List[Dict[str, Any]]]:
    """简单优先级排序（备用方案）"""
    priorities: List[ScenePriorityState] = []
    
    # 主事件优先
    priorities.append(_create_default_priority(main_event))
    
    # 次生事件
    for idx, event in enumerate(related_events):
        priority = _create_default_priority(event)
        priority["rank"] = idx + 2
        priority["priority_score"] *= 0.8  # 次生事件降权
        priorities.append(priority)
    
    # 按分数排序
    priorities.sort(key=lambda p: p["priority_score"], reverse=True)
    for idx, p in enumerate(priorities):
        p["rank"] = idx + 1
    
    return priorities, []
