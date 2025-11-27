"""
救援队驻扎点选址服务层

提供API封装、参数校验、日志记录。
可被FastAPI路由、EmergencyAI节点等调用。
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.domains.staging_area.core import StagingAreaCore
from src.domains.staging_area.schemas import (
    EarthquakeParams,
    EvaluationWeights,
    RescueTarget,
    StagingConstraints,
    StagingRecommendation,
    StagingRecommendationRequest,
    TeamInfo,
)

logger = logging.getLogger(__name__)


class StagingAreaService:
    """
    驻扎点选址服务
    
    提供高层API，封装Core层的复杂逻辑。
    """
    
    @staticmethod
    async def recommend(
        request: StagingRecommendationRequest,
        db: Optional[AsyncSession] = None,
    ) -> StagingRecommendation:
        """
        执行驻扎点推荐
        
        Args:
            request: 推荐请求
            db: 数据库会话（可选，未提供时自动创建）
            
        Returns:
            StagingRecommendation: 推荐结果
        """
        close_db = False
        if db is None:
            db = AsyncSessionLocal()
            close_db = True
        
        try:
            core = StagingAreaCore(db)
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
            
        finally:
            if close_db:
                await db.close()
    
    @staticmethod
    async def recommend_simple(
        scenario_id: UUID,
        epicenter_lon: float,
        epicenter_lat: float,
        magnitude: float,
        team_id: UUID,
        team_base_lon: float,
        team_base_lat: float,
        target_locations: list[tuple[UUID, float, float, str]],
        db: Optional[AsyncSession] = None,
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
            db: 数据库会话
            
        Returns:
            StagingRecommendation: 推荐结果
        """
        from src.domains.staging_area.schemas import TargetPriority
        
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
        
        return await StagingAreaService.recommend(request, db)
