"""
方案生成Agent节点函数

包含8个LangGraph节点：
1. apply_trr_rules - 规则触发
2. extract_capabilities - 能力提取
3. match_resources - 资源匹配
4. arbitrate_scenes - 场景仲裁
5. optimize_scheme - 方案优化
6. filter_hard_rules - 硬规则过滤
7. score_soft_rules - 软规则评分
8. generate_output - 输出生成
"""

from .rules import apply_trr_rules
from .capabilities import extract_capabilities
from .matching import match_resources
from .arbitration import arbitrate_scenes
from .optimization import optimize_scheme
from .filtering import filter_hard_rules, score_soft_rules
from .output import generate_output

__all__ = [
    "apply_trr_rules",
    "extract_capabilities",
    "match_resources",
    "arbitrate_scenes",
    "optimize_scheme",
    "filter_hard_rules",
    "score_soft_rules",
    "generate_output",
]
