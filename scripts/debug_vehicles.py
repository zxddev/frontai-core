"""调试脚本：查看车辆和设备数据"""
import asyncio
import json
from sqlalchemy import text
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')
from src.core.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        # 查看车辆数据
        print('=== 车辆数据 ===')
        result = await db.execute(text("""
            SELECT 
                id::text, name, vehicle_type,
                ST_X(current_location::geometry) as lng,
                ST_Y(current_location::geometry) as lat
            FROM operational_v2.vehicles_v2
            LIMIT 10
        """))
        for row in result.fetchall():
            print(f"  {row.name} ({row.vehicle_type}): ({row.lng}, {row.lat})")
        
        # 查看设备数据
        print('\n=== 设备数据 ===')
        result = await db.execute(text("""
            SELECT 
                d.id::text as device_id,
                d.name as device_name,
                d.device_type,
                d.in_vehicle_id::text,
                v.name as vehicle_name
            FROM operational_v2.devices_v2 d
            LEFT JOIN operational_v2.vehicles_v2 v ON d.in_vehicle_id = v.id
            WHERE d.device_type IN ('drone', 'dog')
            LIMIT 20
        """))
        for row in result.fetchall():
            print(f"  {row.device_name} ({row.device_type}): 在车辆 {row.vehicle_name}")
        
        # 查看指挥车
        print('\n=== 指挥车 ===')
        result = await db.execute(text("""
            SELECT 
                id::text, name, vehicle_type,
                ST_X(current_location::geometry) as lng,
                ST_Y(current_location::geometry) as lat
            FROM operational_v2.vehicles_v2
            WHERE vehicle_type LIKE '%指挥%' OR name LIKE '%指挥%'
        """))
        for row in result.fetchall():
            print(f"  {row.name} ({row.vehicle_type}): ({row.lng}, {row.lat})")


if __name__ == "__main__":
    asyncio.run(main())
