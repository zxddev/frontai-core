"""
救援队驻扎点选址模块

提供基于空间优化的驻扎点推荐服务。
"""
from src.domains.staging_area.core import StagingAreaCore
from src.domains.staging_area.router import router
from src.domains.staging_area.schemas import (
    StagingConstraints,
    StagingRecommendation,
    RankedStagingSite,
    EarthquakeParams,
    RescueTarget,
    TeamInfo,
)

__all__ = [
    "StagingAreaCore",
    "router",
    "StagingConstraints",
    "StagingRecommendation",
    "RankedStagingSite",
    "EarthquakeParams",
    "RescueTarget",
    "TeamInfo",
]
