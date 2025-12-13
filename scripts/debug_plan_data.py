"""调试脚本：查看 recon_plans 表中的 plan_data 数据格式"""
import asyncio
import json
import math
from sqlalchemy import text
from src.core.database import AsyncSessionLocal


def _waypoints_from_geometry(geometry):
    """测试版本的航点生成函数"""
    if not isinstance(geometry, dict):
        print(f"  [WARN] geometry不是dict: {type(geometry)}")
        return []

    geom_type = geometry.get("type", "").lower()
    coords = geometry.get("coordinates")
    print(f"  geom_type={geom_type}, coords类型={type(coords)}, coords长度={len(coords) if isinstance(coords, list) else 'N/A'}")
    
    if not coords:
        return []

    # 处理多边形 - 沿边界飞行
    if geom_type == "polygon" and isinstance(coords, list) and len(coords) > 0:
        outer_ring = coords[0] if isinstance(coords[0], list) else coords
        print(f"  Polygon外环长度: {len(outer_ring)}")
        waypoints = []
        for point in outer_ring:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                lng, lat = float(point[0]), float(point[1])
                if math.isfinite(lng) and math.isfinite(lat):
                    waypoints.append({"lng": lng, "lat": lat})
        print(f"  生成航点数: {len(waypoints)}")
        if len(waypoints) >= 2:
            return waypoints

    # 处理 Point - 生成小矩形
    if geom_type == "point" and isinstance(coords, list) and len(coords) >= 2:
        lng, lat = float(coords[0]), float(coords[1])
        delta = 0.002
        lng2 = max(-180.0, min(180.0, lng + delta))
        lat2 = max(-90.0, min(90.0, lat + delta))
        waypoints = [
            {"lng": lng, "lat": lat},
            {"lng": lng2, "lat": lat},
            {"lng": lng2, "lat": lat2},
            {"lng": lng, "lat": lat2},
            {"lng": lng, "lat": lat},
        ]
        print(f"  Point生成矩形航点: {len(waypoints)}")
        return waypoints

    print(f"  [WARN] 未处理的geometry类型: {geom_type}")
    return []


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
            print("没有找到侦察方案数据")
            return
        
        print(f"plan_id: {row.plan_id}")
        print(f"incident_id: {row.incident_id}")
        print()
        
        plan_data = row.plan_data
        if isinstance(plan_data, str):
            plan_data = json.loads(plan_data)
        
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
        
        print(f"targets 数量: {len(targets)}")
        print(f"target_by_id 数量: {len(target_by_id)}")
        print(f"target_by_name 数量: {len(target_by_name)}")
        
        # 查看 recon_plan.missions
        recon_plan = plan_data.get("recon_plan", {})
        missions = recon_plan.get("missions", [])
        print(f"\nmissions 数量: {len(missions)}")
        
        # 模拟 _build_fallback_flight_plans_from_initial_scan 的逻辑
        print("\n=== 模拟航线生成 ===")
        for i, mission in enumerate(missions[:5]):
            print(f"\n--- Mission {i+1} ---")
            device_name = mission.get("deviceName") or mission.get("device_name") or ""
            target_id = mission.get("targetId") or mission.get("target_id")
            target_name = mission.get("targetName") or mission.get("target_name")
            
            print(f"deviceName: {device_name}")
            print(f"targetId: {target_id}")
            print(f"targetName: {target_name}")
            
            # 查找 target
            target = None
            if target_id:
                target = target_by_id.get(str(target_id))
                print(f"  通过ID找到target: {target is not None}")
            if not target and target_name:
                target = target_by_name.get(target_name)
                print(f"  通过name找到target: {target is not None}")
            
            if target:
                geometry = target.get("geometry", {})
                print(f"  geometry: {geometry.get('type')}")
                waypoints = _waypoints_from_geometry(geometry)
                print(f"  最终航点数: {len(waypoints)}")
                if waypoints:
                    print(f"  前3个航点: {waypoints[:3]}")
            else:
                print(f"  [ERROR] 未找到target!")


if __name__ == "__main__":
    asyncio.run(main())
