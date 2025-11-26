"""
地图实体数据访问层

职责: 数据库CRUD操作，无业务逻辑
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON, ST_DWithin, ST_Distance, ST_MakeEnvelope, ST_Transform
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, shape

from .models import Entity, Layer, LayerTypeDefault, EntityTrack
from .schemas import EntityCreate, EntityUpdate, EntityLocationUpdate, GeoJsonGeometry, TrackPoint

logger = logging.getLogger(__name__)


class EntityRepository:
    """实体数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: EntityCreate, created_by: Optional[str] = None) -> Entity:
        """创建实体"""
        import json
        geom_json = json.dumps(data.geometry.model_dump())
        
        entity = Entity(
            type=data.type.value,
            layer_code=data.layer_code,
            device_id=data.device_id,
            geometry=ST_GeomFromGeoJSON(geom_json),
            properties=data.properties,
            source=data.source.value,
            visible_on_map=data.visible_on_map,
            is_dynamic=data.is_dynamic,
            style_overrides=data.style_overrides,
            scenario_id=data.scenario_id,
            event_id=data.event_id,
            created_by=created_by,
        )
        self._db.add(entity)
        await self._db.flush()
        await self._db.refresh(entity)
        
        logger.info(f"创建实体: type={entity.type}, id={entity.id}")
        return entity
    
    async def get_by_id(self, entity_id: UUID) -> Optional[Entity]:
        """根据ID查询实体"""
        result = await self._db.execute(
            select(Entity)
            .where(Entity.id == entity_id)
            .where(Entity.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        entity_types: Optional[list[str]] = None,
        layer_code: Optional[str] = None,
        is_visible: Optional[bool] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> tuple[Sequence[Entity], int]:
        """
        分页查询实体列表
        
        Args:
            bbox: (min_lng, min_lat, max_lng, max_lat)
        """
        query = select(Entity).where(Entity.deleted_at.is_(None))
        count_query = select(func.count(Entity.id)).where(Entity.deleted_at.is_(None))
        
        if scenario_id:
            query = query.where(Entity.scenario_id == scenario_id)
            count_query = count_query.where(Entity.scenario_id == scenario_id)
        
        if entity_types:
            query = query.where(Entity.type.in_(entity_types))
            count_query = count_query.where(Entity.type.in_(entity_types))
        
        if layer_code:
            query = query.where(Entity.layer_code == layer_code)
            count_query = count_query.where(Entity.layer_code == layer_code)
        
        if is_visible is not None:
            query = query.where(Entity.visible_on_map == is_visible)
            count_query = count_query.where(Entity.visible_on_map == is_visible)
        
        if bbox:
            min_lng, min_lat, max_lng, max_lat = bbox
            envelope = ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
            query = query.where(Entity.geometry.ST_Within(envelope))
            count_query = count_query.where(Entity.geometry.ST_Within(envelope))
        
        query = query.order_by(Entity.updated_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        result = await self._db.execute(query)
        items = result.scalars().all()
        
        count_result = await self._db.execute(count_query)
        total = count_result.scalar() or 0
        
        return items, total
    
    async def list_in_bounds(
        self,
        scenario_id: UUID,
        bounds: tuple[float, float, float, float],
        entity_types: Optional[list[str]] = None,
    ) -> Sequence[Entity]:
        """查询边界框内的实体"""
        min_lng, min_lat, max_lng, max_lat = bounds
        envelope = ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)
        
        query = (
            select(Entity)
            .where(Entity.deleted_at.is_(None))
            .where(Entity.scenario_id == scenario_id)
            .where(Entity.visible_on_map == True)
            .where(Entity.geometry.ST_Within(envelope))
        )
        
        if entity_types:
            query = query.where(Entity.type.in_(entity_types))
        
        result = await self._db.execute(query)
        return result.scalars().all()
    
    async def list_nearby(
        self,
        scenario_id: UUID,
        center_lng: float,
        center_lat: float,
        radius_km: float,
        entity_types: Optional[list[str]] = None,
    ) -> list[tuple[Entity, float]]:
        """
        查询附近实体（带距离）
        
        Returns:
            list of (entity, distance_km)
        """
        from sqlalchemy import cast
        from sqlalchemy.types import TypeDecorator
        from geoalchemy2 import Geography
        
        center_point = func.ST_SetSRID(func.ST_MakePoint(center_lng, center_lat), 4326)
        radius_meters = radius_km * 1000
        
        # 使用geography类型计算距离
        distance_expr = func.ST_Distance(
            cast(Entity.geometry, Geography),
            cast(center_point, Geography)
        )
        
        query = (
            select(Entity, (distance_expr / 1000).label('distance_km'))
            .where(Entity.deleted_at.is_(None))
            .where(Entity.scenario_id == scenario_id)
            .where(Entity.visible_on_map == True)
            .where(ST_DWithin(
                cast(Entity.geometry, Geography),
                cast(center_point, Geography),
                radius_meters
            ))
            .order_by('distance_km')
        )
        
        if entity_types:
            query = query.where(Entity.type.in_(entity_types))
        
        result = await self._db.execute(query)
        return [(row[0], row[1]) for row in result.all()]
    
    async def update(self, entity: Entity, data: EntityUpdate) -> Entity:
        """更新实体"""
        import json
        update_dict = data.model_dump(exclude_unset=True)
        
        if 'geometry' in update_dict and update_dict['geometry']:
            geom_json = json.dumps(update_dict.pop('geometry'))
            entity.geometry = ST_GeomFromGeoJSON(geom_json)
        
        for key, value in update_dict.items():
            setattr(entity, key, value)
        
        await self._db.flush()
        await self._db.refresh(entity)
        
        logger.info(f"更新实体: id={entity.id}")
        return entity
    
    async def update_location(
        self,
        entity: Entity,
        longitude: float,
        latitude: float,
    ) -> Entity:
        """更新实体位置"""
        point = Point(longitude, latitude)
        entity.geometry = from_shape(point, srid=4326)
        entity.last_position_at = datetime.utcnow()
        
        await self._db.flush()
        await self._db.refresh(entity)
        
        logger.info(f"更新实体位置: id={entity.id}, lng={longitude}, lat={latitude}")
        return entity
    
    async def update_visibility(self, entity: Entity, visible: bool) -> Entity:
        """更新实体可见性"""
        entity.visible_on_map = visible
        await self._db.flush()
        await self._db.refresh(entity)
        
        logger.info(f"更新实体可见性: id={entity.id}, visible={visible}")
        return entity
    
    async def delete(self, entity: Entity) -> None:
        """软删除实体"""
        entity.deleted_at = datetime.utcnow()
        await self._db.flush()
        
        logger.info(f"删除实体: id={entity.id}")
    
    async def get_geometry_as_geojson(self, entity: Entity) -> dict:
        """获取实体几何为GeoJSON格式"""
        result = await self._db.execute(
            select(ST_AsGeoJSON(Entity.geometry))
            .where(Entity.id == entity.id)
        )
        geojson_str = result.scalar()
        if geojson_str:
            import json
            return json.loads(geojson_str)
        return {}
    
    # ==================== 轨迹相关方法 ====================
    
    async def add_track_point(
        self,
        entity_id: UUID,
        longitude: float,
        latitude: float,
        speed_kmh: Optional[float] = None,
        heading: Optional[int] = None,
        altitude_m: Optional[float] = None,
        recorded_at: Optional[datetime] = None,
    ) -> EntityTrack:
        """
        添加轨迹点
        
        Args:
            entity_id: 实体ID
            longitude: 经度
            latitude: 纬度
            speed_kmh: 速度(km/h)
            heading: 航向角度(0-360)
            altitude_m: 海拔高度(米)
            recorded_at: 记录时间（默认当前时间）
        """
        point = Point(longitude, latitude)
        track = EntityTrack(
            entity_id=entity_id,
            location=from_shape(point, srid=4326),
            speed_kmh=speed_kmh,
            heading=heading,
            altitude_m=altitude_m,
            recorded_at=recorded_at or datetime.utcnow(),
        )
        self._db.add(track)
        await self._db.flush()
        
        logger.debug(f"轨迹点已记录: entity_id={entity_id}, lng={longitude}, lat={latitude}")
        return track
    
    async def get_tracks(
        self,
        entity_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[TrackPoint]:
        """
        查询实体轨迹
        
        Args:
            entity_id: 实体ID
            start_time: 开始时间
            end_time: 结束时间
            limit: 最大返回数量
            
        Returns:
            轨迹点列表（按时间正序）
        """
        query = (
            select(EntityTrack)
            .where(EntityTrack.entity_id == entity_id)
        )
        
        if start_time:
            query = query.where(EntityTrack.recorded_at >= start_time)
        if end_time:
            query = query.where(EntityTrack.recorded_at <= end_time)
        
        query = query.order_by(EntityTrack.recorded_at.asc()).limit(limit)
        
        result = await self._db.execute(query)
        tracks = result.scalars().all()
        
        # 转换为TrackPoint列表
        track_points: list[TrackPoint] = []
        for t in tracks:
            shape_obj = to_shape(t.location)
            track_points.append(TrackPoint(
                longitude=shape_obj.x,
                latitude=shape_obj.y,
                timestamp=t.recorded_at,
                speed_kmh=float(t.speed_kmh) if t.speed_kmh else None,
                heading=t.heading,
            ))
        
        logger.debug(f"查询轨迹: entity_id={entity_id}, 返回{len(track_points)}个点")
        return track_points


class LayerRepository:
    """图层数据仓库"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def get_by_code(self, code: str) -> Optional[Layer]:
        """根据编码查询图层"""
        result = await self._db.execute(
            select(Layer)
            .where(Layer.code == code)
            .where(Layer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, layer_id: UUID) -> Optional[Layer]:
        """根据ID查询图层"""
        result = await self._db.execute(
            select(Layer)
            .where(Layer.id == layer_id)
            .where(Layer.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def list_all(self) -> Sequence[Layer]:
        """获取所有图层"""
        result = await self._db.execute(
            select(Layer)
            .where(Layer.deleted_at.is_(None))
            .order_by(Layer.sort_order)
        )
        return result.scalars().all()
    
    async def update(self, layer: Layer, data: dict) -> Layer:
        """更新图层"""
        for key, value in data.items():
            if hasattr(layer, key):
                setattr(layer, key, value)
        
        await self._db.flush()
        await self._db.refresh(layer)
        
        logger.info(f"更新图层: code={layer.code}")
        return layer
    
    async def get_type_defaults(self, layer_code: str) -> Sequence[LayerTypeDefault]:
        """获取图层的类型定义"""
        result = await self._db.execute(
            select(LayerTypeDefault)
            .where(LayerTypeDefault.layer_code == layer_code)
        )
        return result.scalars().all()
    
    async def get_all_with_types(self) -> list[dict]:
        """获取所有图层及其支持的类型"""
        layers = await self.list_all()
        result = []
        
        for layer in layers:
            types = await self.get_type_defaults(layer.code)
            result.append({
                'code': layer.code,
                'name': layer.name,
                'category': layer.category,
                'visible_by_default': layer.visible_by_default,
                'style_config': layer.style_config,
                'update_interval_seconds': layer.update_interval_seconds,
                'supported_types': [
                    {
                        'type': t.entity_type,
                        'geometryKind': t.geometry_kind,
                        'icon': t.icon,
                        'propertyKeys': t.property_keys,
                    }
                    for t in types
                ]
            })
        
        return result
