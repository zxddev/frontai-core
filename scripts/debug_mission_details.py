"""调试脚本：查看侦察方案中的详细任务信息"""
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
        
        # 查看 recon_plan 的完整结构
        recon_plan = plan_data.get("recon_plan", {})
        
        print("=== recon_plan 顶层字段 ===")
        for key in recon_plan.keys():
            value = recon_plan[key]
            if isinstance(value, list):
                print(f"  {key}: list[{len(value)}]")
            elif isinstance(value, dict):
                print(f"  {key}: dict")
            else:
                print(f"  {key}: {type(value).__name__} = {str(value)[:100]}")
        
        # 查看第一个 mission 的完整结构
        missions = recon_plan.get("missions", [])
        if missions:
            print("\n=== 第一个 mission 的完整结构 ===")
            print(json.dumps(missions[0], indent=2, ensure_ascii=False))
        
        # 查看是否有 flight_plans
        flight_plans = recon_plan.get("flight_plans", [])
        print(f"\n=== flight_plans 数量: {len(flight_plans)} ===")
        if flight_plans:
            print("第一个 flight_plan:")
            print(json.dumps(flight_plans[0], indent=2, ensure_ascii=False))
        
        # 查看 plan_data 顶层是否有其他有用信息
        print("\n=== plan_data 顶层字段 ===")
        for key in plan_data.keys():
            value = plan_data[key]
            if isinstance(value, list):
                print(f"  {key}: list[{len(value)}]")
            elif isinstance(value, dict):
                print(f"  {key}: dict with keys {list(value.keys())[:5]}")
            else:
                print(f"  {key}: {type(value).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
