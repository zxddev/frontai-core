"""
前端实体API路由

接口路径: /entities/*
对接v2 EntityService真实数据
"""

import logging
from datetime import datetime
from typing import Optional, Any
from uuid import UUID

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import EntityCreate, EntityUpdate, GeoJsonGeometry, EntitySource
from src.domains.frontend_api.common import ApiResponse
from src.domains.frontend_api.layers.schemas import EntityDto, EntityPage, EntityGeometry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entities", tags=["前端-实体"])


def get_entity_service(db: AsyncSession = Depends(get_db)) -> EntityService:
    return EntityService(db)


class CreateEntityRequest(BaseModel):
    """创建实体请求"""
    entities: list[dict[str, Any]]


class CreateEntityResponse(BaseModel):
    """创建实体响应"""
    created: list[EntityDto]


class UpdateEntityRequest(BaseModel):
    """更新实体请求"""
    geometry: Optional[dict] = None
    properties: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    visibleOnMap: Optional[bool] = None


class UpdateEntityResponse(BaseModel):
    """更新实体响应"""
    id: str
    updatedAt: str


class EntityIdsRequest(BaseModel):
    """实体ID列表请求"""
    ids: list[str]


def _convert_entity_to_dto(entity) -> EntityDto:
    """
    将v2实体转换为前端格式
    
    参考: docs/地图图层与后端对接规范.md 第2章
    """
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
    
    return EntityDto(
        id=str(entity.id),
        type=entity.type,
        layerCode=entity.layer_code,
        geometry=geometry,
        properties=entity.properties or {},
        visibleOnMap=entity.visible_on_map,
        styleOverrides={},
        createdAt=entity.created_at.isoformat() if entity.created_at else "",
        updatedAt=entity.updated_at.isoformat() if entity.updated_at else "",
    )


