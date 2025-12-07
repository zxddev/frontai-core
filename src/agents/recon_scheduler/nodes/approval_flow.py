"""
人工审批流程节点

基于 spec.md Requirement: Retry Budget, Circuit Breaker, and Human-Authorized Degradation 实现。

流程:
1. approval_required_node: 发出APPROVAL_REQUIRED事件, 进入等待
2. wait_for_approval_node: 等待人工响应 (300s超时)
3. execute_degradation_node: 执行批准的降级策略

降级选项 (来自spec):
- REDUCE_ALTITUDE: 降低飞行高度
- REDUCE_COVERAGE: 减少覆盖范围
- SWITCH_DEVICE: 切换备用设备
- PERIMETER_ONLY: 仅执行周边扫描

特殊情况:
- 超时 + 信号丢失: 自主RTH (无需ACK)
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from ..state import (
    ReconSchedulerState,
    ApprovalStatus,
    DegradationOption,
    SafeModeAction,
    ApprovalRequest,
)
from ..emitter import get_emitter

logger = logging.getLogger(__name__)

# 配置常量 (来自spec)
APPROVAL_TIMEOUT_S = 300
SAFE_MODE_OPTIONS = [
    SafeModeAction.HOVER,
    SafeModeAction.RTH,
    SafeModeAction.EMERGENCY_LAND,
]
DEGRADATION_OPTIONS = [
    DegradationOption.REDUCE_ALTITUDE,
    DegradationOption.REDUCE_COVERAGE,
    DegradationOption.SWITCH_DEVICE,
    DegradationOption.PERIMETER_ONLY,
]


async def approval_required_node(state: ReconSchedulerState) -> dict:
    """
    审批请求节点
    
    当验证失败超过重试次数时触发。
    发出APPROVAL_REQUIRED事件并进入等待状态。
    """
    logger.info("进入审批请求节点")
    
    mission_id = state.get("event_id", "unknown")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    # 生成审批请求
    request_id = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(seconds=APPROVAL_TIMEOUT_S)).isoformat()
    
    # 确定失败原因
    l1_result = state.get("l1_result", {})
    l2_result = state.get("l2_result", {})
    
    errors = []
    if l1_result and not l1_result.get("passed", True):
        errors.extend(l1_result.get("errors", []))
    if l2_result and not l2_result.get("passed", True):
        errors.extend(l2_result.get("errors", []))
    
    reason = "; ".join(errors[:3]) if errors else "Validation failed"
    
    approval_request: ApprovalRequest = {
        "request_id": request_id,
        "mission_id": mission_id,
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "degradation_options": [opt.value for opt in DEGRADATION_OPTIONS],
        "current_status": "WAITING_APPROVAL",
        "expires_at": expires_at,
    }
    
    # 发送APPROVAL_REQUIRED事件
    emitter = get_emitter()
    await emitter.emit_health(
        mission_id=mission_id,
        device_id=state.get("flight_plans", [{}])[0].get("device_id", "unknown"),
        metric_name="APPROVAL_REQUIRED",
        metric_value={
            "request_id": request_id,
            "reason": reason,
            "options": [opt.value for opt in DEGRADATION_OPTIONS],
            "expires_at": expires_at,
        },
        severity="WARN"
    )
    
    # 进入安全模式 (悬停)
    logger.warning(f"Approval required: {reason}")
    
    return {
        "approval_status": ApprovalStatus.PENDING.value,
        "approval_request": approval_request,
        "approval_timeout_s": APPROVAL_TIMEOUT_S,
        "degradation_options": [opt.value for opt in DEGRADATION_OPTIONS],
        "safe_mode_action": SafeModeAction.HOVER.value,
        "current_phase": "approval_required",
    }


async def wait_for_approval_node(state: ReconSchedulerState) -> dict:
    """
    等待审批节点
    
    等待人工响应或超时。
    
    在实际实现中, 这个节点会:
    1. 轮询外部审批状态API
    2. 或通过WebSocket接收审批结果
    
    Mock实现: 模拟等待并检查state中的审批结果
    """
    logger.info("进入等待审批节点")
    
    approval_request = state.get("approval_request")
    if not approval_request:
        logger.warning("No approval request found")
        return {
            "approval_status": ApprovalStatus.TIMEOUT.value,
            "current_phase": "wait_for_approval",
        }
    
    # 检查是否已有审批结果 (可能从外部设置)
    approved_degradation = state.get("approved_degradation")
    if approved_degradation:
        logger.info(f"Approval received: {approved_degradation}")
        return {
            "approval_status": ApprovalStatus.APPROVED.value,
            "current_phase": "wait_for_approval",
        }
    
    # 检查是否被拒绝
    if state.get("approval_rejected"):
        logger.info("Approval rejected by human")
        return {
            "approval_status": ApprovalStatus.REJECTED.value,
            "current_phase": "wait_for_approval",
        }
    
    # 检查超时
    expires_at = approval_request.get("expires_at")
    if expires_at:
        try:
            expire_time = datetime.fromisoformat(expires_at)
            if datetime.now() > expire_time:
                logger.warning("Approval timeout")
                
                # 检查是否信号丢失 - 自主RTH
                signal_lost = state.get("signal_lost_since")
                if signal_lost:
                    logger.warning("Signal lost + approval timeout -> autonomous RTH")
                    return {
                        "approval_status": ApprovalStatus.TIMEOUT.value,
                        "safe_mode_action": SafeModeAction.RTH.value,
                        "rth_triggers": state.get("rth_triggers", []) + ["APPROVAL_TIMEOUT_COMM_LOST"],
                        "current_phase": "wait_for_approval",
                    }
                
                return {
                    "approval_status": ApprovalStatus.TIMEOUT.value,
                    "safe_mode_action": SafeModeAction.RTH.value,
                    "rth_triggers": state.get("rth_triggers", []) + ["APPROVAL_TIMEOUT"],
                    "current_phase": "wait_for_approval",
                }
        except (ValueError, TypeError):
            pass
    
    # 模拟: 在实际实现中这里会有等待逻辑
    # 这里直接返回待定状态, 由外部触发下一步
    return {
        "approval_status": ApprovalStatus.PENDING.value,
        "current_phase": "wait_for_approval",
    }


async def execute_degradation_node(state: ReconSchedulerState) -> dict:
    """
    执行降级策略节点
    
    根据批准的降级选项调整任务参数并重新规划。
    """
    logger.info("进入执行降级节点")
    
    approved = state.get("approved_degradation")
    if not approved:
        logger.warning("No approved degradation found")
        return {
            "current_phase": "execute_degradation",
        }
    
    mission_id = state.get("event_id", "unknown")
    flight_plans = state.get("flight_plans", [])
    
    # 根据降级选项调整参数
    adjustments = {}
    
    if approved == DegradationOption.REDUCE_ALTITUDE.value:
        # 降低飞行高度 20%
        adjustments["altitude_reduction"] = 0.2
        for plan in flight_plans:
            for wp in plan.get("waypoints", []):
                if "alt_m" in wp:
                    wp["alt_m"] = wp["alt_m"] * 0.8
        logger.info("Applied REDUCE_ALTITUDE: -20%")
    
    elif approved == DegradationOption.REDUCE_COVERAGE.value:
        # 减少覆盖范围 (保留前50%航点)
        adjustments["coverage_reduction"] = 0.5
        for plan in flight_plans:
            waypoints = plan.get("waypoints", [])
            if len(waypoints) > 2:
                plan["waypoints"] = waypoints[:len(waypoints)//2 + 1]
        logger.info("Applied REDUCE_COVERAGE: 50%")
    
    elif approved == DegradationOption.PERIMETER_ONLY.value:
        # 仅执行周边扫描 (保留起点和终点)
        adjustments["perimeter_only"] = True
        for plan in flight_plans:
            waypoints = plan.get("waypoints", [])
            if len(waypoints) > 2:
                plan["waypoints"] = [waypoints[0], waypoints[-1]]
        logger.info("Applied PERIMETER_ONLY")
    
    elif approved == DegradationOption.SWITCH_DEVICE.value:
        # 切换设备 (需要外部处理)
        adjustments["switch_device"] = True
        logger.info("SWITCH_DEVICE requested - requires external handling")
    
    # 发送降级执行事件
    emitter = get_emitter()
    await emitter.emit_health(
        mission_id=mission_id,
        device_id=flight_plans[0].get("device_id", "unknown") if flight_plans else "unknown",
        metric_name="DEGRADATION_EXECUTED",
        metric_value={
            "degradation_type": approved,
            "adjustments": adjustments,
        },
        severity="INFO"
    )
    
    # 重置重试计数, 准备重新验证
    return {
        "flight_plans": flight_plans,
        "retry_count": 0,  # 重置
        "approval_status": ApprovalStatus.NOT_REQUIRED.value,
        "approved_degradation": None,  # 清除
        "current_phase": "execute_degradation",
    }


def should_require_approval(state: ReconSchedulerState) -> bool:
    """
    判断是否需要人工审批 (用于条件边)
    """
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    # 超过重试次数
    if retry_count >= max_retries:
        return True
    
    return False


def should_continue_after_approval(state: ReconSchedulerState) -> str:
    """
    判断审批后的下一步 (用于条件边)
    
    Returns:
        "execute_degradation" | "emergency_rth" | "wait"
    """
    approval_status = state.get("approval_status")
    
    if approval_status == ApprovalStatus.APPROVED.value:
        return "execute_degradation"
    
    if approval_status in [ApprovalStatus.TIMEOUT.value, ApprovalStatus.REJECTED.value]:
        return "emergency_rth"
    
    # 仍在等待
    return "wait"
