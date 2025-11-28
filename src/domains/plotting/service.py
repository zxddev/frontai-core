"""
态势标绘服务

封装EntityService，根据标绘类型自动填充正确的properties，
确保前端能正确渲染动画效果。

调用方式:
1. 其他业务模块直接 import PlottingService
2. REST API 调用
3. 对话Agent通过Tools调用
"""
from __future__ import annotations

import logging
from typing import Dict, Any
from uuid import UUID

from src.core.database import AsyncSessionLocal
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import (
    EntityCreate, EntityType, EntitySource, GeoJsonGeometry
)
from .schemas import (
    PlottingType, PlotPointRequest, PlotCircleRequest,
    PlotPolygonRequest, PlotRouteRequest, PlottingResponse,
    PlotEventRangeRequest, PlotWeatherAreaRequest
)

logger = logging.getLogger(__name__)


# 标绘类型 -> 图层编码映射
# 必须与前端定义的图层一致，参考: docs/地图图层与后端对接规范.md
# 前端有效图层: eventLayer, pathLayer, resourceLayer, equipmentLayer,
#              realtimeEquipmentLayer, weatherLayer, disposeLayer, rescueLayer
PLOTTING_LAYER_MAP: Dict[PlottingType, str] = {
    # 事件图层 (eventLayer)
    PlottingType.event_point: "layer.event",
    PlottingType.situation_point: "layer.event",
    PlottingType.event_range: "layer.event",
    # 救援图层 (rescueLayer)
    PlottingType.rescue_target: "layer.rescue",
    # 前突处置图层 (disposeLayer) - 圆形区域、多边形区域、安置点、指挥点
    PlottingType.danger_area: "layer.dispose",
    PlottingType.safety_area: "layer.dispose",
    PlottingType.investigation_area: "layer.dispose",
    PlottingType.resettle_point: "layer.dispose",
    PlottingType.command_post_candidate: "layer.dispose",
    # 应急资源图层 (resourceLayer)
    PlottingType.resource_point: "layer.resource",
    # 路径图层 (pathLayer)
    PlottingType.planned_route: "layer.path",
    # 天气图层 (weatherLayer)
    PlottingType.weather_area: "layer.weather",
}


