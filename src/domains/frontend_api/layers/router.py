"""
前端图层API路由

接口路径: /layers/*
对接v2 LayerService真实数据
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.map_entities.service import LayerService
from src.domains.frontend_api.common import ApiResponse
from .schemas import LayerDto, LayerTypeDefinition, EntityDto, EntityPage, EntityGeometry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/layers", tags=["前端-图层"])


def get_layer_service(db: AsyncSession = Depends(get_db)) -> LayerService:
    return LayerService(db)


def _convert_layer(layer_data: dict) -> LayerDto:
    """将v2图层数据转换为前端格式"""
    supported_types = []
    for t in layer_data.get('supported_types', []):
        supported_types.append(LayerTypeDefinition(
            type=t.get('type', ''),
            geometryKind=t.get('geometry_kind', 'Point'),
            icon=t.get('icon'),
            propertyKeys=t.get('property_keys', []),
        ))
    
    return LayerDto(
        code=layer_data.get('code', ''),
        name=layer_data.get('name', ''),
        category=layer_data.get('category', 'system'),
        visibleByDefault=layer_data.get('visible_by_default', True),
        styleConfig=layer_data.get('style_config', {}),
        updateIntervalSeconds=layer_data.get('update_interval_seconds'),
        description=layer_data.get('description'),
        supportedTypes=supported_types,
    )


@router.get("", response_model=ApiResponse[list[LayerDto]])
async def fetch_layers(
    category: Optional[str] = Query(None, description="分类筛选"),
    service: LayerService = Depends(get_layer_service),
) -> ApiResponse[list[LayerDto]]:
    """
    获取图层列表 - 对接v2真实数据
    """
    logger.info(f"获取图层列表, category={category}")
    
    try:
        result = await service.list_all()
        
        layers = []
        for layer in result.layers:
            layer_dto = LayerDto(
                code=layer.code,
                name=layer.name,
                category=layer.category,
                visibleByDefault=layer.visible_by_default,
                styleConfig=layer.style_config,
                updateIntervalSeconds=layer.update_interval_seconds,
                supportedTypes=[
                    LayerTypeDefinition(
                        type=t.get('type', ''),
                        geometryKind=t.get('geometry_kind', 'Point'),
                        icon=t.get('icon'),
                        propertyKeys=t.get('property_keys', []),
                    ) for t in layer.supported_types
                ],
            )
            
            if category and layer.category != category:
                continue
            layers.append(layer_dto)
        
        return ApiResponse.success(layers)
        
    except Exception as e:
        logger.exception(f"获取图层列表失败: {e}")
        return ApiResponse.error(500, f"获取图层列表失败: {str(e)}")


@router.get("/{code}", response_model=ApiResponse[LayerDto])
async def fetch_layer_by_code(
    code: str,
    service: LayerService = Depends(get_layer_service),
) -> ApiResponse[LayerDto]:
    """
    获取指定图层 - 对接v2真实数据
    """
    logger.info(f"获取图层, code={code}")
    
    try:
        result = await service.list_all()
        
        for layer in result.layers:
            if layer.code == code:
                layer_dto = LayerDto(
                    code=layer.code,
                    name=layer.name,
                    category=layer.category,
                    visibleByDefault=layer.visible_by_default,
                    styleConfig=layer.style_config,
                    updateIntervalSeconds=layer.update_interval_seconds,
                    supportedTypes=[
                        LayerTypeDefinition(
                            type=t.get('type', ''),
                            geometryKind=t.get('geometry_kind', 'Point'),
                            icon=t.get('icon'),
                            propertyKeys=t.get('property_keys', []),
                        ) for t in layer.supported_types
                    ],
                )
                return ApiResponse.success(layer_dto)
        
        return ApiResponse.error(404, f"图层不存在: {code}")
        
    except Exception as e:
        logger.exception(f"获取图层失败: {e}")
        return ApiResponse.error(500, f"获取图层失败: {str(e)}")


@router.get("/{code}/entities", response_model=ApiResponse[EntityPage])
async def fetch_layer_entities(
    code: str,
    type: Optional[str] = Query(None, description="实体类型筛选"),
    scenarioId: Optional[str] = Query(None, description="场景ID"),
    includeHidden: bool = Query(False, description="是否包含隐藏实体"),
    updatedSince: Optional[str] = Query(None, description="增量查询起始时间"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[EntityPage]:
    """
    获取图层下的实体 - 对接v2真实数据
    
    页面刷新/初始化时按图层获取实体
    """
    logger.info(f"获取图层实体, code={code}, type={type}, scenarioId={scenarioId}")
    
    try:
        from uuid import UUID
        from src.domains.map_entities.service import EntityService
        entity_service = EntityService(db)
        
        is_visible = None if includeHidden else True
        scenario_uuid = UUID(scenarioId) if scenarioId else None
        result = await entity_service.list(
            scenario_id=scenario_uuid,
            layer_code=code,
            entity_types=type,
            is_visible=is_visible,
            page=page,
            page_size=pageSize,
        )
        
        # 转换为前端格式（参考 docs/地图图层与后端对接规范.md 第2章）
        items = []
        for entity in result.items:
            geometry = None
            if entity.geometry:
                geometry_dict = {
                    "type": entity.geometry.type,
                    "coordinates": entity.geometry.coordinates,
                }
                # 圆形区域需要补充 center 和 radius（前端 handleEntity.js 需要）
                circle_types = {'danger_area', 'safety_area', 'command_post_candidate'}
                if entity.type in circle_types:
                    coords = entity.geometry.coordinates
                    if coords and len(coords) >= 2:
                        geometry_dict['center'] = coords[:2]
                    props = entity.properties or {}
                    if 'range' in props:
                        geometry_dict['radius'] = props['range']
                # weather_area 需要 bbox
                if entity.type == 'weather_area':
                    props = entity.properties or {}
                    if 'bbox' in props:
                        geometry_dict['bbox'] = props['bbox']
                geometry = EntityGeometry(**geometry_dict)
            
            items.append(EntityDto(
                id=str(entity.id),
                type=entity.type,
                layerCode=entity.layer_code,
                geometry=geometry,
                properties=entity.properties or {},
                visibleOnMap=entity.visible_on_map,
                styleOverrides={},
                createdAt=entity.created_at.isoformat() if entity.created_at else "",
                updatedAt=entity.updated_at.isoformat() if entity.updated_at else "",
            ))
        
        total = result.total
        total_pages = (total + pageSize - 1) // pageSize if total > 0 else 0
        
        return ApiResponse.success(EntityPage(
            items=items,
            total=total,
            page=page,
            pageSize=pageSize,
            totalPages=total_pages,
        ))
        
    except Exception as e:
        logger.exception(f"获取图层实体失败: {e}")
        return ApiResponse.error(500, f"获取图层实体失败: {str(e)}")
