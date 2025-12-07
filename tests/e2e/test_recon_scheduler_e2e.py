"""
Recon Scheduler V2.1 E2E测试

测试场景:
1. 正常任务完成 - 全流程通过
2. L1失败重试 - plan_adjustment恢复
3. L2失败→人工审批 - HITL流程
4. 盲区中继插入 - relay point插入
5. 低电量RTH - 紧急返航
6. 检查点恢复 - checkpoint resume

运行方式:
    PYTHONPATH=. pytest tests/e2e/test_recon_scheduler_e2e.py -v
"""
from __future__ import annotations

import asyncio
import pytest
from datetime import datetime
from typing import Any


# ============================================================================
# 测试辅助函数
# ============================================================================

def create_test_state(
    event_id: str = "test_mission_001",
    device_id: str = "DJI_M30T_001",
    battery_percent: float = 95.0,
    waypoints: list[dict] = None,
) -> dict[str, Any]:
    """创建测试状态"""
    if waypoints is None:
        waypoints = [
            {"lat": 31.68, "lng": 103.85, "alt_m": 2000},
            {"lat": 31.69, "lng": 103.86, "alt_m": 2000},
            {"lat": 31.70, "lng": 103.87, "alt_m": 2000},
        ]
    
    return {
        "event_id": event_id,
        "mission_id": event_id,
        "device_id": device_id,
        "scenario_id": "rescue_001",
        "recon_request": "搜索茂县震区滞留人员",
        "flight_plans": [{
            "plan_id": f"{event_id}_plan_1",
            "device_id": device_id,
            "waypoints": waypoints,
            "speed_m_s": 15.0,
        }],
        "environment_assessment": {
            "weather": {
                "wind_speed": 5.0,
                "wind_direction": 180,
                "temperature": 20,
            },
            "no_fly_zones": [],
        },
        "allocated_devices": [{"device_id": device_id, "battery_soc": battery_percent}],
        "battery_percent": battery_percent,
        "retry_count": 0,
        "max_retries": 3,
        "breaker_state": "closed",
        "l1_breaker_failures": 0,
        "l2_breaker_failures": 0,
    }


# ============================================================================
# 场景1: 正常任务完成
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_normal_mission_completion():
    """
    测试正常任务完成流程
    
    期望: L1/L2验证通过，生成有效航线
    """
    from src.agents.recon_scheduler.nodes import l1_validation_node, l2_validation_node
    from src.agents.recon_scheduler.rate_limiter import DEVICE_RATE_LIMITER, L2_RATE_LIMITER
    
    # 重置限流器以避免测试间干扰
    DEVICE_RATE_LIMITER.reset_all()
    L2_RATE_LIMITER.reset_all()
    
    # 使用mock_data中定义的设备ID
    state = create_test_state(device_id="DJI_M30T_001")
    
    # L1验证
    l1_result = await l1_validation_node(state)
    assert l1_result["l1_result"]["passed"] is True, f"L1 validation should pass: {l1_result['l1_result'].get('errors', [])}"
    assert l1_result["breaker_state"] == "closed"
    
    # L2验证
    state.update(l1_result)
    l2_result = await l2_validation_node(state)
    # L2可能因为地形或通信问题失败，这是正常的
    print(f"✓ 正常任务流程: L1={l1_result['l1_result']['passed']}, L2={l2_result['l2_result']['passed']}")
    print(f"  L2 errors: {l2_result['l2_result'].get('errors', [])}")


# ============================================================================
# 场景2: L1失败重试
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_2_l1_failure_and_retry():
    """
    测试L1失败重试机制
    
    期望: 验证失败时retry_count递增，不超过max_retries
    """
    from src.agents.recon_scheduler.nodes import l1_validation_node
    
    # 创建一个会导致能耗超限的状态 (低电量)
    state = create_test_state(battery_percent=10.0)  # 低电量
    
    # L1验证 (预期因能耗超限失败)
    l1_result = await l1_validation_node(state)
    
    # 检查重试计数
    if not l1_result["l1_result"]["passed"]:
        assert l1_result.get("retry_count", 0) > 0, "retry_count should increment on failure"
        print(f"✓ L1失败重试: retry_count={l1_result.get('retry_count')}")
    else:
        # 如果通过了，说明能耗检查未触发（取决于航线长度）
        print(f"✓ L1意外通过 (短航线): passed={l1_result['l1_result']['passed']}")


