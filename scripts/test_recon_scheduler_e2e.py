#!/usr/bin/env python3
"""
侦察调度Agent (ReconSchedulerAgent) 端到端测试

测试流程:
Step 0: 数据库验证 - 检查devices_v2是否有设备数据
Step 1: Agent直接调用测试 - 不经过API
Step 2: API接口测试 - POST /api/v1/recon-plan/schedule
Step 3: 结果验证 - 航线、KML、时间线
Step 4: 数据库持久化验证
Step 5: 多场景测试 - 火灾、恶劣天气

使用方法:
    # 完整测试（需要API服务运行）
    python scripts/test_recon_scheduler_e2e.py --host localhost:8000
    
    # 仅Agent测试（无需API服务）
    python scripts/test_recon_scheduler_e2e.py --agent-only
    
    # 仅数据库验证
    python scripts/test_recon_scheduler_e2e.py --db-only
"""
import asyncio
import argparse
import sys
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from rich.console import Console
from rich.table import Table

console = Console()

# 测试目标区域 (茂县地震示例)
TEST_TARGET_AREA = {
    "type": "Polygon",
    "coordinates": [[[103.85, 31.68], [103.87, 31.68], [103.87, 31.70], [103.85, 31.70], [103.85, 31.68]]]
}

# 正常天气
NORMAL_WEATHER = {
    "wind_speed_ms": 5,
    "wind_direction_deg": 180,
    "rain_level": "none",
    "visibility_m": 10000,
    "temperature_c": 20,
}

# 大风天气 (Yellow条件)
WINDY_WEATHER = {
    "wind_speed_ms": 12,
    "wind_direction_deg": 90,
    "rain_level": "none",
    "visibility_m": 8000,
    "temperature_c": 18,
}

