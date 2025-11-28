"""
驻扎点选址智能体

基于LangGraph实现多步分析推理：
- 灾情理解 → 地形分析 → 通信分析 → 安全分析 → 评估排序 → 决策解释

遵循调用规范：Agent节点 → Service → Core
"""
from src.agents.staging_area.agent import StagingAreaAgent
from src.agents.staging_area.graph import staging_area_graph
from src.agents.staging_area.state import StagingAreaAgentState

__all__ = [
    "StagingAreaAgent",
    "staging_area_graph",
    "StagingAreaAgentState",
]