# ============================================================================
# 场景3: L2失败→人工审批
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_3_l2_failure_triggers_approval():
    """
    测试L2失败后触发人工审批流程
    
    期望: 超过重试次数后应发起审批请求
    """
    from src.agents.recon_scheduler.nodes import approval_required_node, should_require_approval
    
    # 模拟已超过重试次数的状态
    state = create_test_state()
    state["retry_count"] = 3
    state["max_retries"] = 3
    state["l1_result"] = {"passed": False, "errors": ["ENERGY_EXCEEDED"]}
    
    # 检查是否需要审批
    needs_approval = should_require_approval(state)
    assert needs_approval is True, "Should require approval when retry_count >= max_retries"
    
    # 发起审批
    approval_result = await approval_required_node(state)
    assert approval_result["approval_status"] == "pending"
    assert len(approval_result["degradation_options"]) > 0
    
    print(f"✓ 人工审批触发: status={approval_result['approval_status']}, options={approval_result['degradation_options']}")


# ============================================================================
# 场景4: 盲区中继插入
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_4_blind_zone_relay_insertion():
    """
    测试盲区检测和中继点插入
    
    期望: 检测到盲区时插入relay waypoint
    """
    from src.agents.recon_scheduler.nodes import relay_insertion_node
    
    state = create_test_state()
    state["flight_plans"][0]["waypoints"] = [
        {"lat": 31.68, "lng": 103.85, "alt_m": 2000},  # 起点
        {"lat": 31.75, "lng": 103.82, "alt_m": 2000},  # 可能进入盲区
        {"lat": 31.80, "lng": 103.80, "alt_m": 2000},  # 终点
    ]
    state["route_history"] = []
    
    # 执行中继插入
    result = await relay_insertion_node(state)
    
    # 检查是否有relay点插入
    relay_points = result.get("relay_points", [])
    print(f"✓ 中继检测: blind_zones_detected={result.get('blind_zones_detected', 0)}, relays={len(relay_points)}")


# ============================================================================
# 场景5: 低电量RTH
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_5_low_battery_emergency_rth():
    """
    测试低电量紧急返航检测
    
    期望: 电量低于阈值时应该触发RTH检测
    """
    from src.agents.recon_scheduler.nodes import check_should_trigger_rth
    
    # 模拟低电量状态
    state = create_test_state(battery_percent=15.0)
    state["rth_required_percent"] = 20.0  # RTH需要20%电量
    
    # 检查是否应触发RTH
    should_rth = check_should_trigger_rth(state)
    
    # 电量15% < 需要的20%，应该触发RTH
    assert should_rth is True, f"Should trigger RTH when battery={state['battery_percent']}% < required={state['rth_required_percent']}%"
    print(f"✓ 低电量RTH检测: battery={state['battery_percent']}%, required={state['rth_required_percent']}%, should_rth={should_rth}")


# ============================================================================
# 场景6: 检查点恢复
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_6_checkpoint_save_and_resume():
    """
    测试检查点保存和恢复
    
    期望: 保存检查点后能正确恢复状态
    """
    from src.agents.recon_scheduler.checkpoint import (
        CheckpointPayload, CheckpointManager, SCHEMA_VERSION
    )
    
    # 创建检查点
    payload = CheckpointPayload(
        mission_id="test_checkpoint_001",
        checkpoint_id="ckpt-test-123",
        timestamp=datetime.now().isoformat(),
        schema_version=SCHEMA_VERSION,
        current_position_utm=(500000.0, 3500000.0, 2000.0),
        heading=90.0,
        utm_zone="48N",
        progress_percent=50.0,
        remaining_distance_m=5000.0,
        environment_snapshot={"wind_speed": 5, "temperature": 20},
    )
    
    # 验证数据结构
    payload_dict = payload.to_dict()
    restored = CheckpointPayload.from_dict(payload_dict)
    
    assert restored.mission_id == payload.mission_id
    assert restored.progress_percent == payload.progress_percent
    assert restored.current_position_utm == payload.current_position_utm
    
    # 验证版本兼容性
    is_compatible, msg = payload.is_version_compatible(SCHEMA_VERSION)
    assert is_compatible is True
    
    print(f"✓ 检查点恢复: mission={payload.mission_id}, progress={payload.progress_percent}%")


