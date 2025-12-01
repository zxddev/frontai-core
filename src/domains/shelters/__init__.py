"""
疏散安置点管理模块

对应SQL表: operational_v2.evacuation_shelters_v2
"""

from .router import router
from .service import ShelterService
from .schemas import (
    ShelterCreate, ShelterUpdate, ShelterResponse, 
    ShelterListResponse, ShelterType, ShelterStatus,
    ShelterCapacityUpdate, ShelterStatusUpdate,
    ShelterNearbyQuery, ShelterNearbyResult
)

__all__ = [
    "router",
    "ShelterService",
    "ShelterCreate",
    "ShelterUpdate",
    "ShelterResponse",
    "ShelterListResponse",
    "ShelterType",
    "ShelterStatus",
    "ShelterCapacityUpdate",
    "ShelterStatusUpdate",
    "ShelterNearbyQuery",
    "ShelterNearbyResult",
]
