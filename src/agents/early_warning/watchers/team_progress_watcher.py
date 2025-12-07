"""
队伍进度监控器

监控救援队伍的执行进度，检测延迟和异常。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from src.core.database import AsyncSessionLocal
from .base_watcher import BaseWatcher, Alert, AlertLevel

logger = logging.getLogger(__name__)


class TeamProgressWatcher(BaseWatcher):
    """
    队伍进度监控器
    
    监控内容：
    1. 队伍是否按时到达（对比预计ETA）
    2. 队伍是否停滞不前（长时间无位置更新）
    3. 队伍状态异常（从 dispatched 变成 unavailable 等）
    """
    
    # 延迟阈值（分钟）
    DELAY_THRESHOLD_MINUTES = 15
    # 停滞阈值（分钟）
    STALL_THRESHOLD_MINUTES = 10
    
    def __init__(self, task_id: str):
        super().__init__(name="TeamProgressWatcher")
        self.task_id = task_id
        self._team_states: Dict[str, Dict[str, Any]] = {}
    
    async def check(self) -> List[Alert]:
        """检查队伍进度"""
        alerts = []
        
        try:
            # 获取任务关联的队伍分配
            assignments = await self._get_task_assignments()
            
            for assignment in assignments:
                team_id = assignment["team_id"]
                team_name = assignment["team_name"]
                
                # 1. 检查移动状态
                movement_alerts = await self._check_movement_progress(assignment)
                alerts.extend(movement_alerts)
                
                # 2. 检查队伍状态变化
                status_alerts = await self._check_team_status(assignment)
                alerts.extend(status_alerts)
                
                # 更新状态缓存
                self._team_states[team_id] = {
                    "status": assignment.get("team_status"),
                    "last_check": datetime.utcnow(),
                }
                
        except Exception as e:
            logger.error(f"[TeamProgressWatcher] 检查失败: {e}")
            alerts.append(Alert(
                type="team_progress_watcher_error",
                level=AlertLevel.WARNING,
                title="队伍进度监控异常",
                message=str(e),
                data={"task_id": self.task_id, "error": str(e)},
            ))
        
        return alerts
    
    async def _get_task_assignments(self) -> List[Dict[str, Any]]:
        """获取任务关联的队伍分配"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        ta.id::text as assignment_id,
                        ta.assignee_id::text as team_id,
                        ta.assignee_name as team_name,
                        ta.status as assignment_status,
                        ta.assigned_at,
                        ta.started_at,
                        ta.completed_at,
                        t.title as task_title,
                        t.priority as task_priority,
                        rt.status as team_status,
                        ST_X(COALESCE(rt.current_location, rt.base_location)::geometry) as team_lon,
                        ST_Y(COALESCE(rt.current_location, rt.base_location)::geometry) as team_lat
                    FROM operational_v2.task_assignments_v2 ta
                    JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
                    LEFT JOIN operational_v2.rescue_teams_v2 rt ON ta.assignee_id = rt.id
                    WHERE t.id = :task_id
                      AND ta.assignee_type = 'team'
                      AND ta.status NOT IN ('cancelled', 'rejected')
                    ORDER BY ta.assigned_at
                """),
                {"task_id": self.task_id}
            )
            rows = result.fetchall()
            
            return [
                {
                    "assignment_id": row[0],
                    "team_id": row[1],
                    "team_name": row[2],
                    "assignment_status": row[3],
                    "assigned_at": row[4],
                    "started_at": row[5],
                    "completed_at": row[6],
                    "task_title": row[7],
                    "task_priority": row[8],
                    "team_status": row[9],
                    "team_lon": row[10],
                    "team_lat": row[11],
                }
                for row in rows
            ]
    
    async def _check_movement_progress(self, assignment: Dict[str, Any]) -> List[Alert]:
        """检查移动进度"""
        alerts = []
        team_id = assignment["team_id"]
        team_name = assignment["team_name"]
        
        # 查询移动仿真状态
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        session_id,
                        state,
                        total_distance_m,
                        traveled_distance_m,
                        speed_mps,
                        started_at,
                        last_update_at,
                        (total_distance_m - traveled_distance_m) / NULLIF(speed_mps, 0) as remaining_seconds
                    FROM operational_v2.movement_sessions
                    WHERE entity_id = :team_id
                      AND state IN ('moving', 'paused', 'executing_task')
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"team_id": team_id}
            )
            row = result.fetchone()
        
        if row is None:
            # 没有移动会话，可能还未出发
            if assignment["assignment_status"] == "assigned":
                assigned_at = assignment.get("assigned_at")
                if assigned_at:
                    wait_time = datetime.utcnow() - assigned_at
                    if wait_time > timedelta(minutes=self.DELAY_THRESHOLD_MINUTES):
                        alerts.append(Alert(
                            type="team_not_departed",
                            level=AlertLevel.WARNING,
                            title="队伍尚未出发",
                            message=f"队伍 {team_name} 已分配 {int(wait_time.total_seconds() / 60)} 分钟，但尚未开始移动",
                            data={
                                "task_id": self.task_id,
                                "team_id": team_id,
                                "team_name": team_name,
                                "wait_minutes": int(wait_time.total_seconds() / 60),
                            },
                            recommendation="请确认队伍是否准备就绪",
                        ))
            return alerts
        
        session_id = row[0]
        state = row[1]
        total_distance = row[2] or 0
        traveled_distance = row[3] or 0
        speed_mps = row[4] or 0
        started_at = row[5]
        last_update_at = row[6]
        remaining_seconds = row[7] or 0
        
        # 计算进度百分比
        progress_percent = (traveled_distance / total_distance * 100) if total_distance > 0 else 0
        
        # 1. 检查是否暂停状态
        if state == "paused":
            alerts.append(Alert(
                type="team_movement_paused",
                level=AlertLevel.WARNING,
                title="队伍移动已暂停",
                message=f"队伍 {team_name} 移动已暂停，进度 {progress_percent:.1f}%",
                data={
                    "task_id": self.task_id,
                    "team_id": team_id,
                    "team_name": team_name,
                    "session_id": session_id,
                    "progress_percent": progress_percent,
                },
                recommendation="请检查暂停原因并决定是否恢复",
            ))
        
        # 2. 检查位置更新是否停滞
        if last_update_at:
            stall_time = datetime.utcnow() - last_update_at
            if stall_time > timedelta(minutes=self.STALL_THRESHOLD_MINUTES) and state == "moving":
                alerts.append(Alert(
                    type="team_movement_stalled",
                    level=AlertLevel.CRITICAL,
                    title="队伍移动停滞",
                    message=f"队伍 {team_name} 已 {int(stall_time.total_seconds() / 60)} 分钟无位置更新",
                    data={
                        "task_id": self.task_id,
                        "team_id": team_id,
                        "team_name": team_name,
                        "session_id": session_id,
                        "stall_minutes": int(stall_time.total_seconds() / 60),
                        "last_position": {
                            "lon": assignment.get("team_lon"),
                            "lat": assignment.get("team_lat"),
                        },
                    },
                    recommendation="队伍可能遇到障碍，建议联系确认情况",
                ))
        
        # 3. 检查预计到达时间延迟（基于原计划）
        # 简化逻辑：如果已出发超过预计时间但未到达，则告警
        if started_at and remaining_seconds > 0:
            elapsed = (datetime.utcnow() - started_at).total_seconds()
            expected_total = total_distance / speed_mps if speed_mps > 0 else 0
            
            if elapsed > expected_total + self.DELAY_THRESHOLD_MINUTES * 60:
                delay_minutes = int((elapsed - expected_total) / 60)
                alerts.append(Alert(
                    type="team_arrival_delayed",
                    level=AlertLevel.WARNING,
                    title="队伍预计延迟到达",
                    message=f"队伍 {team_name} 预计延迟 {delay_minutes} 分钟到达",
                    data={
                        "task_id": self.task_id,
                        "team_id": team_id,
                        "team_name": team_name,
                        "delay_minutes": delay_minutes,
                        "progress_percent": progress_percent,
                        "remaining_distance_m": total_distance - traveled_distance,
                    },
                    recommendation="考虑调整路线或派遣其他队伍补位",
                ))
        
        return alerts
    
    async def _check_team_status(self, assignment: Dict[str, Any]) -> List[Alert]:
        """检查队伍状态变化"""
        alerts = []
        team_id = assignment["team_id"]
        team_name = assignment["team_name"]
        current_status = assignment.get("team_status")
        
        # 获取之前的状态
        prev_state = self._team_states.get(team_id, {})
        prev_status = prev_state.get("status")
        
        # 检查状态变化
        if prev_status and current_status != prev_status:
            # 异常状态变化
            if current_status in ("unavailable", "maintenance"):
                alerts.append(Alert(
                    type="team_status_abnormal",
                    level=AlertLevel.CRITICAL,
                    title="队伍状态异常",
                    message=f"队伍 {team_name} 状态从 {prev_status} 变为 {current_status}",
                    data={
                        "task_id": self.task_id,
                        "team_id": team_id,
                        "team_name": team_name,
                        "old_status": prev_status,
                        "new_status": current_status,
                    },
                    recommendation="队伍可能无法继续执行任务，建议立即调整",
                ))
        
        return alerts
