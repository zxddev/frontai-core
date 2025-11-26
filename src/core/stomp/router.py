"""
STOMP WebSocket路由

端点:
- /ws/stomp: STOMP WebSocket端点
- /ws/stomp/info: SockJS信息端点（可选）
"""

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from .broker import stomp_broker
from .connection import StompConnection
from .frames import StompFrame, StompCommand


logger = logging.getLogger(__name__)

router = APIRouter(tags=["stomp-websocket"])


@router.websocket("/stomp")
async def stomp_websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="客户端ID"),
    scenario_id: Optional[UUID] = Query(None, description="场景ID"),
):
    """
    STOMP WebSocket端点
    
    连接: ws://host/ws/stomp?client_id=xxx&scenario_id=xxx
    
    STOMP协议流程:
    1. 客户端发送CONNECT帧
    2. 服务端返回CONNECTED帧
    3. 客户端发送SUBSCRIBE订阅主题
    4. 服务端推送MESSAGE帧
    5. 客户端可发送SEND到指定目标
    6. 客户端发送DISCONNECT断开
    
    支持的STOMP命令:
    - CONNECT/STOMP: 建立连接
    - SUBSCRIBE: 订阅主题
    - UNSUBSCRIBE: 取消订阅
    - SEND: 发送消息
    - ACK: 确认消息
    - NACK: 否定确认
    - DISCONNECT: 断开连接
    
    主题格式:
    - /topic/xxx: 广播主题
    - /queue/xxx: 队列主题
    - /user/{id}/xxx: 用户私有主题
    """
    await websocket.accept()
    
    session_id = str(uuid4())
    conn = StompConnection(
        websocket=websocket,
        session_id=session_id,
        client_id=client_id,
        scenario_id=scenario_id,
    )
    
    try:
        while True:
            try:
                # 接收消息
                raw_data = await websocket.receive_text()
                conn.update_activity()
                
                # 心跳（空帧或换行）
                if not raw_data or raw_data.strip() in ("", "\n", "\r\n"):
                    continue
                
                # 解析STOMP帧
                try:
                    # 尝试JSON格式（简化协议）
                    frame = StompFrame.from_json(raw_data)
                except json.JSONDecodeError:
                    # 尝试原生STOMP格式
                    frame = StompFrame.from_text(raw_data)
                
                # 处理命令
                await _handle_frame(conn, frame)
                
                if frame.command == StompCommand.DISCONNECT:
                    break
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing frame from {session_id}: {e}")
                await conn.send_error("Frame processing error", str(e))
    
    finally:
        await stomp_broker.disconnect(session_id)


async def _handle_frame(conn: StompConnection, frame: StompFrame):
    """处理STOMP帧"""
    command = frame.command
    headers = frame.headers
    body = frame.body
    
    if command in (StompCommand.CONNECT, StompCommand.STOMP):
        # 处理CONNECT
        accept_version = headers.get("accept-version", "1.0,1.1,1.2")
        if "1.2" in accept_version:
            conn.version = "1.2"
        elif "1.1" in accept_version:
            conn.version = "1.1"
        else:
            conn.version = "1.0"
        
        # 解析心跳
        heart_beat = headers.get("heart-beat", "0,0")
        try:
            cx, cy = map(int, heart_beat.split(","))
            conn.heart_beat_client = cx
        except:
            pass
        
        # 注册连接并发送CONNECTED
        await stomp_broker.connect(conn)
        await conn.send_connected()
        
        logger.info(f"STOMP CONNECT: session={conn.session_id}, version={conn.version}")
    
    elif command == StompCommand.SUBSCRIBE:
        destination = headers.get("destination")
        sub_id = headers.get("id", str(uuid4()))
        ack_mode = headers.get("ack", "auto")
        
        if destination:
            await stomp_broker.subscribe(conn.session_id, destination, sub_id, ack_mode)
            
            # 发送RECEIPT（如果请求了）
            receipt = headers.get("receipt")
            if receipt:
                await conn.send_receipt(receipt)
        else:
            await conn.send_error("Missing destination", "SUBSCRIBE requires destination header")
    
    elif command == StompCommand.UNSUBSCRIBE:
        sub_id = headers.get("id")
        if sub_id:
            await stomp_broker.unsubscribe(conn.session_id, sub_id)
            
            receipt = headers.get("receipt")
            if receipt:
                await conn.send_receipt(receipt)
        else:
            await conn.send_error("Missing subscription id", "UNSUBSCRIBE requires id header")
    
    elif command == StompCommand.SEND:
        destination = headers.get("destination")
        if destination:
            # 转发消息到目标
            await stomp_broker.send_to_destination(destination, body, conn.scenario_id)
            
            receipt = headers.get("receipt")
            if receipt:
                await conn.send_receipt(receipt)
            
            logger.debug(f"STOMP SEND: {destination} from {conn.session_id}")
        else:
            await conn.send_error("Missing destination", "SEND requires destination header")
    
    elif command == StompCommand.ACK:
        message_id = headers.get("id") or headers.get("message-id")
        if message_id:
            conn.ack_message(message_id)
        
    elif command == StompCommand.NACK:
        message_id = headers.get("id") or headers.get("message-id")
        if message_id:
            conn.nack_message(message_id)
    
    elif command == StompCommand.DISCONNECT:
        receipt = headers.get("receipt")
        if receipt:
            await conn.send_receipt(receipt)
        logger.info(f"STOMP DISCONNECT: {conn.session_id}")
    
    else:
        logger.warning(f"Unhandled STOMP command: {command}")


# SockJS info端点（可选，用于SockJS降级）
@router.get("/stomp/info")
async def sockjs_info():
    """SockJS信息端点"""
    return {
        "websocket": True,
        "cookie_needed": False,
        "origins": ["*"],
        "entropy": uuid4().int,
    }


stomp_router = router
