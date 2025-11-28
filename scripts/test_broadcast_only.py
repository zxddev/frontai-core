"""直接测试广播功能（不依赖数据库）"""
import asyncio
from uuid import uuid4
from datetime import datetime

from src.core.stomp.broker import stomp_broker

async def main():
    # 启动broker
    await stomp_broker.start()
    
    # 模拟前端期望格式的事件数据
    event_payload = {
        "eventId": str(uuid4()),
        "title": "测试火灾事件",
        "eventLevel": 3,  # high
        "eventType": 2,   # fire
        "location": [103.85, 31.68],
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "origin": "ai_detection",
        "data": "测试WebSocket广播功能",
        "eventCode": "EV-TEST-001",
        "status": "pending",
        "address": "四川省茂县测试地址",
        "estimatedVictims": 3,
        "isTimeCritical": True,
        "scenarioId": "2f299f2f-1a7c-4d9e-b1c7-75c97c764098",
    }
    
    # 广播事件
    scenario_id = None  # 广播给所有订阅者
    await stomp_broker.broadcast_event("disaster", event_payload, scenario_id)
    
    print(f"广播成功!")
    print(f"  Topic: /topic/scenario.disaster.triggered")
    print(f"  Title: {event_payload['title']}")
    print(f"  EventId: {event_payload['eventId']}")
    print(f"\n前端订阅该topic即可收到此消息")
    
    # 停止broker
    await stomp_broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
