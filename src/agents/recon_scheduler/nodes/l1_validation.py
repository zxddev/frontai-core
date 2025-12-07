"""
L1 快速验证节点

基于 spec.md Requirement: Hierarchical Validation (L1 fast, L2 deep) 实现。

L1 验证内容 (500ms 超时):
- 2.5D 禁飞区检查 (polygon intersection)
- 粗略能耗估算 (distance-based)
- 最大飞行时间约束

特点:
- CPU-only 计算, 无外部 I/O
- 超时后中断, 不保留部分结果
- 失败后计入重试次数
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..state import (
    ReconSchedulerState,
    ValidationResult,
    FlightPlan,
    Waypoint,
    NoFlyZone,
)
from ..energy_model import calculate_energy_simple
from ..mock_data import get_device_provider

logger = logging.getLogger(__name__)

# L1 超时 (毫秒)
L1_TIMEOUT_MS = 500

# 错误码
ERROR_BANZONE = "BANZONE_VIOLATION"
ERROR_ENERGY = "ENERGY_EXCEEDED"
ERROR_FLIGHT_TIME = "FLIGHT_TIME_EXCEEDED"
ERROR_TIMEOUT = "VALIDATION_TIMEOUT"


@dataclass
class L1Config:
    """L1验证配置"""
    timeout_ms: int = L1_TIMEOUT_MS
    energy_margin_percent: float = 20.0  # 能耗安全余量
    max_flight_time_margin: float = 0.9  # 最大飞行时间使用率


def calculate_distance(wp1: dict, wp2: dict) -> float:
    """计算两点间距离 (米)"""
    R = 6371000  # 地球半径
    lat1 = math.radians(wp1["lat"])
    lat2 = math.radians(wp2["lat"])
    dlat = lat2 - lat1
    dlng = math.radians(wp2["lng"] - wp1["lng"])
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    horizontal = R * c
    vertical = abs(wp2.get("alt_m", 0) - wp1.get("alt_m", 0))
    
    return math.sqrt(horizontal**2 + vertical**2)


def calculate_total_distance(waypoints: list[dict]) -> float:
    """计算航线总距离"""
    if len(waypoints) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(waypoints) - 1):
        total += calculate_distance(waypoints[i], waypoints[i+1])
    
    return total


def point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
    """
    射线法判断点是否在多边形内
    
    Args:
        point: (lng, lat)
        polygon: [[lng, lat], ...]
    """
    x, y = point
    n = len(polygon)
    if n < 3:
        return False
    
    inside = False
    j = n - 1
    
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        
        j = i
    
    return inside


def segment_intersects_polygon(
    p1: tuple[float, float],
    p2: tuple[float, float],
    polygon: list[list[float]]
) -> bool:
    """
    检查线段是否与多边形相交
    
    简化实现: 检查线段端点和中点是否在多边形内
    """
    # 检查端点
    if point_in_polygon(p1, polygon) or point_in_polygon(p2, polygon):
        return True
    
    # 检查中点
    mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    if point_in_polygon(mid, polygon):
        return True
    
    return False


def check_banzone_violation(
    waypoints: list[dict],
    no_fly_zones: list[dict]
) -> tuple[bool, Optional[str]]:
    """
    检查航线是否穿过禁飞区
    
    Args:
        waypoints: 航点列表
        no_fly_zones: 禁飞区列表
    
    Returns:
        (is_valid, error_message)
    """
    for zone in no_fly_zones:
        geometry = zone.get("geometry", {})
        if geometry.get("type") != "Polygon":
            continue
        
        coords = geometry.get("coordinates", [[]])[0]
        if len(coords) < 3:
            continue
        
        # 检查每个航段
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]
            
            p1 = (wp1["lng"], wp1["lat"])
            p2 = (wp2["lng"], wp2["lat"])
            
            if segment_intersects_polygon(p1, p2, coords):
                zone_id = zone.get("zone_id", "unknown")
                return False, f"Flight path intersects no-fly zone: {zone_id}"
    
    return True, None


def check_energy_constraint(
    waypoints: list[dict],
    device_profile: Any,
    battery_percent: float,
    margin_percent: float = 20.0
) -> tuple[bool, Optional[str], float]:
    """
    检查能耗约束
    
    Args:
        waypoints: 航点列表
        device_profile: 设备配置
        battery_percent: 当前电量
        margin_percent: 安全余量
    
    Returns:
        (is_valid, error_message, estimated_energy)
    """
    total_distance = calculate_total_distance(waypoints)
    estimated_energy = calculate_energy_simple(total_distance, device_profile.energy_params)
    
    available = battery_percent - margin_percent
    
    if estimated_energy > available:
        return False, f"Energy required ({estimated_energy:.1f}%) exceeds available ({available:.1f}%)", estimated_energy
    
    return True, None, estimated_energy


def check_flight_time_constraint(
    waypoints: list[dict],
    cruise_speed_ms: float,
    max_flight_time_min: float,
    margin: float = 0.9
) -> tuple[bool, Optional[str], float]:
    """
    检查飞行时间约束
    
    Args:
        waypoints: 航点列表
        cruise_speed_ms: 巡航速度
        max_flight_time_min: 最大飞行时间
        margin: 使用率上限
    
    Returns:
        (is_valid, error_message, estimated_time_min)
    """
    total_distance = calculate_total_distance(waypoints)
    
    if cruise_speed_ms <= 0:
        return False, "Invalid cruise speed", 0.0
    
    estimated_time_s = total_distance / cruise_speed_ms
    estimated_time_min = estimated_time_s / 60
    
    allowed_time = max_flight_time_min * margin
    
    if estimated_time_min > allowed_time:
        return False, f"Flight time ({estimated_time_min:.1f}min) exceeds allowed ({allowed_time:.1f}min)", estimated_time_min
    
    return True, None, estimated_time_min


async def run_l1_validation(
    flight_plans: list[dict],
    no_fly_zones: list[dict],
    battery_percent: float,
    config: L1Config = None
) -> ValidationResult:
    """
    执行 L1 验证
    
    Args:
        flight_plans: 航线计划列表
        no_fly_zones: 禁飞区列表
        battery_percent: 当前电量
        config: 验证配置
    
    Returns:
        验证结果
    """
    config = config or L1Config()
    start_time = time.time()
    
    checks: dict[str, bool] = {}
    errors: list[str] = []
    
    device_provider = get_device_provider()
    
    for plan in flight_plans:
        plan_id = plan.get("plan_id", "unknown")
        device_id = plan.get("device_id")
        waypoints = plan.get("waypoints", [])
        
        if not waypoints:
            continue
        
        # 获取设备配置
        device_profile = await device_provider.get_device_profile(device_id)
        if not device_profile:
            errors.append(f"Device not found: {device_id}")
            checks[f"{plan_id}_device"] = False
            continue
        
        # 关键日志：设备参数
        logger.info(f"[L1] 设备 {device_id}: max_endurance={device_profile.max_endurance_min}min, "
                   f"cruise_speed={device_profile.energy_params.cruise_speed_ms}m/s")
        
        # 检查1: 禁飞区
        banzone_valid, banzone_error = check_banzone_violation(waypoints, no_fly_zones)
        checks[f"{plan_id}_banzone"] = banzone_valid
        if not banzone_valid:
            errors.append(f"[{plan_id}] {ERROR_BANZONE}: {banzone_error}")
        
        # 检查超时
        elapsed_ms = (time.time() - start_time) * 1000
        if elapsed_ms > config.timeout_ms:
            errors.append(f"{ERROR_TIMEOUT}: L1 validation exceeded {config.timeout_ms}ms")
            return ValidationResult(
                level="L1",
                passed=False,
                duration_ms=elapsed_ms,
                checks=checks,
                errors=errors,
                timestamp=datetime.now().isoformat()
            )
        
        # 检查2: 能耗
        energy_valid, energy_error, _ = check_energy_constraint(
            waypoints, device_profile, battery_percent, config.energy_margin_percent
        )
        checks[f"{plan_id}_energy"] = energy_valid
        if not energy_valid:
            errors.append(f"[{plan_id}] {ERROR_ENERGY}: {energy_error}")
        
        # 检查3: 飞行时间（从设备配置读取最大续航时间）
        max_flight_time = device_profile.max_endurance_min
        logger.debug(f"设备 {device_id} 最大续航: {max_flight_time}min")
        time_valid, time_error, estimated_time = check_flight_time_constraint(
            waypoints,
            device_profile.energy_params.cruise_speed_ms,
            max_flight_time,
            config.max_flight_time_margin
        )
        if not time_valid:
            logger.warning(f"航线 {plan_id} 飞行时间超限: 预计{estimated_time:.1f}min, 允许{max_flight_time * config.max_flight_time_margin:.1f}min")
        checks[f"{plan_id}_flight_time"] = time_valid
        if not time_valid:
            errors.append(f"[{plan_id}] {ERROR_FLIGHT_TIME}: {time_error}")
        
        # 关键日志：检查结果汇总
        logger.info(f"[L1] 航线 {plan_id} 检查结果: banzone={banzone_valid}, energy={energy_valid}, time={time_valid}")
    
    elapsed_ms = (time.time() - start_time) * 1000
    passed = all(checks.values()) if checks else True
    
    return ValidationResult(
        level="L1",
        passed=passed,
        duration_ms=elapsed_ms,
        checks=checks,
        errors=errors,
        timestamp=datetime.now().isoformat()
    )


async def l1_validation_node(state: ReconSchedulerState) -> dict:
    """
    L1 验证 LangGraph 节点
    
    在 flight_planning 之后、timeline_scheduling 之前执行。
    集成熔断器保护：连续失败3次后进入熔断状态。
    
    输入: state.flight_plans, state.environment_assessment.no_fly_zones
    输出: state.l1_result, state.validation_level, state.breaker_state
    """
    from ..rate_limiter import acquire_device_rate_limit, RateLimitExceededError
    from src.agents.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
    
    logger.info("进入 L1 验证节点")
    
    # 获取熔断器
    l1_breaker = get_circuit_breaker(
        name="l1_validation",
        failure_threshold=3,
        recovery_timeout=60.0,
        timeout=L1_TIMEOUT_MS / 1000
    )
    
    # 检查熔断器状态
    breaker_state = state.get("breaker_state", "closed")
    if l1_breaker.state.value == "open":
        logger.warning("L1 breaker is OPEN, entering fail-safe mode")
        return {
            "l1_result": ValidationResult(
                level="L1",
                passed=False,
                duration_ms=0,
                checks={},
                errors=["CIRCUIT_BREAKER_OPEN: L1 validation breaker is open"],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L1",
            "current_phase": "l1_validation",
            "breaker_state": "open",
            "fail_safe_triggered": True,
            "safe_mode_action": "HOVER",  # 进入悬停等待
        }
    
    flight_plans = state.get("flight_plans", [])
    if not flight_plans:
        logger.warning("No flight plans to validate")
        return {
            "l1_result": ValidationResult(
                level="L1",
                passed=True,
                duration_ms=0,
                checks={},
                errors=[],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L1",
            "current_phase": "l1_validation",
            "breaker_state": breaker_state,
        }
    
    # 检查设备级限流
    try:
        await acquire_device_rate_limit(state)
    except RateLimitExceededError as e:
        logger.warning(f"Device rate limited: {e}")
        return {
            "l1_result": ValidationResult(
                level="L1",
                passed=False,
                duration_ms=0,
                checks={},
                errors=[f"RATE_LIMITED(4002): {e.key}, retry_after={e.retry_after:.1f}s"],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L1",
            "current_phase": "l1_validation",
            "breaker_state": breaker_state,
        }
    
    # 获取禁飞区
    env = state.get("environment_assessment") or {}
    no_fly_zones = env.get("no_fly_zones", [])
    
    # 获取电量 (从 state 或默认值)
    battery_percent = state.get("battery_percent", 100.0)
    
    # 执行验证 (通过熔断器)
    l1_breaker_failures = state.get("l1_breaker_failures", 0)
    result = None
    
    try:
        result = await l1_breaker.call_async(
            run_l1_validation,
            flight_plans, no_fly_zones, battery_percent
        )
        # 成功：重置失败计数
        l1_breaker_failures = 0
        
    except CircuitBreakerOpen as e:
        logger.error(f"L1 breaker opened: {e}")
        result = ValidationResult(
            level="L1",
            passed=False,
            duration_ms=0,
            checks={},
            errors=[f"CIRCUIT_BREAKER_OPEN: remaining={e.remaining_time:.1f}s"],
            timestamp=datetime.now().isoformat()
        )
        breaker_state = "open"
        
    except asyncio.TimeoutError:
        logger.error("L1 validation timeout")
        result = ValidationResult(
            level="L1",
            passed=False,
            duration_ms=L1_TIMEOUT_MS,
            checks={},
            errors=[f"{ERROR_TIMEOUT}: L1 validation exceeded {L1_TIMEOUT_MS}ms"],
            timestamp=datetime.now().isoformat()
        )
        l1_breaker_failures += 1
        
    except Exception as e:
        logger.error(f"L1 validation error: {e}")
        result = ValidationResult(
            level="L1",
            passed=False,
            duration_ms=0,
            checks={},
            errors=[f"L1_ERROR: {str(e)}"],
            timestamp=datetime.now().isoformat()
        )
        l1_breaker_failures += 1
    
    # 更新重试计数 (如果验证失败)
    updates: dict[str, Any] = {
        "l1_result": result,
        "validation_level": "L1",
        "current_phase": "l1_validation",
        "breaker_state": l1_breaker.state.value,
        "l1_breaker_failures": l1_breaker_failures,
    }
    
    if not result["passed"]:
        retry_count = state.get("retry_count", 0) + 1
        updates["retry_count"] = retry_count
        logger.warning(f"L1 validation failed, retry_count={retry_count}, breaker_failures={l1_breaker_failures}")
    
    logger.info(f"L1 验证完成: passed={result['passed']}, duration={result['duration_ms']:.1f}ms, breaker={updates['breaker_state']}")
    
    return updates
