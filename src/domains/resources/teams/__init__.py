"""
救援队伍管理模块

对应SQL表: operational_v2.rescue_teams_v2
"""

from .router import router
from .service import TeamService
from .schemas import (
    TeamCreate, TeamUpdate, TeamResponse, 
    TeamListResponse, TeamType, TeamStatus
)

__all__ = [
    "router",
    "TeamService", 
    "TeamCreate", 
    "TeamUpdate", 
    "TeamResponse",
    "TeamListResponse",
    "TeamType",
    "TeamStatus",
]
