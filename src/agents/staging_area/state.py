"""
驻扎点选址智能体状态定义

使用TypedDict定义Graph State，遵循LangGraph 1.0规范。
"""
from __future__ import annotations

from typing import List, Optional, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Pydantic模型（用于LLM输出校验） ==============

class ParsedConstraint(BaseModel):
    """从灾情描述中提取的约束条件"""
    constraint_type: str = Field(description="约束类型: road_blocked, area_flooded, communication_down, etc.")
    description: str = Field(description="约束描述")
    location_hint: Optional[str] = Field(default=None, description="位置提示")
    severity: str = Field(default="medium", description="严重程度: low, medium, high, critical")
    confidence: float = Field(default=0.8, description="置信度 0-1")


class ParsedDisasterInfo(BaseModel):
    """解析后的灾情信息"""
    disaster_type: str = Field(description="灾害类型: earthquake, flood, etc.")
    epicenter_description: Optional[str] = Field(default=None, description="震中位置描述")
    magnitude: Optional[float] = Field(default=None, description="震级")
    affected_area_description: Optional[str] = Field(default=None, description="影响范围描述")
    key_concerns: List[str] = Field(default_factory=list, description="主要关切点")
    extracted_constraints: List[ParsedConstraint] = Field(default_factory=list, description="提取的约束条件")


class TerrainAssessment(BaseModel):
    """地形评估结果"""
    site_id: UUID
    site_name: str
    terrain_suitability: str = Field(description="适宜性: excellent, good, fair, poor")
    slope_assessment: str = Field(description="坡度评估")
    stability_assessment: str = Field(description="稳定性评估")
    expansion_space: str = Field(description="展开空间评估")
    terrain_risks: List[str] = Field(default_factory=list, description="地形风险")
    confidence: float = Field(default=0.8)


class CommunicationAssessment(BaseModel):
    """通信评估结果"""
    site_id: UUID
    site_name: str
    primary_network_quality: str = Field(description="主网络质量: excellent, good, fair, poor, none")
    backup_options: List[str] = Field(default_factory=list, description="备用通信方案")
    communication_risks: List[str] = Field(default_factory=list, description="通信风险")
    recommended_equipment: List[str] = Field(default_factory=list, description="建议携带设备")
    confidence: float = Field(default=0.8)


class SafetyAssessment(BaseModel):
    """安全评估结果"""
    site_id: UUID
    site_name: str
    safety_level: str = Field(description="安全等级: safe, moderate_risk, high_risk, dangerous")
    secondary_hazard_risks: List[str] = Field(default_factory=list, description="次生灾害风险")
    aftershock_impact: str = Field(description="余震影响评估")
    evacuation_feasibility: str = Field(description="撤离可行性")
    safety_warnings: List[str] = Field(default_factory=list, description="安全警告")
    confidence: float = Field(default=0.8)


class RiskWarning(BaseModel):
    """风险警示"""
    warning_type: str = Field(description="警告类型: secondary_hazard, route_blocked, communication_down, etc.")
    severity: str = Field(description="严重程度: info, warning, critical")
    message: str = Field(description="警告消息")
    affected_sites: List[str] = Field(default_factory=list, description="受影响站点")
    mitigation_advice: Optional[str] = Field(default=None, description="缓解建议")


class SiteExplanation(BaseModel):
    """站点推荐解释"""
    site_id: UUID
    site_name: str
    rank: int
    recommendation_reason: str = Field(description="推荐理由")
    advantages: List[str] = Field(default_factory=list, description="优势")
    concerns: List[str] = Field(default_factory=list, description="需注意事项")
    confidence: float = Field(default=0.8)


class AlternativeSuggestion(BaseModel):
    """备选方案建议"""
    scenario: str = Field(description="适用场景")
    suggested_site_id: UUID
    suggested_site_name: str
    reason: str = Field(description="建议理由")


# ============== TypedDict State ==============

class StagingAreaAgentState(TypedDict, total=False):
    """
    驻扎点选址智能体状态
    
    遵循LangGraph 1.0 TypedDict规范
    """
    # ===== 输入 =====
    # 自然语言灾情描述（Agent模式必需）
    disaster_description: str
    
    # 结构化输入（可选，若提供则跳过LLM解析）
    scenario_id: Optional[UUID]
    epicenter_lon: Optional[float]
    epicenter_lat: Optional[float]
    magnitude: Optional[float]
    team_id: Optional[UUID]
    team_base_lon: Optional[float]
    team_base_lat: Optional[float]
    team_name: Optional[str]
    rescue_targets: Optional[List[dict]]  # [{id, lon, lat, name, priority}]
    
    # 配置
    skip_llm_analysis: bool  # True则跳过LLM分析，直接用算法
    top_n: int  # 返回前N个推荐
    
    # ===== LLM分析结果 =====
    # 灾情理解节点输出
    parsed_disaster: Optional[ParsedDisasterInfo]
    
    # 地形分析节点输出
    terrain_assessments: Optional[List[TerrainAssessment]]
    
    # 通信分析节点输出
    communication_assessments: Optional[List[CommunicationAssessment]]
    
    # 安全分析节点输出
    safety_assessments: Optional[List[SafetyAssessment]]
    
    # ===== 算法计算结果 =====
    # 候选点列表（来自PostGIS查询）
    candidate_sites: Optional[List[dict]]
    
    # 路径验证结果（来自A*算法）
    route_results: Optional[dict]
    
    # 评分排序结果（来自Core算法）
    ranked_sites: Optional[List[dict]]
    
    # ===== 输出 =====
    # 决策解释
    site_explanations: Optional[List[SiteExplanation]]
    
    # 风险警示
    risk_warnings: Optional[List[RiskWarning]]
    
    # 备选方案
    alternatives: Optional[List[AlternativeSuggestion]]
    
    # 最终响应摘要
    summary: Optional[str]
    
    # ===== 元数据 =====
    # 处理模式：agent / fallback
    processing_mode: str
    
    # 置信度
    overall_confidence: float
    
    # 错误信息
    errors: List[str]
    
    # 各阶段耗时
    timing: dict
