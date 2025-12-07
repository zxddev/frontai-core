"""
L2 深度验证节点

基于 spec.md Requirement: Hierarchical Validation (L1 fast, L2 deep) 实现。

L2 验证内容 (5s超时, 允许1次7.5s重试):
- 3D 地形碰撞检测 (DEM-based terrain following)
- 动态能耗验证 (wind/temp/payload factors)
- 通信覆盖验证

特点:
- 包含 DEM 文件读取 (缓存后续调用)
- 超时后允许1次重试 (1.5x timeout = 7.5s)
- 部分结果不复用, 每次验证独立
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from ..state import ReconSchedulerState, ValidationResult
from ..terrain_checker import get_terrain_checker
from ..energy_model import calculate_energy, EnergyCalculator
from ..mock_data import get_comm_provider, get_device_provider, Point3D

logger = logging.getLogger(__name__)

# L2 超时配置
L2_TIMEOUT_S = 5.0
L2_RETRY_TIMEOUT_S = 7.5  # 1.5x
L2_MAX_RETRIES = 1

# 错误码
ERROR_TERRAIN_COLLISION = "TERRAIN_COLLISION"
ERROR_ENERGY_EXCEEDED = "ENERGY_EXCEEDED"
ERROR_COMM_BLIND_ZONE = "COMM_BLIND_ZONE"
ERROR_TIMEOUT = "VALIDATION_TIMEOUT"


@dataclass
class L2Config:
    """L2验证配置"""
    timeout_s: float = L2_TIMEOUT_S
    retry_timeout_s: float = L2_RETRY_TIMEOUT_S
    max_retries: int = L2_MAX_RETRIES
    terrain_clearance_m: float = 30.0
    energy_margin_percent: float = 15.0
    signal_threshold_dbm: float = -90.0


async def check_terrain_collision(
    waypoints: list[dict],
    config: L2Config
) -> tuple[bool, Optional[str], dict]:
    """
    3D 地形碰撞检测
    
    Returns:
        (is_valid, error_message, details)
    """
    checker = get_terrain_checker(use_mock=True)
    result = checker.check_terrain_collision(waypoints, config.terrain_clearance_m)
    
    if result.has_collision:
        return False, f"Terrain collision detected at {len(result.collision_points)} points", {
            "collision_points": result.collision_points[:3],  # 只返回前3个
            "min_clearance_m": result.min_clearance_m,
            "max_ground_m": result.max_ground_elevation_m,
        }
    
    return True, None, {
        "min_clearance_m": result.min_clearance_m,
        "max_ground_m": result.max_ground_elevation_m,
    }


async def check_dynamic_energy(
    waypoints: list[dict],
    device_id: str,
    battery_percent: float,
    weather: dict,
    config: L2Config
) -> tuple[bool, Optional[str], dict]:
    """
    动态能耗验证 (完整模型)
    
    Returns:
        (is_valid, error_message, details)
    """
    device_provider = get_device_provider()
    profile = await device_provider.get_device_profile(device_id)
    
    if not profile:
        return False, f"Device not found: {device_id}", {}
    
    # 计算总距离和高度变化
    total_distance = 0.0
    total_climb = 0.0
    
    for i in range(len(waypoints) - 1):
        wp1, wp2 = waypoints[i], waypoints[i+1]
        # 简化距离计算
        dlat = (wp2["lat"] - wp1["lat"]) * 111000
        dlng = (wp2["lng"] - wp1["lng"]) * 111000 * 0.85  # 纬度修正
        dist = (dlat**2 + dlng**2) ** 0.5
        total_distance += dist
        
        alt_diff = wp2.get("alt_m", 0) - wp1.get("alt_m", 0)
        if alt_diff > 0:
            total_climb += alt_diff
    
    # 获取天气参数
    wind_speed = weather.get("wind_speed_ms", 0)
    wind_dir = weather.get("wind_direction_deg", 0)
    temp = weather.get("temperature_c", 25)
    
    # 估算平均航向 (简化: 使用第一段)
    if len(waypoints) >= 2:
        import math
        dlat = waypoints[1]["lat"] - waypoints[0]["lat"]
        dlng = waypoints[1]["lng"] - waypoints[0]["lng"]
        heading = math.degrees(math.atan2(dlng, dlat)) % 360
    else:
        heading = 0
    
    # 计算能耗
    energy = calculate_energy(
        distance_m=total_distance,
        altitude_gain_m=total_climb,
        hover_time_s=0,  # L2暂不考虑悬停
        wind_speed_ms=wind_speed,
        wind_direction_deg=wind_dir,
        heading_deg=heading,
        temp_c=temp,
        payload_kg=0,
        device_profile=profile,
    )
    
    available = battery_percent - config.energy_margin_percent
    
    if energy > available:
        return False, f"Energy required ({energy:.1f}%) exceeds available ({available:.1f}%)", {
            "required_percent": energy,
            "available_percent": available,
            "distance_m": total_distance,
            "climb_m": total_climb,
        }
    
    return True, None, {
        "required_percent": energy,
        "available_percent": available,
        "margin_percent": available - energy,
    }


async def check_comm_coverage(
    waypoints: list[dict],
    config: L2Config
) -> tuple[bool, Optional[str], dict]:
    """
    通信覆盖验证
    
    Returns:
        (is_valid, error_message, details)
    """
    comm_provider = get_comm_provider()
    
    # 构建路径点
    path = [
        Point3D(lat=wp["lat"], lng=wp["lng"], alt=wp.get("alt_m", 100))
        for wp in waypoints
    ]
    
    # 检测盲区
    blind_zones = await comm_provider.find_blind_zones(path, config.signal_threshold_dbm)
    
    if blind_zones:
        # 获取详细信息
        coverage = await comm_provider.predict_coverage_along_path(path)
        min_signal = min(r.signal_dbm for r in coverage)
        
        return False, f"Communication blind zones detected: {len(blind_zones)} segments", {
            "blind_zones": blind_zones,
            "min_signal_dbm": min_signal,
            "threshold_dbm": config.signal_threshold_dbm,
        }
    
    return True, None, {"coverage_ok": True}


async def run_l2_validation(
    flight_plans: list[dict],
    battery_percent: float,
    weather: dict,
    config: L2Config = None
) -> ValidationResult:
    """
    执行 L2 验证
    
    Args:
        flight_plans: 航线计划列表
        battery_percent: 当前电量
        weather: 天气条件
        config: 验证配置
    
    Returns:
        验证结果
    """
    config = config or L2Config()
    start_time = time.time()
    
    checks: dict[str, bool] = {}
    errors: list[str] = []
    details: dict[str, Any] = {}
    
    for plan in flight_plans:
        plan_id = plan.get("plan_id", "unknown")
        device_id = plan.get("device_id")
        waypoints = plan.get("waypoints", [])
        
        if not waypoints:
            continue
        
        # 检查1: 地形碰撞
        terrain_ok, terrain_err, terrain_detail = await check_terrain_collision(waypoints, config)
        checks[f"{plan_id}_terrain"] = terrain_ok
        if not terrain_ok:
            errors.append(f"[{plan_id}] {ERROR_TERRAIN_COLLISION}: {terrain_err}")
        details[f"{plan_id}_terrain"] = terrain_detail
        
        # 检查超时
        elapsed = time.time() - start_time
        if elapsed > config.timeout_s:
            errors.append(f"{ERROR_TIMEOUT}: L2 validation exceeded {config.timeout_s}s")
            return ValidationResult(
                level="L2",
                passed=False,
                duration_ms=elapsed * 1000,
                checks=checks,
                errors=errors,
                timestamp=datetime.now().isoformat()
            )
        
        # 检查2: 动态能耗
        energy_ok, energy_err, energy_detail = await check_dynamic_energy(
            waypoints, device_id, battery_percent, weather, config
        )
        checks[f"{plan_id}_energy"] = energy_ok
        if not energy_ok:
            errors.append(f"[{plan_id}] {ERROR_ENERGY_EXCEEDED}: {energy_err}")
        details[f"{plan_id}_energy"] = energy_detail
        
        # 检查3: 通信覆盖
        comm_ok, comm_err, comm_detail = await check_comm_coverage(waypoints, config)
        checks[f"{plan_id}_comm"] = comm_ok
        if not comm_ok:
            errors.append(f"[{plan_id}] {ERROR_COMM_BLIND_ZONE}: {comm_err}")
        details[f"{plan_id}_comm"] = comm_detail
    
    elapsed_ms = (time.time() - start_time) * 1000
    passed = all(checks.values()) if checks else True
    
    return ValidationResult(
        level="L2",
        passed=passed,
        duration_ms=elapsed_ms,
        checks=checks,
        errors=errors,
        timestamp=datetime.now().isoformat()
    )


async def l2_validation_node(state: ReconSchedulerState) -> dict:
    """
    L2 验证 LangGraph 节点
    
    在 L1 验证之后执行。
    集成熔断器、信号量和限流器。
    
    输入: state.flight_plans, state.environment_assessment, state.battery_percent
    输出: state.l2_result, state.validation_level, state.breaker_state
    """
    from ..rate_limiter import (
        L2_SEMAPHORE, L2_RATE_LIMITER, 
        RateLimitExceededError, QueueTimeoutError
    )
    from src.agents.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
    
    logger.info("进入 L2 验证节点")
    
    # 获取熔断器
    l2_breaker = get_circuit_breaker(
        name="l2_validation",
        failure_threshold=3,
        recovery_timeout=120.0,
        timeout=L2_TIMEOUT_S
    )
    
    # 检查熔断器状态
    breaker_state = state.get("breaker_state", "closed")
    l2_breaker_failures = state.get("l2_breaker_failures", 0)
    
    if l2_breaker.state.value == "open":
        logger.warning("L2 breaker is OPEN, entering fail-safe mode")
        return {
            "l2_result": ValidationResult(
                level="L2",
                passed=False,
                duration_ms=0,
                checks={},
                errors=["CIRCUIT_BREAKER_OPEN: L2 validation breaker is open"],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L2",
            "current_phase": "l2_validation",
            "breaker_state": "open",
            "fail_safe_triggered": True,
            "safe_mode_action": "RTH",  # L2熔断直接RTH
        }
    
    flight_plans = state.get("flight_plans", [])
    if not flight_plans:
        logger.warning("No flight plans to validate")
        return {
            "l2_result": ValidationResult(
                level="L2",
                passed=True,
                duration_ms=0,
                checks={},
                errors=[],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L2",
            "current_phase": "l2_validation",
            "breaker_state": breaker_state,
        }
    
    # 检查全局L2限流
    try:
        await L2_RATE_LIMITER.acquire()
    except RateLimitExceededError as e:
        logger.warning(f"L2 global rate limited: {e}")
        return {
            "l2_result": ValidationResult(
                level="L2",
                passed=False,
                duration_ms=0,
                checks={},
                errors=[f"RATE_LIMITED(4002): L2 global limit exceeded, retry_after={e.retry_after:.1f}s"],
                timestamp=datetime.now().isoformat()
            ),
            "validation_level": "L2",
            "current_phase": "l2_validation",
            "breaker_state": breaker_state,
        }
    
    # 获取参数
    battery_percent = state.get("battery_percent", 100.0)
    env = state.get("environment_assessment") or {}
    weather = env.get("weather", {})
    
    config = L2Config()
    attempt = 0
    result = None
    
    # 通过信号量控制并发
    try:
        async with L2_SEMAPHORE:
            while attempt <= config.max_retries:
                timeout = config.timeout_s if attempt == 0 else config.retry_timeout_s
                
                try:
                    result = await l2_breaker.call_async(
                        run_l2_validation,
                        flight_plans, battery_percent, weather, config
                    )
                    
                    # 成功：重置失败计数
                    l2_breaker_failures = 0
                    
                    # 如果成功或非超时错误，直接返回
                    if result["passed"] or ERROR_TIMEOUT not in str(result.get("errors", [])):
                        break
                        
                except CircuitBreakerOpen as e:
                    logger.error(f"L2 breaker opened: {e}")
                    result = ValidationResult(
                        level="L2",
                        passed=False,
                        duration_ms=0,
                        checks={},
                        errors=[f"CIRCUIT_BREAKER_OPEN: remaining={e.remaining_time:.1f}s"],
                        timestamp=datetime.now().isoformat()
                    )
                    breaker_state = "open"
                    break
                    
                except asyncio.TimeoutError:
                    logger.warning(f"L2 validation timeout (attempt {attempt + 1})")
                    result = ValidationResult(
                        level="L2",
                        passed=False,
                        duration_ms=timeout * 1000,
                        checks={},
                        errors=[f"{ERROR_TIMEOUT}: L2 validation exceeded {timeout}s (attempt {attempt + 1})"],
                        timestamp=datetime.now().isoformat()
                    )
                    l2_breaker_failures += 1
                    
                except Exception as e:
                    logger.error(f"L2 validation error: {e}")
                    result = ValidationResult(
                        level="L2",
                        passed=False,
                        duration_ms=0,
                        checks={},
                        errors=[f"L2_ERROR: {str(e)}"],
                        timestamp=datetime.now().isoformat()
                    )
                    l2_breaker_failures += 1
                    break
                
                attempt += 1
                
    except QueueTimeoutError as e:
        logger.error(f"L2 semaphore timeout: {e}")
        result = ValidationResult(
            level="L2",
            passed=False,
            duration_ms=0,
            checks={},
            errors=[f"QUEUE_TIMEOUT(4001): L2 semaphore wait exceeded {e.timeout}s"],
            timestamp=datetime.now().isoformat()
        )
    
    # 更新状态
    updates: dict[str, Any] = {
        "l2_result": result,
        "validation_level": "L2",
        "current_phase": "l2_validation",
        "breaker_state": l2_breaker.state.value,
        "l2_breaker_failures": l2_breaker_failures,
    }
    
    if not result["passed"]:
        retry_count = state.get("retry_count", 0) + 1
        updates["retry_count"] = retry_count
        logger.warning(f"L2 validation failed, retry_count={retry_count}, breaker_failures={l2_breaker_failures}")
    
    logger.info(f"L2 验证完成: passed={result['passed']}, duration={result['duration_ms']:.1f}ms, breaker={updates['breaker_state']}")
    
    return updates
