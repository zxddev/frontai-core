"""
监控器基类

定义所有监控器的通用接口和数据结构。
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警数据"""
    type: str
    level: AlertLevel
    title: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    recommendation: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type,
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "recommendation": self.recommendation,
            "created_at": self.created_at.isoformat(),
        }


class BaseWatcher(ABC):
    """
    监控器基类
    
    所有监控器必须实现 check() 方法，返回告警列表。
    """
    
    def __init__(self, name: str):
        self.name = name
        self.last_check_time: Optional[datetime] = None
        self.check_count: int = 0
        self.alert_count: int = 0
        self._cache: Dict[str, Any] = {}
    
    @abstractmethod
    async def check(self) -> List[Alert]:
        """
        执行检查，返回告警列表
        
        Returns:
            告警列表，无告警时返回空列表
        """
        pass
    
    async def run_check(self) -> List[Alert]:
        """
        执行检查的包装方法，记录统计信息
        """
        self.last_check_time = datetime.utcnow()
        self.check_count += 1
        
        try:
            alerts = await self.check()
            self.alert_count += len(alerts)
            
            if alerts:
                logger.info(
                    f"[{self.name}] 检测到 {len(alerts)} 个告警"
                )
            
            return alerts
            
        except Exception as e:
            logger.error(f"[{self.name}] 检查失败: {e}")
            return [Alert(
                type="watcher_error",
                level=AlertLevel.WARNING,
                title=f"{self.name} 检查异常",
                message=str(e),
                data={"watcher": self.name, "error": str(e)},
            )]
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控器状态"""
        return {
            "name": self.name,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "check_count": self.check_count,
            "alert_count": self.alert_count,
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.check_count = 0
        self.alert_count = 0
        self._cache.clear()
