"""
前端车辆装备API路由

接口路径: /car/* 和 /item/*
对接v2 VehicleService/DeviceService真实数据
集成AI装备推荐智能体结果
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.resources.vehicles.service import VehicleService
from src.domains.resources.devices.service import DeviceService
from src.domains.equipment_recommendation.repository import EquipmentRecommendationRepository
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    CarListData, CarItem, ItemData, ShortageAlertData,
    ItemDetailResponse, ItemProperty,
    CarItemSelect, EventIdForm,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["前端-车辆装备"])


def get_vehicle_service(db: AsyncSession = Depends(get_db)) -> VehicleService:
    return VehicleService(db)


def get_device_service(db: AsyncSession = Depends(get_db)) -> DeviceService:
    return DeviceService(db)


# 状态存储（简化实现，生产环境应使用Redis或数据库）
_car_data = {
    "carQuestStatus": "pending",
}


def _get_mock_cars(user_id: str) -> CarListData:
    """获取模拟车辆数据（数据库表结构待迁移）"""
    cars = [
        CarItem(
            id="car-001",
            name="指挥车-01",
            status="available",
            isSelected=False,
            isBelongsToThisCar=1 if user_id == "commander" else 0,
            itemDataList=[
                ItemData(id="dev-001", name="卫星通信设备", model="TS-200", type="device", isSelected=1),
                ItemData(id="dev-002", name="无人机控制站", model="DJI-M300", type="device", isSelected=1),
            ]
        ),
        CarItem(
            id="car-002",
            name="侦察车-01",
            status="available",
            isSelected=False,
            isBelongsToThisCar=1 if user_id == "scout" else 0,
            itemDataList=[
                ItemData(id="dev-003", name="侦察无人机", model="大疆M30", type="device", isSelected=1),
                ItemData(id="dev-004", name="机器狗", model="宇树B2", type="device", isSelected=1),
            ]
        ),
    ]
    return CarListData(
        carItemDataList=cars,
        carQuestStatus=_car_data["carQuestStatus"]
    )


def _build_recommended_device_map(
    ai_recommendation: Optional[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """构建AI推荐设备映射表 {device_id -> {reason, priority, modules}}"""
    if not ai_recommendation:
        return {}
    
    device_map: Dict[str, Dict[str, Any]] = {}
    recommended_devices = ai_recommendation.get("recommended_devices", [])
    
    for rec in recommended_devices:
        device_id = rec.get("device_id", "")
        if device_id:
            device_map[device_id] = {
                "reason": rec.get("reason", ""),
                "priority": rec.get("priority", "medium"),
                "modules": rec.get("modules", []),
            }
    
    return device_map


def _build_shortage_alerts(
    ai_recommendation: Optional[Dict[str, Any]]
) -> Optional[List[ShortageAlertData]]:
    """构建缺口告警列表"""
    if not ai_recommendation:
        return None
    
    alerts = ai_recommendation.get("shortage_alerts", [])
    if not alerts:
        return None
    
    return [
        ShortageAlertData(
            itemType=a.get("item_type", ""),
            itemName=a.get("item_name", ""),
            required=a.get("required", 0),
            available=a.get("available", 0),
            shortage=a.get("shortage", 0),
            severity=a.get("severity", "warning"),
            suggestion=a.get("suggestion", ""),
        )
        for a in alerts
    ]


@router.get("/car/car-item-select-list", response_model=ApiResponse[CarListData])
async def get_car_list(
    userId: str = Query(..., description="用户ID"),
    eventId: Optional[str] = Query(None, description="事件ID，用于获取AI装备推荐"),
    db: AsyncSession = Depends(get_db),
    vehicle_service: VehicleService = Depends(get_vehicle_service),
    device_service: DeviceService = Depends(get_device_service),
) -> ApiResponse[CarListData]:
    """
    获取车辆和装备载荷列表
    
    - 对接v2真实数据
    - 若传入eventId，集成AI装备推荐结果，AI推荐的设备isSelected=1
    """
    logger.info(f"获取车辆列表, userId={userId}, eventId={eventId}")
    
    # 获取AI推荐（如果有eventId）
    ai_recommendation: Optional[Dict[str, Any]] = None
    if eventId:
        try:
            rec_repo = EquipmentRecommendationRepository(db)
            ai_recommendation = await rec_repo.get_by_event_id(UUID(eventId))
            if ai_recommendation:
                logger.info(
                    f"获取到AI推荐: status={ai_recommendation.get('status')}, "
                    f"devices={len(ai_recommendation.get('recommended_devices', []))}"
                )
        except Exception as e:
            logger.warning(f"获取AI推荐失败: {e}")
    
    # 构建推荐设备映射
    rec_device_map = _build_recommended_device_map(ai_recommendation)
    
    try:
        # 尝试获取真实车辆数据
        vehicle_result = await vehicle_service.list(page=1, page_size=100)
        
        cars = []
        for vehicle in vehicle_result.items:
            # 获取车辆上的设备
            device_result = await device_service.list(
                page=1, page_size=50, 
                in_vehicle_id=vehicle.id
            )
            
            item_list = []
            for device in device_result.items:
                device_id_str = str(device.id)
                rec_info = rec_device_map.get(device_id_str)
                
                item_list.append(ItemData(
                    id=device_id_str,
                    name=device.name,
                    model=device.properties.get('model', device.code),
                    type="device",
                    isSelected=1 if rec_info else 0,
                    aiReason=rec_info["reason"] if rec_info else None,
                    priority=rec_info["priority"] if rec_info else None,
                ))
            
            status_map = {
                'available': 'available',
                'deployed': 'ready',
                'maintenance': 'preparing',
            }
            
            cars.append(CarItem(
                id=str(vehicle.id),
                name=vehicle.name,
                status=status_map.get(vehicle.status.value, 'available'),
                isSelected=False,
                isBelongsToThisCar=0,
                itemDataList=item_list,
            ))
        
        return ApiResponse.success(CarListData(
            carItemDataList=cars,
            carQuestStatus=_car_data["carQuestStatus"],
            recommendationId=str(ai_recommendation["id"]) if ai_recommendation else None,
            recommendationStatus=ai_recommendation.get("status") if ai_recommendation else None,
            shortageAlerts=_build_shortage_alerts(ai_recommendation),
        ))
        
    except Exception as e:
        logger.warning(f"获取真实车辆数据失败，使用Mock数据: {e}")
        mock_data = _get_mock_cars(userId)
        mock_data.recommendationId = str(ai_recommendation["id"]) if ai_recommendation else None
        mock_data.recommendationStatus = ai_recommendation.get("status") if ai_recommendation else None
        mock_data.shortageAlerts = _build_shortage_alerts(ai_recommendation)
        return ApiResponse.success(mock_data)


@router.get("/item/get-item-detail", response_model=ApiResponse[ItemDetailResponse])
async def get_equipment_detail(
    itemId: str = Query(..., description="装备ID"),
    type: str = Query(..., description="类型: device/supply"),
    device_service: DeviceService = Depends(get_device_service),
) -> ApiResponse[ItemDetailResponse]:
    """
    获取装备或物资详情 - 对接v2真实数据
    """
    logger.info(f"获取装备详情, itemId={itemId}, type={type}")
    
    try:
        if type == "device":
            device_uuid = UUID(itemId)
            device = await device_service.get_by_id(device_uuid)
            
            properties = [
                {"key": "编号", "value": device.code},
                {"key": "型号", "value": device.properties.get('model', '-')},
                {"key": "类型", "value": device.device_type.value if device.device_type else '-'},
                {"key": "状态", "value": device.status.value if device.status else '-'},
            ]
            
            if device.battery_level is not None:
                properties.append({"key": "电量", "value": f"{device.battery_level}%"})
            if device.weight_kg:
                properties.append({"key": "重量", "value": f"{device.weight_kg}kg"})
            if device.max_speed_kmh:
                properties.append({"key": "最大速度", "value": f"{device.max_speed_kmh}km/h"})
            if device.max_flight_time_min:
                properties.append({"key": "续航", "value": f"{device.max_flight_time_min}分钟"})
            
            detail = {
                "image": device.properties.get('image', ''),
                "properties": properties,
            }
        else:
            # 物资详情（当前暂无v2物资服务，返回基础信息）
            detail = {
                "image": "",
                "properties": [{"key": "ID", "value": itemId}],
            }
        
        return ApiResponse.success(ItemDetailResponse(itemDetail=json.dumps(detail)))
        
    except ValueError:
        return ApiResponse.error(400, f"无效的ID格式: {itemId}")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            return ApiResponse.success(ItemDetailResponse(itemDetail=json.dumps({
                "image": "",
                "properties": [{"key": "ID", "value": itemId}],
            })))
        logger.exception(f"获取装备详情失败: {e}")
        return ApiResponse.error(500, f"获取装备详情失败: {str(e)}")


@router.post("/car/car-item-confirm", response_model=ApiResponse)
async def car_equipment_check(
    request: list[CarItemSelect],
) -> ApiResponse:
    """
    指挥员装备清单指令下发
    """
    logger.info(f"装备清单下发, 车辆数={len(request)}")
    
    _car_data["carQuestStatus"] = "dispatched"
    
    return ApiResponse.success(None, "装备清单下发成功")


@router.post("/car/car-ready", response_model=ApiResponse)
async def equipment_ready(
    request: list[CarItemSelect],
) -> ApiResponse:
    """
    装备清单准备完成
    """
    logger.info(f"装备准备完成, 车辆数={len(request)}")
    
    # 检查是否所有车辆都准备好了（简化逻辑）
    _car_data["carQuestStatus"] = "ready"
    
    return ApiResponse.success(None, "装备准备完成")


@router.post("/car/car-user-preparing", response_model=ApiResponse)
async def equipment_user_preparing(
    request: dict,
) -> ApiResponse:
    """
    收到装备清单通知确认
    """
    logger.info(f"收到装备清单确认, request={request}")
    
    return ApiResponse.success(None, "已确认收到")


@router.post("/car/car-depart", response_model=ApiResponse)
async def car_start(
    request: EventIdForm,
) -> ApiResponse:
    """
    指挥员指挥车辆出发
    """
    logger.info(f"车队出发, eventId={request.eventId}")
    
    _car_data["carQuestStatus"] = "departed"
    
    return ApiResponse.success(None, "车队已出发")
