"""发送测试灾害事件到前端"""
import asyncio
from uuid import uuid4
from datetime import datetime

from src.core.stomp.broker import stomp_broker


async def main():
    # 启动broker
    await stomp_broker.start()
    
    # 构造灾害事件数据（符合前端期望格式）
    disaster_data = {
        "eventId": str(uuid4()),
        "title": "测试地震灾害",
        "eventLevel": 3,  # 1-4，数字越大级别越高
        "eventType": 1,   # 事件类型：1=地震, 2=洪水, 3=火灾, 4=滑坡等
        "location": [116.4074, 39.9042],  # [lng, lat]
        "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "origin": "监测系统",
        "data": "这是一个测试灾害事件",
    }
    
    # 广播灾害事件 (使用 broadcast_event，事件类型为 disaster)
    await stomp_broker.broadcast_event("disaster", disaster_data)
    print(f"已发送灾害事件: {disaster_data['title']}")
    
    # 停止broker
    await stomp_broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
