"""
EmergencyAI节点函数

每个节点对应LangGraph流程中的一个处理步骤。
"""
from __future__ import annotations

from .understanding import understand_disaster, enhance_with_cases
from .reasoning import query_rules, apply_rules
from .htn_decompose import htn_decompose
from .matching import match_resources, optimize_allocation
from .optimization import filter_hard_rules, score_soft_rules, explain_scheme
from .output import generate_output

# 战略层节点
from .domain_classifier import classify_domains
from .phase_manager import apply_phase_priority
from .module_assembler import assemble_modules
from .transport_checker import check_transport
from .safety_checker import check_safety_rules
from .report_generator import generate_reports
from .simulation import run_simulation

__all__ = [
    # 阶段1: 灾情理解
    "understand_disaster",
    "enhance_with_cases",
    # 阶段2: 规则推理
    "query_rules",
    "apply_rules",
    # 阶段2.5: HTN任务分解
    "htn_decompose",
    # 阶段2.6: 战略层 - 任务域/阶段/模块
    "classify_domains",
    "apply_phase_priority",
    "assemble_modules",
    # 阶段3: 资源匹配
    "match_resources",
    "optimize_allocation",
    # 阶段3.5: 战略层 - 运力/安全
    "check_transport",
    "check_safety_rules",
    # 阶段4: 方案优化
    "filter_hard_rules",
    "score_soft_rules",
    "explain_scheme",
    # 阶段4.5: 战略层 - 报告
    "generate_reports",
    # 阶段5: 仿真闭环
    "run_simulation",
    # 输出
    "generate_output",
]
