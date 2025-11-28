"""
前端车辆装备API路由

接口路径: /car/* 和 /item/*
对接v2 VehicleService/DeviceService真实数据
集成AI装备推荐智能体结果
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.stomp.broker import stomp_broker
from src.domains.resources.vehicles.service import VehicleService
from src.domains.resources.devices.service import DeviceService
from src.domains.equipment_recommendation.repository import EquipmentRecommendationRepository
from src.domains.frontend_api.common import ApiResponse
from .repository import PreparationDispatchRepository, ModuleRepository
from .schemas import (
    CarListData, CarItem, ItemData, ModuleData, ShortageAlertData,
    ItemDetailResponse, ItemProperty,
    CarItemSelect, EventIdForm,
    EquipmentDispatchRequest, UserPreparingRequest, CarReadyRequest,
    DispatchStatusItem, DispatchStatusResponse,
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
    # 根据全局状态映射车辆状态，以便联调测试
    current_status = _car_data.get("carQuestStatus", "pending")
    item_status = "available"
    if current_status == "dispatched":
        item_status = "preparing"
    elif current_status in ["ready", "departed"]:
        item_status = "ready"
        
    cars = [
        CarItem(
            id="car-001",
            name="指挥车-01",
            status=item_status,
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
            status=item_status,
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
        carQuestStatus=current_status
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
    获取车辆和装备载荷列表（三级结构：车辆→设备→模块）
    
    - 对接v2真实数据
    - 若传入eventId，集成AI装备推荐结果
    - AI推荐的车辆/设备/模块自动标记为选中
    """
    logger.info(f"获取车辆列表, userId={userId}, eventId={eventId}")
    
    # 获取AI推荐（如果有eventId）
    ai_recommendation: Optional[Dict[str, Any]] = None
    loading_plan: Dict[str, Any] = {}
    if eventId:
        try:
            rec_repo = EquipmentRecommendationRepository(db)
            ai_recommendation = await rec_repo.get_by_event_id(UUID(eventId))
            if ai_recommendation:
                loading_plan = ai_recommendation.get("loading_plan") or {}
                logger.info(
                    f"获取到AI推荐: status={ai_recommendation.get('status')}, "
                    f"devices={len(ai_recommendation.get('recommended_devices', []))}, "
                    f"vehicles_in_plan={len(loading_plan)}"
                )
        except Exception as e:
            logger.warning(f"获取AI推荐失败: {e}")
    
    # 构建推荐设备映射 {device_id -> {reason, priority, modules}}
    rec_device_map = _build_recommended_device_map(ai_recommendation)
    
    # 构建loading_plan中的车辆-设备分配映射
    vehicle_device_map: Dict[str, set] = {}
    for vid, plan in loading_plan.items():
        vehicle_device_map[vid] = set(plan.get("devices", []))
    
    try:
        # 获取所有车辆
        vehicle_result = await vehicle_service.list(page=1, page_size=100)
        
        # 获取所有可用设备
        all_devices_result = await device_service.list(page=1, page_size=200)
        all_devices = all_devices_result.items
        
        # 获取所有模块
        module_repo = ModuleRepository(db)
        all_modules = await module_repo.list_all(limit=200)
        
        # 按设备类型分组模块
        modules_by_device_type: Dict[str, List[Dict]] = {}
        for mod in all_modules:
            for dtype in mod.get("compatible_device_types", []):
                if dtype not in modules_by_device_type:
                    modules_by_device_type[dtype] = []
                modules_by_device_type[dtype].append(mod)
        
        def build_item_list(
            devices, 
            assigned_device_ids: set,
            vehicle_id: str,
        ) -> List[ItemData]:
            """构建设备列表（含模块）"""
            items = []
            for device in devices:
                device_id_str = str(device.id)
                
                # 判断设备是否被AI分配到该车辆
                is_assigned = device_id_str in assigned_device_ids
                
                # 获取设备的AI推荐信息（含推荐模块）
                rec_info = rec_device_map.get(device_id_str)
                ai_module_ids = set()
                ai_module_reasons: Dict[str, str] = {}
                if rec_info:
                    for m in rec_info.get("modules", []):
                        mid = m.get("module_id", "")
                        ai_module_ids.add(mid)
                        ai_module_reasons[mid] = m.get("reason", "")
                
                # 获取该设备可适配的模块
                device_type = device.device_type.value if device.device_type else ""
                compatible_modules = modules_by_device_type.get(device_type, [])
                
                # 构建模块列表
                module_list = []
                has_modules = device.module_slots and device.module_slots > 0 and compatible_modules
                
                if has_modules:
                    for mod in compatible_modules:
                        mod_id = mod["id"]
                        module_list.append(ModuleData(
                            id=mod_id,
                            name=mod["name"],
                            moduleType=mod.get("module_type", ""),
                            isSelected=1 if mod_id in ai_module_ids else 0,
                            aiReason=ai_module_reasons.get(mod_id),
                        ))
                
                items.append(ItemData(
                    id=device_id_str,
                    name=device.name,
                    model=device.properties.get('model', device.code),
                    type="device",
                    isSelected=1 if is_assigned else 0,
                    aiReason=rec_info["reason"] if rec_info else None,
                    priority=rec_info["priority"] if rec_info else None,
                    hasModules=bool(has_modules),
                    modules=module_list,
                ))
            return items
        
        status_map = {
            'available': 'available',
            'deployed': 'ready',
            'maintenance': 'preparing',
        }
        
        cars = []
        for vehicle in vehicle_result.items:
            vehicle_id_str = str(vehicle.id)
            
            # 判断车辆是否在AI装载方案中
            is_vehicle_selected = vehicle_id_str in vehicle_device_map
            assigned_devices = vehicle_device_map.get(vehicle_id_str, set())
            
            cars.append(CarItem(
                id=vehicle_id_str,
                name=vehicle.name,
                status=status_map.get(vehicle.status.value, 'available'),
                isSelected=is_vehicle_selected,
                isBelongsToThisCar=0,
                itemDataList=build_item_list(all_devices, assigned_devices, vehicle_id_str),
            ))
        
        # 如果没有车辆数据，创建一个虚拟车辆来展示设备
        if not cars and all_devices:
            cars.append(CarItem(
                id="default-vehicle",
                name="装备仓库",
                status="available",
                isSelected=False,
                isBelongsToThisCar=0,
                itemDataList=build_item_list(all_devices, set(), "default-vehicle"),
            ))
        
        return ApiResponse.success(CarListData(
            carItemDataList=cars,
            carQuestStatus=_car_data["carQuestStatus"],
            recommendationId=str(ai_recommendation["id"]) if ai_recommendation else None,
            recommendationStatus=ai_recommendation.get("status") if ai_recommendation else None,
            shortageAlerts=_build_shortage_alerts(ai_recommendation),
        ))
        
    except Exception as e:
        logger.exception(f"获取车辆列表失败: {e}")
        raise e


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
                {"key": "型号", "value": device.model or device.properties.get('model', '-')},
                {"key": "类型", "value": device.device_type.value if device.device_type else '-'},
                {"key": "状态", "value": device.status.value if device.status else '-'},
            ]
            
            if device.weight_kg:
                properties.append({"key": "重量", "value": f"{device.weight_kg}kg"})
            if device.manufacturer:
                properties.append({"key": "厂商", "value": device.manufacturer})
            
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


