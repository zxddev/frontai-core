"""
灾情变化监控器

监听 events_v2 表的状态和等级变化，检测灾情升级/降级。
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.core.database import AsyncSessionLocal
from .base_watcher import BaseWatcher, Alert, AlertLevel

logger = logging.getLogger(__name__)


class DisasterWatcher(BaseWatcher):
    """
    灾情变化监控器
    
    监控内容：
    1. 事件状态变化（pending -> confirmed -> executing 等）
    2. 事件优先级变化（灾情升级/降级）
    3. 受困人数变化
    4. 新增次生灾害（子事件）
    """
    
    def __init__(self, event_id: str, scenario_id: Optional[str] = None):
        super().__init__(name="DisasterWatcher")
        self.event_id = event_id
        self.scenario_id = scenario_id
        self._last_state: Optional[Dict[str, Any]] = None
    
    async def check(self) -> List[Alert]:
        """检查灾情变化"""
        alerts = []
        
        try:
            current_state = await self._get_event_state()
            
            if current_state is None:
                return [Alert(
                    type="disaster_event_not_found",
                    level=AlertLevel.WARNING,
                    title="事件不存在",
                    message=f"事件 {self.event_id} 不存在或已被删除",
                    data={"event_id": self.event_id},
                )]
            
            if self._last_state is not None:
                alerts.extend(self._compare_states(self._last_state, current_state))
            
            # 检查新增次生灾害
            new_secondary_events = await self._check_secondary_events()
            alerts.extend(new_secondary_events)
            
            self._last_state = current_state
            
        except Exception as e:
            logger.error(f"[DisasterWatcher] 检查失败: {e}")
            alerts.append(Alert(
                type="disaster_watcher_error",
                level=AlertLevel.WARNING,
                title="灾情监控异常",
                message=str(e),
                data={"event_id": self.event_id, "error": str(e)},
            ))
        
        return alerts
    
    async def _get_event_state(self) -> Optional[Dict[str, Any]]:
        """获取事件当前状态"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        id::text,
                        event_code,
                        title,
                        event_type,
                        status,
                        priority,
                        estimated_victims,
                        rescued_count,
                        casualty_count,
                        is_time_critical,
                        golden_hour_deadline,
                        updated_at
                    FROM operational_v2.events_v2
                    WHERE id = :event_id
                """),
                {"event_id": self.event_id}
            )
            row = result.fetchone()
            
            if row is None:
                return None
            
            return {
                "id": row[0],
                "event_code": row[1],
                "title": row[2],
                "event_type": row[3],
                "status": row[4],
                "priority": row[5],
                "estimated_victims": row[6],
                "rescued_count": row[7],
                "casualty_count": row[8],
                "is_time_critical": row[9],
                "golden_hour_deadline": row[10],
                "updated_at": row[11],
            }
    
    def _compare_states(
        self, 
        old_state: Dict[str, Any], 
        new_state: Dict[str, Any]
    ) -> List[Alert]:
        """对比状态变化，生成告警"""
        alerts = []
        
        # 1. 状态变化
        if old_state["status"] != new_state["status"]:
            alerts.append(Alert(
                type="disaster_status_changed",
                level=AlertLevel.INFO,
                title="事件状态变化",
                message=f"事件 {new_state['event_code']} 状态从 {old_state['status']} 变为 {new_state['status']}",
                data={
                    "event_id": new_state["id"],
                    "event_code": new_state["event_code"],
                    "old_status": old_state["status"],
                    "new_status": new_state["status"],
                },
            ))
        
        # 2. 优先级变化（灾情升级/降级）
        if old_state["priority"] != new_state["priority"]:
            priority_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            old_level = priority_order.get(old_state["priority"], 0)
            new_level = priority_order.get(new_state["priority"], 0)
            
            is_upgrade = new_level > old_level
            level = AlertLevel.CRITICAL if is_upgrade else AlertLevel.INFO
            
            alerts.append(Alert(
                type="disaster_situation_changed",
                level=level,
                title="灾情等级变化" if is_upgrade else "灾情等级调整",
                message=f"事件 {new_state['event_code']} 优先级从 {old_state['priority']} 变为 {new_state['priority']}",
                data={
                    "event_id": new_state["id"],
                    "event_code": new_state["event_code"],
                    "old_priority": old_state["priority"],
                    "new_priority": new_state["priority"],
                    "is_upgrade": is_upgrade,
                },
                recommendation="建议重新评估救援方案" if is_upgrade else None,
            ))
        
        # 3. 受困人数增加
        if new_state["estimated_victims"] > old_state["estimated_victims"]:
            increase = new_state["estimated_victims"] - old_state["estimated_victims"]
            alerts.append(Alert(
                type="disaster_victims_increased",
                level=AlertLevel.CRITICAL,
                title="受困人数增加",
                message=f"事件 {new_state['event_code']} 受困人数从 {old_state['estimated_victims']} 增加到 {new_state['estimated_victims']}（+{increase}）",
                data={
                    "event_id": new_state["id"],
                    "event_code": new_state["event_code"],
                    "old_victims": old_state["estimated_victims"],
                    "new_victims": new_state["estimated_victims"],
                    "increase": increase,
                },
                recommendation="建议增派救援力量",
            ))
        
        # 4. 黄金时间状态变化
        if not old_state["is_time_critical"] and new_state["is_time_critical"]:
            alerts.append(Alert(
                type="disaster_golden_hour_activated",
                level=AlertLevel.CRITICAL,
                title="黄金救援时间激活",
                message=f"事件 {new_state['event_code']} 进入黄金救援时间",
                data={
                    "event_id": new_state["id"],
                    "event_code": new_state["event_code"],
                    "deadline": new_state["golden_hour_deadline"].isoformat() if new_state["golden_hour_deadline"] else None,
                },
                recommendation="紧急！请立即调配最近的救援队伍",
            ))
        
        return alerts
    
    async def _check_secondary_events(self) -> List[Alert]:
        """检查新增次生灾害"""
        alerts = []
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        id::text,
                        event_code,
                        title,
                        event_type,
                        priority,
                        created_at
                    FROM operational_v2.events_v2
                    WHERE parent_event_id = :event_id
                      AND created_at > :last_check
                    ORDER BY created_at
                """),
                {
                    "event_id": self.event_id,
                    "last_check": self.last_check_time or datetime(2000, 1, 1),
                }
            )
            rows = result.fetchall()
            
            for row in rows:
                alerts.append(Alert(
                    type="disaster_secondary_event",
                    level=AlertLevel.CRITICAL,
                    title="发现次生灾害",
                    message=f"主事件产生次生灾害: {row[2]} ({row[3]})",
                    data={
                        "parent_event_id": self.event_id,
                        "secondary_event_id": row[0],
                        "event_code": row[1],
                        "title": row[2],
                        "event_type": row[3],
                        "priority": row[4],
                    },
                    recommendation="建议评估次生灾害影响并调整救援方案",
                ))
        
        return alerts
