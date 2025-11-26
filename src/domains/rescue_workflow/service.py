"""
救援业务流程服务

实现五阶段救援流程的业务逻辑
- 阶段1: 接警通报 - 复用EventService
- 阶段2: 途中导航 - 路径管理、安全点
- 阶段3: 现场指挥 - 指挥所、无人机、救援点检测
- 阶段4: 救援作业 - 救援点CRUD、协同总览
- 阶段5: 评估总结 - 评估报告

AI功能（装备推荐、路径规划、风险预测等）保留占位，返回Mock数据
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from shapely import wkb

from .schemas import (
    IncidentNotification, EquipmentSuggestionRequest, EquipmentSuggestionResponse,
    PreparationTask, PreparationTaskComplete, DepartCommand, 
    RouteRequest, RouteResponse,
    RiskPrediction, SafePoint, SafePointConfirm,
    CommandPostRecommendation, CommandPostConfirm, UAVClusterControl,
    RescuePointDetection, RescuePointConfirm, RescuePointCreate, RescuePointUpdate,
    RescuePointResponse, CoordinationTracking, CoordinationUpdate,
    EvaluationReportRequest, EvaluationReport,
    ManualRecommendation, ManualSearchRequest, Location, EquipmentItem
)
from .repository import RescuePointRepository, EvaluationReportRepository
from .models import RescuePoint, EvaluationReport as EvaluationReportModel

from src.domains.events.service import EventService
from src.domains.events.schemas import EventCreate, EventType, EventSourceType, EventPriority
from src.domains.events.schemas import Location as EventLocation
from src.domains.tasks.service import TaskService
from src.domains.tasks.schemas import TaskCreate, TaskType, TaskPriority
from src.domains.tasks.schemas import Location as TaskLocation
from src.domains.resources.teams.service import TeamService
from src.domains.resources.teams.schemas import TeamStatus
from src.domains.resources.vehicles.service import VehicleService
from src.domains.resources.vehicles.schemas import VehicleStatus
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import EntityCreate as MapEntityCreate, EntityType as MapEntityType, GeoJsonGeometry, EntitySource

from src.core.exceptions import NotFoundError, ConflictError
from src.core.websocket import broadcast_event_update, broadcast_alert


logger = logging.getLogger(__name__)


class RescueWorkflowService:
    """救援流程服务 - 编排五阶段救援流程"""
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._rescue_point_repo = RescuePointRepository(db)
        self._evaluation_report_repo = EvaluationReportRepository(db)
        # 复用其他模块的Service
        self._event_service = EventService(db)
        self._task_service = TaskService(db)
        self._team_service = TeamService(db)
        self._vehicle_service = VehicleService(db)
        self._entity_service = EntityService(db)
    
    # ========================================================================
    # 阶段1: 接警通报
    # ========================================================================
    
    async def receive_incident(
        self, 
        scenario_id: UUID, 
        data: IncidentNotification
    ) -> dict[str, Any]:
        """
        接收事件通报
        
        业务流程:
        1. 调用EventService创建事件记录
        2. 广播事件通知到WebSocket
        3. 返回创建的事件信息
        """
        logger.info(f"接收事件通报: scenario_id={scenario_id}, type={data.incident_type}, title={data.title}")
        
        # 构造EventCreate请求
        event_create = EventCreate(
            scenario_id=scenario_id,
            event_type=self._map_incident_type(data.incident_type),
            source_type=EventSourceType.external_system,
            source_detail={"source": data.source, "reporter_info": data.reporter_info},
            title=data.title,
            description=data.description,
            location=EventLocation(
                longitude=data.location.longitude,
                latitude=data.location.latitude
            ),
            address=data.address,
            priority=self._map_severity_to_priority(data.severity),
            estimated_victims=0,
            is_time_critical=data.severity == "critical",
            media_attachments=data.attachments,
        )
        
        # 调用EventService创建事件
        event_response = await self._event_service.create(event_create)
        
        # 广播事件通知
        await broadcast_event_update(scenario_id, "incident_received", {
            "event_id": str(event_response.id),
            "event_code": event_response.event_code,
            "incident_type": data.incident_type,
            "title": data.title,
            "location": data.location.model_dump(),
            "status": event_response.status.value,
        })
        
        logger.info(f"事件创建成功: event_id={event_response.id}, code={event_response.event_code}")
        
        return {
            "event_id": event_response.id,
            "event_code": event_response.event_code,
            "status": event_response.status.value,
            "message": "事件已接收并创建",
        }
    
    async def get_equipment_suggestion(
        self, 
        data: EquipmentSuggestionRequest
    ) -> EquipmentSuggestionResponse:
        """
        获取装备建议（AI功能）
        
        TODO P2: 接入AI装备推荐算法
        当前返回Mock数据
        """
        logger.info(f"获取装备建议: event_id={data.event_id}, type={data.incident_type}")
        
        # Mock数据 - 后续由AI模块实现
        return EquipmentSuggestionResponse(
            event_id=data.event_id,
            suggested_equipment=[
                EquipmentItem(
                    equipment_id=uuid4(),
                    equipment_name="生命探测仪",
                    equipment_type="detection",
                    quantity=2,
                    priority="high",
                    reason="用于搜索被困人员",
                ),
                EquipmentItem(
                    equipment_id=uuid4(),
                    equipment_name="液压剪切器",
                    equipment_type="rescue_tool",
                    quantity=1,
                    priority="high",
                    reason="用于破拆救援",
                ),
            ],
            suggested_vehicles=[
                {"vehicle_type": "rescue_truck", "quantity": 1, "reason": "运输救援装备"},
                {"vehicle_type": "ambulance", "quantity": 1, "reason": "伤员转运"},
            ],
            suggested_teams=[
                {"team_type": "search_rescue", "personnel": 6, "reason": "搜救作业"},
                {"team_type": "medical", "personnel": 2, "reason": "现场急救"},
            ],
            ai_confidence=0.85,
            reasoning="根据事件类型和预估受困人数，推荐以上装备配置（Mock数据）",
        )
    
    async def create_preparation_tasks(
        self, 
        scenario_id: UUID,
        event_id: UUID, 
        tasks: list[PreparationTask]
    ) -> list[dict[str, Any]]:
        """
        创建准备任务
        
        业务流程:
        1. 为每个准备任务调用TaskService创建记录
        2. 关联到指定事件
        3. 返回创建的任务列表
        """
        logger.info(f"创建准备任务: event_id={event_id}, count={len(tasks)}")
        
        created_tasks: list[dict[str, Any]] = []
        
        for task in tasks:
            # 准备任务无关联方案，scheme_id为None
            task_create = TaskCreate(
                scheme_id=None,
                scenario_id=scenario_id,
                event_id=event_id,
                task_type=self._map_prep_task_type(task.task_type),
                title=task.title,
                description=task.description,
                priority=TaskPriority.high,
                estimated_duration_minutes=task.deadline_minutes,
            )
            
            task_response = await self._task_service.create(task_create)
            
            created_tasks.append({
                "task_id": task_response.id,
                "task_code": task_response.task_code,
                "event_id": event_id,
                "task_type": task.task_type,
                "title": task.title,
                "status": task_response.status.value,
                "created_at": task_response.created_at.isoformat(),
            })
        
        logger.info(f"准备任务创建完成: count={len(created_tasks)}")
        return created_tasks
    
    async def complete_preparation_task(
        self,
        task_id: UUID,
        data: PreparationTaskComplete,
    ) -> dict[str, Any]:
        """
        提交准备任务完成状态
        
        业务流程:
        1. 调用TaskService.complete_direct完成任务
        2. 返回任务状态和完成详情
        """
        logger.info(f"准备任务完成: task_id={task_id}")
        
        completion_summary = data.notes or f"准备完成 - 人员: {data.personnel_onboard}, 燃油: {data.fuel_level}%"
        
        # 使用complete_direct直接完成任务（无需assignee）
        await self._task_service.complete_direct(
            task_id=task_id,
            completion_summary=completion_summary,
        )
        
        logger.info(f"准备任务完成: task_id={task_id}, status=completed")
        
        return {
            "task_id": task_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "completed_items": [item.model_dump() for item in data.completed_items] if data.completed_items else [],
            "personnel_onboard": data.personnel_onboard,
            "fuel_level": data.fuel_level,
        }
    
    async def issue_depart_command(
        self, 
        scenario_id: UUID, 
        data: DepartCommand
    ) -> dict[str, Any]:
        """
        发布出发指令
        
        业务流程:
        1. 更新队伍状态为deployed
        2. 更新车辆状态为deployed
        3. 广播出发指令
        4. 返回指令信息
        """
        logger.info(f"发布出发指令: event_id={data.event_id}, teams={len(data.team_ids)}, vehicles={len(data.vehicle_ids)}")
        
        # 创建一个临时任务ID用于部署（队伍部署需要关联任务）
        deployment_task_id = uuid4()
        
        # 更新队伍状态
        for team_id in data.team_ids:
            try:
                await self._team_service.update_status(team_id, TeamStatus.deployed, task_id=deployment_task_id)
                logger.info(f"队伍状态更新: team_id={team_id}, status=deployed")
            except NotFoundError:
                logger.warning(f"队伍不存在: team_id={team_id}")
            except ConflictError as e:
                logger.warning(f"队伍状态转换失败: team_id={team_id}, error={e}")
        
        # 更新车辆状态
        for vehicle_id in data.vehicle_ids:
            try:
                await self._vehicle_service.update_status(vehicle_id, VehicleStatus.deployed)
                logger.info(f"车辆状态更新: vehicle_id={vehicle_id}, status=deployed")
            except NotFoundError:
                logger.warning(f"车辆不存在: vehicle_id={vehicle_id}")
            except ConflictError as e:
                logger.warning(f"车辆状态转换失败: vehicle_id={vehicle_id}, error={e}")
        
        # 广播出发指令
        await broadcast_alert(scenario_id, "depart_command", {
            "event_id": str(data.event_id),
            "team_ids": [str(t) for t in data.team_ids],
            "vehicle_ids": [str(v) for v in data.vehicle_ids],
            "destination": data.destination.model_dump(),
            "departure_time": data.departure_time.isoformat() if data.departure_time else datetime.utcnow().isoformat(),
        })
        
        command_id = uuid4()
        logger.info(f"出发指令发布完成: command_id={command_id}")
        
        return {
            "command_id": command_id,
            "status": "issued",
            "teams_notified": len(data.team_ids),
            "vehicles_dispatched": len(data.vehicle_ids),
            "issued_at": datetime.utcnow().isoformat(),
        }
    
    # ========================================================================
    # 阶段2: 途中导航
    # ========================================================================
    
    async def plan_route(self, data: RouteRequest) -> RouteResponse:
        """
        规划路径
        
        调用VehicleRoutingPlanner计算最优路径。
        """
        from .route_planner import plan_route_vrp
        
        logger.info(f"规划路径: event_id={data.event_id}, vehicle_id={data.vehicle_id}")
        
        # 调用VRP规划
        response = plan_route_vrp(data)
        
        logger.info(
            f"路径规划完成: route_id={response.route_id}, "
            f"distance={response.total_distance_meters}m, "
            f"duration={response.total_duration_seconds}s"
        )
        
        return response
    
    async def switch_route(
        self, 
        route_id: UUID, 
        new_route_index: int
    ) -> dict[str, Any]:
        """
        切换备选路径
        
        TODO: 实现路径表操作
        当前返回简单响应
        """
        logger.info(f"切换路径: route_id={route_id}, new_index={new_route_index}")
        
        return {
            "route_id": route_id,
            "switched_to": new_route_index,
            "status": "active",
            "switched_at": datetime.utcnow().isoformat(),
        }
    
    async def get_risk_predictions(
        self, 
        event_id: UUID, 
        area: dict[str, float]
    ) -> list[RiskPrediction]:
        """
        获取风险预测（AI功能）
        
        TODO P2: 接入风险预测算法
        当前返回空列表
        """
        logger.info(f"获取风险预测: event_id={event_id}, area={area}")
        return []
    
    async def get_safe_points(
        self, 
        event_id: UUID, 
        route_id: UUID
    ) -> list[SafePoint]:
        """
        获取沿途安全点
        
        查询map_entities中entity_type为resettle_point或safety_area的实体
        """
        logger.info(f"获取安全点: event_id={event_id}, route_id={route_id}")
        
        # 获取事件关联的scenario_id
        event = await self._event_service.get_by_id(event_id)
        
        # 查询安全点实体（resettle_point和safety_area）
        entities = await self._entity_service.list(
            scenario_id=event.scenario_id,
            entity_types="resettle_point,safety_area",
        )
        
        # 转换为SafePoint响应
        safe_points: list[SafePoint] = []
        for entity in entities.items:
            # 从geometry中提取位置
            if entity.geometry.type == "Point":
                coords = entity.geometry.coordinates
                location = Location(longitude=coords[0], latitude=coords[1])
            else:
                # 对于polygon类型，取中心点
                coords = entity.geometry.coordinates
                if isinstance(coords[0], list) and isinstance(coords[0][0], list):
                    # Polygon: 取第一个环的第一个点
                    location = Location(longitude=coords[0][0][0], latitude=coords[0][0][1])
                else:
                    location = Location(longitude=coords[0], latitude=coords[1])
            
            safe_point = SafePoint(
                point_id=entity.id,
                name=entity.properties.get("name", f"安全点-{entity.id}"),
                location=location,
                point_type=entity.type.value if hasattr(entity.type, 'value') else str(entity.type),
                capacity=entity.properties.get("capacity"),
                facilities=entity.properties.get("facilities"),
                contact_info=entity.properties.get("contact"),
            )
            safe_points.append(safe_point)
        
        logger.info(f"查询到 {len(safe_points)} 个安全点")
        return safe_points
    
    async def confirm_safe_point(self, data: SafePointConfirm) -> dict[str, Any]:
        """确认安全点到达"""
        logger.info(f"确认安全点: point_id={data.point_id}")
        
        return {
            "point_id": data.point_id,
            "confirmed": True,
            "confirmed_at": datetime.utcnow().isoformat(),
            "confirmed_by": str(data.confirmed_by) if data.confirmed_by else None,
        }
    
    # ========================================================================
    # 阶段3: 现场指挥
    # ========================================================================
    
    async def get_command_post_recommendation(
        self, 
        event_id: UUID
    ) -> CommandPostRecommendation:
        """
        获取指挥所选址推荐（AI功能）
        
        TODO P2: 接入选址推荐算法
        当前返回Mock数据
        """
        logger.info(f"获取指挥所推荐: event_id={event_id}")
        
        return CommandPostRecommendation(
            event_id=event_id,
            recommended_locations=[
                {
                    "location": {"longitude": 116.4, "latitude": 39.9},
                    "score": 0.92,
                    "reasons": ["地势较高", "通信良好", "交通便利"],
                }
            ],
            factors_considered=["safety", "accessibility", "communication", "visibility"],
            ai_reasoning="综合考虑安全性、可达性、通信条件和视野范围（Mock数据）",
        )
    
    async def confirm_command_post(
        self, 
        scenario_id: UUID, 
        data: CommandPostConfirm
    ) -> dict[str, Any]:
        """
        确认指挥所位置
        
        业务流程:
        1. 调用EntityService创建指挥所实体
        2. 广播指挥所建立通知
        3. 返回指挥所信息
        """
        logger.info(f"确认指挥所: event_id={data.event_id}, name={data.name}")
        
        # 创建指挥所地图实体
        entity_create = MapEntityCreate(
            type=MapEntityType.command_post_candidate,  # 使用现有的枚举值
            layer_code="layer.command",  # 指挥图层
            geometry=GeoJsonGeometry(
                type="Point",
                coordinates=[data.location.longitude, data.location.latitude]
            ),
            properties={
                "name": data.name,
                "event_id": str(data.event_id),
                "established_at": data.established_at.isoformat() if data.established_at else datetime.utcnow().isoformat(),
            },
            source=EntitySource.manual,
            visible_on_map=True,
            scenario_id=scenario_id,
            event_id=data.event_id,
        )
        
        try:
            entity_response = await self._entity_service.create(entity_create)
            command_post_id = entity_response.id
            logger.info(f"指挥所实体创建成功: entity_id={command_post_id}")
        except Exception as e:
            logger.warning(f"指挥所实体创建失败: {e}，使用临时ID")
            command_post_id = uuid4()
        
        # 广播指挥所建立通知
        await broadcast_event_update(scenario_id, "command_post_established", {
            "event_id": str(data.event_id),
            "command_post_id": str(command_post_id),
            "location": data.location.model_dump(),
            "name": data.name,
        })
        
        return {
            "command_post_id": command_post_id,
            "event_id": data.event_id,
            "location": data.location.model_dump(),
            "name": data.name,
            "established_at": datetime.utcnow().isoformat(),
        }
    
    async def control_uav_cluster(self, data: UAVClusterControl) -> dict[str, Any]:
        """
        无人机集群控制
        
        根据命令类型批量更新设备状态
        """
        logger.info(f"无人机集群控制: command_type={data.command_type}, count={len(data.uav_ids)}")
        
        # 导入DeviceService
        from src.domains.resources.devices.service import DeviceService
        from src.domains.resources.devices.schemas import DeviceStatus
        
        device_service = DeviceService(self._db)
        
        # 根据命令类型映射设备状态
        status_map = {
            "deploy": DeviceStatus.deployed,
            "recall": DeviceStatus.available,
            "reposition": DeviceStatus.deployed,
            "search_pattern": DeviceStatus.deployed,
        }
        target_status = status_map.get(data.command_type, DeviceStatus.deployed)
        
        # 批量更新设备状态
        success_count = 0
        failed_ids: list[str] = []
        
        for uav_id in data.uav_ids:
            try:
                await device_service.update_status(uav_id, target_status)
                success_count += 1
                logger.info(f"设备状态更新: device_id={uav_id}, status={target_status.value}")
            except NotFoundError:
                logger.warning(f"设备不存在: device_id={uav_id}")
                failed_ids.append(str(uav_id))
            except Exception as e:
                logger.error(f"设备状态更新失败: device_id={uav_id}, error={e}")
                failed_ids.append(str(uav_id))
        
        command_id = uuid4()
        return {
            "command_id": command_id,
            "command_type": data.command_type,
            "uav_count": len(data.uav_ids),
            "success_count": success_count,
            "failed_ids": failed_ids,
            "status": "executing" if success_count > 0 else "failed",
            "issued_at": datetime.utcnow().isoformat(),
        }
    
    async def get_rescue_point_detections(
        self, 
        event_id: UUID
    ) -> list[RescuePointDetection]:
        """
        获取AI救援点识别结果（AI功能）
        
        TODO P2: 接入图像识别算法
        当前返回空列表
        """
        logger.info(f"获取救援点检测: event_id={event_id}")
        return []
    
    async def confirm_rescue_point_detection(
        self,
        scenario_id: UUID,
        data: RescuePointConfirm
    ) -> dict[str, Any]:
        """
        确认救援点识别结果
        
        业务流程:
        1. 如果确认且提供了必要信息，创建RescuePoint记录
        2. 关联detection_id
        3. 返回确认结果
        """
        logger.info(f"确认救援点检测: detection_id={data.detection_id}, confirmed={data.is_confirmed}")
        
        result: dict[str, Any] = {
            "detection_id": data.detection_id,
            "confirmed": data.is_confirmed,
            "confirmed_at": datetime.utcnow().isoformat(),
            "rescue_point_created": False,
        }
        
        if data.is_confirmed and data.event_id and data.location:
            # 创建救援点记录
            try:
                rescue_point = await self._rescue_point_repo.create(
                    scenario_id=scenario_id,
                    event_id=data.event_id,
                    name=data.name or f"检测点-{str(data.detection_id)[:8]}",
                    point_type=data.point_type or "trapped_person",
                    location_lng=data.location.longitude,
                    location_lat=data.location.latitude,
                    priority="high",  # AI检测的默认高优先级
                    estimated_victims=data.estimated_victims or 0,
                    detection_id=data.detection_id,
                    detection_source="ai_analysis",
                    notes=data.notes,
                )
                
                await self._db.commit()
                
                result["rescue_point_created"] = True
                result["rescue_point_id"] = str(rescue_point.id)
                logger.info(f"救援点创建成功: id={rescue_point.id}, detection_id={data.detection_id}")
                
            except Exception as e:
                logger.error(f"创建救援点失败: {e}")
                result["error"] = str(e)
        elif data.is_confirmed:
            logger.warning(f"确认检测但缺少必要信息: event_id={data.event_id}, location={data.location}")
            result["warning"] = "确认成功但未创建救援点（缺少event_id或location）"
        
        return result
    
    # ========================================================================
    # 阶段4: 救援作业
    # ========================================================================
    
    async def create_rescue_point(
        self,
        scenario_id: UUID,
        data: RescuePointCreate
    ) -> RescuePointResponse:
        """
        手动添加救援点
        
        业务流程:
        1. 调用RescuePointRepository创建记录
        2. 返回创建的救援点
        """
        logger.info(f"创建救援点: event_id={data.event_id}, name={data.name}")
        
        rescue_point = await self._rescue_point_repo.create(
            scenario_id=scenario_id,
            event_id=data.event_id,
            name=data.name,
            point_type=data.point_type,
            location_lng=data.location.longitude,
            location_lat=data.location.latitude,
            priority=data.priority,
            description=data.description,
            estimated_victims=data.estimated_victims,
            detection_source="manual",
            reported_by=data.reported_by,
        )
        
        await self._db.commit()
        
        logger.info(f"救援点创建成功: id={rescue_point.id}")
        return self._rescue_point_to_response(rescue_point)
    
    async def update_rescue_point(
        self, 
        point_id: UUID, 
        data: RescuePointUpdate
    ) -> RescuePointResponse:
        """
        更新救援点状态
        
        业务流程:
        1. 获取救援点
        2. 更新状态/救援人数
        3. 触发器自动记录进度
        4. 返回更新后的救援点
        """
        logger.info(f"更新救援点: point_id={point_id}")
        
        rescue_point = await self._rescue_point_repo.get_by_id(point_id)
        if not rescue_point:
            raise NotFoundError("RescuePoint", str(point_id))
        
        rescue_point = await self._rescue_point_repo.update(
            rescue_point=rescue_point,
            status=data.status,
            rescued_count=data.rescued_count,
            notes=data.notes,
        )
        
        await self._db.commit()
        
        logger.info(f"救援点更新成功: id={point_id}, status={data.status}")
        return self._rescue_point_to_response(rescue_point)
    
    async def get_coordination_overview(
        self, 
        event_id: UUID
    ) -> CoordinationTracking:
        """
        获取协同总览图
        
        业务流程:
        1. 查询事件关联的所有救援点
        2. 查询队伍当前位置（deployed状态）
        3. 查询车辆当前位置（deployed状态）
        4. 计算总体救援进度
        """
        logger.info(f"获取协同总览: event_id={event_id}")
        
        # 查询救援点
        rescue_points = await self._rescue_point_repo.list_by_event(event_id)
        rescue_point_responses = [self._rescue_point_to_response(rp) for rp in rescue_points]
        
        # 获取统计信息
        stats = await self._rescue_point_repo.get_statistics_by_event(event_id)
        
        # 查询deployed状态的队伍位置
        team_locations: list[dict[str, Any]] = []
        try:
            teams_result = await self._team_service.list(page=1, page_size=100, status="deployed")
            for team in teams_result.items:
                if team.current_location:
                    team_locations.append({
                        "id": str(team.id),
                        "name": team.name,
                        "code": team.code,
                        "location": {
                            "longitude": team.current_location.longitude,
                            "latitude": team.current_location.latitude,
                        },
                        "status": team.status.value if hasattr(team.status, 'value') else team.status,
                        "current_task_id": str(team.current_task_id) if team.current_task_id else None,
                    })
        except Exception as e:
            logger.warning(f"查询队伍位置失败: {e}")
        
        # 查询deployed状态的车辆位置
        vehicle_locations: list[dict[str, Any]] = []
        try:
            vehicles_result = await self._vehicle_service.list(page=1, page_size=100, status="deployed")
            for vehicle in vehicles_result.items:
                if vehicle.current_location:
                    vehicle_locations.append({
                        "id": str(vehicle.id),
                        "name": vehicle.name,
                        "code": vehicle.code,
                        "location": {
                            "longitude": vehicle.current_location.longitude,
                            "latitude": vehicle.current_location.latitude,
                        },
                        "status": vehicle.status.value if hasattr(vehicle.status, 'value') else vehicle.status,
                    })
        except Exception as e:
            logger.warning(f"查询车辆位置失败: {e}")
        
        logger.info(f"协同总览: {len(rescue_point_responses)} 救援点, {len(team_locations)} 队伍, {len(vehicle_locations)} 车辆")
        
        return CoordinationTracking(
            event_id=event_id,
            rescue_points=rescue_point_responses,
            team_locations=team_locations,
            vehicle_locations=vehicle_locations,
            total_rescued=stats["total_rescued"],
            total_remaining=stats["total_estimated_victims"] - stats["total_rescued"],
            overall_progress=stats["rescue_progress_percent"],
        )
    
    async def update_coordination(
        self, 
        scenario_id: UUID, 
        data: CoordinationUpdate
    ) -> dict[str, Any]:
        """
        更新协同状态
        
        业务流程:
        1. 根据entity_type更新对应实体
        2. 广播协同更新
        """
        logger.info(f"更新协同状态: event_id={data.event_id}, type={data.update_type}, entity_type={data.entity_type}")
        
        # 根据entity_type分发更新
        update_result: dict[str, Any] = {"entity_updated": False}
        
        try:
            if data.entity_type == "team":
                # 更新队伍位置
                if "location" in data.data:
                    from src.domains.resources.teams.schemas import TeamLocationUpdate
                    loc_data = data.data["location"]
                    location_update = TeamLocationUpdate(
                        longitude=loc_data["longitude"],
                        latitude=loc_data["latitude"],
                        heading=loc_data.get("heading"),
                    )
                    await self._team_service.update_location(data.entity_id, location_update)
                    update_result["entity_updated"] = True
                    
            elif data.entity_type == "vehicle":
                # 更新车辆位置
                if "location" in data.data:
                    from src.domains.resources.vehicles.schemas import VehicleLocationUpdate
                    loc_data = data.data["location"]
                    location_update = VehicleLocationUpdate(
                        longitude=loc_data["longitude"],
                        latitude=loc_data["latitude"],
                        heading=loc_data.get("heading"),
                        speed_kmh=loc_data.get("speed_kmh"),
                    )
                    await self._vehicle_service.update_location(data.entity_id, location_update)
                    update_result["entity_updated"] = True
                    
            elif data.entity_type == "rescue_point":
                # 更新救援点状态
                update_data = RescuePointUpdate(
                    status=data.data.get("status"),
                    rescued_count=data.data.get("rescued_count"),
                    notes=data.data.get("notes"),
                )
                await self.update_rescue_point(data.entity_id, update_data)
                update_result["entity_updated"] = True
                
        except NotFoundError as e:
            logger.warning(f"实体不存在: {e}")
            update_result["error"] = str(e)
        except Exception as e:
            logger.error(f"更新实体失败: {e}")
            update_result["error"] = str(e)
        
        # 广播协同更新
        await broadcast_event_update(scenario_id, "coordination_update", {
            "event_id": str(data.event_id),
            "update_type": data.update_type,
            "entity_id": str(data.entity_id),
            "entity_type": data.entity_type,
            "data": data.data,
        })
        
        update_id = uuid4()
        return {
            "update_id": update_id,
            "status": "processed",
            "entity_updated": update_result.get("entity_updated", False),
            "processed_at": datetime.utcnow().isoformat(),
        }
    
    # ========================================================================
    # 阶段5: 评估总结
    # ========================================================================
    
    async def generate_evaluation_report(
        self, 
        data: EvaluationReportRequest
    ) -> EvaluationReport:
        """
        生成评估报告（AI功能）
        
        TODO P2: 接入AI报告生成算法
        当前生成Mock数据并持久化到数据库
        """
        logger.info(f"生成评估报告: event_id={data.event_id}")
        
        # 获取事件信息以获取scenario_id
        event = await self._event_service.get_by_id(data.event_id)
        
        # 构造报告数据（AI生成的Mock数据）
        report_data = {
            "summary": {
                "event_type": "earthquake",
                "duration_hours": 4.5,
                "total_rescued": 12,
                "resources_deployed": {"teams": 3, "vehicles": 5},
            },
            "timeline": [
                {"time": "10:00", "event": "接警"},
                {"time": "10:15", "event": "队伍出发"},
                {"time": "10:45", "event": "抵达现场"},
                {"time": "14:30", "event": "救援完成"},
            ],
            "resource_usage": {
                "teams": [{"team_id": "...", "duration_hours": 4}],
                "vehicles": [{"vehicle_id": "...", "distance_km": 25}],
            },
            "rescue_results": {
                "total_rescued": 12,
                "casualties": 0,
                "rescue_points_cleared": 3,
            },
            "lessons_learned": [
                "需要增加通信设备数量",
                "建议提前部署无人机",
            ],
            "ai_analysis": "本次救援响应及时，资源配置合理（Mock数据）",
        }
        
        # 持久化报告（upsert：存在则更新，不存在则创建）
        report_model = await self._evaluation_report_repo.upsert(
            event_id=data.event_id,
            scenario_id=event.scenario_id,
            report_data=report_data,
            generated_by="ai_generated",
        )
        
        await self._db.commit()
        
        logger.info(f"评估报告已生成并保存: report_id={report_model.id}")
        
        return EvaluationReport(
            report_id=report_model.id,
            event_id=report_model.event_id,
            generated_at=report_model.generated_at,
            summary=report_data["summary"],
            timeline=report_data["timeline"],
            resource_usage=report_data["resource_usage"],
            rescue_results=report_data["rescue_results"],
            lessons_learned=report_data["lessons_learned"],
            ai_analysis=report_data["ai_analysis"],
        )
    
    async def get_evaluation_report(
        self, 
        event_id: UUID
    ) -> Optional[EvaluationReport]:
        """
        获取评估报告
        
        从数据库查询已生成的评估报告
        """
        logger.info(f"获取评估报告: event_id={event_id}")
        
        report = await self._evaluation_report_repo.get_by_event_id(event_id)
        if not report:
            return None
        
        # 从数据库模型转换为响应模型
        return EvaluationReport(
            report_id=report.id,
            event_id=report.event_id,
            generated_at=report.generated_at,
            summary=report.report_data.get("summary", {}),
            timeline=report.report_data.get("timeline", []),
            resource_usage=report.report_data.get("resource_usage", {}),
            rescue_results=report.report_data.get("rescue_results", {}),
            lessons_learned=report.report_data.get("lessons_learned"),
            ai_analysis=report.report_data.get("ai_analysis"),
        )
    
    # ========================================================================
    # 操作手册
    # ========================================================================
    
    async def get_manual_recommendations(
        self, 
        event_id: UUID
    ) -> list[ManualRecommendation]:
        """
        获取相关操作手册推荐
        
        根据事件信息（灾害类型、描述）调用RAG检索相关操作手册。
        """
        from .rag_client import search_manuals_by_event
        
        logger.info(f"获取手册推荐: event_id={event_id}")
        
        # 获取事件信息
        event = await self._event_service.get_by_id(event_id)
        
        # 调用RAG检索
        recommendations = search_manuals_by_event(
            event_id=event_id,
            disaster_type=event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
            description=event.description or "",
            limit=5,
        )
        
        logger.info(f"手册推荐完成: event_id={event_id}, count={len(recommendations)}")
        return recommendations
    
    async def search_manuals(
        self, 
        data: ManualSearchRequest
    ) -> list[ManualRecommendation]:
        """
        搜索操作手册
        
        根据查询文本调用RAG检索操作手册。
        """
        from .rag_client import search_manuals_by_query
        
        logger.info(f"搜索手册: query={data.query}")
        
        # 调用RAG检索
        recommendations = search_manuals_by_query(
            query=data.query,
            limit=data.limit,
            disaster_type=data.disaster_type,
        )
        
        logger.info(f"手册搜索完成: query={data.query}, count={len(recommendations)}")
        return recommendations
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _map_incident_type(self, incident_type: str) -> EventType:
        """映射事件类型"""
        mapping = {
            "earthquake": EventType.earthquake_secondary,
            "fire": EventType.fire,
            "flood": EventType.flood,
            "landslide": EventType.landslide,
            "building_collapse": EventType.building_collapse,
            "trapped_person": EventType.trapped_person,
            "hazmat_leak": EventType.hazmat_leak,
        }
        return mapping.get(incident_type, EventType.other)
    
    def _map_severity_to_priority(self, severity: str) -> EventPriority:
        """映射严重程度到优先级"""
        mapping = {
            "critical": EventPriority.critical,
            "high": EventPriority.high,
            "medium": EventPriority.medium,
            "low": EventPriority.low,
        }
        return mapping.get(severity, EventPriority.medium)
    
    def _map_prep_task_type(self, task_type: str) -> TaskType:
        """映射准备任务类型"""
        mapping = {
            "equipment_check": TaskType.supply,
            "vehicle_prep": TaskType.transport,
            "team_assembly": TaskType.other,
            "briefing": TaskType.communication,
        }
        return mapping.get(task_type, TaskType.other)
    
    def _rescue_point_to_response(self, rescue_point: RescuePoint) -> RescuePointResponse:
        """将RescuePoint ORM转换为响应模型"""
        # 解析位置
        point = wkb.loads(bytes(rescue_point.location.data))
        location = Location(longitude=point.x, latitude=point.y)
        
        # 获取已指派队伍ID
        assigned_teams = [a.team_id for a in rescue_point.team_assignments]
        
        return RescuePointResponse(
            id=rescue_point.id,
            event_id=rescue_point.event_id,
            name=rescue_point.name,
            location=location,
            point_type=rescue_point.point_type,
            priority=rescue_point.priority,
            status=rescue_point.status,
            estimated_victims=rescue_point.estimated_victims,
            rescued_count=rescue_point.rescued_count,
            remaining_victims=rescue_point.estimated_victims - rescue_point.rescued_count,
            assigned_teams=assigned_teams,
            created_at=rescue_point.created_at,
            updated_at=rescue_point.updated_at,
        )
