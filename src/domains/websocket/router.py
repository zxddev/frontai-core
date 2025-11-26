"""
WebSocket 路由

连接地址: ws://host/api/v2/ws?client_id=xxx&scenario_id=xxx

消息格式：
- 客户端发送: {"action": "subscribe|unsubscribe|ping", "channels": [...], "last_msg_id": "..."}
- 服务端推送: {"id": "...", "channel": "...", "event_type": "...", "payload": {...}, "timestamp": "..."}
"""

import logging
from uuid import UUID
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from src.core.websocket import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Query(..., description="客户端唯一标识"),
    scenario_id: Optional[UUID] = Query(None, description="想定ID"),
    last_msg_id: Optional[str] = Query(None, description="最后收到的消息ID（断线重连用）"),
):
    """
    WebSocket连接端点
    
    连接流程：
    1. 客户端连接: ws://host/api/v2/ws?client_id=xxx&scenario_id=xxx
    2. 服务端返回: {"type": "connected", "client_id": "...", "available_channels": [...]}
    3. 客户端订阅: {"action": "subscribe", "channels": ["events", "tasks"]}
    4. 服务端推送: {"channel": "events", "event_type": "event_created", "payload": {...}}
    
    支持的action:
    - subscribe: 订阅频道
    - unsubscribe: 取消订阅
    - ping: 心跳
    - replay: 回放错过的消息
    
    支持的频道:
    - events: 事件更新（created/confirmed/resolved等）
    - tasks: 任务更新（assigned/progress/completed等）
    - schemes: 方案更新（approved/executing等）
    - telemetry: 遥测数据（车辆/队伍/设备位置）
    - alerts: 告警通知（紧急事件/超时等）
    - messages: 指挥消息
    - entities: 地图实体更新
    """
    conn = await ws_manager.connect(websocket, client_id, scenario_id)
    
    # 断线重连：回放错过的消息
    if last_msg_id:
        await ws_manager.replay_messages(client_id, last_msg_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "subscribe":
                channels = data.get("channels", [])
                subscribed = await ws_manager.subscribe(client_id, channels)
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": subscribed,
                })
            
            elif action == "unsubscribe":
                channels = data.get("channels", [])
                unsubscribed = await ws_manager.unsubscribe(client_id, channels)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channels": unsubscribed,
                })
            
            elif action == "ping":
                await ws_manager.heartbeat(client_id)
            
            elif action == "replay":
                msg_id = data.get("last_msg_id")
                if msg_id:
                    count = await ws_manager.replay_messages(client_id, msg_id)
                    await websocket.send_json({
                        "type": "replay_complete",
                        "replayed_count": count,
                    })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        ws_manager.disconnect(client_id)
