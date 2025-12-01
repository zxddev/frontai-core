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
from src.domains.scenarios.repository import ScenarioRepository
from src.domains.frontend_api.common import ApiResponse
from .repository import PreparationDispatchRepository, ModuleRepository, CarItemAssignmentRepository, MyEquipmentRepository
from .schemas import (
    CarListData, CarItem, ItemData, ModuleData, ShortageAlertData,
    ItemDetailResponse, ItemProperty,
    CarItemSelect, EventIdForm,
    EquipmentDispatchRequest, UserPreparingRequest, CarReadyRequest,
    DispatchStatusItem, DispatchStatusResponse,
    CarItemAddRequest, CarItemAddResponse,
    CarItemRemoveRequest, CarItemRemoveResponse,
    CarItemToggleRequest, CarItemToggleResponse, ModuleToggleItem,
    CarModuleUpdateRequest, CarModuleUpdateResponse,
    MyEquipmentData, MyEquipmentDevice, MyEquipmentSupply, MyEquipmentModule,
    MyEquipmentToggleRequest, MyEquipmentToggleResponse,
)
logger = logging.getLogger(__name__)

router = APIRouter(tags=["前端-车辆装备"])


def get_vehicle_service(db: AsyncSession = Depends(get_db)) -> VehicleService:
    return VehicleService(db)


def get_device_service(db: AsyncSession = Depends(get_db)) -> DeviceService:
    return DeviceService(db)


async def _resolve_event_id(db: AsyncSession, event_id: Optional[str] = None) -> Optional[UUID]:
    """
    解析事件ID：
    1. 如果前端传了 eventId，使用前端的
    2. 如果没传，自动获取活动想定的主事件ID
    """
    if event_id:
        return UUID(event_id)
    
    scenario_repo = ScenarioRepository(db)
    main_event_id = await scenario_repo.get_active_main_event_id()
    return main_event_id


async def _get_quest_status(db: AsyncSession, event_id: Optional[UUID] = None) -> str:
    """
    获取任务状态：
    1. 如果有事件ID，从数据库查询状态
    2. 如果没有事件ID，返回pending
    """
    if not event_id:
        return "pending"
    
    dispatch_repo = PreparationDispatchRepository(db)
    return await dispatch_repo.get_quest_status(event_id)