class PlottingService:
    """态势标绘服务 - 提供统一的标绘能力"""
    
    @staticmethod
    async def plot_point(request: PlotPointRequest) -> PlottingResponse:
        """
        标绘点类实体
        
        支持: event_point, rescue_target, situation_point, resettle_point, resource_point
        
        前端渲染效果:
        - event_point: ADD_EVENT_POINT 事件图标
        - rescue_target: ADD_POINT_IMG 带波纹动画
        - situation_point: ADD_POINT_LABEL 文字标签
        """
        entity_type = EntityType(request.plotting_type.value)
        layer_code = PLOTTING_LAYER_MAP.get(request.plotting_type, "layer.manual")
        
        # 根据类型构建properties，确保前端能正确渲染
        properties: Dict[str, Any] = {
            "name": request.name,
            "locationName": request.name,
        }
        
        if request.description:
            properties["textContent"] = request.description
        
        # rescue_target 特殊处理（触发波纹动画）
        if request.plotting_type == PlottingType.rescue_target:
            properties["level"] = request.level or 3
            properties["origin"] = "ai_plotting"
        
        # situation_point 文字标签
        if request.plotting_type == PlottingType.situation_point:
            properties["textContent"] = request.description or request.name
        
        if request.extra_properties:
            properties.update(request.extra_properties)
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=entity_type,
                layer_code=layer_code,
                geometry=GeoJsonGeometry(
                    type="Point",
                    coordinates=[request.longitude, request.latitude]
                ),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘点: type={request.plotting_type.value}, id={entity.id}, "
            f"location=({request.longitude}, {request.latitude})"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type=request.plotting_type.value,
            message=f"已标绘{request.plotting_type.value}: {request.name}"
        )
    
    @staticmethod
    async def plot_circle(request: PlotCircleRequest) -> PlottingResponse:
        """
        标绘圆形区域
        
        支持: danger_area(橙), safety_area(绿), command_post_candidate(蓝)
        
        前端渲染效果: ADD_AREA_POINT（圆形区域+中心图标）
        """
        entity_type = EntityType(request.plotting_type.value)
        layer_code = PLOTTING_LAYER_MAP.get(request.plotting_type, "layer.dispose")
        
        # 前端handleEntity.js读取properties.range作为半径
        properties: Dict[str, Any] = {
            "locationName": request.name,
            "range": request.radius_m,
            "isSelect": "1" if request.is_selected else "0",
        }
        
        if request.description:
            properties["textContent"] = request.description
        
        # 圆形几何 - 前端需要geometry.center和geometry.radius
        geometry_data: Dict[str, Any] = {
            "type": "Point",
            "coordinates": [request.center_longitude, request.center_latitude],
            "center": [request.center_longitude, request.center_latitude],
            "radius": request.radius_m,
        }
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=entity_type,
                layer_code=layer_code,
                geometry=GeoJsonGeometry(**geometry_data),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘圆形区域: type={request.plotting_type.value}, id={entity.id}, "
            f"center=({request.center_longitude}, {request.center_latitude}), radius={request.radius_m}m"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type=request.plotting_type.value,
            message=f"已标绘{request.plotting_type.value}: {request.name}, 半径{request.radius_m}米"
        )
    
    @staticmethod
    async def plot_polygon(request: PlotPolygonRequest) -> PlottingResponse:
        """
        标绘多边形区域
        
        支持: investigation_area
        
        前端渲染效果: ADD_POLYGON_AREA
        """
        entity_type = EntityType(request.plotting_type.value)
        layer_code = PLOTTING_LAYER_MAP.get(request.plotting_type, "layer.dispose")
        
        properties: Dict[str, Any] = {
            "name": request.name,
        }
        if request.description:
            properties["textContent"] = request.description
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=entity_type,
                layer_code=layer_code,
                geometry=GeoJsonGeometry(
                    type="Polygon",
                    coordinates=[request.coordinates]  # GeoJSON Polygon需要嵌套数组
                ),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘多边形: type={request.plotting_type.value}, id={entity.id}, "
            f"vertices={len(request.coordinates)}"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type=request.plotting_type.value,
            message=f"已标绘{request.plotting_type.value}: {request.name}"
        )
    
    @staticmethod
    async def plot_route(request: PlotRouteRequest) -> PlottingResponse:
        """
        标绘规划路线
        
        前端渲染效果: ADD_NAVIGATION_ROUTE（导航动画）
        """
        # 前端handleEntity.js读取properties.deviceType, routeType, isSelect
        properties: Dict[str, Any] = {
            "name": request.name,
            "deviceType": request.device_type,
            "routeType": "planned_route",
            "isSelect": "1" if request.is_selected else "0",
        }
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=EntityType.planned_route,
                layer_code=PLOTTING_LAYER_MAP[PlottingType.planned_route],
                geometry=GeoJsonGeometry(
                    type="LineString",
                    coordinates=request.coordinates
                ),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘路线: id={entity.id}, name={request.name}, "
            f"points={len(request.coordinates)}, device={request.device_type}"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type="planned_route",
            message=f"已标绘路线: {request.name}"
        )
    
    @staticmethod
    async def delete_plot(entity_id: UUID) -> PlottingResponse:
        """删除标绘实体"""
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            await service.delete(entity_id)
            await db.commit()
        
        logger.info(f"删除标绘: id={entity_id}")
        
        return PlottingResponse(
            success=True,
            entity_id=entity_id,
            entity_type="",
            message=f"已删除标绘: {entity_id}"
        )
    
    @staticmethod
    async def plot_event_range(request: PlotEventRangeRequest) -> PlottingResponse:
        """
        标绘事件区域范围（三层多边形）
        
        前端渲染效果: 红色半透明三层区域（外/中/内）
        """
        layer_code = PLOTTING_LAYER_MAP[PlottingType.event_range]
        
        properties: Dict[str, Any] = {
            "name": request.name,
        }
        if request.description:
            properties["textContent"] = request.description
        
        # 前端支持数组格式: [外圈, 中圈, 内圈]
        # GeoJSON MultiPolygon 需要 [[ring], [ring], [ring]] 格式
        geometry_data: Dict[str, Any] = {
            "type": "MultiPolygon",
            "coordinates": [
                [request.outer_ring],   # 每个 polygon 需要套一层数组
                [request.middle_ring],
                [request.inner_ring],
            ]
        }
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=EntityType.event_range,
                layer_code=layer_code,
                geometry=GeoJsonGeometry(**geometry_data),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘事件区域范围: id={entity.id}, name={request.name}"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type="event_range",
            message=f"已标绘事件区域范围: {request.name}"
        )
    
    @staticmethod
    async def plot_weather_area(request: PlotWeatherAreaRequest) -> PlottingResponse:
        """
        标绘天气区域（雨区）
        
        前端渲染效果: 雨区粒子特效 + 自动飞行
        """
        layer_code = PLOTTING_LAYER_MAP[PlottingType.weather_area]
        
        properties: Dict[str, Any] = {
            "name": request.name,
        }
        if request.description:
            properties["textContent"] = request.description
        
        # 前端需要 geometry.bbox 格式: [minLng, minLat, maxLng, maxLat]
        geometry_data: Dict[str, Any] = {
            "type": "Polygon",
            "bbox": [
                request.min_longitude,
                request.min_latitude,
                request.max_longitude,
                request.max_latitude,
            ],
            "coordinates": [[
                [request.min_longitude, request.min_latitude],
                [request.max_longitude, request.min_latitude],
                [request.max_longitude, request.max_latitude],
                [request.min_longitude, request.max_latitude],
                [request.min_longitude, request.min_latitude],
            ]]
        }
        
        async with AsyncSessionLocal() as db:
            service = EntityService(db)
            entity = await service.create(EntityCreate(
                type=EntityType.weather_area,
                layer_code=layer_code,
                geometry=GeoJsonGeometry(**geometry_data),
                properties=properties,
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=request.scenario_id,
            ))
            await db.commit()
        
        logger.info(
            f"标绘天气区域: id={entity.id}, name={request.name}, "
            f"bbox=[{request.min_longitude}, {request.min_latitude}, {request.max_longitude}, {request.max_latitude}]"
        )
        
        return PlottingResponse(
            success=True,
            entity_id=entity.id,
            entity_type="weather_area",
            message=f"已标绘天气区域: {request.name}"
        )
