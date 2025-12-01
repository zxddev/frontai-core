"""
装备推荐 Service
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ConflictError
from src.core.stomp.broker import stomp_broker
from .repository import EquipmentRecommendationRepository
from .schemas import (
    EquipmentRecommendationResponse,
    EquipmentRecommendationConfirm,
    EquipmentRecommendationBrief,
    DeviceRecommendationSchema,
    SupplyRecommendationSchema,
    ShortageAlertSchema,
    LoadingPlanItemSchema,
)

logger = logging.getLogger(__name__)


class EquipmentRecommendationService:
    def __init__(self, db: AsyncSession):
        self.repo = EquipmentRecommendationRepository(db)
        self.db = db
    
    async def get_by_event_id(self, event_id: UUID) -> EquipmentRecommendationResponse:
        """根据事件ID获取装备推荐"""
        data = await self.repo.get_by_event_id(event_id)
        if not data:
            raise NotFoundError("EquipmentRecommendation", f"event_id={event_id}")
        return self._to_response(data)
    
    async def get_by_id(self, rec_id: UUID) -> EquipmentRecommendationResponse:
        """根据推荐ID获取"""
        data = await self.repo.get_by_id(rec_id)
        if not data:
            raise NotFoundError("EquipmentRecommendation", str(rec_id))
        return self._to_response(data)
    
    async def confirm(
        self,
        event_id: UUID,
        data: EquipmentRecommendationConfirm,
        confirmed_by: Optional[UUID] = None,
    ) -> EquipmentRecommendationResponse:
        """确认装备推荐"""
        rec_data = await self.repo.get_by_event_id(event_id)
        if not rec_data:
            raise NotFoundError("EquipmentRecommendation", f"event_id={event_id}")
        
        if rec_data["status"] != "ready":
            raise ConflictError(
                "ER4001", 
                f"只能确认ready状态的推荐，当前状态: {rec_data['status']}"
            )
        
        updated = await self.repo.confirm(
            rec_id=rec_data["id"],
            device_ids=data.device_ids,
            supplies=data.supplies,
            note=data.note,
            confirmed_by=confirmed_by,
        )
        
        logger.info(
            f"装备推荐已确认: event_id={event_id}, "
            f"devices={len(data.device_ids)}, supplies={len(data.supplies)}"
        )
        
        return self._to_response(updated)
    
    async def trigger_analysis(
        self,
        event_id: UUID,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]] = None,
        scenario_id: Optional[UUID] = None,
    ) -> None:
        """
        触发装备分析（异步执行）
        
        由 EventService.create() 调用，不等待完成。
        会自动取消之前未确认的推荐（pending/ready状态）。
        同时清理该事件的旧装备分配记录，确保不影响新推荐结果。
        """
        # 取消之前未确认的推荐，确保前端只看到最新结果
        cancelled_count = await self.repo.cancel_previous_unconfirmed()
        if cancelled_count > 0:
            logger.info(f"已取消 {cancelled_count} 条旧推荐记录")
        
        # 清理该事件的旧装备分配记录
        await self._clear_event_assignments(event_id)
        
        logger.info(f"触发装备分析: event_id={event_id}")
        
        # 创建异步任务
        asyncio.create_task(
            self._run_analysis_and_notify(
                event_id=event_id,
                disaster_description=disaster_description,
                structured_input=structured_input,
                scenario_id=scenario_id,
            )
        )
    
    async def _run_analysis_and_notify(
        self,
        event_id: UUID,
        disaster_description: str,
        structured_input: Optional[Dict[str, Any]],
        scenario_id: Optional[UUID],
    ) -> None:
        """执行分析并通过WebSocket通知"""
        try:
            # 导入图执行函数
            from src.agents.equipment_preparation.graph import run_equipment_preparation
            
            # 执行智能体
            final_state = await run_equipment_preparation(
                event_id=str(event_id),
                disaster_description=disaster_description,
                structured_input=structured_input,
            )
            
            # 检查是否有错误
            errors = final_state.get("errors", [])
            if errors:
                logger.error(f"装备分析有错误: {errors}")
            
            # 获取事件信息用于通知
            event_info = await self._get_event_info(event_id)
            
            # 构建通知消息
            brief = EquipmentRecommendationBrief(
                recommendation_id=event_id,  # 简化处理，实际应从数据库获取
                event_id=event_id,
                event_code=event_info.get("event_code", "UNKNOWN"),
                event_title=event_info.get("title", "未知事件"),
                total_devices=len(final_state.get("recommended_devices", [])),
                total_supplies=len(final_state.get("recommended_supplies", [])),
                critical_alerts=sum(
                    1 for a in final_state.get("shortage_alerts", []) 
                    if a.get("severity") == "critical"
                ),
                warning_alerts=sum(
                    1 for a in final_state.get("shortage_alerts", []) 
                    if a.get("severity") == "warning"
                ),
                key_devices=[
                    d.get("device_name", "") 
                    for d in final_state.get("recommended_devices", [])[:3]
                ],
                ready_at=event_info.get("ready_at") or event_info.get("created_at"),
            )
            
            # 通过WebSocket广播
            await self._broadcast_equipment_ready(brief, scenario_id)
            
            logger.info(
                f"装备分析完成并已通知: event_id={event_id}, "
                f"devices={brief.total_devices}, supplies={brief.total_supplies}"
            )
            
        except Exception as e:
            logger.exception(f"装备分析失败: event_id={event_id}")
    
    async def _clear_event_assignments(self, event_id: UUID) -> None:
        """清理事件的旧装备分配记录"""
        from sqlalchemy import text
        
        result = await self.db.execute(
            text("""
                DELETE FROM operational_v2.car_item_assignment
                WHERE event_id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        await self.db.commit()
        if result.rowcount > 0:
            logger.info(f"已清理事件 {event_id} 的旧装备分配记录，共 {result.rowcount} 条")
    
    async def _get_event_info(self, event_id: UUID) -> Dict[str, Any]:
        """获取事件信息"""
        from sqlalchemy import text
        
        result = await self.db.execute(
            text("""
                SELECT event_code, title, scenario_id, created_at
                FROM operational_v2.events_v2
                WHERE id = :event_id
            """),
            {"event_id": str(event_id)}
        )
        row = result.fetchone()
        if row:
            return {
                "event_code": row.event_code,
                "title": row.title,
                "scenario_id": row.scenario_id,
                "created_at": row.created_at,
            }
        return {}
    
    async def _broadcast_equipment_ready(
        self,
        brief: EquipmentRecommendationBrief,
        scenario_id: Optional[UUID],
    ) -> None:
        """广播装备就绪通知"""
        try:
            payload = {
                "type": "equipment_ready",
                "recommendationId": str(brief.recommendation_id),
                "eventId": str(brief.event_id),
                "eventCode": brief.event_code,
                "eventTitle": brief.event_title,
                "summary": {
                    "totalDevices": brief.total_devices,
                    "totalSupplies": brief.total_supplies,
                    "criticalAlerts": brief.critical_alerts,
                    "warningAlerts": brief.warning_alerts,
                    "keyDevices": brief.key_devices,
                },
                "readyAt": brief.ready_at.isoformat() if brief.ready_at else None,
            }
            
            await stomp_broker.broadcast_event("equipment", payload, scenario_id)
            logger.info(f"已广播装备就绪通知: {brief.event_code}")
            
        except Exception as e:
            logger.error(f"广播装备就绪通知失败: {e}")
    
    def _to_response(self, data: Dict[str, Any]) -> EquipmentRecommendationResponse:
        """转换为响应对象"""
        # 转换设备推荐
        devices = [
            DeviceRecommendationSchema(**d) 
            for d in data.get("recommended_devices", [])
        ]
        
        # 转换物资推荐
        supplies = [
            SupplyRecommendationSchema(**s)
            for s in data.get("recommended_supplies", [])
        ]
        
        # 转换缺口告警
        alerts = [
            ShortageAlertSchema(**a)
            for a in data.get("shortage_alerts", [])
        ]
        
        # 转换装载方案
        loading_plan = None
        if data.get("loading_plan"):
            loading_plan = {
                k: LoadingPlanItemSchema(**v)
                for k, v in data["loading_plan"].items()
            }
        
        return EquipmentRecommendationResponse(
            id=data["id"],
            event_id=data["event_id"],
            status=data["status"],
            disaster_analysis=data.get("disaster_analysis"),
            requirement_analysis=data.get("requirement_analysis"),
            recommended_devices=devices,
            recommended_supplies=supplies,
            shortage_alerts=alerts,
            loading_plan=loading_plan,
            confirmed_devices=data.get("confirmed_devices"),
            confirmed_supplies=data.get("confirmed_supplies"),
            confirmation_note=data.get("confirmation_note"),
            created_at=data["created_at"],
            ready_at=data.get("ready_at"),
            confirmed_at=data.get("confirmed_at"),
        )
