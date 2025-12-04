"""
风险区域业务逻辑层

功能：
- 风险区域 CRUD 操作
- 风险区域变更实时通知（WebSocket 广播）
- 受影响路线空间查询
- 集成 early_warning 智能体生成精准预警
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.stomp.broker import stomp_broker
from .repository import RiskAreaRepository
from .schemas import (
    RiskAreaCreateRequest,
    RiskAreaUpdateRequest,
    PassageStatusUpdateRequest,
    RiskAreaResponse,
    RiskAreaListResponse,
)


# 风险区域类型到灾害类型的映射
AREA_TYPE_TO_DISASTER_TYPE = {
    "fire": "fire",
    "flooded": "flood",
    "flood": "flood",
    "contaminated": "chemical",
    "landslide": "landslide",
    "seismic_red": "earthquake",
    "seismic_orange": "earthquake",
    "seismic_yellow": "earthquake",
    # 其他类型默认不触发 early_warning（仅广播）
}


logger = logging.getLogger(__name__)


class RiskAreaService:
    """风险区域服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = RiskAreaRepository(db)

    async def create(self, request: RiskAreaCreateRequest) -> RiskAreaResponse:
        """创建风险区域"""
        data = await self.repo.create(request)
        response = RiskAreaResponse(**data)
        
        # 触发风险区域变更通知
        await self._notify_risk_area_change(
            risk_area=response,
            change_type="created",
        )
        return response

    async def get_by_id(self, area_id: UUID) -> Optional[RiskAreaResponse]:
        """根据ID获取风险区域"""
        data = await self.repo.get_by_id(area_id)
        if not data:
            return None
        return RiskAreaResponse(**data)

    async def list_by_scenario(
        self,
        scenario_id: Optional[UUID] = None,
        area_type: Optional[str] = None,
        min_risk_level: Optional[int] = None,
        passage_status: Optional[str] = None,
    ) -> RiskAreaListResponse:
        """获取风险区域列表，scenario_id 为 None 时返回所有数据"""
        items = await self.repo.list_by_scenario(
            scenario_id=scenario_id,
            area_type=area_type,
            min_risk_level=min_risk_level,
            passage_status=passage_status,
        )
        return RiskAreaListResponse(
            items=[RiskAreaResponse(**item) for item in items],
            total=len(items),
        )

    async def update(
        self,
        area_id: UUID,
        request: RiskAreaUpdateRequest,
    ) -> Optional[RiskAreaResponse]:
        """更新风险区域"""
        # 先获取旧数据，用于检测变化
        old_data = await self.repo.get_by_id(area_id)
        if not old_data:
            return None
        
        data = await self.repo.update(area_id, request)
        if not data:
            return None
        response = RiskAreaResponse(**data)
        
        # 检查是否需要通知（risk_level 或 passage_status 变化）
        if self._should_notify_change(old_data, response):
            await self._notify_risk_area_change(
                risk_area=response,
                change_type="updated",
                old_risk_level=old_data.get("risk_level"),
            )
        return response

    async def update_passage_status(
        self,
        area_id: UUID,
        request: PassageStatusUpdateRequest,
    ) -> Optional[RiskAreaResponse]:
        """更新通行状态"""
        # 先获取旧数据
        old_data = await self.repo.get_by_id(area_id)
        if not old_data:
            return None
        
        data = await self.repo.update_passage_status(area_id, request)
        if not data:
            return None
        response = RiskAreaResponse(**data)
        
        # 通行状态变更时触发通知，包含不可通行原因
        old_status = old_data.get("passage_status")
        if old_status != response.passage_status:
            await self._notify_passage_status_change(
                risk_area=response,
                old_status=old_status,
                new_status=response.passage_status,
                reason=request.reason,
            )
        return response

    async def delete(self, area_id: UUID) -> bool:
        """删除风险区域"""
        return await self.repo.delete(area_id)

    # =========================================================================
    # 风险区域变更通知相关方法
    # =========================================================================

    def _should_notify_change(self, old: dict, new: RiskAreaResponse) -> bool:
        """
        判断是否需要发送变更通知
        
        只有当 risk_level 或 passage_status 发生变化时才触发通知，
        避免对无关属性更新（如 name、description）产生噪音。
        """
        if old.get("risk_level") != new.risk_level:
            return True
        if old.get("passage_status") != new.passage_status:
            return True
        return False

    async def _notify_risk_area_change(
        self,
        risk_area: RiskAreaResponse,
        change_type: str,
        old_risk_level: Optional[int] = None,
    ) -> None:
        """
        触发风险区域变更通知
        
        两层通知机制：
        1. WebSocket 广播：通知所有前端客户端（地图刷新、状态更新）
        2. early_warning 预警：精准通知受影响的指挥员/队长（需要决策响应）
        
        Args:
            risk_area: 风险区域响应对象
            change_type: 变更类型 ("created" | "updated")
            old_risk_level: 旧的风险等级（仅 updated 时传入）
        """
        if risk_area.scenario_id is None:
            logger.warning(
                f"[风险区域通知] scenario_id 为空，跳过: risk_area_id={risk_area.id}"
            )
            return
        
        try:
            # 1. 判断是否需要指挥决策
            requires_decision = self._requires_commander_decision(
                risk_area.risk_level,
                risk_area.passage_status,
            )
            
            # 2. 查询受影响的活动路线
            affected_routes = await self._find_affected_routes(risk_area)
            
            # 2.5 查询正在移动车辆的剩余路径是否穿过风险区域
            affected_moving_entities = await self._find_affected_moving_entities(risk_area)
            
            # 3. 生成可用决策选项
            available_actions = self._get_available_actions(risk_area.passage_status)
            
            # 3.5 使用 LLM 生成风险描述和建议（高风险时）
            llm_advice = None
            if risk_area.risk_level >= 5 and (affected_routes or affected_moving_entities):
                llm_advice = await self._generate_llm_risk_advice(
                    risk_area=risk_area,
                    affected_routes=affected_routes,
                    affected_moving_entities=affected_moving_entities,
                )
            
            # 4. 构建通知 payload（匹配前端 route-warning-modal 期望的格式）
            # 从受影响路径中提取第一个用于绕行方案生成
            first_affected = affected_routes[0] if affected_routes else None
            
            alert_data = {
                "change_type": change_type,
                "requires_decision": requires_decision,
                "available_actions": available_actions,
                # 前端期望的数组格式
                "risk_area_ids": [str(risk_area.id)],
                "risk_areas": [{
                    "id": str(risk_area.id),
                    "name": risk_area.name,
                    "risk_level": risk_area.risk_level,
                    "passage_status": risk_area.passage_status,
                }],
                # 用于生成绕行方案的参数
                "task_id": first_affected.get("task_id") if first_affected else None,
                "team_id": first_affected.get("team_id") if first_affected else None,
                "origin": first_affected.get("origin") if first_affected else None,
                "destination": first_affected.get("destination") if first_affected else None,
                # 附加信息
                "affected_routes": affected_routes,
                "affected_moving_entities": affected_moving_entities,
                "llm_advice": llm_advice,
                "geometry": risk_area.geometry_geojson,
                "description": risk_area.description,
            }
            
            # 5. STOMP 广播（通知所有前端）
            broadcast_payload = {
                "event_type": "risk_area_change",
                **alert_data,
            }
            logger.info(
                f"[风险区域通知] 准备广播: requires_decision={requires_decision}, "
                f"affected_routes_count={len(affected_routes)}, risk_area_ids={alert_data.get('risk_area_ids')}"
            )
            logger.info(f"[风险区域通知] 广播内容: {broadcast_payload}")
            
            await stomp_broker.broadcast_alert(
                alert_data=broadcast_payload,
                scenario_id=risk_area.scenario_id,
            )
            
            logger.info(
                f"[风险区域通知] WebSocket广播完成: {change_type}, "
                f"risk_level={risk_area.risk_level}, affected_routes={len(affected_routes)}"
            )
            
            # 6. 调用 early_warning 生成精准预警（高风险时）
            if risk_area.risk_level >= 5:
                warnings_count = await self._trigger_early_warning(
                    risk_area=risk_area,
                    change_type=change_type,
                )
                if warnings_count > 0:
                    logger.info(
                        f"[风险区域通知] early_warning预警生成: {warnings_count}条"
                    )
            
        except Exception as e:
            logger.error(f"[风险区域通知] 失败: {e}", exc_info=True)

    async def _trigger_early_warning(
        self,
        risk_area: RiskAreaResponse,
        change_type: str,
    ) -> int:
        """
        调用 early_warning 智能体核心逻辑，生成精准预警
        
        复用 early_warning 的队伍/车辆查询和预警生成逻辑，
        将预警记录保存到 early_warning_records 表，
        并通过 WebSocket 精准推送给相关指挥员。
        
        Args:
            risk_area: 风险区域响应对象
            change_type: 变更类型
            
        Returns:
            生成的预警记录数量
        """
        try:
            from src.agents.early_warning.repository import WarningRepository
            
            # 1. 计算风险区域中心点
            center = self._get_geometry_center(risk_area.geometry_geojson)
            if not center:
                logger.warning("[early_warning] 无法计算风险区域中心点")
                return 0
            
            center_lon, center_lat = center
            
            # 2. 根据风险等级确定缓冲距离
            # risk_level 1-4: 1km, 5-6: 2km, 7-8: 3km, 9-10: 5km
            if risk_area.risk_level >= 9:
                buffer_m = 5000
            elif risk_area.risk_level >= 7:
                buffer_m = 3000
            elif risk_area.risk_level >= 5:
                buffer_m = 2000
            else:
                buffer_m = 1000
            
            # 3. 查询缓冲区内的队伍（基于驻地或当前位置）
            result = await self.db.execute(text('''
                SELECT 
                    t.id::text,
                    t.name,
                    t.contact_person,
                    ST_Distance(
                        COALESCE(t.current_location, t.base_location)::geography,
                        ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography
                    ) as distance_m
                FROM operational_v2.rescue_teams_v2 t
                WHERE COALESCE(t.current_location, t.base_location) IS NOT NULL
                  AND t.status IN ('standby', 'deployed')
                  AND ST_DWithin(
                      COALESCE(t.current_location, t.base_location)::geography,
                      ST_SetSRID(ST_MakePoint(:center_lon, :center_lat), 4326)::geography,
                      :buffer_m
                  )
                ORDER BY distance_m
            '''), {
                "center_lon": center_lon,
                "center_lat": center_lat,
                "buffer_m": buffer_m,
            })
            affected_teams = result.fetchall()
            
            if not affected_teams:
                logger.info("[early_warning] 未找到受影响的队伍")
            
            # 4. 为每个受影响队伍创建预警记录
            warning_repo = WarningRepository(self.db)
            warnings_created = 0
            
            # 映射风险区域类型到灾害类型
            disaster_type = AREA_TYPE_TO_DISASTER_TYPE.get(
                risk_area.area_type, "landslide"
            )
            
            for team in affected_teams:
                team_id, team_name, contact_person, distance_m = team
                
                # 确定预警级别
                if distance_m < 1000:
                    level = "red"
                elif distance_m < 2000:
                    level = "orange"
                elif distance_m < 3000:
                    level = "yellow"
                else:
                    level = "blue"
                
                # 计算预计接触时间（假设30km/h行进速度）
                estimated_minutes = int(distance_m / (30 * 1000 / 60)) if distance_m > 0 else 0
                
                # 生成预警标题和消息
                level_name = {"red": "红色", "orange": "橙色", "yellow": "黄色", "blue": "蓝色"}.get(level, "黄色")
                warning_title = f"【风险区域预警-{level_name}】{risk_area.name or '未命名区域'}"
                warning_message = (
                    f"队伍「{team_name}」距风险区域{distance_m:.0f}米，"
                    f"预计{estimated_minutes}分钟后可能接触。"
                    f"风险等级: {risk_area.risk_level}/10，"
                    f"通行状态: {self.PASSAGE_STATUS_LABELS.get(risk_area.passage_status, '未知')}"
                )
                
                await warning_repo.create(
                    disaster_id=risk_area.id,  # 复用 risk_area.id 作为关联
                    scenario_id=risk_area.scenario_id,
                    affected_type="team",
                    affected_id=UUID(team_id),
                    affected_name=team_name,
                    notify_target_type="team_leader",
                    notify_target_name=contact_person,
                    warning_level=level,
                    distance_m=distance_m,
                    estimated_contact_minutes=estimated_minutes,
                    warning_title=warning_title,
                    warning_message=warning_message,
                )
                warnings_created += 1
            
            # 5. 为穿过风险区域的规划路线生成预警
            affected_routes = await self._find_affected_routes(risk_area)
            route_warning_level = self._get_route_warning_level(risk_area.risk_level)
            route_level_name = {"red": "红色", "orange": "橙色", "yellow": "黄色", "blue": "蓝色"}.get(route_warning_level, "黄色")
            
            for route in affected_routes:
                route_id = route.get("route_id")
                task_title = route.get("task_title", "未知任务")
                team_id_route = route.get("team_id")
                team_name_route = route.get("team_name")
                vehicle_name = route.get("vehicle_name")
                
                warning_title = f"【路线预警-{route_level_name}】{risk_area.name or '风险区域'}"
                warning_message = (
                    f"任务「{task_title}」的规划路线穿过风险区域，"
                    f"风险等级: {risk_area.risk_level}/10，"
                    f"通行状态: {self.PASSAGE_STATUS_LABELS.get(risk_area.passage_status, '未知')}，"
                    f"建议: {self._get_route_recommendation(risk_area.passage_status)}"
                )
                
                await warning_repo.create(
                    disaster_id=risk_area.id,
                    scenario_id=risk_area.scenario_id,
                    affected_type="route",
                    affected_id=UUID(route_id),
                    affected_name=task_title,
                    notify_target_type="team_leader" if team_id_route else "driver",
                    notify_target_name=team_name_route or vehicle_name or "未知",
                    warning_level=route_warning_level,
                    distance_m=0,  # 路线相交，距离为0
                    estimated_contact_minutes=0,
                    warning_title=warning_title,
                    warning_message=warning_message,
                )
                warnings_created += 1
            
            logger.info(
                f"[early_warning] 路线预警生成: {len(affected_routes)}条"
            )
            
            # 6. 提交事务（预警记录）
            await self.db.commit()
            
            # 7. 推送预警通知到前端
            if warnings_created > 0:
                try:
                    from src.domains.frontend_api.websocket.router import ws_manager
                    await ws_manager.broadcast_disaster({
                        "source": "risk_area",
                        "risk_area_id": str(risk_area.id),
                        "risk_area_name": risk_area.name,
                        "disaster_type": disaster_type,
                        "scenario_id": str(risk_area.scenario_id),
                        "risk_level": risk_area.risk_level,
                        "center": {"lon": center_lon, "lat": center_lat},
                        "warnings_count": warnings_created,
                        "change_type": change_type,
                    })
                except Exception as e:
                    logger.warning(f"[early_warning] WebSocket推送失败: {e}")
            
            return warnings_created
            
        except ImportError as e:
            logger.warning(f"[early_warning] 模块导入失败，跳过预警生成: {e}")
            return 0
        except Exception as e:
            logger.error(f"[early_warning] 预警生成失败: {e}", exc_info=True)
            return 0

    def _get_geometry_center(self, geometry: Optional[dict]) -> Optional[tuple[float, float]]:
        """
        计算 GeoJSON 多边形的中心点
        
        Returns:
            (lon, lat) 元组，或 None
        """
        if not geometry:
            return None
        
        try:
            coords = geometry.get("coordinates", [])
            if not coords or not coords[0]:
                return None
            
            # 取外环坐标
            ring = coords[0]
            if len(ring) < 3:
                return None
            
            # 计算质心（简单平均）
            lon_sum = sum(p[0] for p in ring)
            lat_sum = sum(p[1] for p in ring)
            count = len(ring)
            
            return (lon_sum / count, lat_sum / count)
        except Exception:
            return None

    def _requires_commander_decision(
        self,
        risk_level: int,
        passage_status: str,
    ) -> bool:
        """
        判断是否需要指挥决策弹窗
        
        规则：
        - confirmed_blocked: 必须决策（完全不可通行）
        - risk_level >= 7: 需要确认（高风险，橙色及以上）
        - needs_reconnaissance + risk_level >= 5: 需要确认（黄色+需侦察）
        """
        if passage_status == "confirmed_blocked":
            return True
        if risk_level >= 7:
            return True
        if passage_status == "needs_reconnaissance" and risk_level >= 5:
            return True
        return False

    def _get_available_actions(self, passage_status: str) -> list[str]:
        """
        根据通行状态返回可用决策选项
        
        复用现有 ResponseAction 枚举值: continue/detour/standby
        - confirmed_blocked: 完全不可通行，不允许 continue
        - 其他状态: 允许谨慎通过
        """
        if passage_status == "confirmed_blocked":
            return ["detour", "standby"]
        else:
            return ["continue", "detour", "standby"]

    def _get_route_warning_level(self, risk_level: int) -> str:
        """根据风险等级映射路线预警级别"""
        if risk_level >= 9:
            return "red"
        elif risk_level >= 7:
            return "orange"
        elif risk_level >= 5:
            return "yellow"
        return "blue"

    def _get_route_recommendation(self, passage_status: str) -> str:
        """根据通行状态生成路线建议"""
        recommendations = {
            "confirmed_blocked": "立即停止行进，联系指挥中心改道",
            "needs_reconnaissance": "减速行驶，等待侦察结果",
            "passable_with_caution": "减速通过，保持警惕",
            "clear": "正常通行",
            "unknown": "谨慎行驶，注意观察",
        }
        return recommendations.get(passage_status, "谨慎行驶")

    async def _find_affected_routes(
        self,
        risk_area: RiskAreaResponse,
    ) -> list[dict]:
        """
        查询与风险区域空间相交的活动路线
        
        使用 PostGIS ST_Intersects 进行空间查询，
        连接 planned_routes_v2 获取路线几何数据。
        
        Returns:
            受影响路线列表，包含任务、车辆、队伍信息
        """
        # 防御性检查
        if risk_area.scenario_id is None:
            return []
        
        # planned_routes_v2.task_id 外键引用 tasks_v2(id)
        # 风险区域可能存储在 disaster_affected_areas_v2 或 entities_v2 (type='danger_area')
        sql = text("""
            WITH risk_geometry AS (
                SELECT geometry 
                FROM operational_v2.disaster_affected_areas_v2 
                WHERE id = :risk_area_id
                UNION ALL
                SELECT ST_GeomFromGeoJSON(geometry::text)::geography::geometry
                FROM operational_v2.entities_v2 
                WHERE id = :risk_area_id AND type = 'danger_area'
                LIMIT 1
            )
            SELECT 
                pr.id as route_id,
                t.id as task_id,
                t.title as task_title,
                t.status as task_status,
                pr.vehicle_id,
                pr.team_id,
                v.name as vehicle_name,
                tm.name as team_name,
                ST_X(pr.start_location::geometry) as origin_lng,
                ST_Y(pr.start_location::geometry) as origin_lat,
                ST_X(pr.end_location::geometry) as dest_lng,
                ST_Y(pr.end_location::geometry) as dest_lat
            FROM operational_v2.planned_routes_v2 pr
            LEFT JOIN operational_v2.tasks_v2 t ON pr.task_id = t.id
            LEFT JOIN operational_v2.vehicles_v2 v ON pr.vehicle_id = v.id
            LEFT JOIN operational_v2.rescue_teams_v2 tm ON pr.team_id = tm.id
            WHERE pr.status = 'active'
              AND (t.scenario_id = :scenario_id OR pr.task_id IS NULL)
              AND ST_Intersects(
                  pr.route_geometry::geometry,
                  (SELECT geometry FROM risk_geometry)
              )
        """)
        
        try:
            result = await self.db.execute(sql, {
                "scenario_id": str(risk_area.scenario_id),
                "risk_area_id": str(risk_area.id),
            })
            
            return [
                {
                    "route_id": str(row.route_id),
                    "task_id": str(row.task_id) if row.task_id else None,
                    "task_title": row.task_title,
                    "task_status": row.task_status,
                    "vehicle_id": str(row.vehicle_id) if row.vehicle_id else None,
                    "vehicle_name": row.vehicle_name,
                    "team_id": str(row.team_id) if row.team_id else None,
                    "team_name": row.team_name,
                    "origin": {"lng": row.origin_lng, "lat": row.origin_lat} if row.origin_lng else None,
                    "destination": {"lng": row.dest_lng, "lat": row.dest_lat} if row.dest_lng else None,
                }
                for row in result.fetchall()
            ]
        except Exception as e:
            # 空间查询失败时返回空列表，不阻塞主流程
            logger.warning(
                f"[风险区域通知] 受影响路线查询失败: {e}",
                exc_info=True,
            )
            return []

    async def _find_affected_moving_entities(
        self,
        risk_area: RiskAreaResponse,
    ) -> list[dict]:
        """
        查询正在移动的实体，其剩余路径是否穿过风险区域
        
        从 Redis 获取活跃移动会话，计算每个会话的剩余路径，
        使用 PostGIS ST_Intersects 检测与风险区域的交集。
        
        Returns:
            受影响的移动实体列表
        """
        affected = []
        
        try:
            from src.domains.movement_simulation.persistence import get_persistence
            from src.domains.movement_simulation.schemas import MovementState
            
            persistence = await get_persistence()
            sessions = await persistence.get_active_sessions()
            
            if not sessions:
                return []
            
            # 获取风险区域几何（支持两种数据源）
            risk_geometry_sql = text("""
                SELECT geometry 
                FROM operational_v2.disaster_affected_areas_v2 
                WHERE id = :risk_area_id
                UNION ALL
                SELECT ST_GeomFromGeoJSON(geometry::text)::geography::geometry
                FROM operational_v2.entities_v2 
                WHERE id = :risk_area_id AND type = 'danger_area'
                LIMIT 1
            """)
            risk_result = await self.db.execute(risk_geometry_sql, {
                "risk_area_id": str(risk_area.id),
            })
            risk_row = risk_result.first()
            if not risk_row:
                logger.warning(f"[剩余路径检测] 未找到风险区域几何: {risk_area.id}")
                return []
            
            for session in sessions:
                if session.state not in (MovementState.MOVING, MovementState.PAUSED):
                    continue
                
                # 计算剩余路径：当前位置到终点
                remaining_route = session.route[session.current_segment_index:]
                if len(remaining_route) < 2:
                    continue
                
                # 构建剩余路径的 WKT LINESTRING
                coords_str = ", ".join(
                    f"{p.lon} {p.lat}" for p in remaining_route
                )
                remaining_linestring = f"LINESTRING({coords_str})"
                
                # 检测剩余路径是否与风险区域相交
                intersect_sql = text("""
                    SELECT ST_Intersects(
                        ST_GeomFromText(:linestring, 4326),
                        (SELECT geometry 
                         FROM operational_v2.disaster_affected_areas_v2 
                         WHERE id = :risk_area_id
                         UNION ALL
                         SELECT ST_GeomFromGeoJSON(geometry::text)::geography::geometry
                         FROM operational_v2.entities_v2 
                         WHERE id = :risk_area_id AND type = 'danger_area'
                         LIMIT 1)
                    ) as intersects
                """)
                
                try:
                    result = await self.db.execute(intersect_sql, {
                        "linestring": remaining_linestring,
                        "risk_area_id": str(risk_area.id),
                    })
                    row = result.first()
                    
                    if row and row.intersects:
                        affected.append({
                            "session_id": session.session_id,
                            "entity_id": str(session.entity_id),
                            "entity_type": session.entity_type.value,
                            "resource_id": str(session.resource_id) if session.resource_id else None,
                            "current_segment": session.current_segment_index,
                            "total_segments": len(session.route),
                            "remaining_distance_m": session.total_distance_m - session.traveled_distance_m,
                            "speed_kmh": session.speed_mps * 3.6,
                        })
                        
                except Exception as e:
                    logger.debug(f"[剩余路径检测] 单个会话检测失败: {e}")
                    continue
            
            if affected:
                logger.info(
                    f"[剩余路径检测] 发现 {len(affected)} 个移动实体受影响"
                )
            
            return affected
            
        except Exception as e:
            logger.warning(f"[剩余路径检测] 失败: {e}", exc_info=True)
            return []

    async def _generate_llm_risk_advice(
        self,
        risk_area: RiskAreaResponse,
        affected_routes: list[dict],
        affected_moving_entities: list[dict],
    ) -> Optional[dict]:
        """
        使用 LLM 生成风险描述和建议
        
        Args:
            risk_area: 风险区域信息
            affected_routes: 受影响的规划路线
            affected_moving_entities: 受影响的移动实体
            
        Returns:
            LLM 生成的建议，包含 summary, recommendation, urgency
        """
        try:
            import os
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            
            # 获取 LLM 客户端
            llm = ChatOpenAI(
                model=os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b'),
                base_url=os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1'),
                api_key=os.environ.get('OPENAI_API_KEY', 'dummy_key'),
                timeout=30,
                max_retries=0,
                max_tokens=512,
            )
            
            # 构建提示词
            passage_status_labels = {
                "confirmed_blocked": "已确认完全不可通行",
                "needs_reconnaissance": "需侦察确认",
                "passable_with_caution": "可通行但需谨慎",
                "clear": "安全通行",
                "unknown": "未知状态",
            }
            
            area_type_labels = {
                "flood": "洪涝区域",
                "debris": "泥石流区域",
                "collapse": "塌方区域",
                "fire": "火灾区域",
                "chemical": "化学污染区域",
                "road_damage": "道路损毁区域",
                "other": "其他危险区域",
            }
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一名专业的应急救援指挥顾问。根据风险区域信息和受影响的救援队伍/路线，
生成简洁的风险评估和行动建议。回复格式必须严格为JSON：
{{"summary": "风险概述（50字内）", "recommendation": "行动建议（100字内）", "urgency": "紧急程度high/medium/low"}}"""),
                ("user", """风险区域信息：
