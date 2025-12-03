"""
救援队伍调度服务

整合队伍管理、路径规划、移动仿真，提供一站式队伍调度能力。
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from shapely import wkb

from src.core.exceptions import NotFoundError, ValidationError
from src.core.coord_transform import wgs84_to_gcj02, gcj02_to_wgs84
from src.domains.resources.teams.service import TeamService
from src.domains.resources.teams.schemas import TeamResponse
from src.domains.routing.service import RoutePlanningService
from src.domains.routing.schemas import Point as RoutingPoint, RouteResult
from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import (
    EntityCreate, EntityType, EntitySource, GeoJsonGeometry
)
from src.planning.algorithms.routing import (
    DatabaseRouteEngine,
    load_vehicle_capability,
    get_team_primary_vehicle,
    Point as InternalPoint,
    VehicleCapability,
)
from .schemas import (
    TeamDispatchRequest, TeamDispatchResponse, RouteInfo,
    MovementStartRequest, EntityType as MovementEntityType, MovementState,
)
from .service import get_movement_manager


# 配置独立日志文件
def _setup_logger() -> logging.Logger:
    """配置队伍调度专用日志，输出到 logs/team_dispatch.log"""
    log = logging.getLogger("team_dispatch")
    if log.handlers:
        return log
    
    log.setLevel(logging.DEBUG)
    log.propagate = True  # 同时输出到控制台
    
    # 确保日志目录存在
    log_dir = os.path.join(os.path.dirname(__file__), "../../../logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "team_dispatch.log")
    
    # 文件处理器：按大小轮转，最多保留5个文件
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    log.addHandler(file_handler)
    
    log.info(f"===== 队伍调度日志初始化，文件: {log_file} =====")
    return log

logger = _setup_logger()


class TeamDispatchService:
    """
    救援队伍调度服务
    
    职责：
    1. 获取队伍当前位置
    2. 调用路径规划获取行动路径
    3. 确保地图实体存在
    4. 启动移动仿真
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._team_service = TeamService(db)
        self._routing_service = RoutePlanningService(db)
        self._entity_service = EntityService(db)
    
    async def dispatch_team(
        self,
        team_id: UUID,
        request: TeamDispatchRequest,
    ) -> TeamDispatchResponse:
        """
        调度救援队伍到目标位置
        
        Args:
            team_id: 队伍ID
            request: 调度请求（目标位置、停靠点等）
            
        Returns:
            调度响应（会话ID、路径信息等）
            
        Raises:
            NotFoundError: 队伍不存在
            ValidationError: 队伍没有位置信息或路径规划失败
        """
        logger.info(
            f"开始调度队伍: team_id={team_id}, destination={request.destination}, "
            f"use_internal_routing={request.use_internal_routing}"
        )
        
        # 1. 获取队伍信息
        team = await self._team_service.get_by_id(team_id)
        logger.info(f"获取队伍成功: name={team.name}, status={team.status}")
        
        # 2. 获取队伍当前位置（数据库存的是WGS84坐标）
        origin_wgs = await self._get_team_location(team_id)
        logger.info(f"队伍当前位置(WGS84): lon={origin_wgs.lon}, lat={origin_wgs.lat}")
        
        # 3. 路径规划（根据配置选择高德API或内部A*）
        if request.use_internal_routing:
            route_result, route_source = await self._plan_route_internal(
                team_id=team_id,
                origin_wgs=origin_wgs,
                destination_gcj=request.destination,
                scenario_id=request.scenario_id,
            )
        else:
            route_result, route_source = await self._plan_route_amap(
                origin_wgs=origin_wgs,
                destination_gcj=request.destination,
            )
        
        logger.info(
            f"路径规划成功: distance={route_result.total_distance_m:.0f}m, "
            f"duration={route_result.total_duration_s:.0f}s, "
            f"source={route_source}, points={len(route_result.polyline)}"
        )
        
        # 4. 获取或创建地图实体（使用GCJ02坐标，因为前端是高德地图）
        origin_gcj = wgs84_to_gcj02(origin_wgs.lon, origin_wgs.lat)
        origin_gcj_point = RoutingPoint(lon=origin_gcj[0], lat=origin_gcj[1])
        entity_id = await self._ensure_map_entity(team, origin_gcj_point, request.scenario_id)
        logger.info(f"地图实体ID: {entity_id}")
        
        # 5. 构建路径数组
        route_points = self._build_route_points(route_result)
        
        # 6. 启动移动仿真
        movement_request = MovementStartRequest(
            entity_id=entity_id,
            entity_type=MovementEntityType.TEAM,
            resource_id=team_id,
            route=route_points,
            speed_mps=request.speed_mps,
            waypoints=request.waypoints,
        )
        
        manager = await get_movement_manager()
        movement_response = await manager.start_movement(movement_request, self._db)
        
        logger.info(
            f"移动仿真启动成功: session_id={movement_response.session_id}, "
            f"speed={movement_response.speed_mps:.2f}m/s"
        )
        
        # 7. 构建响应
        route_info = RouteInfo(
            distance_m=route_result.total_distance_m,
            duration_s=route_result.total_duration_s,
            source=route_source,
            point_count=len(route_result.polyline),
        )
        
        return TeamDispatchResponse(
            session_id=movement_response.session_id,
            team_id=team_id,
            team_name=team.name,
            entity_id=entity_id,
            route_info=route_info,
            state=movement_response.state,
            estimated_duration_s=movement_response.estimated_duration_s,
            speed_mps=movement_response.speed_mps,
        )
    
    async def _get_team_location(self, team_id: UUID) -> RoutingPoint:
        """
        获取队伍当前位置
        
        优先使用 current_location（实时位置），否则使用 base_location（驻地）
        """
        from src.domains.resources.teams.models import Team
        from sqlalchemy import select
        
        result = await self._db.execute(
            select(Team.current_location, Team.base_location)
            .where(Team.id == team_id)
        )
        row = result.first()
        
        if not row:
            raise NotFoundError("Team", str(team_id))
        
        current_loc, base_loc = row
        
        # 优先使用实时位置
        location_data = current_loc or base_loc
        
        if not location_data:
            raise ValidationError(
                error_code="TD4002",
                message="队伍没有位置信息（current_location 和 base_location 均为空）"
            )
        
        # 解析 Geography 类型
        try:
            point = wkb.loads(bytes(location_data.data))
            return RoutingPoint(lon=point.x, lat=point.y)
        except Exception as e:
            logger.error(f"解析队伍位置失败: {e}")
            raise ValidationError(
                error_code="TD4003",
                message=f"解析队伍位置失败: {e}"
            )
    
    async def _ensure_map_entity(
        self,
        team: TeamResponse,
        location: RoutingPoint,
        scenario_id: Optional[UUID],
    ) -> UUID:
        """
        确保队伍对应的地图实体存在
        
        使用确定性UUID生成策略：uuid5(NAMESPACE_DNS, "team-entity-{team_id}")
        """
        # 生成确定性实体ID
        entity_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"team-entity-{team.id}")
        
        # 检查实体是否已存在
        existing_entity = await self._entity_service._entity_repo.get_by_id(entity_id)
        
        if existing_entity:
            # 更新位置
            from src.domains.map_entities.schemas import EntityUpdate, Location
            await self._entity_service.update_location(
                entity_id,
                type('EntityLocationUpdate', (), {
                    'location': Location(longitude=location.lon, latitude=location.lat),
                    'speed_kmh': None,
                    'heading': None,
                })()
            )
            logger.debug(f"更新已有地图实体位置: entity_id={entity_id}")
            return entity_id
        
        # 创建新实体
        entity_props = {
            "team_id": str(team.id),
            "name": team.name,
            "team_type": team.team_type.value if hasattr(team.team_type, 'value') else str(team.team_type),
            "status": team.status.value if hasattr(team.status, 'value') else str(team.status),
            "contact": team.contact_person or "",
            "phone": team.contact_phone or "",
        }
        
        entity_data = EntityCreate(
            type=EntityType.rescue_team,
            layer_code="layer.team",
            geometry=GeoJsonGeometry(
                type="Point",
                coordinates=[location.lon, location.lat]
            ),
            properties=entity_props,
            source=EntitySource.system,
            visible_on_map=True,
            is_dynamic=True,
            scenario_id=scenario_id,
        )
        
        # 创建实体（注意：EntityRepository.create 会生成新ID，这里我们需要手动指定）
        from src.domains.map_entities.models import Entity
        from geoalchemy2.functions import ST_GeomFromGeoJSON
        import json
        
        geojson_str = json.dumps({
            "type": "Point",
            "coordinates": [location.lon, location.lat]
        })
        
        entity = Entity(
            id=entity_id,
            type=EntityType.rescue_team.value,
            layer_code="layer.team",
            geometry=ST_GeomFromGeoJSON(geojson_str),
            properties=entity_props,
            source=EntitySource.system.value,
            visible_on_map=True,
            is_dynamic=True,
            scenario_id=scenario_id,
        )
        
        self._db.add(entity)
        await self._db.flush()
        
        logger.info(f"创建地图实体: entity_id={entity_id}, team_name={team.name}")
        return entity_id
    
    def _build_route_points(self, route_result: RouteResult) -> list[list[float]]:
        """
        将路径规划结果转换为移动仿真需要的格式
        
        RouteResult.polyline: List[Point] -> [[lng, lat], ...]
        """
        if route_result.polyline:
            return [[p.lon, p.lat] for p in route_result.polyline]
        
        # 如果没有 polyline，从 segments 构建
        points: list[list[float]] = []
        for segment in route_result.segments:
            if not points or points[-1] != [segment.from_point.lon, segment.from_point.lat]:
                points.append([segment.from_point.lon, segment.from_point.lat])
            points.append([segment.to_point.lon, segment.to_point.lat])
        
        # 至少需要起点和终点
        if len(points) < 2:
            points = [
                [route_result.origin.lon, route_result.origin.lat],
                [route_result.destination.lon, route_result.destination.lat],
            ]
        
        return points
    
    async def _plan_route_amap(
        self,
        origin_wgs: RoutingPoint,
        destination_gcj: list[float],
    ) -> tuple[RouteResult, str]:
        """
        使用高德API进行路径规划
        
        Args:
            origin_wgs: 起点（WGS84坐标）
            destination_gcj: 目标位置 [lng, lat]（GCJ02坐标）
            
        Returns:
            (RouteResult, source) 路径结果和来源标识
        """
        # 起点从WGS84转GCJ02（高德API使用GCJ02）
        origin_gcj = wgs84_to_gcj02(origin_wgs.lon, origin_wgs.lat)
        origin = RoutingPoint(lon=origin_gcj[0], lat=origin_gcj[1])
        destination = RoutingPoint(lon=destination_gcj[0], lat=destination_gcj[1])
        
        route_result = await self._routing_service.plan_route(origin, destination)
        
        if not route_result.success:
            logger.error(f"高德路径规划失败: {route_result.error_message}")
            raise ValidationError(
                error_code="TD4001",
                message=f"路径规划失败: {route_result.error_message}"
            )
        
        return route_result, route_result.source
    
    async def _plan_route_internal(
        self,
        team_id: UUID,
        origin_wgs: RoutingPoint,
        destination_gcj: list[float],
        scenario_id: Optional[UUID],
    ) -> tuple[RouteResult, str]:
        """
        使用内部A*引擎进行路径规划（基于数据库路网，支持避障）
        
        坐标转换流程：
        1. 前端输入 destination_gcj (GCJ02) → 转 WGS84 → 数据库规划
        2. 数据库输出 WGS84 → 转 GCJ02 → 返回前端显示
        
        Args:
            team_id: 队伍ID（用于获取车辆能力）
            origin_wgs: 起点（WGS84坐标，数据库原始坐标）
            destination_gcj: 目标位置 [lng, lat]（GCJ02坐标）
            scenario_id: 想定ID（用于查询灾害避障）
            
        Returns:
            (RouteResult, source) 路径结果和来源标识
        """
        # 1. 目标点从GCJ02转WGS84
        dest_wgs = gcj02_to_wgs84(destination_gcj[0], destination_gcj[1])
        logger.debug(f"坐标转换: GCJ02({destination_gcj}) → WGS84({dest_wgs})")
        
        # 2. 获取队伍的主力车辆能力参数
        vehicle_id = await get_team_primary_vehicle(self._db, team_id)
        if not vehicle_id:
            logger.warning(f"队伍 {team_id} 没有关联车辆，使用默认能力参数")
            vehicle_cap = self._get_default_vehicle_capability()
        else:
            vehicle_cap = await load_vehicle_capability(self._db, vehicle_id)
            if not vehicle_cap:
                logger.warning(f"车辆 {vehicle_id} 能力参数加载失败，使用默认参数")
                vehicle_cap = self._get_default_vehicle_capability()
        
        logger.info(f"车辆能力: code={vehicle_cap.vehicle_code}, speed={vehicle_cap.max_speed_kmh}km/h")
        
        # 3. 调用内部A*引擎
        engine = DatabaseRouteEngine(self._db)
        try:
            internal_result = await engine.plan_route(
                start=InternalPoint(lon=origin_wgs.lon, lat=origin_wgs.lat),
                end=InternalPoint(lon=dest_wgs[0], lat=dest_wgs[1]),
                vehicle=vehicle_cap,
                scenario_id=scenario_id,
                search_radius_km=150.0,
            )
        except Exception as e:
            logger.error(f"内部A*路径规划失败: {e}")
            raise ValidationError(
                error_code="TD4004",
                message=f"内部路径规划失败: {e}"
            )
        
        # 4. 将结果路径点从WGS84转GCJ02
        gcj02_points = []
        for p in internal_result.path_points:
            gcj_coord = wgs84_to_gcj02(p.lon, p.lat)
            gcj02_points.append(RoutingPoint(lon=gcj_coord[0], lat=gcj_coord[1]))
        
        logger.info(f"内部A*规划完成: 原始点={len(internal_result.path_points)}, 转换后={len(gcj02_points)}")
        
        # 5. 构建兼容的RouteResult
        route_result = RouteResult(
            source="internal_astar",
            success=True,
            origin=RoutingPoint(lon=origin_wgs.lon, lat=origin_wgs.lat),
            destination=RoutingPoint(lon=dest_wgs[0], lat=dest_wgs[1]),
            total_distance_m=internal_result.distance_m,
            total_duration_s=internal_result.duration_seconds,
            polyline=gcj02_points,
        )
        
        return route_result, "internal_astar"
    
    def _get_default_vehicle_capability(self) -> VehicleCapability:
        """获取默认车辆能力参数"""
        return VehicleCapability(
            vehicle_id=uuid.uuid4(),
            vehicle_code="default",
            max_speed_kmh=60,
            is_all_terrain=False,
            terrain_capabilities=["paved", "gravel"],
            terrain_speed_factors={},
            max_gradient_percent=30,
            max_wading_depth_m=0.3,
            width_m=2.5,
            height_m=2.5,
            total_weight_kg=5000,
        )
