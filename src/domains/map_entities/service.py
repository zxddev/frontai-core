"""
地图实体业务服务层

职责: 业务逻辑、验证、异常处理
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON
from geoalchemy2.shape import to_shape

from src.core.exceptions import NotFoundError, ConflictError, ValidationError
from .repository import EntityRepository, LayerRepository


def _get_stomp_broker():
    """延迟导入避免循环依赖"""
    from src.core.stomp.broker import stomp_broker
    return stomp_broker
from .schemas import (
    EntityCreate, EntityUpdate, EntityResponse, EntityListResponse,
    EntityLocationUpdate, BatchLocationUpdate, EntityWithDistance,
    PlotCreate, PlotResponse, PlotType,
    LayerResponse, LayerUpdate, LayerWithTypes, LayerListResponse,
    TrackPoint, TrackResponse,
    Location, GeoJsonGeometry, EntityType, EntitySource
)

logger = logging.getLogger(__name__)


class EntityService:
    """实体业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._entity_repo = EntityRepository(db)
        self._layer_repo = LayerRepository(db)
        self._db = db
    
    async def create(
        self, 
        data: EntityCreate, 
        created_by: Optional[str] = None
    ) -> EntityResponse:
        """
        创建实体
        
        业务规则:
        - 验证图层是否存在
        - 验证实体类型是否被图层支持
        """
        layer = await self._layer_repo.get_by_code(data.layer_code)
        if not layer:
            raise NotFoundError("Layer", data.layer_code)
        
        entity = await self._entity_repo.create(data, created_by)
        response = await self._to_response(entity)
        
        # 构建广播用的 geometry（为圆形区域补充 center 和 radius）
        broadcast_geometry = response.geometry.model_dump() if response.geometry else {}
        circle_types = {'danger_area', 'safety_area', 'command_post_candidate'}
        if response.type.value in circle_types:
            # 前端 handleEntity.js 需要 geometry.center 和 geometry.radius
            coords = broadcast_geometry.get('coordinates', [])
            if coords and len(coords) >= 2:
                broadcast_geometry['center'] = coords[:2]
            # 半径从 properties.range 获取
            if 'range' in response.properties:
                broadcast_geometry['radius'] = response.properties['range']
        
        # 广播实体创建事件（通过WebSocket发送给前端，包含完整数据）
        broadcast_data = {
            "id": str(response.id),
            "type": response.type.value,
            "layerCode": response.layer_code,
            "geometry": broadcast_geometry,
            "properties": response.properties,
            "visibleOnMap": response.visible_on_map,
            "styleOverrides": response.style_overrides,
            "source": response.source.value,
            "scenarioId": str(data.scenario_id) if data.scenario_id else None,
            "createdAt": response.created_at.isoformat(),
            "updatedAt": response.updated_at.isoformat(),
        }
        logger.info(f"广播实体创建: type={response.type.value}, geometry={broadcast_data['geometry']}")
        await _get_stomp_broker().broadcast_entity_create(broadcast_data)
        
        # 如果是危险区域（前端绘制），触发风险检测通知
        if response.type.value == 'danger_area':
            logger.info(f"[危险区域创建] 检测到 danger_area 类型，准备触发风险检测: entity_id={entity.id}")
            await self._trigger_danger_area_risk_check(response, data.scenario_id)
        
        return response
    
    async def _trigger_danger_area_risk_check(
        self, 
        entity: EntityResponse, 
        scenario_id: Optional[UUID]
    ) -> None:
        """
        当前端创建危险区域时，触发风险检测通知
        
        检测所有活跃路线和移动中的车辆是否穿过该危险区域
        """
        try:
            from src.domains.frontend_api.risk_area.schemas import RiskAreaResponse
            from src.domains.frontend_api.risk_area.service import RiskAreaService
            
            # 构建一个类似 RiskAreaResponse 的对象
            # 从 entity 的 properties 中提取风险信息
            props = entity.properties or {}
            
            # 创建一个模拟的 RiskAreaResponse
            risk_level = props.get('risk_level', 7)  # 默认高风险
            passage_status = props.get('passage_status', 'needs_reconnaissance')
            
            # 根据风险等级确定严重程度
            if risk_level >= 9:
                severity = "critical"
            elif risk_level >= 7:
                severity = "high"
            elif risk_level >= 5:
                severity = "medium"
            else:
                severity = "low"
            
            risk_area = RiskAreaResponse(
                id=entity.id,
                scenario_id=scenario_id,
                name=props.get('name', '前端绘制的危险区域'),
                area_type=props.get('area_type', 'other'),
                risk_level=risk_level,
                severity=severity,
                passage_status=passage_status,
                passable=passage_status not in ('confirmed_blocked',),
                passable_vehicle_types=None,
                speed_reduction_percent=50 if passage_status == 'passable_with_caution' else 100,
                reconnaissance_required=passage_status == 'needs_reconnaissance',
                geometry_geojson=entity.geometry.model_dump() if entity.geometry else None,
                description=props.get('description', ''),
                created_at=entity.created_at,
                updated_at=entity.updated_at,
            )
            
            # 调用风险区域服务的通知方法
            risk_service = RiskAreaService(self._db)
            await risk_service._notify_risk_area_change(
                risk_area=risk_area,
                change_type="created",
            )
            
            logger.info(
                f"[危险区域风险检测] 已触发: entity_id={entity.id}, "
                f"scenario_id={scenario_id}"
            )
            
        except Exception as e:
            # 风险检测失败不阻塞实体创建
            logger.warning(f"[危险区域风险检测] 触发失败: {e}", exc_info=True)
    
    async def get_by_id(self, entity_id: UUID) -> EntityResponse:
        """根据ID获取实体"""
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        return await self._to_response(entity)
    
    async def list(
        self,
        scenario_id: Optional[UUID] = None,
        entity_types: Optional[str] = None,
        layer_code: Optional[str] = None,
        is_visible: Optional[bool] = None,
        bbox: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> EntityListResponse:
        """
        分页查询实体列表
        
        Args:
            entity_types: 逗号分隔的类型列表
            bbox: "minLng,minLat,maxLng,maxLat"
        """
        types_list = entity_types.split(',') if entity_types else None
        bbox_tuple = None
        if bbox:
            parts = bbox.split(',')
            if len(parts) == 4:
                bbox_tuple = tuple(float(p) for p in parts)
        
        items, total = await self._entity_repo.list(
            scenario_id, types_list, layer_code, is_visible, bbox_tuple, page, page_size
        )
        
        responses = [await self._to_response(e) for e in items]
        return EntityListResponse(items=responses, total=total)
    
    async def list_in_bounds(
        self,
        scenario_id: UUID,
        bounds: str,
        entity_types: Optional[str] = None,
    ) -> EntityListResponse:
        """
        查询边界框内的实体
        
        Args:
            bounds: "minLng,minLat,maxLng,maxLat"
        """
        parts = bounds.split(',')
        if len(parts) != 4:
            raise ValidationError(
                error_code="EN4002",
                message="无效的边界框格式，应为: minLng,minLat,maxLng,maxLat"
            )
        
        bounds_tuple = tuple(float(p) for p in parts)
        types_list = entity_types.split(',') if entity_types else None
        
        items = await self._entity_repo.list_in_bounds(scenario_id, bounds_tuple, types_list)
        responses = [await self._to_response(e) for e in items]
        
        return EntityListResponse(items=responses, total=len(responses))
    
    async def list_nearby(
        self,
        scenario_id: UUID,
        center: str,
        radius_km: float,
        entity_types: Optional[str] = None,
    ) -> list[EntityWithDistance]:
        """
        查询附近实体
        
        Args:
            center: "lng,lat"
        """
        parts = center.split(',')
        if len(parts) != 2:
            raise ValidationError(
                error_code="EN4002",
                message="无效的中心点格式，应为: lng,lat"
            )
        
        center_lng, center_lat = float(parts[0]), float(parts[1])
        types_list = entity_types.split(',') if entity_types else None
        
        items = await self._entity_repo.list_nearby(
            scenario_id, center_lng, center_lat, radius_km, types_list
        )
        
        results = []
        for entity, distance in items:
            geom = to_shape(entity.geometry)
            results.append(EntityWithDistance(
                id=entity.id,
                type=entity.type,
                name=entity.properties.get('name'),
                location=Location(longitude=geom.x, latitude=geom.y),
                distance_km=round(distance, 2),
            ))
        
        return results
    
    async def update(self, entity_id: UUID, data: EntityUpdate) -> EntityResponse:
        """更新实体"""
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        
        entity = await self._entity_repo.update(entity, data)
        response = await self._to_response(entity)
        
        # 广播实体更新事件（通过WebSocket发送给前端，包含完整数据）
        await _get_stomp_broker().broadcast_entity_update({
            "id": str(response.id),
            "type": response.type.value,
            "layerCode": response.layer_code,
            "geometry": response.geometry.model_dump(),
            "properties": response.properties,
            "visibleOnMap": response.visible_on_map,
            "styleOverrides": response.style_overrides,
            "source": response.source.value,
            "scenarioId": str(entity.scenario_id) if entity.scenario_id else None,
            "updatedAt": response.updated_at.isoformat(),
        })
        
        return response
    
    async def update_location(
        self, 
        entity_id: UUID, 
        data: EntityLocationUpdate
    ) -> EntityResponse:
        """
        更新单个实体位置
        
        位置更新时自动记录轨迹点（仅动态实体）
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        
        entity = await self._entity_repo.update_location(
            entity, data.location.longitude, data.location.latitude
        )
        
        # 动态实体自动记录轨迹点
        if entity.is_dynamic:
            await self._entity_repo.add_track_point(
                entity_id=entity.id,
                longitude=data.location.longitude,
                latitude=data.location.latitude,
                speed_kmh=float(data.speed_kmh) if data.speed_kmh else None,
                heading=data.heading,
            )
            logger.debug(f"实体{entity_id}轨迹点已记录")
        
        # 广播位置更新（通过WebSocket发送给前端）
        await _get_stomp_broker().broadcast_location({
            "id": str(entity.id),
            "type": entity.type,
            "location": data.location.model_dump(),
            "speed_kmh": float(data.speed_kmh) if data.speed_kmh else None,
            "heading": data.heading,
        })
        
        return await self._to_response(entity)
    
    async def batch_update_location(
        self, 
        data: BatchLocationUpdate
    ) -> dict[str, Any]:
        """批量更新实体位置"""
        success_count = 0
        failed_ids = []
        
        for item in data.updates:
            entity = await self._entity_repo.get_by_id(item.entity_id)
            if not entity:
                failed_ids.append(str(item.entity_id))
                continue
            
            await self._entity_repo.update_location(
                entity, item.location.longitude, item.location.latitude
            )
            success_count += 1
            
            # 广播位置更新（通过WebSocket发送给前端）
            await _get_stomp_broker().broadcast_location({
                "id": str(entity.id),
                "type": entity.type,
                "location": item.location.model_dump(),
                "speed_kmh": float(item.speed_kmh) if item.speed_kmh else None,
                "heading": item.heading,
            })
        
        return {
            "success_count": success_count,
            "failed_count": len(failed_ids),
            "failed_ids": failed_ids,
        }
    
    async def update_visibility(
        self, 
        entity_id: UUID, 
        visible: bool
    ) -> EntityResponse:
        """更新实体可见性"""
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        
        entity = await self._entity_repo.update_visibility(entity, visible)
        return await self._to_response(entity)
    
    async def delete(self, entity_id: UUID) -> None:
        """删除实体"""
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        
        # 保存删除前的实体信息用于广播
        delete_info = {
            "id": str(entity.id),
            "type": entity.type,
            "layerCode": entity.layer_code,
        }
        
        await self._entity_repo.delete(entity)
        
        # 广播实体删除事件（通过WebSocket发送给前端，包含完整信息）
        # 注意：不传入 scenario_id，广播给所有订阅者（前端未绑定场景）
        await _get_stomp_broker().broadcast_entity_delete_full(delete_info)
    
    async def create_plot(
        self, 
        data: PlotCreate, 
        created_by: Optional[str] = None
    ) -> PlotResponse:
        """
        创建态势标绘
        
        将标绘转换为实体存储
        """
        # 验证图层
        layer = await self._layer_repo.get_by_code(data.layer_code)
        if not layer:
            raise NotFoundError("Layer", data.layer_code)
        
        # 映射标绘类型到实体类型
        plot_to_entity_type = {
            PlotType.point: EntityType.situation_point,
            PlotType.polyline: EntityType.planned_route,
            PlotType.polygon: EntityType.danger_area,
            PlotType.circle: EntityType.danger_area,
            PlotType.arrow: EntityType.planned_route,
            PlotType.text: EntityType.situation_point,
        }
        
        entity_type = plot_to_entity_type.get(data.plot_type)
        if not entity_type:
            raise ValidationError(
                error_code="EN4006",
                message=f"不支持的标绘类型: {data.plot_type}"
            )
        
        # 创建实体
        entity_data = EntityCreate(
            type=entity_type,
            layer_code=data.layer_code,
            geometry=data.geometry,
            properties={
                **data.properties,
                "name": data.name,
                "plot_type": data.plot_type.value,
            },
            source=EntitySource.manual,
            visible_on_map=True,
            style_overrides=data.style,
            scenario_id=data.scenario_id,
        )
        
        entity = await self._entity_repo.create(entity_data, created_by)
        
        return PlotResponse(
            id=entity.id,
            plot_type=data.plot_type,
            name=data.name,
            created_at=entity.created_at,
        )
    
    async def get_tracks(
        self,
        entity_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sample_interval: Optional[int] = None,
    ) -> TrackResponse:
        """
        获取实体历史轨迹
        
        Args:
            entity_id: 实体ID
            start_time: 开始时间
            end_time: 结束时间
            sample_interval: 采样间隔（秒），用于稀疏轨迹点
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Entity", str(entity_id))
        
        # 查询轨迹点
        tracks = await self._entity_repo.get_tracks(
            entity_id=entity_id,
            start_time=start_time,
            end_time=end_time,
        )
        
        # 采样过滤（按时间间隔）
        if sample_interval and sample_interval > 0 and len(tracks) > 1:
            sampled_tracks: list[TrackPoint] = [tracks[0]]
            last_time = tracks[0].timestamp
            for point in tracks[1:]:
                delta = (point.timestamp - last_time).total_seconds()
                if delta >= sample_interval:
                    sampled_tracks.append(point)
                    last_time = point.timestamp
            # 保证最后一个点被包含
            if tracks[-1] != sampled_tracks[-1]:
                sampled_tracks.append(tracks[-1])
            tracks = sampled_tracks
        
        # 计算总距离（Haversine公式）
        total_distance_km: Optional[float] = None
        if len(tracks) >= 2:
            total_distance_km = 0.0
            for i in range(1, len(tracks)):
                prev = tracks[i - 1]
                curr = tracks[i]
                total_distance_km += self._haversine_distance(
                    prev.latitude, prev.longitude,
                    curr.latitude, curr.longitude
                )
            total_distance_km = round(total_distance_km, 3)
        
        # 计算总时长
        duration_min: Optional[float] = None
        if len(tracks) >= 2:
            delta = tracks[-1].timestamp - tracks[0].timestamp
            duration_min = round(delta.total_seconds() / 60, 2)
        
        logger.info(f"获取轨迹: entity_id={entity_id}, 点数={len(tracks)}, 距离={total_distance_km}km")
        
        return TrackResponse(
            entity_id=entity_id,
            tracks=tracks,
            total_distance_km=total_distance_km,
            duration_min=duration_min,
        )
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Haversine公式计算两点间球面距离（km）
        
        精度足够用于轨迹距离统计
        """
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371.0  # 地球半径(km)
        
        lat1_rad = radians(lat1)
        lat2_rad = radians(lat2)
        delta_lat = radians(lat2 - lat1)
        delta_lon = radians(lon2 - lon1)
        
        a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        return R * c
    
    async def _to_response(self, entity) -> EntityResponse:
        """ORM模型转响应模型"""
        geojson = await self._entity_repo.get_geometry_as_geojson(entity)
        
        return EntityResponse(
            id=entity.id,
            type=entity.type,
            layer_code=entity.layer_code,
            device_id=entity.device_id,
            geometry=GeoJsonGeometry(**geojson) if geojson else None,
            properties=entity.properties or {},
            source=entity.source,
            visible_on_map=entity.visible_on_map,
            is_dynamic=entity.is_dynamic,
            last_position_at=entity.last_position_at,
            style_overrides=entity.style_overrides or {},
            scenario_id=entity.scenario_id,
            event_id=entity.event_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class LayerService:
    """图层业务服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._repo = LayerRepository(db)
    
    async def list_all(self) -> LayerListResponse:
        """获取所有图层及其支持的类型"""
        layers_data = await self._repo.get_all_with_types()
        
        layers = [
            LayerWithTypes(
                code=l['code'],
                name=l['name'],
                category=l['category'],
                visible_by_default=l['visible_by_default'],
                style_config=l['style_config'] or {},
                update_interval_seconds=l['update_interval_seconds'],
                supported_types=l['supported_types'],
            )
            for l in layers_data
        ]
        
        return LayerListResponse(layers=layers)
    
    async def get_by_id(self, layer_id: UUID) -> LayerResponse:
        """根据ID获取图层"""
        layer = await self._repo.get_by_id(layer_id)
        if not layer:
            raise NotFoundError("Layer", str(layer_id))
        return self._to_response(layer)
    
    async def update(self, layer_id: UUID, data: LayerUpdate) -> LayerResponse:
        """更新图层配置"""
        layer = await self._repo.get_by_id(layer_id)
        if not layer:
            raise NotFoundError("Layer", str(layer_id))
        
        update_data = {}
        if data.is_visible is not None:
            update_data['visible_by_default'] = data.is_visible
        if data.z_index is not None:
            update_data['sort_order'] = data.z_index
        if data.style is not None:
            update_data['style_config'] = data.style
        
        if update_data:
            layer = await self._repo.update(layer, update_data)
        
        return self._to_response(layer)
    
    def _to_response(self, layer) -> LayerResponse:
        """ORM模型转响应模型"""
        return LayerResponse(
            id=layer.id,
            code=layer.code,
            name=layer.name,
            category=layer.category,
            visible_by_default=layer.visible_by_default,
            style_config=layer.style_config or {},
            update_interval_seconds=layer.update_interval_seconds,
            description=layer.description,
            sort_order=layer.sort_order,
        )
