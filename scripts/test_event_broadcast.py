"""测试事件创建和广播"""
import asyncio
import httpx
from uuid import uuid4

API_BASE = "http://localhost:8000"

async def main():
    # 需要一个有效的 scenario_id，这里用一个测试用的
    # 如果没有，需要先创建场景
    scenario_id = "2f299f2f-1a7c-4d9e-b1c7-75c97c764098"  # 四川茂县地震场景
    
    event_data = {
        "scenario_id": scenario_id,
        "event_type": "fire",
        "source_type": "ai_detection",
        "title": "测试火灾事件",
        "description": "这是一个测试火灾事件，用于验证WebSocket广播",
        "location": {
            "longitude": 116.4074,
            "latitude": 39.9042
        },
        "address": "北京市东城区测试地址",
        "priority": "high",
        "estimated_victims": 5,
        "is_time_critical": True,
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/api/v2/events",
                json=event_data,
                timeout=10.0
            )
            
            if response.status_code == 201:
                result = response.json()
                print(f"事件创建成功!")
                print(f"  ID: {result['id']}")
                print(f"  Code: {result['event_code']}")
                print(f"  Title: {result['title']}")
                print(f"  Status: {result['status']}")
                print(f"\n消息已广播到: /topic/scenario.disaster.triggered")
            else:
                print(f"创建失败: {response.status_code}")
                print(response.text)
        except httpx.ConnectError:
            print("连接失败，请确保服务已启动: uvicorn src.main:app --reload")
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
