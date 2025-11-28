"""
仿真时钟

管理仿真时间与真实时间的映射关系，支持时间倍率调整
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class SimulationClock:
    """
    仿真时钟
    
    管理仿真时间：
    - 支持时间倍率（0.5x - 10x）
    - 支持暂停/恢复
    - 计算仿真时间与真实时间的映射
    
    使用示例:
    ```python
    clock = SimulationClock(
        simulation_start=datetime(2025, 11, 27, 8, 0),
        time_scale=2.0
    )
    clock.start()
    
    # 真实过了5分钟，仿真时间过了10分钟
    current_sim_time = clock.current_simulation_time
    
    clock.pause()
    clock.resume()
    clock.set_time_scale(4.0)
    ```
    """
    
    def __init__(
        self,
        simulation_start: datetime,
        time_scale: Decimal = Decimal("1.0"),
    ) -> None:
        """
        初始化仿真时钟
        
        Args:
            simulation_start: 仿真世界的起始时间
            time_scale: 时间倍率（1.0 = 实时，2.0 = 2倍速）
        """
        self._simulation_start = simulation_start
        self._time_scale = float(time_scale)
        
        # 真实世界的开始时间（调用start()时设置）
        self._real_start: Optional[datetime] = None
        
        # 暂停相关
        self._paused = False
        self._pause_time: Optional[datetime] = None
        self._total_pause_duration = timedelta()
    
    def start(self) -> None:
        """启动时钟"""
        if self._real_start is None:
            self._real_start = datetime.utcnow()
            logger.info(
                f"仿真时钟启动: simulation_start={self._simulation_start}, "
                f"time_scale={self._time_scale}x"
            )
    
    def pause(self) -> None:
        """暂停时钟"""
        if not self._paused and self._real_start is not None:
            self._paused = True
            self._pause_time = datetime.utcnow()
            logger.debug("仿真时钟暂停")
    
    def resume(self) -> None:
        """恢复时钟"""
        if self._paused and self._pause_time is not None:
            pause_duration = datetime.utcnow() - self._pause_time
            self._total_pause_duration += pause_duration
            self._paused = False
            self._pause_time = None
            logger.debug(f"仿真时钟恢复，本次暂停时长: {pause_duration}")
    
    def set_time_scale(self, time_scale: Decimal) -> None:
        """
        设置时间倍率
        
        注意：更改倍率时会重新计算基准点，确保当前仿真时间连续
        """
        if self._real_start is None:
            self._time_scale = float(time_scale)
            return
        
        # 记录当前仿真时间
        current_sim_time = self.current_simulation_time
        
        # 更新基准点
        self._simulation_start = current_sim_time
        self._real_start = datetime.utcnow()
        self._total_pause_duration = timedelta()
        
        # 设置新倍率
        self._time_scale = float(time_scale)
        
        logger.info(f"时间倍率调整为 {time_scale}x，当前仿真时间: {current_sim_time}")
    
    @property
    def current_simulation_time(self) -> datetime:
        """获取当前仿真时间"""
        if self._real_start is None:
            return self._simulation_start
        
        if self._paused and self._pause_time is not None:
            # 暂停时返回暂停时刻的仿真时间
            real_elapsed = self._pause_time - self._real_start - self._total_pause_duration
        else:
            real_elapsed = datetime.utcnow() - self._real_start - self._total_pause_duration
        
        # 应用时间倍率
        simulation_elapsed = real_elapsed * self._time_scale
        
        return self._simulation_start + simulation_elapsed
    
    @property
    def elapsed_real_seconds(self) -> float:
        """已过真实时间（秒）"""
        if self._real_start is None:
            return 0.0
        
        if self._paused and self._pause_time is not None:
            elapsed = self._pause_time - self._real_start - self._total_pause_duration
        else:
            elapsed = datetime.utcnow() - self._real_start - self._total_pause_duration
        
        return elapsed.total_seconds()
    
    @property
    def elapsed_simulation_seconds(self) -> float:
        """已过仿真时间（秒）"""
        return self.elapsed_real_seconds * self._time_scale
    
    @property
    def time_scale(self) -> float:
        """当前时间倍率"""
        return self._time_scale
    
    @property
    def is_paused(self) -> bool:
        """是否暂停"""
        return self._paused
    
    @property
    def is_started(self) -> bool:
        """是否已启动"""
        return self._real_start is not None
    
    @property
    def total_pause_duration_seconds(self) -> float:
        """累计暂停时长（秒）"""
        current_pause = timedelta()
        if self._paused and self._pause_time is not None:
            current_pause = datetime.utcnow() - self._pause_time
        
        return (self._total_pause_duration + current_pause).total_seconds()
    
    def simulation_to_real_time(self, sim_time: datetime) -> Optional[datetime]:
        """
        将仿真时间转换为真实时间
        
        Args:
            sim_time: 仿真时间
            
        Returns:
            对应的真实时间，如果在启动前返回None
        """
        if self._real_start is None:
            return None
        
        sim_elapsed = sim_time - self._simulation_start
        real_elapsed = sim_elapsed / self._time_scale
        
        return self._real_start + real_elapsed + self._total_pause_duration
    
    def real_to_simulation_time(self, real_time: datetime) -> datetime:
        """
        将真实时间转换为仿真时间
        
        Args:
            real_time: 真实时间
            
        Returns:
            对应的仿真时间
        """
        if self._real_start is None:
            return self._simulation_start
        
        real_elapsed = real_time - self._real_start - self._total_pause_duration
        sim_elapsed = real_elapsed * self._time_scale
        
        return self._simulation_start + sim_elapsed
    
    def get_status(self) -> dict:
        """获取时钟状态"""
        return {
            "simulation_start": self._simulation_start.isoformat(),
            "current_simulation_time": self.current_simulation_time.isoformat(),
            "time_scale": self._time_scale,
            "is_started": self.is_started,
            "is_paused": self.is_paused,
            "elapsed_real_seconds": self.elapsed_real_seconds,
            "elapsed_simulation_seconds": self.elapsed_simulation_seconds,
            "total_pause_duration_seconds": self.total_pause_duration_seconds,
        }
