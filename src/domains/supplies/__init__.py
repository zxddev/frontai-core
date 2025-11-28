"""
物资管理模块

对应SQL表: operational_v2.supplies_v2, supply_inventory_v2, supply_depots_v2
"""

from .router import router
from .service import SupplyService
from .inventory_service import (
    SupplyInventoryService,
    SupplyInventoryItem,
    TransferRequest,
    TransferResult,
)
from .schemas import (
    SupplyCreate, SupplyUpdate, SupplyResponse, 
    SupplyListResponse, SupplyCategory, SupplyUnit
)

__all__ = [
    "router",
    "SupplyService",
    "SupplyInventoryService",
    "SupplyInventoryItem",
    "TransferRequest",
    "TransferResult",
    "SupplyCreate",
    "SupplyUpdate",
    "SupplyResponse",
    "SupplyListResponse",
    "SupplyCategory",
    "SupplyUnit",
]
