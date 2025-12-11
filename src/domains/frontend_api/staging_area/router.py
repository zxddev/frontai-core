"""
驻扎点选址前端适配API

接口路径: /staging-area/*
提供安全点位查找接口
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.domains.staging_area.repository import StagingAreaRepository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staging-area", tags=["前端-驻扎点选址"])


# ============== 请求/响应模型 ==============

class SafePointConstraintsRequest(BaseModel):
    """安全点位筛选约束"""
    min_buffer_m: float = Field(default=500.0, description="距危险区最小缓冲距离(m)")
    max_slope_deg: float = Field(default=15.0, description="最大坡度(度)")
    min_area_m2: Optional[float] = Field(default=None, description="最小面积要求(m²)")
    require_water_supply: bool = Field(default=False, description="是否要求水源")
    require_power_supply: bool = Field(default=False, description="是否要求电源")
    require_helicopter_landing: bool = Field(default=False, description="是否要求直升机起降")
    require_ground_stability: Optional[str] = Field(default=None, description="地面稳定性要求")
    require_network_type: Optional[str] = Field(default=None, description="通信网络类型要求")
    max_distance_to_supply_m: Optional[float] = Field(default=None, description="距补给点最大距离(m)")
    max_distance_to_medical_m: Optional[float] = Field(default=None, description="距医疗点最大距离(m)")
    site_types: Optional[List[str]] = Field(default=None, description="限定场地类型列表")


class FindSafePointRequestV1(BaseModel):
    """安全点位查找请求"""
    scenario_id: UUID = Field(..., description="想定ID")
    center_lon: float = Field(..., description="搜索中心经度")
    center_lat: float = Field(..., description="搜索中心纬度")
    search_radius_m: float = Field(default=30000.0, description="搜索半径(m)")
    constraints: SafePointConstraintsRequest = Field(default_factory=SafePointConstraintsRequest, description="筛选约束条件")
    top_n: int = Field(default=3, description="返回前N个结果")

    # Agent模式可选参数
    use_agent: bool = Field(default=True, description="是否使用Agent模式（LLM分析+推荐理由）")
    disaster_description: Optional[str] = Field(default=None, description="灾情描述（自然语言）")
    magnitude: Optional[float] = Field(default=6.0, description="震级")
    team_id: Optional[UUID] = Field(default=None, description="队伍ID")
    team_name: Optional[str] = Field(default="救援队", description="队伍名称")
    team_base_lon: Optional[float] = Field(default=None, description="队伍驻地经度")
    team_base_lat: Optional[float] = Field(default=None, description="队伍驻地纬度")
    rescue_targets: Optional[List[Dict]] = Field(default=None, description="救援目标列表")


class SafePointFacilitiesResponse(BaseModel):
    """安全点位设施信息"""
    hasWater: bool = Field(alias="hasWater")
    hasPower: bool = Field(alias="hasPower")
    canHelicopter: bool = Field(alias="canHelicopter")
    networkType: str = Field(alias="networkType")
    groundStability: str = Field(alias="groundStability")

    class Config:
        populate_by_name = True


class ScoreBreakdownResponse(BaseModel):
    """
    评分详情响应

    基于 GIS-AHP-TOPSIS 多准则决策方法的5维度评分
    """
    hazardRisk: float = Field(alias="hazardRisk", description="灾害风险评分 (0-1)，权重35%")
    terrain: float = Field(description="地形安全评分 (0-1)，权重25%")
    accessibility: float = Field(description="可达性评分 (0-1)，权重20%")
    facility: float = Field(description="设施条件评分 (0-1)，权重15%")
    communication: float = Field(description="通信质量评分 (0-1)，权重5%")

    class Config:
        populate_by_name = True


class HazardDistancesResponse(BaseModel):
    """
    到各类灾害区的距离响应

    分类记录到不同类型灾害区域的最近距离(m)
    """
    landslide: Optional[float] = Field(None, description="距滑坡区距离(m)")
    debrisFlow: Optional[float] = Field(None, alias="debrisFlow", description="距泥石流区距离(m)")
    flooded: Optional[float] = Field(None, description="距洪水区距离(m)")
    fire: Optional[float] = Field(None, description="距火灾区距离(m)")
    dammedLake: Optional[float] = Field(None, alias="dammedLake", description="距堰塞湖影响区距离(m)")
    otherDanger: Optional[float] = Field(None, alias="otherDanger", description="距其他危险区距离(m)")

    class Config:
        populate_by_name = True


class SafePointResultResponse(BaseModel):
    """安全点位结果"""
    siteId: UUID = Field(alias="siteId")
    siteCode: str = Field(alias="siteCode")
    name: str
    longitude: float
    latitude: float
    siteType: str = Field(alias="siteType")
    areaM2: Optional[float] = Field(alias="areaM2")
    slopeDegree: Optional[float] = Field(alias="slopeDegree")
    distanceM: float = Field(alias="distanceM", description="距搜索中心距离(m)")
    distanceToDangerM: Optional[float] = Field(alias="distanceToDangerM", description="距危险区距离(m)")
    score: float = Field(description="综合评分 0-1")
    facilities: SafePointFacilitiesResponse
    nearestSupplyDepotM: Optional[float] = Field(alias="nearestSupplyDepotM")
    nearestMedicalPointM: Optional[float] = Field(alias="nearestMedicalPointM")

    # 新增字段 - 评分详情和风险提示
    scoreBreakdown: Optional[ScoreBreakdownResponse] = Field(
        None,
        alias="scoreBreakdown",
        description="各维度评分详情"
    )
    riskWarnings: List[str] = Field(
        default_factory=list,
        alias="riskWarnings",
        description="风险提示列表"
    )
    hazardDistances: Optional[HazardDistancesResponse] = Field(
        None,
        alias="hazardDistances",
        description="到各类灾害区的距离"
    )

    class Config:
        populate_by_name = True


class SiteExplanationResponse(BaseModel):
    """站点推荐理由响应"""
    siteId: str = Field(alias="siteId", description="站点ID")
    siteName: str = Field(alias="siteName", description="站点名称")
    rank: int = Field(description="推荐排名")
    recommendationReason: str = Field(alias="recommendationReason", description="推荐理由")
    advantages: List[str] = Field(default_factory=list, description="优势列表")
    concerns: List[str] = Field(default_factory=list, description="注意事项")
    confidence: float = Field(default=0.8, description="置信度")

    class Config:
        populate_by_name = True


class RiskWarningResponse(BaseModel):
    """风险警示响应"""
    warningType: str = Field(alias="warningType", description="警告类型")
    severity: str = Field(description="严重程度: critical/warning/info")
    message: str = Field(description="警告消息")
    affectedSites: List[str] = Field(default_factory=list, alias="affectedSites", description="受影响的站点")
    mitigationAdvice: Optional[str] = Field(None, alias="mitigationAdvice", description="缓解建议")

    class Config:
        populate_by_name = True


class AlternativeSuggestionResponse(BaseModel):
    """备选方案响应"""
    scenario: str = Field(description="场景描述")
    suggestedSiteId: Optional[str] = Field(None, alias="suggestedSiteId", description="建议的站点ID")
    suggestedSiteName: Optional[str] = Field(None, alias="suggestedSiteName", description="建议的站点名称")
    reason: str = Field(description="建议理由")

    class Config:
        populate_by_name = True


class FindSafePointDataResponse(BaseModel):
    """安全点位查找数据响应"""
    sites: List[SafePointResultResponse]
    totalCandidates: int = Field(alias="totalCandidates")
    elapsedMs: int = Field(alias="elapsedMs")

    # Agent模式增强字段
    explanations: Optional[List[SiteExplanationResponse]] = Field(
        None,
        description="推荐理由列表（Agent模式）"
    )
    riskWarnings: Optional[List[RiskWarningResponse]] = Field(
        None,
        alias="riskWarnings",
        description="风险警示列表（Agent模式）"
    )
    alternatives: Optional[List[AlternativeSuggestionResponse]] = Field(
        None,
        description="备选方案列表（Agent模式）"
    )
    summary: Optional[str] = Field(
        None,
        description="总体推荐摘要（Agent模式）"
    )
    processingMode: str = Field(
        default="algorithm",
        alias="processingMode",
        description="处理模式: agent/algorithm/fallback"
    )

    class Config:
        populate_by_name = True


# ============== 路由 ==============

@router.post("/find-safe-point", response_model=ApiResponse[FindSafePointDataResponse])
async def find_safe_point(
    request: FindSafePointRequestV1,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    查找安全点位

    支持两种模式：
    1. **Agent模式** (use_agent=True, 默认): LLM分析 + 算法计算 + 推荐理由生成
    2. **算法模式** (use_agent=False): 纯算法计算，快速但无推荐理由

    **Agent模式功能**：
    - 灾情理解：LLM解析灾情描述
    - 地形分析：评估候选点地形适宜性
    - 通信分析：评估通信条件
    - 安全分析：综合评估安全风险
    - 推荐理由：生成自然语言推荐理由

    **评分维度**（基于 GIS-AHP-TOPSIS 方法）：
    - 灾害风险 (50%): 距各类灾害区的安全距离
    - 地形安全 (20%): 坡度、地面稳定性、高程
    - 可达性 (15%): 距道路、医疗点、补给点距离
    - 设施条件 (10%): 水电、直升机、面积
    - 通信质量 (5%): 网络类型、信号质量

    **返回**：按综合评分排序的安全点位列表，附带评分详情、推荐理由和风险警示
    """
    start_time = time.perf_counter()
    logger.info(
        f"[安全点位API] 开始查询: scenario={request.scenario_id}, "
        f"center=({request.center_lon}, {request.center_lat}), "
        f"radius={request.search_radius_m}m, top_n={request.top_n}, "
        f"use_agent={request.use_agent}"
    )

    try:
        # 根据use_agent选择处理模式
        if request.use_agent:
            return await _find_safe_point_with_agent(request, db, start_time)
        else:
            return await _find_safe_point_algorithm_only(request, db, start_time)

    except Exception as e:
        logger.exception(f"[安全点位API] 查询失败: {e}")
        return ApiResponse.error(500, f"查找安全点位失败: {str(e)}")


