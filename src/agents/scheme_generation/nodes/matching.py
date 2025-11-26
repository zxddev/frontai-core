"""
资源匹配节点

调用RescueTeamSelector和CapabilityMatcher进行资源匹配
支持熔断机制防止算法超时拖垮系统
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import uuid4

from ..state import (
    SchemeGenerationState,
    ResourceCandidateState,
    ResourceAllocationState,
)
from ..utils import track_node_time
from src.agents.utils.circuit_breaker import (
    get_circuit_breaker,
    CircuitBreakerOpen,
    CircuitBreakerTimeout,
)

logger = logging.getLogger(__name__)

# 资源匹配熔断器配置
_matcher_breaker = get_circuit_breaker(
    name="rescue_team_selector",
    failure_threshold=3,
    recovery_timeout=60.0,
    timeout=30.0,
)

# 默认资源匹配权重（可通过state.optimization_weights覆盖）
DEFAULT_WEIGHTS = {
    "capability_match": 0.35,
    "distance": 0.25,
    "availability": 0.20,
    "equipment": 0.10,
    "history": 0.10,
}


@track_node_time("match_resources")
def match_resources(state: SchemeGenerationState) -> Dict[str, Any]:
    """
    资源匹配节点
    
    根据能力需求匹配可用资源，计算匹配得分
    优先使用state中预查询的available_teams数据
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典，包含resource_candidates和resource_allocations
    """
    logger.info("开始执行资源匹配节点")
    
    capability_requirements = state.get("capability_requirements", [])
    event_analysis = state.get("event_analysis", {})
    constraints = state.get("constraints", {})
    optimization_weights = state.get("optimization_weights", {})
    available_teams = state.get("available_teams", [])  # 预查询的队伍数据
    trace = state.get("trace", {})
    errors = list(state.get("errors", []))
    
    # 合并权重
    weights = {**DEFAULT_WEIGHTS, **optimization_weights}
    
    # 获取事件位置
    location = event_analysis.get("location", {})
    event_lat = location.get("latitude", 0)
    event_lng = location.get("longitude", 0)
    
    # 获取灾害类型（用于差异化权重）
    disaster_type = event_analysis.get("disaster_type", "unknown")
    
    # 判断数据来源
    teams_source = "database" if available_teams else "mock"
    
    try:
        # 使用熔断器保护算法调用
        candidates, allocations = _matcher_breaker.call(
            _match_resources_with_algorithm,
            capability_requirements=capability_requirements,
            event_location=(event_lat, event_lng),
            disaster_type=disaster_type,
            constraints=constraints,
            weights=weights,
            event_analysis=event_analysis,
            available_teams=available_teams,
        )
        logger.info(f"RescueTeamSelector匹配完成: {len(candidates)}个候选, {len(allocations)}个分配, 数据来源={teams_source}")
        trace["algorithm_status"] = "success"
        trace["teams_source"] = teams_source
        trace["matcher_breaker_state"] = _matcher_breaker.state.value
        
    except CircuitBreakerOpen as e:
        logger.warning(f"资源匹配器熔断: {e}")
        errors.append(f"资源匹配器熔断: {e}")
        candidates, allocations = _generate_mock_resources(capability_requirements)
        trace["algorithm_status"] = "circuit_breaker_open"
        trace["teams_source"] = "mock"
        trace["matcher_breaker_state"] = "open"
        
    except CircuitBreakerTimeout as e:
        logger.warning(f"资源匹配器超时: {e}")
        errors.append(f"资源匹配器超时: {e}")
        candidates, allocations = _generate_mock_resources(capability_requirements)
        trace["algorithm_status"] = "timeout"
        trace["teams_source"] = "mock"
        trace["matcher_breaker_state"] = _matcher_breaker.state.value
        
    except Exception as e:
        logger.warning(f"RescueTeamSelector执行异常: {e}，使用模拟数据")
        errors.append(f"资源匹配算法异常: {e}")
        candidates, allocations = _generate_mock_resources(capability_requirements)
        trace["algorithm_status"] = "fallback"
        trace["teams_source"] = "mock"
    
    # 更新追踪信息
    trace["resource_candidates_count"] = len(candidates)
    trace["resource_allocations_count"] = len(allocations)
    trace.setdefault("algorithms_used", []).append("RescueTeamSelector")
    trace.setdefault("nodes_executed", []).append("match_resources")
    
    return {
        "resource_candidates": candidates,
        "resource_allocations": allocations,
        "trace": trace,
        "errors": errors,
    }


def _match_resources_with_algorithm(
    capability_requirements: List[Dict[str, Any]],
    event_location: tuple[float, float],
    disaster_type: str,
    constraints: Dict[str, Any],
    weights: Dict[str, float],
    event_analysis: Dict[str, Any] = None,
    available_teams: List[Dict[str, Any]] = None,
) -> tuple[List[ResourceCandidateState], List[ResourceAllocationState]]:
    """
    调用RescueTeamSelector进行资源匹配
    
    Args:
        capability_requirements: 能力需求列表
        event_location: 事件位置 (lat, lng)
        disaster_type: 灾害类型
        constraints: 约束条件
        weights: 优化权重
        event_analysis: 事件分析结果（用于提取特征）
        available_teams: 预查询的可用队伍（来自数据库），若为空则使用模拟数据
    """
    from src.planning.algorithms.matching import RescueTeamSelector
    
    event_analysis = event_analysis or {}
    assessment = event_analysis.get("assessment", {})
    
    # 1. 构造disaster_profile（按RescueTeamSelector期望格式）
    disaster_profile = {
        "type": disaster_type,
        "subtype": _infer_subtype(disaster_type, assessment),
        "level": assessment.get("disaster_level", "III"),
        "location": {"lat": event_location[0], "lng": event_location[1]},
        "features": {
            "has_collapse": assessment.get("collapse_area_sqm", 0) > 0,
            "has_trapped": assessment.get("has_trapped", False) or assessment.get("estimated_casualties", {}).get("trapped", 0) > 0,
            "has_fire": assessment.get("has_fire", False),
            "has_hazmat": assessment.get("has_leak", False) or disaster_type == "hazmat",
            "high_rise": assessment.get("building_height_m", 0) > 24,
            "water_area": disaster_type == "flood",
            "confined_space": assessment.get("confined_space", False),
            "night_time": event_analysis.get("is_night_operation", False),
        },
    }
    
    # 2. 获取可用队伍：优先使用预查询数据，否则使用模拟数据
    if available_teams:
        teams = available_teams
        logger.info(f"使用预查询队伍数据: {len(teams)}支队伍")
    else:
        teams = _get_available_teams(event_location, disaster_type)
        logger.info(f"使用模拟队伍数据: {len(teams)}支队伍")
    
    if not teams:
        raise Exception("无可用救援队伍")
    
    # 3. 构造算法输入
    problem = {
        "disaster_profile": disaster_profile,
        "available_teams": teams,
        "constraints": {
            "max_response_time": constraints.get("max_response_time_min", 60),
            "max_teams": constraints.get("max_teams", 10),
        },
    }
    
    logger.debug(f"RescueTeamSelector输入: disaster_type={disaster_type}, teams={len(teams)}")
    
    # 4. 执行算法
    selector = RescueTeamSelector()
    result = selector.run(problem)
    
    if result.status.value != "success":
        raise Exception(f"算法返回状态: {result.status.value}, 消息: {result.message}")
    
    if not result.solution:
        raise Exception("算法未返回有效解")
    
    # 5. 解析结果
    return _parse_algorithm_result(result.solution, capability_requirements, teams)


def _infer_subtype(disaster_type: str, assessment: Dict[str, Any]) -> str:
    """推断事件子类型"""
    if disaster_type == "earthquake":
        if assessment.get("collapse_area_sqm", 0) > 0:
            return "building_collapse"
        if assessment.get("has_trapped"):
            return "people_trapped"
    elif disaster_type == "fire":
        if assessment.get("building_height_m", 0) > 24:
            return "high_rise_fire"
        return assessment.get("fire_type", "structural_fire")
    elif disaster_type == "hazmat":
        return "chemical_leak"
    elif disaster_type == "flood":
        return assessment.get("flood_type", "urban_flood")
    return None


def _get_available_teams(
    event_location: tuple[float, float],
    disaster_type: str,
) -> List[Dict[str, Any]]:
    """
    获取可用救援队伍
    
    优先从数据库查询，无数据库时使用模拟数据
    """
    # TODO: 从数据库查询 rescue_teams_v2 表
    # 当前使用模拟数据
    
    base_lat, base_lng = event_location
    
    # 模拟队伍数据（覆盖常见能力）
    mock_teams = [
        {
            "id": "team-001",
            "name": "蓝天救援队",
            "type": "rescue_team",
            "capabilities": ["SEARCH_LIFE_DETECT", "RESCUE_STRUCTURAL", "RESCUE_CONFINED", "MEDICAL_FIRST_AID"],
            "specialty": "earthquake_rescue",
            "location": {"lat": base_lat + 0.02, "lng": base_lng + 0.01},
            "personnel": 25,
            "equipment_level": "advanced",
            "status": "available",
        },
        {
            "id": "team-002",
            "name": "市消防支队一中队",
            "type": "fire_team",
            "capabilities": ["FIRE_SUPPRESS", "FIRE_SUPPLY_WATER", "RESCUE_HIGH_ANGLE", "RESCUE_CONFINED"],
            "specialty": "firefighting",
            "location": {"lat": base_lat - 0.015, "lng": base_lng + 0.02},
            "personnel": 30,
            "equipment_level": "advanced",
            "status": "available",
        },
        {
            "id": "team-003",
            "name": "医疗急救队",
            "type": "medical_team",
            "capabilities": ["MEDICAL_TRIAGE", "MEDICAL_FIRST_AID", "MEDICAL_TRANSPORT"],
            "specialty": "emergency_medical",
            "location": {"lat": base_lat + 0.01, "lng": base_lng - 0.02},
            "personnel": 15,
            "equipment_level": "advanced",
            "status": "available",
        },
        {
            "id": "team-004",
            "name": "重型工程救援队",
            "type": "engineering_team",
            "capabilities": ["ENG_HEAVY_MACHINE", "ENG_DEMOLITION", "RESCUE_STRUCTURAL"],
            "specialty": "building_collapse",
            "location": {"lat": base_lat - 0.025, "lng": base_lng - 0.01},
            "personnel": 20,
            "equipment_level": "advanced",
            "status": "available",
        },
        {
            "id": "team-005",
            "name": "危化品处置队",
            "type": "hazmat_team",
            "capabilities": ["HAZMAT_DETECT", "HAZMAT_CONTAIN", "HAZMAT_DECON"],
            "specialty": "hazmat",
            "location": {"lat": base_lat + 0.03, "lng": base_lng + 0.025},
            "personnel": 12,
            "equipment_level": "advanced",
            "status": "available",
        },
        {
            "id": "team-006",
            "name": "水域救援队",
            "type": "water_rescue_team",
            "capabilities": ["RESCUE_WATER_FLOOD", "RESCUE_WATER_SWIFT"],
            "specialty": "water_rescue",
            "location": {"lat": base_lat - 0.02, "lng": base_lng + 0.03},
            "personnel": 18,
            "equipment_level": "standard",
            "status": "available",
        },
        {
            "id": "team-007",
            "name": "地震救援二队",
            "type": "rescue_team",
            "capabilities": ["SEARCH_LIFE_DETECT", "RESCUE_STRUCTURAL", "GEO_MONITOR"],
            "specialty": "search_rescue",
            "location": {"lat": base_lat + 0.015, "lng": base_lng - 0.015},
            "personnel": 22,
            "equipment_level": "standard",
            "status": "available",
        },
        {
            "id": "team-008",
            "name": "通信保障队",
            "type": "support_team",
            "capabilities": ["COMM_FIELD", "COMM_SATELLITE", "UAV_RECONNAISSANCE"],
            "specialty": "communication",
            "location": {"lat": base_lat - 0.01, "lng": base_lng - 0.025},
            "personnel": 10,
            "equipment_level": "advanced",
            "status": "available",
        },
    ]
    
    return mock_teams


def _parse_algorithm_result(
    solution: List[Dict[str, Any]],
    capability_requirements: List[Dict[str, Any]],
    available_teams: List[Dict[str, Any]],
) -> tuple[List[ResourceCandidateState], List[ResourceAllocationState]]:
    """
    解析RescueTeamSelector算法结果
    
    RescueTeamSelector返回格式:
    [
        {
            "team_id": "team-001",
            "team_name": "蓝天救援队",
            "score": 85.2,
            "eta_minutes": 15,
            "assigned_capabilities": ["SEARCH_LIFE_DETECT", "RESCUE_STRUCTURAL"],
            "priority_order": 1
        },
        ...
    ]
    """
    candidates: List[ResourceCandidateState] = []
    allocations: List[ResourceAllocationState] = []
    
    # 构建team_id到team_info的映射
    team_map = {t["id"]: t for t in available_teams}
    
    for item in solution:
        team_id = item.get("team_id", "")
        team_info = team_map.get(team_id, {})
        team_name = item.get("team_name", team_info.get("name", "未知队伍"))
        team_type = team_info.get("type", "rescue_team")
        team_caps = team_info.get("capabilities", item.get("assigned_capabilities", []))
        
        score = item.get("score", 0)
        eta = item.get("eta_minutes", 30)
        assigned_caps = item.get("assigned_capabilities", [])
        
        candidate: ResourceCandidateState = {
            "resource_id": team_id,
            "resource_name": team_name,
            "resource_type": team_type,
            "capabilities": team_caps,
            "match_score": score,
            "distance_km": eta * 0.5,  # 估算：1分钟约0.5km
            "eta_minutes": eta,
            "availability": 1.0,
            "score_breakdown": {
                "capability_match": score * 0.6,
                "distance": score * 0.2,
                "specialty": score * 0.2,
            },
        }
        candidates.append(candidate)
        
        allocation: ResourceAllocationState = {
            "resource_id": team_id,
            "resource_name": team_name,
            "resource_type": team_type,
            "assigned_task_types": [],
            "match_score": score,
            "recommendation_reason": _generate_recommendation_reason(
                team_name, score, assigned_caps, eta
            ),
            "alternatives": [],
            "capabilities": assigned_caps,  # 用于硬规则检查
        }
        allocations.append(allocation)
    
    logger.info(f"解析算法结果: {len(candidates)}支队伍, 覆盖能力{len(set(c for a in allocations for c in a.get('capabilities', [])))}")
    
    return candidates, allocations


def _generate_recommendation_reason(
    team_name: str,
    score: float,
    capabilities: List[str],
    eta_minutes: int = 0,
) -> str:
    """生成推荐理由"""
    cap_str = "、".join(capabilities[:3])
    if len(capabilities) > 3:
        cap_str += f"等{len(capabilities)}项能力"
    
    eta_str = f"，预计{eta_minutes}分钟到达" if eta_minutes > 0 else ""
    
    return f"{team_name}匹配得分{score:.1f}分，具备{cap_str}{eta_str}"


def _generate_mock_resources(
    capability_requirements: List[Dict[str, Any]],
) -> tuple[List[ResourceCandidateState], List[ResourceAllocationState]]:
    """
    生成模拟资源数据（算法不可用时的备用方案）
    
    注意：这不是降级，只是为了让流程可以继续执行以便测试
    """
    logger.warning("使用模拟资源数据（仅用于测试）")
    
    candidates: List[ResourceCandidateState] = []
    allocations: List[ResourceAllocationState] = []
    
    # 根据能力需求生成模拟资源
    resource_templates = {
        "SEARCH_LIFE_DETECT": ("蓝天救援队", "rescue_team"),
        "RESCUE_STRUCTURAL": ("地震救援队", "rescue_team"),
        "MEDICAL_TRIAGE": ("医疗急救队", "medical_team"),
        "FIRE_SUPPRESS": ("消防中队", "fire_team"),
        "HAZMAT_CONTAIN": ("危化品处置队", "hazmat_team"),
        "RESCUE_WATER_FLOOD": ("水域救援队", "water_rescue_team"),
    }
    
    used_ids = set()
    
    for req in capability_requirements:
        code = req["code"]
        template = resource_templates.get(code, ("应急救援队", "rescue_team"))
        
        resource_id = f"mock-{code.lower()}-{uuid4().hex[:8]}"
        if resource_id in used_ids:
            continue
        used_ids.add(resource_id)
        
        candidate: ResourceCandidateState = {
            "resource_id": resource_id,
            "resource_name": template[0],
            "resource_type": template[1],
            "capabilities": [code],
            "match_score": 85.0,
            "distance_km": 5.0,
            "eta_minutes": 15,
            "availability": 1.0,
            "score_breakdown": {
                "capability_match": 0.95,
                "distance": 0.80,
                "availability": 1.0,
            },
        }
        candidates.append(candidate)
        
        allocation: ResourceAllocationState = {
            "resource_id": resource_id,
            "resource_name": template[0],
            "resource_type": template[1],
            "assigned_task_types": [],
            "match_score": 85.0,
            "recommendation_reason": f"{template[0]}具备{code}能力，距离事件点5km，预计15分钟到达",
            "alternatives": [],
            "capabilities": [code],  # 添加能力字段用于过滤节点
        }
        allocations.append(allocation)
    
    return candidates, allocations
