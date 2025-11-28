"""
驻扎点选址智能体节点

各节点职责：
- understand: 灾情理解（LLM解析非结构化输入）
- terrain: 地形分析（LLM + GIS数据）
- communication: 通信分析（LLM + 通信数据）
- safety: 安全分析（LLM + 算法）
- evaluate: 评估排序（调用StagingAreaCore算法）
- explain: 决策解释（LLM生成解释和风险警示）
"""
from src.agents.staging_area.nodes.understand import understand_disaster
from src.agents.staging_area.nodes.terrain import analyze_terrain
from src.agents.staging_area.nodes.communication import analyze_communication
from src.agents.staging_area.nodes.safety import analyze_safety
from src.agents.staging_area.nodes.evaluate import evaluate_candidates
from src.agents.staging_area.nodes.explain import explain_decision

__all__ = [
    "understand_disaster",
    "analyze_terrain",
    "analyze_communication",
    "analyze_safety",
    "evaluate_candidates",
    "explain_decision",
]
