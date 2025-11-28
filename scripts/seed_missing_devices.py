#!/usr/bin/env python3
"""
补充缺失的设备数据脚本

将capability_equipment_v2中引用但devices_v2中不存在的设备添加到数据库。
设备将分配到合适的车辆上以获得位置信息。

使用方法:
    python scripts/seed_missing_devices.py
    python scripts/seed_missing_devices.py --dry-run  # 仅预览
"""
import asyncio
import argparse
import sys
import os
from typing import Dict, List, Tuple
from uuid import UUID, uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# device_type_v2枚举值: drone, dog, ship, robot
# env_type枚举值: air, ground, sea, land
# 将新设备映射到现有枚举类型

# 缺失设备的定义：(code, name, device_type, env_type, applicable_disasters, vehicle_code)
MISSING_DEVICES: List[Tuple[str, str, str, str, List[str], str]] = [
    # 消防设备 -> 综合保障车 (robot类型包含各种机械设备)
    ("EQ-PUMP", "消防水泵", "robot", "ground", ["fire", "flood"], "VH-002"),
    
    # 工程救援设备 -> 综合保障车
    ("EQ-CRANE-MINI", "小型起重机", "robot", "ground", ["earthquake", "collapse"], "VH-002"),
    
    # 生命探测设备 -> 前突侦察控制车
    ("EQ-DOG-SEARCH", "搜救犬", "dog", "land", ["earthquake", "collapse", "avalanche"], "VH-001"),
    ("EQ-DETECTOR-GAS", "气体检测仪", "robot", "ground", ["hazmat", "fire"], "VH-001"),
    ("EQ-MONITOR-VITAL", "生命体征监护仪", "robot", "ground", ["earthquake", "flood", "fire"], "VH-005"),
    
    # 无人机设备 -> 无人机输送车
    ("EQ-UAV-SURVEY", "侦察无人机", "drone", "air", ["earthquake", "flood", "fire", "hazmat"], "VH-003"),
    ("EQ-UAV-THERMAL", "热成像无人机", "drone", "air", ["earthquake", "fire", "flood"], "VH-003"),
    
    # 水上救援设备 -> 无人艇输送车
    ("EQ-BOAT-INFLATABLE", "冲锋舟", "ship", "sea", ["flood", "water_rescue"], "VH-004"),
    ("EQ-USV", "无人救援艇", "ship", "sea", ["flood", "water_rescue"], "VH-004"),
    
    # 危化品处置设备 -> 综合保障车
    ("EQ-PUMP-CHEM", "防爆泵", "robot", "ground", ["hazmat"], "VH-002"),
    
    # 通信设备 -> 前突侦察控制车
    ("EQ-RADIO", "对讲机", "robot", "ground", ["earthquake", "flood", "fire", "hazmat"], "VH-001"),
    ("EQ-SATELLITE", "卫星电话", "robot", "ground", ["earthquake", "flood", "fire", "hazmat"], "VH-001"),
    ("EQ-REPEATER", "中继台", "robot", "ground", ["earthquake", "flood", "fire", "hazmat"], "VH-001"),
    
    # 照明设备 -> 综合保障车
    ("EQ-LIGHT-TOWER", "移动照明灯塔", "robot", "ground", ["earthquake", "flood", "fire"], "VH-002"),
    ("EQ-GENERATOR", "发电机", "robot", "ground", ["earthquake", "flood", "fire", "hazmat"], "VH-002"),
]