@router.get("", response_model=ApiResponse[EntityPage])
async def fetch_entities(
    layerCode: Optional[str] = Query(None, description="图层编码"),
    type: Optional[str] = Query(None, description="实体类型"),
    scenarioId: Optional[str] = Query(None, description="场景ID"),
    includeHidden: bool = Query(False, description="是否包含隐藏实体"),
    updatedSince: Optional[str] = Query(None, description="增量查询起始时间"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[EntityPage]:
    """
    获取实体列表 - 对接v2真实数据
    
    页面刷新/初始化时调用此接口获取所有实体
    """
    logger.info(f"获取实体列表, layerCode={layerCode}, type={type}, scenarioId={scenarioId}")
    
    try:
        is_visible = None if includeHidden else True
        scenario_uuid = UUID(scenarioId) if scenarioId else None
        result = await service.list(
            scenario_id=scenario_uuid,
            layer_code=layerCode,
            entity_types=type,
            is_visible=is_visible,
            page=page,
            page_size=pageSize,
        )
        
        items = [_convert_entity_to_dto(e) for e in result.items]
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
        logger.exception(f"获取实体列表失败: {e}")
        return ApiResponse.error(500, f"获取实体列表失败: {str(e)}")


@router.get("/{entityId}", response_model=ApiResponse[EntityDto])
async def fetch_entity_by_id(
    entityId: str,
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[EntityDto]:
    """
    获取单个实体 - 对接v2真实数据
    """
    logger.info(f"获取实体, entityId={entityId}")
    
    try:
        entity_uuid = UUID(entityId)
        result = await service.get_by_id(entity_uuid)
        if not result or not result.id:
            return ApiResponse.error(404, f"实体不存在: {entityId}")
        
        return ApiResponse.success(_convert_entity_to_dto(result))
        
    except ValueError:
        return ApiResponse.error(400, f"无效的实体ID格式: {entityId}")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "404" in error_msg:
            return ApiResponse.error(404, f"实体不存在: {entityId}")
        logger.exception(f"获取实体失败: {e}")
        return ApiResponse.error(500, f"获取实体失败: {str(e)}")


@router.post("", response_model=ApiResponse[CreateEntityResponse])
async def create_entities(
    request: CreateEntityRequest,
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[CreateEntityResponse]:
    """
    批量创建实体 - 对接v2真实数据
    """
    logger.info(f"创建实体, 数量={len(request.entities)}")
    
    try:
        created = []
        
        for entity_data in request.entities:
            geometry_data = entity_data.get("geometry", {})
            geometry = None
            if geometry_data:
                geometry = GeoJsonGeometry(
                    type=geometry_data.get("type", "Point"),
                    coordinates=geometry_data.get("coordinates", [0, 0]),
                )
            
            source_str = entity_data.get("source", "manual")
            source_map = {"user": "manual", "system": "system", "manual": "manual"}
            source = EntitySource(source_map.get(source_str, "manual"))
            
            entity_create = EntityCreate(
                layer_code=entity_data.get("layerCode", "layer.manual"),
                type=entity_data.get("type", "unknown"),
                geometry=geometry,
                properties=entity_data.get("properties", {}),
                visible_on_map=entity_data.get("visibleOnMap", True),
                is_dynamic=entity_data.get("dynamic", False),
                source=source,
            )
            
            entity = await service.create(entity_create)
            created.append(_convert_entity_to_dto(entity))
        
        return ApiResponse.success(CreateEntityResponse(created=created))
        
    except Exception as e:
        logger.exception(f"创建实体失败: {e}")
        return ApiResponse.error(500, f"创建实体失败: {str(e)}")


@router.patch("/{entityId}", response_model=ApiResponse[UpdateEntityResponse])
async def update_entity(
    entityId: str,
    request: UpdateEntityRequest,
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[UpdateEntityResponse]:
    """
    更新实体 - 对接v2真实数据
    """
    logger.info(f"更新实体, entityId={entityId}")
    
    try:
        entity_uuid = UUID(entityId)
        
        # 构建更新对象，只更新有值的字段
        update_data = {}
        if request.geometry:
            update_data['geometry'] = GeoJsonGeometry(
                type=request.geometry.get("type", "Point"),
                coordinates=request.geometry.get("coordinates", [0, 0]),
            )
        if request.properties is not None:
            update_data['properties'] = request.properties
        if request.visibleOnMap is not None:
            update_data['visible_on_map'] = request.visibleOnMap
        
        entity_update = EntityUpdate(**update_data)
        entity = await service.update(entity_uuid, entity_update)
        
        return ApiResponse.success(UpdateEntityResponse(
            id=str(entity.id),
            updatedAt=entity.updated_at.isoformat() if entity.updated_at else datetime.utcnow().isoformat(),
        ))
        
    except ValueError:
        return ApiResponse.error(400, f"无效的实体ID格式: {entityId}")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return ApiResponse.error(404, f"实体不存在: {entityId}")
        logger.exception(f"更新实体失败: {e}")
        return ApiResponse.error(500, f"更新实体失败: {str(e)}")


@router.delete("/{entityId}")
async def delete_entity(
    entityId: str,
    service: EntityService = Depends(get_entity_service),
):
    """
    删除实体 - 对接v2真实数据
    """
    logger.info(f"删除实体, entityId={entityId}")
    
    try:
        entity_uuid = UUID(entityId)
        await service.delete(entity_uuid)
        return ApiResponse.success(None, "删除成功")
        
    except ValueError:
        return ApiResponse.error(400, f"无效的实体ID格式: {entityId}")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return ApiResponse.error(404, f"实体不存在: {entityId}")
        logger.exception(f"删除实体失败: {e}")
        return ApiResponse.error(500, f"删除实体失败: {str(e)}")


@router.post("/by-ids", response_model=ApiResponse[list[EntityDto]])
async def get_entities_by_ids(
    request: EntityIdsRequest,
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[list[EntityDto]]:
    """
    批量获取实体 - 对接v2真实数据
    """
    logger.info(f"批量获取实体, ids={request.ids}")
    
    try:
        entities = []
        for entity_id in request.ids:
            try:
                entity_uuid = UUID(entity_id)
                result = await service.get_by_id(entity_uuid)
                if result and result.id:
                    entities.append(_convert_entity_to_dto(result))
            except ValueError:
                continue
        
        return ApiResponse.success(entities)
        
    except Exception as e:
        logger.exception(f"批量获取实体失败: {e}")
        return ApiResponse.error(500, f"批量获取实体失败: {str(e)}")
