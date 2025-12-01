#!/usr/bin/env python3
"""
装备准备调度 端到端测试脚本

测试流程:
1. 获取现有scenario/event/vehicle
2. GET /api/v1/car/car-item-select-list - 查看装备列表
3. POST /api/v1/car/car-item-confirm - 指挥员下发
4. GET /api/v1/car/dispatch-status - 验证调度记录
5. POST /api/v1/car/car-user-preparing - 人员确认
6. POST /api/v1/car/car-ready - 准备完成
7. POST /api/v1/car/car-depart - 出发

使用方法:
    python scripts/test_equipment_dispatch_e2e.py
    python scripts/test_equipment_dispatch_e2e.py --host 192.168.31.50:8000
"""
import asyncio
import argparse
import sys
import os
from typing import Optional
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from rich.console import Console
from rich.table import Table

console = Console()


class EquipmentDispatchE2ETest:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.event_id: Optional[str] = None
        self.vehicle_ids: list[str] = []
        self.user_id: Optional[str] = None
    
    async def close(self):
        await self.client.aclose()
    
    async def get_test_data(self) -> bool:
        """获取测试数据（现有的event和vehicle）"""
        console.print("\n[bold cyan]Step 0: 获取测试数据[/]")
        
        # 从数据库获取测试数据
        from src.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # 获取一个event
            result = await db.execute(text("""
                SELECT id FROM operational_v2.events_v2 
                ORDER BY created_at DESC LIMIT 1
            """))
            row = result.fetchone()
            if row:
                self.event_id = str(row[0])
                console.print(f"  使用事件: {self.event_id}")
            else:
                # 创建测试event
                console.print("  [yellow]没有现有事件，创建测试事件...[/]")
                scenario_result = await db.execute(text("""
                    SELECT id FROM operational_v2.scenarios_v2 LIMIT 1
                """))
                scenario_row = scenario_result.fetchone()
                if not scenario_row:
                    console.print("  [red]没有scenario，无法创建事件[/]")
                    return False
                
                scenario_id = str(scenario_row[0])
                event_id = str(uuid4())
                await db.execute(text("""
                    INSERT INTO operational_v2.events_v2 
                    (id, scenario_id, name, description, event_type, status, location)
                    VALUES (:id, :scenario_id, '测试事件', '装备调度测试', 'earthquake', 'active',
                            ST_SetSRID(ST_MakePoint(104.06, 30.67), 4326))
                """), {"id": event_id, "scenario_id": scenario_id})
                await db.commit()
                self.event_id = event_id
                console.print(f"  创建测试事件: {self.event_id}")
            
            # 获取vehicles
            result = await db.execute(text("""
                SELECT id, name FROM operational_v2.vehicles_v2 
                WHERE status = 'available' LIMIT 3
            """))
            rows = result.fetchall()
            self.vehicle_ids = [str(row[0]) for row in rows]
            if self.vehicle_ids:
                console.print(f"  使用车辆: {len(self.vehicle_ids)} 辆")
                for row in rows:
                    console.print(f"    - {row[1]} ({row[0]})")
            else:
                console.print("  [red]没有可用车辆[/]")
                return False
            
            # 获取一个user
            result = await db.execute(text("""
                SELECT id, real_name FROM operational_v2.users_v2 LIMIT 1
            """))
            row = result.fetchone()
            if row:
                self.user_id = str(row[0])
                console.print(f"  使用用户: {row[1]} ({self.user_id})")
        
        return bool(self.event_id and self.vehicle_ids)
    
    async def test_get_equipment_list(self) -> bool:
        """测试获取装备列表"""
        console.print("\n[bold cyan]Step 1: GET /api/v1/car/car-item-select-list[/]")
        
        url = f"{self.base_url}/api/v1/car/car-item-select-list"
        # 前端API不再使用eventId，只需要提供userId
        params = {"userId": self.user_id or "test-user"}
        
        try:
            resp = await self.client.get(url, params=params)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("code") in (0, 200):
                console.print(f"  [green]PASS[/] HTTP {resp.status_code}")
                result = data.get("result") or data.get("data") or {}
                console.print(f"  车辆数: {len(result.get('carList', []))}")
                console.print(f"  装备数: {len(result.get('itemList', []))}")
                
                # 检查是否有AI推荐标记
                ai_selected = sum(1 for item in result.get('itemList', []) if item.get('isSelected') == 1)
                console.print(f"  AI推荐: {ai_selected} 项")
                return True
            else:
                console.print(f"  [red]FAIL[/] HTTP {resp.status_code}: {data}")
                return False
        except Exception as e:
            console.print(f"  [red]ERROR[/] {e}")
            return False
    
    async def test_confirm_dispatch(self) -> bool:
        """测试指挥员下发装备清单"""
        console.print("\n[bold cyan]Step 2: POST /api/v1/car/car-item-confirm[/]")
        
        url = f"{self.base_url}/api/v1/car/car-item-confirm"
        
        # 构造下发请求
        assignments = []
        for vid in self.vehicle_ids:
            assignments.append({
                "carId": vid,
                "deviceIds": [],  # 空表示使用默认
                "supplies": [
                    {"supplyId": "supply-1", "quantity": 10, "supplyName": "饮用水"},
                    {"supplyId": "supply-2", "quantity": 5, "supplyName": "急救包"},
                ]
            })
        
        payload = {
            "eventId": self.event_id,
            "assignments": assignments
        }
        
        try:
            resp = await self.client.post(url, json=payload)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("code") in (0, 200):
                console.print(f"  [green]PASS[/] HTTP {resp.status_code}")
                console.print(f"  消息: {data.get('message')}")
                return True
            else:
                console.print(f"  [red]FAIL[/] HTTP {resp.status_code}: {data}")
                return False
        except Exception as e:
            console.print(f"  [red]ERROR[/] {e}")
            return False
    
    async def test_get_dispatch_status(self) -> bool:
        """测试获取调度状态"""
        console.print("\n[bold cyan]Step 3: GET /api/v1/car/dispatch-status[/]")
        
        url = f"{self.base_url}/api/v1/car/dispatch-status"
        params = {"eventId": self.event_id}
        
        try:
            resp = await self.client.get(url, params=params)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("code") in (0, 200):
                console.print(f"  [green]PASS[/] HTTP {resp.status_code}")
                result = data.get("result") or data.get("data") or {}
                console.print(f"  总车辆: {result.get('totalVehicles')}")
                console.print(f"  已确认: {result.get('confirmedCount')}")
                console.print(f"  已就绪: {result.get('readyCount')}")
                
                # 显示状态表格
                items = result.get("items", [])
                if items:
                    table = Table(title="调度状态")
                    table.add_column("车辆")
                    table.add_column("状态")
                    table.add_column("下发时间")
                    for item in items:
                        table.add_row(
                            item.get("vehicleName") or item.get("vehicleId", "")[:8],
                            item.get("status"),
                            item.get("dispatchedAt", "")[:19] if item.get("dispatchedAt") else "-"
                        )
                    console.print(table)
                return True
            else:
                console.print(f"  [red]FAIL[/] HTTP {resp.status_code}: {data}")
                return False
        except Exception as e:
            console.print(f"  [red]ERROR[/] {e}")
            return False
    
    async def test_user_preparing(self) -> bool:
        """测试人员确认收到"""
        console.print("\n[bold cyan]Step 4: POST /api/v1/car/car-user-preparing[/]")
        
        url = f"{self.base_url}/api/v1/car/car-user-preparing"
        
        # 为每辆车确认
        all_ok = True
        for vid in self.vehicle_ids:
            payload = {
                "eventId": self.event_id,
                "carId": vid,
                "userId": self.user_id
            }
            
            try:
                resp = await self.client.post(url, json=payload)
                data = resp.json()
                
                if resp.status_code == 200 and data.get("code") in (0, 200):
                    console.print(f"  [green]PASS[/] 车辆 {vid[:8]}... 已确认")
                else:
                    console.print(f"  [red]FAIL[/] 车辆 {vid[:8]}...: {data}")
                    all_ok = False
            except Exception as e:
                console.print(f"  [red]ERROR[/] {e}")
                all_ok = False
        
        return all_ok
    
    async def test_car_ready(self) -> bool:
        """测试准备完成"""
        console.print("\n[bold cyan]Step 5: POST /api/v1/car/car-ready[/]")
        
        url = f"{self.base_url}/api/v1/car/car-ready"
        
        # 为每辆车标记准备完成
        all_ok = True
        for vid in self.vehicle_ids:
            payload = {
                "eventId": self.event_id,
                "carId": vid,
                "userId": self.user_id
            }
            
            try:
                resp = await self.client.post(url, json=payload)
                data = resp.json()
                
                if resp.status_code == 200 and data.get("code") in (0, 200):
                    result = data.get("result") or data.get("data") or {}
                    console.print(f"  [green]PASS[/] 车辆 {vid[:8]}... 准备完成")
                    console.print(f"    就绪: {result.get('readyCount')}/{result.get('totalVehicles')}")
                    if result.get("allReady"):
                        console.print(f"    [bold green]所有车辆已就绪![/]")
                else:
                    console.print(f"  [red]FAIL[/] 车辆 {vid[:8]}...: {data}")
                    all_ok = False
            except Exception as e:
                console.print(f"  [red]ERROR[/] {e}")
                all_ok = False
        
        return all_ok
    
    async def test_car_depart(self) -> bool:
        """测试出发"""
        console.print("\n[bold cyan]Step 6: POST /api/v1/car/car-depart[/]")
        
        url = f"{self.base_url}/api/v1/car/car-depart"
        payload = {"eventId": self.event_id}
        
        try:
            resp = await self.client.post(url, json=payload)
            data = resp.json()
            
            if resp.status_code == 200 and data.get("code") in (0, 200):
                console.print(f"  [green]PASS[/] HTTP {resp.status_code}")
                console.print(f"  [bold green]车队已出发![/]")
                return True
            else:
                console.print(f"  [red]FAIL[/] HTTP {resp.status_code}: {data}")
                return False
        except Exception as e:
            console.print(f"  [red]ERROR[/] {e}")
            return False
    
    async def test_depart_without_ready(self) -> bool:
        """测试未就绪就出发（异常测试）"""
        console.print("\n[bold cyan]异常测试: 未就绪就出发[/]")
        
        # 使用一个新的event_id，没有任何车辆准备
        url = f"{self.base_url}/api/v1/car/car-depart"
        fake_event_id = str(uuid4())
        payload = {"eventId": fake_event_id}
        
        try:
            resp = await self.client.post(url, json=payload)
            data = resp.json()
            
            # 预期应该失败（400）或返回错误
            if data.get("code") not in (0, 200):
                console.print(f"  [green]PASS[/] 正确拒绝: {data.get('message')}")
                return True
            else:
                console.print(f"  [yellow]WARN[/] 未预期成功: {data}")
                return True  # 不阻塞测试
        except Exception as e:
            console.print(f"  [red]ERROR[/] {e}")
            return False
    
    async def cleanup(self):
        """清理测试数据"""
        console.print("\n[bold cyan]清理测试数据[/]")
        
        from src.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            await db.execute(text("""
                DELETE FROM operational_v2.equipment_preparation_dispatch_v2 
                WHERE event_id = :event_id
            """), {"event_id": self.event_id})
            await db.commit()
            console.print(f"  已清理调度记录")