async def seed_missing_devices(dry_run: bool = False) -> Tuple[int, int]:
    """
    补充缺失的设备数据
    
    Returns:
        (inserted_count, skipped_count)
    """
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        # 1. 获取车辆ID映射
        logger.info("加载车辆数据...")
        result = await db.execute(text("SELECT id, code, name FROM operational_v2.vehicles_v2"))
        vehicles: Dict[str, Tuple[UUID, str]] = {}
        for row in result.fetchall():
            vehicles[row[1]] = (row[0], row[2])
        logger.info(f"找到 {len(vehicles)} 辆车辆")
        
        # 2. 获取已存在的设备编码
        result = await db.execute(text("SELECT code FROM operational_v2.devices_v2"))
        existing_codes = {row[0] for row in result.fetchall()}
        logger.info(f"现有 {len(existing_codes)} 个设备")
        
        # 3. 筛选需要添加的设备
        devices_to_insert: List[Tuple] = []
        skipped = 0
        
        for code, name, device_type, env_type, disasters, vehicle_code in MISSING_DEVICES:
            if code in existing_codes:
                logger.debug(f"跳过 {code}: 已存在")
                skipped += 1
                continue
            
            if vehicle_code not in vehicles:
                logger.warning(f"跳过 {code}: 车辆 {vehicle_code} 不存在")
                skipped += 1
                continue
            
            vehicle_id = vehicles[vehicle_code][0]
            devices_to_insert.append((code, name, device_type, env_type, disasters, vehicle_id, vehicle_code))
        
        logger.info(f"\n需要添加: {len(devices_to_insert)} 个设备，跳过: {skipped} 个")
        
        if not devices_to_insert:
            logger.info("无需添加")
            return 0, skipped
        
        # 4. 预览
        logger.info("\n添加计划:")
        for code, name, device_type, env_type, disasters, vehicle_id, vehicle_code in devices_to_insert:
            logger.info(f"  {code}: {name} ({device_type}/{env_type}) -> {vehicle_code}")
        
        if dry_run:
            logger.info("\n[DRY RUN] 未执行实际添加")
            return 0, skipped
        
        # 5. 执行插入
        logger.info("\n执行添加...")
        inserted = 0
        
        for code, name, device_type, env_type, disasters, vehicle_id, vehicle_code in devices_to_insert:
            device_id = uuid4()
            await db.execute(
                text("""
                    INSERT INTO operational_v2.devices_v2 
                    (id, code, name, device_type, env_type, weight_kg, volume_m3, module_slots, 
                     status, in_vehicle_id, applicable_disasters, properties, created_at, updated_at)
                    VALUES (:id, :code, :name, :device_type, :env_type, :weight_kg, :volume_m3, 0,
                            'available', :vehicle_id, :disasters, '{}'::jsonb, NOW(), NOW())
                """),
                {
                    "id": device_id,
                    "code": code,
                    "name": name,
                    "device_type": device_type,
                    "env_type": env_type,
                    "weight_kg": 10.0,  # 默认10kg
                    "volume_m3": 0.05,  # 默认0.05立方米
                    "vehicle_id": vehicle_id,
                    "disasters": disasters,
                }
            )
            inserted += 1
            logger.info(f"  ✓ 添加 {code}: {name}")
        
        await db.commit()
        logger.info(f"\n成功添加 {inserted} 个设备")
        
        return inserted, skipped


async def verify_coverage() -> None:
    """验证设备覆盖率"""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        logger.info("\n=== 验证设备覆盖率 ===")
        
        # capability_equipment中device类型的编码
        result = await db.execute(
            text("SELECT DISTINCT equipment_code FROM operational_v2.capability_equipment_v2 WHERE equipment_type = :t"),
            {"t": "device"}
        )
        required_codes = {row[0] for row in result.fetchall()}
        
        # devices_v2中的编码
        result = await db.execute(text("SELECT code FROM operational_v2.devices_v2"))
        existing_codes = {row[0] for row in result.fetchall()}
        
        covered = required_codes & existing_codes
        missing = required_codes - existing_codes
        
        logger.info(f"需要的设备: {len(required_codes)}")
        logger.info(f"已有的设备: {len(covered)}")
        logger.info(f"覆盖率: {len(covered)/len(required_codes)*100:.1f}%")
        
        if missing:
            logger.warning(f"仍缺失: {sorted(missing)}")
        else:
            logger.info("✓ 所有设备已覆盖")


def main():
    parser = argparse.ArgumentParser(description='补充缺失的设备数据')
    parser.add_argument('--dry-run', action='store_true', help='仅预览')
    parser.add_argument('--verify', action='store_true', help='仅验证覆盖率')
    args = parser.parse_args()
    
    if args.verify:
        asyncio.run(verify_coverage())
        return
    
    inserted, skipped = asyncio.run(seed_missing_devices(dry_run=args.dry_run))
    
    if not args.dry_run:
        asyncio.run(verify_coverage())


if __name__ == '__main__':
    main()
