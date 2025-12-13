"""调试脚本：查看侦察方案中的 assignments"""
import asyncio
import json
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 查询最新的侦察方案
        result = await db.execute(text("""
            SELECT plan_id, incident_id, plan_data 
            FROM operational_v2.recon_plans
            WHERE plan_type = 'recon'
            ORDER BY created_at DESC 
            LIMIT 1
        """))
        row = result.fetchone()
        if not row:
            print("没有找到侦察方案")
            return
        
        plan_data = row.plan_data
        if isinstance(plan_data, str):
            plan_data = json.loads(plan_data)
        
        # 查看 assignments
        assignments = plan_data.get("assignments", [])
        print(f"=== assignments 数量: {len(assignments)} ===")
        
        if assignments:
            print("\n第一个 assignment:")
            print(json.dumps(assignments[0], indent=2, ensure_ascii=False))
            
            print("\n=== 所有 assignments 摘要 ===")
            for i, a in enumerate(assignments):
                device_name = a.get("deviceName") or a.get("device_name") or ""
                target_name = a.get("targetName") or a.get("target_name") or ""
                print(f"{i+1}. {device_name} -> {target_name}")
        
        # 查看 devices
        devices = plan_data.get("devices", [])
        print(f"\n=== devices 数量: {len(devices)} ===")
        if devices:
            print("\n第一个 device:")
            print(json.dumps(devices[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