- 名称：{area_name}
- 类型：{area_type}
- 风险等级：{risk_level}/10
- 通行状态：{passage_status}
- 描述：{description}

受影响情况：
- 规划路线数：{route_count}条
- 移动中车辆数：{moving_count}辆

请生成风险评估和行动建议（JSON格式）：""")
            ])
            
            # 调用 LLM
            chain = prompt | llm
            response = await chain.ainvoke({
                "area_name": risk_area.name or "未命名区域",
                "area_type": area_type_labels.get(risk_area.area_type, "危险区域"),
                "risk_level": risk_area.risk_level,
                "passage_status": passage_status_labels.get(risk_area.passage_status, "未知"),
                "description": risk_area.description or "无详细描述",
                "route_count": len(affected_routes),
                "moving_count": len(affected_moving_entities),
            })
            
            # 解析 JSON 响应
            import json
            content = response.content.strip()
            # 尝试提取 JSON 部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            advice = json.loads(content)
            
            logger.info(f"[LLM风险建议] 生成成功: urgency={advice.get('urgency')}")
            return advice
            
        except Exception as e:
            logger.warning(f"[LLM风险建议] 生成失败，使用默认建议: {e}")
            # 返回默认建议
            return {
                "summary": f"发现{risk_area.name or '风险区域'}，风险等级{risk_area.risk_level}/10",
                "recommendation": self._get_route_recommendation(risk_area.passage_status),
                "urgency": "high" if risk_area.risk_level >= 7 else "medium",
            }

    # =========================================================================
    # 通行状态变更通知
    # =========================================================================

    # 通行状态中文描述映射
    PASSAGE_STATUS_LABELS: dict[str, str] = {
        "confirmed_blocked": "已确认完全不可通行",
        "needs_reconnaissance": "需侦察确认",
        "passable_with_caution": "可通行但需谨慎",
        "clear": "安全通行",
        "unknown": "未知状态",
    }

    async def _notify_passage_status_change(
        self,
        risk_area: RiskAreaResponse,
        old_status: Optional[str],
        new_status: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        通行状态变更通知
        
        专门用于侦察确认后的状态更新，包含不可通行原因。
        
        Args:
            risk_area: 风险区域响应对象
            old_status: 旧通行状态
            new_status: 新通行状态
            reason: 不可通行原因（如：塌方、断桥、深水等）
        """
        if risk_area.scenario_id is None:
            logger.warning(
                f"[通行状态通知] scenario_id 为空，跳过广播: "
                f"risk_area_id={risk_area.id}"
            )
            return
        
        try:
            # 查询受影响的活动路线
            affected_routes = await self._find_affected_routes(risk_area)
            
            # 判断是否需要决策（状态变为 blocked 或 needs_reconnaissance 时需要）
            requires_decision = new_status in ("confirmed_blocked", "needs_reconnaissance")
            
            # 生成可用决策选项
            available_actions = self._get_available_actions(new_status)
            
            # 生成通知消息
            old_label = self.PASSAGE_STATUS_LABELS.get(old_status or "", "未知")
            new_label = self.PASSAGE_STATUS_LABELS.get(new_status, "未知")
            
            # 构建消息内容，包含不可通行原因
            message = f"通行状态从「{old_label}」变更为「{new_label}」"
            if reason:
                message += f"，原因：{reason}"
            
            alert_data = {
                "risk_area_id": str(risk_area.id),
                "risk_area_name": risk_area.name,
                "change_type": "passage_status_changed",
                "risk_level": risk_area.risk_level,
                "old_passage_status": old_status,
                "passage_status": new_status,
                "passage_status_label": new_label,
                "reason": reason,  # 不可通行原因
                "message": message,
                "requires_decision": requires_decision,
                "available_actions": available_actions,
                "affected_routes": affected_routes,
                "geometry": risk_area.geometry_geojson,
            }
            
            await stomp_broker.broadcast_alert(
                alert_data={
                    "event_type": "risk_area_passage_change",
                    **alert_data,
                },
                scenario_id=risk_area.scenario_id,
            )
            
            logger.info(
                f"[通行状态通知] 已广播: {risk_area.name} "
                f"{old_status}→{new_status}, "
                f"reason={reason}, "
                f"affected_routes={len(affected_routes)}"
            )
            
        except Exception as e:
            logger.error(
                f"[通行状态通知] 广播失败: {e}",
                exc_info=True,
            )
