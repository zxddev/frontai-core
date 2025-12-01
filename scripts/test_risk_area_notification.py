#!/usr/bin/env python3
"""
风险区域通知功能测试脚本

测试内容：
1. 创建风险区域时触发 WebSocket 广播
2. 高风险区域（risk_level >= 5）触发 early_warning 预警生成
3. 更新风险区域时的变更检测
4. 通行状态变更通知
"""
import asyncio
import json
import sys
from uuid import uuid4

import httpx

BASE_URL = "http://localhost:8000/api/v2"


async def test_create_risk_area(scenario_id: str):
    """测试创建风险区域（会触发通知）"""
    print("\n" + "=" * 60)
    print("测试1: 创建高风险区域（risk_level=7）")
    print("=" * 60)
    
    payload = {
        "scenarioId": scenario_id,
        "name": "测试滑坡风险区",
        "areaType": "landslide",
        "riskLevel": 7,
        "severity": "high",
        "passageStatus": "needs_reconnaissance",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [104.065, 30.660],
                [104.070, 30.660],
                [104.070, 30.665],
                [104.065, 30.665],
                [104.065, 30.660],
            ]]
        },
        "passable": False,
        "passableVehicleTypes": [],
        "speedReductionPercent": 100,
        "reconnaissanceRequired": True,
        "description": "测试滑坡风险区域，需要侦察确认",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{BASE_URL}/risk-areas",
                json=payload,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code in [200, 201]:
                data = resp.json()
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
                return data.get("id")
            else:
                print(f"Error: {resp.text}")
                return None
        except Exception as e:
            print(f"Request failed: {e}")
            return None


async def test_update_risk_level(area_id: str):
    """测试更新风险等级（会触发通知）"""
    print("\n" + "=" * 60)
    print(f"测试2: 更新风险等级 7 -> 9")
    print("=" * 60)
    
    payload = {
        "riskLevel": 9,
        "severity": "critical",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.patch(
                f"{BASE_URL}/risk-areas/{area_id}",
                json=payload,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Updated riskLevel: {data.get('riskLevel')}")
                return True
            else:
                print(f"Error: {resp.text}")
                return False
        except Exception as e:
            print(f"Request failed: {e}")
            return False


async def test_update_passage_status(area_id: str):
    """测试更新通行状态（会触发专门的通知）"""
    print("\n" + "=" * 60)
    print(f"测试3: 更新通行状态为 confirmed_blocked")
    print("=" * 60)
    
    payload = {
        "passageStatus": "confirmed_blocked",
        "reason": "侦察确认：山体滑坡导致道路完全阻断，预计修复需要48小时",
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.patch(
                f"{BASE_URL}/risk-areas/{area_id}/passage-status",
                json=payload,
            )
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Updated passageStatus: {data.get('passageStatus')}")
                return True
            else:
                print(f"Error: {resp.text}")
                return False
        except Exception as e:
            print(f"Request failed: {e}")
            return False


async def test_list_warnings():
    """检查 early_warning 预警记录"""
    print("\n" + "=" * 60)
    print("测试4: 查询生成的预警记录")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{BASE_URL}/ai/early-warning/warnings")
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                print(f"Total warnings: {data.get('total', 0)}")
                for item in data.get("items", [])[:5]:
                    print(f"  - {item.get('warning_title')} [{item.get('warning_level')}]")
                return True
            else:
                print(f"Error: {resp.text}")
                return False
        except Exception as e:
            print(f"Request failed: {e}")
            return False


async def get_active_scenario():
    """获取活动想定"""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE_URL}/scenarios")
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if items:
                    return items[0].get("id")
        except Exception:
            pass
    return None


async def main():
    print("=" * 60)
    print("风险区域通知功能测试")
    print("=" * 60)
    
    # 检查API
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(f"{BASE_URL}/docs")
            if resp.status_code != 200:
                print("API服务未启动")
                return 1
        except Exception:
            print("无法连接到API服务，请先启动: uvicorn src.main:app --port 8000")
            return 1
    
    # 获取想定ID
    scenario_id = await get_active_scenario()
    if not scenario_id:
        print("未找到活动想定，使用临时UUID")
        scenario_id = str(uuid4())
    
    print(f"\n使用想定ID: {scenario_id}")
    
    # 执行测试
    area_id = await test_create_risk_area(scenario_id)
    
    if area_id:
        await test_update_risk_level(area_id)
        await test_update_passage_status(area_id)
    
    await test_list_warnings()
    
    print("\n" + "=" * 60)
    print("测试完成！请检查:")
    print("1. 服务器日志中的 [风险区域通知] 和 [early_warning] 日志")
    print("2. WebSocket 客户端是否收到 risk_area_change 事件")
    print("3. early_warning_records 表中是否有新记录")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
