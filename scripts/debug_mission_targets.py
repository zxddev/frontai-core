"""调试脚本：查看侦察方案中设备和目标的对应关系"""
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
        
        # 查看事件位置
        print("=== 查询事件位置 ===")
        event_result = await db.execute(text("""
            SELECT 
                id::text, title,
                ST_X(location::geometry) as lng,
                ST_Y(location::geometry) as lat
            FROM operational_v2.events_v2
            WHERE id = :event_id
        """), {"event_id": str(row.incident_id)})
        event_row = event_result.fetchone()
        if event_row:
            print(f"事件: {event_row.title}")
            print(f"位置: ({event_row.lng}, {event_row.lat})")
        
        # 构建 target 索引
        targets = plan_data.get("targets", [])
        target_by_id = {}
        target_by_name = {}
        for target in targets:
            target_id = target.get("id")
            target_name = target.get("name")
            if target_id:
                target_by_id[str(target_id)] = target
            if target_name:
                target_by_name[target_name] = target
        
        # 查看 missions 中的设备和目标对应关系
        recon_plan = plan_data.get("recon_plan", {})
        missions = recon_plan.get("missions", [])
        
        print(f"\n=== 侦察方案中的任务分配 ({len(missions)} 个任务) ===")
        for i, mission in enumerate(missions):
            device_name = mission.get("deviceName") or mission.get("device_name") or ""
            device_type = mission.get("deviceType") or mission.get("device_type") or ""
            target_id = mission.get("targetId") or mission.get("target_id")
            target_name = mission.get("targetName") or mission.get("target_name")
            
            # 查找目标
            target = None
            if target_id:
                target = target_by_id.get(str(target_id))
            if not target and target_name:
                target = target_by_name.get(target_name)
            
            # 获取目标坐标
            if target:
                geometry = target.get("geometry", {})
                geom_type = geometry.get("type", "")
                coords = geometry.get("coordinates", [])
                
                # 获取中心点坐标
                if geom_type == "Point":
                    center = coords
                elif geom_type == "Polygon" and coords:
                    # 计算多边形中心
                    outer_ring = coords[0] if coords else []
                    if outer_ring:
                        lngs = [p[0] for p in outer_ring if len(p) >= 2]
                        lats = [p[1] for p in outer_ring if len(p) >= 2]
                        center = [sum(lngs)/len(lngs), sum(lats)/len(lats)] if lngs else []
                    else:
                        center = []
                else:
                    center = []
                
                print(f"\n{i+1}. {device_name} ({device_type})")
                print(f"   目标: {target_name}")
                print(f"   类型: {geom_type}")
                if center:
                    print(f"   坐标: ({center[0]:.6f}, {center[1]:.6f})")
            else:
                print(f"\n{i+1}. {device_name} ({device_type})")
                print(f"   目标: {target_name} [未找到]")


if __name__ == "__main__":
    asyncio.run(main())
