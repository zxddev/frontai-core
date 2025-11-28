"""
AI Agent模块

模块结构:
- base/ - Agent基础设施
- emergency_ai/ - 应急救灾AI Agent（AI+规则混合架构）
- route_planning/ - 路径规划智能体（双频架构：LLM决策+算法计算）
- task_dispatch/ - 任务智能分发Agent（双模式：初始分配+动态调整）
- scheme_parsing/ - 方案解析Agent（LLM结构化输出）
- early_warning/ - 预警监测智能体（Human in the Loop）
- staging_area/ - 驻扎点选址智能体（Hybrid Agent：LLM分析+算法计算）
- router.py - AI API路由
- schemas.py - 请求响应模型
"""

from .base import BaseAgent
from .emergency_ai import EmergencyAIAgent, get_emergency_ai_agent
from .route_planning import invoke as route_planning_invoke
from .task_dispatch import TaskDispatchAgent, get_task_dispatch_agent
from .scheme_parsing import SchemeParsingAgent, parse_scheme_text
from .early_warning import EarlyWarningAgent, get_early_warning_agent
from .staging_area import StagingAreaAgent, staging_area_graph
from .router import router

__all__ = [
    "BaseAgent",
    "EmergencyAIAgent",
    "get_emergency_ai_agent",
    "TaskDispatchAgent",
    "get_task_dispatch_agent",
    "SchemeParsingAgent",
    "parse_scheme_text",
    "EarlyWarningAgent",
    "get_early_warning_agent",
    "StagingAreaAgent",
    "staging_area_graph",
    "route_planning_invoke",
    "router",
]
