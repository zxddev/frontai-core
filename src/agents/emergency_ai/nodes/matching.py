"""
阶段3: 资源匹配节点

从数据库查询真实救援队伍，根据事件坐标计算距离和响应时间，
按时间约束过滤并进行能力匹配。

改进：
- 基于队伍类型推断车辆速度和全地形能力
- 考虑道路系数计算真实行驶距离
- 支持危险区域避障（查询disaster_affected_areas_v2）
- 山区/复杂地形自动降速
- 整合人装物调度（IntegratedResourceSchedulingCore）
"""
from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.domains.resource_scheduling import (
    IntegratedResourceSchedulingCore,
    DisasterContext,
    IntegratedSchedulingRequest,
    CapabilityRequirement,
    SchedulingConstraints,
    PriorityLevel,
)
from src.domains.resource_scheduling.sphere_demand_calculator import SphereDemandCalculator
from src.domains.supplies.inventory_service import SupplyInventoryService
from src.infra.config.algorithm_config_service import AlgorithmConfigService
from src.planning.algorithms.arbitration import ConflictResolver, GRAConfigLoader
from src.planning.algorithms.arbitration.conflict_resolver import (
    Conflict, ConflictType, ResourceState, GRA_PRIORITY_MAP, GRA_DEFAULT_PRIORITY
)
from src.domains.disaster import (
    ResponsePhase,
    ClimateType,
    CasualtyEstimator,
    DisasterType as DisasterTypeEnum,
)
from src.domains.disaster.casualty_estimator import CasualtyEstimate
from ..state import (
    EmergencyAIState,
    ResourceCandidate,
    AllocationSolution,
    ResolvedRescuePoint,
    PointAllocation,
    TeamAllocation,
    MultiPointAllocationPlan,
)
from ..tools.routing_tools import (
    batch_calculate_team_etas,
    get_disaster_avoid_areas,
    get_danger_area_avoid_areas,
)
from src.infra.clients.amap import amap_geocode_async
from src.agents.schemas import RescuePointInput
from src.planning.algorithms.optimization.pymoo_optimizer import PymooOptimizer
from src.planning.algorithms.base import AlgorithmStatus

logger = logging.getLogger(__name__)

# 是否启用真实路径规划（可通过环境变量或配置控制）
ENABLE_REAL_ROUTING = True
# 路径规划最大并发数
ROUTING_MAX_CONCURRENT = 10


# ============================================================================
# 车辆参数配置（基于队伍类型推断）
# ============================================================================

@dataclass
class VehicleProfile:
    """车辆参数配置"""
    speed_kmh: float           # 正常道路速度(km/h)
    mountain_speed_kmh: float  # 山区道路速度(km/h)
    is_all_terrain: bool       # 是否全地形车辆
    road_factor: float         # 道路系数（直线距离→实际距离）


# 队伍类型→车辆参数映射
TEAM_VEHICLE_PROFILES: Dict[str, VehicleProfile] = {
    "fire_rescue": VehicleProfile(
        speed_kmh=60.0,           # 消防车在城市道路
        mountain_speed_kmh=35.0,  # 山区道路降速
        is_all_terrain=True,      # 消防车通常有越野能力
        road_factor=1.3,          # 城市道路系数
    ),
    "medical": VehicleProfile(
        speed_kmh=70.0,           # 救护车速度较快
        mountain_speed_kmh=40.0,
        is_all_terrain=False,     # 标准救护车非全地形
        road_factor=1.25,
    ),
    "search_rescue": VehicleProfile(
        speed_kmh=50.0,           # 搜救车辆中等速度
        mountain_speed_kmh=30.0,
        is_all_terrain=True,
        road_factor=1.4,
    ),
    "hazmat": VehicleProfile(
        speed_kmh=55.0,           # 危化品车辆谨慎驾驶
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.35,
    ),
    "engineering": VehicleProfile(
        speed_kmh=45.0,           # 工程车辆速度较慢
        mountain_speed_kmh=25.0,
        is_all_terrain=True,      # 工程车辆通常能越野
        road_factor=1.4,
    ),
    "water_rescue": VehicleProfile(
        speed_kmh=50.0,           # 带冲锋舟运输车
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.35,
    ),
    "communication": VehicleProfile(
        speed_kmh=60.0,           # 通信保障车
        mountain_speed_kmh=35.0,
        is_all_terrain=False,
        road_factor=1.3,
    ),
    "mine_rescue": VehicleProfile(
        speed_kmh=50.0,           # 矿山救护车
        mountain_speed_kmh=28.0,
        is_all_terrain=True,
        road_factor=1.45,
    ),
    "armed_police": VehicleProfile(
        speed_kmh=70.0,           # 武警车辆较快
        mountain_speed_kmh=40.0,
        is_all_terrain=True,
        road_factor=1.25,
    ),
    "volunteer": VehicleProfile(
        speed_kmh=50.0,           # 志愿者车辆（普通车）
        mountain_speed_kmh=30.0,
        is_all_terrain=False,
        road_factor=1.4,
    ),
    "command": VehicleProfile(
        speed_kmh=65.0,           # 指挥车辆
        mountain_speed_kmh=35.0,
        is_all_terrain=False,
        road_factor=1.3,
    ),
}

# 默认车辆参数
DEFAULT_VEHICLE_PROFILE = VehicleProfile(
    speed_kmh=40.0,
    mountain_speed_kmh=25.0,
    is_all_terrain=False,
    road_factor=1.4,
)

# 地形类型配置
TERRAIN_SPEED_FACTORS: Dict[str, float] = {
    "urban": 1.0,       # 城市道路正常
    "suburban": 0.9,    # 郊区略慢
    "rural": 0.8,       # 乡村道路
    "mountain": 0.5,    # 山区大幅降速
    "highway": 1.2,     # 高速公路加速
}


# ============================================================================
# 原有配置
# ============================================================================

# 默认最大搜索距离（km）
DEFAULT_MAX_DISTANCE_KM: float = 100.0

# 扩大搜索范围的步长（km）
DISTANCE_EXPAND_STEP_KM: float = 50.0

# 最大搜索距离上限（km）
MAX_SEARCH_DISTANCE_KM: float = 300.0

# 默认队伍查询上限（支持大规模救援场景）
DEFAULT_MAX_TEAMS: int = 200

# 灾害等级对应的队伍数量上限
DISASTER_SCALE_LIMITS: Dict[str, int] = {
    "small": 50,      # 小型灾害（社区级）
    "medium": 100,    # 中型灾害（区县级）
    "large": 200,     # 大型灾害（城市级）
    "catastrophic": 500,  # 特大灾害（地震级）
}


# ============================================================================
# 能力缺口协调建议（指挥员应急协调用）
# 能力代码严格对应 capability_codes_v2 数据库表
# ============================================================================

CAPABILITY_COORDINATION_ADVICE: Dict[str, Dict[str, str]] = {
    # 搜索类 (search)
    "SEARCH_LIFE_DETECT": {
        "name": "生命探测",
        "agency": "消防救援支队特勤站、USAR城市搜救队",
        "hotline": "119",
    },
    "SEARCH_THERMAL": {
        "name": "热成像搜索",
        "agency": "消防救援支队特勤站",
        "hotline": "119",
    },
    "SEARCH_CANINE": {
        "name": "搜救犬搜索",
        "agency": "消防救援支队搜救犬分队、公安警犬基地",
        "hotline": "119/110",
    },
    "SEARCH_SONAR": {
        "name": "声纳探测",
        "agency": "海事局、专业潜水救援队",
        "hotline": "12395（海上搜救）",
    },
    # 救援类 (rescue)
    "RESCUE_STRUCTURAL": {
        "name": "建筑物救援",
        "agency": "消防救援支队、USAR城市搜救队",
        "hotline": "119",
    },
    "RESCUE_CONFINED": {
        "name": "狭小空间救援",
        "agency": "消防特勤站、矿山救援队",
        "hotline": "119/12350",
    },
    "RESCUE_TRENCH": {
        "name": "沟渠救援",
        "agency": "消防特勤站、市政工程应急队",
        "hotline": "119",
    },
    "RESCUE_ROPE": {
        "name": "绳索救援",
        "agency": "消防特勤站、山地救援队",
        "hotline": "119",
    },
    "RESCUE_WATER_SWIFT": {
        "name": "急流水域救援",
        "agency": "水上救援队、消防特勤站",
        "hotline": "119",
    },
    "RESCUE_WATER_FLOOD": {
        "name": "洪水救援",
        "agency": "消防救援支队、武警部队、民兵预备役",
        "hotline": "119/市防汛指挥部",
    },
    "RESCUE_VEHICLE": {
        "name": "车辆救援",
        "agency": "消防救援支队、交通事故救援队",
        "hotline": "119/122",
    },
    # 医疗类 (medical)
    "MEDICAL_TRIAGE": {
        "name": "伤员分诊",
        "agency": "市级医院急救中心、红十字会急救队",
        "hotline": "120",
    },
    "MEDICAL_FIRST_AID": {
        "name": "现场急救",
        "agency": "市级医院急救中心、红十字会急救队",
        "hotline": "120/999",
    },
    "MEDICAL_TRAUMA": {
        "name": "创伤处理",
        "agency": "市级三甲医院创伤中心",
        "hotline": "120",
    },
    "MEDICAL_CPR": {
        "name": "心肺复苏",
        "agency": "急救中心、红十字会",
        "hotline": "120",
    },
    "MEDICAL_TRANSPORT": {
        "name": "伤员转运",
        "agency": "急救中心、医院救护车队",
        "hotline": "120",
    },
    # 危化品类 (hazmat)
    "HAZMAT_DETECT": {
        "name": "危化品检测",
        "agency": "环境监测站、危化品检测机构",
        "hotline": "12369",
    },
    "HAZMAT_CONTAIN": {
        "name": "泄漏控制",
        "agency": "危化品应急救援中心、消防特勤站",
        "hotline": "119/12119",
    },
    "HAZMAT_DECON": {
        "name": "洗消",
        "agency": "环保部门、专业洗消队伍、疾控中心",
        "hotline": "12369（环保投诉热线）",
    },
    "HAZMAT_FIRE": {
        "name": "化学火灾扑救",
        "agency": "消防特勤站、危化品专职消防队",
        "hotline": "119",
    },
    # 消防类 (fire)
    "FIRE_SUPPRESS": {
        "name": "火灾扑救",
        "agency": "消防救援支队、企业专职消防队",
        "hotline": "119",
    },
    "FIRE_FOREST": {
        "name": "森林灭火",
        "agency": "森林消防队、航空护林站",
        "hotline": "119/12119",
    },
    "FIRE_HIGH_RISE": {
        "name": "高层灭火",
        "agency": "消防救援支队、云梯车中队",
        "hotline": "119",
    },
    # 工程类 (engineering)
    "ENG_SHORING": {
        "name": "支撑加固",
        "agency": "建工集团、消防救援支队",
        "hotline": "119/市应急局调度热线",
    },
    "ENG_DEMOLITION": {
        "name": "破拆清障",
        "agency": "消防救援支队、武警交通部队",
        "hotline": "119",
    },
    "ENG_LIFTING": {
        "name": "重物起吊",
        "agency": "建工集团、大型吊装公司",
        "hotline": "市应急局调度热线",
    },
    # 保障类 (logistics)
    "LOG_POWER": {
        "name": "电力保障",
        "agency": "供电公司应急抢修队",
        "hotline": "95598",
    },
    "LOG_LIGHTING": {
        "name": "照明保障",
        "agency": "消防救援支队、供电公司",
        "hotline": "119/95598",
    },
    "LOG_COMM": {
        "name": "通信保障",
        "agency": "无线电管理局、通信管理局",
        "hotline": "市应急通信保障热线",
    },
    "LOG_SHELTER": {
        "name": "安置保障",
        "agency": "民政局、红十字会",
        "hotline": "12345/市民政局",
    },
    "LOG_SUPPLY": {
        "name": "物资保障",
        "agency": "应急物资储备中心、红十字会",
        "hotline": "市应急局物资调度",
    },
}


def _get_capability_name(cap_code: str) -> str:
    """获取能力代码对应的中文名称"""
    if cap_code in CAPABILITY_COORDINATION_ADVICE:
        return CAPABILITY_COORDINATION_ADVICE[cap_code]["name"]
    return cap_code


def _generate_coordination_advice(missing_caps: set) -> str:
    """
    根据缺失能力生成协调建议
    
    Args:
        missing_caps: 缺失的能力代码集合
        
    Returns:
        格式化的协调建议文本
    """
    advices = []
    for cap_code in missing_caps:
        info = CAPABILITY_COORDINATION_ADVICE.get(cap_code)
        if info:
            advices.append(
                f"  【{info['name']}】\n"
                f"    ↳ 建议联络: {info['agency']}\n"
                f"    ↳ 参考热线: {info['hotline']}"
            )
        else:
            advices.append(
                f"  【{cap_code}】\n"
                f"    ↳ 建议联络上级指挥部协调外部资源"
            )
    return "\n".join(advices)


