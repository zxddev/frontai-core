"""检查侦察方案中目标的距离"""
import asyncio
import json
import math
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


def haversine_distance(lon1, lat1, lon2, lat2):
    """计算两点之间的距离（km）"""
    R = 6371  # 地球半径（km）
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


async def main():
    async with AsyncSessionLocal() as db:
        # 事件位置（茂县地震）
        event_lon, event_lat = 103.7975, 31.7022
        
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
        
        # 构建 target 索引
        targets = plan_data.get("targets", [])
        target_by_id = {}
        for target in targets:
            target_id = target.get("id")
            if target_id:
                target_by_id[str(target_id)] = target
        
        # 查看 missions 中的目标距离
        recon_plan = plan_data.get("recon_plan", {})
        missions = recon_plan.get("missions", [])
        
        print(f"事件位置: ({event_lon:.4f}, {event_lat:.4f})")
        print(f"\n=== 侦察方案中的任务 ({len(missions)} 个) ===")
        
        within_50km = []
        beyond_50km = []
        
        for mission in missions:
            device_name = mission.get("deviceName") or ""
            device_type = mission.get("deviceType") or ""
            target_id = mission.get("targetId")
            target_name = mission.get("targetName") or ""
            
            target = target_by_id.get(str(target_id)) if target_id else None
            
            if target:
                geometry = target.get("geometry", {})
                coords = geometry.get("coordinates", [])
                geom_type = geometry.get("type", "")
                
                # 获取中心点
                if geom_type == "Point":
                    center_lon, center_lat = coords[0], coords[1]
                elif geom_type == "Polygon" and coords:
                    outer_ring = coords[0]
                    lngs = [p[0] for p in outer_ring]
                    lats = [p[1] for p in outer_ring]
                    center_lon = sum(lngs) / len(lngs)
                    center_lat = sum(lats) / len(lats)
                else:
                    center_lon, center_lat = None, None
                
                if center_lon and center_lat:
                    dist_km = haversine_distance(event_lon, event_lat, center_lon, center_lat)
                    
                    info = {
                        "device": device_name,
                        "type": device_type,
                        "target": target_name,
                        "distance": dist_km
                    }
                    
                    if dist_km <= 50:
                        within_50km.append(info)
                    else:
                        beyond_50km.append(info)
        
        print(f"\n--- 50km以内的目标 ({len(within_50km)} 个) ---")
        for info in within_50km:
            print(f"  {info['device']} ({info['type']}) -> {info['target']}: {info['distance']:.1f}km")
        
        print(f"\n--- 超过50km的目标 ({len(beyond_50km)} 个) ---")
        for info in beyond_50km:
            print(f"  {info['device']} ({info['type']}) -> {info['target']}: {info['distance']:.1f}km")


if __name__ == "__main__":
    asyncio.run(main())
