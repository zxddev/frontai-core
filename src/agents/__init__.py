"""
AI Agent模块

模块结构:
- base/ - Agent基础设施
- emergency_ai/ - 应急救灾AI Agent（AI+规则混合架构）
- route_planning/ - 路径规划智能体（双频架构：LLM决策+算法计算）
- task_dispatch/ - 任务智能分发Agent（双模式：初始分配+动态调整）
- early_warning/ - 预警监测智能体（Human in the Loop）
- router.py - AI API路由
- schemas.py - 请求响应模型
"""

from .base import BaseAgent
from .emergency_ai import EmergencyAIAgent, get_emergency_ai_agent
from .route_planning import invoke as route_planning_invoke
from .task_dispatch import TaskDispatchAgent, get_task_dispatch_agent
from .early_warning import EarlyWarningAgent, get_early_warning_agent
from .router import router

__all__ = [
    "BaseAgent",
    "EmergencyAIAgent",
    "get_emergency_ai_agent",
    "TaskDispatchAgent",
    "get_task_dispatch_agent",
    "EarlyWarningAgent",
    "get_early_warning_agent",
    "route_planning_invoke",
    "router",
]
