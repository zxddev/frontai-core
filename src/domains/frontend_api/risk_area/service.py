"""
风险区域业务逻辑层

功能：
- 风险区域 CRUD 操作
- 风险区域变更实时通知（WebSocket 广播）
- 受影响路线空间查询
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
        scenario_id: UUID,
        area_type: Optional[str] = None,
        min_risk_level: Optional[int] = None,
        passage_status: Optional[str] = None,
    ) -> RiskAreaListResponse:
        """获取想定下的风险区域列表"""
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
        
        通过 WebSocket alerts 频道广播，前端根据 requires_decision 字段
        决定是否弹出指挥决策对话框。
        
        Args:
            risk_area: 风险区域响应对象
            change_type: 变更类型 ("created" | "updated")
            old_risk_level: 旧的风险等级（仅 updated 时传入）
        """
        # Guard: scenario_id 为 None 时不广播（无法确定目标客户端）
        if risk_area.scenario_id is None:
            logger.warning(
                f"[风险区域通知] scenario_id 为空，跳过广播: "
                f"risk_area_id={risk_area.id}"
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
            
            # 3. 生成可用决策选项（复用现有 ResponseAction: continue/detour/standby）
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
            
            # 5. 通过现有 alerts 频道广播
            await broadcast_alert(
                scenario_id=risk_area.scenario_id,
                alert_type="risk_area_change",
                alert_data=alert_data,
            )
            
            logger.info(
                f"[风险区域通知] 已广播: change_type={change_type}, "
                f"risk_level={risk_area.risk_level}, "
                f"requires_decision={requires_decision}, "
                f"affected_routes={len(affected_routes)}"
            )
            
        except Exception as e:
            # 通知失败不阻塞主流程，仅记录错误
            logger.error(
                f"[风险区域通知] 广播失败: {e}",
                exc_info=True,
            )

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
