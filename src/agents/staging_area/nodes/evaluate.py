"""
评估排序节点

职责：
1. 调用StagingAreaService执行核心算法
2. 获取候选点、路径验证、评分排序结果
3. 整合LLM分析结果调整权重（可选）

此节点主要是算法计算，复用现有实现。
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.staging_area.state import StagingAreaAgentState
from src.domains.staging_area.service import StagingAreaService
from src.domains.staging_area.schemas import (
    EarthquakeParams,
    EvaluationWeights,
    RescueTarget,
    StagingConstraints,
    StagingRecommendationRequest,
    TargetPriority,
    TeamInfo,
)

logger = logging.getLogger(__name__)


def _build_dynamic_weights(state: StagingAreaAgentState) -> EvaluationWeights:
    """
    根据LLM分析结果动态构建权重
    
    调整策略：
    1. 安全分析检测到高风险 → 提升 safety 权重
    2. 通信分析检测到问题 → 提升 communication 权重
    3. 地形分析检测到问题 → 适当调整
    """
    # 默认权重
    response_time = 0.35
    safety = 0.25
    logistics = 0.20
    facility = 0.10
    communication = 0.10
    
    # 1. 根据安全分析调整
    safety_assessments = state.get("safety_assessments")
    if safety_assessments:
        high_risk_count = sum(
            1 for sa in safety_assessments 
            if hasattr(sa, 'safety_level') and sa.safety_level in ('high_risk', 'dangerous')
        )
        if high_risk_count > 0:
            # 检测到高风险，提升安全权重
            safety = 0.35
            response_time = 0.25
            logger.info(f"[权重调整] 检测到 {high_risk_count} 个高风险点，提升安全权重至 0.35")
    
    # 2. 根据通信分析调整
    communication_assessments = state.get("communication_assessments")
    if communication_assessments:
        poor_comm_count = sum(
            1 for ca in communication_assessments
            if hasattr(ca, 'primary_network_quality') and ca.primary_network_quality in ('poor', 'none')
        )
        if poor_comm_count > len(communication_assessments) * 0.5:
            # 超过一半候选点通信差，提升通信权重
            communication = 0.15
            logistics = 0.15
            logger.info(f"[权重调整] 检测到 {poor_comm_count} 个通信差的点，提升通信权重至 0.15")
    
    # 3. 根据地形分析调整
    terrain_assessments = state.get("terrain_assessments")
    if terrain_assessments:
        poor_terrain_count = sum(
            1 for ta in terrain_assessments
            if hasattr(ta, 'terrain_suitability') and ta.terrain_suitability == 'poor'
        )
        if poor_terrain_count > len(terrain_assessments) * 0.5:
            # 超过一半候选点地形差，可能需要调整后勤权重（地形影响后勤展开）
            logistics = 0.25
            facility = 0.05
            logger.info(f"[权重调整] 检测到 {poor_terrain_count} 个地形差的点，调整后勤权重至 0.25")
    
    return EvaluationWeights(
        response_time=response_time,
        safety=safety,
        logistics=logistics,
        facility=facility,
        communication=communication,
    )


async def evaluate_candidates(
    state: StagingAreaAgentState,
    db: AsyncSession,
) -> Dict[str, Any]:
    """
    评估排序节点
    
    调用StagingAreaService（遵循调用规范）执行：
    1. 候选点搜索（PostGIS）
    2. 路径验证（A*算法）
    3. 多目标评分排序
    
    Args:
        state: Agent状态
        db: 数据库会话
        
    Returns:
        状态更新字典
    """
    start_time = time.perf_counter()
    
    try:
        # 构建请求参数
        scenario_id = state.get("scenario_id")
        if scenario_id is None:
            return {
                "errors": state.get("errors", []) + ["缺少scenario_id"],
                "timing": {
                    **state.get("timing", {}),
                    "evaluate_ms": int((time.perf_counter() - start_time) * 1000),
                },
            }
        
        # 从state或parsed_disaster获取参数
        epicenter_lon = state.get("epicenter_lon")
        epicenter_lat = state.get("epicenter_lat")
        magnitude = state.get("magnitude")
        
        # 如果LLM解析了灾情，尝试使用解析结果补充
        parsed = state.get("parsed_disaster")
        if parsed and magnitude is None:
            magnitude = parsed.magnitude
        
        if epicenter_lon is None or epicenter_lat is None:
            return {
                "errors": state.get("errors", []) + ["缺少震中坐标"],
                "timing": {
                    **state.get("timing", {}),
                    "evaluate_ms": int((time.perf_counter() - start_time) * 1000),
                },
            }
        
        if magnitude is None:
            magnitude = 6.0  # 默认震级
            logger.warning("[评估节点] 未提供震级，使用默认值6.0")
        
        # 构建救援目标
        rescue_targets_raw = state.get("rescue_targets", [])
        rescue_targets = []
        for t in rescue_targets_raw:
            if isinstance(t, dict):
                rescue_targets.append(RescueTarget(
                    id=UUID(t["id"]) if isinstance(t["id"], str) else t["id"],
                    name=t.get("name", ""),
                    longitude=t["lon"],
                    latitude=t["lat"],
                    priority=TargetPriority(t.get("priority", "medium")),
                ))
        
        if not rescue_targets:
            return {
                "errors": state.get("errors", []) + ["缺少救援目标"],
                "timing": {
                    **state.get("timing", {}),
                    "evaluate_ms": int((time.perf_counter() - start_time) * 1000),
                },
            }
        
        # 构建队伍信息
        team = TeamInfo(
            team_id=state.get("team_id") or UUID("00000000-0000-0000-0000-000000000001"),
            team_name=state.get("team_name", "救援队"),
            base_lon=state.get("team_base_lon", epicenter_lon - 0.1),  # 默认在震中西边
            base_lat=state.get("team_base_lat", epicenter_lat),
        )
        
        # 构建权重（根据LLM分析动态调整）
        weights = _build_dynamic_weights(state)
        logger.info(f"[评估节点] 权重配置: response_time={weights.response_time}, safety={weights.safety}, communication={weights.communication}")
        
        # 构建请求
        request = StagingRecommendationRequest(
            scenario_id=UUID(scenario_id) if isinstance(scenario_id, str) else scenario_id,
            earthquake=EarthquakeParams(
                epicenter_lon=epicenter_lon,
                epicenter_lat=epicenter_lat,
                magnitude=magnitude,
            ),
            rescue_targets=rescue_targets,
            team=team,
            constraints=StagingConstraints(top_n=state.get("top_n", 5)),
            weights=weights,
        )
        
        # 调用Service（遵循调用规范）
        service = StagingAreaService(db)
        result = await service.recommend(request)
        
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        
        if not result.success:
            return {
                "ranked_sites": [],
                "errors": state.get("errors", []) + [result.error or "评估失败"],
                "timing": {**state.get("timing", {}), "evaluate_ms": elapsed_ms},
            }
        
        # 转换为dict以便存入state
        ranked_sites = [
            {
                "site_id": str(site.site_id),
                "site_code": site.site_code,
                "name": site.name,
                "site_type": site.site_type,
                "longitude": site.longitude,
                "latitude": site.latitude,
                "total_score": site.total_score,
                "scores": site.scores,
                "route_from_base_distance_m": site.route_from_base_distance_m,
                "route_from_base_duration_s": site.route_from_base_duration_s,
                "avg_response_time_to_targets_s": site.avg_response_time_to_targets_s,
                "has_water_supply": site.has_water_supply,
                "has_power_supply": site.has_power_supply,
                "can_helicopter_land": site.can_helicopter_land,
            }
            for site in (result.recommended_sites or [])
        ]
        
        logger.info(f"[评估节点] 完成: {len(ranked_sites)} 个推荐, 耗时 {elapsed_ms}ms")
        
        return {
            "ranked_sites": ranked_sites,
            "candidate_sites": ranked_sites,  # 兼容
            "timing": {**state.get("timing", {}), "evaluate_ms": elapsed_ms},
        }
        
    except Exception as e:
        logger.error(f"[评估节点] 异常: {e}", exc_info=True)
        return {
            "ranked_sites": [],
            "errors": state.get("errors", []) + [f"评估异常: {str(e)}"],
            "timing": {
                **state.get("timing", {}),
                "evaluate_ms": int((time.perf_counter() - start_time) * 1000),
            },
        }
