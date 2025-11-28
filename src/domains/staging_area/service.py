"""
救援队驻扎点选址服务层

遵循调用规范：
- Service层负责实例化Repository和Core
- 管理事务边界
- 不使用@staticmethod
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.staging_area.core import StagingAreaCore
from src.domains.staging_area.repository import StagingAreaRepository
from src.domains.staging_area.schemas import (
    EarthquakeParams,
    EvaluationWeights,
    RescueTarget,
    StagingConstraints,
    StagingRecommendation,
    StagingRecommendationRequest,
    TargetPriority,
    TeamInfo,
)
from src.planning.algorithms.routing.db_route_engine import DatabaseRouteEngine

logger = logging.getLogger(__name__)


class StagingAreaService:
    """
    驻扎点选址服务
    
    遵循调用规范：
    - 接收db作为构造函数参数
    - 实例化Repository和RouteEngine
    - 将依赖注入到Core
    """
    
    def __init__(self, db: AsyncSession) -> None:
        """
        初始化服务
        
        Args:
            db: 数据库会话（由路由层通过依赖注入提供）
        """
        self._db = db
        self._repo = StagingAreaRepository(db)
        self._route_engine = DatabaseRouteEngine(db)
    
    async def recommend(
        self,
        request: StagingRecommendationRequest,
    ) -> StagingRecommendation:
        """
        执行驻扎点推荐
        
        Args:
            request: 推荐请求
            
        Returns:
            StagingRecommendation: 推荐结果
        """
        try:
            # Service实例化Core，传入依赖（遵循调用规范）
            core = StagingAreaCore(
                repository=self._repo,
                route_engine=self._route_engine,
            )
            
            result = await core.recommend(
                scenario_id=request.scenario_id,
                earthquake=request.earthquake,
                rescue_targets=request.rescue_targets,
                team=request.team,
                constraints=request.constraints,
                weights=request.weights,
            )
            return result
            
        except Exception as e:
            logger.error(f"[驻扎点服务] 推荐失败: {e}", exc_info=True)
            return StagingRecommendation(
                success=False,
                error=f"服务异常: {str(e)}",
            )
    
    async def recommend_simple(
        self,
        scenario_id: UUID,
        epicenter_lon: float,
        epicenter_lat: float,
        magnitude: float,
        team_id: UUID,
        team_base_lon: float,
        team_base_lat: float,
        target_locations: list[tuple[UUID, float, float, str]],
    ) -> StagingRecommendation:
        """
        简化版推荐接口
        
        Args:
            scenario_id: 想定ID
            epicenter_lon: 震中经度
            epicenter_lat: 震中纬度
            magnitude: 震级
            team_id: 队伍ID
            team_base_lon: 队伍驻地经度
            team_base_lat: 队伍驻地纬度
            target_locations: 救援目标列表 [(id, lon, lat, priority), ...]
            
        Returns:
            StagingRecommendation: 推荐结果
        """
        request = StagingRecommendationRequest(
            scenario_id=scenario_id,
            earthquake=EarthquakeParams(
                epicenter_lon=epicenter_lon,
                epicenter_lat=epicenter_lat,
                magnitude=magnitude,
            ),
            rescue_targets=[
                RescueTarget(
                    id=t[0],
                    longitude=t[1],
                    latitude=t[2],
                    priority=TargetPriority(t[3]) if len(t) > 3 else TargetPriority.MEDIUM,
                )
                for t in target_locations
            ],
            team=TeamInfo(
                team_id=team_id,
                base_lon=team_base_lon,
                base_lat=team_base_lat,
            ),
            constraints=StagingConstraints(),
            weights=EvaluationWeights(),
        )
        
        return await self.recommend(request)
