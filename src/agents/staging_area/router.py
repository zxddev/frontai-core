"""
驻扎点选址智能体 API 路由

提供Agent模式的API入口：/api/v2/ai/staging-area
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.agents.staging_area.agent import StagingAreaAgent

logger = logging.getLogger(__name__)


# ============== 请求/响应模型 ==============

class RescueTargetInput(BaseModel):
    """救援目标输入"""
    id: UUID
    lon: float
    lat: float
    name: str = ""
    priority: str = "medium"  # low, medium, high, critical


class StagingAreaAgentRequest(BaseModel):
    """驻扎点选址Agent请求"""
    scenario_id: UUID = Field(description="想定ID")
    epicenter_lon: float = Field(description="震中经度")
    epicenter_lat: float = Field(description="震中纬度")
    magnitude: float = Field(description="震级")
    team_id: UUID = Field(description="队伍ID")
    team_base_lon: float = Field(description="队伍驻地经度")
    team_base_lat: float = Field(description="队伍驻地纬度")
    rescue_targets: List[RescueTargetInput] = Field(description="救援目标列表")
    disaster_description: Optional[str] = Field(
        default=None,
        description="自然语言灾情描述（可选，提供后会使用LLM分析）"
    )
    team_name: str = Field(default="救援队", description="队伍名称")
    top_n: int = Field(default=5, description="返回前N个推荐")
    skip_llm_analysis: bool = Field(
        default=False,
        description="是否跳过LLM分析（True则降级为纯算法模式）"
    )


class SiteExplanationOutput(BaseModel):
    """站点解释输出"""
    site_id: str
    site_name: str
    rank: int
    recommendation_reason: str
    advantages: List[str]
    concerns: List[str]
    confidence: float


class RiskWarningOutput(BaseModel):
    """风险警示输出"""
    warning_type: str
    severity: str
    message: str
    affected_sites: List[str]
    mitigation_advice: Optional[str]


class AlternativeOutput(BaseModel):
    """备选方案输出"""
    scenario: str
    suggested_site_id: str
    suggested_site_name: str
    reason: str


class RecommendedSiteOutput(BaseModel):
    """推荐站点输出"""
    site_id: str
    site_code: Optional[str]
    name: str
    site_type: str
    longitude: float
    latitude: float
    total_score: float
    scores: Dict[str, float]
    route_from_base_distance_m: Optional[float]
    route_from_base_duration_s: Optional[float]
    avg_response_time_to_targets_s: Optional[float]
    has_water_supply: bool
    has_power_supply: bool
    can_helicopter_land: bool


class StagingAreaAgentResponse(BaseModel):
    """驻扎点选址Agent响应"""
    success: bool
    processing_mode: str = Field(description="处理模式: agent, algorithm_only, fallback, error")
    recommended_sites: List[RecommendedSiteOutput] = Field(default_factory=list)
    site_explanations: List[SiteExplanationOutput] = Field(default_factory=list)
    risk_warnings: List[RiskWarningOutput] = Field(default_factory=list)
    alternatives: List[AlternativeOutput] = Field(default_factory=list)
    summary: str = ""
    errors: List[str] = Field(default_factory=list)
    timing: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# ============== 路由 ==============

router = APIRouter(
    prefix="/staging-area",
    tags=["staging-area-agent"],
)


@router.post(
    "",
    response_model=StagingAreaAgentResponse,
    summary="智能驻扎点选址（Agent模式）",
    description="""
    使用LangGraph Agent进行多步分析推理的驻扎点选址。
    
    **Agent流程**：
    1. **灾情理解**（LLM）：解析自然语言描述，提取约束条件
    2. **评估排序**（算法）：候选搜索 + 路径验证 + 多目标评分
    3. **决策解释**（LLM）：生成推荐理由、风险警示、备选方案
    
    **处理模式**：
    - `agent`: 完整LLM分析流程
    - `algorithm_only`: 跳过LLM，纯算法计算
    - `fallback`: LLM失败后降级
    
    **与纯算法API的区别**：
    - 纯算法: `POST /api/v1/staging-area/recommend`
    - Agent: `POST /api/v2/ai/staging-area`（本接口）
    """,
)
async def recommend_staging_site_agent(
    request: StagingAreaAgentRequest,
    db: AsyncSession = Depends(get_db),
) -> StagingAreaAgentResponse:
    """
    智能驻扎点选址（Agent模式）
    """
    try:
        agent = StagingAreaAgent(db)
        
        # 转换救援目标格式
        rescue_targets = [
            {
                "id": str(t.id),
                "lon": t.lon,
                "lat": t.lat,
                "name": t.name,
                "priority": t.priority,
            }
            for t in request.rescue_targets
        ]
        
        result = await agent.recommend(
            scenario_id=request.scenario_id,
            epicenter_lon=request.epicenter_lon,
            epicenter_lat=request.epicenter_lat,
            magnitude=request.magnitude,
            team_id=request.team_id,
            team_base_lon=request.team_base_lon,
            team_base_lat=request.team_base_lat,
            rescue_targets=rescue_targets,
            disaster_description=request.disaster_description,
            team_name=request.team_name,
            top_n=request.top_n,
            skip_llm_analysis=request.skip_llm_analysis,
        )
        
        return StagingAreaAgentResponse(**result)
        
    except Exception as e:
        logger.error(f"[驻扎点Agent API] 异常: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"驻扎点Agent执行失败: {str(e)}",
        )