def _build_capability_gap_report(
    missing_caps: set,
    search_distance_km: float,
    event_location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    构建结构化的能力缺口报告
    
    Args:
        missing_caps: 缺失的能力代码集合
        search_distance_km: 搜索半径（km）
        event_location: 事件位置描述
        
    Returns:
        能力缺口报告字典
    """
    if not missing_caps:
        return {
            "has_gap": False,
            "message": "所有需求能力均有队伍可覆盖",
        }
    
    severity = "critical" if len(missing_caps) > 2 else "warning"
    
    cap_details = []
    for cap_code in missing_caps:
        info = CAPABILITY_COORDINATION_ADVICE.get(cap_code, {})
        cap_details.append({
            "capability_code": cap_code,
            "capability_name": info.get("name", cap_code),
            "suggested_agency": info.get("agency", "上级指挥部"),
            "hotline": info.get("hotline", "N/A"),
        })
    
    coordination_advice = _generate_coordination_advice(missing_caps)
    
    # 构建可读的告警消息
    cap_names = [_get_capability_name(c) for c in missing_caps]
    message = (
        f"⚠️ 【能力缺口告警】系统内 {search_distance_km}km 范围内缺少以下救援能力，"
        f"请指挥员紧急协调外部资源：\n\n"
        f"缺失能力：{', '.join(cap_names)}\n\n"
        f"协调建议：\n{coordination_advice}"
    )
    
    return {
        "has_gap": True,
        "severity": severity,  # "warning" | "critical"
        "missing_capabilities": list(missing_caps),
        "capability_details": cap_details,
        "search_radius_km": search_distance_km,
        "event_location": event_location,
        "coordination_advice": coordination_advice,
        "message": message,
    }


async def match_resources(state: EmergencyAIState) -> Dict[str, Any]:
    """
    资源匹配节点：从数据库查询真实队伍并匹配

    根据事件坐标从rescue_teams_v2表查询可用队伍，
    计算距离和响应时间，按能力需求进行匹配评分。

    Args:
        state: 当前状态，必须包含structured_input.location

    Returns:
        更新的状态字段，包含resource_candidates

    Raises:
        ValueError: structured_input.location缺失或无效
    """
    logger.info(f"[资源匹配] 开始执行，event_id={state['event_id']}")
    start_time = time.time()

    errors: List[str] = list(state.get("errors", []))
    trace: Dict[str, Any] = dict(state.get("trace", {}))

    # 获取事件坐标（必须从structured_input获取）
    event_location = _extract_event_location(state)
    if event_location is None:
        error_msg = "structured_input.location缺失或无效，必须提供事件坐标(longitude/latitude)"
        logger.error(f"[资源匹配] {error_msg}")
        errors.append(error_msg)
        return {
            "resource_candidates": [],
            "errors": errors,
            "trace": trace,
        }

    event_lat, event_lng = event_location
    logger.info(f"[资源匹配] 事件坐标: lat={event_lat}, lng={event_lng}")

    # 获取能力需求（合并规则推理和任务需求）
    capability_requirements = state.get("capability_requirements", [])
    task_sequence = state.get("task_sequence", [])
    
    # 从规则推理获取能力
    rule_caps = {cap["capability_code"] for cap in capability_requirements}
    
    # 从任务序列获取能力（确保包含所有任务需要的能力）
    task_caps = set()
    for task in task_sequence:
        task_caps.update(task.get("required_capabilities", []))
    
    # 合并两个来源的能力需求
    required_caps = rule_caps | task_caps
    
    if not required_caps:
        logger.warning("[资源匹配] 无能力需求，仅执行多点位分配")
        # 即使没有能力需求，也执行多点位分配
        rescue_points_input = state.get("structured_input", {}).get("rescue_points", [])
        resolved_rescue_points: List[ResolvedRescuePoint] = []
        point_candidates: Dict[str, List[ResourceCandidate]] = {}
        point_allocations = None
        
        if rescue_points_input:
            try:
                logger.info(f"[资源匹配] 检测到{len(rescue_points_input)}个救援点输入，启动多点位分配")
                input_points = [
                    RescuePointInput(**p) if isinstance(p, dict) else p 
                    for p in rescue_points_input
                ]
                multi_result = await match_resources_multi_point(state, input_points)
                resolved_rescue_points = multi_result.get("resolved_rescue_points", [])
                point_candidates = multi_result.get("point_candidates", {})
                state["resolved_rescue_points"] = resolved_rescue_points
                state["point_candidates"] = point_candidates
                point_allocations = optimize_multi_point_allocation(state)
                logger.info(f"[资源匹配] 多点位分配完成: {point_allocations['total_rescue_points']}个救援点")
            except Exception as e:
                logger.error(f"[资源匹配] 多点位分配失败: {e}")
        
        return {
            "resource_candidates": [],
            "resolved_rescue_points": resolved_rescue_points,
            "point_candidates": point_candidates,
            "point_allocations": point_allocations,
            "trace": trace,
        }

    logger.info(f"[资源匹配] 需要的能力({len(required_caps)}种): 规则{len(rule_caps)}种 + 任务{len(task_caps)}种 = {required_caps}")

    # 获取约束条件
    constraints = state.get("constraints", {})
    
    # 获取灾害等级和队伍数量上限
    disaster_scale = _determine_disaster_scale(state)
    max_teams = constraints.get("max_teams", DISASTER_SCALE_LIMITS.get(disaster_scale, DEFAULT_MAX_TEAMS))
    logger.info(f"[资源匹配] 灾害等级: {disaster_scale}，队伍上限: {max_teams}")

    # 获取时间约束，使用默认车辆速度计算初始搜索距离
    max_response_hours: float = constraints.get("max_response_time_hours", 2.0)
    initial_max_distance: float = max_response_hours * DEFAULT_VEHICLE_PROFILE.speed_kmh
    logger.info(f"[资源匹配] 时间约束: {max_response_hours}小时，初始搜索距离: {initial_max_distance}km（默认速度{DEFAULT_VEHICLE_PROFILE.speed_kmh}km/h）")

    # 从数据库查询队伍
    teams: List[Dict[str, Any]] = []
    search_distance = initial_max_distance
    search_expanded = False

    async with AsyncSessionLocal() as db:
        # 第一次查询：按时间约束范围
        teams = await _query_teams_from_db(
            db=db,
            event_lat=event_lat,
            event_lng=event_lng,
            max_distance_km=search_distance,
            max_teams=max_teams,
        )
        logger.info(f"[资源匹配] 初始查询: 距离<={search_distance}km, 上限{max_teams}支, 找到{len(teams)}支队伍")

        # 检查能力覆盖
        covered_caps = _get_covered_capabilities(teams)
        missing_caps = required_caps - covered_caps

        # 如果能力覆盖不足，扩大搜索范围
        while missing_caps and search_distance < MAX_SEARCH_DISTANCE_KM:
            search_distance += DISTANCE_EXPAND_STEP_KM
            search_expanded = True
            logger.warning(
                f"[资源匹配] 能力覆盖不足，缺失: {missing_caps}，扩大搜索范围至{search_distance}km"
            )

            teams = await _query_teams_from_db(
                db=db,
                event_lat=event_lat,
                event_lng=event_lng,
                max_distance_km=search_distance,
                max_teams=max_teams,
            )
            covered_caps = _get_covered_capabilities(teams)
            missing_caps = required_caps - covered_caps

    if not teams:
        error_msg = f"在{search_distance}km范围内未找到任何可用队伍"
        logger.error(f"[资源匹配] {error_msg}")
        errors.append(error_msg)
        return {
            "resource_candidates": [],
            "errors": errors,
            "trace": trace,
        }

    # 记录搜索范围扩大的情况
    if search_expanded:
        expand_msg = f"搜索范围从{initial_max_distance}km扩大至{search_distance}km以覆盖所需能力"
        logger.warning(f"[资源匹配] {expand_msg}")
        trace["search_expanded"] = True
        trace["initial_distance_km"] = initial_max_distance
        trace["final_distance_km"] = search_distance

    # 检查最终能力覆盖，并生成能力缺口报告
    event_loc_desc = state.get("structured_input", {}).get("location", {}).get("address")
    capability_gap_report = _build_capability_gap_report(
        missing_caps=missing_caps,
        search_distance_km=search_distance,
        event_location=event_loc_desc,
    )
    
    if missing_caps:
        missing_msg = f"以下能力在{search_distance}km范围内无队伍具备: {missing_caps}"
        logger.warning(f"[资源匹配] {missing_msg}")
        errors.append(missing_msg)
        trace["missing_capabilities"] = list(missing_caps)
        # 严重告警日志（指挥员必须看到）
        logger.warning(f"[能力缺口告警] {capability_gap_report['message']}")

    # 获取道路损坏信息用于动态调整ETA
    parsed_disaster_for_road = state.get("parsed_disaster", {})
    has_road_damage: bool = parsed_disaster_for_road.get("has_road_damage", False) if parsed_disaster_for_road else False

    # 从数据库获取道路系数参数（缺失则报错，无Fallback）
    async with AsyncSessionLocal() as config_db:
        config_service = AlgorithmConfigService(config_db)
        base_road_config = await config_service.get_or_raise("emergency_ai", "BASE_ROAD_FACTOR")
        damaged_road_config = await config_service.get_or_raise("emergency_ai", "DAMAGED_ROAD_FACTOR")
    
    base_road_factor: float = float(base_road_config["value"])
    damaged_road_factor: float = float(damaged_road_config["value"])
    logger.info(f"[资源匹配] 道路系数配置: base={base_road_factor}, damaged={damaged_road_factor}")

    # 计算匹配分数
    candidates = _calculate_match_scores(
        teams=teams,
        required_capabilities=required_caps,
        event_lat=event_lat,
        event_lng=event_lng,
        max_response_hours=max_response_hours,
        has_road_damage=has_road_damage,
        base_road_factor=base_road_factor,
        damaged_road_factor=damaged_road_factor,
    )

    # ========================================================================
    # 真实路径规划：更新 ETA（考虑避障）
    # ========================================================================
    if ENABLE_REAL_ROUTING and candidates:
        routing_start = time.time()
        try:
            # 先查询避让区域（使用独立会话）
            avoid_areas = []
            scenario_uuid = None
            scenario_id_raw = state.get("scenario_id")
            
            async with AsyncSessionLocal() as area_db:
                if scenario_id_raw:
                    try:
                        scenario_uuid = UUID(str(scenario_id_raw))
                        disaster_areas = await get_disaster_avoid_areas(area_db, scenario_uuid)
                        avoid_areas.extend(disaster_areas)
                    except (ValueError, TypeError):
                        pass
                
                # 获取前端绘制的危险区域
                danger_areas = await get_danger_area_avoid_areas(area_db)
                avoid_areas.extend(danger_areas)
            
            if avoid_areas:
                logger.info(f"[路径规划] 加载 {len(avoid_areas)} 个避让区域")
            
            # 批量计算真实 ETA（每个子任务会创建独立的数据库会话）
            eta_results = await batch_calculate_team_etas(
                teams=teams,
                event_lat=event_lat,
                event_lng=event_lng,
                scenario_id=scenario_uuid,
                avoid_areas=avoid_areas if avoid_areas else None,
                max_concurrent=ROUTING_MAX_CONCURRENT,
            )
            # 更新候选列表的 ETA
            routing_success = 0
            routing_fallback = 0
            for candidate in candidates:
                team_id = candidate.get("resource_id")
                if team_id and team_id in eta_results:
                    eta_result = eta_results[team_id]
                    candidate["response_time_minutes"] = eta_result.response_time_minutes
                    candidate["travel_time_minutes"] = eta_result.travel_time_minutes
                    candidate["eta_minutes"] = eta_result.eta_minutes
                    candidate["route_distance_km"] = eta_result.route_distance_km
                    candidate["route_source"] = eta_result.route_source
                    if eta_result.route_source != "estimate":
                        routing_success += 1
                    else:
                        routing_fallback += 1
            
            routing_elapsed = int((time.time() - routing_start) * 1000)
            logger.info(
                f"[路径规划] 批量 ETA 更新完成: 成功={routing_success}, "
                f"估算={routing_fallback}, 避让区域={len(avoid_areas)}, 耗时={routing_elapsed}ms"
            )
            trace["real_routing"] = {
                "enabled": True,
                "success_count": routing_success,
                "fallback_count": routing_fallback,
                "avoid_areas_count": len(avoid_areas),
                "elapsed_ms": routing_elapsed,
            }
        except Exception as e:
            logger.warning(f"[路径规划] 批量 ETA 计算失败，保留估算值: {e}")
            trace["real_routing"] = {"enabled": True, "error": str(e)}

    # 按匹配分数排序
    candidates.sort(key=lambda x: x["match_score"], reverse=True)

    # ========================================================================
    # 整合调度：装备调度 + 物资需求计算 + 前线库存缺口分析
    # ========================================================================
    equipment_allocations: List[Dict[str, Any]] = []
    supply_requirements: List[Dict[str, Any]] = []
    supply_shortages: List[Dict[str, Any]] = []
    
    # 获取灾情信息
    parsed_disaster = state.get("parsed_disaster", {})
    disaster_type = parsed_disaster.get("disaster_type", "earthquake") if parsed_disaster else "earthquake"
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0) if parsed_disaster else 0
    affected_population = parsed_disaster.get("affected_population", 0) if parsed_disaster else 0
    # 不再使用猜测逻辑（被困人数*5），只使用用户提供或物理模型计算的数据
    
    try:
        async with AsyncSessionLocal() as db:
            integrated_core = IntegratedResourceSchedulingCore(db)
            
            # 1. 装备调度（基于能力需求）
            capability_codes = list(required_caps)
            if capability_codes:
                logger.info(f"[资源匹配] 开始装备调度，能力需求: {capability_codes}")
                equipment_result = await integrated_core.schedule_equipment(
                    capability_codes=capability_codes,
                    destination_lon=event_lng,
                    destination_lat=event_lat,
                    max_distance_km=search_distance,
                )
                
                # 总是添加已分配的装备（即使未满足所有必须需求）
                for alloc in equipment_result.allocations:
                    equipment_allocations.append({
                        "equipment_id": str(alloc.equipment_id),
                        "equipment_code": alloc.equipment_code,
                        "equipment_name": alloc.equipment_name,
                        "equipment_type": alloc.equipment_type.value,
                        "source_name": alloc.source_name,
                        "allocated_quantity": alloc.allocated_quantity,
                        "for_capability": alloc.for_capability,
                        "distance_km": alloc.distance_km,
                    })
                logger.info(
                    f"[资源匹配] 装备调度完成: {len(equipment_allocations)}件装备，"
                    f"必须满足{equipment_result.required_met}/{equipment_result.required_total}"
                )
                if not equipment_result.success:
                    logger.warning(f"[资源匹配] 装备调度未能满足所有必须需求: {equipment_result.warnings}")
                
                trace["equipment_scheduling"] = {
                    "success": equipment_result.success,
                    "required_met": equipment_result.required_met,
                    "required_total": equipment_result.required_total,
                    "total_count": equipment_result.total_equipment_count,
                    "elapsed_ms": equipment_result.elapsed_ms,
                }
            
            # 2. 物资需求计算 - 使用SphereDemandCalculator
            if affected_population > 0:
                logger.info(f"[资源匹配] 开始物资需求计算(Sphere): 灾害类型={disaster_type}, 受灾人数={affected_population}")
                
                # 构造伤亡估算
                estimator = CasualtyEstimator()
                severity = parsed_disaster.get("severity", "medium") if parsed_disaster else "medium"
                severity_score = {"critical": 0.9, "high": 0.7, "medium": 0.5, "low": 0.3}.get(severity, 0.5)
                
                try:
                    dt = DisasterTypeEnum(disaster_type)
                except ValueError:
                    dt = DisasterTypeEnum.EARTHQUAKE
                
                casualty = estimator.estimate_generic(
                    disaster_type=dt,
                    severity=severity_score,
                    population=affected_population,
                )
                
                # 打印伤亡估算结果
                logger.info(f"【伤亡估算-输入】灾害类型={disaster_type}, 严重程度={severity}({severity_score}), 受灾人口={affected_population}")
                logger.info(f"【伤亡估算-输出】死亡={casualty.fatalities}, 重伤={casualty.severe_injuries}, 轻伤={casualty.minor_injuries}, 被困={casualty.trapped}")
                
                # 如果有明确被困人数，覆盖估算值
                if estimated_trapped > 0:
                    logger.info(f"【伤亡估算-覆盖】使用实际被困人数{estimated_trapped}覆盖估算值{casualty.trapped}")
                    casualty = CasualtyEstimate(
                        fatalities=casualty.fatalities,
                        severe_injuries=casualty.severe_injuries,
                        minor_injuries=casualty.minor_injuries,
                        trapped=estimated_trapped,
                        displaced=casualty.displaced,
                        affected=affected_population,
                        confidence=casualty.confidence,
                        methodology=casualty.methodology,
                    )
                
                config_service = AlgorithmConfigService(db)
                sphere_calculator = SphereDemandCalculator(db, config_service)
                supply_result = await sphere_calculator.calculate(
                    phase=ResponsePhase.IMMEDIATE,
                    casualty_estimate=casualty,
                    duration_days=3,
                    climate=ClimateType.TEMPERATE,
                )
                
                for req in supply_result.requirements:
                    supply_requirements.append({
                        "supply_code": req.supply_code,
                        "supply_name": req.supply_name,
                        "category": req.category,
                        "quantity": req.quantity,
                        "unit": req.unit,
                        "priority": req.priority,
                    })
                
                logger.info(
                    f"[资源匹配] 物资需求计算完成(Sphere): {len(supply_requirements)}种物资，"
                    f"耗时={supply_result.elapsed_ms}ms"
                )
                
                trace["supply_calculation"] = {
                    "disaster_type": disaster_type,
                    "affected_count": affected_population,
                    "duration_days": 3,
                    "supply_types": len(supply_requirements),
                    "source": "SphereDemandCalculator",
                    "elapsed_ms": supply_result.elapsed_ms,
                }
            else:
                logger.info("[资源匹配] 跳过伤亡估算和物资需求计算：缺少受灾人口数据")
            
            # 3. 查询前线可用库存并计算缺口
            scenario_id_raw = state.get("scenario_id")
            scenario_uuid: Optional[UUID] = None
            
            # 验证并转换scenario_id为UUID
            if scenario_id_raw and supply_requirements:
                scenario_uuid = await _resolve_scenario_id(db, scenario_id_raw)
                if scenario_uuid is None:
                    logger.warning(
                        f"[资源匹配] scenario_id '{scenario_id_raw}' 无法解析为有效UUID，跳过库存查询"
                    )
            
            if scenario_uuid and supply_requirements:
                logger.info(f"[资源匹配] 查询前线可用库存，scenario_id={scenario_uuid}")
                inventory_service = SupplyInventoryService(db)
                
                # 查询前线所有depot的库存（field_depot/vehicle/team_base）
                field_inventory = await inventory_service.get_field_available_supplies(
                    scenario_id=scenario_uuid
                )
                
                # 计算缺口
                supply_shortages = await inventory_service.calculate_shortage(
                    requirements=supply_requirements,
                    available=field_inventory,
                )
                
                logger.info(
                    f"[资源匹配] 前线库存查询完成: {len(field_inventory)}条库存，"
                    f"{len(supply_shortages)}种物资存在缺口"
                )
                
                trace["field_inventory"] = {
                    "scenario_id": str(scenario_uuid),
                    "inventory_count": len(field_inventory),
                    "shortage_count": len(supply_shortages),
                }
                
                # 将缺口信息添加到返回值
                if supply_shortages:
                    for shortage in supply_shortages:
                        # 标记需要从后方调拨的物资
                        shortage["needs_transfer"] = True
                        shortage["transfer_suggestion"] = (
                            f"前线缺口{shortage['shortage']}，建议从后方仓库调拨"
                        )
    except Exception as e:
        logger.error(f"[资源匹配] 综合调度异常: {e}")
        errors.append(f"综合调度异常: {e}")

    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_resources"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["database_query", "capability_matching", "integrated_scheduling"]
    trace["teams_queried"] = len(teams)
    trace["candidates_count"] = len(candidates)
    trace["equipment_count"] = len(equipment_allocations)
    trace["supply_types_count"] = len(supply_requirements)
    trace["supply_shortages_count"] = len(supply_shortages)

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[资源匹配] 完成，查询{len(teams)}支队伍，生成{len(candidates)}个候选，"
        f"调度{len(equipment_allocations)}件装备，计算{len(supply_requirements)}种物资需求，"
        f"缺口{len(supply_shortages)}种，耗时{elapsed_ms}ms"
    )
    
    # ========== 多点位分配（如果有rescue_points输入） ==========
    # rescue_points从structured_input传入
    rescue_points_input = state.get("structured_input", {}).get("rescue_points", [])
    resolved_rescue_points: List[ResolvedRescuePoint] = []
    point_candidates: Dict[str, List[ResourceCandidate]] = {}
    point_allocations = None
    
    if rescue_points_input:
        try:
            logger.info(f"[资源匹配] 检测到{len(rescue_points_input)}个救援点输入，启动多点位分配")
            # 将dict转换为RescuePointInput
            input_points = [
                RescuePointInput(**p) if isinstance(p, dict) else p 
                for p in rescue_points_input
            ]
            
            # 多点匹配
            multi_result = await match_resources_multi_point(state, input_points)
            resolved_rescue_points = multi_result.get("resolved_rescue_points", [])
            point_candidates = multi_result.get("point_candidates", {})
            
            # 更新state用于优化
            state["resolved_rescue_points"] = resolved_rescue_points
            state["point_candidates"] = point_candidates
            
            # 多点优化分配
            point_allocations = optimize_multi_point_allocation(state)
            
            logger.info(
                f"[资源匹配] 多点位分配完成: {point_allocations['total_rescue_points']}个救援点，"
                f"{point_allocations['assigned_points']}个已分配"
            )
        except Exception as e:
            logger.error(f"[资源匹配] 多点位分配失败: {e}")
            errors.append(f"多点位分配失败: {e}")

    return {
        "resource_candidates": candidates,
        "equipment_allocations": equipment_allocations,
        "supply_requirements": supply_requirements,
        "supply_shortages": supply_shortages,
        "capability_gap_report": capability_gap_report,
        # 多点位分配结果
        "resolved_rescue_points": resolved_rescue_points,
        "point_candidates": point_candidates,
        "point_allocations": point_allocations,
        "trace": trace,
        "errors": errors,
        "current_phase": "matching",
    }


async def optimize_allocation(state: EmergencyAIState) -> Dict[str, Any]:
    """
    分配优化节点：基于候选资源生成多个分配方案

    使用NSGA-II多目标优化生成Pareto最优解集。
    如果候选资源较少（<=10），退化为贪心策略以提高效率。

    Args:
        state: 当前状态

    Returns:
        更新的状态字段，包含allocation_solutions和pareto_solutions
    """
    logger.info(f"[分配优化] 开始执行，event_id={state['event_id']}")
    start_time = time.time()

    candidates = state.get("resource_candidates", [])
    capability_requirements = state.get("capability_requirements", [])
    task_sequence = state.get("task_sequence", [])  # HTN分解后的任务序列
    constraints = state.get("constraints", {})
    trace: Dict[str, Any] = dict(state.get("trace", {}))
    errors: List[str] = list(state.get("errors", []))
    
    # 提取事件坐标（用于GRA仲裁）
    event_location = _extract_event_location(state)
    if event_location:
        event_lat, event_lng = event_location
    else:
        event_lat, event_lng = 0.0, 0.0
        logger.warning("[分配优化] 无法提取事件坐标，GRA仲裁可能受影响")
    
    # 合并能力需求：规则推理阶段 + 任务实际需求
    # 确保NSGA-II优化时考虑所有任务需要的能力
    rule_caps = {cap["capability_code"] for cap in capability_requirements}
    task_caps = set()
    for task in task_sequence:
        task_caps.update(task.get("required_capabilities", []))
    all_required_caps = rule_caps | task_caps
    
    # 如果任务需要的能力超出规则推理的范围，扩展capability_requirements
    missing_caps = task_caps - rule_caps
    if missing_caps:
        logger.info(f"[分配优化] 任务需要额外{len(missing_caps)}种能力: {missing_caps}")
        for cap_code in missing_caps:
            capability_requirements.append({
                "capability_code": cap_code,
                "capability_name": cap_code,  # 临时名称
                "source": "task_required",
            })
    
    # 获取被困人数用于计算救援容量需求
    parsed_disaster = state.get("parsed_disaster", {})
    estimated_trapped: int = parsed_disaster.get("estimated_trapped", 0) if parsed_disaster else 0
    logger.info(f"[分配优化] 被困人数: {estimated_trapped}")

    # 从数据库获取容量安全系数（缺失则报错，无Fallback）
    async with AsyncSessionLocal() as config_db:
        config_service = AlgorithmConfigService(config_db)
        capacity_config = await config_service.get_or_raise("emergency_ai", "CAPACITY_SAFETY_FACTOR")
    capacity_safety_factor: float = float(capacity_config["value"])
    logger.info(f"[分配优化] 容量安全系数: {capacity_safety_factor}")

    if not candidates:
        logger.warning("[分配优化] 无候选资源，无法生成方案")
        return {
            "allocation_solutions": [],
            "pareto_solutions": [],
            "trace": trace,
            "errors": errors,
        }

    # 获取生成方案数量
    n_alternatives = constraints.get("n_alternatives", 5)
    
    solutions: List[AllocationSolution] = []
    algorithm_used = "greedy"  # 默认贪心

    # 尝试使用NSGA-II（候选资源>10时效果更好）
    # 候选资源>10时使用NSGA-III多目标优化
    if len(candidates) > 10:
        nsga_solutions = _run_nsga2_optimization(
            candidates=candidates,
            capability_requirements=capability_requirements,
            task_sequence=task_sequence,
            n_solutions=n_alternatives,
            estimated_trapped=estimated_trapped,
            event_lat=event_lat,
            event_lng=event_lng,
        )
        if nsga_solutions:
            solutions = nsga_solutions
            algorithm_used = "NSGA-II"
            logger.info(f"[分配优化] NSGA-II生成{len(solutions)}个Pareto解")

    # 如果NSGA-II未生成方案，使用贪心策略
    if not solutions:
        # 方案1: 最高匹配分数优先
        solution1 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="match_score",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
            event_lat=event_lat,
            event_lng=event_lng,
        )
        if solution1:
            solutions.append(solution1)

        # 方案2: 最短响应时间优先（按距离排序）
        solution2 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="distance",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
            event_lat=event_lat,
            event_lng=event_lng,
        )
        if solution2:
            solutions.append(solution2)

        # 方案3: 最高可用性优先
        solution3 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="availability",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
            event_lat=event_lat,
            event_lng=event_lng,
        )
        if solution3:
            solutions.append(solution3)

        # 方案4: 最高救援容量优先（巨灾场景）
        solution4 = _generate_greedy_solution(
            candidates=candidates,
            capability_requirements=capability_requirements,
            strategy="capacity",
            solution_id=f"solution-{uuid.uuid4().hex[:8]}",
            estimated_trapped=estimated_trapped,
            capacity_safety_factor=capacity_safety_factor,
            event_lat=event_lat,
            event_lng=event_lng,
        )
        if solution4:
            solutions.append(solution4)

    # 为每个方案生成任务-资源分配序列
    if task_sequence and solutions:
        for solution in solutions:
            task_assignments, execution_path = _assign_tasks_to_resources(
                task_sequence=task_sequence,
                selected_resources=solution.get("allocations", []),
                capability_requirements=capability_requirements,
            )
            solution["task_assignments"] = task_assignments
            solution["execution_path"] = execution_path
            
            # 为每个队伍生成任务描述（基于task_assignments反向汇总）
            _enrich_allocations_with_task_descriptions(solution, task_assignments)
    else:
        # 无任务序列时，填充空值
        for solution in solutions:
            solution["task_assignments"] = []
            solution["execution_path"] = ""

    # Pareto最优解
    pareto_solutions = _deduplicate_solutions(solutions)[:n_alternatives]

    # =============================
    # GRA 仲裁（对资源冲突进行全局抢占判定）
    # =============================
    gra_inputs = _build_gra_inputs(pareto_solutions, event_lat=event_lat, event_lng=event_lng)
    if gra_inputs["conflicts"]:
        async with AsyncSessionLocal() as gra_db:
            config_service = AlgorithmConfigService(gra_db)
            gra_loader = GRAConfigLoader(config_service)
            gra_params = await gra_loader.load_params()
        resolver = ConflictResolver(params=gra_params)

        for sol in pareto_solutions:
            sol.setdefault("gra_actions", [])
            sol.setdefault("gra_switching_cost", None)
            sol.setdefault("safety_classification", {"reject": [], "break_glass": [], "warn": []})
            sol.setdefault("break_glass_rules", [])

        for conflict in gra_inputs["conflicts"]:
            res_id = conflict["resource_id"]
            resource_state = gra_inputs["resources"].get(res_id)
            claims = resolver._parse_claims(conflict["claims"])
            conflict_obj = Conflict(
                id=conflict["id"],
                conflict_type=ConflictType.EXCLUSIVE,
                resource_id=res_id,
                claims=claims,
                severity=1.0,
            )
            resolution = resolver.gra_resolve_conflict(conflict_obj, gra_inputs["resources"])
            if resolution:
                for sol in pareto_solutions:
                    if sol.get("solution_id") == conflict["id"]:
                        sol["gra_actions"].extend(resolution.actions)
                        sol["gra_switching_cost"] = resolution.cost
                        break

    # 更新追踪信息
    trace["phases_executed"] = trace.get("phases_executed", []) + ["optimize_allocation"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + [algorithm_used]
    trace["solutions_generated"] = len(solutions)
    trace["optimization_algorithm"] = algorithm_used

    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[分配优化] 完成，算法={algorithm_used}，生成{len(solutions)}个方案，Pareto解{len(pareto_solutions)}个，耗时{elapsed_ms}ms"
    )

    return {
        "allocation_solutions": solutions,
        "pareto_solutions": pareto_solutions,
        "trace": trace,
        "errors": errors,
    }


def _run_nsga2_optimization(
    candidates: List[ResourceCandidate],
    capability_requirements: List[Dict[str, Any]],
    task_sequence: List[Dict[str, Any]],
    n_solutions: int = 5,
    estimated_trapped: int = 0,
    event_lat: float = 0.0,
    event_lng: float = 0.0,
) -> List[AllocationSolution]:
    """
    使用NSGA-II进行多目标优化 (调用统一算法库)
    
    优化目标（5维评估）：
    1. 最大化成功率（权重0.35）
    2. 最小化响应时间（权重0.30）
    3. 最大化覆盖率（权重0.20）
    4. 最小化风险（权重0.05）
    5. 最大化冗余性（权重0.10）
    
    Args:
        candidates: 候选资源
        capability_requirements: 能力需求
        task_sequence: HTN任务序列
        n_solutions: 生成方案数量
        
    Returns:
        Pareto最优解列表
    """
    logger.info(f"[NSGA-II] 开始多目标优化 (使用 PymooOptimizer)")
    
    # 检查候选资源
    n_resources = len(candidates)
    if n_resources == 0:
        raise RuntimeError("[NSGA-III] 候选资源为空，无法执行优化")
        
    required_caps = {cap["capability_code"] for cap in capability_requirements}
    
    # 定义问题类 (继承自pymoo ElementwiseProblem)
    # 注意：这里我们需要在运行时定义，因为依赖闭包变量(candidates)
    from pymoo.core.problem import ElementwiseProblem
    import numpy as np

    class EmergencyAllocationProblem(ElementwiseProblem):
        def __init__(self):
            super().__init__(
                n_var=n_resources,
                n_obj=5,  # 成功率、响应时间、覆盖率、风险、冗余性
                n_constr=1,  # 覆盖率约束
                xl=0,
                xu=1,
                vtype=int,
            )
        
        def _evaluate(self, x, out, *args, **kwargs):
            selected_indices = np.where(x > 0.5)[0]
            
            if len(selected_indices) == 0:
                out["F"] = [1.0, 1e5, 1.0, 1.0, 1.0]  # 5维惩罚值
                out["G"] = [1.0]
                return
            
            max_eta = 0.0
            covered_caps: set = set()
            total_match_score = 0.0
            total_capacity = 0
            
            for idx in selected_indices:
                cand = candidates[idx]
                max_eta = max(max_eta, cand.get("eta_minutes", 0))
                covered_caps.update(cand["capabilities"])
                total_match_score += cand.get("match_score", 0.5)
                total_capacity += cand.get("rescue_capacity", 0)
            
            # 覆盖率：已覆盖能力 / 所需能力
            coverage = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
            avg_match_score = total_match_score / len(selected_indices) if selected_indices.size > 0 else 0.5
            
            # 冗余性：每个能力被多少队伍覆盖（平均值归一化）
            cap_coverage_count: Dict[str, int] = {}
            for idx in selected_indices:
                for cap in candidates[idx]["capabilities"]:
                    if cap in required_caps:
                        cap_coverage_count[cap] = cap_coverage_count.get(cap, 0) + 1
            redundancy = sum(min(c, 2) for c in cap_coverage_count.values()) / (2 * len(required_caps)) if required_caps else 1.0
            
            # 5维目标（pymoo最小化所有目标，最大化需取负）
            # f0: 成功率（基于覆盖率×匹配度，取负最大化）
            success_rate = coverage * avg_match_score
            # f1: 响应时间（归一化到0-1，120分钟为基准）
            time_score = min(max_eta / 120.0, 1.0)
            # f2: 覆盖率（取负最大化）
            # f3: 风险（1-覆盖率，最小化）
            risk = 1.0 - coverage
            # f4: 冗余性（取负最大化）
            
            out["F"] = [
                -success_rate,  # f0: 成功率（权重0.35）
                time_score,     # f1: 响应时间（权重0.30）
                -coverage,      # f2: 覆盖率（权重0.20）
                risk,           # f3: 风险（权重0.05）
                -redundancy,    # f4: 冗余性（权重0.10）
            ]
            # 约束: 覆盖率 >= 95%
            out["G"] = [0.95 - coverage]

    # 调用统一算法优化器（5目标使用NSGA-III）
    # 时间预算30秒，紧急情况下可以更快得到结果
    optimizer = PymooOptimizer()
    result = optimizer.run({
        "problem": EmergencyAllocationProblem(),
        "pop_size": 100,
        "n_generations": 80,  # 备用：无时间预算时使用
        "time_budget_seconds": 30,  # 优先使用时间预算
        "algorithm": "nsga3",  # 5维目标使用NSGA-III
        "objective_names": ["success_rate", "response_time", "coverage_rate", "risk", "redundancy"],
        "verbose": False,
        "seed": 42
    })
    logger.info(f"[NSGA-III] 5维优化完成: 成功率、响应时间、覆盖率、风险、冗余性")
    
    if result.status != AlgorithmStatus.SUCCESS or not result.solution:
        logger.warning(f"[NSGA-III] 优化未找到可行解: {result.message}，降级到贪心算法")
        return []  # 返回空列表，外层会使用贪心算法生成方案
        
    # 解析结果并构建 AllocationSolution
    solutions: List[AllocationSolution] = []
    seen_solutions: set = set()
    
    for sol in result.solution:
        # PymooOptimizer返回的variables是列表
        x = np.array(sol["variables"])
        objectives = sol["objectives"]
        
        selected_indices = np.where(x > 0.5)[0]
        if len(selected_indices) == 0:
            continue
            
        # 去重
        sol_key = frozenset(int(i) for i in selected_indices)
        if sol_key in seen_solutions:
            continue
        seen_solutions.add(sol_key)
        
        # 构建方案详情
        allocations: List[Dict[str, Any]] = []
        covered_caps = set()
        max_eta = 0.0
        max_distance = 0.0
        total_capacity = 0
        
        for idx in selected_indices:
            cand = candidates[int(idx)]
            # 计算该资源贡献的新能力
            assignable_caps = set(cand["capabilities"]).intersection(required_caps) - covered_caps
            cand_capacity = cand.get("rescue_capacity", 0)
            
            allocations.append({
                "resource_id": cand["resource_id"],
                "resource_name": cand["resource_name"],
                "resource_type": cand["resource_type"],
                "assigned_capabilities": list(assignable_caps) if assignable_caps else cand["capabilities"],
                "match_score": cand["match_score"],
                "distance_km": cand["distance_km"],
                "eta_minutes": cand.get("eta_minutes", 0),
                "rescue_capacity": cand_capacity,
                "task_start": (event_lng, event_lat),
                "resource_state": {
                    "current_position": (cand.get("base_lng", 0), cand.get("base_lat", 0)),
                    "home_position": (cand.get("base_lng", 0), cand.get("base_lat", 0)),
                    "remaining_capacity": float(cand_capacity),
                    "max_range": 100.0,
                    "current_task_progress": 0.0,
                },
            })
            covered_caps.update(cand["capabilities"])
            max_eta = max(max_eta, cand.get("eta_minutes", 0))
            max_distance = max(max_distance, cand["distance_km"])
            total_capacity += cand_capacity
            
        # 计算综合指标
        coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
        avg_score = sum(a["match_score"] for a in allocations) / len(allocations) if allocations else 0
        
        # 容量分析
        capacity_coverage = total_capacity / estimated_trapped if estimated_trapped > 0 else 1.0
        capacity_warning = None
        if estimated_trapped > 0 and capacity_coverage < 0.8:
            capacity_warning = f"⚠️ 救援容量不足 (覆盖率{capacity_coverage*100:.1f}%)"
            
        allocation_sol: AllocationSolution = {
            "solution_id": f"nsga-{uuid.uuid4().hex[:8]}",
            "allocations": allocations,
            "total_score": round(avg_score, 3),
            "response_time_min": round(max_eta, 1),
            "coverage_rate": round(coverage_rate, 3),
            "resource_scale": len(allocations),
            "risk_level": round(1.0 - coverage_rate, 3),
            "total_rescue_capacity": total_capacity,
            "capacity_coverage_rate": round(capacity_coverage, 3),
            "capacity_warning": capacity_warning,
            "uncovered_capabilities": list(required_caps - covered_caps),
            "max_distance_km": round(max_distance, 2),
            "teams_count": len(allocations),
            "objectives": {
                "success_rate": round(-objectives.get("success_rate", 0), 3),  # 负转正
                "response_time": round(objectives.get("response_time", 0), 3),
                "coverage_rate": round(-objectives.get("coverage_rate", 0), 3),  # 负转正
                "risk": round(objectives.get("risk", 0), 3),
                "redundancy": round(-objectives.get("redundancy", 0), 3),  # 负转正
            }
        }
        solutions.append(allocation_sol)
        
        if len(solutions) >= n_solutions:
            break
            
    # 按覆盖率排序
    solutions.sort(key=lambda s: s["coverage_rate"], reverse=True)
    logger.info(f"[NSGA-III] 生成 {len(solutions)} 个Pareto解")
    
    return solutions


async def _resolve_scenario_id(
    db: AsyncSession,
    scenario_id_raw: Any,
) -> Optional[UUID]:
    """
    解析scenario_id为UUID
    
    支持以下输入格式：
    1. 已经是UUID对象 -> 直接返回
    2. 有效的UUID字符串 -> 转换为UUID
    3. scenario名称 -> 从数据库查找对应的UUID
    4. 无效输入 -> 返回None
    
    Args:
        db: 数据库会话
        scenario_id_raw: 原始scenario_id（可能是UUID、字符串或其他）
        
    Returns:
        有效的UUID，或None表示无法解析
    """
    if scenario_id_raw is None:
        return None
    
    # 已经是UUID对象
    if isinstance(scenario_id_raw, UUID):
        return scenario_id_raw
    
    # 尝试转换为UUID字符串
    if isinstance(scenario_id_raw, str):
        # 尝试直接解析为UUID
        try:
            return UUID(scenario_id_raw)
        except ValueError:
            pass
        
        # 不是有效UUID格式，尝试按名称查找
        try:
            sql = text("""
                SELECT id FROM operational_v2.scenarios_v2
                WHERE name ILIKE :name_pattern
                LIMIT 1
            """)
            result = await db.execute(sql, {"name_pattern": f"%{scenario_id_raw}%"})
            row = result.fetchone()
            if row:
                logger.info(f"[scenario解析] 按名称'{scenario_id_raw}'找到scenario: {row[0]}")
                return row[0]
            else:
                logger.warning(f"[scenario解析] 未找到名称匹配'{scenario_id_raw}'的scenario")
                return None
        except Exception as e:
            logger.warning(f"[scenario解析] 查询失败: {e}")
            return None
    
    # 其他类型，尝试转换为字符串再解析
    try:
        return UUID(str(scenario_id_raw))
    except (ValueError, TypeError):
        return None


def _extract_event_location(state: EmergencyAIState) -> Optional[Tuple[float, float]]:
    """
    从state中提取事件坐标

    优先从structured_input.location获取，
    支持{longitude, latitude}或{lng, lat}格式。

    Returns:
        (latitude, longitude)元组，或None表示无效
    """
    structured_input = state.get("structured_input", {})
    if not structured_input:
        return None

    location = structured_input.get("location", {})
    if not location:
        return None

    # 支持多种字段名
    lat = location.get("latitude") or location.get("lat")
    lng = location.get("longitude") or location.get("lng")

    if lat is None or lng is None:
        return None

    try:
        lat_float = float(lat)
        lng_float = float(lng)
        # 基本有效性检查
        if not (-90 <= lat_float <= 90 and -180 <= lng_float <= 180):
            return None
        return (lat_float, lng_float)
    except (TypeError, ValueError):
        return None


def _determine_disaster_scale(state: EmergencyAIState) -> str:
    """
    根据灾情判断灾害等级
    
    Args:
        state: 当前状态
        
    Returns:
        灾害等级: small/medium/large/catastrophic
    """
    parsed_disaster = state.get("parsed_disaster")
    if parsed_disaster is None:
        logger.info("[匹配-灾害等级] 无灾情数据，使用默认等级: medium")
        return "medium"
    
    # 根据受影响人口判断
    affected_pop = parsed_disaster.get("affected_population", 0)
    estimated_trapped = parsed_disaster.get("estimated_trapped", 0)
    severity = parsed_disaster.get("severity", "medium")
    disaster_type = parsed_disaster.get("disaster_type", "").lower()
    
    logger.info(f"[匹配-灾害等级] 判断输入参数:")
    logger.info(f"  - disaster_type: {disaster_type}")
    logger.info(f"  - severity: {severity}")
    logger.info(f"  - affected_population: {affected_pop}")
    logger.info(f"  - estimated_trapped: {estimated_trapped}")
    
    # 地震/特大灾害
    if disaster_type == "earthquake" or severity == "critical":
        if affected_pop > 10000 or estimated_trapped > 100:
            logger.info(f"[匹配-灾害等级] 判断: 地震/特大灾害 + (人口>{10000}或被困>{100}) -> catastrophic")
            return "catastrophic"
        logger.info(f"[匹配-灾害等级] 判断: 地震/严重灾害 -> large")
        return "large"
    
    # 根据被困人数
    if estimated_trapped > 50:
        logger.info(f"[匹配-灾害等级] 判断: 被困人数{estimated_trapped} > 50 -> large")
        return "large"
    elif estimated_trapped > 10:
        logger.info(f"[匹配-灾害等级] 判断: 被困人数{estimated_trapped} > 10 -> medium")
        return "medium"
    
    # 根据严重程度
    severity_mapping = {
        "critical": "large",
        "high": "medium",
        "medium": "medium",
        "low": "small",
    }
    result = severity_mapping.get(severity, "medium")
    logger.info(f"[匹配-灾害等级] 判断: 按严重程度{severity} -> {result}")
    return result


async def _query_teams_from_db(
    db: AsyncSession,
    event_lat: float,
    event_lng: float,
    max_distance_km: float,
    max_teams: int = DEFAULT_MAX_TEAMS,
) -> List[Dict[str, Any]]:
    """
    从数据库查询指定范围内的可用队伍

    使用PostGIS ST_Distance计算球面距离，
    关联team_capabilities_v2获取能力列表，
    关联team_vehicles_v2和vehicles_v2获取主力车辆参数。

    Args:
        db: 数据库会话
        event_lat: 事件纬度
        event_lng: 事件经度
        max_distance_km: 最大距离（公里）
        max_teams: 返回的最大队伍数量

    Returns:
        队伍列表，包含id, name, type, capabilities, distance_m, vehicle_speed_kmh等
    """
    # 使用子查询获取每个队伍的主力车辆（按is_primary DESC, assigned_at ASC取第一辆）
    sql = text("""
        WITH primary_vehicles AS (
            SELECT DISTINCT ON (tv.team_id) 
                tv.team_id,
                tv.vehicle_id,
                v.max_speed_kmh,
                v.is_all_terrain,
                v.code as vehicle_code,
                v.name as vehicle_name
            FROM operational_v2.team_vehicles_v2 tv
            JOIN operational_v2.vehicles_v2 v ON v.id = tv.vehicle_id
            WHERE tv.status = 'available'
            ORDER BY tv.team_id, tv.is_primary DESC, tv.assigned_at ASC
        )
        SELECT 
            t.id,
            t.code,
            t.name,
            t.team_type,
            ST_Y(t.base_location::geometry) AS base_lat,
            ST_X(t.base_location::geometry) AS base_lng,
            t.base_address,
            t.total_personnel,
            t.available_personnel,
            t.capability_level,
            t.response_time_minutes,
            t.status,
            COALESCE(
                ARRAY_AGG(DISTINCT tc.capability_code) 
                FILTER (WHERE tc.capability_code IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) AS capabilities,
            COALESCE(SUM(tc.max_capacity), 0) AS total_rescue_capacity,
            ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
            ) AS distance_m,
            pv.max_speed_kmh AS vehicle_speed_kmh,
            pv.is_all_terrain AS vehicle_is_all_terrain,
            pv.vehicle_code,
            pv.vehicle_name
        FROM operational_v2.rescue_teams_v2 t
        LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
        LEFT JOIN primary_vehicles pv ON pv.team_id = t.id
        WHERE (t.status = 'standby' OR t.team_type = 'command')
          AND t.base_location IS NOT NULL
          AND ST_Distance(
                t.base_location,
                ST_SetSRID(ST_MakePoint(:event_lng, :event_lat), 4326)::geography
              ) <= :max_distance_m
        GROUP BY t.id, pv.max_speed_kmh, pv.is_all_terrain, pv.vehicle_code, pv.vehicle_name
        ORDER BY distance_m ASC, t.capability_level DESC
        LIMIT :max_teams
    """)

    params = {
        "event_lat": event_lat,
        "event_lng": event_lng,
        "max_distance_m": max_distance_km * 1000,
        "max_teams": max_teams,
    }

    try:
        result = await db.execute(sql, params)
        rows = result.fetchall()
        columns = result.keys()

        teams: List[Dict[str, Any]] = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            
            # 救援容量：优先使用数据库值，否则按类型估算
            db_capacity = row_dict.get("total_rescue_capacity", 0) or 0
            team_type = row_dict["team_type"]
            available = row_dict["available_personnel"] or 0
            
            if db_capacity > 0:
                rescue_capacity = int(db_capacity)
            else:
                # 数据库缺失max_capacity，记录严重警告
                # 按队伍类型估算救援容量（72小时内可救援人数）
                capacity_multipliers: Dict[str, float] = {
                    "fire_rescue": 2.0,
                    "search_rescue": 1.5,
                    "medical": 5.0,
                    "hazmat": 0.5,
                    "engineering": 0.0,
                    "volunteer": 1.0,
                }
                multiplier = capacity_multipliers.get(team_type, 1.0)
                rescue_capacity = int(available * multiplier)
                if rescue_capacity == 0 and available > 0:
                    rescue_capacity = available
                # 严重警告：数据库缺失关键字段，估算值可能不准确
                logger.warning(
                    f"[救援容量] 队伍 {row_dict['name']} 数据库缺失max_capacity，"
                    f"使用估算值: {available}人×{multiplier}={rescue_capacity}，请尽快补充数据库数据"
                )
            
            # 车辆速度：优先使用数据库值，否则使用默认配置
            vehicle_speed: int = row_dict.get("vehicle_speed_kmh") or 0
            vehicle_is_all_terrain: bool = row_dict.get("vehicle_is_all_terrain") or False
            vehicle_code: Optional[str] = row_dict.get("vehicle_code")
            vehicle_name: Optional[str] = row_dict.get("vehicle_name")
            
            # 无车辆数据时，使用队伍类型默认配置
            if vehicle_speed == 0:
                profile = TEAM_VEHICLE_PROFILES.get(team_type, DEFAULT_VEHICLE_PROFILE)
                vehicle_speed = int(profile.speed_kmh)
                vehicle_is_all_terrain = profile.is_all_terrain
                logger.debug(f"[车辆参数] {row_dict['name']} 无关联车辆，使用默认配置: {vehicle_speed}km/h, 全地形={vehicle_is_all_terrain}")
            
            team = {
                "id": str(row_dict["id"]),
                "code": row_dict["code"],
                "name": row_dict["name"],
                "team_type": row_dict["team_type"],
                "base_lat": row_dict["base_lat"],
                "base_lng": row_dict["base_lng"],
                "base_address": row_dict["base_address"],
                "total_personnel": row_dict["total_personnel"],
                "available_personnel": row_dict["available_personnel"],
                "capability_level": row_dict["capability_level"],
                "response_time_minutes": row_dict["response_time_minutes"],
                "status": row_dict["status"],
                "capabilities": list(row_dict["capabilities"] or []),
                "distance_m": row_dict["distance_m"],
                "distance_km": row_dict["distance_m"] / 1000.0 if row_dict["distance_m"] else 0,
                "rescue_capacity": rescue_capacity,
                # 车辆参数（用于ETA计算）
                "vehicle_speed_kmh": vehicle_speed,
                "vehicle_is_all_terrain": vehicle_is_all_terrain,
                "vehicle_code": vehicle_code,
                "vehicle_name": vehicle_name,
            }
            teams.append(team)

        total_capacity = sum(t["rescue_capacity"] for t in teams)
        teams_with_vehicle = sum(1 for t in teams if t.get("vehicle_code"))
        logger.info(f"【数据库-队伍查询】找到{len(teams)}支队伍，{teams_with_vehicle}支有关联车辆，总救援容量{total_capacity}人:")
        for t in teams[:10]:  # 打印前10支
            logger.info(f"  - {t['name']}: 能力={t['capabilities']}, 距离={t['distance_km']:.1f}km, 容量={t['rescue_capacity']}人")
        if len(teams) > 10:
            logger.info(f"  ... 还有{len(teams)-10}支队伍")
        return teams

    except Exception as e:
        logger.error(f"[数据库查询] 查询队伍失败: {e}")
        raise


def _get_covered_capabilities(teams: List[Dict[str, Any]]) -> set:
    """获取所有队伍覆盖的能力集合"""
    covered: set = set()
    for team in teams:
        covered.update(team.get("capabilities", []))
    return covered


def _calculate_match_scores(
    teams: List[Dict[str, Any]],
    required_capabilities: set,
    event_lat: float,
    event_lng: float,
    max_response_hours: float,
    terrain_type: str = "mountain",
    has_road_damage: bool = False,
    base_road_factor: float = 1.4,
    damaged_road_factor: float = 2.8,
) -> List[ResourceCandidate]:
    """
    计算每个队伍的匹配分数

    评分维度：
    - 能力覆盖率（50%）：队伍能力与需求的交集比例
    - 距离评分（30%）：距离越近分数越高
    - 能力等级（20%）：capability_level越高分数越高

    ETA计算：
    - 使用队伍关联车辆的max_speed_kmh（无车辆时使用队伍类型默认速度）
    - 道路系数：直线距离×1.4（山区道路迂回）
    - 地形降速：非全地形车辆在山区降速50%

    Args:
        teams: 队伍列表（含vehicle_speed_kmh, vehicle_is_all_terrain）
        required_capabilities: 需要的能力集合
        event_lat: 事件纬度
        event_lng: 事件经度
        max_response_hours: 最大响应时间（小时）
        terrain_type: 地形类型，影响ETA计算（默认mountain山区）

    Returns:
        ResourceCandidate列表
    """
    candidates: List[ResourceCandidate] = []
    
    # 道路系数：根据道路是否受损动态调整（参数从数据库获取）
    road_factor: float = damaged_road_factor if has_road_damage else base_road_factor
    if has_road_damage:
        logger.warning(f"[匹配-道路] 检测到道路受损，ETA系数={road_factor}（正常={base_road_factor}）")
    terrain_speed_factor: float = TERRAIN_SPEED_FACTORS.get(terrain_type, 0.5)
    
    # 使用默认速度计算最大搜索距离（用于距离评分归一化）
    default_speed: float = DEFAULT_VEHICLE_PROFILE.speed_kmh
    max_distance_km: float = max_response_hours * default_speed

    for team in teams:
        team_caps = set(team.get("capabilities", []))
        matched_caps = team_caps.intersection(required_capabilities)

        # 无匹配能力则跳过
        if not matched_caps:
            continue

        # 能力覆盖率评分
        capability_score = len(matched_caps) / len(required_capabilities) if required_capabilities else 0

        # 距离评分（距离越近越好）
        distance_km: float = team.get("distance_km", 0)
        distance_score = max(0, 1.0 - distance_km / max_distance_km) if max_distance_km > 0 else 0

        # 能力等级评分（1-5映射到0.2-1.0）
        capability_level: int = team.get("capability_level", 3)
        level_score = capability_level / 5.0

        # 获取车辆参数
        vehicle_speed_kmh: int = team.get("vehicle_speed_kmh", int(default_speed))
        vehicle_is_all_terrain: bool = team.get("vehicle_is_all_terrain", False)
        
        # 获取队伍类型对应的山区速度限制
        team_type = team.get("team_type", "")
        profile = TEAM_VEHICLE_PROFILES.get(team_type, DEFAULT_VEHICLE_PROFILE)
        mountain_speed_limit = profile.mountain_speed_kmh
        
        # 计算实际道路距离（使用动态道路系数，考虑道路损坏情况）
        road_distance_km: float = distance_km * road_factor
        
        # 计算实际行驶速度（考虑地形和山区限速）
        # 即使是全地形车辆，在山区也要受山区道路限速约束
        if vehicle_is_all_terrain:
            # 全地形车辆：取车辆速度和山区限速的较小值
            actual_speed_kmh: float = min(float(vehicle_speed_kmh), mountain_speed_limit)
        else:
            # 非全地形车辆：车辆速度降速后，再取与山区限速的较小值
            reduced_speed = float(vehicle_speed_kmh) * terrain_speed_factor
            actual_speed_kmh = min(reduced_speed, mountain_speed_limit)
        
        # 最低速度保护（防止除零和不合理值）
        actual_speed_kmh = max(actual_speed_kmh, 10.0)
        
        # 队伍响应/集结时间（从数据库字段读取，默认5分钟）
        team_response_time: float = float(team.get("response_time_minutes") or 5)
        
        # 行驶时间（分钟）= 道路距离 / 实际速度 × 60
        travel_time_minutes: float = (road_distance_km / actual_speed_kmh) * 60 if road_distance_km > 0 else 0
        
        # 总到达时间 = 响应时间 + 行驶时间
        eta_minutes: float = team_response_time + travel_time_minutes

        # 综合得分
        match_score = (
            capability_score * 0.50 +
            distance_score * 0.30 +
            level_score * 0.20
        )

        # 队伍类型映射
        resource_type = _map_team_type(team.get("team_type", ""))

        candidate: ResourceCandidate = {
            "resource_id": team["id"],
            "resource_name": team["name"],
            "resource_type": resource_type,
            # 保存队伍的全部能力，而不是只保存与当前需求匹配的能力
            # 这样在分配优化阶段可以考虑任务的所有能力需求
            "capabilities": list(team_caps),
            "distance_km": round(distance_km, 2),
            "road_distance_km": round(road_distance_km, 2),  # 实际道路距离
            "availability_score": 1.0,
            "match_score": round(match_score, 3),
            "rescue_capacity": team.get("rescue_capacity", 0),
            # ETA相关（时间拆分）
            "response_time_minutes": round(team_response_time, 1),  # 队伍集结时间
            "travel_time_minutes": round(travel_time_minutes, 1),   # 行驶时间
            "eta_minutes": round(eta_minutes, 1),                   # 总到达时间
            "route_distance_km": round(road_distance_km, 2),        # 路径距离（初始为估算值）
            "route_source": "estimate",                              # 路径来源（初始为估算）
            "vehicle_speed_kmh": vehicle_speed_kmh,
            "actual_speed_kmh": round(actual_speed_kmh, 1),
            "vehicle_is_all_terrain": vehicle_is_all_terrain,
            "vehicle_code": team.get("vehicle_code"),
            "vehicle_name": team.get("vehicle_name"),
            "capability_level": capability_level,
            "base_address": team.get("base_address", ""),
            "personnel": team.get("available_personnel") or team.get("total_personnel", 0),
        }
        candidates.append(candidate)

    return candidates


def _map_team_type(team_type: str) -> str:
    """队伍类型映射到标准资源类型"""
    mapping = {
        "fire_rescue": "FIRE_TEAM",
        "medical": "MEDICAL_TEAM",
        "search_rescue": "RESCUE_TEAM",
        "hazmat": "HAZMAT_TEAM",
        "engineering": "ENGINEERING_TEAM",
        "communication": "SUPPORT_TEAM",
        "logistics": "SUPPORT_TEAM",
        "water_rescue": "WATER_RESCUE_TEAM",
        "mountain_rescue": "RESCUE_TEAM",
        "mine_rescue": "RESCUE_TEAM",
        "armed_police": "ARMED_TEAM",
        "evacuation": "EVACUATION_TEAM",
        "volunteer": "VOLUNTEER_TEAM",
        "command": "COMMAND_TEAM",
    }
    return mapping.get(team_type, "RESCUE_TEAM")


# ============================================================================
# 任务-资源分配（对齐杀伤链路径概念）
# ============================================================================


def _assign_tasks_to_resources(
    task_sequence: List[Dict[str, Any]],
    selected_resources: List[Dict[str, Any]],
    capability_requirements: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    """
    为任务序列分配最佳资源
    
    对齐参考系统的杀伤链路径概念：
    - 输入：任务序列 + 候选资源列表
    - 输出：任务-资源分配序列 + 执行路径字符串
    
    分配策略：
    1. 对每个任务，找出具备所需能力的资源
    2. 优先选择匹配度高、距离近的资源
    3. 尽量让同类任务由同一资源执行（减少协调开销）
    4. 生成执行路径字符串，如 "探测(队A)→支撑(队B)→救治(队C)"
    
    Args:
        task_sequence: HTN分解后的任务序列
        selected_resources: 已选中的资源列表
        capability_requirements: 能力需求列表
        
    Returns:
        (task_assignments, execution_path_str)
    """
    logger.info(f"【任务分配-输入】开始为{len(task_sequence)}个任务分配资源")
    logger.info(f"  - 任务列表: {[t.get('task_id') for t in task_sequence]}")
    logger.info(f"  - 候选资源: {len(selected_resources)}支队伍")
    for r in selected_resources[:5]:
        logger.info(f"    {r.get('resource_name')}: 能力={r.get('capabilities', [])}")
    if len(selected_resources) > 5:
        logger.info(f"    ... 还有{len(selected_resources)-5}支队伍")
    
    if not task_sequence or not selected_resources:
        return [], ""
    
    # 构建能力→任务映射
    cap_to_tasks: Dict[str, List[str]] = {}
    for cap in capability_requirements:
        cap_code = cap.get("capability_code", "")
        if cap_code:
            cap_to_tasks[cap_code] = cap_to_tasks.get(cap_code, [])
    
    # 构建资源ID→资源信息映射
    resource_map: Dict[str, Dict[str, Any]] = {
        r.get("resource_id", ""): r for r in selected_resources
    }
    
    task_assignments: List[Dict[str, Any]] = []
    resource_task_count: Dict[str, int] = {}  # 每个资源分配的任务数
    
    for seq_idx, task in enumerate(task_sequence, start=1):
        task_id = task.get("task_id", f"TASK-{seq_idx}")
        task_name = task.get("task_name", "未知任务")
        task_phase = task.get("phase", "execute")
        
        # 获取任务所需的能力（从Neo4j MetaTask节点查询得到）
        # 转换为大写格式以匹配资源能力代码（Neo4j用小写蛇形，PostgreSQL用大写下划线）
        raw_caps = task.get("required_capabilities", [])
        required_caps = set(cap.upper().replace("-", "_") for cap in raw_caps)
        if not required_caps:
            logger.warning(
                f"[任务分配] 任务{task_id}无required_capabilities，"
                "请检查Neo4j中MetaTask节点的数据"
            )
        
        # 寻找最佳匹配资源
        best_resource: Optional[Dict[str, Any]] = None
        best_score = -1.0
        match_reason = "默认分配"
        
        for resource in selected_resources:
            # 兼容两种字段名：candidates用capabilities，allocations用assigned_capabilities
            resource_caps = set(resource.get("capabilities", []) or resource.get("assigned_capabilities", []))
            resource_id = resource.get("resource_id", "")
            
            # 计算能力匹配度
            if required_caps:
                matched_caps = resource_caps.intersection(required_caps)
                cap_match_rate = len(matched_caps) / len(required_caps) if required_caps else 0
            else:
                # 无特定要求时，看资源是否有任何相关能力
                cap_match_rate = 0.5 if resource_caps else 0.1
            
            # 综合评分 = 能力匹配度(60%) + 原始匹配分(30%) + 负载均衡(10%)
            base_score = resource.get("match_score", 0.5)
            load_factor = 1.0 / (1 + resource_task_count.get(resource_id, 0))  # 任务越少越好
            
            score = cap_match_rate * 0.6 + base_score * 0.3 + load_factor * 0.1
            
            if score > best_score:
                best_score = score
                best_resource = resource
                if matched_caps if required_caps else resource_caps:
                    caps_str = "、".join(list(matched_caps)[:2]) if required_caps and matched_caps else "综合能力"
                    match_reason = f"具备{caps_str}能力，匹配度{cap_match_rate*100:.0f}%"
        
        # 如果找不到匹配资源，使用第一个可用资源
        if best_resource is None and selected_resources:
            best_resource = selected_resources[0]
            match_reason = "无最佳匹配，使用首选资源"
        
        if best_resource:
            resource_id = best_resource.get("resource_id", "")
            resource_task_count[resource_id] = resource_task_count.get(resource_id, 0) + 1
            
            assignment = {
                "task_id": task_id,
                "task_name": task_name,
                "resource_id": resource_id,
                "resource_name": best_resource.get("resource_name", "未知队伍"),
                "resource_type": best_resource.get("resource_type", "RESCUE_TEAM"),
                "execution_sequence": seq_idx,
                "phase": task_phase,
                "eta_minutes": best_resource.get("eta_minutes", 0),
                "match_score": round(best_score, 3),
                "match_reason": match_reason,
            }
            task_assignments.append(assignment)
            
            logger.info(
                f"【任务分配】{task_name}({task_id}) → {best_resource.get('resource_name')} "
                f"(分数={best_score:.3f}, 原因: {match_reason})"
            )
    
    # 生成执行路径字符串
    path_parts = []
    for assignment in task_assignments:
        short_name = assignment["task_name"][:4]  # 取前4个字符
        resource_short = assignment["resource_name"][:6]  # 取前6个字符
        path_parts.append(f"{short_name}({resource_short})")
    
    execution_path = " → ".join(path_parts) if path_parts else "无执行路径"
    
    logger.info(f"【任务分配-输出】完成，{len(task_assignments)}个任务已分配:")
    for a in task_assignments:
        logger.info(f"  {a['execution_sequence']}. {a['task_name']} → {a['resource_name']} (分数={a['match_score']:.3f})")
    logger.info(f"【执行路径】{execution_path}")
    
    return task_assignments, execution_path


def _enrich_allocations_with_task_descriptions(
    solution: AllocationSolution,
    task_assignments: List[Dict[str, Any]],
) -> None:
    """
    为方案中的每个队伍添加任务描述
    
    基于 task_assignments 反向汇总，为 allocations 中的每个队伍
    生成 task_description 字段，描述该队伍负责的具体任务。
    
    Args:
        solution: 分配方案（会被原地修改）
        task_assignments: 任务-资源分配列表
    """
    if not task_assignments:
        return
    
    # 构建资源ID→任务列表映射
    resource_tasks: Dict[str, List[Dict[str, Any]]] = {}
    for assignment in task_assignments:
        resource_id = assignment.get("resource_id", "")
        if resource_id:
            if resource_id not in resource_tasks:
                resource_tasks[resource_id] = []
            resource_tasks[resource_id].append(assignment)
    
    # 为每个allocation添加task_description
    allocations = solution.get("allocations", [])
    for alloc in allocations:
        resource_id = alloc.get("resource_id", "")
        tasks = resource_tasks.get(resource_id, [])
        
        if tasks:
            # 生成任务描述：如 "负责危化品泄漏侦检(EM20)、堵漏处置(EM21)"
            task_parts = [f"{t['task_name']}({t['task_id']})" for t in tasks]
            alloc["task_description"] = "负责" + "、".join(task_parts)
            alloc["assigned_tasks"] = [{"task_id": t["task_id"], "task_name": t["task_name"]} for t in tasks]
        else:
            # 没有分配任务的队伍（可能是能力冗余备份）
            caps = alloc.get("assigned_capabilities", [])
            if caps:
                alloc["task_description"] = f"提供{caps[0]}等能力支援"
            else:
                alloc["task_description"] = "综合救援支援"
            alloc["assigned_tasks"] = []


def _generate_greedy_solution(
    candidates: List[ResourceCandidate],
    capability_requirements: List[Dict[str, Any]],
    strategy: str,
    solution_id: str,
    estimated_trapped: int = 0,
    capacity_safety_factor: float = 1.2,
    event_lat: float = 0.0,
    event_lng: float = 0.0,
) -> Optional[AllocationSolution]:
    """
    使用贪心策略生成分配方案
    
    修复版本：同时考虑能力覆盖和救援容量，不会在能力覆盖100%时就停止

    Args:
        candidates: 候选资源列表
        capability_requirements: 能力需求列表
        strategy: 策略 (match_score/distance/availability)
        solution_id: 方案ID
        estimated_trapped: 被困人数，用于计算最低救援容量需求

    Returns:
        分配方案或None
    """
    if not candidates or not capability_requirements:
        return None

    # 按策略排序
    if strategy == "match_score":
        sorted_candidates = sorted(candidates, key=lambda x: x["match_score"], reverse=True)
    elif strategy == "distance":
        sorted_candidates = sorted(candidates, key=lambda x: x["distance_km"])
    elif strategy == "availability":
        sorted_candidates = sorted(candidates, key=lambda x: x["availability_score"], reverse=True)
    elif strategy == "capacity":
        # 容量优先：按救援容量降序排序（巨灾场景优先选择大容量队伍）
        sorted_candidates = sorted(candidates, key=lambda x: x.get("rescue_capacity", 0), reverse=True)
    else:
        sorted_candidates = list(candidates)

    # 计算最低救援容量需求（使用数据库配置的容量安全系数）
    min_capacity_required: int = int(estimated_trapped * capacity_safety_factor) if estimated_trapped > 0 else 0
    logger.info(f"[贪心-容量] 被困人数={estimated_trapped}，目标容量={min_capacity_required}（系数={capacity_safety_factor}）")

    # 贪心分配
    required_caps = {cap["capability_code"] for cap in capability_requirements}
    covered_caps: set = set()
    allocations: List[Dict[str, Any]] = []
    max_eta = 0.0
    total_distance = 0.0
    total_capacity = 0  # 累计救援容量
    capability_covered = False  # 标记能力是否已全覆盖
    selected_ids: set = set()  # 已选择的队伍ID，避免重复

    for candidate in sorted_candidates:
        if candidate["resource_id"] in selected_ids:
            continue
            
        candidate_caps = set(candidate["capabilities"])
        new_caps = candidate_caps - covered_caps
        assignable_caps = new_caps.intersection(required_caps)
        candidate_capacity = candidate.get("rescue_capacity", 0)

        # 决策逻辑：
        # 1. 如果有新能力可覆盖，必须选择
        # 2. 如果能力已全覆盖但容量不足，也要选择（只要有救援容量）
        should_select = False
        select_reason = ""
        
        if assignable_caps:
            should_select = True
            select_reason = f"新增能力{assignable_caps}"
        elif capability_covered and total_capacity < min_capacity_required and candidate_capacity > 0:
            should_select = True
            select_reason = f"容量不足({total_capacity}<{min_capacity_required})，增加容量{candidate_capacity}"

        if should_select:
            # 容量补充队伍：使用队伍与需求的交集能力（而非空列表）
            effective_caps = assignable_caps if assignable_caps else candidate_caps.intersection(required_caps)
            allocations.append({
                "resource_id": candidate["resource_id"],
                "resource_name": candidate["resource_name"],
                "resource_type": candidate["resource_type"],
                "assigned_capabilities": list(effective_caps),
                "match_score": candidate["match_score"],
                "distance_km": candidate["distance_km"],
                "eta_minutes": candidate.get("eta_minutes", 0),
                "rescue_capacity": candidate_capacity,
                "task_start": (event_lng, event_lat),
                "resource_state": {
                    "current_position": (candidate.get("base_lng", 0), candidate.get("base_lat", 0)),
                    "home_position": (candidate.get("base_lng", 0), candidate.get("base_lat", 0)),
                    "remaining_capacity": float(candidate_capacity),
                    "max_range": 100.0,
                    "current_task_progress": 0.0,
                },
            })
            selected_ids.add(candidate["resource_id"])
            covered_caps.update(assignable_caps)
            max_eta = max(max_eta, candidate.get("eta_minutes", 0))
            total_distance = max(total_distance, candidate["distance_km"])
            total_capacity += candidate_capacity
            
            logger.info(f"【贪心-选择】{candidate['resource_name']}: {select_reason}，累计容量={total_capacity}，已覆盖能力={len(covered_caps)}/{len(required_caps)}")

        # 检查能力是否全覆盖
        if covered_caps.issuperset(required_caps):
            if not capability_covered:
                logger.info(f"[贪心-能力] 能力已全覆盖，当前容量={total_capacity}，需求={min_capacity_required}")
            capability_covered = True
            
            # 终止条件：能力全覆盖 AND 容量足够
            if estimated_trapped == 0 or total_capacity >= min_capacity_required:
                logger.info(f"[贪心-完成] 能力覆盖100%且容量足够，总容量={total_capacity}")
                break

    if not allocations:
        return None
    
    # === 冗余性增强阶段 ===
    # 统计每个能力被多少队伍覆盖
    capability_coverage_count: Dict[str, int] = {cap: 0 for cap in required_caps}
    for alloc in allocations:
        for cap in alloc.get("assigned_capabilities", []):
            if cap in capability_coverage_count:
                capability_coverage_count[cap] += 1
    
    # 找出低冗余能力（只有1个队伍覆盖）
    low_redundancy_caps = {cap for cap, count in capability_coverage_count.items() if count <= 1}
    
    if low_redundancy_caps:
        logger.info(f"[贪心-冗余] 低冗余能力: {low_redundancy_caps}，尝试增加备份队伍")
        
        # 最多额外添加2支队伍提高冗余性
        max_redundancy_teams = 2
        added_for_redundancy = 0
        
        for candidate in sorted_candidates:
            if added_for_redundancy >= max_redundancy_teams:
                break
            if candidate["resource_id"] in selected_ids:
                continue
            
            candidate_caps = set(candidate["capabilities"])
            # 检查是否能为低冗余能力提供备份
            can_backup = candidate_caps.intersection(low_redundancy_caps)
            
            if can_backup:
                candidate_capacity = candidate.get("rescue_capacity", 0)
                allocations.append({
                    "resource_id": candidate["resource_id"],
                    "resource_name": candidate["resource_name"],
                    "resource_type": candidate["resource_type"],
                    "assigned_capabilities": list(can_backup),
                    "match_score": candidate["match_score"],
                    "distance_km": candidate["distance_km"],
                    "eta_minutes": candidate.get("eta_minutes", 0),
                    "rescue_capacity": candidate_capacity,
                    "task_start": (event_lng, event_lat),
                    "resource_state": {
                        "current_position": (candidate.get("base_lng", 0), candidate.get("base_lat", 0)),
                        "home_position": (candidate.get("base_lng", 0), candidate.get("base_lat", 0)),
                        "remaining_capacity": float(candidate_capacity),
                        "max_range": 100.0,
                        "current_task_progress": 0.0,
                    },
                })
                selected_ids.add(candidate["resource_id"])
                total_capacity += candidate.get("rescue_capacity", 0)
                max_eta = max(max_eta, candidate.get("eta_minutes", 0))
                total_distance = max(total_distance, candidate["distance_km"])
                added_for_redundancy += 1
                
                # 更新覆盖计数
                for cap in can_backup:
                    capability_coverage_count[cap] += 1
                
                # 重新计算低冗余能力
                low_redundancy_caps = {cap for cap, count in capability_coverage_count.items() if count <= 1}
                
                logger.info(f"[贪心-冗余] 添加备份队伍: {candidate['resource_name']}，为能力{can_backup}提供备份")
        
        if added_for_redundancy > 0:
            logger.info(f"[贪心-冗余] 冗余增强完成，额外添加{added_for_redundancy}支队伍")

    if not allocations:
        return None

    # 计算方案指标
    coverage_rate = len(covered_caps.intersection(required_caps)) / len(required_caps) if required_caps else 1.0
    avg_score = sum(a["match_score"] for a in allocations) / len(allocations)
    capacity_coverage = total_capacity / estimated_trapped if estimated_trapped > 0 else 1.0

    # 未覆盖的能力
    uncovered = required_caps - covered_caps
    
    # 生成容量警告（分级）
    capacity_warning: Optional[str] = None
    if estimated_trapped > 0:
        capacity_gap = estimated_trapped - total_capacity
        if capacity_coverage < 0.5:
            # 严重不足：覆盖率<50%
            capacity_warning = (
                f"🚨 救援容量严重不足！被困{estimated_trapped}人，"
                f"派出队伍总容量仅{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。必须紧急请求国家级增援！"
            )
            logger.error(f"[贪心-严重警告] {capacity_warning}")
        elif capacity_coverage < 0.8:
            # 不足：覆盖率50%-80%
            capacity_warning = (
                f"⚠️ 救援容量不足！被困{estimated_trapped}人，"
                f"派出队伍总容量{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。建议紧急请求省级增援！"
            )
            logger.warning(f"[贪心-警告] {capacity_warning}")
        elif capacity_coverage < 1.0:
            # 轻度不足：覆盖率80%-100%
            capacity_warning = (
                f"⚠ 救援容量存在缺口。被困{estimated_trapped}人，"
                f"派出队伍总容量{total_capacity}人（覆盖率{capacity_coverage*100:.1f}%），"
                f"缺口{capacity_gap}人。建议申请额外增援以确保全员获救。"
            )
            logger.warning(f"[贪心-提示] {capacity_warning}")

    # 计算5维目标值（与NSGA-III对齐）
    success_rate = coverage_rate * avg_score
    time_score = min(max_eta / 120.0, 1.0)
    risk = 1.0 - coverage_rate
    # 冗余性：每个能力被多少队伍覆盖（平均值归一化）
    redundancy = sum(min(c, 2) for c in capability_coverage_count.values()) / (2 * len(required_caps)) if required_caps else 1.0
    
    solution: AllocationSolution = {
        "solution_id": solution_id,
        "allocations": allocations,
        "total_score": round(avg_score, 3),
        "response_time_min": round(max_eta, 1),
        "coverage_rate": round(coverage_rate, 3),
        "resource_scale": len(allocations),
        "risk_level": round(1.0 - coverage_rate, 3),
        "total_rescue_capacity": total_capacity,
        "capacity_coverage_rate": round(capacity_coverage, 3),
        "capacity_warning": capacity_warning,
        # 扩展字段
        "uncovered_capabilities": list(uncovered) if uncovered else [],
        "max_distance_km": round(total_distance, 2),
        "teams_count": len(allocations),
        # 5维优化目标（与NSGA-III对齐）
        "objectives": {
            "success_rate": round(success_rate, 3),
            "response_time": round(time_score, 3),
            "coverage_rate": round(coverage_rate, 3),
            "risk": round(risk, 3),
            "redundancy": round(redundancy, 3),
        },
    }

    # 打印贪心方案汇总
    logger.info(f"【贪心方案-输出】{solution_id} (策略={strategy}):")
    logger.info(f"  - 队伍数: {len(allocations)}支")
    logger.info(f"  - 总救援容量: {total_capacity}人 (覆盖率={capacity_coverage*100:.1f}%)")
    logger.info(f"  - 能力覆盖率: {coverage_rate*100:.1f}%")
    logger.info(f"  - 最大响应时间: {max_eta:.0f}分钟")
    logger.info(f"  - 队伍列表:")
    for a in allocations:
        logger.info(f"    {a['resource_name']}: 能力={a['assigned_capabilities']}, 容量={a.get('rescue_capacity', 0)}")

    return solution


def _deduplicate_solutions(solutions: List[AllocationSolution]) -> List[AllocationSolution]:
    """去重方案（基于分配的队伍ID集合）"""
    seen: set = set()
    unique: List[AllocationSolution] = []

    for sol in solutions:
        team_ids = frozenset(a["resource_id"] for a in sol["allocations"])
        if team_ids not in seen:
            seen.add(team_ids)
            unique.append(sol)

    return unique


def _build_gra_inputs(
    solutions: List[AllocationSolution],
    event_lat: float,
    event_lng: float,
) -> Dict[str, Any]:
    """为 GRA 构造 ResourceState 和 ResourceClaim 输入（基于方案内容）。"""
    # 这里假设 solutions 中的 allocations 包含资源位置与任务起点；若缺失则无法计算成本。
    resources: Dict[str, ResourceState] = {}
    conflicts: List[Dict[str, Any]] = []

    for sol in solutions:
        claims: List[Dict[str, Any]] = []
        for alloc in sol.get("allocations", []):
            task_type = alloc.get("task_type") or alloc.get("task_code") or ""
            # 根据任务类型从优先级映射表获取GRA优先级，未知类型使用默认优先级(3)
            gra_priority: int = GRA_PRIORITY_MAP.get(task_type, GRA_DEFAULT_PRIORITY)
            if not alloc.get("task_start"):
                raise ValueError("缺少任务起点坐标，无法执行GRA仲裁")
            start_position = alloc.get("task_start")
            claims.append({
                "task_id": alloc.get("task_id", alloc.get("task_code", "")),
                "task_name": alloc.get("task_name", ""),
                "resource_id": alloc.get("resource_id"),
                "quantity": 1,
                "start_time": 0,
                "end_time": 999999,
                "priority": alloc.get("priority", 3),
                "is_preemptible": alloc.get("is_preemptible", True),
                "task_type": task_type,
                "gra_priority": gra_priority,
                "start_position": start_position,
            })

            if not alloc.get("resource_id") or not alloc.get("resource_state"):
                raise ValueError("缺少资源状态，无法执行GRA仲裁")

            rs = alloc["resource_state"]
            if "current_position" not in rs or "home_position" not in rs:
                raise ValueError("资源状态缺少位置信息，无法执行GRA仲裁")

            resources[alloc["resource_id"]] = ResourceState(
                resource_id=alloc["resource_id"],
                current_position=tuple(rs.get("current_position")),
                home_position=tuple(rs.get("home_position")),
                remaining_capacity=float(rs.get("remaining_capacity", 0.0)),
                max_range=float(rs.get("max_range", 0.0)),
                current_task_progress=float(rs.get("current_task_progress", 0.0)),
            )

        if len(claims) > 1:
            conflicts.append({
                "id": sol.get("solution_id", ""),
                "resource_id": claims[0].get("resource_id"),
                "claims": claims,
            })

    return {"resources": resources, "conflicts": conflicts}


# ============================================================================
# 地理编码与多救援点处理
# ============================================================================

class GeocodingError(Exception):
    """地理编码异常"""
    def __init__(self, address: str, reason: str = "地理编码失败"):
        self.address = address
        self.reason = reason
        super().__init__(f"{reason}: {address}")


async def resolve_rescue_point_location(
    point: RescuePointInput,
    timeout_seconds: float = 10.0,
) -> Tuple[float, float]:
    """
    解析救援点位置（坐标优先，否则调用高德地理编码）
    
    Args:
        point: 救援点输入
        timeout_seconds: 地理编码超时时间
        
    Returns:
        (latitude, longitude) 元组
        
    Raises:
        GeocodingError: 无坐标且地理编码失败时抛出
    """
    # 坐标优先
    if point.location:
        logger.info(f"救援点'{point.name}'使用输入坐标: ({point.location.latitude}, {point.location.longitude})")
        return (point.location.latitude, point.location.longitude)
    
    # 使用地名进行地理编码
    address = point.address or point.name
    logger.info(f"救援点'{point.name}'开始地理编码: {address}")
    
    try:
        result = await amap_geocode_async(address)
        if result:
            lat, lng = result["latitude"], result["longitude"]
            logger.info(f"救援点'{point.name}'地理编码成功: ({lat}, {lng})")
            return (lat, lng)
        else:
            raise GeocodingError(address, f"高德API返回空结果")
    except GeocodingError:
        raise
    except Exception as e:
        if "timeout" in str(e).lower():
            raise GeocodingError(address, "地理编码服务超时")
        raise GeocodingError(address, f"地理编码异常: {str(e)}")


async def resolve_all_rescue_points(
    points: List[RescuePointInput],
) -> List[ResolvedRescuePoint]:
    """
    批量解析所有救援点位置
    
    Args:
        points: 救援点输入列表
        
    Returns:
        解析后的救援点列表（含坐标）
        
    Raises:
        GeocodingError: 任一救援点地理编码失败时抛出
    """
    resolved: List[ResolvedRescuePoint] = []
    
    for point in points:
        lat, lng = await resolve_rescue_point_location(point)
        resolved.append(ResolvedRescuePoint(
            point_id=str(uuid.uuid4()),
            name=point.name,
            latitude=lat,
            longitude=lng,
            estimated_victims=point.estimated_victims,
            priority=point.priority,
            source="input",
        ))
    
    logger.info(f"成功解析{len(resolved)}个救援点位置")
    return resolved


async def get_rescue_points_from_db(
    event_id: str,
    session: AsyncSession,
) -> List[ResolvedRescuePoint]:
    """
    从数据库加载事件关联的救援点
    
    Args:
        event_id: 事件ID
        session: 数据库会话
        
    Returns:
        救援点列表（可能为空）
    """
    sql = text("""
        SELECT id, name, latitude, longitude, estimated_victims, priority
        FROM operational_v2.rescue_points_v2
        WHERE event_id = :event_id
        ORDER BY priority DESC, created_at
    """)
    
    result = await session.execute(sql, {"event_id": event_id})
    rows = result.fetchall()
    
    points: List[ResolvedRescuePoint] = []
    for row in rows:
        points.append(ResolvedRescuePoint(
            point_id=str(row.id),
            name=row.name,
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            estimated_victims=row.estimated_victims or 0,
            priority=row.priority or "medium",
            source="database",
        ))
    
    logger.info(f"从数据库加载{len(points)}个救援点 (event_id={event_id})")
    return points


def get_rescue_point_from_event_location(
    state: EmergencyAIState,
) -> ResolvedRescuePoint:
    """
    从事件位置创建单一救援点（向后兼容）
    
    Args:
        state: AI状态
        
    Returns:
        基于事件位置的救援点
    """
    location = state["structured_input"].get("location", {})
    lat = location.get("latitude", 0.0)
    lng = location.get("longitude", 0.0)
    
    # 从灾情理解中获取被困人数
    estimated_victims = 0
    if state.get("parsed_disaster"):
        estimated_victims = state["parsed_disaster"].get("estimated_casualties", 0)
    
    return ResolvedRescuePoint(
        point_id=str(uuid.uuid4()),
        name="主救援点",
        latitude=lat,
        longitude=lng,
        estimated_victims=estimated_victims,
        priority="high",
        source="event_location",
    )


async def load_rescue_points(
    state: EmergencyAIState,
    input_points: Optional[List[RescuePointInput]] = None,
) -> List[ResolvedRescuePoint]:
    """
    加载救援点（优先级：输入 > 数据库 > 事件位置）
    
    Args:
        state: AI状态
        input_points: 输入的救援点列表
        
    Returns:
        解析后的救援点列表
    """
    # 1. 优先使用输入的救援点
    if input_points and len(input_points) > 0:
        if len(input_points) > 50:
            raise ValueError(f"救援点数量超过上限: {len(input_points)} > 50")
        return await resolve_all_rescue_points(input_points)
    
    # 2. 从数据库查询
    async with AsyncSessionLocal() as session:
        db_points = await get_rescue_points_from_db(state["event_id"], session)
        if db_points:
            return db_points
    
    # 3. 使用事件位置作为单一救援点
    logger.info("无救援点输入，使用事件位置作为救援点")
    return [get_rescue_point_from_event_location(state)]


async def query_candidates_for_point(
    rescue_point: ResolvedRescuePoint,
    state: EmergencyAIState,
    max_distance_km: float = 100.0,
    max_candidates: int = 20,
) -> List[ResourceCandidate]:
    """
    为单个救援点查询候选队伍
    
    Args:
        rescue_point: 救援点
        state: AI状态
        max_distance_km: 最大搜索距离
        max_candidates: 最多返回候选数
        
    Returns:
        候选队伍列表（按匹配分数排序）
    """
    async with AsyncSessionLocal() as session:
        # 查询队伍并计算距离（基于base_location）
        sql = text("""
            SELECT 
                t.id, 
                t.name as team_name, 
                t.team_type,
                ARRAY_AGG(DISTINCT tc.capability_code) FILTER (WHERE tc.capability_code IS NOT NULL) as capabilities,
                COALESCE(SUM(tc.max_capacity), 10) AS rescue_capacity,
                ST_Distance(
                    t.base_location,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                ) / 1000.0 as distance_km
            FROM operational_v2.rescue_teams_v2 t
            LEFT JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
            WHERE t.status IN ('standby', 'available')
              AND t.base_location IS NOT NULL
              AND ST_DWithin(
                  t.base_location,
                  ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                  :max_dist_m
              )
            GROUP BY t.id, t.name, t.team_type
            ORDER BY distance_km
            LIMIT :limit
        """)
        
        result = await session.execute(sql, {
            "lat": rescue_point["latitude"],
            "lng": rescue_point["longitude"],
            "max_dist_m": max_distance_km * 1000,
            "limit": max_candidates,
        })
        rows = result.fetchall()
        
        candidates: List[ResourceCandidate] = []
        for row in rows:
            # 计算ETA（假设平均速度40km/h）
            eta_min = row.distance_km / 40.0 * 60
            
            # 计算能力匹配分数
            required_caps = [req.get("capability_name", "") for req in state.get("capability_requirements", [])]
            team_caps = list(row.capabilities) if row.capabilities else []
            if required_caps:
                match_count = sum(1 for cap in required_caps if cap in team_caps)
                cap_score = match_count / len(required_caps)
            else:
                cap_score = 1.0
            
            # 综合匹配分数 = 能力匹配 * 距离因子
            distance_factor = max(0, 1 - row.distance_km / max_distance_km)
            match_score = cap_score * 0.6 + distance_factor * 0.4
            
            candidates.append(ResourceCandidate(
                resource_id=str(row.id),
                resource_name=row.team_name,
                resource_type=row.team_type or "rescue",
                capabilities=team_caps,
                distance_km=round(row.distance_km, 2),
                availability_score=1.0,
                match_score=round(match_score, 3),
                rescue_capacity=row.rescue_capacity or 10,
            ))
        
        logger.info(f"救援点'{rescue_point['name']}'找到{len(candidates)}个候选队伍")
        return candidates


async def match_resources_multi_point(
    state: EmergencyAIState,
    input_points: Optional[List[RescuePointInput]] = None,
) -> Dict[str, Any]:
    """
    多救援点资源匹配
    
    为每个救援点查询候选队伍，更新状态中的point_candidates。
    
    Args:
        state: AI状态
        input_points: 输入的救援点（可选）
        
    Returns:
        更新字典，包含 resolved_rescue_points 和 point_candidates
    """
    start_time = time.time()
    
    # 加载救援点
    rescue_points = await load_rescue_points(state, input_points)
    logger.info(f"开始多点资源匹配，共{len(rescue_points)}个救援点")
    
    # 为每个救援点查询候选
    point_candidates: Dict[str, List[ResourceCandidate]] = {}
    for point in rescue_points:
        candidates = await query_candidates_for_point(point, state)
        point_candidates[point["point_id"]] = candidates
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"多点资源匹配完成，耗时{elapsed_ms}ms")
    
    return {
        "resolved_rescue_points": rescue_points,
        "point_candidates": point_candidates,
    }


def optimize_multi_point_allocation(
    state: EmergencyAIState,
    solver_timeout_sec: float = 30.0,
) -> MultiPointAllocationPlan:
    """
    多点位全局优化分配
    
    使用贪心算法为每个救援点分配队伍，约束：每个队伍最多分配到一个救援点。
    
    Args:
        state: AI状态（需包含 resolved_rescue_points 和 point_candidates）
        solver_timeout_sec: 求解超时时间
        
    Returns:
        多点位分配方案
    """
    rescue_points = state.get("resolved_rescue_points", [])
    point_candidates = state.get("point_candidates", {})
    
    if not rescue_points:
        return MultiPointAllocationPlan(
            event_id=state["event_id"],
            total_rescue_points=0,
            assigned_points=0,
            rescue_points=[],
            unassigned_points=[],
            resource_warnings=["无救援点需要分配"],
        )
    
    # 按优先级排序救援点
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_points = sorted(
        rescue_points,
        key=lambda p: (priority_order.get(p["priority"], 2), -p["estimated_victims"])
    )
    
    assigned_teams: set = set()  # 已分配的队伍ID
    point_allocations: List[PointAllocation] = []
    unassigned_points: List[str] = []
    warnings: List[str] = []
    
    for point in sorted_points:
        point_id = point["point_id"]
        candidates = point_candidates.get(point_id, [])
        
        # 过滤已分配的队伍
        available = [c for c in candidates if c["resource_id"] not in assigned_teams]
        
        if not available:
            unassigned_points.append(point_id)
            warnings.append(f"救援点'{point['name']}'无可用队伍")
            continue
        
        # 选择最佳候选（按match_score排序）
        available.sort(key=lambda c: c["match_score"], reverse=True)
        
        # 根据被困人数和队伍容量分配多个队伍
        victims = point["estimated_victims"] or 10
        needed_capacity = victims
        assigned_to_point: List[TeamAllocation] = []
        
        for candidate in available:
            if needed_capacity <= 0:
                break
            
            team_alloc = TeamAllocation(
                team_id=candidate["resource_id"],
                team_name=candidate["resource_name"],
                capabilities=candidate["capabilities"],
                distance_km=candidate["distance_km"],
                eta_minutes=round(candidate["distance_km"] / 40.0 * 60, 1),
                task_description=f"前往{point['name']}执行救援任务",
            )
            assigned_to_point.append(team_alloc)
            assigned_teams.add(candidate["resource_id"])
            needed_capacity -= candidate["rescue_capacity"] or 10
        
        # 计算覆盖状态
        if needed_capacity > 0:
            coverage_status = "partial"
            warnings.append(f"救援点'{point['name']}'救援容量不足，缺口{needed_capacity}人")
        else:
            coverage_status = "full"
        
        # 最长ETA
        max_eta = max((t["eta_minutes"] for t in assigned_to_point), default=0)
        
        point_allocations.append(PointAllocation(
            rescue_point_id=point_id,
            rescue_point_name=point["name"],
            location={"latitude": point["latitude"], "longitude": point["longitude"]},
            estimated_victims=victims,
            priority=point["priority"],
            assigned_teams=assigned_to_point,
            total_eta_minutes=max_eta,
            coverage_status=coverage_status,
        ))
    
    return MultiPointAllocationPlan(
        event_id=state["event_id"],
        total_rescue_points=len(rescue_points),
        assigned_points=len(point_allocations),
        rescue_points=point_allocations,
        unassigned_points=unassigned_points,
        resource_warnings=warnings,
    )
