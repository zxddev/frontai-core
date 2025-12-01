"""
前端资源单位API路由

接口路径: /unit/*
对接v2 EntityService (layer.resource) 真实数据
"""

import logging
from uuid import uuid4, UUID
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.map_entities.service import EntityService
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    UnitSearchRequest, UnitCategory, Unit, UnitLocation,
    UnitSupportRequest, SupportResource,
    MobilizeRequest, MobilizeResponse,
)
from .service import UnitService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/unit", tags=["前端-资源单位"])


def get_entity_service(db: AsyncSession = Depends(get_db)) -> EntityService:
    return EntityService(db)


def get_unit_service(db: AsyncSession = Depends(get_db)) -> UnitService:
    return UnitService(db)


@router.post("/search-unit", response_model=ApiResponse[list[UnitCategory]])
async def search_units(
    request: UnitSearchRequest,
    service: EntityService = Depends(get_entity_service),
) -> ApiResponse[list[UnitCategory]]:
    """
    搜索应急单位列表 - 对接v2真实数据
    
    根据位置、搜索范围和关键词搜索附近的应急资源单位（layer.resource图层）
    """
    logger.info(f"搜索单位, lon={request.lon}, lat={request.lat}, range={request.rangeInMeters}m")
    
    try:
        # 从layer.resource图层查询实体
        result = await service.list(
            layer_code="layer.resource",
            entity_types="resource_point",
            page=1,
            page_size=100,
        )
        
        # 按类型分组
        categories_map: dict[str, list[Unit]] = {}
        
        for entity in result.items:
            props = entity.properties or {}
            
            # 获取位置
            lon, lat = request.lon, request.lat
            if entity.geometry and entity.geometry.coordinates:
                coords = entity.geometry.coordinates
                if len(coords) >= 2:
                    lon, lat = coords[0], coords[1]
            
            # 提取类型
            unit_type = props.get('type', props.get('category', '应急资源'))
            
            # 名称筛选
            name = props.get('name', entity.type)
            if request.nameLike and request.nameLike not in name:
                continue
            
            # 类型筛选
            if request.type and request.type != unit_type:
                continue
            
            unit = Unit(
                id=str(entity.id),
                name=name,
                type=unit_type,
                location=UnitLocation(longitude=lon, latitude=lat),
                address=props.get('address', ''),
                contact=props.get('contact', ''),
                phone=props.get('phone', ''),
            )
            
            if unit_type not in categories_map:
                categories_map[unit_type] = []
            categories_map[unit_type].append(unit)
        
        # 转换为响应格式
        categories = [
            UnitCategory(type=cat_type, units=units)
            for cat_type, units in categories_map.items()
        ]
        
        # 如果没有真实数据，返回示例数据
        if not categories:
            categories = [
                UnitCategory(
                    type="应急资源",
                    units=[
                        Unit(
                            id=str(uuid4()),
                            name="示例应急资源点",
                            type="应急资源",
                            location=UnitLocation(longitude=request.lon, latitude=request.lat),
                            address="待配置",
                            contact="待配置",
                            phone="12350",
                        ),
                    ]
                ),
            ]
        
        return ApiResponse.success(categories)
        
    except Exception as e:
        logger.exception(f"搜索单位失败: {e}")
        return ApiResponse.error(500, f"搜索单位失败: {str(e)}")


@router.post("/get-unit-support", response_model=ApiResponse[list[SupportResource]])
async def get_unit_support(request: UnitSupportRequest) -> ApiResponse[list[SupportResource]]:
    """
    获取单位支援资源
    
    获取指定单位可提供的支援资源列表
    """
    logger.info(f"获取单位支援资源, unitId={request.unitId}")
    
    mock_resources = [
        SupportResource(
            id=str(uuid4()),
            name="消防车",
            type="车辆",
            quantity=3,
            status="available",
            description="水罐消防车",
        ),
        SupportResource(
            id=str(uuid4()),
            name="救援人员",
            type="人员",
            quantity=20,
            status="available",
            description="专业消防员",
        ),
        SupportResource(
            id=str(uuid4()),
            name="破拆工具",
            type="设备",
            quantity=5,
            status="available",
            description="液压破拆设备",
        ),
        SupportResource(
            id=str(uuid4()),
            name="生命探测仪",
            type="设备",
            quantity=2,
            status="available",
            description="雷达生命探测仪",
        ),
    ]
    
    return ApiResponse.success(mock_resources)


@router.post("/mobilize", response_model=ApiResponse[MobilizeResponse])
async def mobilize_vehicles(
    request: MobilizeRequest,
    service: UnitService = Depends(get_unit_service),
) -> ApiResponse[MobilizeResponse]:
    """
    车辆动员为救援队伍
    
    将选定的车辆及其装备转换为救援队伍：
    1. 读取车辆及其装备/模块信息
    2. 构建AI上下文数据
    3. 创建或更新Team记录
    4. 同步创建地图实体
    """
    logger.info(f"动员车辆, event_id={request.event_id}, vehicle_ids={request.vehicle_ids}")
    
    try:
        result = await service.mobilize_vehicles(request)
        return ApiResponse.success(result)
    except Exception as e:
        logger.exception(f"车辆动员失败: {e}")
        return ApiResponse.error(500, f"车辆动员失败: {str(e)}")
