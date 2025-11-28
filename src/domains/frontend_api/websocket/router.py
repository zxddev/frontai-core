"""
前端WebSocket路由

提供STOMP协议兼容的WebSocket端点
支持前端 EntityWebSocketClient 和 stompClient 的连接

端点: /ws/real-time
协议: 简化的STOMP-like协议（原生WebSocket传输）

由于Python没有成熟的STOMP服务端库，这里实现一个简化版本：
- 支持STOMP帧格式的订阅/发送
- 通过原生WebSocket传输
- 前端可通过SockJS降级到XHR-polling

主题映射:
- /topic/map.entity.create -> entities/entity_created
- /topic/map.entity.update -> entities/entity_updated
- /topic/map.entity.delete -> entities/entity_deleted
- /topic/realtime.location -> telemetry/location_update
- /topic/scenario.disaster.triggered -> alerts/disaster
- /topic/scenario.task.triggered -> tasks/task_triggered
- /topic/scenario.prompt.triggered -> messages/prompt
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Any
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["前端-WebSocket"])


@dataclass
class FrontendWSConnection:
    """前端WebSocket连接"""
    websocket: WebSocket
    client_id: str
    subscriptions: set = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)


class FrontendWebSocketManager:
    """前端WebSocket连接管理器"""
    
    TOPIC_MAPPING = {
        "/topic/map.entity.create": ("entities", "entity_created"),
        "/topic/map.entity.update": ("entities", "entity_updated"),
        "/topic/map.entity.delete": ("entities", "entity_deleted"),
        "/topic/realtime.location": ("telemetry", "location_update"),
        "/topic/scenario.disaster.triggered": ("alerts", "disaster"),
        "/topic/scenario.task.triggered": ("tasks", "task_triggered"),
        "/topic/scenario.prompt.triggered": ("messages", "prompt"),
    }
    
    def __init__(self):
        self.connections: dict[str, FrontendWSConnection] = {}
        self.topic_subscriptions: dict[str, set[str]] = defaultdict(set)
        self._heartbeat_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket, client_id: str) -> FrontendWSConnection:
        """建立连接"""
        await websocket.accept()
        
        conn = FrontendWSConnection(
            websocket=websocket,
            client_id=client_id,
        )
        self.connections[client_id] = conn
        
        logger.info(f"Frontend WS connected: {client_id}")
        
        # 发送SockJS open帧
        await websocket.send_text("o")
        
        return conn
    
    def disconnect(self, client_id: str):
        """断开连接"""
        conn = self.connections.pop(client_id, None)
        if conn:
            for topic in conn.subscriptions:
                self.topic_subscriptions[topic].discard(client_id)
            logger.info(f"Frontend WS disconnected: {client_id}")
    
    async def subscribe(self, client_id: str, topic: str, subscription_id: str):
        """订阅主题"""
        conn = self.connections.get(client_id)
        if not conn:
            return
        
        conn.subscriptions.add(topic)
        self.topic_subscriptions[topic].add(client_id)
        
        logger.info(f"Client {client_id} subscribed to {topic}")
    
    async def unsubscribe(self, client_id: str, subscription_id: str):
        """取消订阅"""
        conn = self.connections.get(client_id)
        if not conn:
            return
        
        # 根据subscription_id找到对应的topic并移除
        # 简化实现：遍历所有subscriptions
        topics_to_remove = []
        for topic in conn.subscriptions:
            if topic in self.topic_subscriptions:
                self.topic_subscriptions[topic].discard(client_id)
                topics_to_remove.append(topic)
        
        for topic in topics_to_remove:
            conn.subscriptions.discard(topic)
    
    async def broadcast_to_topic(self, topic: str, payload: dict):
        """向主题广播消息"""
        client_ids = self.topic_subscriptions.get(topic, set())
        logger.info(f"Broadcasting to {topic}: {len(client_ids)} subscribers")
        
        for client_id in list(client_ids):
            conn = self.connections.get(client_id)
            if conn:
                try:
                    await self._send_message(conn.websocket, topic, payload)
                    logger.info(f"Sent to {client_id} on {topic}")
                except Exception as e:
                    logger.error(f"Failed to send to {client_id}: {e}")
                    self.disconnect(client_id)
    
    async def broadcast_entity_create(self, entity_data: dict):
        """广播实体创建"""
        await self.broadcast_to_topic("/topic/map.entity.create", {"payload": entity_data})
    
    async def broadcast_entity_update(self, entity_data: dict):
        """广播实体更新"""
        await self.broadcast_to_topic("/topic/map.entity.update", {"payload": entity_data})
    
    async def broadcast_entity_delete(self, entity_id: str):
        """广播实体删除"""
        await self.broadcast_to_topic("/topic/map.entity.delete", {"payload": {"id": entity_id}})
    
    async def broadcast_location(self, location_data: dict):
        """广播实时位置"""
        await self.broadcast_to_topic("/topic/realtime.location", {"payload": location_data})
    
    async def broadcast_disaster(self, disaster_data: dict):
        """广播灾害事件"""
        await self.broadcast_to_topic("/topic/scenario.disaster.triggered", {"payload": disaster_data})
    
    async def broadcast_task_triggered(self, task_data: dict):
        """广播任务触发"""
        await self.broadcast_to_topic("/topic/scenario.task.triggered", {"payload": task_data})
    
    async def broadcast_prompt(self, prompt_data: dict):
        """广播提示消息"""
        await self.broadcast_to_topic("/topic/scenario.prompt.triggered", {"payload": prompt_data})
    
    async def _send_frame(self, websocket: WebSocket, command: str, headers: dict, body: str = ""):
        """发送STOMP帧（SockJS包装格式）"""
        # 构建标准STOMP帧格式
        lines = [command]
        for key, value in headers.items():
            lines.append(f"{key}:{value}")
        lines.append("")  # 空行分隔headers和body
        lines.append(body)
        lines.append("\x00")  # NULL结束符
        
        frame = "\n".join(lines)
        
        # SockJS消息格式: a["message"] 
        # 需要将STOMP帧JSON编码后包装
        sockjs_message = 'a' + json.dumps([frame])
        await websocket.send_text(sockjs_message)
    
    async def _send_message(self, websocket: WebSocket, destination: str, content: dict):
        """发送MESSAGE帧"""
        await self._send_frame(
            websocket,
            "MESSAGE",
            {
                "destination": destination,
                "content-type": "application/json",
                "message-id": str(uuid4()),
            },
            json.dumps(content)
        )
    
    async def _send_receipt(self, websocket: WebSocket, receipt_id: str):
        """发送RECEIPT帧"""
        await self._send_frame(websocket, "RECEIPT", {"receipt-id": receipt_id})
    
    async def _send_error(self, websocket: WebSocket, message: str):
        """发送ERROR帧"""
        await self._send_frame(websocket, "ERROR", {"message": message})
    
    async def heartbeat(self, client_id: str):
        """心跳 - 记录时间并发送响应"""
        conn = self.connections.get(client_id)
        if conn:
            conn.last_heartbeat = datetime.utcnow()
            # 发送SockJS心跳帧 (STOMP心跳是换行符，SockJS包装为 a["\n"])
            try:
                await conn.websocket.send_text('a["\\n"]')
            except Exception:
                pass


# 全局实例
frontend_ws_manager = FrontendWebSocketManager()


@router.get("/real-time/info")
async def sockjs_info():
    """
    SockJS info端点
    """
    import random
    return {
        "entropy": random.randint(0, 2**32),
        "origins": ["*:*"],
        "cookie_needed": False,
        "websocket": True,
    }


@router.get("/real-time/{server_id}/{session_id}/info")
async def sockjs_session_info(server_id: str, session_id: str):
    """SockJS session info"""
    import random
    return {
        "entropy": random.randint(0, 2**32),
        "origins": ["*:*"],
        "cookie_needed": False,
        "websocket": True,
    }


@router.get("/real-time/iframe.html")
async def sockjs_iframe():
    """SockJS iframe for cross-domain"""
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <script type="text/javascript">
    document.domain = document.domain;
    _sockjs_onload = function(){SockJS.bootstrap_iframe();};
  </script>
</head>
<body>
  <h2>Don't panic!</h2>
  <p>This is a SockJS hidden iframe.</p>
</body>
</html>"""
    return HTMLResponse(content=html)


