"""调试脚本：查看 POI 的距离数据"""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 查看 POI 的距离数据
        print("=== POI 距离数据 ===")
        result = await db.execute(text("""
            SELECT name, poi_type, 
                   ST_X(location::geometry) as lng, ST_Y(location::geometry) as lat,
                   distance_to_epicenter_m
            FROM operational_v2.poi_v2
            WHERE status != 'destroyed'
            ORDER BY distance_to_epicenter_m ASC NULLS LAST
            LIMIT 30
        """))
        
        for row in result.fetchall():
            dist = row.distance_to_epicenter_m
            dist_str = f"{dist/1000:.1f}km" if dist else "NULL"
            print(f"  {row.name}: ({row.lng:.4f}, {row.lat:.4f}) - {dist_str}")
        
        # 统计距离分布
        print("\n=== 距离分布统计 ===")
        result = await db.execute(text("""
            SELECT 
                CASE 
                    WHEN distance_to_epicenter_m IS NULL THEN 'NULL'
                    WHEN distance_to_epicenter_m <= 10000 THEN '0-10km'
                    WHEN distance_to_epicenter_m <= 30000 THEN '10-30km'
                    WHEN distance_to_epicenter_m <= 50000 THEN '30-50km'
                    WHEN distance_to_epicenter_m <= 100000 THEN '50-100km'
                    ELSE '>100km'
                END as distance_range,
                COUNT(*) as count
            FROM operational_v2.poi_v2
            WHERE status != 'destroyed'
            GROUP BY distance_range
            ORDER BY distance_range
        """))
        
        for row in result.fetchall():
            print(f"  {row.distance_range}: {row.count} 个")


if __name__ == "__main__":
    asyncio.run(main())
