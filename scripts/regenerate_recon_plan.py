"""重新生成侦察方案

使用方法：
1. 确保后端服务已启动
2. 运行此脚本：python scripts/regenerate_recon_plan.py

这将调用 /initial-scan API 重新生成侦察方案，
新方案将只包含距离事件位置 50km 以内的 POI。
"""
import asyncio
import httpx
import json
import sys

# 事件ID（茂县地震）
EVENT_ID = "411196cf-f923-48c2-b19c-00ab770553a6"

# 后端API地址
API_BASE_URL = "http://localhost:8000"


async def regenerate_recon_plan():
    """调用 /initial-scan API 重新生成侦察方案"""
    
    print(f"=== 重新生成侦察方案 ===")
    print(f"事件ID: {EVENT_ID}")
    print(f"API地址: {API_BASE_URL}")
    print()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 调用 initial-scan API
        url = f"{API_BASE_URL}/agents/initial-scan"
        payload = {
            "event_id": EVENT_ID,
            "force_regenerate": True  # 强制重新生成
        }
        
        print(f"正在调用 {url}...")
        print(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")
        print()
        
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("success"):
                print("✅ 侦察方案生成成功！")
                print()
                
                data = result.get("data", {})
                recon_plan = data.get("recon_plan", {})
                missions = recon_plan.get("missions", [])
                
                print(f"任务数量: {len(missions)}")
                print()
                
                # 按设备类型分组
                drones = [m for m in missions if m.get("deviceType") == "drone"]
                dogs = [m for m in missions if m.get("deviceType") == "dog"]
                
                print(f"无人机任务 ({len(drones)} 个):")
                for m in drones:
                    print(f"  - {m.get('deviceName')} -> {m.get('targetName')}")
                
                print()
                print(f"机器狗任务 ({len(dogs)} 个):")
                for m in dogs:
                    print(f"  - {m.get('deviceName')} -> {m.get('targetName')}")
                
            else:
                print(f"❌ 侦察方案生成失败: {result.get('message')}")
                
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP错误: {e.response.status_code}")
            print(f"响应: {e.response.text}")
        except Exception as e:
            print(f"❌ 请求失败: {e}")


if __name__ == "__main__":
    asyncio.run(regenerate_recon_plan())
