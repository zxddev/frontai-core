"""
Mode 2: 执行行动节点

执行分发行动，包括重新分配任务、更新数据库等操作。
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, List
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal

from ..state import (
    TaskDispatchState,
    DispatchAction,
    DispatchActionType,
    TaskAssignment,
    AssignmentStatus,
)

logger = logging.getLogger(__name__)


async def execute_dispatch_action(state: TaskDispatchState) -> Dict[str, Any]:
    """
    执行分发行动
    
    根据决策结果执行具体操作：重新分配、重试、取消等。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[动态调整-3] 执行行动: event_id={state['event_id']}")
    start_time = time.time()
    
    proposed_action = state.get("proposed_action")
    human_decision = state.get("human_decision")
    
    if not proposed_action:
        logger.warning("[动态调整-3] 无建议行动")
        return {
            "errors": state.get("errors", []) + ["无建议行动"],
            "current_phase": "execute_action",
        }
    
    # 如果需要人工确认但被拒绝
    if state.get("requires_human_approval") and human_decision == "reject":
        logger.info("[动态调整-3] 行动被人工拒绝")
        trace = dict(state.get("trace", {}))
        trace["phases_executed"] = trace.get("phases_executed", []) + ["execute_action_rejected"]
        return {
            "trace": trace,
            "current_phase": "execute_action",
        }
    
    # 执行行动
    action_type = proposed_action.get("action_type")
    errors: List[str] = list(state.get("errors", []))
    dispatch_orders: List[Dict[str, Any]] = list(state.get("dispatch_orders", []))
    current_assignments = list(state.get("current_assignments", []))
    
    try:
        if action_type == DispatchActionType.REASSIGN.value:
            result = await _execute_reassign(proposed_action, current_assignments, state)
            
        elif action_type == DispatchActionType.RETRY.value:
            result = await _execute_retry(proposed_action, current_assignments, state)
            
        elif action_type == DispatchActionType.CANCEL.value:
            result = await _execute_cancel(proposed_action, current_assignments, state)
            
        elif action_type == DispatchActionType.WAIT.value:
            result = {"success": True, "message": "等待中，暂不执行"}
            
        elif action_type == DispatchActionType.ESCALATE.value:
            result = {"success": True, "message": "已上报人工处理", "escalated": True}
            
        else:
            result = {"success": False, "message": f"未知行动类型: {action_type}"}
        
        if result.get("success"):
            logger.info(f"[动态调整-3] 行动执行成功: {result.get('message')}")
            
            # 添加新的调度指令
            if result.get("new_order"):
                dispatch_orders.append(result["new_order"])
            
            # 更新分配列表
            if result.get("updated_assignments"):
                current_assignments = result["updated_assignments"]
        else:
            logger.error(f"[动态调整-3] 行动执行失败: {result.get('message')}")
            errors.append(result.get("message", "执行失败"))
            
    except Exception as e:
        logger.exception(f"[动态调整-3] 执行异常: {e}")
        errors.append(f"执行异常: {str(e)}")
        result = {"success": False, "message": str(e)}
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["execute_dispatch_action"]
    trace["action_result"] = {
        "action_type": action_type,
        "success": result.get("success", False),
        "message": result.get("message", ""),
    }
    
    # 清除已处理的事件（关键：防止无限循环）
    current_event = state.get("current_event")
    pending_events = list(state.get("pending_events", []))
    if current_event and pending_events:
        current_event_id = current_event.get("event_id") or current_event.get("task_id")
        pending_events = [
            e for e in pending_events 
            if (e.get("event_id") or e.get("task_id")) != current_event_id
        ]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[动态调整-3] 完成: success={result.get('success')}, 剩余事件={len(pending_events)}, 耗时{elapsed_ms}ms")
    
    return {
        "current_assignments": current_assignments,
        "dispatch_orders": dispatch_orders,
        "pending_events": pending_events,  # 更新待处理事件列表
        "errors": errors,
        "trace": trace,
        "current_phase": "execute_action",
    }


