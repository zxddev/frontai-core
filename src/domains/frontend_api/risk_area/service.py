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

from src.core.websocket import broadcast_alert
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
            
            # 3. 生成可用决策选项
            available_actions = self._get_available_actions(risk_area.passage_status)
            
            # 4. 构建通知 payload
            alert_data = {
                "risk_area_id": str(risk_area.id),
                "risk_area_name": risk_area.name,
                "change_type": change_type,
                "risk_level": risk_area.risk_level,
                "old_risk_level": old_risk_level,
                "passage_status": risk_area.passage_status,
                "requires_decision": requires_decision,
                "available_actions": available_actions,
                "affected_routes": affected_routes,
                "geometry": risk_area.geometry_geojson,
                "description": risk_area.description,
            }
            
            # 5. WebSocket 广播（通知所有前端）
            await broadcast_alert(
                scenario_id=risk_area.scenario_id,
                alert_type="risk_area_change",
                alert_data=alert_data,
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
        
        sql = text("""
            SELECT 
                pr.id as route_id,
                t.id as task_id,
                t.title as task_title,
                t.status as task_status,
                pr.vehicle_id,
                pr.team_id,
                v.name as vehicle_name,
                tm.name as team_name
            FROM operational_v2.planned_routes_v2 pr
            JOIN operational_v2.tasks_v2 t ON pr.task_id = t.id
            LEFT JOIN operational_v2.vehicles_v2 v ON pr.vehicle_id = v.id
            LEFT JOIN operational_v2.rescue_teams_v2 tm ON pr.team_id = tm.id
            WHERE t.scenario_id = :scenario_id
              AND t.status IN ('assigned', 'accepted', 'in_progress')
              AND pr.status = 'active'
              AND ST_Intersects(
                  pr.route_geometry,
                  (SELECT geometry FROM operational_v2.disaster_affected_areas_v2 
                   WHERE id = :risk_area_id)
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
                    "task_id": str(row.task_id),
                    "task_title": row.task_title,
                    "task_status": row.task_status,
                    "vehicle_id": str(row.vehicle_id) if row.vehicle_id else None,
                    "vehicle_name": row.vehicle_name,
                    "team_id": str(row.team_id) if row.team_id else None,
                    "team_name": row.team_name,
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
            
            await broadcast_alert(
                scenario_id=risk_area.scenario_id,
                alert_type="risk_area_passage_change",
                alert_data=alert_data,
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
