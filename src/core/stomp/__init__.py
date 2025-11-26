"""
STOMP消息代理模块

基于Redis Pub/Sub实现STOMP协议支持
架构: 前端 <--WebSocket/STOMP--> Python <--Pub/Sub--> Redis

功能:
- STOMP协议帧解析和生成
- WebSocket连接管理
- Redis Pub/Sub消息转发
- 订阅管理和消息路由
- 心跳和ACK机制
- SockJS降级支持（可选）
"""

from .broker import StompBroker, stomp_broker
from .connection import StompConnection
from .frames import StompFrame, StompCommand
from .router import stomp_router

__all__ = [
    "StompBroker",
    "stomp_broker",
    "StompConnection",
    "StompFrame",
    "StompCommand",
    "stomp_router",
]
