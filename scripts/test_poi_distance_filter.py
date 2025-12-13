"""测试脚本：验证 POI 距离筛选逻辑"""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 事件位置（茂县地震）
        event_id = "411196cf-f923-48c2-b19c-00ab770553a6"
        
        # 获取事件位置
        event_result = await db.execute(text("""
            SELECT ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat, title
            FROM operational_v2.events_v2
            WHERE id = :event_id
        """), {"event_id": event_id})
        event_row = event_result.fetchone()
        
        if not event_row:
            print("事件不存在")
            return
        
        print(f"事件: {event_row.title[:50]}...")
        print(f"位置: ({event_row.lon:.4f}, {event_row.lat:.4f})")
        
        # 使用 PostGIS 计算距离，只加载50km以内的POI
        MAX_DISTANCE = 50000  # 50km
        
        poi_result = await db.execute(text("""
            SELECT id, name, poi_type, 
                   ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat,
                   ST_Distance(
                       location::geography, 
                       ST_SetSRID(ST_MakePoint(:event_lon, :event_lat), 4326)::geography
                   ) as distance_to_event_m
            FROM operational_v2.poi_v2
            WHERE status != 'destroyed'
              AND ST_DWithin(
                  location::geography,
                  ST_SetSRID(ST_MakePoint(:event_lon, :event_lat), 4326)::geography,
                  :max_distance
              )
            ORDER BY distance_to_event_m ASC
        """), {
            "event_lon": event_row.lon,
            "event_lat": event_row.lat,
            "max_distance": MAX_DISTANCE
        })
        
        pois = poi_result.fetchall()
        print(f"\n=== 距离事件{MAX_DISTANCE/1000:.0f}km以内的POI ({len(pois)}个) ===")
        
        for poi in pois:
            dist_km = poi.distance_to_event_m / 1000
            print(f"  {poi.name} ({poi.poi_type}): ({poi.lon:.4f}, {poi.lat:.4f}) - {dist_km:.1f}km")


if __name__ == "__main__":
    asyncio.run(main())
