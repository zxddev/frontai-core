"""
持续监控主循环

EmergencyMonitorLoop - 管理多个监控器的生命周期和调度
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .watchers import (
    BaseWatcher, Alert, AlertLevel,
    DisasterWatcher, TeamProgressWatcher, RouteWatcher,
)

logger = logging.getLogger(__name__)


def _get_stomp_broker():
    """延迟导入避免循环依赖"""
    from src.core.stomp.broker import stomp_broker
    return stomp_broker


class EmergencyMonitorLoop:
    """
    应急救援持续监控循环
    
    功能：
    1. 管理多个监控器（灾情、队伍、路网）
    2. 周期性执行检查
    3. 收集告警并推送 WebSocket
    4. 记录告警历史
    
    使用示例:
    ```python
    loop = EmergencyMonitorLoop(
        task_id="xxx",
        event_id="yyy",
        scenario_id="zzz",
    )
    await loop.start()
    # ... 运行一段时间 ...
    await loop.stop()
    ```
    """
    
    # 默认检查间隔（秒）
    DEFAULT_CHECK_INTERVAL = 10
    
    def __init__(
        self,
        task_id: str,
        event_id: str,
        scenario_id: Optional[str] = None,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
    ):
        self.task_id = task_id
        self.event_id = event_id
        self.scenario_id = scenario_id
        self.check_interval = check_interval
        
        # 监控器列表
        self.watchers: List[BaseWatcher] = []
        
        # 运行状态
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime] = None
        
        # 告警历史
        self._alert_history: List[Alert] = []
        self._max_history = 1000  # 最多保留1000条
    
    def _init_watchers(self):
        """初始化监控器"""
        self.watchers = [
            DisasterWatcher(
                event_id=self.event_id,
                scenario_id=self.scenario_id,
            ),
            TeamProgressWatcher(
                task_id=self.task_id,
            ),
            RouteWatcher(
                task_id=self.task_id,
                scenario_id=self.scenario_id,
            ),
        ]
        logger.info(f"[MonitorLoop] 初始化 {len(self.watchers)} 个监控器")
    
    async def start(self):
        """启动监控循环"""
        if self._running:
            logger.warning("[MonitorLoop] 已在运行中")
            return
        
        logger.info(
            f"[MonitorLoop] 启动监控: task_id={self.task_id}, "
            f"event_id={self.event_id}, interval={self.check_interval}s"
        )
        
        self._init_watchers()
        self._running = True
        self._started_at = datetime.utcnow()
        
        # 启动后台任务
        self._task = asyncio.create_task(
            self._run_loop(),
            name=f"monitor-{self.task_id[:8]}"
        )
        
        # 广播启动事件
        await self._broadcast_status("started")
    
    async def stop(self):
        """停止监控循环"""
        if not self._running:
            return
        
        logger.info(f"[MonitorLoop] 停止监控: task_id={self.task_id}")
        
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # 广播停止事件
        await self._broadcast_status("stopped")
    
    async def _run_loop(self):
        """监控主循环"""
        logger.info(f"[MonitorLoop] 进入主循环: task_id={self.task_id}")
        
        try:
            while self._running:
                # 执行所有监控器检查
                all_alerts = await self._run_all_checks()
                
                # 处理告警
                if all_alerts:
                    await self._handle_alerts(all_alerts)
                
                # 等待下次检查
                await asyncio.sleep(self.check_interval)
                
        except asyncio.CancelledError:
            logger.info(f"[MonitorLoop] 循环被取消: task_id={self.task_id}")
        except Exception as e:
            logger.error(f"[MonitorLoop] 循环异常: {e}", exc_info=True)
        finally:
            self._running = False
            logger.info(f"[MonitorLoop] 退出主循环: task_id={self.task_id}")
    
    async def _run_all_checks(self) -> List[Alert]:
        """执行所有监控器检查"""
        all_alerts = []
        
        for watcher in self.watchers:
            try:
                alerts = await watcher.run_check()
                all_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"[MonitorLoop] 监控器 {watcher.name} 检查失败: {e}")
                all_alerts.append(Alert(
                    type="watcher_error",
                    level=AlertLevel.WARNING,
                    title=f"{watcher.name} 检查异常",
                    message=str(e),
                    data={"watcher": watcher.name, "error": str(e)},
                ))
        
        return all_alerts
    
    async def _handle_alerts(self, alerts: List[Alert]):
        """处理告警"""
        for alert in alerts:
            # 记录到历史
            self._alert_history.append(alert)
            if len(self._alert_history) > self._max_history:
                self._alert_history = self._alert_history[-self._max_history:]
            
            # 记录日志
            log_level = {
                AlertLevel.INFO: logging.INFO,
                AlertLevel.WARNING: logging.WARNING,
                AlertLevel.CRITICAL: logging.ERROR,
            }.get(alert.level, logging.INFO)
            
            logger.log(
                log_level,
                f"[MonitorLoop] 告警: [{alert.level.value}] {alert.title} - {alert.message}"
            )
            
            # 推送 WebSocket
            await self._broadcast_alert(alert)
    
    async def _broadcast_alert(self, alert: Alert):
        """推送告警到 WebSocket"""
        try:
            broker = _get_stomp_broker()
            
            payload = {
                "task_id": self.task_id,
                "event_id": self.event_id,
                "alert": alert.to_dict(),
            }
            
            # 根据告警类型选择不同的主题
            topic = f"/topic/emergency.monitor.{alert.type}"
            await broker.broadcast(topic, {"payload": payload})
            
            # 同时发送到通用告警主题
            await broker.broadcast("/topic/emergency.monitor.alert", {"payload": payload})
            
        except Exception as e:
            logger.warning(f"[MonitorLoop] 推送告警失败: {e}")
    
    async def _broadcast_status(self, status: str):
        """推送状态变化"""
        try:
            broker = _get_stomp_broker()
            
            payload = {
                "task_id": self.task_id,
                "event_id": self.event_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            await broker.broadcast("/topic/emergency.monitor.status", {"payload": payload})
            
        except Exception as e:
            logger.warning(f"[MonitorLoop] 推送状态失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return {
            "task_id": self.task_id,
            "event_id": self.event_id,
            "scenario_id": self.scenario_id,
            "running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "check_interval": self.check_interval,
            "watchers": [w.get_status() for w in self.watchers],
            "total_alerts": len(self._alert_history),
            "recent_alerts": [a.to_dict() for a in self._alert_history[-10:]],
        }
    
    def get_alert_history(
        self,
        limit: int = 100,
        level: Optional[AlertLevel] = None,
        alert_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取告警历史"""
        alerts = self._alert_history
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if alert_type:
            alerts = [a for a in alerts if a.type == alert_type]
        
        return [a.to_dict() for a in alerts[-limit:]]