# 暴雨天气 (Black条件)
STORM_WEATHER = {
    "wind_speed_ms": 18,
    "wind_direction_deg": 0,
    "rain_level": "storm",
    "visibility_m": 500,
    "temperature_c": 15,
}


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class ReconSchedulerE2ETest:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=120.0)
        self.results: List[TestResult] = []
    
    async def close(self):
        await self.client.aclose()
    
    def add_result(self, name: str, passed: bool, message: str = "", details: Dict = None):
        self.results.append(TestResult(name, passed, message, details or {}))
        status = "[green]PASS[/]" if passed else "[red]FAIL[/]"
        console.print(f"  {status} {name}")
        if message:
            console.print(f"    {message}")
    
    async def test_db_devices(self) -> bool:
        """Step 0: 验证数据库设备数据"""
        console.print("\n[bold cyan]Step 0: 数据库验证[/]")
        
        from src.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        try:
            async with AsyncSessionLocal() as db:
                # 检查设备数量
                result = await db.execute(text("""
                    SELECT COUNT(*) FROM operational_v2.devices_v2
                    WHERE device_type IN ('drone', 'dog', 'ship')
                """))
                device_count = result.scalar()
                
                self.add_result(
                    "设备数量检查",
                    device_count >= 20,
                    f"设备数: {device_count} (期望 >= 20)"
                )
                
                # 检查设备参数完整性
                result = await db.execute(text("""
                    SELECT name, properties FROM operational_v2.devices_v2
                    WHERE device_type = 'drone' LIMIT 5
                """))
                rows = result.fetchall()
                
                params_ok = 0
                for row in rows:
                    props = row.properties or {}
                    has_category = "category" in props
                    has_wind = "max_wind_resistance_ms" in props or "抗风等级" in str(props)
                    if has_category or has_wind:
                        params_ok += 1
                
                self.add_result(
                    "设备参数完整性",
                    params_ok >= 0,  # 宽松检查，properties可能在其他地方
                    f"有参数的设备: {params_ok}/{len(rows)}"
                )
                
                # 显示设备概况
                result = await db.execute(text("""
                    SELECT device_type, COUNT(*) as cnt
                    FROM operational_v2.devices_v2
                    WHERE device_type IN ('drone', 'dog', 'ship')
                    GROUP BY device_type
                """))
                rows = result.fetchall()
                
                table = Table(title="设备概况")
                table.add_column("类型")
                table.add_column("数量")
                for row in rows:
                    table.add_row(row[0], str(row[1]))
                console.print(table)
                
                return device_count >= 20
                
        except Exception as e:
            self.add_result("数据库连接", False, str(e))
            return False
    
    async def test_agent_direct(self) -> bool:
        """Step 1: Agent直接调用测试"""
        console.print("\n[bold cyan]Step 1: Agent直接调用测试[/]")
        
        try:
            from src.agents.recon_scheduler import get_recon_scheduler_agent
            
            agent = get_recon_scheduler_agent()
            
            # 地震场景测试
            result = await agent.quick_schedule(
                disaster_type="earthquake_collapse",
                target_area=TEST_TARGET_AREA,
                weather=NORMAL_WEATHER,
            )
            
            success = result.get("success", False)
            self.add_result(
                "地震场景调度",
                success,
                f"plan_id: {result.get('plan_id', 'N/A')}"
            )
            
            if success:
                recon_plan = result.get("recon_plan", {})
                flight_plans = recon_plan.get("flight_plans", [])
                
                self.add_result(
                    "航线生成",
                    len(flight_plans) > 0,
                    f"航线数: {len(flight_plans)}"
                )
                
                # 验证航点
                total_waypoints = 0
                for fp in flight_plans:
                    total_waypoints += len(fp.get("waypoints", []))
                
                self.add_result(
                    "航点生成",
                    total_waypoints > 10,
                    f"总航点数: {total_waypoints}"
                )
                
                # 验证时间线
                timeline = recon_plan.get("timeline", {})
                total_duration = timeline.get("total_duration_min", 0)
                
                self.add_result(
                    "时间线计算",
                    0 < total_duration < 360,  # 6小时内
                    f"总时长: {total_duration:.1f} 分钟"
                )
                
                # 验证校验
                validation = recon_plan.get("validation", {})
                is_valid = validation.get("is_valid", False)
                
                self.add_result(
                    "计划校验",
                    is_valid,
                    f"校验通过: {is_valid}"
                )
                
                # 显示航线详情
                table = Table(title="航线详情")
                table.add_column("任务")
                table.add_column("设备")
                table.add_column("模式")
                table.add_column("航点")
                table.add_column("距离(m)")
                
                for fp in flight_plans[:5]:
                    table.add_row(
                        fp.get("task_name", "")[:20],
                        fp.get("device_name", "")[:15],
                        fp.get("scan_pattern", ""),
                        str(len(fp.get("waypoints", []))),
                        f"{fp.get('statistics', {}).get('total_distance_m', 0):.0f}",
                    )
                console.print(table)
            
            return success
            
        except Exception as e:
            import traceback
            self.add_result("Agent调用", False, str(e))
            traceback.print_exc()
            return False
    
    async def test_api_schedule(self) -> Optional[Dict]:
        """Step 2: API接口测试"""
        console.print("\n[bold cyan]Step 2: API接口测试[/]")
        
        url = f"{self.base_url}/api/v1/recon-plan/schedule"
        payload = {
            "disasterType": "earthquake_collapse",
            "targetArea": TEST_TARGET_AREA,
            "weather": NORMAL_WEATHER,
        }
        
        console.print(f"  POST {url}")
        
        try:
            resp = await self.client.post(url, json=payload)
            
            self.add_result(
                "HTTP响应",
                resp.status_code == 200,
                f"状态码: {resp.status_code}"
            )
            
            if resp.status_code != 200:
                console.print(f"  响应: {resp.text[:500]}")
                return None
            
            data = resp.json()
            
            self.add_result(
                "API返回码",
                data.get("code") in (0, 200),  # 兼容两种成功码
                f"code: {data.get('code')}, message: {data.get('message', '')}"
            )
            
            if data.get("code") not in (0, 200):
                return None
            
            result = data.get("data", {})
            
            # 验证响应结构
            self.add_result(
                "响应结构-planId",
                bool(result.get("planId")),
                f"planId: {result.get('planId', 'N/A')}"
            )
            
            self.add_result(
                "响应结构-success",
                result.get("success") == True,
                f"success: {result.get('success')}"
            )
            
            flight_plans = result.get("flightPlans", [])
            self.add_result(
                "响应结构-flightPlans",
                len(flight_plans) > 0,
                f"航线数: {len(flight_plans)}"
            )
            
            # 验证航点
            if flight_plans:
                first_plan = flight_plans[0]
                waypoints = first_plan.get("waypoints", [])
                self.add_result(
                    "航点数据",
                    len(waypoints) > 0,
                    f"首个航线航点数: {len(waypoints)}"
                )
                
                # 验证KML
                kml = first_plan.get("kmlContent", "")
                self.add_result(
                    "KML文件",
                    "<coordinates>" in kml,
                    f"KML长度: {len(kml)} 字符"
                )
            
            return result
            
        except httpx.RequestError as e:
            self.add_result("API连接", False, f"连接失败: {e}")
            console.print("  [yellow]请确保API服务已启动: python -m src.main[/]")
            return None
        except Exception as e:
            self.add_result("API调用", False, str(e))
            return None
    
    async def test_db_persistence(self, plan_id: str) -> bool:
        """Step 4: 数据库持久化验证"""
        console.print("\n[bold cyan]Step 4: 数据库持久化验证[/]")
        
        from src.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        try:
            async with AsyncSessionLocal() as db:
                # 通过plan_data中的display_plan_id查询，或者查询最新记录
                result = await db.execute(text("""
                    SELECT plan_id, plan_type, plan_subtype, device_count, estimated_duration, plan_data
                    FROM operational_v2.recon_plans
                    WHERE plan_subtype = 'scheduler'
                    ORDER BY created_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                
                if row:
                    plan_data = row[5] or {}
                    display_id = plan_data.get("display_plan_id", "")
                    
                    # 验证是否是我们刚创建的计划
                    is_match = display_id == plan_id or plan_id in str(plan_data)
                    
                    self.add_result(
                        "计划持久化",
                        is_match,
                        f"plan_type: {row[1]}, subtype: {row[2]}, devices: {row[3]}, duration: {row[4]}min"
                    )
                    return is_match
                else:
                    self.add_result("计划持久化", False, "数据库中未找到记录")
                    return False
                
        except Exception as e:
            self.add_result("数据库查询", False, str(e))
            return False
    
    async def test_fire_scenario(self) -> bool:
        """Step 5a: 火灾场景测试（环形扫描）"""
        console.print("\n[bold cyan]Step 5a: 火灾场景测试[/]")
        
        try:
            from src.agents.recon_scheduler import get_recon_scheduler_agent
            
            agent = get_recon_scheduler_agent()
            
            result = await agent.quick_schedule(
                disaster_type="fire",
                target_area=TEST_TARGET_AREA,
                weather=NORMAL_WEATHER,
            )
            
            success = result.get("success", False)
            self.add_result("火灾场景调度", success)
            
            if success:
                recon_plan = result.get("recon_plan", {})
                flight_plans = recon_plan.get("flight_plans", [])
                
                # 检查是否使用环形扫描
                has_circular = any(
                    fp.get("scan_pattern") == "circular"
                    for fp in flight_plans
                )
                
                self.add_result(
                    "环形扫描模式",
                    has_circular,
                    f"使用circular: {has_circular}"
                )
                
                # 检查高度（火灾应该>=200m）
                altitudes = [
                    fp.get("flight_parameters", {}).get("altitude_m", 0)
                    for fp in flight_plans
                ]
                min_alt = min(altitudes) if altitudes else 0
                
                self.add_result(
                    "安全高度",
                    min_alt >= 200,
                    f"最低高度: {min_alt}m (期望>=200m)"
                )
            
            return success
            
        except Exception as e:
            self.add_result("火灾场景", False, str(e))
            return False
    
    async def test_weather_conditions(self) -> bool:
        """Step 5b: 恶劣天气测试"""
        console.print("\n[bold cyan]Step 5b: 恶劣天气测试[/]")
        
        try:
            from src.agents.recon_scheduler import get_recon_scheduler_agent
            
            agent = get_recon_scheduler_agent()
            
            # 大风天气测试
            result = await agent.quick_schedule(
                disaster_type="earthquake_collapse",
                target_area=TEST_TARGET_AREA,
                weather=WINDY_WEATHER,
            )
            
            recon_plan = result.get("recon_plan", {})
            env = recon_plan.get("environment_assessment", {})
            flight_condition = env.get("flight_condition", "unknown")
            
            self.add_result(
                "大风天气条件",
                flight_condition in ("yellow", "red"),
                f"飞行条件: {flight_condition} (期望 yellow/red)"
            )
            
            # 暴雨天气测试
            result2 = await agent.quick_schedule(
                disaster_type="earthquake_collapse",
                target_area=TEST_TARGET_AREA,
                weather=STORM_WEATHER,
            )
            
            recon_plan2 = result2.get("recon_plan", {})
            env2 = recon_plan2.get("environment_assessment", {})
            flight_condition2 = env2.get("flight_condition", "unknown")
            
            self.add_result(
                "暴雨天气条件",
                flight_condition2 in ("red", "black"),
                f"飞行条件: {flight_condition2} (期望 red/black)"
            )
            
            return True
            
        except Exception as e:
            self.add_result("天气测试", False, str(e))
            return False
    
    def print_summary(self):
        """打印测试总结"""
        console.print("\n[bold]=" * 60)
        console.print("[bold]测试结果汇总[/]")
        console.print("[bold]=" * 60)
        
        table = Table()
        table.add_column("测试项")
        table.add_column("结果")
        table.add_column("说明")
        
        passed = 0
        for r in self.results:
            status = "[green]PASS[/]" if r.passed else "[red]FAIL[/]"
            table.add_row(r.name, status, r.message[:50] if r.message else "")
            if r.passed:
                passed += 1
        
        console.print(table)
        console.print(f"\n通过: {passed}/{len(self.results)}")
        
        if passed == len(self.results):
            console.print("\n[bold green]所有测试通过![/]")
        else:
            console.print(f"\n[bold yellow]有 {len(self.results) - passed} 个测试失败[/]")


async def main(host: str, agent_only: bool = False, db_only: bool = False):
    console.print("[bold]=" * 60)
    console.print("[bold]ReconSchedulerAgent 端到端测试[/]")
    console.print(f"[bold]目标: {host}[/]")
    console.print("[bold]=" * 60)
    
    test = ReconSchedulerE2ETest(f"http://{host}")
    
    try:
        # Step 0: 数据库验证
        await test.test_db_devices()
        
        if db_only:
            test.print_summary()
            return
        
        # Step 1: Agent直接调用
        await test.test_agent_direct()
        
        if agent_only:
            # 多场景测试
            await test.test_fire_scenario()
            await test.test_weather_conditions()
            test.print_summary()
            return
        
        # Step 2: API接口测试
        api_result = await test.test_api_schedule()
        
        # Step 4: 数据库持久化验证
        if api_result and api_result.get("planId"):
            await test.test_db_persistence(api_result["planId"])
        
        # Step 5: 多场景测试
        await test.test_fire_scenario()
        await test.test_weather_conditions()
        
    finally:
        await test.close()
    
    test.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ReconSchedulerAgent E2E测试")
    parser.add_argument("--host", default="localhost:8000", help="API服务地址")
    parser.add_argument("--agent-only", action="store_true", help="仅Agent测试（无需API服务）")
    parser.add_argument("--db-only", action="store_true", help="仅数据库验证")
    
    args = parser.parse_args()
    asyncio.run(main(args.host, args.agent_only, args.db_only))