# SockJS XHR传输端点
from fastapi import Response
from fastapi.responses import StreamingResponse
import asyncio

# 存储SockJS会话
sockjs_sessions: dict[str, dict] = {}


@router.post("/real-time/{server_id}/{session_id}/xhr_streaming")
async def sockjs_xhr_streaming(server_id: str, session_id: str):
    """SockJS XHR Streaming传输"""
    session_key = f"{server_id}_{session_id}"
    
    async def generate():
        # 发送2KB prelude（用于绕过某些代理的缓冲）
        yield "h" * 2048 + "\n"
        # 发送open帧
        yield "o\n"
        
        # 保持连接并发送心跳
        for _ in range(30):  # 30秒超时
            await asyncio.sleep(1)
            yield "h\n"  # 心跳帧
    
    return StreamingResponse(
        generate(),
        media_type="application/javascript;charset=UTF-8",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": "true",
            "Cache-Control": "no-store, no-cache, no-transform",
        }
    )


@router.post("/real-time/{server_id}/{session_id}/xhr")
async def sockjs_xhr(server_id: str, session_id: str):
    """SockJS XHR轮询传输"""
    session_key = f"{server_id}_{session_id}"
    
    if session_key not in sockjs_sessions:
        sockjs_sessions[session_key] = {"opened": False, "messages": []}
    
    session = sockjs_sessions[session_key]
    
    if not session["opened"]:
        session["opened"] = True
        return Response(
            content="o\n",
            media_type="application/javascript;charset=UTF-8",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    
    # 返回心跳或等待消息
    await asyncio.sleep(0.1)
    return Response(
        content="h\n",
        media_type="application/javascript;charset=UTF-8",
        headers={"Access-Control-Allow-Origin": "*"}
    )


@router.post("/real-time/{server_id}/{session_id}/xhr_send")
async def sockjs_xhr_send(server_id: str, session_id: str):
    """SockJS XHR发送端点"""
    return Response(
        content="",
        status_code=204,
        headers={"Access-Control-Allow-Origin": "*"}
    )


@router.options("/real-time/{server_id}/{session_id}/xhr_streaming")
@router.options("/real-time/{server_id}/{session_id}/xhr")
@router.options("/real-time/{server_id}/{session_id}/xhr_send")
async def sockjs_xhr_options(server_id: str, session_id: str):
    """SockJS CORS预检"""
    return Response(
        content="",
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        }
    )


