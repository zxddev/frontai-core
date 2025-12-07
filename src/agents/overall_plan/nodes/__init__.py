"""LangGraph Nodes for Overall Plan Generation

Implements the workflow nodes:
- load_context: Data aggregation from events_v2, EmergencyAI, resources
- disaster_summary: 灾情数据汇总（从数据库聚合，无LLM）
- command_structure: 组织指挥结构生成（从command_groups模板）
- resource_demand: 资源需求计算（集成SPHERE标准）
- gap_analysis: 缺口分析（复用emergency_ai逻辑）
- secondary_disaster: 次生灾害分析（保留CrewAI）
- situational_awareness: CrewAI wrapper node（文档润色）
- resource_calculation: MetaGPT wrapper node
- human_review: HITL checkpoint with interrupt/resume
- document_generation: Final document generation
"""

from src.agents.overall_plan.nodes.load_context import load_context_node
from src.agents.overall_plan.nodes.disaster_summary import disaster_summary_node
from src.agents.overall_plan.nodes.command_structure import command_structure_node
from src.agents.overall_plan.nodes.resource_demand import resource_demand_node
from src.agents.overall_plan.nodes.gap_analysis import gap_analysis_node
from src.agents.overall_plan.nodes.secondary_disaster import secondary_disaster_node
from src.agents.overall_plan.nodes.situational_awareness import situational_awareness_node
from src.agents.overall_plan.nodes.resource_calculation import resource_calculation_node
from src.agents.overall_plan.nodes.human_review import human_review_node
from src.agents.overall_plan.nodes.document_generation import document_generation_node

__all__ = [
    "load_context_node",
    "disaster_summary_node",
    "command_structure_node",
    "resource_demand_node",
    "gap_analysis_node",
    "secondary_disaster_node",
    "situational_awareness_node",
    "resource_calculation_node",
    "human_review_node",
    "document_generation_node",
]
