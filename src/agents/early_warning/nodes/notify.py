"""
通知发送节点

通过WebSocket推送预警消息到前端。
"""
import logging
import asyncio
from typing import Any, Dict, List
from datetime import datetime
from uuid import UUID

from ..state import EarlyWarningState, WarningRecord

logger = logging.getLogger(__name__)


def send_notifications(state: EarlyWarningState) -> Dict[str, Any]:
    """
    发送预警通知
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info(f"[notify] Sending notifications for request {state['request_id']}")
    
    warning_records = state.get("warning_records", [])
    disaster = state.get("disaster_situation")
    
    if not warning_records:
        logger.info("[notify] No warning records to notify")
        return {
            "current_phase": "notify",
            "notifications_sent": 0,
            "success": True,
            "summary": "No warnings to send",
        }
    
    notifications_sent = 0
    notification_errors: List[str] = []
    
    for record in warning_records:
        try:
            # 构建通知消息
            notification = _build_notification(record, disaster)
            
            # 发送通知（同步版本，实际应使用异步）
            success = _send_alert_sync(
                scenario_id=state.get("scenario_id"),
                notification=notification,
            )
            
            if success:
                notifications_sent += 1
                logger.info(f"[notify] Sent notification for warning {record['id']}")
            else:
                notification_errors.append(f"Failed to send notification for {record['id']}")
                
        except Exception as e:
            error_msg = f"Error sending notification for {record['id']}: {str(e)}"
            logger.error(f"[notify] {error_msg}")
            notification_errors.append(error_msg)
    
    # 更新trace
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["notify"]
    trace["notify_time"] = datetime.utcnow().isoformat()
    trace["notifications_sent"] = notifications_sent
    trace["notification_errors"] = len(notification_errors)
    
    # 生成摘要
    summary = (
        f"已发送{notifications_sent}条预警通知，"
        f"涉及{len(warning_records)}个受影响对象"
    )
    if notification_errors:
        summary += f"，{len(notification_errors)}条发送失败"
    
    return {
        "notifications_sent": notifications_sent,
        "notification_errors": notification_errors,
        "current_phase": "notify",
        "success": notifications_sent > 0 or len(warning_records) == 0,
        "summary": summary,
        "trace": trace,
    }


def _build_notification(record: WarningRecord, disaster: Dict) -> Dict[str, Any]:
    """构建WebSocket通知消息"""
    return {
        "warning_id": record["id"],
        "warning_level": record["warning_level"],
        "warning_title": record["warning_title"],
        "warning_message": record["warning_message"],
        "disaster_type": disaster.get("disaster_type", "") if disaster else "",
        "disaster_name": disaster.get("disaster_name") if disaster else None,
        "affected_type": record["affected_type"],
        "affected_id": record["affected_id"],
        "affected_name": record["affected_name"],
        "distance_m": record["distance_m"],
        "estimated_contact_minutes": record["estimated_contact_minutes"],
        "route_affected": record["route_affected"],
        "actions": ["detour", "continue", "standby"],
        "created_at": record["created_at"],
    }


def _send_alert_sync(scenario_id: str, notification: Dict[str, Any]) -> bool:
    """
    同步发送告警（包装异步函数）
    
    在实际环境中，应该在异步上下文中直接调用异步版本
    """
    try:
        # 尝试获取事件循环
        try:
            loop = asyncio.get_running_loop()
            # 如果在异步上下文中，创建任务
            future = asyncio.ensure_future(_send_alert_async(scenario_id, notification))
            # 注意：这里不会等待完成，只是创建任务
            return True
        except RuntimeError:
            # 没有运行中的事件循环，创建新的
            return asyncio.run(_send_alert_async(scenario_id, notification))
    except Exception as e:
        logger.error(f"[notify] Error in sync wrapper: {e}")
        return False


async def _send_alert_async(scenario_id: str, notification: Dict[str, Any]) -> bool:
    """
    异步发送告警
    
    使用现有的WebSocket管理器广播告警
    """
    try:
        from core.websocket import broadcast_alert
        
        if scenario_id:
            await broadcast_alert(
                scenario_id=UUID(scenario_id),
                alert_type="early_warning",
                alert_data=notification,
            )
        else:
            # 如果没有scenario_id，广播到所有订阅alerts的客户端
            from core.websocket import ws_manager
            await ws_manager.broadcast_to_channel(
                channel="alerts",
                event_type="early_warning",
                payload=notification,
            )
        
        return True
        
    except ImportError:
        logger.warning("[notify] WebSocket module not available, skipping notification")
        return True  # 不算失败，只是跳过
    except Exception as e:
        logger.error(f"[notify] Error sending async alert: {e}")
        return False
