"""
前端事件API路由

接口路径: /events/*
对接前端事件确认等操作

新增地震事件触发接口，用于模拟仿真测试
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.stomp.broker import stomp_broker
from src.domains.events.service import EventService
from src.domains.events.schemas import (
    EventConfirm, EventCreate, EventType, EventSourceType, EventPriority, Location,
)
from src.domains.map_entities.service import EntityService as MapEntityService
from src.domains.map_entities.schemas import (
    EntityCreate as MapEntityCreate, EntityType as MapEntityType,
    EntitySource as MapEntitySource, GeoJsonGeometry,
)
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    EarthquakeTriggerRequest, EarthquakeTriggerResponse, EarthquakeAnimationPayload,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["前端-事件"])


def get_event_service(db: AsyncSession = Depends(get_db)) -> EventService:
    """获取事件服务实例"""
    return EventService(db)


@router.get("/event-confirm", response_model=ApiResponse)
async def confirm_event(
    eventId: Optional[str] = Query(None, description="事件ID，不传则确认最新待确认事件"),
    scenarioId: Optional[str] = Query(None, description="想定ID"),
    service: EventService = Depends(get_event_service),
) -> ApiResponse:
    """
    灾害事件确认
    
    前端调用时机：指挥员收到事件消息后点击确认
    业务逻辑：
    1. 如果传了eventId，确认指定事件
    2. 如果没传eventId但传了scenarioId，确认该想定下最新的待确认事件
    3. 都没传则返回错误
    """
    logger.info(f"事件确认请求, eventId={eventId}, scenarioId={scenarioId}")
    
    try:
        if eventId:
            event_uuid = UUID(eventId)
            confirm_data = EventConfirm(confirmation_note="前端确认")
            result = await service.confirm(event_uuid, confirm_data)
            logger.info(f"事件确认成功, eventId={eventId}")
            return ApiResponse.success({"eventId": str(result.id), "status": result.status})
        
        elif scenarioId:
            scenario_uuid = UUID(scenarioId)
            pending_events = await service.get_pending_review(scenario_uuid)
            
            if not pending_events:
                logger.info(f"没有待确认事件, scenarioId={scenarioId}")
                return ApiResponse.success(None, "没有待确认的事件")
            
            latest_event = pending_events[0]
            confirm_data = EventConfirm(confirmation_note="前端确认")
            result = await service.confirm(latest_event.id, confirm_data)
            logger.info(f"确认最新事件成功, eventId={latest_event.id}")
            return ApiResponse.success({"eventId": str(result.id), "status": result.status})
        
        else:
            return ApiResponse.error(400, "需要提供eventId或scenarioId")
            
    except ValueError as e:
        logger.warning(f"无效的ID格式: {e}")
        return ApiResponse.error(400, f"无效的ID格式: {str(e)}")
    except Exception as e:
        logger.exception(f"事件确认失败: {e}")
        return ApiResponse.error(500, f"事件确认失败: {str(e)}")


@router.get("/pending", response_model=ApiResponse)
async def get_pending_events(
    scenarioId: str = Query(..., description="想定ID"),
    service: EventService = Depends(get_event_service),
) -> ApiResponse:
    """
    获取待确认事件列表
    
    返回pending和pre_confirmed状态的事件
    """
    logger.info(f"获取待确认事件列表, scenarioId={scenarioId}")
    
    try:
        scenario_uuid = UUID(scenarioId)
        events = await service.get_pending_review(scenario_uuid)
        
        result = []
        for event in events:
            result.append({
                "eventId": str(event.id),
                "title": event.title,
                "description": event.description,
                "status": event.status,
                "priority": event.priority,
                "eventType": event.event_type,
                "location": {
                    "longitude": event.location.longitude,
                    "latitude": event.location.latitude,
                },
                "address": event.address,
                "reportedAt": event.reported_at.isoformat() if event.reported_at else None,
            })
        
        logger.info(f"返回待确认事件数量: {len(result)}")
        return ApiResponse.success(result)
        
    except ValueError as e:
        logger.warning(f"无效的ID格式: {e}")
        return ApiResponse.error(400, f"无效的ID格式: {str(e)}")
    except Exception as e:
        logger.exception(f"获取待确认事件失败: {e}")
        return ApiResponse.error(500, f"获取待确认事件失败: {str(e)}")


# ============================================================================
# 地震事件触发（模拟仿真）
# ============================================================================

from src.domains.scenarios.service import ScenarioService

@router.post("/earthquake/trigger", response_model=ApiResponse[EarthquakeTriggerResponse])
async def trigger_earthquake_event(
    request: EarthquakeTriggerRequest,
    service: EventService = Depends(get_event_service),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[EarthquakeTriggerResponse]:
    """
    触发地震事件（模拟仿真）
    
    用于系统测试和模拟仿真推演，执行顺序：
    1. **先** 创建真实事件记录（入库）
    2. **后** 推送地震动画到WebSocket（前端播放动画+弹窗）
    
    WebSocket主题：
    - /topic/scenario.disaster.triggered - 事件数据（由EventService自动推送）
    - /topic/scenario.earthquake.triggered - 动画触发
    
    请求示例：
    ```json
    {
        "magnitude": 6.5,
        "location": {"longitude": 104.5, "latitude": 31.2},
        "depthKm": 10,
        "epicenterName": "北川县",
        "message": "北川县发生6.5级地震",
        "estimatedVictims": 100,
        "animationDurationMs": 3000
    }
    ```
    """
    logger.info(
        f"地震事件触发请求: scenario={request.scenario_id}, "
        f"magnitude={request.magnitude}, location={request.epicenter_name}"
    )
    
    try:
        # 0. 处理想定ID（如果未提供，则从数据库查询当前活动想定）
        scenario_id = request.scenario_id
        if not scenario_id:
            scenario_service = ScenarioService(db)
            # 查询数据库中状态为 active 的想定
            active_scenario = await scenario_service.get_active()
            if active_scenario:
                scenario_id = active_scenario.id
                logger.info(f"使用活动想定ID: {scenario_id}")
            else:
                # 如果没有活动想定，返回错误
                return ApiResponse.error(400, "未指定想定ID，且系统中无活动想定（status='active'）")

        # 1. 构建推送消息文本（如果用户未提供则自动生成）
        push_message = request.message
        if not push_message:
            push_message = f"{request.epicenter_name}发生{request.magnitude}级地震"
        
        # 2. 震源深度默认值
        depth_km = request.depth_km or Decimal("10")
        
        # 3. 幂等检查：同一想定下相同震中+震级的地震只能创建一次
        existing = await service.repo.find_earthquake_by_params(
            scenario_id=scenario_id,
            epicenter_name=request.epicenter_name,
            magnitude=float(request.magnitude),
        )
        if existing:
            logger.info(f"地震事件已存在（幂等返回）: event_id={existing.id}")
            response_data = EarthquakeTriggerResponse(
                event_id=str(existing.id),
                event_code=existing.event_code,
                message=push_message,
                animation_sent=False,  # 不重复推送动画
                duplicate=True,
            )
            return ApiResponse.success(
                response_data.model_dump(by_alias=True),
                "地震事件已存在"
            )
        
        # 4. **创建事件** - 调用EventService创建真实事件记录（入库）
        # EventService.create()内部会自动广播到 /topic/scenario.disaster.triggered
        event_create = EventCreate(
            scenario_id=scenario_id,
            event_type=EventType.earthquake,
            source_type=EventSourceType.system_inference,  # 标记为系统推断（模拟仿真）
            source_detail={
                "simulation": True,
                "magnitude": float(request.magnitude),
                "depth_km": float(depth_km),
                "affected_area_km2": float(request.affected_area_km2) if request.affected_area_km2 else None,
            },
            title=push_message,
            description=f"震中: {request.epicenter_name}, 震级: {request.magnitude}级, 震源深度: {depth_km}公里",
            location=Location(
                longitude=request.location.longitude,
                latitude=request.location.latitude,
            ),
            address=request.epicenter_name,
            priority=_get_earthquake_priority(request.magnitude),
            estimated_victims=request.estimated_victims,
            is_time_critical=request.magnitude >= Decimal("5.0"),  # 5级以上为时间紧急
            is_main_event=True,  # 地震事件作为想定的主事件
        )
        
        event = await service.create(event_create)
        logger.info(f"地震事件已创建: event_id={event.id}, code={event.event_code}")
        
        # 5. 写入风险区域表（用于路径规划绕行判断）
        await _create_earthquake_risk_zones(
            db=service.repo.db,
            scenario_id=scenario_id,
            event_id=event.id,
            center_lng=request.location.longitude,
            center_lat=request.location.latitude,
            magnitude=float(request.magnitude),
            epicenter_name=request.epicenter_name,
        )
        
        # 6. 创建地震地图实体（写入数据库，同时广播给前端）
        # 生成热力图数据：以震中为中心，根据震级生成影响范围内的热力点
        heat_points = _generate_earthquake_heat_points(
            center_lng=request.location.longitude,
            center_lat=request.location.latitude,
            magnitude=float(request.magnitude),
        )
        
        # 使用 MapEntityService 创建实体（写入数据库 + 自动广播）
        map_entity_service = MapEntityService(service.repo.db)
        entity_create = MapEntityCreate(
            type=MapEntityType.event_point,
            layer_code="layer.event",
            geometry=GeoJsonGeometry(
                type="Point",
                coordinates=[request.location.longitude, request.location.latitude],
            ),
            properties={
                "disasterType": "earthquake",
                "eventType": 1,
                "eventLevel": _get_earthquake_event_level(request.magnitude),
                "title": push_message,
                "magnitude": float(request.magnitude),
                "depthKm": float(depth_km),
                "epicenterName": request.epicenter_name,
                "eventId": str(event.id),
                "heatPoints": heat_points,
                "heatStyle": {
                    "radius": 180,
                    "minOpacity": 0,
                    "maxOpacity": 0.4,
                    "blur": 0.5,
                },
            },
            source=MapEntitySource.system,
            visible_on_map=True,
            scenario_id=scenario_id,
            event_id=event.id,
        )
        earthquake_entity = await map_entity_service.create(entity_create)
        earthquake_entity_id = str(earthquake_entity.id)
        logger.info(f"地震实体已创建并持久化: {earthquake_entity_id}")
        
        # 7. **后推送灾害消息** - 发送到 /topic/scenario.disaster.triggered
        # 必须包含前端灾害事件所需字段：eventId, messageId, eventLevel, eventType, title, time, origin, data
        event_timestamp = datetime.utcnow().isoformat() + "Z"
        message_id = f"msg-earthquake-{event.id}"  # 生成消息ID用于前端确认接口
        animation_payload = EarthquakeAnimationPayload(
            # 前端灾害事件必填字段
            event_id=str(event.id),
            message_id=message_id,
            title=push_message,
            event_level=_get_earthquake_event_level(request.magnitude),  # 1=红 2=橙 3=蓝 4=黑
            event_type=1,  # 1=地震（前端图标目录为 event/1/）
            time=event_timestamp,
            origin="模拟仿真系统",
            data=f"震中: {request.epicenter_name}, 震级: {request.magnitude}级, 震源深度: {depth_km}公里",
            # 地震专属字段
            animation_type="earthquake",
            magnitude=request.magnitude,
            location=[request.location.longitude, request.location.latitude],
            epicenter_name=request.epicenter_name,
            depth_km=depth_km,
            message=push_message,
            animation_duration_ms=request.animation_duration_ms,
            timestamp=event_timestamp,
            scenario_id=str(scenario_id),
            estimated_victims=request.estimated_victims if request.estimated_victims > 0 else None,
            affected_area_km2=request.affected_area_km2,
            # 关联实体ID（前端用于地图渲染）
            entity_ids=[earthquake_entity_id],
        )
        
        # 广播灾害事件消息（触发前端弹窗）
        animation_data = animation_payload.model_dump(by_alias=True, exclude_none=True)
        
        # STOMP协议推送到 /topic/scenario.disaster.triggered（前端已订阅此主题）
        # 注意：不传scenario_id，因为前端连接时未指定scenario_id，传入会导致消息被过滤
        await stomp_broker.broadcast_event(
            "disaster",  # 使用disaster主题，前端EntityWebSocketClient已订阅
            animation_data,
            scenario_id=None,  # 不过滤场景，所有订阅者都能收到
        )
        logger.info(f"地震灾害消息已推送: {push_message}")
        
        animation_sent = True
        
        # 8. 返回响应
        response_data = EarthquakeTriggerResponse(
            event_id=str(event.id),
            event_code=event.event_code,
            message=push_message,
            animation_sent=animation_sent,
            duplicate=False,
        )
        
        return ApiResponse.success(
            response_data.model_dump(by_alias=True),
            f"地震事件触发成功: {push_message}"
        )
        
    except Exception as e:
        logger.exception(f"地震事件触发失败: {e}")
        return ApiResponse.error(500, f"地震事件触发失败: {str(e)}")


def _get_earthquake_priority(magnitude: Decimal) -> EventPriority:
    """根据震级计算事件优先级"""
    if magnitude >= Decimal("7.0"):
        return EventPriority.critical  # 7级以上：特大地震
    elif magnitude >= Decimal("6.0"):
        return EventPriority.high  # 6-7级：强烈地震
    elif magnitude >= Decimal("4.5"):
        return EventPriority.medium  # 4.5-6级：中强地震
    else:
        return EventPriority.low  # 4.5以下：有感地震


def _get_earthquake_event_level(magnitude: Decimal) -> int:
    """
    根据震级计算前端灾害等级
    
    前端 eventLevel 含义：1=红色(紧急) 2=橙色(警告) 3=蓝色(信息) 4=黑色(普通)
    """
    if magnitude >= Decimal("7.0"):
        return 1  # 红色：特大地震
    elif magnitude >= Decimal("6.0"):
        return 1  # 红色：强烈地震
    elif magnitude >= Decimal("4.5"):
        return 2  # 橙色：中强地震
    else:
        return 3  # 蓝色：有感地震


async def _create_earthquake_risk_zones(
    db: AsyncSession,
    scenario_id: UUID,
    event_id: UUID,
    center_lng: float,
    center_lat: float,
    magnitude: float,
    epicenter_name: str,
) -> None:
    """
    创建地震风险区域（写入 disaster_affected_areas_v2 表）
    
    根据震级创建三个同心圆风险区域：
    - 核心区（红色）：risk_level=10，救援车辆可通行，普通车辆绕行
    - 影响区（橙色）：risk_level=7，所有车辆可通行但降速
    - 外围区（黄色）：risk_level=4，正常通行，提示警告
    
    路径规划时根据 risk_level 和 passable_vehicle_types 判断绕行策略
    """
    import math
    from sqlalchemy import text
    
    # 根据震级计算各区域半径（单位：米）
    # 震级每增加1级，影响范围约扩大2倍
    base_radius_m = 2000  # 4级地震核心区半径约2km
    core_radius = base_radius_m * (1.5 ** (magnitude - 4))
    impact_radius = core_radius * 2
    outer_radius = core_radius * 4
    
    # 限制最大半径
    core_radius = min(core_radius, 10000)    # 最大10km
    impact_radius = min(impact_radius, 25000)  # 最大25km
    outer_radius = min(outer_radius, 50000)   # 最大50km
    
    # 定义三个风险区域（使用新的 passage_status 字段）
    zones = [
        {
            "name": f"{epicenter_name}地震核心区",
            "area_type": "seismic_red",
            "radius_m": core_radius,
            "severity": "critical",
            "risk_level": 10,
            "passable": True,  # 救援车辆可进入
            "passable_vehicle_types": ["rescue", "ambulance", "fire_truck", "police"],
            "speed_reduction_percent": 50,  # 降速50%
            "passage_status": "needs_reconnaissance",  # 需侦察确认
            "reconnaissance_required": True,
            "description": f"震中{core_radius/1000:.1f}km范围内，需侦察确认通行性",
        },
        {
            "name": f"{epicenter_name}地震影响区",
            "area_type": "seismic_orange",
            "radius_m": impact_radius,
            "severity": "high",
            "risk_level": 7,
            "passable": True,
            "passable_vehicle_types": None,  # 所有车辆可通行
            "speed_reduction_percent": 30,  # 降速30%
            "passage_status": "passable_with_caution",  # 可通行但需谨慎
            "reconnaissance_required": False,
            "description": f"震中{impact_radius/1000:.1f}km范围内，建议减速通行",
        },
        {
            "name": f"{epicenter_name}地震外围区",
            "area_type": "seismic_yellow",
            "radius_m": outer_radius,
            "severity": "medium",
            "risk_level": 4,
            "passable": True,
            "passable_vehicle_types": None,  # 所有车辆可通行
            "speed_reduction_percent": 0,  # 正常速度
            "passage_status": "clear",  # 安全通行
            "reconnaissance_required": False,
            "description": f"震中{outer_radius/1000:.1f}km范围内，注意余震风险",
        },
    ]
    
    # 生成圆形多边形并插入数据库
    for zone in zones:
        # 生成近似圆形的多边形（32个点）
        polygon_wkt = _create_circle_polygon_wkt(
            center_lng, center_lat, zone["radius_m"], num_points=32
        )
        
        # 构建INSERT语句（包含新的 passage_status 字段）
        sql = text("""
            INSERT INTO operational_v2.disaster_affected_areas_v2 (
                scenario_id, name, area_type, geometry, severity, risk_level,
                passable, passable_vehicle_types, speed_reduction_percent,
                passage_status, reconnaissance_required,
                description, properties
            ) VALUES (
                :scenario_id, :name, :area_type, ST_GeogFromText(:geometry),
                :severity, :risk_level, :passable, :passable_vehicle_types,
                :speed_reduction_percent, :passage_status, :reconnaissance_required,
                :description, :properties
            )
        """)
        
        await db.execute(sql, {
            "scenario_id": str(scenario_id),
            "name": zone["name"],
            "area_type": zone["area_type"],
            "geometry": polygon_wkt,
            "severity": zone["severity"],
            "risk_level": zone["risk_level"],
            "passable": zone["passable"],
            "passable_vehicle_types": zone["passable_vehicle_types"],
            "speed_reduction_percent": zone["speed_reduction_percent"],
            "passage_status": zone["passage_status"],
            "reconnaissance_required": zone["reconnaissance_required"],
            "description": zone["description"],
            "properties": f'{{"event_id": "{event_id}", "magnitude": {magnitude}}}',
        })
    
    await db.commit()
    logger.info(f"地震风险区域已创建: 核心区{core_radius/1000:.1f}km, 影响区{impact_radius/1000:.1f}km, 外围区{outer_radius/1000:.1f}km")


def _create_circle_polygon_wkt(
    center_lng: float,
    center_lat: float,
    radius_m: float,
    num_points: int = 32,
) -> str:
    """
    创建圆形多边形的WKT表示
    
    Args:
        center_lng: 圆心经度
        center_lat: 圆心纬度
        radius_m: 半径（米）
        num_points: 多边形顶点数（越多越接近圆形）
    
    Returns:
        WKT格式的POLYGON字符串
    """
    import math
    
    # 将米转换为度数（近似值，1度约111km）
    radius_deg = radius_m / 111000
    
    points = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        lng = center_lng + radius_deg * math.cos(angle)
        lat = center_lat + radius_deg * math.sin(angle) * 0.9  # 纬度方向略压缩
        points.append(f"{lng:.6f} {lat:.6f}")
    
    # 闭合多边形
    points.append(points[0])
    
    return f"POLYGON(({', '.join(points)}))"


def _generate_earthquake_heat_points(
    center_lng: float,
    center_lat: float,
    magnitude: float,
) -> list[list[float]]:
    """
    生成地震热力图数据点（精简版）
    
    以震中为中心，根据震级生成影响范围内的热力点
    热力值从震中向外递减
    
    Args:
        center_lng: 震中经度
        center_lat: 震中纬度
        magnitude: 震级
    
    Returns:
        热力点列表 [[lng, lat, value], ...]，约17个点
    """
    import math
    
    # 根据震级计算影响半径（度数，约111km/度）
    base_radius = 0.05  # 基础半径约5.5km
    radius = base_radius * (1.5 ** (magnitude - 4))  # 4级地震为基准
    radius = min(radius, 0.5)  # 最大约55km
    
    heat_points = []
    
    # 震中点（最高热力值）
    heat_points.append([center_lng, center_lat, 1.0])
    
    # 生成同心圆环上的点（精简：2圈，每圈8个点 = 17个点）
    rings = 2
    points_per_ring = 8
    
    for ring in range(1, rings + 1):
        ring_radius = radius * ring / rings
        heat_value = 1.0 - (ring / rings) * 0.6  # 热力值从1.0递减到0.4
        
        for i in range(points_per_ring):
            angle = 2 * math.pi * i / points_per_ring
            lng = center_lng + ring_radius * math.cos(angle)
            lat = center_lat + ring_radius * math.sin(angle) * 0.9
            heat_points.append([round(lng, 6), round(lat, 6), round(heat_value, 2)])
    
    return heat_points