@router.get("/real-time/{server_id}/{session_id}/eventsource")
async def sockjs_eventsource(server_id: str, session_id: str):
    """SockJS EventSource传输"""
    async def generate():
        yield "data: o\r\n\r\n"
        for _ in range(30):
            await asyncio.sleep(1)
            yield "data: h\r\n\r\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-cache",
        }
    )


@router.get("/real-time/{server_id}/{session_id}/htmlfile")
async def sockjs_htmlfile(server_id: str, session_id: str, c: str = ""):
    """SockJS HTMLFile传输"""
    from fastapi.responses import HTMLResponse
    html = f"""<!doctype html>
<html><head>
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
</head><body><h2>Don't panic!</h2>
  <script>document.domain = document.domain;var c = parent.{c};c.start();c.message('o');c.message('h');</script>
</body></html>"""
    return HTMLResponse(content=html)


@router.get("/real-time/{server_id}/{session_id}/jsonp")
async def sockjs_jsonp(server_id: str, session_id: str, c: str = ""):
    """SockJS JSONP传输"""
    return Response(
        content=f'{c}("o");\n',
        media_type="application/javascript;charset=UTF-8",
        headers={"Access-Control-Allow-Origin": "*"}
    )


async def _handle_websocket(websocket: WebSocket, client_id: str):
    """处理WebSocket连接的公共逻辑"""
    conn = await frontend_ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
                logger.info(f"[WS {client_id}] Received: {raw_data[:200] if raw_data else 'empty'}...")
                
                if not raw_data or raw_data.strip() in ("", "\n", "\r\n"):
                    await frontend_ws_manager.heartbeat(client_id)
                    continue
                
                # SockJS包装的消息格式: ["message"]
                if raw_data.startswith("[") and raw_data.endswith("]"):
                    try:
                        sockjs_messages = json.loads(raw_data)
                        if isinstance(sockjs_messages, list) and sockjs_messages:
                            raw_data = sockjs_messages[0]
                            logger.info(f"[WS {client_id}] Unwrapped SockJS: {repr(raw_data[:50])}...")
                            # 解包后检查是否为心跳
                            if raw_data in ("\n", "\r\n", ""):
                                await frontend_ws_manager.heartbeat(client_id)
                                continue
                    except:
                        pass
                
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    data = _parse_stomp_frame(raw_data)
                
                command = data.get("command", "").upper()
                headers = data.get("headers", {})
                body = data.get("body", "")
                logger.info(f"[WS {client_id}] Command: {command}, Headers: {headers}")
                
                if command == "CONNECT" or command == "STOMP":
                    # 发送STOMP CONNECTED响应
                    await frontend_ws_manager._send_frame(websocket, "CONNECTED", {
                        "version": "1.2",
                        "heart-beat": "4000,4000",
                        "server": "frontai-ws/1.0",
                    })
                    logger.info(f"[WS {client_id}] Sent CONNECTED frame")
                elif command == "SUBSCRIBE":
                    destination = headers.get("destination", "")
                    sub_id = headers.get("id", str(uuid4()))
                    await frontend_ws_manager.subscribe(client_id, destination, sub_id)
                    receipt = headers.get("receipt")
                    if receipt:
                        await frontend_ws_manager._send_receipt(websocket, receipt)
                elif command == "UNSUBSCRIBE":
                    sub_id = headers.get("id", "")
                    await frontend_ws_manager.unsubscribe(client_id, sub_id)
                elif command == "SEND":
                    destination = headers.get("destination", "")
                    logger.info(f"Received SEND to {destination}: {body[:100] if body else ''}...")
                elif command == "DISCONNECT":
                    frontend_ws_manager.disconnect(client_id)
                    break
                elif command == "PING" or command == "":
                    await frontend_ws_manager.heartbeat(client_id)
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    finally:
        frontend_ws_manager.disconnect(client_id)


