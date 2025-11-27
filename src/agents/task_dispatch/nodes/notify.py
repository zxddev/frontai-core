"""
通知节点

通过WebSocket等方式通知相关方（执行者、指挥员等）。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List
from datetime import datetime

from ..state import TaskDispatchState

logger = logging.getLogger(__name__)


async def notify_stakeholders(state: TaskDispatchState) -> Dict[str, Any]:
    """
    通知相关方
    
    通过WebSocket或其他方式通知执行者和指挥员。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[通知] 发送通知: event_id={state['event_id']}")
    start_time = time.time()
    
    dispatch_orders = state.get("dispatch_orders", [])
    notifications_sent: List[Dict[str, Any]] = list(state.get("notifications_sent", []))
    errors: List[str] = list(state.get("errors", []))
    
    if not dispatch_orders:
        logger.info("[通知] 无调度指令需要通知")
        return {
            "current_phase": "notify",
        }
    
    now = datetime.utcnow().isoformat()
    
    for order in dispatch_orders:
        # 检查是否已通知
        order_id = order.get("order_id")
        already_notified = any(
            n.get("order_id") == order_id for n in notifications_sent
        )
        if already_notified:
            continue
        
        try:
            # 构建通知内容
            notification = _build_notification(order, state)
            
            # 发送通知（这里是模拟，实际应调用WebSocket服务）
            success = await _send_notification(notification)
            
            if success:
                notifications_sent.append({
                    "notification_id": f"notif-{order_id}",
                    "order_id": order_id,
                    "executor_id": order.get("executor_id"),
                    "sent_at": now,
                    "status": "sent",
                    "channel": "websocket",
                })
                logger.info(f"[通知] 已发送: order_id={order_id}, executor={order.get('executor_name')}")
            else:
                errors.append(f"通知发送失败: order_id={order_id}")
                
        except Exception as e:
            logger.error(f"[通知] 发送异常: {e}")
            errors.append(f"通知异常: {str(e)}")
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["notify_stakeholders"]
    trace["notifications_count"] = len(notifications_sent)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[通知] 完成: 发送{len(notifications_sent)}条通知, 耗时{elapsed_ms}ms")
    
    return {
        "notifications_sent": notifications_sent,
        "errors": errors,
        "trace": trace,
        "current_phase": "notify",
    }


def _build_notification(order: Dict[str, Any], state: TaskDispatchState) -> Dict[str, Any]:
    """构建通知内容"""
    
    is_reassignment = order.get("is_reassignment", False)
    is_retry = order.get("is_retry", False)
    
    if is_reassignment:
        title = "【任务重新分配通知】"
        notification_type = "task_reassignment"
    elif is_retry:
        title = "【任务重试通知】"
        notification_type = "task_retry"
    else:
        title = "【新任务分配通知】"
        notification_type = "task_assignment"
    
    return {
        "type": notification_type,
        "title": title,
        "content": {
            "order_id": order.get("order_id"),
            "task_id": order.get("task_id"),
            "task_name": order.get("task_name"),
            "priority": order.get("priority"),
            "instructions": order.get("instructions"),
            "scheduled_start": order.get("scheduled_start"),
            "scheduled_end": order.get("scheduled_end"),
        },
        "target": {
            "executor_id": order.get("executor_id"),
            "executor_name": order.get("executor_name"),
            "executor_type": order.get("executor_type"),
        },
        "metadata": {
            "event_id": state.get("event_id"),
            "scheme_id": state.get("scheme_id"),
        },
    }


async def _send_notification(notification: Dict[str, Any]) -> bool:
    """
    发送通知
    
    实际实现应调用WebSocket服务或消息队列。
    当前为模拟实现。
    
    Args:
        notification: 通知内容
        
    Returns:
        是否发送成功
    """
    # TODO: 集成实际的WebSocket服务
    # 可以调用 src/core/stomp/broker.py 中的 StompBroker
    
    try:
        # 模拟发送
        executor_id = notification.get("target", {}).get("executor_id")
        notification_type = notification.get("type")
        
        logger.info(
            f"[通知] 模拟发送: type={notification_type}, "
            f"executor={executor_id}, "
            f"task={notification.get('content', {}).get('task_id')}"
        )
        
        # 实际实现示例:
        # from src.core.stomp.broker import get_stomp_broker
        # broker = get_stomp_broker()
        # await broker.publish(
        #     topic=f"/queue/executor/{executor_id}",
        #     message=notification
        # )
        
        return True
        
    except Exception as e:
        logger.error(f"[通知] 发送失败: {e}")
        return False
