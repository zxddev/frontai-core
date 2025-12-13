"""调试脚本：查看 recon_plans 的完整数据结构"""
import asyncio
import json
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
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
        
        # 查看 recon_plan 结构
        recon_plan = plan_data.get('recon_plan', {})
        print('=== recon_plan 结构 ===')
        print('keys:', list(recon_plan.keys()))
        
        # 查看 missions
        missions = recon_plan.get('missions', [])
        print(f'\nmissions 数量: {len(missions)}')
        if missions:
            print('\n=== 前3个 missions ===')
            for i, m in enumerate(missions[:3]):
                print(f'\n--- Mission {i+1} ---')
                print(json.dumps(m, indent=2, ensure_ascii=False))
        
        # 查看 flight_plans
        flight_plans = recon_plan.get('flight_plans', [])
        print(f'\n\nflight_plans 数量: {len(flight_plans)}')
        if flight_plans:
            print('\n=== 前2个 flight_plans ===')
            for i, fp in enumerate(flight_plans[:2]):
                print(f'\n--- Flight Plan {i+1} ---')
                # 只显示前5个航点
                fp_copy = fp.copy()
                if 'waypoints' in fp_copy and len(fp_copy['waypoints']) > 5:
                    fp_copy['waypoints'] = fp_copy['waypoints'][:5] + [f'... 共{len(fp["waypoints"])}个航点']
                print(json.dumps(fp_copy, indent=2, ensure_ascii=False))
        
        # 查看 targets
        targets = plan_data.get('targets', [])
        print(f'\n\ntargets 数量: {len(targets)}')
        
        # 统计 geometry 类型
        geom_types = {}
        for t in targets:
            geom = t.get('geometry', {})
            gtype = geom.get('type', 'unknown')
            geom_types[gtype] = geom_types.get(gtype, 0) + 1
        print(f'geometry 类型统计: {geom_types}')
        
        # 显示 Polygon 类型的目标
        print('\n=== Polygon 类型目标 ===')
        polygon_targets = [t for t in targets if t.get('geometry', {}).get('type') == 'Polygon']
        for t in polygon_targets[:3]:
            coords = t.get('geometry', {}).get('coordinates', [[]])
            outer_ring = coords[0] if coords else []
            print(f"  - {t.get('name')}: {len(outer_ring)} 个边界点")


if __name__ == "__main__":
    asyncio.run(main())
