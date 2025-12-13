"""测试脚本：验证风险区域的位置"""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 事件位置（茂县地震）
        event_lon, event_lat = 103.7975, 31.7022
        
        print(f"事件位置: ({event_lon:.4f}, {event_lat:.4f})")
        
        # 查看风险区域
        result = await db.execute(text("""
            SELECT id::text, name, area_type, risk_level,
                   ST_X(ST_Centroid(geometry::geometry)) as center_lon,
                   ST_Y(ST_Centroid(geometry::geometry)) as center_lat,
                   ST_Distance(
                       ST_Centroid(geometry::geometry)::geography, 
                       ST_SetSRID(ST_MakePoint(:event_lon, :event_lat), 4326)::geography
                   ) as distance_to_event_m
            FROM operational_v2.disaster_affected_areas_v2
            ORDER BY distance_to_event_m ASC
            LIMIT 20
        """), {"event_lon": event_lon, "event_lat": event_lat})
        
        print("\n=== 风险区域 ===")
        for row in result.fetchall():
            dist_km = row.distance_to_event_m / 1000 if row.distance_to_event_m else 0
            print(f"  {row.name} ({row.area_type}, 风险{row.risk_level}): ({row.center_lon:.4f}, {row.center_lat:.4f}) - {dist_km:.1f}km")


if __name__ == "__main__":
    asyncio.run(main())