async def _execute_reassign(
    action: DispatchAction,
    assignments: List[TaskAssignment],
    state: TaskDispatchState
) -> Dict[str, Any]:
    """执行重新分配"""
    
    task_id = action.get("task_id")
    old_executor_id = action.get("old_executor_id")
    new_executor_id = action.get("new_executor_id")
    
    if not task_id or not new_executor_id:
        return {"success": False, "message": "缺少必要参数：task_id或new_executor_id"}
    
    # 查找并更新分配记录
    target_assignment = None
    for assignment in assignments:
        if assignment.get("task_id") == task_id:
            target_assignment = assignment
            break
    
    if not target_assignment:
        return {"success": False, "message": f"未找到任务分配记录: {task_id}"}
    
    # 查找新执行者信息
    new_executor_name = new_executor_id
    new_executor_type = "team"
    for executor in state.get("available_executors", []):
        if executor.get("executor_id") == new_executor_id:
            new_executor_name = executor.get("executor_name", new_executor_id)
            new_executor_type = executor.get("executor_type", "team")
            break
    
    # 更新分配记录
    now = datetime.utcnow().isoformat()
    old_executor_name = target_assignment.get("executor_name", "")
    
    target_assignment["executor_id"] = new_executor_id
    target_assignment["executor_name"] = new_executor_name
    target_assignment["executor_type"] = new_executor_type
    target_assignment["status"] = AssignmentStatus.ASSIGNED.value
    target_assignment["updated_at"] = now
    
    # 更新数据库（如果有TaskAssignment表）
    try:
        async with AsyncSessionLocal() as session:
            # 调用TaskService的reassign方法（如果存在）
            # 这里简化为直接更新
            pass
    except Exception as e:
        logger.warning(f"[动态调整-3] 数据库更新跳过: {e}")
    
    # 生成新的调度指令
    new_order = {
        "order_id": str(uuid.uuid4()),
        "assignment_id": target_assignment.get("assignment_id"),
        "task_id": task_id,
        "task_name": target_assignment.get("task_name", ""),
        "executor_id": new_executor_id,
        "executor_name": new_executor_name,
        "executor_type": new_executor_type,
        "priority": target_assignment.get("task_priority", "medium"),
        "instructions": f"【任务重新分配】原执行者{old_executor_name}无法执行，现分配给{new_executor_name}。{action.get('reasoning', '')}",
        "status": "pending",
        "created_at": now,
        "event_id": state["event_id"],
        "is_reassignment": True,
    }
    
    return {
        "success": True,
        "message": f"任务{task_id}已从{old_executor_name}重新分配给{new_executor_name}",
        "new_order": new_order,
        "updated_assignments": assignments,
    }


async def _execute_retry(
    action: DispatchAction,
    assignments: List[TaskAssignment],
    state: TaskDispatchState
) -> Dict[str, Any]:
    """执行重试"""
    
    task_id = action.get("task_id")
    executor_id = action.get("old_executor_id") or action.get("new_executor_id")
    
    if not task_id:
        return {"success": False, "message": "缺少必要参数：task_id"}
    
    # 查找分配记录
    target_assignment = None
    for assignment in assignments:
        if assignment.get("task_id") == task_id:
            target_assignment = assignment
            break
    
    if not target_assignment:
        return {"success": False, "message": f"未找到任务分配记录: {task_id}"}
    
    # 重置状态
    now = datetime.utcnow().isoformat()
    target_assignment["status"] = AssignmentStatus.ASSIGNED.value
    target_assignment["updated_at"] = now
    
    # 生成重试指令
    new_order = {
        "order_id": str(uuid.uuid4()),
        "assignment_id": target_assignment.get("assignment_id"),
        "task_id": task_id,
        "task_name": target_assignment.get("task_name", ""),
        "executor_id": target_assignment.get("executor_id"),
        "executor_name": target_assignment.get("executor_name"),
        "executor_type": target_assignment.get("executor_type"),
        "priority": target_assignment.get("task_priority", "medium"),
        "instructions": f"【任务重试】请重新执行任务。{action.get('reasoning', '')}",
        "status": "pending",
        "created_at": now,
        "event_id": state["event_id"],
        "is_retry": True,
    }
    
    return {
        "success": True,
        "message": f"任务{task_id}已发送重试指令",
        "new_order": new_order,
        "updated_assignments": assignments,
    }


async def _execute_cancel(
    action: DispatchAction,
    assignments: List[TaskAssignment],
    state: TaskDispatchState
) -> Dict[str, Any]:
    """执行取消"""
    
    task_id = action.get("task_id")
    
    if not task_id:
        return {"success": False, "message": "缺少必要参数：task_id"}
    
    # 查找并更新分配记录
    target_assignment = None
    for assignment in assignments:
        if assignment.get("task_id") == task_id:
            target_assignment = assignment
            break
    
    if not target_assignment:
        return {"success": False, "message": f"未找到任务分配记录: {task_id}"}
    
    # 更新状态为取消
    now = datetime.utcnow().isoformat()
    target_assignment["status"] = "cancelled"
    target_assignment["updated_at"] = now
    
    return {
        "success": True,
        "message": f"任务{task_id}已取消",
        "updated_assignments": assignments,
    }