@router.websocket("/real-time/{server_id}/{session_id}/websocket")
async def sockjs_websocket_endpoint(
    websocket: WebSocket,
    server_id: str,
    session_id: str,
):
    """SockJS WebSocket端点（带session路径）"""
    await _handle_websocket(websocket, session_id)


@router.websocket("/real-time")
async def frontend_websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="客户端ID"),
):
    """
    前端STOMP-like WebSocket端点
    
    连接: ws://host/ws/real-time?client_id=xxx
    
    支持的STOMP命令:
    - CONNECT: 建立连接
    - SUBSCRIBE: 订阅主题
    - UNSUBSCRIBE: 取消订阅
    - SEND: 发送消息
    - DISCONNECT: 断开连接
    - 心跳: 空帧或特殊心跳帧
    
    前端使用SockJS + STOMP.js连接
    """
    if not client_id:
        client_id = str(uuid4())
    
    conn = await frontend_ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            try:
                # 接收消息（支持文本和JSON）
                raw_data = await websocket.receive_text()
                
                # 心跳帧（空或换行）
                if not raw_data or raw_data.strip() in ("", "\n", "\r\n"):
                    await frontend_ws_manager.heartbeat(client_id)
                    continue
                
                # 解析JSON帧
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    # 可能是原始STOMP帧，尝试解析
                    data = _parse_stomp_frame(raw_data)
                
                command = data.get("command", "").upper()
                headers = data.get("headers", {})
                body = data.get("body", "")
                
                if command == "CONNECT" or command == "STOMP":
                    # 已在connect时处理
                    pass
                
                elif command == "SUBSCRIBE":
                    destination = headers.get("destination", "")
                    sub_id = headers.get("id", str(uuid4()))
                    await frontend_ws_manager.subscribe(client_id, destination, sub_id)
                    
                    receipt = headers.get("receipt")
                    if receipt:
                        await frontend_ws_manager._send_receipt(websocket, receipt)
                
                elif command == "UNSUBSCRIBE":
                    sub_id = headers.get("id", "")
                    await frontend_ws_manager.unsubscribe(client_id, sub_id)
                
                elif command == "SEND":
                    destination = headers.get("destination", "")
                    logger.info(f"Received SEND to {destination}: {body[:100]}...")
                    # 可以在这里处理客户端发送的消息
                
                elif command == "DISCONNECT":
                    frontend_ws_manager.disconnect(client_id)
                    break
                
                elif command == "PING" or command == "":
                    # 心跳
                    await frontend_ws_manager.heartbeat(client_id)
                
                else:
                    logger.warning(f"Unknown STOMP command: {command}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    finally:
        frontend_ws_manager.disconnect(client_id)


def _parse_stomp_frame(raw: str) -> dict:
    """解析原始STOMP帧"""
    lines = raw.split("\n")
    if not lines:
        return {}
    
    command = lines[0].strip()
    headers = {}
    body = ""
    
    header_done = False
    body_lines = []
    
    for line in lines[1:]:
        if not header_done:
            if line.strip() == "":
                header_done = True
            elif ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        else:
            body_lines.append(line)
    
    body = "\n".join(body_lines).rstrip("\x00")
    
    return {
        "command": command,
        "headers": headers,
        "body": body,
    }
