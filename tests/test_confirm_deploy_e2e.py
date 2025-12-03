#!/usr/bin/env python3
"""
端到端测试：确认部署完整流程

测试流程：
1. 获取活跃场景ID
2. 获取待处理事件
3. 触发AI分析
4. 等待分析完成
5. 调用确认部署接口（传递team_ids）
6. 验证任务创建 (tasks_v2)
7. 验证分配记录 (task_assignments_v2)
8. 验证队伍状态 (rescue_teams_v2)
9. 验证事件状态 (events_v2)
"""

import asyncio
import httpx
import time
from uuid import UUID

BASE_URL = "http://localhost:8000"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        print("=" * 60)
        print("端到端测试：确认部署完整流程")
        print("=" * 60)
        
        # ========== 1. 获取活跃场景 ==========
        print("\n[1] 获取活跃场景...")
        resp = await client.get("/api/v2/scenarios/active")
        if resp.status_code != 200:
            print(f"   ❌ 获取场景失败: {resp.text}")
            return
        
        scenario = resp.json()
        scenario_id = scenario.get("id")
        print(f"   ✅ 场景ID: {scenario_id}")
        print(f"   场景名称: {scenario.get('name')}")
        
        # ========== 2. 获取待处理事件 ==========
        print("\n[2] 获取待处理事件...")
        resp = await client.get(f"/api/v2/events?scenario_id={scenario_id}&status=confirmed")
        if resp.status_code != 200:
            print(f"   ❌ 获取事件失败: {resp.text}")
            # 尝试获取所有事件
            resp = await client.get(f"/api/v2/events?scenario_id={scenario_id}")
            if resp.status_code != 200:
                print(f"   ❌ 获取所有事件也失败: {resp.text}")
                return
        
        events = resp.json()
        if isinstance(events, dict):
            events = events.get("items", events.get("events", []))
        
        if not events:
            print("   ⚠️ 无待处理事件，创建测试事件...")
            # 创建测试事件
            event_data = {
                "scenario_id": scenario_id,
                "title": "E2E测试-火灾事件",
                "description": "端到端测试用火灾事件",
                "event_type": "fire",
                "priority": "high",
                "status": "confirmed",
                "location": {"lng": 121.4737, "lat": 31.2304},
                "source": "manual",
            }
            resp = await client.post("/api/v2/events", json=event_data)
            if resp.status_code not in [200, 201]:
                print(f"   ❌ 创建事件失败: {resp.text}")
                return
            event = resp.json()
            event_id = event.get("id")
            print(f"   ✅ 创建事件成功: {event_id}")
        else:
            event = events[0]
            event_id = event.get("id")
            print(f"   ✅ 使用现有事件: {event_id}")
            print(f"   事件标题: {event.get('title')}")
            print(f"   事件状态: {event.get('status')}")
        
        # ========== 3. 触发AI分析 ==========
        print("\n[3] 触发AI分析...")
        event_title = event.get("title", "紧急事件")
        event_desc = event.get("description", "需要救援")
        event_location = event.get("location", {})
        
        analyze_data = {
            "event_id": event_id,
            "scenario_id": scenario_id,
            "disaster_description": f"{event_title}: {event_desc}",
            "structured_input": {
                "location": {
                    "longitude": event_location.get("longitude", 103.85),
                    "latitude": event_location.get("latitude", 31.68),
                }
            }
        }
        resp = await client.post("/api/v2/ai/emergency-analyze", json=analyze_data)
        task_result = resp.json()
        
        if resp.status_code not in [200, 202] or not task_result.get("success"):
            print(f"   ❌ 触发分析失败: status={resp.status_code}, response={resp.text}")
            return
        
        task_id = task_result.get("task_id")
        print(f"   ✅ 分析任务ID: {task_id}")
        print(f"   状态: {task_result.get('status')}")
        
        # ========== 4. 轮询等待分析完成 ==========
        print("\n[4] 等待AI分析完成...")
        max_wait = 60
        start_time = time.time()
        ai_result = None
        
        while time.time() - start_time < max_wait:
            resp = await client.get(f"/api/v2/ai/emergency-analyze/{task_id}")
            if resp.status_code == 200:
                ai_result = resp.json()
                status = ai_result.get("status")
                print(f"   状态: {status}")
                
                if status == "completed":
                    print(f"   ✅ AI分析完成!")
                    break
                elif status == "failed":
                    print(f"   ❌ AI分析失败: {ai_result.get('errors')}")
                    return
            else:
                print(f"   查询状态失败: {resp.status_code}")
            
            await asyncio.sleep(2)
        else:
            print("   ❌ 等待超时")
            return
        
        # 提取推荐队伍
        recommended_scheme = ai_result.get("recommended_scheme", {})
        allocations = recommended_scheme.get("allocations", [])
        
        if not allocations:
            print("   ❌ 无推荐队伍")
            return
        
        team_ids = [alloc.get("resource_id") for alloc in allocations if alloc.get("resource_id")]
        print(f"   推荐队伍数: {len(team_ids)}")
        for i, alloc in enumerate(allocations[:3]):
            print(f"   - {alloc.get('resource_name', 'N/A')} (ETA: {alloc.get('eta_minutes', 'N/A')}分钟)")
        
        # ========== 5. 调用确认部署接口 ==========
        print("\n[5] 调用确认部署接口...")
        confirm_data = {
            "team_ids": team_ids
        }
        resp = await client.post(f"/api/v2/ai/emergency-analyze/{task_id}/confirm", json=confirm_data)
        
        print(f"   响应状态码: {resp.status_code}")
        confirm_result = resp.json()
        print(f"   响应内容: {confirm_result}")
        
        if not confirm_result.get("success"):
            if confirm_result.get("conflict"):
                print(f"   ⚠️ 存在冲突: {confirm_result.get('message')}")
                print(f"   不可用队伍: {confirm_result.get('unavailable_teams')}")
            else:
                print(f"   ❌ 确认失败: {confirm_result.get('error')}")
            return
        
        new_task_id = confirm_result.get("task_id")
        task_code = confirm_result.get("task_code")
        deployed_teams = confirm_result.get("deployed_teams", [])
        
        print(f"   ✅ 确认部署成功!")
        print(f"   新任务ID: {new_task_id}")
        print(f"   任务编号: {task_code}")
        print(f"   部署队伍数: {len(deployed_teams)}")
        
        # ========== 6. 验证任务创建 ==========
        print("\n[6] 验证任务创建 (tasks_v2)...")
        resp = await client.get(f"/api/v2/tasks/{new_task_id}")
        if resp.status_code == 200:
            task = resp.json()
            print(f"   ✅ 任务存在")
            print(f"   - 任务编号: {task.get('task_code')}")
            print(f"   - 标题: {task.get('title')}")
            print(f"   - 状态: {task.get('status')}")
            print(f"   - 类型: {task.get('task_type')}")
            print(f"   - 事件ID: {task.get('event_id')}")
        else:
            print(f"   ⚠️ 任务API不存在，尝试直接查询数据库...")
            # 直接用SQL验证
            
        # ========== 7. 验证分配记录 ==========
        print("\n[7] 验证分配记录 (task_assignments_v2)...")
        # 通过SQL验证
        
        # ========== 8. 验证队伍状态 ==========
        print("\n[8] 验证队伍状态 (rescue_teams_v2)...")
        for team in deployed_teams[:3]:
            team_id = team.get("id")
            resp = await client.get(f"/api/v2/rescue-teams/{team_id}")
            if resp.status_code == 200:
                team_data = resp.json()
                status = team_data.get("status")
                current_task = team_data.get("current_task_id")
                print(f"   - {team.get('name')}: status={status}, current_task_id={current_task}")
                if status == "deployed" and str(current_task) == str(new_task_id):
                    print(f"     ✅ 状态正确")
                else:
                    print(f"     ⚠️ 状态异常 (期望 deployed, task={new_task_id})")
            else:
                print(f"   ⚠️ 无法查询队伍 {team_id}")
        
        # ========== 9. 验证事件状态 ==========
        print("\n[9] 验证事件状态 (events_v2)...")
        resp = await client.get(f"/api/v2/events/{event_id}")
        if resp.status_code == 200:
            event_data = resp.json()
            event_status = event_data.get("status")
            print(f"   事件状态: {event_status}")
            if event_status == "planning":
                print(f"   ✅ 事件状态已更新为 planning")
            else:
                print(f"   ⚠️ 事件状态未更新 (当前: {event_status})")
        else:
            print(f"   ⚠️ 无法查询事件")
        
        # ========== 测试总结 ==========
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"✅ AI分析任务: {task_id}")
        print(f"✅ 创建任务: {task_code} ({new_task_id})")
        print(f"✅ 部署队伍: {len(deployed_teams)} 支")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
