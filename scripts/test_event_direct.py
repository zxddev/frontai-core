"""直接测试EventService"""
import asyncio
import sys
sys.path.insert(0, "/home/dev/gitcode/frontai/frontai-core")

from uuid import UUID
from src.domains.events.schemas import EventCreate, EventType, EventSourceType, EventPriority, Location
from src.domains.events.service import EventService
from src.core.database import AsyncSessionLocal

async def main():
    scenario_id = UUID("2f299f2f-1a7c-4d9e-b1c7-75c97c764098")
    
    event_data = EventCreate(
        scenario_id=scenario_id,
        event_type=EventType.fire,
        source_type=EventSourceType.ai_detection,
        title="测试火灾事件",
        description="测试WebSocket广播功能",
        location=Location(longitude=103.85, latitude=31.68),
        address="四川省茂县测试地址",
        priority=EventPriority.high,
        estimated_victims=3,
        is_time_critical=True,
    )
    
    async with AsyncSessionLocal() as session:
        service = EventService(session)
        try:
            result = await service.create(event_data)
            print(f"事件创建成功!")
            print(f"  ID: {result.id}")
            print(f"  Code: {result.event_code}")
            print(f"  Title: {result.title}")
            print(f"  Status: {result.status}")
            print(f"\n广播已发送到: /topic/scenario.disaster.triggered")
        except Exception as e:
            print(f"错误: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
