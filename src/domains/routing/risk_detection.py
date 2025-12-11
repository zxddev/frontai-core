"""
路径风险区域检测服务

检测规划路径是否穿过风险区域，使用 PostGIS ST_Intersects 进行空间查询
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point

logger = logging.getLogger(__name__)


@dataclass
class RiskAreaInfo:
    """风险区域信息"""
    id: UUID
    name: str
    risk_level: int
    passage_status: str
    area_type: str
    description: Optional[str] = None


class RiskDetectionService:
    """
    路径风险区域检测服务
    
    检测给定路径（polyline）是否穿过任何风险区域
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def detect_risk_areas(
        self,
        polyline: List[Point],
        scenario_id: Optional[UUID] = None,
    ) -> List[RiskAreaInfo]:
        """
        检测路径是否穿过风险区域
        
        Args:
            polyline: 路径点列表
            scenario_id: 场景ID（可选，不再作为过滤条件）
            
        Returns:
            穿过的风险区域列表（按风险等级降序）
        """
        if len(polyline) < 2:
            logger.warning("路径点数量不足，无法检测风险区域")
            return []
        
        # 构建 LineString WKT
        coords = ",".join([f"{p.lon} {p.lat}" for p in polyline])
        linestring_wkt = f"LINESTRING({coords})"
        
        logger.info(f"检测路径风险区域: points={len(polyline)}")
        
        # 同时查询两个数据源：
        # 1. disaster_affected_areas_v2 - 后端创建的风险区域
        # 2. entities_v2 中 type='danger_area' 的实体 - 前端绘制的危险区域
        sql = text("""
            SELECT id, name, risk_level, passage_status, area_type, description
            FROM (
                -- 数据源1: 灾害影响区域表
                SELECT 
                    id,
                    name,
                    risk_level,
                    passage_status,
                    area_type,
                    description,
                    geometry
                FROM operational_v2.disaster_affected_areas_v2
                
                UNION ALL
                
                -- 数据源2: 前端绘制的危险区域实体
                SELECT 
                    id,
                    COALESCE(properties->>'name', '未命名风险区域') as name,
                    COALESCE((properties->>'risk_level')::int, 5) as risk_level,
                    COALESCE(properties->>'passage_status', 'unknown') as passage_status,
                    COALESCE(properties->>'area_type', 'danger_area') as area_type,
                    properties->>'description' as description,
                    geometry
                FROM operational_v2.entities_v2
                WHERE type = 'danger_area'
            ) AS combined_risk_areas
            WHERE ST_Intersects(
                  geometry,
                  ST_GeomFromText(:linestring_wkt, 4326)
              )
            ORDER BY risk_level DESC
        """)
        
        try:
            result = await self._db.execute(sql, {
                "linestring_wkt": linestring_wkt,
            })
            rows = result.fetchall()
            
            risk_areas = [
                RiskAreaInfo(
                    id=row.id,
                    name=row.name or "未命名风险区域",
                    risk_level=row.risk_level or 5,
                    passage_status=row.passage_status or "unknown",
                    area_type=row.area_type or "unknown",
                    description=row.description,
                )
                for row in rows
            ]
            
            if risk_areas:
                logger.warning(
                    f"路径穿过 {len(risk_areas)} 个风险区域: "
                    f"{[ra.name for ra in risk_areas]}"
                )
            else:
                logger.info("路径未穿过任何风险区域")
            
            return risk_areas
            
        except Exception as e:
            logger.error(f"风险区域检测失败: {e}", exc_info=True)
            return []
    
    # 高德API避障区域限制
    MAX_AVOID_AREA_KM2: float = 80.0  # 每个区域最大81平方公里，保守取80
    MAX_POLYGON_POINTS: int = 16  # 每个多边形最多16个顶点
    
    async def get_risk_area_polygons(
        self,
        risk_area_ids: List[UUID],
        buffer_meters: float = 0,
    ) -> List[List[tuple[float, float]]]:
        """
        获取风险区域的多边形坐标（用于避障规划）
        
        只查询 disaster_affected_areas_v2 表（风险区域唯一数据源）
        
        高德API限制：
        - 每个避障区域不能超过81平方公里
        - 每个多边形最多16个顶点
        
        Args:
            risk_area_ids: 风险区域ID列表
            buffer_meters: 缓冲区距离（米），用于安全绕行方案
            
        Returns:
            多边形列表，每个多边形是坐标点列表 [(lon, lat), ...]
        """
        if not risk_area_ids:
            return []
        
        # 查询多边形及其面积（平方公里）
        if buffer_meters > 0:
            sql = text("""
                SELECT 
                    id,
                    name,
                    ST_AsText(
                        ST_Transform(
                            ST_Buffer(
                                ST_Transform(geometry::geometry, 3857),
                                :buffer_meters
                            ),
                            4326
                        )
                    ) as wkt,
                    ST_Area(
                        ST_Transform(
                            ST_Buffer(
                                ST_Transform(geometry::geometry, 3857),
                                :buffer_meters
                            ),
                            4326
                        )::geography
                    ) / 1000000 as area_km2,
                    ST_NPoints(geometry::geometry) as num_points
                FROM operational_v2.disaster_affected_areas_v2
                WHERE id = ANY(:ids)
            """)
        else:
            sql = text("""
                SELECT 
                    id,
                    name,
                    ST_AsText(geometry::geometry) as wkt,
                    ST_Area(geometry::geography) / 1000000 as area_km2,
                    ST_NPoints(geometry::geometry) as num_points
                FROM operational_v2.disaster_affected_areas_v2
                WHERE id = ANY(:ids)
            """)
        
        try:
            result = await self._db.execute(sql, {
                "ids": [str(id) for id in risk_area_ids],
                "buffer_meters": buffer_meters,
            })
            rows = result.fetchall()
            
            polygons = []
            skipped_count = 0
            
            for row in rows:
                area_km2 = row.area_km2 or 0
                num_points = row.num_points or 0
                
                # 检查面积是否超过高德限制
                if area_km2 > self.MAX_AVOID_AREA_KM2:
                    logger.warning(
                        f"[避障区域] 跳过超大区域: {row.name}, "
                        f"面积={area_km2:.1f}km² (限制{self.MAX_AVOID_AREA_KM2}km²)"
                    )
                    skipped_count += 1
                    continue
                
                coords = self._parse_polygon_wkt(row.wkt)
                if not coords:
                    continue
                
                # 如果顶点数超过限制，简化多边形（保留首尾和均匀采样）
                if len(coords) > self.MAX_POLYGON_POINTS:
                    logger.info(
                        f"[避障区域] 简化多边形: {row.name}, "
                        f"顶点数 {len(coords)} -> {self.MAX_POLYGON_POINTS}"
                    )
                    coords = self._simplify_polygon(coords, self.MAX_POLYGON_POINTS)
                
                polygons.append(coords)
                logger.info(
                    f"[避障区域] 添加: {row.name}, "
                    f"面积={area_km2:.2f}km², 顶点数={len(coords)}"
                )
            
            logger.info(
                f"获取风险区域多边形: ids={len(risk_area_ids)}, "
                f"有效={len(polygons)}, 跳过超大={skipped_count}"
            )
            return polygons
            
        except Exception as e:
            logger.error(f"获取风险区域多边形失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _simplify_polygon(coords: List[tuple[float, float]], max_points: int) -> List[tuple[float, float]]:
        """
        简化多边形，保留首尾点和均匀采样的中间点
        """
        if len(coords) <= max_points:
            return coords
        
        # 保留第一个点，均匀采样中间点，确保最后一个点（闭合）
        step = (len(coords) - 1) / (max_points - 1)
        indices = [int(i * step) for i in range(max_points - 1)]
        indices.append(len(coords) - 1)  # 确保最后一个点
        
        return [coords[i] for i in indices]
    
    @staticmethod
    def _parse_polygon_wkt(wkt: str) -> List[tuple[float, float]]:
        """
        解析 WKT POLYGON 字符串为坐标列表
        
        Args:
            wkt: WKT 格式字符串，如 "POLYGON((lon1 lat1, lon2 lat2, ...))"
            
        Returns:
            坐标列表 [(lon, lat), ...]
        """
        if not wkt or not wkt.startswith("POLYGON"):
            return []
        
        try:
            # 提取坐标部分：POLYGON((x1 y1, x2 y2, ...))
            coords_str = wkt.replace("POLYGON((", "").replace("))", "")
            # 处理多环情况，只取外环
            if "),(" in coords_str:
                coords_str = coords_str.split("),(")[0]
            
            coords = []
            for point_str in coords_str.split(","):
                parts = point_str.strip().split()
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    coords.append((lon, lat))
            
            return coords
        except Exception:
            return []
