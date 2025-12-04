"""
CrewAI增强模块 - 侦察调度智能体

提供核心Crew：
1. DisasterAnalysisCrew - 灾情理解，从自然语言提取关键信息
2. PlanPresentationCrew - 计划呈报，生成指挥员级别报告
3. TargetPriorityAnalysisCrew - 目标优先级分析，智能排序侦察目标

无fallback设计：LLM失败直接抛出CrewAIError
"""
from .crew import (
    ReconSchedulerCrew,
    DisasterAnalysisCrew,
    PlanPresentationCrew,
    CrewAIError,
)
from .agents import (
    create_disaster_analyst,
    create_plan_presenter,
)
from .tasks import (
    DisasterAnalysisOutput,
    PlanPresentationOutput,
)
from .target_analysis import (
    TargetPriorityAnalysisCrew,
    TargetPriorityOutput,
    TargetReconPlan,
    DeviceRecommendation,
    ReconMethodDetail,
    RiskMitigation,
    rule_based_priority_analysis,
)

__all__ = [
    "ReconSchedulerCrew",
    "DisasterAnalysisCrew",
    "PlanPresentationCrew",
    "TargetPriorityAnalysisCrew",
    "CrewAIError",
    "create_disaster_analyst",
    "create_plan_presenter",
    "DisasterAnalysisOutput",
    "PlanPresentationOutput",
    "TargetPriorityOutput",
    "TargetReconPlan",
    "DeviceRecommendation",
    "ReconMethodDetail",
    "RiskMitigation",
    "rule_based_priority_analysis",
]
