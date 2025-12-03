"""侦察目标打分与初始分配节点

职责：
- 从数据库加载指定想定下的风险区域、POI、救援集结点和可用无人设备
- 将各类实体适配为 ScoringContext 列表
- 调用 PriorityScoringEngine 执行打分
- 生成按优先级排序的侦察目标列表
- 按优先级对设备做智能匹配分配（支持规则模式和 CrewAI 专家模式）
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy import text

from src.agents.shared.priority_scoring import (
    EntityType,
    PriorityScoringEngine,
    ScoringContext,
)
from src.agents.reconnaissance.state import (
    DeviceAssignment,
    DeviceInfo,
    ReconState,
    ReconTarget,
)
from src.domains.frontend_api.risk_area.service import RiskAreaService
from src.domains.frontend_api.risk_area.schemas import RiskAreaListResponse
from src.domains.resources.devices.service import DeviceService
from src.domains.resources.devices.schemas import DeviceResponse
from src.infra.config.algorithm_config_service import AlgorithmConfigService
from src.core.database import AsyncSessionLocal


logger = logging.getLogger(__name__)


RULE_CODE_RECON_TARGET = "SCORING_RECON_TARGET_V1"

# 侦察相关能力标签（来自 devices_v2.base_capabilities）
RECON_CAPABILITIES = {
    "aerial_recon",      # 空中侦察
    "ground_recon",      # 地面侦察
    "water_recon",       # 水面侦察
    "3d_mapping",        # 3D建模
    "video_stream",      # 实时视频
    "thermal_imaging",   # 热成像
    "life_detection",    # 生命探测
    "environment_analysis",  # 环境分析
}

# 非侦察能力（仅具备这些能力的设备不适合侦察）
NON_RECON_CAPABILITIES = {
    "cargo_delivery",    # 物资投送
    "cargo_transport",   # 货物运输
    "medical_delivery",  # 医疗投送
    "water_rescue",      # 水上救援
    "search_rescue",     # 搜救
    "communication_relay",  # 通讯组网
}

# 允许侦察的设备类型
RECON_DEVICE_TYPES = {"drone", "dog", "ship"}

# 设备名称关键词（用于 base_capabilities 为空时的回退判断）
RECON_NAME_KEYWORDS = {"侦察", "热成像", "扫图", "建模", "分析"}
NON_RECON_NAME_KEYWORDS = {"投送", "搜救", "救援", "组网", "运输"}


async def score_targets(state: ReconState) -> Dict[str, Any]:
    """为指定想定下的各类目标生成侦察优先级列表并做智能设备分配。

    侦察目标来源：
    - 风险区域 (disaster_affected_areas_v2)
    - 重点设施POI (poi_v2): 学校、医院、化工厂等
    - 救援集结点 (rescue_staging_sites_v2): 需要预先侦察的集结候选点

    实现特点：
    - 规则+结构化字段进行打分，不依赖AI残差
    - 智能设备匹配：根据目标类型选择最适合的设备
    - 不修改数据库，仅读取数据
    """

    scenario_id = state.get("scenario_id")
    event_id = state.get("event_id")
    if not scenario_id:
        return {
            "errors": state.get("errors", []) + ["scenario_id is required for recon scoring"],
            "current_phase": "score_targets_failed",
        }

    logger.info(
        "[Recon] 开始侦察目标打分",
        extra={"scenario_id": scenario_id, "event_id": event_id},
    )

    # 加载风险区域和可用无人设备
    async with AsyncSessionLocal() as session:
        risk_service = RiskAreaService(session)
        device_service = DeviceService(session)

        # 不限想定，加载所有风险区域
        risk_list: RiskAreaListResponse = await risk_service.list_by_scenario(
            scenario_id=None,
            area_type=None,
            min_risk_level=None,
            passage_status=None,
        )

        # 加载所有可用的无人设备（drone/dog/ship），筛选逻辑后置
        all_devices: List[Dict[str, Any]] = []
        device_list: List[DeviceInfo] = []
        try:
            devices: List[DeviceResponse] = await device_service.list_available(
                device_type=None,
                env_type=None,
                not_in_vehicle=False,
            )
            for d in devices:
                if d.device_type.value not in RECON_DEVICE_TYPES:
                    continue
                
                # 保存完整设备信息用于 CrewAI
                device_data = {
                    "device_id": str(d.id),
                    "code": d.code,
                    "name": d.name,
                    "device_type": d.device_type.value,
                    "env_type": d.env_type.value if d.env_type else "unknown",
                    "base_capabilities": d.base_capabilities or [],
                    "applicable_disasters": d.applicable_disasters or [],
                    "forbidden_disasters": d.forbidden_disasters or [],
                    "in_vehicle_id": str(d.in_vehicle_id) if d.in_vehicle_id else None,
                    "status": d.status.value,
                }
                all_devices.append(device_data)
                
                # 基于 base_capabilities 筛选侦察设备
                if _is_recon_device_by_capabilities(device_data):
                    device_list.append(
                        DeviceInfo(
                            device_id=str(d.id),
                            code=d.code,
                            name=d.name,
                            device_type=d.device_type.value,
                            env_type=d.env_type.value if d.env_type else "land",
                            in_vehicle_id=str(d.in_vehicle_id) if d.in_vehicle_id else None,
                            status=d.status.value,
                        )
                    )
            
            logger.info(
                f"[Recon] 加载设备: 总计{len(all_devices)}台, 侦察设备{len(device_list)}台 (基于base_capabilities)"
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[Recon] 加载设备列表失败，将仅输出目标优先级", extra={"error": str(e)})
            all_devices = []
            device_list = []

        # 加载POI (重点设施) - 不限想定，加载所有数据
        pois: List[Dict[str, Any]] = []
        try:
            poi_result = await session.execute(text("""
                SELECT id, name, poi_type, risk_level, 
                       ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat,
                       estimated_population, distance_to_epicenter_m, status,
                       last_reconnaissance_at, reconnaissance_priority
                FROM operational_v2.poi_v2
                WHERE status != 'destroyed'
                ORDER BY reconnaissance_priority DESC, distance_to_epicenter_m ASC
            """))
            for row in poi_result.fetchall():
                pois.append({
                    "id": str(row.id),
                    "name": row.name,
                    "poi_type": row.poi_type,
                    "risk_level": row.risk_level,
                    "lon": row.lon,
                    "lat": row.lat,
                    "estimated_population": row.estimated_population or 0,
                    "distance_to_epicenter_m": float(row.distance_to_epicenter_m or 0),
                    "status": row.status,
                    "last_reconnaissance_at": row.last_reconnaissance_at,
                })
            logger.info(f"[Recon] 加载POI数量: {len(pois)}")
        except Exception as e:  # noqa: BLE001
            logger.warning("[Recon] 加载POI列表失败", extra={"error": str(e)})

        # 加载救援集结点 - 不限想定，加载所有数据
        staging_sites: List[Dict[str, Any]] = []
        try:
            site_result = await session.execute(text("""
                SELECT id, name, site_type, 
                       ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat,
                       max_personnel, status, safety_score
                FROM operational_v2.rescue_staging_sites_v2
                WHERE status = 'available'
                ORDER BY safety_score DESC NULLS LAST
            """))
            for row in site_result.fetchall():
                staging_sites.append({
                    "id": str(row.id),
                    "name": row.name,
                    "site_type": row.site_type,
                    "lon": row.lon,
                    "lat": row.lat,
                    "max_personnel": row.max_personnel or 0,
                    "status": row.status,
                    "safety_score": float(row.safety_score or 50),
                })
            logger.info(f"[Recon] 加载救援集结点数量: {len(staging_sites)}")
        except Exception as e:  # noqa: BLE001
            logger.warning("[Recon] 加载救援集结点列表失败", extra={"error": str(e)})

        # 构造打分上下文
        contexts: List[ScoringContext] = []
        risk_areas: List[Dict[str, Any]] = []
        all_targets_meta: Dict[str, Dict[str, Any]] = {}  # id -> metadata for all target types

        now = datetime.now(timezone.utc)

        for item in risk_list.items:
            # 只对需要侦察或风险较高的区域进行打分
            if not item.reconnaissance_required and item.risk_level < 5:
                continue

            info_age_hours = _compute_info_age_hours(item.last_verified_at, now)
            route_importance = _estimate_route_importance(
                area_type=item.area_type,
                passage_status=item.passage_status,
                passable=item.passable,
            )

            features: Dict[str, Any] = {
                "risk_level": item.risk_level,
                # TODO: 与伤亡/人口估算模块打通后填充真实值
                "population_exposed": 0.0,
                "route_importance": route_importance,
                "info_age_hours": info_age_hours,
                "is_main_corridor": _is_main_corridor_candidate(item.area_type, item.passage_status),
            }

            texts: List[str] = []
            if item.description:
                texts.append(item.description)

            ctx: ScoringContext = {
                "scenario_id": scenario_id,
                "event_id": event_id,
                "entity_type": EntityType.RECON_TARGET,
                "entity_id": str(item.id),
                "features": features,
                "texts": texts,
                "tags": {
                    "area_type": item.area_type,
                    "severity": item.severity,
                    "passage_status": item.passage_status,
                },
            }
            contexts.append(ctx)

            risk_area_data = {
                "id": str(item.id),
                "scenario_id": str(item.scenario_id) if item.scenario_id else None,
                "name": item.name,
                "area_type": item.area_type,
                "geometry": item.geometry_geojson or {},
                "severity": item.severity,
                "risk_level": item.risk_level,
                "passable": item.passable,
                "passable_vehicle_types": item.passable_vehicle_types,
                "speed_reduction_percent": item.speed_reduction_percent,
                "passage_status": item.passage_status,
                "reconnaissance_required": item.reconnaissance_required,
                "description": item.description,
                "started_at": item.started_at,
                "estimated_end_at": item.estimated_end_at,
                "last_verified_at": item.last_verified_at,
                "verified_by": str(item.verified_by) if item.verified_by else None,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "target_type": "risk_area",
            }
            risk_areas.append(risk_area_data)
            all_targets_meta[str(item.id)] = risk_area_data

        # 2. 为POI构造打分上下文
        for poi in pois:
            poi_risk_map = {"critical": 10, "high": 8, "medium": 5, "low": 3, "unknown": 4}
            risk_level = poi_risk_map.get(poi["risk_level"], 5)
            
            info_age_hours = _compute_info_age_hours(poi.get("last_reconnaissance_at"), now)
            
            features: Dict[str, Any] = {
                "risk_level": risk_level,
                "population_exposed": poi.get("estimated_population", 0) / 100,  # 归一化
                "route_importance": 0.5,  # POI默认中等路线重要性
                "info_age_hours": info_age_hours,
                "is_main_corridor": False,
            }
            
            ctx: ScoringContext = {
                "scenario_id": scenario_id,
                "event_id": event_id,
                "entity_type": EntityType.RECON_TARGET,
                "entity_id": poi["id"],
                "features": features,
                "texts": [],
                "tags": {
                    "area_type": f"poi_{poi['poi_type']}",
                    "severity": poi["risk_level"],
                    "poi_type": poi["poi_type"],
                },
            }
            contexts.append(ctx)
            
            poi_meta = {
                **poi,
                "target_type": "poi",
                "geometry": {"type": "Point", "coordinates": [poi["lon"], poi["lat"]]},
            }
            all_targets_meta[poi["id"]] = poi_meta

        # 3. 为救援集结点构造打分上下文（优先级较低，但需要预先侦察）
        for site in staging_sites:
            # 集结点风险等级根据安全评分反推
            risk_level = max(1, 10 - int(site.get("safety_score", 50) / 10))
            
            features: Dict[str, Any] = {
                "risk_level": risk_level,
                "population_exposed": site.get("max_personnel", 0) / 500,  # 潜在人员
                "route_importance": 0.3,  # 集结点路线重要性较低
                "info_age_hours": 24.0,  # 假设需要侦察
                "is_main_corridor": False,
            }
            
            ctx: ScoringContext = {
                "scenario_id": scenario_id,
                "event_id": event_id,
                "entity_type": EntityType.RECON_TARGET,
                "entity_id": site["id"],
                "features": features,
                "texts": [],
                "tags": {
                    "area_type": f"staging_{site['site_type']}",
                    "severity": "low",
                    "site_type": site["site_type"],
                },
            }
            contexts.append(ctx)
            
            site_meta = {
                **site,
                "target_type": "staging_site",
                "geometry": {"type": "Point", "coordinates": [site["lon"], site["lat"]]},
            }
            all_targets_meta[site["id"]] = site_meta

        # 无候选目标时直接返回
        if not contexts:
            logger.info("[Recon] 无需要侦察的目标，返回空结果")
            return {
                "risk_areas": risk_areas,
                "pois": pois,
                "staging_sites": staging_sites,
                "devices": device_list,
                "candidate_targets": [],
                "scored_targets": [],
                "assignments": [],
                "explanation": "当前想定下没有需要侦察的目标。",
                "current_phase": "score_targets_completed",
            }

        # 读取规则并执行打分
        config_service = AlgorithmConfigService(session)
        scoring_engine = PriorityScoringEngine(config_service=config_service)
        scoring_results = await scoring_engine.score_many(contexts, RULE_CODE_RECON_TARGET)

    # 离开session上下文后仅保留纯内存结果（all_targets_meta 已包含所有目标类型）

    targets: List[ReconTarget] = []
    for ctx, res in zip(contexts, scoring_results, strict=False):
        target_id = ctx.get("entity_id") or ""
        meta = all_targets_meta.get(target_id, {})
        target_type = meta.get("target_type", "risk_area")
        
        target: ReconTarget = {
            "target_id": target_id,
            "risk_area_id": target_id if target_type == "risk_area" else None,
            "name": meta.get("name") or target_id,
            "geometry": meta.get("geometry", {}),
            "features": ctx.get("features", {}),
            "score": res.get("score", 0.0),
            "priority": res.get("priority", "medium"),
            "reasons": res.get("reasons", []),
        }
        # 添加额外元数据用于解释生成
        target["_target_type"] = target_type
        target["_poi_type"] = meta.get("poi_type")
        target["_site_type"] = meta.get("site_type")
        target["_area_type"] = meta.get("area_type")
        targets.append(target)

    # 按分数排序
    targets.sort(key=lambda t: t.get("score", 0.0), reverse=True)

    # 智能设备分配：根据目标特征匹配最适合的设备类型
    assignments: List[DeviceAssignment] = []
    used_device_ids: set = set()
    
    for target in targets:
        best_device, reason = _match_device_for_target(
            target=target,
            available_devices=[d for d in device_list if d["device_id"] not in used_device_ids],
            risk_info=all_targets_meta.get(target["target_id"], {}),
        )
        if best_device:
            used_device_ids.add(best_device["device_id"])
            assignments.append(
                DeviceAssignment(
                    device_id=best_device["device_id"],
                    device_name=best_device["name"],
                    device_type=best_device["device_type"],
                    target_id=target["target_id"],
                    target_name=target["name"],
                    priority=target["priority"],
                    reason=reason,
                )
            )

    explanation = _build_explanation(targets, assignments)

    logger.info(
        "[Recon] 侦察目标打分完成",
        extra={
            "scenario_id": scenario_id,
            "targets": len(targets),
            "assignments": len(assignments),
        },
    )

    return {
        "risk_areas": risk_areas,
        "pois": pois,
        "staging_sites": staging_sites,
        "devices": device_list,
        "candidate_targets": targets,
        "scored_targets": targets,
        "assignments": assignments,
        "explanation": explanation,
        "current_phase": "score_targets_completed",
        "trace": {
            "all_devices": all_devices,  # 保存全部设备数据供 CrewAI 节点使用
        },
    }


def _compute_info_age_hours(last_verified_at: datetime | None, now: datetime) -> float:
    """计算情报时效（小时）"""

    if not last_verified_at:
        return 24.0
    try:
        delta = now - last_verified_at.astimezone(now.tzinfo)
        return max(delta.total_seconds() / 3600.0, 0.0)
    except Exception:  # noqa: BLE001
        return 24.0


def _estimate_route_importance(area_type: str, passage_status: str, passable: bool) -> float:
    """粗略估计该风险区域对通行的影响重要性。

    为了避免过度工程，这里采用简单启发式：
    - 高危通行状态 + 不可通行 → 1.0
    - 地震/滑坡/淹没等高危区域 → 0.7
    - 其他情况 → 0.3
    """

    high_block_states = {"confirmed_blocked", "needs_reconnaissance"}
    if not passable and passage_status in high_block_states:
        return 1.0

    corridor_like_types = {
        "danger_zone",
        "blocked",
        "damaged",
        "landslide",
        "flooded",
        "contaminated",
        "seismic_red",
        "seismic_orange",
    }
    if area_type in corridor_like_types:
        return 0.7

    return 0.3


def _is_main_corridor_candidate(area_type: str, passage_status: str) -> bool:
    """是否视为关键通行走廊上的风险点候选。"""

    if passage_status in {"confirmed_blocked", "needs_reconnaissance"} and area_type in {
        "danger_zone",
        "blocked",
        "seismic_red",
    }:
        return True
    return False


# 设备类型到中文名称的映射
DEVICE_TYPE_CN: Dict[str, str] = {
    "drone": "无人机",
    "dog": "机器狗",
    "ship": "无人艇",
    "robot": "机器人",
    "ugv": "无人车",
}

# 目标类型到推荐设备类型的映射（优先级从高到低）
AREA_TYPE_DEVICE_PREFERENCE: Dict[str, List[str]] = {
    # 风险区域类型
    "landslide": ["drone", "dog"],  # 滑坡：无人机航拍全貌 + 机器狗地面探测
    "flooded": ["drone", "ship"],   # 淹没：无人机 + 无人艇
    "seismic_red": ["drone", "dog"],  # 高危地震区：先航拍再地面
    "seismic_orange": ["drone"],
    "contaminated": ["drone", "robot"],  # 污染区：避免人员进入
    "blocked": ["drone", "dog"],
    "danger_zone": ["drone", "dog"],
    "damaged": ["drone"],
    # POI类型
    "poi_hospital": ["drone", "dog"],  # 医院：快速航拍+地面搜救
    "poi_school": ["drone", "dog"],    # 学校：航拍确认人员情况
    "poi_kindergarten": ["drone"],     # 幼儿园
    "poi_chemical_plant": ["drone", "robot"],  # 化工厂：避免人员进入
    "poi_gas_station": ["drone"],      # 加油站：远程侦察
    "poi_reservoir": ["drone", "ship"],  # 水库：空中+水面
    "poi_nursing_home": ["drone", "dog"],  # 养老院：人员搜救
    "poi_substation": ["drone"],       # 变电站
    # 救援集结点类型
    "staging_open_ground": ["drone"],
    "staging_parking_lot": ["drone"],
    "staging_sports_field": ["drone"],
    "staging_school_yard": ["drone"],
    "staging_plaza": ["drone"],
    "staging_logistics_center": ["drone"],
}


def _get_target_env_type(area_type: str, target_type: str) -> str:
    """根据目标类型推断其环境类型
    
    Returns:
        "land" - 陆地目标（默认）
        "sea" - 水域目标（淹没区、水库等）
        "air" - 所有目标都可以空中侦察
    """
    # 水域相关目标
    water_area_types = {
        "flooded",           # 淹没区
        "poi_reservoir",     # 水库
        "poi_dam",           # 大坝
        "poi_river",         # 河流
        "poi_lake",          # 湖泊
    }
    
    if area_type in water_area_types:
        return "sea"
    
    return "land"


def _is_device_env_compatible(device_env: str, target_env: str) -> bool:
    """判断设备环境类型是否与目标兼容
    
    规则：
    - air（无人机）：可以侦察所有环境（陆地、水域都可以从空中看）
    - land（机器狗）：只能侦察陆地目标
    - sea（无人艇）：只能侦察水域目标
    """
    if device_env == "air":
        return True  # 无人机万能
    
    return device_env == target_env


def _match_device_for_target(
    target: ReconTarget,
    available_devices: List[DeviceInfo],
    risk_info: Dict[str, Any],
) -> tuple[DeviceInfo | None, str]:
    """为目标匹配最合适的设备，返回设备和选择理由。
    
    匹配逻辑：
    1. 首先根据目标环境类型过滤兼容的设备
    2. 根据灾害类型确定推荐设备类型顺序
    3. 优先选择推荐类型中可用的设备
    4. 无推荐类型可用时，默认选择无人机（最通用）
    5. 生成人类可读的选择理由
    """
    if not available_devices:
        return None, ""
    
    area_type = risk_info.get("area_type", "")
    target_type = risk_info.get("target_type", "risk_area")
    severity = risk_info.get("severity", "")
    priority = target.get("priority", "medium")
    
    # 推断目标环境类型
    target_env = _get_target_env_type(area_type, target_type)
    
    # 过滤出环境兼容的设备
    compatible_devices = [
        d for d in available_devices
        if _is_device_env_compatible(d.get("env_type", "land"), target_env)
    ]
    
    if not compatible_devices:
        # 没有兼容设备，记录日志并返回空
        logger.debug(
            f"[Recon] 目标 {target.get('name')} (env={target_env}) 无兼容设备"
        )
        return None, ""
    
    # 获取推荐设备类型顺序
    preferred_types = AREA_TYPE_DEVICE_PREFERENCE.get(area_type, ["drone"])
    
    # 按推荐顺序查找可用设备（只从兼容设备中选）
    for device_type in preferred_types:
        for device in compatible_devices:
            if device.get("device_type") == device_type:
                reason = _generate_assignment_reason(
                    device=device,
                    area_type=area_type,
                    severity=severity,
                    priority=priority,
                )
                return device, reason
    
    # 无推荐类型可用，按通用优先级选择：drone > dog > ship > robot
    # 注意：只从兼容设备中选
    fallback_order = ["drone", "dog", "ship", "robot", "ugv"]
    for device_type in fallback_order:
        for device in compatible_devices:
            if device.get("device_type") == device_type:
                reason = "作为通用侦察力量执行任务"
                return device, reason
    
    # 最后兜底：返回第一个兼容设备
    device = compatible_devices[0]
    return device, "执行侦察任务"


def _generate_assignment_reason(
    device: DeviceInfo,
    area_type: str,
    severity: str,
    priority: str,
) -> str:
    """生成设备分配的人类可读理由。"""
    
    device_type = device.get("device_type", "")
    device_type_cn = DEVICE_TYPE_CN.get(device_type, "设备")
    
    # 根据目标类型和设备类型生成理由
    reasons_map = {
        # 风险区域
        ("landslide", "drone"): "可快速航拍滑坡全貌，评估滑坡体规模和二次灾害风险",
        ("landslide", "dog"): "可进入复杂地形探测被困人员生命迹象",
        ("flooded", "drone"): "可从空中侦察淹没范围，定位被困群众位置",
        ("flooded", "ship"): "可在水面机动，近距离探测并辅助救援",
        ("seismic_red", "drone"): "可安全航拍危险建筑，避免人员进入高危区域",
        ("seismic_red", "dog"): "可进入废墟缝隙探测生命迹象",
        ("contaminated", "drone"): "可在污染区上空侦察，无接触风险",
        ("contaminated", "robot"): "可进入污染区采集样本和环境数据",
        ("blocked", "drone"): "可快速确认道路阻断情况和绕行路线",
        ("danger_zone", "drone"): "可从安全距离侦察危险区域态势",
        # POI类型
        ("poi_hospital", "drone"): "可快速航拍医院建筑受损情况，评估医疗救治能力",
        ("poi_hospital", "dog"): "可进入建筑内部搜索被困伤病员",
        ("poi_school", "drone"): "可航拍学校整体受灾情况，确认师生疏散状态",
        ("poi_school", "dog"): "可进入教室搜索被困人员",
        ("poi_kindergarten", "drone"): "可快速确认幼儿园安全状态和人员疏散情况",
        ("poi_chemical_plant", "drone"): "可远程监测化工设施泄漏风险，避免人员暴露",
        ("poi_chemical_plant", "robot"): "可进入化工区采集环境数据，评估污染范围",
        ("poi_gas_station", "drone"): "可远程侦察加油站安全状态，防止爆炸风险",
        ("poi_reservoir", "drone"): "可航拍水库大坝完整性，评估溃坝风险",
        ("poi_reservoir", "ship"): "可近距离检查水位和泄洪设施状态",
        ("poi_nursing_home", "drone"): "可快速确认养老院受损情况和老人疏散状态",
        ("poi_nursing_home", "dog"): "可进入建筑搜索行动不便的被困老人",
        ("poi_substation", "drone"): "可远程检查变电设施损坏情况，确保侦察安全",
        # 救援集结点
        ("staging_open_ground", "drone"): "可航拍空地整体情况，评估驻扎条件和安全性",
        ("staging_parking_lot", "drone"): "可确认停车场通行条件和可用面积",
        ("staging_plaza", "drone"): "可航拍广场周边态势，评估集结点安全性",
    }
    
    specific_reason = reasons_map.get((area_type, device_type))
    if specific_reason:
        return specific_reason
    
    # 通用理由
    generic_reasons = {
        "drone": "可快速获取区域全貌影像，支持态势评估",
        "dog": "可进入复杂地形执行近距离侦察",
        "ship": "可在水域执行侦察和搜救任务",
        "robot": "可执行危险区域的侦察任务",
    }
    
    return generic_reasons.get(device_type, "执行侦察任务")


def _build_explanation(
    targets: List[ReconTarget],
    assignments: List[DeviceAssignment],
) -> str:
    """构造指挥员友好的中文解释文本。"""

    if not targets:
        return "当前没有需要优先侦察的目标。"

    lines: List[str] = []
    
    # 统计信息
    priority_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    type_counts = {"risk_area": 0, "poi": 0, "staging_site": 0}
    for t in targets:
        p = t.get("priority", "medium")
        priority_counts[p] = priority_counts.get(p, 0) + 1
        tt = t.get("_target_type", "risk_area")
        type_counts[tt] = type_counts.get(tt, 0) + 1
    
    # 开头概述
    summary_parts = []
    if priority_counts["critical"]:
        summary_parts.append(f"紧急{priority_counts['critical']}处")
    if priority_counts["high"]:
        summary_parts.append(f"高优先{priority_counts['high']}处")
    if priority_counts["medium"] + priority_counts["low"]:
        summary_parts.append(f"一般{priority_counts['medium'] + priority_counts['low']}处")
    
    type_parts = []
    if type_counts.get("risk_area"):
        type_parts.append(f"风险区域{type_counts['risk_area']}个")
    if type_counts.get("poi"):
        type_parts.append(f"重点设施{type_counts['poi']}个")
    if type_counts.get("staging_site"):
        type_parts.append(f"集结点{type_counts['staging_site']}个")
    
    lines.append(f"【侦察任务概况】共识别{len(targets)}个侦察目标（{', '.join(summary_parts)}），"
                 f"包含{', '.join(type_parts)}。已分配{len(assignments)}台无人设备。")
    lines.append("")
    
    # 按优先级分组展示分配方案
    if assignments:
        lines.append("【设备分配方案】")
        
        # 按优先级排序
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_assignments = sorted(
            assignments, 
            key=lambda a: priority_order.get(a.get("priority", "medium"), 99)
        )
        
        # 找到对应target以获取类型信息
        target_map = {t.get("target_id"): t for t in targets}
        
        for idx, a in enumerate(sorted_assignments, start=1):
            priority = a.get("priority", "medium")
            priority_cn = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}.get(priority, "")
            device_type_cn = DEVICE_TYPE_CN.get(a.get("device_type", ""), "设备")
            
            # 获取目标类型标签
            target = target_map.get(a.get("target_id"), {})
            target_type = target.get("_target_type", "risk_area")
            type_label = {"risk_area": "风险区", "poi": "重点设施", "staging_site": "集结点"}.get(target_type, "")
            
            lines.append(f"{idx}. 【{priority_cn}】{a.get('target_name', '')}（{type_label}）")
            lines.append(f"   派出：{a.get('device_name', '')}（{device_type_cn}）")
            lines.append(f"   理由：{a.get('reason', '')}")
            lines.append("")
    
    # 未分配设备的目标
    assigned_target_ids = {a.get("target_id") for a in assignments}
    unassigned = [t for t in targets if t.get("target_id") not in assigned_target_ids]
    if unassigned:
        lines.append("【待分配目标】以下目标暂无可用设备：")
        for t in unassigned[:5]:
            target_type = t.get("_target_type", "risk_area")
            type_label = {"risk_area": "风险区", "poi": "重点设施", "staging_site": "集结点"}.get(target_type, "")
            lines.append(f"  - {t.get('name', '')}（{type_label}, {t.get('priority', '')}）")

    return "\n".join(lines)


def _is_recon_device_by_capabilities(device_data: Dict[str, Any]) -> bool:
    """基于 base_capabilities 判断设备是否适合侦察任务
    
    判断逻辑：
    1. 如果有 base_capabilities：
       - 包含任一侦察能力 → 适合侦察
       - 仅包含非侦察能力 → 不适合
    2. 如果 base_capabilities 为空：
       - 根据名称关键词判断（回退逻辑）
    """
    capabilities = set(device_data.get("base_capabilities") or [])
    name = device_data.get("name", "")
    
    if capabilities:
        # 有能力标签，检查是否包含侦察能力
        has_recon = bool(capabilities & RECON_CAPABILITIES)
        only_non_recon = capabilities.issubset(NON_RECON_CAPABILITIES)
        
        if has_recon:
            return True
        if only_non_recon:
            return False
        # 有未知能力但无侦察能力，回退到名称判断
    
    # 回退：根据名称关键词判断
    if any(kw in name for kw in NON_RECON_NAME_KEYWORDS):
        return False
    if any(kw in name for kw in RECON_NAME_KEYWORDS):
        return True
    
    # 默认不认为是侦察设备
    return False


__all__ = ["score_targets"]