@router.get("/item/module-detail", response_model=ApiResponse[ItemDetailResponse])
async def get_module_detail(
    moduleId: str = Query(..., description="模块ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ItemDetailResponse]:
    """
    获取模块详情
    """
    logger.info(f"获取模块详情, moduleId={moduleId}")
    
    try:
        module_repo = ModuleRepository(db)
        module = await module_repo.get_by_id(UUID(moduleId))
        
        if not module:
            return ApiResponse.error(404, f"模块不存在: {moduleId}")
        
        properties = [
            {"key": "编号", "value": module.get("code", "-")},
            {"key": "名称", "value": module.get("name", "-")},
            {"key": "类型", "value": module.get("module_type", "-")},
            {"key": "重量", "value": f"{module.get('weight_kg', 0)}kg"},
            {"key": "槽位需求", "value": str(module.get("slots_required", 1))},
            {"key": "提供能力", "value": module.get("provides_capability", "-")},
        ]
        
        # 添加适用设备类型
        compatible_types = module.get("compatible_device_types", [])
        if compatible_types:
            properties.append({"key": "适用设备", "value": ", ".join(compatible_types)})
        
        # 添加适用灾害
        disasters = module.get("applicable_disasters", [])
        if disasters:
            properties.append({"key": "适用灾害", "value": ", ".join(disasters)})
        
        detail = {
            "image": "",
            "properties": properties,
        }
        
        return ApiResponse.success(ItemDetailResponse(itemDetail=json.dumps(detail)))
        
    except ValueError:
        return ApiResponse.error(400, f"无效的模块ID格式: {moduleId}")
    except Exception as e:
        logger.exception(f"获取模块详情失败: {e}")
        return ApiResponse.error(500, f"获取模块详情失败: {str(e)}")


@router.post("/car/car-item-confirm", response_model=ApiResponse)
async def car_equipment_check(
    request: EquipmentDispatchRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    指挥员装备清单指令下发
    
    1. 持久化各车辆的装备分配到数据库
    2. 通过WebSocket通知各车辆人员
    3. 更新全局状态
    """
    logger.info(f"装备清单下发, eventId={request.eventId}, 车辆数={len(request.assignments)}")
    
    try:
        event_id = UUID(request.eventId)
        dispatch_repo = PreparationDispatchRepository(db)
        
        # 获取AI推荐ID（如果存在）
        rec_repo = EquipmentRecommendationRepository(db)
        ai_rec = await rec_repo.get_by_event_id(event_id)
        recommendation_id = ai_rec["id"] if ai_rec else None
        
        # 为每辆车创建调度记录
        for assignment in request.assignments:
            vehicle_id = UUID(assignment.carId)
            
            # 转换物资格式
            supplies = [
                {
                    "supply_id": s.supplyId,
                    "quantity": s.quantity,
                    "supply_name": s.supplyName,
                }
                for s in assignment.supplies
            ]
            
            await dispatch_repo.create_dispatch(
                event_id=event_id,
                vehicle_id=vehicle_id,
                device_ids=assignment.deviceIds,
                supplies=supplies,
                recommendation_id=recommendation_id,
                dispatched_by=None,  # TODO: 从认证获取当前用户
            )
            
            # 获取车辆关联用户并发送通知
            vehicle_users = await dispatch_repo.get_vehicle_users(vehicle_id)
            for user in vehicle_users:
                try:
                    await stomp_broker.send_to_user(
                        user["user_id"],
                        "/equipment/dispatch",
                        {
                            "type": "equipment_dispatch",
                            "eventId": request.eventId,
                            "carId": assignment.carId,
                            "devices": assignment.deviceIds,
                            "supplies": [s.model_dump() for s in assignment.supplies],
                        }
                    )
                    logger.info(f"已通知用户 {user['real_name']} 装备清单")
                except Exception as e:
                    logger.warning(f"通知用户失败: {e}")
        
        _car_data["carQuestStatus"] = "dispatched"
        
        return ApiResponse.success(None, f"装备清单已下发给 {len(request.assignments)} 辆车")
        
    except Exception as e:
        logger.exception(f"装备清单下发失败: {e}")
        return ApiResponse.error(500, f"下发失败: {str(e)}")


@router.post("/car/car-ready", response_model=ApiResponse)
async def equipment_ready(
    request: CarReadyRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    车辆装备准备完成
    
    1. 更新该车辆状态为ready
    2. 检查是否所有车辆都准备完成
    3. 通知指挥员进度
    """
    logger.info(f"车辆准备完成, eventId={request.eventId}, carId={request.carId}")
    
    try:
        event_id = UUID(request.eventId)
        vehicle_id = UUID(request.carId)
        user_id = UUID(request.userId) if request.userId else None
        
        dispatch_repo = PreparationDispatchRepository(db)
        
        # 更新状态
        updated = await dispatch_repo.update_status(
            event_id=event_id,
            vehicle_id=vehicle_id,
            status="ready",
            user_id=user_id,
        )
        
        if not updated:
            return ApiResponse.error(404, "未找到调度记录")
        
        # 检查是否全部完成
        summary = await dispatch_repo.get_dispatch_summary(event_id)
        all_ready = await dispatch_repo.check_all_ready(event_id)
        
        if all_ready:
            _car_data["carQuestStatus"] = "ready"
            # 广播所有车辆已准备完成
            await stomp_broker.broadcast_event(
                "equipment_all_ready",
                {
                    "eventId": request.eventId,
                    "message": "所有车辆装备准备完成，可以出发",
                },
                scenario_id=None,
            )
        
        return ApiResponse.success({
            "totalVehicles": summary["total"],
            "readyCount": summary["ready_count"],
            "allReady": all_ready,
        }, "准备完成")
        
    except Exception as e:
        logger.exception(f"更新准备状态失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.post("/car/car-user-preparing", response_model=ApiResponse)
async def equipment_user_preparing(
    request: UserPreparingRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    车辆人员确认收到装备清单
    
    1. 更新状态为confirmed
    2. 通知指挥员
    """
    logger.info(f"用户确认收到, eventId={request.eventId}, carId={request.carId}, userId={request.userId}")
    
    try:
        event_id = UUID(request.eventId)
        vehicle_id = UUID(request.carId)
        user_id = UUID(request.userId) if request.userId else None
        
        dispatch_repo = PreparationDispatchRepository(db)
        
        # 更新状态为confirmed
        updated = await dispatch_repo.update_status(
            event_id=event_id,
            vehicle_id=vehicle_id,
            status="confirmed",
            user_id=user_id,
        )
        
        if not updated:
            return ApiResponse.error(404, "未找到调度记录")
        
        # 获取进度并通知指挥员
        summary = await dispatch_repo.get_dispatch_summary(event_id)
        
        await stomp_broker.broadcast_event(
            "equipment_progress",
            {
                "eventId": request.eventId,
                "carId": request.carId,
                "userId": request.userId,
                "status": "confirmed",
                "confirmedCount": summary["confirmed_count"],
                "totalVehicles": summary["total"],
            },
            scenario_id=None,
        )
        
        return ApiResponse.success({
            "confirmedCount": summary["confirmed_count"],
            "totalVehicles": summary["total"],
        }, "已确认收到")
        
    except Exception as e:
        logger.exception(f"确认失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.post("/car/car-depart", response_model=ApiResponse)
async def car_start(
    request: EventIdForm,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """
    指挥员指挥车队出发
    
    1. 检查所有车辆是否准备完成
    2. 广播出发消息
    3. 更新状态
    """
    logger.info(f"车队出发, eventId={request.eventId}")
    
    try:
        event_id = UUID(request.eventId)
        dispatch_repo = PreparationDispatchRepository(db)
        
        # 检查是否所有车辆都准备完成
        all_ready = await dispatch_repo.check_all_ready(event_id)
        if not all_ready:
            summary = await dispatch_repo.get_dispatch_summary(event_id)
            return ApiResponse.error(
                400, 
                f"还有 {summary['total'] - summary['ready_count']} 辆车未准备完成"
            )
        
        _car_data["carQuestStatus"] = "departed"
        
        # 广播出发消息
        await stomp_broker.broadcast_event(
            "equipment_departed",
            {
                "eventId": request.eventId,
                "message": "车队已出发",
                "departedAt": datetime.now().isoformat(),
            },
            scenario_id=None,
        )
        
        return ApiResponse.success(None, "车队已出发")
        
    except Exception as e:
        logger.exception(f"出发指令失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.get("/car/dispatch-status", response_model=ApiResponse[DispatchStatusResponse])
async def get_dispatch_status(
    eventId: str = Query(..., description="事件ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[DispatchStatusResponse]:
    """
    获取装备准备调度状态
    """
    try:
        event_id = UUID(eventId)
        dispatch_repo = PreparationDispatchRepository(db)
        
        dispatches = await dispatch_repo.get_by_event(event_id)
        summary = await dispatch_repo.get_dispatch_summary(event_id)
        
        items = [
            DispatchStatusItem(
                vehicleId=str(d["vehicle_id"]),
                vehicleName=d.get("vehicle_name", ""),
                status=d["status"],
                assigneeUserId=str(d["assignee_user_id"]) if d.get("assignee_user_id") else None,
                assigneeName=d.get("assignee_name"),
                dispatchedAt=d["dispatched_at"].isoformat() if d.get("dispatched_at") else None,
                confirmedAt=d["confirmed_at"].isoformat() if d.get("confirmed_at") else None,
                readyAt=d["ready_at"].isoformat() if d.get("ready_at") else None,
            )
            for d in dispatches
        ]
        
        return ApiResponse.success(DispatchStatusResponse(
            eventId=eventId,
            totalVehicles=summary["total"],
            confirmedCount=summary["confirmed_count"],
            readyCount=summary["ready_count"],
            items=items,
        ))
        
    except Exception as e:
        logger.exception(f"获取调度状态失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")