# 全局监控管理器
class MonitorManager:
    """监控管理器 - 管理多个监控循环"""
    
    def __init__(self):
        self._loops: Dict[str, EmergencyMonitorLoop] = {}
    
    async def start_monitor(
        self,
        task_id: str,
        event_id: str,
        scenario_id: Optional[str] = None,
        check_interval: float = EmergencyMonitorLoop.DEFAULT_CHECK_INTERVAL,
    ) -> EmergencyMonitorLoop:
        """启动监控"""
        # 检查是否已存在
        if task_id in self._loops:
            existing = self._loops[task_id]
            if existing._running:
                logger.warning(f"[MonitorManager] 任务 {task_id} 已有运行中的监控")
                return existing
            else:
                # 清理旧的
                del self._loops[task_id]
        
        # 创建新的监控循环
        loop = EmergencyMonitorLoop(
            task_id=task_id,
            event_id=event_id,
            scenario_id=scenario_id,
            check_interval=check_interval,
        )
        
        await loop.start()
        self._loops[task_id] = loop
        
        return loop
    
    async def stop_monitor(self, task_id: str) -> bool:
        """停止监控"""
        loop = self._loops.get(task_id)
        if loop:
            await loop.stop()
            del self._loops[task_id]
            return True
        return False
    
    def get_monitor(self, task_id: str) -> Optional[EmergencyMonitorLoop]:
        """获取监控循环"""
        return self._loops.get(task_id)
    
    def list_monitors(self) -> List[Dict[str, Any]]:
        """列出所有监控"""
        return [loop.get_status() for loop in self._loops.values()]
    
    async def stop_all(self):
        """停止所有监控"""
        for task_id in list(self._loops.keys()):
            await self.stop_monitor(task_id)


# 全局单例
_monitor_manager: Optional[MonitorManager] = None


def get_monitor_manager() -> MonitorManager:
    """获取监控管理器单例"""
    global _monitor_manager
    if _monitor_manager is None:
        _monitor_manager = MonitorManager()
    return _monitor_manager
