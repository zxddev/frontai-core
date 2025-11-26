"""
事件分析Agent

功能:
1. 灾情评估 - 调用DisasterAssessment算法
2. 次生灾害预测 - 调用SecondaryHazardPredictor算法
3. 损失估算 - 调用LossEstimator算法
4. 确认评分 - 调用ConfirmationScorer算法，决定状态流转
"""

from .agent import EventAnalysisAgent

__all__ = ["EventAnalysisAgent"]