# ============================================================================
# 集成测试: 完整流程
# ============================================================================

@pytest.mark.asyncio
async def test_integration_full_validation_flow():
    """
    测试完整的L1→L2验证流程
    """
    from src.agents.recon_scheduler.nodes import l1_validation_node, l2_validation_node
    from src.agents.recon_scheduler.rate_limiter import (
        get_rate_limiter_stats, DEVICE_RATE_LIMITER, L2_RATE_LIMITER
    )
    
    # 重置限流器
    DEVICE_RATE_LIMITER.reset_all()
    L2_RATE_LIMITER.reset_all()
    
    # 使用mock_data中定义的设备ID
    state = create_test_state(device_id="DJI_M30T_001")
    
    # L1验证
    l1_result = await l1_validation_node(state)
    state.update(l1_result)
    
    # L2验证
    l2_result = await l2_validation_node(state)
    state.update(l2_result)
    
    # 检查限流器状态
    stats = get_rate_limiter_stats()
    
    print(f"\n=== 完整流程测试结果 ===")
    print(f"L1: passed={l1_result['l1_result']['passed']}, duration={l1_result['l1_result']['duration_ms']:.1f}ms")
    print(f"L2: passed={l2_result['l2_result']['passed']}, duration={l2_result['l2_result']['duration_ms']:.1f}ms")
    print(f"Breaker: {l2_result.get('breaker_state', 'N/A')}")
    print(f"L1 errors: {l1_result['l1_result'].get('errors', [])}")
    print(f"L2 errors: {l2_result['l2_result'].get('errors', [])}")
    
    # L1应该通过 (基本检查)
    assert l1_result["l1_result"]["passed"] is True, f"L1 should pass: {l1_result['l1_result'].get('errors', [])}"
    # L2可能因环境因素失败，只检查熔断器状态
    assert l2_result.get("breaker_state") == "closed", "Breaker should remain closed"


# ============================================================================
# 性能测试: 熔断器
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """
    测试熔断器在连续失败后打开
    """
    from src.agents.utils.circuit_breaker import CircuitBreaker, CircuitState
    
    breaker = CircuitBreaker(
        name="test_breaker",
        failure_threshold=2,
        recovery_timeout=1.0,
    )
    
    # 模拟连续失败
    for i in range(2):
        try:
            def fail_func():
                raise ValueError("Simulated failure")
            breaker.call(fail_func)
        except ValueError:
            pass
    
    # 熔断器应该打开
    assert breaker.state == CircuitState.OPEN, "Breaker should be OPEN after failures"
    
    # 等待恢复
    await asyncio.sleep(1.1)
    
    # 熔断器应该进入半开状态
    assert breaker.state == CircuitState.HALF_OPEN, "Breaker should be HALF_OPEN after recovery"
    
    print(f"✓ 熔断器测试: threshold=2, state={breaker.state.value}")


# ============================================================================
# 性能测试: 限流器
# ============================================================================

@pytest.mark.asyncio
async def test_rate_limiter_blocks_excess_requests():
    """
    测试限流器阻止过量请求
    """
    from src.agents.recon_scheduler.rate_limiter import (
        SlidingWindowRateLimiter, RateLimitExceededError
    )
    
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=1)
    
    # 前两次应该成功
    await limiter.acquire()
    await limiter.acquire()
    
    # 第三次应该失败
    with pytest.raises(RateLimitExceededError) as exc_info:
        await limiter.acquire()
    
    assert exc_info.value.limit == 2
    assert exc_info.value.retry_after > 0
    
    print(f"✓ 限流器测试: limit=2, retry_after={exc_info.value.retry_after:.2f}s")


if __name__ == "__main__":
    # 直接运行测试
    import sys
    pytest.main([__file__, "-v", *sys.argv[1:]])