def _get_mock_cars(user_id: str, quest_status: str = "pending") -> CarListData:
    """获取模拟车辆数据（数据库表结构待迁移）"""
    # 根据任务状态映射车辆状态，以便联调测试
    item_status = "available"
    if quest_status == "dispatched":
        item_status = "preparing"
    elif quest_status in ["ready", "departed"]:
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
        carQuestStatus=quest_status
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
    db: AsyncSession = Depends(get_db),
    vehicle_service: VehicleService = Depends(get_vehicle_service),
    device_service: DeviceService = Depends(get_device_service),
) -> ApiResponse[CarListData]:
    """
    获取车辆和装备载荷列表（三级结构：车辆→设备→模块）
    
    - 对接v2真实数据
    - 自动集成最近一次就绪(ready)的AI装备推荐结果
    - AI推荐的车辆/设备/模块自动标记为选中
    """
    logger.info(f"获取车辆列表, userId={userId}")
    
    # 获取活动想定的主事件ID和任务状态
    main_event_id = await _resolve_event_id(db)
    logger.info(f"解析到 main_event_id={main_event_id}")
    quest_status = await _get_quest_status(db, main_event_id)
    
    # 获取最近一次就绪(ready)的AI推荐（无需前端传eventId）
    ai_recommendation: Optional[Dict[str, Any]] = None
    loading_plan: Dict[str, Any] = {}
    try:
        rec_repo = EquipmentRecommendationRepository(db)
        ready_list = await rec_repo.list_by_status("ready", limit=1)
        if ready_list:
            ai_recommendation = ready_list[0]
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
    
    # 获取指挥员手动分配数据（优先级高于AI推荐）
    user_assignment_map: Dict[tuple, bool] = {}
    if main_event_id:
        try:
            assignment_repo = CarItemAssignmentRepository(db)
            user_assignments = await assignment_repo.get_all_by_event(main_event_id)
            user_assignment_map = {
                (a['car_id'], a['item_id']): a['is_selected']
                for a in user_assignments
            }
            if user_assignment_map:
                logger.info(f"获取到用户分配数据: {len(user_assignment_map)} 条")
        except Exception as e:
            logger.warning(f"获取用户分配数据失败: {e}")
    
    # 仅保留车辆ID为有效UUID的装载方案（兼容旧数据）
    if loading_plan:
        normalized_loading_plan: Dict[str, Any] = {}
        for vid, plan in loading_plan.items():
            try:
                UUID(vid)
            except Exception:
                logger.warning("忽略loading_plan中的非UUID车辆ID: %s", vid)
                continue
            normalized_loading_plan[vid] = plan
        loading_plan = normalized_loading_plan
    
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
        
        # 构建车辆ID→名称映射（用于专属车辆名称查找）
        vehicle_id_to_name: Dict[str, str] = {
            str(v.id): v.name for v in vehicle_result.items
        }

        # 构建设备→分配车辆的映射 {device_id -> (vehicle_id, vehicle_name)}，直接使用loading_plan中的真实车辆ID
        device_to_vehicle_map: Dict[str, tuple] = {}
        vehicle_device_map: Dict[str, set] = {}
        for vid, plan in (loading_plan or {}).items():
            vname = plan.get("vehicle_name", vehicle_id_to_name.get(vid, ""))
            devices_in_plan = plan.get("devices", []) or []
            if not devices_in_plan:
                continue
            vehicle_device_map.setdefault(vid, set()).update(devices_in_plan)
            for dev_id in devices_in_plan:
                device_to_vehicle_map[dev_id] = (vid, vname)
        
        def build_item_list(
            devices, 
            current_vehicle_id: str,
            user_assignment_map: Dict[tuple, bool],
        ) -> List[ItemData]:
            """构建设备列表（含模块），用户分配优先于AI推荐"""
            items = []
            for device in devices:
                device_id_str = str(device.id)
                
                # 获取设备的AI推荐信息（含推荐模块）
                rec_info = rec_device_map.get(device_id_str)
                ai_module_ids = set()
                ai_module_reasons: Dict[str, str] = {}
                if rec_info:
                    for m in rec_info.get("modules", []):
                        mid = m.get("module_id", "")
                        ai_module_ids.add(mid)
                        ai_module_reasons[mid] = m.get("reason", "")
                
                # 获取该设备可适配的模块（双向匹配）
                # 1. 设备类型匹配模块的compatible_device_types
                # 2. 模块类型匹配设备的compatible_module_types
                device_type = device.device_type.value if device.device_type else ""
                device_compatible_module_types = device.compatible_module_types or []
                
                # 从按设备类型分组的模块中筛选
                candidate_modules = modules_by_device_type.get(device_type, [])
                # 再过滤：模块类型必须在设备允许的模块类型中
                compatible_modules = [
                    m for m in candidate_modules 
                    if m.get("module_type") in device_compatible_module_types
                ]
                
                # 构建模块列表（含专有模块过滤）
                module_list = []
                has_modules = device.module_slots and device.module_slots > 0 and compatible_modules
                
                if has_modules:
                    for mod in compatible_modules:
                        mod_id = mod["id"]
                        exclusive_device_id = mod.get("exclusive_to_device_id")
                        
                        # 如果是专有模块且不属于当前设备，跳过
                        if exclusive_device_id and exclusive_device_id != device_id_str:
                            continue
                        
                        # 模块 isSelected：用户分配 > AI推荐
                        module_user_selected = user_assignment_map.get((current_vehicle_id, mod_id))
                        if module_user_selected is not None:
                            module_is_selected = 1 if module_user_selected else 0
                        else:
                            module_is_selected = 1 if mod_id in ai_module_ids else 0
                        
                        module_list.append(ModuleData(
                            id=mod_id,
                            name=mod["name"],
                            moduleType=mod.get("module_type", ""),
                            isSelected=module_is_selected,
                            aiReason=ai_module_reasons.get(mod_id),
                            exclusiveToDeviceId=exclusive_device_id,
                        ))
                
                # 获取设备的专属车辆信息
                exclusive_vehicle_id = str(device.exclusive_to_vehicle_id) if device.exclusive_to_vehicle_id else None
                exclusive_vehicle_name = vehicle_id_to_name.get(exclusive_vehicle_id) if exclusive_vehicle_id else None
                
                # 查找该设备被AI分配到哪辆车（如果有装载方案）
                assigned_vehicle = device_to_vehicle_map.get(device_id_str)
                assigned_to_vid = assigned_vehicle[0] if assigned_vehicle else None
                assigned_to_vname = assigned_vehicle[1] if assigned_vehicle else None

                # 设备 isSelected：用户分配 > 专属装备 > AI推荐
                user_selected = user_assignment_map.get((current_vehicle_id, device_id_str))
                if user_selected is not None:
                    # 指挥员已手动设置，以指挥员选择为准
                    is_selected_flag = 1 if user_selected else 0
                elif exclusive_vehicle_id == current_vehicle_id:
                    # 专属装备在其专属车辆上默认选中
                    is_selected_flag = 1
                else:
                    # 无用户操作，使用AI推荐作为初始值
                    is_assigned_to_current = assigned_to_vid == current_vehicle_id
                    is_ai_recommended = rec_info is not None
                    is_selected_flag = 1 if (is_assigned_to_current or (not loading_plan and is_ai_recommended)) else 0

                props = device.properties or {}
                items.append(ItemData(
                    id=device_id_str,
                    name=device.name,
                    model=device.model or props.get('model', device.code),
                    type="device",
                    isSelected=is_selected_flag,
                    aiReason=rec_info["reason"] if rec_info else None,
                    priority=rec_info["priority"] if rec_info else None,
                    assignedToVehicle=assigned_to_vid,
                    assignedToVehicleName=assigned_to_vname,
                    exclusiveToVehicleId=exclusive_vehicle_id,
                    exclusiveToVehicleName=exclusive_vehicle_name,
                    hasModules=bool(has_modules),
                    modules=module_list,
                    image=props.get('image'),
                    description=props.get('description'),
                    manufacturer=device.manufacturer,
                    specifications=props.get('specifications'),
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
            
            cars.append(CarItem(
                id=vehicle_id_str,
                code=vehicle.code,
                name=vehicle.name,
                status=status_map.get(vehicle.status.value, 'available'),
                isSelected=is_vehicle_selected,
                isBelongsToThisCar=0,
                itemDataList=build_item_list(all_devices, vehicle_id_str, user_assignment_map),
            ))
        
        # 如果没有车辆数据，创建一个虚拟车辆来展示设备
        if not cars and all_devices:
            cars.append(CarItem(
                id="default-vehicle",
                name="装备仓库",
                status="available",
                isSelected=False,
                isBelongsToThisCar=0,
                itemDataList=build_item_list(all_devices, "default-vehicle", user_assignment_map),
            ))
        
        return ApiResponse.success(CarListData(
            carItemDataList=cars,
            carQuestStatus=quest_status,
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
        
        # 状态现在从数据库dispatch记录推断，无需设置内存变量
        
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
            # 状态现在从数据库dispatch记录推断，无需设置内存变量
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
    2. 将车辆动员为救援队伍（转换数据结构）
    3. 广播出发消息
    4. 更新状态
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
        
        # 获取所有已调度的车辆ID
        dispatches = await dispatch_repo.get_by_event(event_id)
        vehicle_ids = [str(d["vehicle_id"]) for d in dispatches]
        
        # 将车辆动员为救援队伍
        if vehicle_ids:
            from src.domains.frontend_api.unit.service import UnitService
            from src.domains.frontend_api.unit.schemas import MobilizeRequest
            
            unit_service = UnitService(db)
            mobilize_request = MobilizeRequest(
                event_id=request.eventId,
                vehicle_ids=vehicle_ids,
            )
            mobilize_result = await unit_service.mobilize_vehicles(mobilize_request)
            logger.info(
                f"车辆动员完成: {mobilize_result.mobilized_count} 辆车转换为救援队伍"
            )
        
        # 标记已出发到数据库
        await dispatch_repo.mark_departed(event_id)
        
        # 广播出发消息
        await stomp_broker.broadcast_event(
            "equipment_departed",
            {
                "eventId": request.eventId,
                "message": "车队已出发",
                "departedAt": datetime.now().isoformat(),
                "mobilizedTeams": mobilize_result.mobilized_count if vehicle_ids else 0,
            },
            scenario_id=None,
        )
        
        return ApiResponse.success({
            "mobilizedTeams": mobilize_result.mobilized_count if vehicle_ids else 0,
            "teams": [t.model_dump() for t in mobilize_result.teams] if vehicle_ids else [],
        }, "车队已出发，已转换为救援队伍")
        
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


# ==================== 装备实时分配接口 ====================

@router.post("/car/car-item-add", response_model=ApiResponse[CarItemAddResponse])
async def add_item_to_car(
    request: CarItemAddRequest,
    db: AsyncSession = Depends(get_db),
    device_service: DeviceService = Depends(get_device_service),
) -> ApiResponse[CarItemAddResponse]:
    """
    添加装备到车辆
    
    业务逻辑:
    1. 验证任务状态（pending/preparing 可修改）
    2. 检查装备是否已被其他车辆占用
    3. 创建分配记录
    """
    logger.info(f"添加装备到车辆, carId={request.carId}, itemId={request.itemId}")
    
    try:
        # 统一使用活动想定的主事件ID
        event_id = await _resolve_event_id(db)
        if not event_id:
            return ApiResponse.error(40001, "没有活动想定或主事件")
        
        # 状态校验
        current_status = await _get_quest_status(db, event_id)
        if current_status in ["ready", "departed"]:
            return ApiResponse.error(40002, "当前状态不允许修改装备")
        car_id = UUID(request.carId)
        item_id = UUID(request.itemId)
        
        assignment_repo = CarItemAssignmentRepository(db)
        
        # 检查是否为专属装备
        is_exclusive = False
        if request.itemType == "device":
            try:
                device = await device_service.get_by_id(item_id)
                if device.exclusive_to_vehicle_id:
                    if str(device.exclusive_to_vehicle_id) != request.carId:
                        return ApiResponse.error(40003, "该装备为其他车辆的专属装备")
                    is_exclusive = True
            except Exception:
                pass  # 设备不存在时继续
        
        # 检查是否已被其他车辆占用（非专属装备）
        if not is_exclusive:
            occupied_car = await assignment_repo.check_item_assigned(
                event_id, item_id, exclude_car_id=car_id
            )
            if occupied_car:
                return ApiResponse.error(40003, f"装备已被其他车辆占用")
        
        # 创建分配记录
        parent_device_id = UUID(request.parentDeviceId) if request.parentDeviceId else None
        result = await assignment_repo.add_item(
            event_id=event_id,
            car_id=car_id,
            item_id=item_id,
            item_type=request.itemType,
            quantity=request.quantity,
            parent_device_id=parent_device_id,
            is_exclusive=is_exclusive,
            assigned_by=None,  # TODO: 从认证获取
        )
        
        return ApiResponse.success(CarItemAddResponse(
            carId=request.carId,
            itemId=request.itemId,
            assignedAt=result["assigned_at"].isoformat(),
        ), "添加成功")
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"添加装备失败: {e}")
        return ApiResponse.error(500, f"添加失败: {str(e)}")


@router.post("/car/car-item-remove", response_model=ApiResponse[CarItemRemoveResponse])
async def remove_item_from_car(
    request: CarItemRemoveRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CarItemRemoveResponse]:
    """
    从车辆移除装备
    
    业务逻辑:
    1. 验证任务状态
    2. 删除分配记录
    """
    logger.info(f"移除装备, carId={request.carId}, itemId={request.itemId}")
    
    try:
        # 统一使用活动想定的主事件ID
        event_id = await _resolve_event_id(db)
        if not event_id:
            return ApiResponse.error(40001, "没有活动想定或主事件")
        
        # 状态校验
        current_status = await _get_quest_status(db, event_id)
        if current_status in ["ready", "departed"]:
            return ApiResponse.error(40002, "当前状态不允许修改装备")
        
        car_id = UUID(request.carId)
        item_id = UUID(request.itemId)
        
        assignment_repo = CarItemAssignmentRepository(db)
        
        # 标记装备为未选中（覆盖AI推荐的默认选中状态）
        await assignment_repo.mark_deselected(event_id, car_id, item_id)
        
        return ApiResponse.success(CarItemRemoveResponse(
            carId=request.carId,
            itemId=request.itemId,
            returnedToWarehouse=True,
        ), "移除成功")
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"移除装备失败: {e}")
        return ApiResponse.error(500, f"移除失败: {str(e)}")


@router.post("/car/car-item-toggle", response_model=ApiResponse[CarItemToggleResponse])
async def toggle_car_item(
    request: CarItemToggleRequest,
    db: AsyncSession = Depends(get_db),
    device_service: DeviceService = Depends(get_device_service),
) -> ApiResponse[CarItemToggleResponse]:
    """
    切换专属装备选中状态
    
    业务逻辑:
    1. 验证任务状态
    2. 验证装备是否为该车辆的专属装备
    3. 更新选中状态
    4. 同步更新关联模块状态
    """
    logger.info(f"切换装备选中, carId={request.carId}, itemId={request.itemId}, isSelected={request.isSelected}")
    
    try:
        # 统一使用活动想定的主事件ID
        event_id = await _resolve_event_id(db)
        if not event_id:
            return ApiResponse.error(40001, "没有活动想定或主事件")
        
        # 状态校验
        current_status = await _get_quest_status(db, event_id)
        if current_status in ["ready", "departed"]:
            return ApiResponse.error(40002, "当前状态不允许修改装备")
        
        car_id = UUID(request.carId)
        item_id = UUID(request.itemId)
        
        # 验证专属装备
        try:
            device = await device_service.get_by_id(item_id)
            if not device.exclusive_to_vehicle_id:
                return ApiResponse.error(400, "该装备非专属装备，请使用add/remove接口")
            if str(device.exclusive_to_vehicle_id) != request.carId:
                return ApiResponse.error(40001, "无权限操作此装备")
        except Exception:
            return ApiResponse.error(40006, "装备不存在")
        
        assignment_repo = CarItemAssignmentRepository(db)
        
        # 确保专属装备存在分配记录
        await assignment_repo.ensure_exclusive_item(event_id, car_id, item_id)
        
        # 更新选中状态
        await assignment_repo.toggle_item(event_id, car_id, item_id, request.isSelected)
        
        # 获取并同步更新模块状态
        modules_result: List[ModuleToggleItem] = []
        assignments = await assignment_repo.get_by_event_car(event_id, car_id)
        for a in assignments:
            if a["parent_device_id"] == str(item_id) and a["item_type"] == "module":
                # 设备取消选中时，其模块也取消
                new_selected = request.isSelected and a["is_selected"]
                if not request.isSelected:
                    await assignment_repo.toggle_item(
                        event_id, car_id, UUID(a["item_id"]), False
                    )
                    new_selected = False
                modules_result.append(ModuleToggleItem(
                    id=a["item_id"],
                    isSelected=new_selected,
                ))
        
        return ApiResponse.success(CarItemToggleResponse(
            carId=request.carId,
            itemId=request.itemId,
            isSelected=request.isSelected,
            modules=modules_result,
        ), "更新成功")
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"切换装备状态失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


@router.post("/car/car-module-update", response_model=ApiResponse[CarModuleUpdateResponse])
async def update_car_modules(
    request: CarModuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[CarModuleUpdateResponse]:
    """
    批量更新设备模块选中状态
    
    业务逻辑:
    1. 验证任务状态
    2. 获取设备下所有模块
    3. 将moduleIds中的模块设为选中，其他设为未选中
    """
    logger.info(f"更新模块选中, carId={request.carId}, deviceId={request.deviceId}")
    
    try:
        # 统一使用活动想定的主事件ID
        event_id = await _resolve_event_id(db)
        if not event_id:
            return ApiResponse.error(40001, "没有活动想定或主事件")
        
        # 状态校验
        current_status = await _get_quest_status(db, event_id)
        if current_status in ["ready", "departed"]:
            return ApiResponse.error(40002, "当前状态不允许修改装备")
        
        car_id = UUID(request.carId)
        device_id = UUID(request.deviceId)
        
        assignment_repo = CarItemAssignmentRepository(db)
        
        updated_modules = await assignment_repo.update_modules_selection(
            event_id, car_id, device_id, request.moduleIds
        )
        
        return ApiResponse.success(CarModuleUpdateResponse(
            deviceId=request.deviceId,
            modules=[ModuleToggleItem(id=m["id"], isSelected=m["isSelected"]) for m in updated_modules],
        ), "更新成功")
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"更新模块状态失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")


# ==================== 车辆成员装备接口 ====================

@router.get("/car/my-equipment", response_model=ApiResponse[MyEquipmentData])
async def get_my_equipment(
    eventId: str = Query(..., description="事件ID"),
    userId: str = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MyEquipmentData]:
    """
    获取我的车辆装备清单（车辆成员专用）
    
    - 通过用户ID查询所属车辆
    - 返回指挥员分配的装备清单（不是AI推荐）
    - 仅返回 is_selected=true 的装备
    """
    logger.info(f"获取我的装备清单: eventId={eventId}, userId={userId}")
    
    try:
        event_id = UUID(eventId)
        user_id = UUID(userId)
        
        repo = MyEquipmentRepository(db)
        
        # 1. 获取用户所属车辆
        vehicle_info = await repo.get_user_vehicle(user_id, event_id)
        if not vehicle_info:
            return ApiResponse.error(403, "您不属于任何车辆，无法查看装备")
        
        vehicle_id = UUID(vehicle_info["vehicle_id"])
        
        # 2. 获取车辆被分配的装备
        items = await repo.get_vehicle_assigned_items(event_id, vehicle_id)
        
        # 3. 组装设备（含模块）
        devices = []
        modules_by_device = {}
        for mod in items["modules"]:
            parent_id = mod.get("parent_device_id")
            if parent_id:
                if parent_id not in modules_by_device:
                    modules_by_device[parent_id] = []
                modules_by_device[parent_id].append(MyEquipmentModule(
                    id=mod["id"],
                    name=mod["name"],
                    moduleType=mod["module_type"],
                    isSelected=mod["is_selected"],
                ))
        
        for dev in items["devices"]:
            device_modules = modules_by_device.get(dev["id"], [])
            devices.append(MyEquipmentDevice(
                id=dev["id"],
                name=dev["name"],
                model=dev["model"],
                deviceType=dev["device_type"],
                quantity=dev["quantity"],
                modules=device_modules,
                image=dev.get("image"),
                description=dev.get("description"),
                manufacturer=dev.get("manufacturer"),
                specifications=dev.get("specifications"),
            ))
        
        # 4. 组装物资
        supplies = [
            MyEquipmentSupply(
                id=s["id"],
                name=s["name"],
                category=s["category"],
                quantity=s["quantity"],
            )
            for s in items["supplies"]
        ]
        
        return ApiResponse.success(MyEquipmentData(
            vehicleId=vehicle_info["vehicle_id"],
            vehicleName=vehicle_info["vehicle_name"],
            vehicleCode=vehicle_info["vehicle_code"],
            vehicleStatus=vehicle_info["dispatch_status"],
            devices=devices,
            supplies=supplies,
            dispatchedAt=vehicle_info["dispatched_at"],
            dispatchedBy=vehicle_info["dispatched_by_name"],
        ))
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"获取我的装备清单失败: {e}")
        return ApiResponse.error(500, f"获取失败: {str(e)}")


@router.post("/car/my-equipment/toggle", response_model=ApiResponse[MyEquipmentToggleResponse])
async def toggle_my_equipment(
    request: MyEquipmentToggleRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[MyEquipmentToggleResponse]:
    """
    车辆成员切换装备选中状态
    
    - 验证用户是否属于该车辆
    - 修改 car_item_assignment 表中的选中状态
    - 记录修改人
    """
    logger.info(f"车辆成员切换装备: eventId={request.eventId}, userId={request.userId}, itemId={request.itemId}")
    
    try:
        event_id = UUID(request.eventId)
        user_id = UUID(request.userId)
        item_id = UUID(request.itemId)
        
        repo = MyEquipmentRepository(db)
        
        # 1. 验证用户所属车辆
        vehicle_info = await repo.get_user_vehicle(user_id, event_id)
        if not vehicle_info:
            return ApiResponse.error(403, "您不属于任何车辆，无权修改装备")
        
        vehicle_id = UUID(vehicle_info["vehicle_id"])
        
        # 2. 检查状态是否允许修改
        dispatch_status = vehicle_info.get("dispatch_status", "pending")
        if dispatch_status in ["ready", "departed"]:
            return ApiResponse.error(400, "当前状态不允许修改装备")
        
        # 3. 更新选中状态
        success = await repo.toggle_item_selection(
            event_id=event_id,
            vehicle_id=vehicle_id,
            item_id=item_id,
            is_selected=request.isSelected,
            updated_by=request.userId,
        )
        
        if not success:
            return ApiResponse.error(404, "装备不存在或未分配给您的车辆")
        
        return ApiResponse.success(MyEquipmentToggleResponse(
            vehicleId=str(vehicle_id),
            itemId=request.itemId,
            isSelected=request.isSelected,
            updatedBy=request.userId,
        ), "修改成功")
        
    except ValueError as e:
        return ApiResponse.error(400, f"参数格式错误: {str(e)}")
    except Exception as e:
        logger.exception(f"切换装备状态失败: {e}")
        return ApiResponse.error(500, f"操作失败: {str(e)}")