async def _find_safe_point_with_agent(
    request: FindSafePointRequestV1,
    db: AsyncSession,
    start_time: float,
) -> ApiResponse:
    """
    使用Agent模式查找安全点位（LLM分析 + 推荐理由）
    """
    from uuid import uuid4
    from src.agents.staging_area.agent import StagingAreaAgent

    logger.info("[安全点位API] 使用Agent模式")

    # 准备参数
    team_id = request.team_id or uuid4()
    team_base_lon = request.team_base_lon or request.center_lon
    team_base_lat = request.team_base_lat or request.center_lat
    rescue_targets = request.rescue_targets or []

    # 构建灾情描述
    disaster_description = request.disaster_description
    if not disaster_description:
        disaster_description = f"震中位于({request.center_lon:.4f}, {request.center_lat:.4f})，震级{request.magnitude or 6.0}级"

    # 调用Agent
    agent = StagingAreaAgent(db)
    result = await agent.recommend(
        scenario_id=request.scenario_id,
        epicenter_lon=request.center_lon,
        epicenter_lat=request.center_lat,
        magnitude=request.magnitude or 6.0,
        team_id=team_id,
        team_base_lon=team_base_lon,
        team_base_lat=team_base_lat,
        rescue_targets=rescue_targets,
        disaster_description=disaster_description,
        team_name=request.team_name or "救援队",
        top_n=request.top_n,
        skip_llm_analysis=False,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    # 转换Agent返回的结果为API响应格式
    sites_response = []
    for site in result.get("recommended_sites", []):
        # 构建评分详情
        score_breakdown = site.get("score_breakdown") or site.get("scores", {})
        score_breakdown_response = None
        if score_breakdown:
            score_breakdown_response = ScoreBreakdownResponse(
                hazardRisk=score_breakdown.get("hazard_risk", score_breakdown.get("safety", 0)),
                terrain=score_breakdown.get("terrain", 0),
                accessibility=score_breakdown.get("accessibility", score_breakdown.get("response_time", 0)),
                facility=score_breakdown.get("facility", score_breakdown.get("logistics", 0)),
                communication=score_breakdown.get("communication", 0),
            )

        sites_response.append(SafePointResultResponse(
            siteId=site.get("site_id", ""),
            siteCode=site.get("site_code", ""),
            name=site.get("name", ""),
            longitude=site.get("longitude", 0),
            latitude=site.get("latitude", 0),
            siteType=site.get("site_type", "other"),
            areaM2=site.get("area_m2"),
            slopeDegree=site.get("slope_degree"),
            distanceM=site.get("distance_to_epicenter_m", site.get("distance_m", 0)),
            distanceToDangerM=site.get("distance_to_danger_m"),
            score=site.get("total_score", site.get("score", 0)),
            facilities=SafePointFacilitiesResponse(
                hasWater=site.get("has_water_supply", False),
                hasPower=site.get("has_power_supply", False),
                canHelicopter=site.get("can_helicopter_land", False),
                networkType=site.get("primary_network_type", "none"),
                groundStability=site.get("ground_stability", "unknown"),
            ),
            nearestSupplyDepotM=site.get("nearest_supply_depot_m"),
            nearestMedicalPointM=site.get("nearest_medical_point_m"),
            scoreBreakdown=score_breakdown_response,
            riskWarnings=site.get("risk_warnings", []),
            hazardDistances=None,
        ))

    # 转换推荐理由
    explanations_response = []
    for exp in result.get("site_explanations", []):
        explanations_response.append(SiteExplanationResponse(
            siteId=str(exp.get("site_id", "")),
            siteName=exp.get("site_name", ""),
            rank=exp.get("rank", 0),
            recommendationReason=exp.get("recommendation_reason", ""),
            advantages=exp.get("advantages", []),
            concerns=exp.get("concerns", []),
            confidence=exp.get("confidence", 0.8),
        ))

    # 转换风险警示
    risk_warnings_response = []
    for warn in result.get("risk_warnings", []):
        risk_warnings_response.append(RiskWarningResponse(
            warningType=warn.get("warning_type", "unknown"),
            severity=warn.get("severity", "info"),
            message=warn.get("message", ""),
            affectedSites=warn.get("affected_sites", []),
            mitigationAdvice=warn.get("mitigation_advice"),
        ))

    # 转换备选方案
    alternatives_response = []
    for alt in result.get("alternatives", []):
        alternatives_response.append(AlternativeSuggestionResponse(
            scenario=alt.get("scenario", ""),
            suggestedSiteId=alt.get("suggested_site_id"),
            suggestedSiteName=alt.get("suggested_site_name"),
            reason=alt.get("reason", ""),
        ))

    data = FindSafePointDataResponse(
        sites=sites_response,
        totalCandidates=len(sites_response),
        elapsedMs=elapsed_ms,
        explanations=explanations_response if explanations_response else None,
        riskWarnings=risk_warnings_response if risk_warnings_response else None,
        alternatives=alternatives_response if alternatives_response else None,
        summary=result.get("summary"),
        processingMode=result.get("processing_mode", "agent"),
    )

    logger.info(
        f"[安全点位API] Agent模式完成: 返回 {len(sites_response)} 个点位, "
        f"推荐理由 {len(explanations_response)} 条, 耗时 {elapsed_ms}ms"
    )

    return ApiResponse.success(data.model_dump(by_alias=True))


async def _find_safe_point_algorithm_only(
    request: FindSafePointRequestV1,
    db: AsyncSession,
    start_time: float,
) -> ApiResponse:
    """
    使用纯算法模式查找安全点位（快速，无LLM）
    """
    logger.info("[安全点位API] 使用算法模式")

    repo = StagingAreaRepository(db)
    constraints = request.constraints

    sites = await repo.find_safe_points(
        scenario_id=request.scenario_id,
        center_lon=request.center_lon,
        center_lat=request.center_lat,
        search_radius_m=request.search_radius_m,
        min_buffer_m=constraints.min_buffer_m,
        max_slope_deg=constraints.max_slope_deg,
        min_area_m2=constraints.min_area_m2,
        require_water=constraints.require_water_supply,
        require_power=constraints.require_power_supply,
        require_helicopter=constraints.require_helicopter_landing,
        require_ground_stability=constraints.require_ground_stability,
        require_network_type=constraints.require_network_type,
        max_distance_to_supply_m=constraints.max_distance_to_supply_m,
        max_distance_to_medical_m=constraints.max_distance_to_medical_m,
        site_types=constraints.site_types,
        top_n=request.top_n,
    )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    results = []
    for s in sites:
        # 构建评分详情响应
        score_breakdown_data = s.get("score_breakdown")
        score_breakdown_response = None
        if score_breakdown_data:
            score_breakdown_response = ScoreBreakdownResponse(
                hazardRisk=score_breakdown_data.get("hazard_risk", 0),
                terrain=score_breakdown_data.get("terrain", 0),
                accessibility=score_breakdown_data.get("accessibility", 0),
                facility=score_breakdown_data.get("facility", 0),
                communication=score_breakdown_data.get("communication", 0),
            )

        # 构建灾害距离响应
        hazard_distances_data = s.get("hazard_distances")
        hazard_distances_response = None
        if hazard_distances_data:
            hazard_distances_response = HazardDistancesResponse(
                landslide=hazard_distances_data.get("landslide"),
                debrisFlow=hazard_distances_data.get("debris_flow"),
                flooded=hazard_distances_data.get("flooded"),
                fire=hazard_distances_data.get("fire"),
                dammedLake=hazard_distances_data.get("dammed_lake"),
                otherDanger=hazard_distances_data.get("other_danger"),
            )

        results.append(SafePointResultResponse(
            siteId=s["site_id"],
            siteCode=s["site_code"],
            name=s["name"],
            longitude=s["longitude"],
            latitude=s["latitude"],
            siteType=s["site_type"],
            areaM2=s["area_m2"],
            slopeDegree=s["slope_degree"],
            distanceM=s["distance_m"],
            distanceToDangerM=s["distance_to_danger_m"],
            score=s["score"],
            facilities=SafePointFacilitiesResponse(
                hasWater=s["has_water_supply"],
                hasPower=s["has_power_supply"],
                canHelicopter=s["can_helicopter_land"],
                networkType=s["primary_network_type"],
                groundStability=s["ground_stability"],
            ),
            nearestSupplyDepotM=s["nearest_supply_depot_m"],
            nearestMedicalPointM=s["nearest_medical_point_m"],
            scoreBreakdown=score_breakdown_response,
            riskWarnings=s.get("risk_warnings", []),
            hazardDistances=hazard_distances_response,
        ))

    data = FindSafePointDataResponse(
        sites=results,
        totalCandidates=len(results),
        elapsedMs=elapsed_ms,
        processingMode="algorithm",
    )

    logger.info(
        f"[安全点位API] 算法模式完成: 返回 {len(results)} 个点位, 耗时 {elapsed_ms}ms"
    )

    return ApiResponse.success(data.model_dump(by_alias=True))
