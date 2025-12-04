"""
规划路径业务逻辑层

整合路径规划、存储、风险检测、绕行方案生成
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import Point, RouteResult
from .planned_route_repository import PlannedRouteRepository, PlannedRouteRecord
from .unified_service import UnifiedRoutePlanningService
from .risk_detection import RiskDetectionService, RiskAreaInfo
from .alternative_routes import AlternativeRoutesService, AlternativeRoute

from src.domains.map_entities.service import EntityService
from src.domains.map_entities.schemas import EntityCreate, GeoJsonGeometry, EntityType, EntitySource

logger = logging.getLogger(__name__)


class PlannedRouteService:
    """
    规划路径服务
    
    整合路径规划、存储、风险检测功能
    """
    
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PlannedRouteRepository(db)
        self._unified_service = UnifiedRoutePlanningService(db)
        self._risk_service = RiskDetectionService(db)
        self._alt_service = AlternativeRoutesService(db)
        self._entity_service = EntityService(db)
    
    async def plan_and_save(
        self,
        device_id: UUID,
        origin: Point,
        destination: Point,
        task_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None,
        vehicle_id: Optional[UUID] = None,
        scenario_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        规划路径并存储到数据库
        
        Args:
            device_id: 设备ID（用于确定规划类型）
            origin: 起点
            destination: 终点
            task_id: 关联任务ID（task_requirements_v2）
            team_id: 关联队伍ID
            vehicle_id: 关联车辆ID
            scenario_id: 场景ID（用于风险检测）
            
        Returns:
            包含路径信息和风险检测结果
        """
        logger.info(
            f"规划并存储路径: device_id={device_id}, "
            f"task_id={task_id}, team_id={team_id}"
        )
        
        # 1. 调用统一路径规划服务
        route_result = await self._unified_service.plan_route(
            device_id=device_id,
            origin=origin,
            destination=destination,
        )
        
        if not route_result.success:
            logger.error(f"路径规划失败: {route_result.error_message}")
            return {
                "success": False,
                "error": route_result.error_message,
            }
        
        # 2. 存储路径到数据库
        estimated_time_minutes = int(route_result.total_duration_s / 60)
        
        route_id = await self._repo.create(
            task_id=task_id,
            vehicle_id=vehicle_id,
            team_id=team_id,
            polyline=route_result.polyline,
            total_distance_m=route_result.total_distance_m,
            estimated_time_minutes=estimated_time_minutes,
            start_location=origin,
            end_location=destination,
            risk_level=1,
            status="active",
            properties={
                "source": route_result.source,
                "device_id": str(device_id),
            },
        )
        
        logger.info(f"路径已存储: route_id={route_id}")
        
        # 3. 创建 entity 记录（用于前端 getEntityList 同步渲染）
        try:
            coordinates = [[p.lon, p.lat] for p in route_result.polyline]
            team_name = f"队伍{str(team_id)[:8]}" if team_id else "未知队伍"
            
            entity_create = EntityCreate(
                type=EntityType.planned_route,
                layer_code="layer.path",
                geometry=GeoJsonGeometry(
                    type="LineString",
                    coordinates=coordinates,
                ),
                properties={
                    "name": f"救援路径-{team_name}",
                    "type": "rescue",
                    "isSelect": "1",
                    "deviceType": "car",
                    "routeType": "rescue",
                    "task_id": str(task_id) if task_id else None,
                    "team_id": str(team_id) if team_id else None,
                    "distance_m": route_result.total_distance_m,
                },
                source=EntitySource.system,
                visible_on_map=True,
                scenario_id=scenario_id,
            )
            await self._entity_service.create(entity_create)
            logger.info(f"路径实体已创建: route_id={route_id}")
        except Exception as entity_err:
            logger.warning(f"创建路径实体失败（不影响路径存储）: {entity_err}")
        
        # 4. 风险检测
        risk_areas: List[RiskAreaInfo] = []
        if route_result.polyline:
            risk_areas = await self._risk_service.detect_risk_areas(
                polyline=route_result.polyline,
            )
            
            # 更新风险等级
            if risk_areas:
                max_risk = max(ra.risk_level for ra in risk_areas)
                await self._repo.update_risk_level(route_id, max_risk)
                logger.info(f"路径风险等级更新: route_id={route_id}, risk_level={max_risk}")
        
        return {
            "success": True,
            "route_id": str(route_id),
            "route": {
                "source": route_result.source,
                "total_distance_m": route_result.total_distance_m,
                "total_duration_s": route_result.total_duration_s,
                "polyline": [{"lon": p.lon, "lat": p.lat} for p in route_result.polyline],
            },
            "has_risk": len(risk_areas) > 0,
            "risk_areas": [
                {
                    "id": str(ra.id),
                    "name": ra.name,
                    "risk_level": ra.risk_level,
                    "passage_status": ra.passage_status,
                }
                for ra in risk_areas
            ],
        }
    
    async def generate_and_save_alternatives(
        self,
        task_id: UUID,
        origin: Point,
        destination: Point,
        risk_area_ids: List[UUID],
        team_id: Optional[UUID] = None,
        vehicle_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        生成绕行方案并存储到数据库
        
        Args:
            task_id: 任务ID
            origin: 起点
            destination: 终点
            risk_area_ids: 需要避让的风险区域ID列表
            team_id: 队伍ID
            vehicle_id: 车辆ID
            
        Returns:
            包含绕行方案信息
        """
        logger.info(
            f"生成绕行方案: task_id={task_id}, "
            f"避让区域数={len(risk_area_ids)}"
        )
        
        # 1. 生成绕行方案
        alternatives = await self._alt_service.generate_alternatives(
            origin=origin,
            destination=destination,
            risk_area_ids=risk_area_ids,
        )
        
        if not alternatives:
            logger.warning("未能生成绕行方案")
            return {
                "success": False,
                "error": "未能生成绕行方案",
                "alternatives": [],
            }
        
        # 2. 存储每个绕行方案到数据库
        saved_routes = []
        for alt in alternatives:
            estimated_time_minutes = int(alt.duration_s / 60)
            
            route_id = await self._repo.create(
                task_id=task_id,
                vehicle_id=vehicle_id,
                team_id=team_id,
                polyline=alt.polyline,
                total_distance_m=alt.distance_m,
                estimated_time_minutes=estimated_time_minutes,
                status="alternative",
                properties={
                    "strategy": alt.strategy,
                    "strategy_name": alt.strategy_name,
                    "description": alt.description,
                },
            )
            
            saved_routes.append({
                "route_id": str(route_id),
                "strategy": alt.strategy,
                "strategy_name": alt.strategy_name,
                "distance_m": alt.distance_m,
                "duration_s": alt.duration_s,
                "description": alt.description,
                "polyline": [{"lon": p.lon, "lat": p.lat} for p in alt.polyline],
            })
            
            logger.info(f"绕行方案已存储: route_id={route_id}, strategy={alt.strategy}")
        
        # 3. 更新任务的备选路径数
        # 这里可以通过 properties 记录或其他方式
        
        return {
            "success": True,
            "alternatives": saved_routes,
            "alternative_count": len(saved_routes),
        }
    
    async def confirm_route(
        self,
        route_id: UUID,
        task_id: UUID,
    ) -> Dict[str, Any]:
        """
        确认使用某条路径
        
        将选中的路径设为 active，原有 active 路径设为 replaced
        
        Args:
            route_id: 选中的路径ID
            task_id: 任务ID
            
        Returns:
            确认结果
        """
        logger.info(f"确认路径: route_id={route_id}, task_id={task_id}")
        
        # 1. 获取选中的路径
        selected_route = await self._repo.get_by_id(route_id)
        if not selected_route:
            return {
                "success": False,
                "error": "路径不存在",
            }
        
        # 2. 将任务的所有 active 路径设为 replaced
        active_routes = await self._repo.get_by_task_id(task_id, status="active")
        for route in active_routes:
            if route.id != route_id:
                await self._repo.update_status(route.id, "replaced")
        
        # 3. 将选中的路径设为 active
        await self._repo.update_status(route_id, "active")
        
        # 4. 将其他 alternative 路径设为 cancelled
        alt_routes = await self._repo.get_by_task_id(task_id, status="alternative")
        for route in alt_routes:
            if route.id != route_id:
                await self._repo.update_status(route.id, "cancelled")
        
        return {
            "success": True,
            "route_id": str(route_id),
            "message": "路径已确认",
        }
    
    async def get_routes_by_task(
        self,
        task_id: UUID,
        include_alternatives: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取任务的所有路径
        
        Args:
            task_id: 任务ID
            include_alternatives: 是否包含备选路径
            
        Returns:
            路径列表
        """
        routes = await self._repo.get_by_task_id(task_id)
        
        result = []
        for route in routes:
            if not include_alternatives and route.status == "alternative":
                continue
            
            result.append(self._route_to_dict(route))
        
        return result
    
    async def get_active_route(self, task_id: UUID) -> Optional[Dict[str, Any]]:
        """获取任务的当前活跃路径"""
        routes = await self._repo.get_by_task_id(task_id, status="active")
        if not routes:
            return None
        return self._route_to_dict(routes[0])
    
    @staticmethod
    def _route_to_dict(route: PlannedRouteRecord) -> Dict[str, Any]:
        """将路径记录转换为字典"""
        return {
            "route_id": str(route.id),
            "task_id": str(route.task_id) if route.task_id else None,
            "vehicle_id": str(route.vehicle_id) if route.vehicle_id else None,
            "team_id": str(route.team_id) if route.team_id else None,
            "total_distance_m": route.total_distance_m,
            "estimated_time_minutes": route.estimated_time_minutes,
            "risk_level": route.risk_level,
            "status": route.status,
            "planned_at": route.planned_at.isoformat() if route.planned_at else None,
            "properties": route.properties,
            "polyline": [{"lon": p.lon, "lat": p.lat} for p in route.polyline],
        }
