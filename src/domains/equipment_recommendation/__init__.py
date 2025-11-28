"""
装备推荐领域模块

提供装备推荐的查询、确认等业务能力。
"""

from .router import router
from .service import EquipmentRecommendationService
from .schemas import (
    EquipmentRecommendationResponse,
    EquipmentRecommendationConfirm,
    DeviceRecommendationSchema,
    SupplyRecommendationSchema,
    ShortageAlertSchema,
)

__all__ = [
    "router",
    "EquipmentRecommendationService",
    "EquipmentRecommendationResponse",
    "EquipmentRecommendationConfirm",
    "DeviceRecommendationSchema",
    "SupplyRecommendationSchema",
    "ShortageAlertSchema",
]
