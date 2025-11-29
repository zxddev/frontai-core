"""State definition for Overall Plan Generation workflow.

This module defines the TypedDict state that flows through the LangGraph workflow,
containing all 9 modules, HITL review status, and error tracking.
"""

from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class BasicDisasterValue(TypedDict, total=False):
    """Structured output for Module 0 - Basic Disaster Situation."""

    disaster_name: str
    disaster_type: str
    occurrence_time: str
    magnitude: float | None
    epicenter_depth_km: float | None
    affected_area: str
    affected_scope_km2: float | None
    deaths: int
    injuries: int
    missing: int
    trapped: int
    buildings_collapsed: int
    buildings_damaged: int
    infrastructure_damage: str


class SecondaryDisasterRisk(TypedDict, total=False):
    """Structured output for a single secondary disaster risk."""

    risk_type: str
    risk_level: Literal["high", "medium", "low"]
    prevention_measures: list[str]
    monitoring_recommendations: list[str]


class SecondaryDisasterValue(TypedDict, total=False):
    """Structured output for Module 5 - Secondary Disaster Prevention."""

    risks: list[SecondaryDisasterRisk]
    narrative: str


class CalculationDetails(TypedDict, total=False):
    """Details of resource calculations for commander review."""

    affected_population: int
    trapped_count: int
    injured_count: int
    serious_injury_count: int
    emergency_duration_days: int
    shelter_calculation: dict[str, Any]
    rescue_calculation: dict[str, Any]
    medical_calculation: dict[str, Any]
    infrastructure_calculation: dict[str, Any]
    communication_calculation: dict[str, Any]
    logistics_calculation: dict[str, Any]
    self_support_calculation: dict[str, Any]
    calculation_basis: str


class OverallPlanState(TypedDict, total=False):
    """State for Overall Disaster Plan Generation workflow.

    This state flows through the LangGraph workflow and contains:
    - Input identifiers
    - Data aggregation results
    - CrewAI outputs (modules 0, 5)
    - MetaGPT outputs (modules 1-4, 6-8)
    - HITL review status
    - Final document
    - Error tracking
    """

    # Input identifiers
    event_id: str
    scenario_id: str
    task_id: str  # Unique ID for this plan generation run, maps to LangGraph thread_id

    # Data aggregation (load_context node output) - 新版本按想定加载
    scenario_data: dict[str, Any]  # 想定基本信息（从scenarios_v2）
    events_data: list[dict[str, Any]]  # 想定下的所有事件
    disaster_situations: list[dict[str, Any]]  # 灾情态势
    available_teams: list[dict[str, Any]]  # 可用救援队伍
    available_supplies: list[dict[str, Any]]  # 可用物资
    command_groups: list[dict[str, Any]]  # 工作组配置（基于国家预案）
    
    # 兼容旧字段
    event_data: dict[str, Any]  # 兼容：第一个事件数据
    ai_analysis: dict[str, Any]  # From EmergencyAI
    available_resources: list[dict[str, Any]]  # 兼容：同available_teams

    # 按Word模板7章结构的模块输出
    # 第0章：总体描述
    module_0_overview: str
    
    # 第一章：当前灾情初步评估（结构化数据）
    module_1_disaster_assessment: BasicDisasterValue
    
    # 第二章：组织指挥
    module_2_command: str
    
    # 第三章：救援力量部署与任务分工（包含4个子节）
    module_3_force_deployment: str  # 应急力量配置
    module_3_medical_deployment: str  # 医疗救护部署
    module_3_engineering: str  # 工程抢险安排
    module_3_resettlement: str  # 受灾群众安置与生活保障
    
    # 第四章：次生灾害预防与安全措施
    module_4_secondary_disaster: SecondaryDisasterValue
    
    # 第五章：通信与信息保障
    module_5_communication: str
    
    # 第六章：物资调配与运输保障
    module_6_logistics: str
    
    # 第七章：救援力量自身保障
    module_7_self_support: str
    
    # 第八章：附录与签章
    module_8_appendix: str
    
    # 兼容旧字段（向后兼容）
    module_0_basic_disaster: BasicDisasterValue  # 兼容：同module_1_disaster_assessment
    module_5_secondary_disaster: SecondaryDisasterValue  # 兼容：同module_4_secondary_disaster
    module_1_rescue_force: str  # 兼容：同module_3_force_deployment
    module_2_medical: str  # 兼容：同module_3_medical_deployment
    module_3_infrastructure: str  # 兼容：同module_3_engineering
    module_4_shelter: str  # 兼容：同module_3_resettlement
    module_6_communication: str  # 兼容：同module_5_communication
    module_7_logistics: str  # 兼容：同module_6_logistics
    module_8_self_support: str  # 兼容：同module_7_self_support

    # Calculation details for commander review
    calculation_details: CalculationDetails

    # Commander HITL review
    commander_feedback: str | None
    approved: bool

    # Final output
    final_document: str | None

    # Workflow tracking
    status: Literal["pending", "running", "awaiting_approval", "completed", "failed"]
    current_phase: str
    errors: list[str]

    # Message history for LLM interactions
    messages: Annotated[list[BaseMessage], add_messages]
