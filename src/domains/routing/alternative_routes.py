"""
绕行方案生成服务

根据风险区域生成3个绕行方案：
1. 推荐绕行（综合最优，strategy=32）
2. 最快绕行（时间优先，strategy=38）
3. 安全绕行（外扩500m缓冲区，strategy=32）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point, RouteResult
from .risk_detection import RiskDetectionService
from src.infra.clients.amap.route_planning import amap_route_planning_with_avoidance_async

logger = logging.getLogger(__name__)

# 安全绕行的缓冲区距离（米）
SAFETY_BUFFER_METERS: float = 500.0


@dataclass
class AlternativeRoute:
    """绕行方案"""
    strategy: str  # recommended / fastest / safest
    strategy_name: str  # 中文名称
    distance_m: float
    duration_s: float
    polyline: List[Point] = field(default_factory=list)
    description: str = ""


class AlternativeRoutesService:
    """
    绕行方案生成服务
    
    为穿过风险区域的路径生成3个备选绕行方案
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._risk_detection = RiskDetectionService(db)
    
    async def generate_alternatives(
        self,
        origin: Point,
        destination: Point,
        risk_area_ids: List[UUID],
    ) -> List[AlternativeRoute]:
        """
        生成绕行方案
        
        Args:
            origin: 起点
            destination: 终点
            risk_area_ids: 需要避让的风险区域ID列表
            
        Returns:
            最多3个绕行方案（去重后可能少于3个）
        """
        if not risk_area_ids:
            logger.warning("无风险区域ID，无法生成绕行方案")
            return []
        
        logger.info(f"生成绕行方案: 避让 {len(risk_area_ids)} 个风险区域")
        
        # 获取风险区域原始多边形
        original_polygons = await self._risk_detection.get_risk_area_polygons(
            risk_area_ids, buffer_meters=0
        )
        
        # 获取扩大缓冲区后的多边形（安全绕行用）
        buffered_polygons = await self._risk_detection.get_risk_area_polygons(
            risk_area_ids, buffer_meters=SAFETY_BUFFER_METERS
        )
        
        if not original_polygons:
            logger.error("无法获取风险区域多边形")
            return []
        
        alternatives: List[AlternativeRoute] = []
        
        # 方案1：推荐绕行（strategy=32，高德推荐）
        route1 = await self._plan_avoidance_route(
            origin, destination, original_polygons,
            strategy=32,
            strategy_key="recommended",
            strategy_name="推荐绕行",
            description="距离与时间平衡的绕行路线"
        )
        if route1:
            alternatives.append(route1)
        
        # 方案2：最快绕行（strategy=38，速度最快）
        route2 = await self._plan_avoidance_route(
            origin, destination, original_polygons,
            strategy=38,
            strategy_key="fastest",
            strategy_name="最快绕行",
            description="时间最短的绕行路线"
        )
        if route2:
            # 去重：如果和方案1距离差距小于5%，不添加
            if not alternatives or abs(route2.distance_m - alternatives[0].distance_m) / alternatives[0].distance_m > 0.05:
                alternatives.append(route2)
        
        # 方案3：安全绕行（扩大缓冲区）
        if buffered_polygons:
            route3 = await self._plan_avoidance_route(
                origin, destination, buffered_polygons,
                strategy=32,
                strategy_key="safest",
                strategy_name="安全绕行",
                description=f"远离风险区域{SAFETY_BUFFER_METERS:.0f}米的绕行路线"
            )
            if route3:
                # 去重：安全路线通常更远，只要比推荐路线长就添加
                if not alternatives or route3.distance_m > alternatives[0].distance_m * 1.05:
                    alternatives.append(route3)
        
        logger.info(f"绕行方案生成完成: {len(alternatives)} 个方案")
        return alternatives
    
    async def _plan_avoidance_route(
        self,
        origin: Point,
        destination: Point,
        avoid_polygons: List[List[tuple[float, float]]],
        strategy: int,
        strategy_key: str,
        strategy_name: str,
        description: str,
    ) -> Optional[AlternativeRoute]:
        """
        调用高德避障API规划单条绕行路线
        """
        try:
            result = await amap_route_planning_with_avoidance_async(
                origin_lon=origin.lon,
                origin_lat=origin.lat,
                dest_lon=destination.lon,
                dest_lat=destination.lat,
                avoid_polygons=avoid_polygons,
                strategy=strategy,
            )
            
            paths = result.get("paths", [])
            if not paths:
                logger.warning(f"高德避障API无返回路径: strategy={strategy}")
                return None
            
            path = paths[0]
            distance_m = float(path.get("distance", 0))
            duration_s = float(path.get("duration", 0))
            
            # 解析 polyline
            polyline: List[Point] = []
            for step in path.get("steps", []):
                step_polyline = step.get("polyline", "")
                if step_polyline:
                    for coord_str in step_polyline.split(";"):
                        parts = coord_str.split(",")
                        if len(parts) >= 2:
                            try:
                                lon, lat = float(parts[0]), float(parts[1])
                                polyline.append(Point(lon=lon, lat=lat))
                            except ValueError:
                                continue
            
            return AlternativeRoute(
                strategy=strategy_key,
                strategy_name=strategy_name,
                distance_m=distance_m,
                duration_s=duration_s,
                polyline=polyline,
                description=description,
            )
            
        except Exception as e:
            logger.error(f"绕行路线规划失败 (strategy={strategy}): {e}", exc_info=True)
            return None