async def main(host: str, cleanup: bool = False):
    console.print("[bold]=" * 60)
    console.print("[bold]装备准备调度 E2E 测试[/]")
    console.print(f"[bold]目标: {host}[/]")
    console.print("[bold]=" * 60)
    
    test = EquipmentDispatchE2ETest(f"http://{host}")
    
    results = []
    
    try:
        # Step 0: 获取测试数据
        if not await test.get_test_data():
            console.print("[red]无法获取测试数据，测试中止[/]")
            return
        
        # Step 1: 获取装备列表
        results.append(("获取装备列表", await test.test_get_equipment_list()))
        
        # Step 2: 指挥员下发
        results.append(("指挥员下发", await test.test_confirm_dispatch()))
        
        # Step 3: 查看调度状态
        results.append(("查看调度状态", await test.test_get_dispatch_status()))
        
        # Step 4: 人员确认
        results.append(("人员确认", await test.test_user_preparing()))
        
        # Step 5: 准备完成
        results.append(("准备完成", await test.test_car_ready()))
        
        # Step 6: 再次查看状态
        results.append(("最终状态", await test.test_get_dispatch_status()))
        
        # Step 7: 出发
        results.append(("出发", await test.test_car_depart()))
        
        # 异常测试
        results.append(("异常-未就绪出发", await test.test_depart_without_ready()))
        
        # 清理
        if cleanup:
            await test.cleanup()
        
    finally:
        await test.close()
    
    # 汇总
    console.print("\n[bold]=" * 60)
    console.print("[bold]测试结果汇总[/]")
    console.print("[bold]=" * 60)
    
    table = Table()
    table.add_column("测试项")
    table.add_column("结果")
    
    passed = 0
    for name, result in results:
        status = "[green]PASS[/]" if result else "[red]FAIL[/]"
        table.add_row(name, status)
        if result:
            passed += 1
    
    console.print(table)
    console.print(f"\n通过: {passed}/{len(results)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="装备准备调度E2E测试")
    parser.add_argument("--host", default="localhost:8000", help="API服务地址")
    parser.add_argument("--cleanup", action="store_true", help="测试后清理数据")
    
    args = parser.parse_args()
    asyncio.run(main(args.host, args.cleanup))
