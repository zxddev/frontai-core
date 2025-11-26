"""
灾情评估与预测模块

功能:
1. 灾情等级评估 - 根据灾害参数评估等级和影响范围
2. 次生灾害预测 - 预测火灾、滑坡、余震等次生灾害风险
3. 损失预测 - 估算伤亡、建筑损毁、基础设施损失
4. 确认评分 - 计算事件确认评分并决定状态流转
"""

from .disaster_assessment import DisasterAssessment
from .secondary_hazard import SecondaryHazardPredictor
from .loss_estimation import LossEstimator
from .confirmation_scorer import ConfirmationScorer

__all__ = ["DisasterAssessment", "SecondaryHazardPredictor", "LossEstimator", "ConfirmationScorer"]
