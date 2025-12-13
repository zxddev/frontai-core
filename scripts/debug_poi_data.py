"""调试脚本：查看 POI 数据"""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 查看 POI 数据
        print("=== POI 数据 ===")
        result = await db.execute(text("""
            SELECT id::text, name, poi_type, 
                   ST_X(location::geometry) as lng, ST_Y(location::geometry) as lat,
                   scenario_id::text
            FROM operational_v2.poi_v2
            WHERE status != 'destroyed'
            ORDER BY name
            LIMIT 30
        """))
        
        # 统计不同区域的 POI
        poi_by_region = {}
        for row in result.fetchall():
            lng = row.lng
            if lng:
                if lng < 104:
                    region = "茂县附近 (103.x)"
                elif lng < 104.5:
                    region = "绵阳西部 (104.0-104.5)"
                else:
                    region = "绵阳东部 (104.5+)"
            else:
                region = "未知"
            
            if region not in poi_by_region:
                poi_by_region[region] = []
            poi_by_region[region].append({
                "name": row.name,
                "type": row.poi_type,
                "lng": lng,
                "lat": row.lat,
                "scenario_id": row.scenario_id
            })
        
        for region, pois in poi_by_region.items():
            print(f"\n{region}: {len(pois)} 个")
            for poi in pois[:5]:
                print(f"  - {poi['name']} ({poi['type']}): ({poi['lng']:.4f}, {poi['lat']:.4f})")
            if len(pois) > 5:
                print(f"  ... 还有 {len(pois) - 5} 个")
        
        # 查看事件位置
        print("\n=== 事件位置 ===")
        result = await db.execute(text("""
            SELECT id::text, title,
                   ST_X(location::geometry) as lng, ST_Y(location::geometry) as lat
            FROM operational_v2.events_v2
            LIMIT 5
        """))
        for row in result.fetchall():
            print(f"  {row.title[:50]}...: ({row.lng:.4f}, {row.lat:.4f})")


if __name__ == "__main__":
    asyncio.run(main())
