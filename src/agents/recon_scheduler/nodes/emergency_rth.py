"""
紧急RTH节点

基于 spec.md Requirement: Emergency RTH (Return To Home) 实现。

触发条件 (按优先级排序):
1. CRITICAL_HARDWARE_FAULT (motor/GPS/IMU) - 立即
2. BATTERY_CRITICAL (< RTH_required) - 立即
3. HUMAN_COMMAND - 立即
4. SIGNAL_LOST_TIMEOUT (30s) - 延迟
5. VALIDATION_EXHAUSTED + APPROVAL_TIMEOUT - 延迟

RTH路径计算:
- 优先使用 route_history_stack 逆向返回
- 若路径阻挡, 爬升 obstacle_height + 50m
- 无历史路径: 爬升100m AGL直飞
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..state import (
    ReconSchedulerState,
    RTHTrigger,
    RouteHistoryEntry,
    UTMPosition,
)
from ..energy_model import calculate_rth_required_from_profile, should_trigger_rth
from ..mock_data import get_device_provider
from ..terrain_checker import get_terrain_checker

logger = logging.getLogger(__name__)

# 配置常量 (来自spec)
SIGNAL_LOST_TIMEOUT_S = 30
APPROVAL_TIMEOUT_S = 300
RTH_MARGIN_PERCENT = 10.0
DEFAULT_RTH_ALTITUDE_M = 100
OBSTACLE_CLEARANCE_M = 50


# RTH触发优先级映射
RTH_PRIORITY = {
    RTHTrigger.CRITICAL_HARDWARE_FAULT: 1,
    RTHTrigger.BATTERY_CRITICAL: 2,
    RTHTrigger.HUMAN_COMMAND: 3,
    RTHTrigger.SIGNAL_LOST_TIMEOUT: 4,
    RTHTrigger.VALIDATION_EXHAUSTED: 5,
}


@dataclass
class RTHConfig:
    """RTH配置"""
    signal_lost_timeout_s: float = SIGNAL_LOST_TIMEOUT_S
    approval_timeout_s: float = APPROVAL_TIMEOUT_S
    rth_margin_percent: float = RTH_MARGIN_PERCENT
    default_altitude_m: float = DEFAULT_RTH_ALTITUDE_M
    obstacle_clearance_m: float = OBSTACLE_CLEARANCE_M


@dataclass
class RTHPath:
    """RTH路径"""
    waypoints: list[dict]
    method: str  # "inverse_history" | "climb_direct" | "direct"
    altitude_m: float
    distance_m: float
    estimated_energy_percent: float


@dataclass
class RTHResult:
    """RTH结果"""
    triggered: bool
    triggers: list[str]
    highest_priority: Optional[str]
    rth_path: Optional[RTHPath]
    emit_event: bool = True


class EmergencyRTH:
    """紧急RTH处理器"""
    
    def __init__(self, config: RTHConfig = None):
        self.config = config or RTHConfig()
        self._terrain_checker = get_terrain_checker(use_mock=True)
    
    async def check_triggers(self, state: ReconSchedulerState) -> list[RTHTrigger]:
        """
        检查所有RTH触发条件
        
        Returns:
            触发的条件列表
        """
        triggers = []
        
        # 1. 硬件故障 (从state读取)
        hardware_fault = state.get("hardware_fault")
        if hardware_fault:
            triggers.append(RTHTrigger.CRITICAL_HARDWARE_FAULT)
        
        # 2. 电池低
        battery_percent = state.get("battery_percent", 100.0)
        rth_required = state.get("rth_required_percent", 20.0)
        
        if should_trigger_rth(battery_percent, rth_required, self.config.rth_margin_percent):
            triggers.append(RTHTrigger.BATTERY_CRITICAL)
        
        # 3. 人工命令
        if state.get("human_rth_command"):
            triggers.append(RTHTrigger.HUMAN_COMMAND)
        
        # 4. 信号丢失
        signal_lost_since = state.get("signal_lost_since")
        if signal_lost_since:
            try:
                lost_time = datetime.fromisoformat(signal_lost_since)
                elapsed = (datetime.now() - lost_time).total_seconds()
                if elapsed > self.config.signal_lost_timeout_s:
                    triggers.append(RTHTrigger.SIGNAL_LOST_TIMEOUT)
            except (ValueError, TypeError):
                pass
        
        # 5. 验证失败 + 审批超时
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)
        approval_status = state.get("approval_status", "not_required")
        
        if retry_count >= max_retries and approval_status == "timeout":
            triggers.append(RTHTrigger.VALIDATION_EXHAUSTED)
        
        # 检查其他RTH触发 (从relay_insertion等传来)
        existing_triggers = state.get("rth_triggers", [])
        for t in existing_triggers:
            if t not in [trig.value for trig in triggers]:
                # 映射字符串到枚举 (如果可能)
                try:
                    triggers.append(RTHTrigger(t))
                except ValueError:
                    logger.warning(f"Unknown RTH trigger: {t}")
        
        return triggers
    
    def get_highest_priority(self, triggers: list[RTHTrigger]) -> Optional[RTHTrigger]:
        """
        获取最高优先级的触发条件
        """
        if not triggers:
            return None
        
        return min(triggers, key=lambda t: RTH_PRIORITY.get(t, 99))
    
    def calculate_inverse_path(
        self,
        route_history: list[RouteHistoryEntry],
        home_position: dict
    ) -> Optional[list[dict]]:
        """
        基于路径历史计算逆向返回路径
        """
        if not route_history:
            return None
        
        # 逆序路径历史
        inverse_waypoints = []
        for entry in reversed(route_history):
            pos = entry.get("position_utm") or entry
            inverse_waypoints.append({
                "lat": pos.get("lat", pos.get("northing", 0) / 111000 + 31.0),  # 简化转换
                "lng": pos.get("lng", pos.get("easting", 0) / 111000 + 103.0),
                "alt_m": pos.get("altitude", pos.get("alt_m", 100)),
            })
        
        # 添加home点
        if home_position:
            inverse_waypoints.append({
                "lat": home_position.get("lat", 31.68),
                "lng": home_position.get("lng", 103.85),
                "alt_m": home_position.get("alt_m", 100),
            })
        
        return inverse_waypoints
    
    def calculate_climb_direct_path(
        self,
        current_position: dict,
        home_position: dict,
        obstacle_height: float = 0
    ) -> list[dict]:
        """
        计算爬升直飞路径
        
        Args:
            current_position: 当前位置
            home_position: 起飞点
            obstacle_height: 最高障碍物高度
        """
        # 计算安全高度
        safe_altitude = max(
            self.config.default_altitude_m,
            obstacle_height + self.config.obstacle_clearance_m
        )
        
        waypoints = [
            # 当前位置爬升
            {
                "lat": current_position.get("lat", 31.7),
                "lng": current_position.get("lng", 103.85),
                "alt_m": safe_altitude,
                "action": "CLIMB",
            },
            # 直飞到home上方
            {
                "lat": home_position.get("lat", 31.68),
                "lng": home_position.get("lng", 103.85),
                "alt_m": safe_altitude,
                "action": "FLY_TO",
            },
            # 下降到home
            {
                "lat": home_position.get("lat", 31.68),
                "lng": home_position.get("lng", 103.85),
                "alt_m": home_position.get("alt_m", 100),
                "action": "LAND",
            },
        ]
        
        return waypoints
    
    def calculate_path_distance(self, waypoints: list[dict]) -> float:
        """计算路径总距离"""
        if len(waypoints) < 2:
            return 0.0
        
        total = 0.0
        for i in range(len(waypoints) - 1):
            wp1, wp2 = waypoints[i], waypoints[i+1]
            dlat = (wp2["lat"] - wp1["lat"]) * 111000
            dlng = (wp2["lng"] - wp1["lng"]) * 111000 * 0.85
            dalt = wp2.get("alt_m", 0) - wp1.get("alt_m", 0)
            total += math.sqrt(dlat**2 + dlng**2 + dalt**2)
        
        return total
    
    async def calculate_rth_path(
        self,
        state: ReconSchedulerState,
        highest_trigger: RTHTrigger
    ) -> RTHPath:
        """
        计算RTH路径
        
        优先级:
        1. 使用route_history逆向
        2. 爬升直飞
        """
        route_history = state.get("route_history", [])
        home_position = state.get("home_position_utm") or {
            "lat": 31.68, "lng": 103.85, "alt_m": 1600
        }
        current_position = state.get("current_position_utm") or {
            "lat": 31.70, "lng": 103.87, "alt_m": 1800
        }
        
        # 方法1: 尝试逆向路径
        if route_history:
            inverse_path = self.calculate_inverse_path(route_history, home_position)
            if inverse_path:
                # 检查路径是否安全 (简化: 检查地形碰撞)
                collision = self._terrain_checker.check_terrain_collision(inverse_path)
                
                if not collision.has_collision:
                    distance = self.calculate_path_distance(inverse_path)
                    return RTHPath(
                        waypoints=inverse_path,
                        method="inverse_history",
                        altitude_m=max(wp.get("alt_m", 100) for wp in inverse_path),
                        distance_m=distance,
                        estimated_energy_percent=distance / 1000 * 3.0  # 简化估算
                    )
                else:
                    logger.warning("Inverse path has terrain collision, using climb_direct")
        
        # 方法2: 爬升直飞
        # 获取最高地形
        max_ground = self._terrain_checker.get_safe_altitude([current_position, home_position])
        
        climb_path = self.calculate_climb_direct_path(
            current_position, home_position, max_ground
        )
        
        distance = self.calculate_path_distance(climb_path)
        
        return RTHPath(
            waypoints=climb_path,
            method="climb_direct",
            altitude_m=climb_path[0]["alt_m"],
            distance_m=distance,
            estimated_energy_percent=distance / 1000 * 3.0
        )
    
    async def execute(self, state: ReconSchedulerState) -> RTHResult:
        """
        执行RTH检查和路径计算
        """
        # 检查触发条件
        triggers = await self.check_triggers(state)
        
        if not triggers:
            return RTHResult(
                triggered=False,
                triggers=[],
                highest_priority=None,
                rth_path=None,
                emit_event=False
            )
        
        # 获取最高优先级触发
        highest = self.get_highest_priority(triggers)
        
        logger.warning(f"RTH triggered: {[t.value for t in triggers]}, highest={highest.value}")
        
        # 计算RTH路径
        rth_path = await self.calculate_rth_path(state, highest)
        
        return RTHResult(
            triggered=True,
            triggers=[t.value for t in triggers],
            highest_priority=highest.value,
            rth_path=rth_path,
            emit_event=True
        )


async def emergency_rth_node(state: ReconSchedulerState) -> dict:
    """
    紧急RTH LangGraph节点
    
    检查RTH触发条件并生成RTH路径。
    """
    logger.info("进入紧急RTH检查节点")
    
    rth_handler = EmergencyRTH()
    result = await rth_handler.execute(state)
    
    updates = {
        "current_phase": "emergency_rth_check",
    }
    
    if result.triggered:
        updates["rth_triggers"] = result.triggers
        updates["safe_mode_action"] = "RTH"
        
        if result.rth_path:
            # 替换flight_plans为RTH路径
            updates["flight_plans"] = [{
                "plan_id": "emergency_rth",
                "device_id": state.get("flight_plans", [{}])[0].get("device_id", "unknown"),
                "waypoints": result.rth_path.waypoints,
                "is_emergency_rth": True,
                "rth_method": result.rth_path.method,
            }]
        
        logger.warning(f"Emergency RTH activated: {result.highest_priority}")
    else:
        logger.info("No RTH triggers detected")
    
    return updates


def check_should_trigger_rth(state: ReconSchedulerState) -> bool:
    """
    快速检查是否应触发RTH (用于条件边)
    """
    # 检查已有触发器
    if state.get("rth_triggers"):
        return True
    
    # 检查电量
    battery = state.get("battery_percent", 100)
    rth_required = state.get("rth_required_percent", 20)
    if battery < rth_required + 10:
        return True
    
    # 检查信号丢失
    signal_lost = state.get("signal_lost_since")
    if signal_lost:
        try:
            lost_time = datetime.fromisoformat(signal_lost)
            if (datetime.now() - lost_time).total_seconds() > 30:
                return True
        except:
            pass
    
    return False
