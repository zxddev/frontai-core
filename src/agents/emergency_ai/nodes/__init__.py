"""
EmergencyAI节点函数

每个节点对应LangGraph流程中的一个处理步骤。
"""
from __future__ import annotations

from .understanding import understand_disaster, enhance_with_cases
from .reasoning import query_rules, apply_rules
from .matching import match_resources, optimize_allocation
from .optimization import filter_hard_rules, score_soft_rules, explain_scheme
from .output import generate_output

__all__ = [
    # 阶段1: 灾情理解
    "understand_disaster",
    "enhance_with_cases",
    # 阶段2: 规则推理
    "query_rules",
    "apply_rules",
    # 阶段3: 资源匹配
    "match_resources",
    "optimize_allocation",
    # 阶段4: 方案优化
    "filter_hard_rules",
    "score_soft_rules",
    "explain_scheme",
    # 输出
    "generate_output",
]
