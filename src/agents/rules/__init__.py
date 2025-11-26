"""
TRR规则引擎模块

提供应急救灾触发规则的加载、匹配和执行
参考军事版TRR-001规则库设计
"""

from .models import (
    TRRRule,
    Condition,
    TriggerConfig,
    ActionConfig,
    CapabilityRequirement,
    MatchedRule,
    HardRule,
    HardRuleResult,
)
from .loader import RuleLoader, clear_rules_cache, get_cache_stats, reset_cache_stats
from .engine import TRRRuleEngine

__all__ = [
    "TRRRule",
    "Condition",
    "TriggerConfig",
    "ActionConfig",
    "CapabilityRequirement",
    "MatchedRule",
    "HardRule",
    "HardRuleResult",
    "RuleLoader",
    "TRRRuleEngine",
    "clear_rules_cache",
    "get_cache_stats",
    "reset_cache_stats",
]
