"""
第三方接入业务服务

处理灾情上报、传感器告警、设备遥测、天气数据的业务逻辑。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.websocket import broadcast_event_update, broadcast_telemetry_batch
from src.domains.events.schemas import (
    EventCreate, EventSourceType, EventType, EventPriority, Location as EventLocation
)
from src.domains.events.service import EventService
from src.domains.events.repository import EventRepository
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import (
    EntityCreate, EntityType, EntitySource, GeoJsonGeometry, 
    EntityLocationUpdate, Location as EntityLocation
)

from .schemas import (
    DisasterReportRequest, DisasterReportResponse,
    SensorAlertRequest, SensorAlertResponse, AlertLevel,
    TelemetryBatchRequest, TelemetryResponse, TelemetryEntityUpdate,
    WeatherDataRequest, WeatherDataResponse,
    DeviceTelemetryRequest, DeviceTelemetryResponse,
    LocationUpdateRequest, LocationUpdateResponse,
    CallbackRequest, CallbackResponse, CallbackType,
)
from .deduplication import check_duplicate, DeduplicationResult
from .weather_repository import WeatherRepository

logger = logging.getLogger(__name__)


class IntegrationService:
    """第三方接入服务"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._event_service = EventService(db)
        self._event_repo = EventRepository(db)
        self._entity_service = EntityService(db)
    
    # ========================================================================
    # 灾情上报
    # ========================================================================
    
    async def process_disaster_report(
        self,
        scenario_id: UUID,
        data: DisasterReportRequest,
        source_system: str,
    ) -> DisasterReportResponse:
        """
        处理灾情上报
        
        流程：去重检查 → 创建事件 → 创建实体 → WebSocket推送
        
        Args:
            scenario_id: 想定ID
            data: 灾情上报数据
            source_system: 来源系统（从API密钥获取）
        
        Returns:
            上报响应
        """
        logger.info(
            f"处理灾情上报: scenario_id={scenario_id}, "
            f"disaster_type={data.disaster_type}, source_system={source_system}"
        )
        
        # 去重检查
        dedup_result = await check_duplicate(
            db=self._db,
            scenario_id=scenario_id,
            source_system=data.source_system,
            source_event_id=data.source_event_id,
            longitude=data.location.longitude,
            latitude=data.location.latitude,
            disaster_type=data.disaster_type.value,
            occurred_at=data.occurred_at,
        )
        
        if dedup_result.is_duplicate:
            logger.info(f"灾情去重命中: {dedup_result.reason}")
            
            # 追加更新记录到已有事件
            await self._append_update_to_event(
                event_id=dedup_result.duplicate_event_id,
                source_system=data.source_system,
                source_event_id=data.source_event_id,
                description=data.description,
            )
            
            return DisasterReportResponse(
                success=True,
                event_id=dedup_result.duplicate_event_id,
                event_code=dedup_result.duplicate_event_code,
                status="duplicate",
                message=f"该灾情已存在，已合并到现有事件: {dedup_result.reason}",
                created_at=datetime.utcnow(),
                duplicate_of=dedup_result.duplicate_event_id,
            )
        
        # 构建事件创建数据
        event_data = EventCreate(
            scenario_id=scenario_id,
            event_type=EventType(data.disaster_type.value),
            source_type=EventSourceType.external_system,
            source_detail={
                "source_system": data.source_system,
                "source_event_id": data.source_event_id,
                "reporter": data.reporter.model_dump() if data.reporter else None,
                "metadata": data.metadata,
            },
            title=f"{data.disaster_type.value}: {data.location.address or '位置待确认'}",
            description=data.description,
            location=EventLocation(
                longitude=data.location.longitude,
                latitude=data.location.latitude,
            ),
            address=data.location.address,
            priority=EventPriority(data.priority.value),
            estimated_victims=data.estimated_victims,
            is_time_critical=data.priority in ["critical", "high"],
            media_attachments=[{"url": url} for url in data.media_urls] if data.media_urls else None,
        )
        
        # 创建事件
        event_response = await self._event_service.create(event_data)
        
        logger.info(
            f"灾情事件创建成功: event_id={event_response.id}, "
            f"event_code={event_response.event_code}"
        )
        
        # 创建地图实体
        entity_id = await self._create_event_entity(
            scenario_id=scenario_id,
            event_id=event_response.id,
            disaster_type=data.disaster_type.value,
            longitude=data.location.longitude,
            latitude=data.location.latitude,
        )
        
        # WebSocket推送
        await broadcast_event_update(
            scenario_id=scenario_id,
            event_type="event_created",
            payload={
                "event_id": str(event_response.id),
                "event_code": event_response.event_code,
                "disaster_type": data.disaster_type.value,
                "priority": data.priority.value,
                "location": {
                    "longitude": data.location.longitude,
                    "latitude": data.location.latitude,
                },
                "source_system": source_system,
            },
        )
        
        return DisasterReportResponse(
            success=True,
            event_id=event_response.id,
            event_code=event_response.event_code,
            status="pending",
            message="灾情已接收，等待确认",
            entity_id=entity_id,
            created_at=event_response.created_at,
            duplicate_of=None,
        )
    
    async def _append_update_to_event(
        self,
        event_id: UUID,
        source_system: str,
        source_event_id: str,
        description: str,
    ) -> None:
        """追加更新记录到已有事件"""
        await self._event_repo.add_update_record(
            event_id=event_id,
            update_type="external_report_merged",
            previous_value=None,
            new_value={
                "source_system": source_system,
                "source_event_id": source_event_id,
                "description": description,
            },
            description=f"来自{source_system}的上报已合并",
            source_type="external_system",
        )
    
    async def _create_event_entity(
        self,
        scenario_id: UUID,
        event_id: UUID,
        disaster_type: str,
        longitude: float,
        latitude: float,
    ) -> Optional[UUID]:
        """为事件创建地图实体"""
        try:
            entity_data = EntityCreate(
                type=EntityType.event_point,
                layer_code="event_layer",
                geometry=GeoJsonGeometry(
                    type="Point",
                    coordinates=[longitude, latitude],
                ),
                properties={
                    "disaster_type": disaster_type,
                    "event_id": str(event_id),
                },
                source=EntitySource.system,
                visible_on_map=True,
                is_dynamic=False,
                scenario_id=scenario_id,
                event_id=event_id,
            )
            
            entity_response = await self._entity_service.create(entity_data)
            return entity_response.id
            
        except Exception as e:
            logger.error(f"创建事件实体失败: event_id={event_id}, error={e}")
            return None
    
    # ========================================================================
    # 传感器告警
    # ========================================================================
    
    async def process_sensor_alert(
        self,
        scenario_id: UUID,
        data: SensorAlertRequest,
        source_system: str,
    ) -> SensorAlertResponse:
        """
        处理传感器告警
        
        告警级别映射：
        - critical → 创建事件（优先级critical）
        - warning → 创建事件（优先级high）
        - info → 仅记录日志
        
        Args:
            scenario_id: 想定ID
            data: 告警数据
            source_system: 来源系统
        
        Returns:
            告警响应
        """
        alert_id = uuid4()
        
        logger.info(
            f"处理传感器告警: scenario_id={scenario_id}, "
            f"sensor_id={data.sensor_id}, alert_level={data.alert_level}"
        )
        
        # info级别仅记录日志
        if data.alert_level == AlertLevel.info:
            logger.info(f"传感器信息告警已记录: sensor_id={data.sensor_id}")
            return SensorAlertResponse(
                success=True,
                alert_id=alert_id,
                event_id=None,
                action_taken="logged",
                message="信息级告警已记录",
            )
        
        # 映射告警级别到事件优先级
        priority_map = {
            AlertLevel.critical: EventPriority.critical,
            AlertLevel.warning: EventPriority.high,
        }
        
        # 映射传感器类型到灾情类型
        disaster_type_map = {
            "seismometer": EventType.earthquake_secondary,
            "water_level_gauge": EventType.flood,
            "smoke_detector": EventType.fire,
            "gas_detector": EventType.hazmat_leak,
            "rain_gauge": EventType.flood,
            "displacement_sensor": EventType.landslide,
        }
        
        disaster_type = disaster_type_map.get(
            data.sensor_type.value, 
            EventType.other
        )
        
        # 创建事件
        event_data = EventCreate(
            scenario_id=scenario_id,
            event_type=disaster_type,
            source_type=EventSourceType.sensor_alert,
            source_detail={
                "sensor_id": data.sensor_id,
                "sensor_type": data.sensor_type.value,
                "alert_type": data.alert_type,
                "readings": data.readings,
                "source_system": data.source_system or source_system,
            },
            title=f"传感器告警: {data.sensor_id} - {data.alert_type}",
            description=f"传感器{data.sensor_id}触发{data.alert_level.value}级告警",
            location=EventLocation(
                longitude=data.location.longitude,
                latitude=data.location.latitude,
            ),
            address=data.location.address,
            priority=priority_map[data.alert_level],
            is_time_critical=data.alert_level == AlertLevel.critical,
        )
        
        event_response = await self._event_service.create(event_data)
        
        logger.info(
            f"传感器告警事件创建成功: alert_id={alert_id}, "
            f"event_id={event_response.id}"
        )
        
        return SensorAlertResponse(
            success=True,
            alert_id=alert_id,
            event_id=event_response.id,
            action_taken="event_created",
            message=f"已创建{data.alert_level.value}级告警事件",
        )
    
    # ========================================================================
    # 设备遥测（批量）
    # ========================================================================
    
    async def process_telemetry_batch(
        self,
        data: TelemetryBatchRequest,
        source_system: str,
    ) -> TelemetryResponse:
        """
        处理批量遥测数据
        
        更新设备关联实体的位置，记录轨迹，触发WebSocket推送。
        
        Args:
            data: 批量遥测数据
            source_system: 来源系统
        
        Returns:
            处理响应
        """
        logger.info(
            f"处理批量遥测: count={len(data.batch)}, source_system={source_system}"
        )
        
        entity_updates: list[TelemetryEntityUpdate] = []
        processed_count = 0
        
        for item in data.batch:
            try:
                # 查找设备关联的实体
                entity = await self._find_device_entity(item.device_id)
                
                if not entity:
                    logger.warning(f"设备实体不存在: device_id={item.device_id}")
                    entity_updates.append(TelemetryEntityUpdate(
                        device_id=item.device_id,
                        entity_id=None,
                        success=False,
                        error="设备实体不存在",
                    ))
                    continue
                
                # 更新实体位置
                if item.payload.longitude is not None and item.payload.latitude is not None:
                    await self._entity_service.update_location(
                        entity_id=entity.id,
                        data=EntityLocationUpdate(
                            location=EntityLocation(
                                longitude=item.payload.longitude,
                                latitude=item.payload.latitude,
                            ),
                            speed_kmh=item.payload.ground_speed * 3.6 if item.payload.ground_speed else None,
                            heading=int(item.payload.heading) if item.payload.heading else None,
                        ),
                    )
                
                entity_updates.append(TelemetryEntityUpdate(
                    device_id=item.device_id,
                    entity_id=entity.id,
                    success=True,
                    error=None,
                ))
                processed_count += 1
                
            except Exception as e:
                logger.error(f"处理遥测失败: device_id={item.device_id}, error={e}")
                entity_updates.append(TelemetryEntityUpdate(
                    device_id=item.device_id,
                    entity_id=None,
                    success=False,
                    error=str(e),
                ))
        
        # 批量WebSocket推送（遥测数据不绑定特定scenario）
        if processed_count > 0:
            # 构造成功的更新列表用于推送
            ws_updates = []
            for i, item in enumerate(data.batch):
                update_result = entity_updates[i]
                if update_result.success and item.payload.longitude and item.payload.latitude:
                    ws_updates.append({
                        "device_id": item.device_id,
                        "entity_id": str(update_result.entity_id) if update_result.entity_id else None,
                        "location": {
                            "longitude": item.payload.longitude,
                            "latitude": item.payload.latitude,
                        },
                        "speed_kmh": item.payload.ground_speed * 3.6 if item.payload.ground_speed else None,
                        "heading": int(item.payload.heading) if item.payload.heading else None,
                    })
            
            # 推送到所有订阅telemetry频道的客户端
            if ws_updates:
                await broadcast_telemetry_batch(ws_updates)
                logger.info(f"遥测数据推送完成: ws_updates={len(ws_updates)}")
            
            logger.info(f"遥测数据处理完成: processed={processed_count}, total={len(data.batch)}")
        
        return TelemetryResponse(
            success=True,
            received_count=len(data.batch),
            processed_count=processed_count,
            entity_updates=entity_updates,
        )
    
    async def _find_device_entity(self, device_id: str):
        """根据device_id查找关联实体"""
        from src.domains.map_entities.models import Entity
        
        stmt = select(Entity).where(Entity.device_id == device_id).limit(1)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
    
    # ========================================================================
    # 天气数据
    # ========================================================================
    
    async def process_weather_data(
        self,
        data: WeatherDataRequest,
        source_system: str,
    ) -> WeatherDataResponse:
        """
        处理天气数据
        
        存储天气记录，评估无人机飞行条件，处理天气预警。
        
        Args:
            data: 天气数据
            source_system: 来源系统
        
        Returns:
            处理响应
        """
        logger.info(
            f"处理天气数据: area_id={data.area_id}, "
            f"weather_type={data.weather_type}, source={source_system}"
        )
        
        # 评估无人机飞行条件
        uav_flyable, restriction_reason = self._evaluate_uav_conditions(data)
        
        # 评估地面行动条件
        ground_operable, ground_restriction = self._evaluate_ground_conditions(data)
        
        # 转换预警数据格式
        alerts_data = [
            {
                "type": a.alert_type,
                "level": a.level.value,
                "message": a.message,
                "issued_at": a.issued_at.isoformat() if a.issued_at else None,
            }
            for a in data.alerts
        ] if data.alerts else []
        
        # 转换预报数据格式
        forecast_data = None
        if data.forecast:
            forecast_data = [
                {
                    "hour": f.hour,
                    "weather_type": f.weather_type.value,
                    "temperature": f.temperature,
                    "wind_speed": f.wind_speed,
                    "precipitation": f.precipitation,
                }
                for f in data.forecast
            ]
        
        # 转换覆盖区域GeoJSON
        coverage_area = None
        if data.coverage_area:
            coverage_area = data.coverage_area.model_dump()
        
        # 天气数据入库
        weather_repo = WeatherRepository(self._db)
        weather_record = await weather_repo.create(
            weather_type=data.weather_type.value,
            temperature=data.temperature,
            wind_speed=data.wind_speed,
            wind_direction=data.wind_direction,
            visibility=data.visibility,
            precipitation=data.precipitation,
            humidity=data.humidity,
            pressure=data.pressure,
            coverage_area=coverage_area,
            area_id=data.area_id,
            area_name=data.area_name,
            alerts=alerts_data,
            forecast_data={"forecasts": forecast_data} if forecast_data else None,
            data_source=source_system,
            recorded_at=data.recorded_at,
            valid_until=data.valid_until,
            uav_flyable=uav_flyable,
            uav_restriction_reason=restriction_reason,
            ground_operable=ground_operable,
            ground_restriction_reason=ground_restriction,
        )
        
        logger.info(
            f"天气数据已入库: weather_id={weather_record.id}, "
            f"uav_flyable={uav_flyable}, alerts_count={len(alerts_data)}"
        )
        
        return WeatherDataResponse(
            success=True,
            weather_id=weather_record.id,
            uav_flyable=uav_flyable,
            uav_restriction_reason=restriction_reason,
            active_alerts_count=len(alerts_data),
        )
    
    def _evaluate_uav_conditions(
        self,
        data: WeatherDataRequest,
    ) -> tuple[bool, Optional[str]]:
        """评估无人机飞行条件"""
        reasons = []
        
        # 风速限制（超过8m/s不宜飞行）
        if data.wind_speed and data.wind_speed > 8:
            reasons.append(f"风速{data.wind_speed}m/s超过安全阈值8m/s")
        
        # 能见度限制（低于1000米不宜飞行）
        if data.visibility and data.visibility < 1000:
            reasons.append(f"能见度{data.visibility}m低于安全阈值1000m")
        
        # 恶劣天气类型限制
        bad_weather = ["heavy_rain", "rainstorm", "thunderstorm", "typhoon", "sandstorm", "snow", "fog"]
        if data.weather_type.value in bad_weather:
            reasons.append(f"恶劣天气类型: {data.weather_type.value}")
        
        # 降水量限制（超过10mm/h不宜飞行）
        if data.precipitation and data.precipitation > 10:
            reasons.append(f"降水量{data.precipitation}mm/h超过安全阈值10mm/h")
        
        if reasons:
            return False, "；".join(reasons)
        return True, None
    
    def _evaluate_ground_conditions(
        self,
        data: WeatherDataRequest,
    ) -> tuple[bool, Optional[str]]:
        """评估地面行动条件"""
        reasons = []
        
        # 暴雨/台风限制地面行动
        severe_weather = ["rainstorm", "typhoon", "thunderstorm"]
        if data.weather_type.value in severe_weather:
            reasons.append(f"恶劣天气: {data.weather_type.value}")
        
        # 降水量超过50mm/h严重影响地面行动
        if data.precipitation and data.precipitation > 50:
            reasons.append(f"降水量{data.precipitation}mm/h过大")
        
        # 能见度低于100米严重影响地面行动
        if data.visibility and data.visibility < 100:
            reasons.append(f"能见度{data.visibility}m过低")
        
        # 风力超过10级影响地面行动
        if data.wind_scale and data.wind_scale >= 10:
            reasons.append(f"风力{data.wind_scale}级过强")
        
        if reasons:
            return False, "；".join(reasons)
        return True, None
    
    # ========================================================================
    # 外部系统回调
    # ========================================================================
    
    async def process_callback(
        self,
        data: CallbackRequest,
        source_system: str,
    ) -> CallbackResponse:
        """
        处理外部系统回调
        
        根据回调类型分发处理：
        - task_completed/task_failed: 更新任务状态
        - resource_status: 更新资源状态
        - system_event: 记录系统事件
        - acknowledgment: 确认消息
        
        Args:
            data: 回调数据
            source_system: 来源系统
        
        Returns:
            回调响应
        """
        callback_id = uuid4()
        
        logger.info(
            f"处理外部回调: callback_type={data.callback_type}, "
            f"reference_id={data.reference_id}, source_system={source_system}"
        )
        
        try:
            action_taken = "processed"
            message = "回调已处理"
            
            if data.callback_type in (CallbackType.task_completed, CallbackType.task_failed):
                await self._handle_task_callback(data)
                message = f"任务{data.callback_type.value}回调已处理"
                
            elif data.callback_type == CallbackType.resource_status:
                await self._handle_resource_callback(data)
                message = "资源状态回调已处理"
                
            elif data.callback_type == CallbackType.system_event:
                logger.info(f"系统事件回调: {data.message}")
                action_taken = "logged"
                message = "系统事件已记录"
                
            elif data.callback_type == CallbackType.acknowledgment:
                logger.info(f"确认回调: reference_id={data.reference_id}")
                action_taken = "acknowledged"
                message = "确认已记录"
            
            return CallbackResponse(
                success=True,
                callback_id=callback_id,
                action_taken=action_taken,
                message=message,
            )
            
        except Exception as e:
            logger.error(f"处理回调失败: callback_type={data.callback_type}, error={e}")
            return CallbackResponse(
                success=False,
                callback_id=callback_id,
                action_taken="failed",
                message=f"回调处理失败: {str(e)}",
            )
    
    async def _handle_task_callback(self, data: CallbackRequest) -> None:
        """处理任务回调"""
        from src.domains.tasks.repository import TaskRepository
        
        task_repo = TaskRepository(self._db)
        task = await task_repo.get_by_id(data.reference_id)
        
        if not task:
            logger.warning(f"任务不存在: task_id={data.reference_id}")
            return
        
        if data.callback_type == CallbackType.task_completed:
            await task_repo.update_status(task, "completed")
        elif data.callback_type == CallbackType.task_failed:
            await task_repo.update_status(task, "failed")
        
        logger.info(f"任务状态已更新: task_id={data.reference_id}, new_status={data.status}")
    
    async def _handle_resource_callback(self, data: CallbackRequest) -> None:
        """处理资源状态回调"""
        resource_type = data.reference_type
        new_status = data.payload.get("status")
        
        if not new_status:
            logger.warning(f"资源回调缺少status: {data.payload}")
            return
        
        logger.info(
            f"资源状态更新: type={resource_type}, "
            f"id={data.reference_id}, status={new_status}"
        )
        # 具体状态更新逻辑由对应资源模块处理
