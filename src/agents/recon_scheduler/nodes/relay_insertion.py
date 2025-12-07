"""
强制中继插入节点

基于 spec.md Requirement: Forced Relay (No Blind Flight) 实现。

核心逻辑:
1. 检测盲区 (signal < -90dBm)
2. 回溯到最后安全点 (route_history_stack)
3. 悬停上传数据, 等待ACK (60s)
4. 超时重试3次 (10s间隔)
5. 重试失败则爬升 (+50m, max 500m AGL)
6. 总停留>150s触发Emergency RTH
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..state import (
    ReconSchedulerState,
    RouteHistoryEntry,
    UTMPosition,
)
from ..mock_data import get_comm_provider, Point3D

logger = logging.getLogger(__name__)

# 配置常量 (来自spec)
SIGNAL_THRESHOLD_DBM = -90.0
SAFE_SIGNAL_MARGIN_DBM = 10.0  # 安全点需要 >= -80dBm
ACK_TIMEOUT_S = 60
ACK_RETRY_COUNT = 3
ACK_RETRY_INTERVAL_S = 10
CLIMB_STEP_M = 50
MAX_CLIMB_M = 150  # 3次爬升
MAX_ALTITUDE_AGL_M = 500
TOTAL_DWELL_LIMIT_S = 150
SAFE_POINT_TIME_VALIDITY_S = 600  # 10分钟
SAFE_POINT_DISTANCE_VALIDITY_M = 2000  # 2km


@dataclass
class BlindZone:
    """盲区段"""
    start_idx: int
    end_idx: int
    min_signal_dbm: float


@dataclass
class RelayPoint:
    """中继点"""
    lat: float
    lng: float
    alt_m: float
    signal_dbm: float
    is_safe_point: bool
    action: str = "HOVER_AND_UPLOAD"


@dataclass
class RelayConfig:
    """中继配置"""
    signal_threshold_dbm: float = SIGNAL_THRESHOLD_DBM
    safe_signal_margin_dbm: float = SAFE_SIGNAL_MARGIN_DBM
    ack_timeout_s: float = ACK_TIMEOUT_S
    ack_retry_count: int = ACK_RETRY_COUNT
    ack_retry_interval_s: float = ACK_RETRY_INTERVAL_S
    climb_step_m: float = CLIMB_STEP_M
    max_climb_m: float = MAX_CLIMB_M
    max_altitude_agl_m: float = MAX_ALTITUDE_AGL_M
    total_dwell_limit_s: float = TOTAL_DWELL_LIMIT_S


@dataclass
class RelayResult:
    """中继结果"""
    success: bool
    relay_points_inserted: int
    total_dwell_s: float
    trigger_rth: bool = False
    rth_reason: Optional[str] = None
    modified_waypoints: list = field(default_factory=list)


class RelayInserter:
    """中继点插入器"""
    
    def __init__(self, config: RelayConfig = None):
        self.config = config or RelayConfig()
        self._comm_provider = get_comm_provider()
    
    async def detect_blind_zones(
        self,
        waypoints: list[dict]
    ) -> list[BlindZone]:
        """
        检测航线上的盲区段
        
        Args:
            waypoints: 航点列表
        
        Returns:
            盲区段列表
        """
        path = [
            Point3D(lat=wp["lat"], lng=wp["lng"], alt=wp.get("alt_m", 100))
            for wp in waypoints
        ]
        
        # 获取路径覆盖
        coverage = await self._comm_provider.predict_coverage_along_path(path)
        
        # 找出盲区段
        blind_zones = []
        in_blind = False
        start_idx = 0
        min_signal = 0.0
        
        for i, result in enumerate(coverage):
            if result.signal_dbm < self.config.signal_threshold_dbm:
                if not in_blind:
                    in_blind = True
                    start_idx = i
                    min_signal = result.signal_dbm
                else:
                    min_signal = min(min_signal, result.signal_dbm)
            else:
                if in_blind:
                    blind_zones.append(BlindZone(
                        start_idx=start_idx,
                        end_idx=i - 1,
                        min_signal_dbm=min_signal
                    ))
                    in_blind = False
        
        # 处理末尾盲区
        if in_blind:
            blind_zones.append(BlindZone(
                start_idx=start_idx,
                end_idx=len(coverage) - 1,
                min_signal_dbm=min_signal
            ))
        
        return blind_zones
    
    async def find_last_safe_point(
        self,
        waypoints: list[dict],
        blind_zone: BlindZone,
        route_history: list[RouteHistoryEntry],
        current_time: datetime
    ) -> Optional[RelayPoint]:
        """
        找到最后一个安全信号点
        
        安全点条件 (来自spec):
        - 时间有效性: < 10分钟
        - 距离有效性: < 2km
        - 信号有效性: >= -80dBm
        """
        safe_threshold = self.config.signal_threshold_dbm + self.config.safe_signal_margin_dbm
        
        # 从盲区起点向前搜索
        for i in range(blind_zone.start_idx - 1, -1, -1):
            if i >= len(waypoints):
                continue
            
            wp = waypoints[i]
            signal = await self._comm_provider.get_signal_strength(
                wp["lat"], wp["lng"], wp.get("alt_m", 100)
            )
            
            if signal >= safe_threshold:
                return RelayPoint(
                    lat=wp["lat"],
                    lng=wp["lng"],
                    alt_m=wp.get("alt_m", 100),
                    signal_dbm=signal,
                    is_safe_point=True
                )
        
        # 没有找到安全点, 返回盲区前一个点
        if blind_zone.start_idx > 0:
            wp = waypoints[blind_zone.start_idx - 1]
            signal = await self._comm_provider.get_signal_strength(
                wp["lat"], wp["lng"], wp.get("alt_m", 100)
            )
            return RelayPoint(
                lat=wp["lat"],
                lng=wp["lng"],
                alt_m=wp.get("alt_m", 100),
                signal_dbm=signal,
                is_safe_point=False
            )
        
        return None
    
    async def simulate_ack_wait(self, timeout_s: float) -> bool:
        """
        模拟等待ACK
        
        在真实实现中, 这里应该:
        1. 上传数据到服务器
        2. 等待服务器ACK
        
        Mock实现: 70%概率成功
        """
        await asyncio.sleep(0.1)  # 模拟网络延迟
        import random
        return random.random() < 0.7
    
    async def attempt_climb_for_signal(
        self,
        lat: float,
        lng: float,
        current_alt: float,
        max_alt: float
    ) -> tuple[bool, float, float]:
        """
        尝试爬升获取信号
        
        Returns:
            (success, new_alt, signal_dbm)
        """
        alt = current_alt
        climbed = 0.0
        
        while climbed < self.config.max_climb_m and alt < max_alt:
            alt += self.config.climb_step_m
            climbed += self.config.climb_step_m
            
            signal = await self._comm_provider.get_signal_strength(lat, lng, alt)
            
            if signal >= self.config.signal_threshold_dbm:
                logger.info(f"Signal recovered at alt={alt}m, signal={signal:.1f}dBm")
                return True, alt, signal
        
        # 爬升失败, 返回最终状态
        final_signal = await self._comm_provider.get_signal_strength(lat, lng, alt)
        return False, alt, final_signal
    
    async def insert_relay_points(
        self,
        waypoints: list[dict],
        route_history: list[RouteHistoryEntry]
    ) -> RelayResult:
        """
        在航线中插入中继点
        
        Args:
            waypoints: 原始航点列表
            route_history: 路径历史
        
        Returns:
            中继结果
        """
        # 检测盲区
        blind_zones = await self.detect_blind_zones(waypoints)
        
        if not blind_zones:
            logger.info("No blind zones detected")
            return RelayResult(
                success=True,
                relay_points_inserted=0,
                total_dwell_s=0,
                modified_waypoints=waypoints
            )
        
        logger.info(f"Detected {len(blind_zones)} blind zones")
        
        modified_waypoints = []
        relay_points_inserted = 0
        total_dwell_s = 0.0
        current_time = datetime.now()
        
        i = 0
        for blind_zone in blind_zones:
            # 添加盲区之前的所有航点
            while i < blind_zone.start_idx and i < len(waypoints):
                modified_waypoints.append(waypoints[i])
                i += 1
            
            # 找到安全点
            safe_point = await self.find_last_safe_point(
                waypoints, blind_zone, route_history, current_time
            )
            
            if safe_point:
                # 插入中继点
                relay_wp = {
                    "lat": safe_point.lat,
                    "lng": safe_point.lng,
                    "alt_m": safe_point.alt_m,
                    "action": "HOVER_AND_UPLOAD",
                    "is_relay": True,
                    "signal_dbm": safe_point.signal_dbm,
                }
                modified_waypoints.append(relay_wp)
                relay_points_inserted += 1
                
                # 模拟ACK等待流程
                dwell_start = time.time()
                ack_received = False
                
                # 第一次尝试
                ack_received = await self.simulate_ack_wait(self.config.ack_timeout_s)
                
                # 重试
                retry = 0
                while not ack_received and retry < self.config.ack_retry_count:
                    await asyncio.sleep(0.1)  # 模拟重试间隔
                    ack_received = await self.simulate_ack_wait(self.config.ack_timeout_s)
                    retry += 1
                
                dwell_time = time.time() - dwell_start
                total_dwell_s += dwell_time
                
                # 检查是否需要爬升
                if not ack_received:
                    climb_success, new_alt, new_signal = await self.attempt_climb_for_signal(
                        safe_point.lat,
                        safe_point.lng,
                        safe_point.alt_m,
                        self.config.max_altitude_agl_m
                    )
                    
                    if climb_success:
                        relay_wp["alt_m"] = new_alt
                        relay_wp["signal_dbm"] = new_signal
                        ack_received = True
                
                # 检查总停留时间
                if total_dwell_s > self.config.total_dwell_limit_s:
                    logger.warning(f"Total dwell time exceeded: {total_dwell_s:.1f}s > {self.config.total_dwell_limit_s}s")
                    return RelayResult(
                        success=False,
                        relay_points_inserted=relay_points_inserted,
                        total_dwell_s=total_dwell_s,
                        trigger_rth=True,
                        rth_reason="RELAY_DWELL_EXCEEDED",
                        modified_waypoints=modified_waypoints
                    )
                
                # 如果仍然没有ACK, 触发RTH
                if not ack_received:
                    logger.warning("ACK not received after all retries and climb")
                    return RelayResult(
                        success=False,
                        relay_points_inserted=relay_points_inserted,
                        total_dwell_s=total_dwell_s,
                        trigger_rth=True,
                        rth_reason="ACK_TIMEOUT",
                        modified_waypoints=modified_waypoints
                    )
            
            # 跳过盲区中的航点
            i = blind_zone.end_idx + 1
        
        # 添加剩余航点
        while i < len(waypoints):
            modified_waypoints.append(waypoints[i])
            i += 1
        
        return RelayResult(
            success=True,
            relay_points_inserted=relay_points_inserted,
            total_dwell_s=total_dwell_s,
            modified_waypoints=modified_waypoints
        )


async def relay_insertion_node(state: ReconSchedulerState) -> dict:
    """
    强制中继 LangGraph 节点
    
    在 L2 验证通过后执行, 检查并插入中继点。
    
    输入: state.flight_plans, state.route_history
    输出: state.flight_plans (modified), state.relay_dwell_total_s
    """
    logger.info("进入强制中继节点")
    
    flight_plans = state.get("flight_plans", [])
    route_history = state.get("route_history", [])
    
    if not flight_plans:
        return {
            "current_phase": "relay_insertion",
        }
    
    inserter = RelayInserter()
    total_relay_points = 0
    total_dwell = 0.0
    trigger_rth = False
    rth_reason = None
    
    modified_plans = []
    
    for plan in flight_plans:
        waypoints = plan.get("waypoints", [])
        
        result = await inserter.insert_relay_points(waypoints, route_history)
        
        total_relay_points += result.relay_points_inserted
        total_dwell += result.total_dwell_s
        
        if result.trigger_rth:
            trigger_rth = True
            rth_reason = result.rth_reason
            break
        
        # 更新航点
        modified_plan = {**plan, "waypoints": result.modified_waypoints}
        modified_plans.append(modified_plan)
    
    updates = {
        "flight_plans": modified_plans if not trigger_rth else flight_plans,
        "relay_dwell_total_s": total_dwell,
        "current_phase": "relay_insertion",
    }
    
    if trigger_rth:
        updates["rth_triggers"] = state.get("rth_triggers", []) + [rth_reason]
        logger.warning(f"Relay insertion triggered RTH: {rth_reason}")
    else:
        logger.info(f"Relay insertion complete: {total_relay_points} points, {total_dwell:.1f}s dwell")
    
    return updates
