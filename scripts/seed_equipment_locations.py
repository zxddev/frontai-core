#!/usr/bin/env python3
"""
设备位置数据补充脚本

将设备分配到救援车辆上，使装备调度器能够通过车辆位置定位设备。

设备分配策略：
- 无人机 (DV-DRONE-*) -> 多功能无人机输送车 (VH-003)
- 机器狗 (DV-DOG-*)   -> 前突侦察控制车 (VH-001)
- 无人艇 (DV-SHIP-*)  -> 多功能无人艇输送车 (VH-004)
- 医疗设备 (EQ-MED-*, EQ-DEFIBRILLATOR, EQ-IV-SET, EQ-VENTILATOR-PORT) -> 医疗救援车 (VH-005)
- 救援装备 (EQ-HYD-*, EQ-JACK, EQ-DETECTOR-*, EQ-CAMERA-*) -> 综合保障车 (VH-002)
- 其他设备 -> 综合保障车 (VH-002)

使用方法:
    python scripts/seed_equipment_locations.py
    python scripts/seed_equipment_locations.py --dry-run  # 仅预览，不执行
"""
import asyncio
import argparse
import sys
import os
from typing import Dict, List, Tuple
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# 设备编码前缀 -> 车辆编码 映射
DEVICE_VEHICLE_MAPPING: Dict[str, str] = {
    "DV-DRONE": "VH-003",      # 无人机 -> 无人机输送车
    "DV-DOG": "VH-001",        # 机器狗 -> 前突侦察控制车
    "DV-SHIP": "VH-004",       # 无人艇 -> 无人艇输送车
    "EQ-MED": "VH-005",        # 医疗设备 -> 医疗救援车
    "EQ-DEFIBRILLATOR": "VH-005",
    "EQ-IV-SET": "VH-005",
    "EQ-VENTILATOR": "VH-005",
    "EQ-TRIAGE": "VH-005",
    "EQ-HYD": "VH-002",        # 液压救援工具 -> 综合保障车
    "EQ-JACK": "VH-002",
    "EQ-DETECTOR": "VH-002",   # 生命探测仪 -> 综合保障车
    "EQ-CAMERA": "VH-002",
    "EQ-FLASHLIGHT": "VH-002",
    "EQ-SPEAKER": "VH-002",
    "EQ-CRANE": "VH-002",
    "EQ-EXCAVATOR": "VH-002",
    "EQ-LOADER": "VH-002",
    "EQ-TENT": "VH-002",
}

DEFAULT_VEHICLE = "VH-002"  # 默认分配到综合保障车


def get_vehicle_code_for_device(device_code: str) -> str:
    """根据设备编码确定分配的车辆"""
    for prefix, vehicle_code in DEVICE_VEHICLE_MAPPING.items():
        if device_code.startswith(prefix):
            return vehicle_code
    return DEFAULT_VEHICLE


async def seed_equipment_locations(dry_run: bool = False) -> Tuple[int, int]:
    """
    补充设备位置数据
    
    Args:
        dry_run: 仅预览，不执行更新
        
    Returns:
        (updated_count, skipped_count)
    """
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        # 1. 获取所有车辆ID映射
        logger.info("加载车辆数据...")
        result = await db.execute(text("""
            SELECT id, code, name FROM operational_v2.vehicles_v2
        """))
        vehicles: Dict[str, Tuple[UUID, str]] = {}
        for row in result.fetchall():
            vehicles[row[1]] = (row[0], row[2])
        
        logger.info(f"找到 {len(vehicles)} 辆车辆:")
        for code, (vid, name) in vehicles.items():
            logger.info(f"  {code}: {name}")
        
        # 2. 获取所有需要分配位置的设备
        logger.info("\n加载设备数据...")
        result = await db.execute(text("""
            SELECT d.id, d.code, d.name, d.in_vehicle_id,
                   e.longitude, e.latitude
            FROM operational_v2.devices_v2 d
            LEFT JOIN operational_v2.layer_entities_v2 e ON d.entity_id = e.id
            WHERE d.status = 'available'
            ORDER BY d.code
        """))
        
        devices_to_update: List[Tuple[UUID, str, str, str]] = []  # (id, code, name, vehicle_code)
        skipped = 0
        
        for row in result.fetchall():
            device_id, device_code, device_name = row[0], row[1], row[2]
            current_vehicle_id, lon, lat = row[3], row[4], row[5]
            
            # 已有位置或已分配车辆，跳过
            if current_vehicle_id is not None:
                logger.debug(f"  跳过 {device_code}: 已分配车辆")
                skipped += 1
                continue
            if lon is not None and lat is not None:
                logger.debug(f"  跳过 {device_code}: 已有位置 ({lon}, {lat})")
                skipped += 1
                continue
            
            # 确定分配的车辆
            vehicle_code = get_vehicle_code_for_device(device_code)
            if vehicle_code not in vehicles:
                logger.warning(f"  跳过 {device_code}: 目标车辆 {vehicle_code} 不存在")
                skipped += 1
                continue
            
            devices_to_update.append((device_id, device_code, device_name, vehicle_code))
        
        logger.info(f"\n需要更新: {len(devices_to_update)} 个设备，跳过: {skipped} 个")
        
        if not devices_to_update:
            logger.info("无需更新")
            return 0, skipped
        
        # 3. 预览更新
        logger.info("\n更新计划:")
        for device_id, device_code, device_name, vehicle_code in devices_to_update:
            vehicle_name = vehicles[vehicle_code][1]
            logger.info(f"  {device_code} ({device_name}) -> {vehicle_code} ({vehicle_name})")
        
        if dry_run:
            logger.info("\n[DRY RUN] 未执行实际更新")
            return 0, skipped
        
        # 4. 执行更新
        logger.info("\n执行更新...")
        updated = 0
        for device_id, device_code, device_name, vehicle_code in devices_to_update:
            vehicle_id = vehicles[vehicle_code][0]
            await db.execute(
                text("UPDATE operational_v2.devices_v2 SET in_vehicle_id = :vid WHERE id = :did"),
                {"vid": vehicle_id, "did": device_id}
            )
            updated += 1
        
        await db.commit()
        logger.info(f"成功更新 {updated} 个设备")
        
        return updated, skipped


async def verify_results() -> None:
    """验证更新结果"""
    from src.core.database import AsyncSessionLocal
    from sqlalchemy import text
    
    async with AsyncSessionLocal() as db:
        logger.info("\n=== 验证结果 ===")
        result = await db.execute(text("""
            SELECT d.code, d.name, v.code as vehicle_code, v.name as vehicle_name,
                   e.longitude, e.latitude
            FROM operational_v2.devices_v2 d
            LEFT JOIN operational_v2.vehicles_v2 v ON d.in_vehicle_id = v.id
            LEFT JOIN operational_v2.layer_entities_v2 e ON v.entity_id = e.id
            WHERE d.status = 'available'
            ORDER BY d.code
            LIMIT 15
        """))
        
        with_location = 0
        without_location = 0
        
        for row in result.fetchall():
            device_code, device_name = row[0], row[1]
            vehicle_code, vehicle_name = row[2], row[3]
            lon, lat = row[4], row[5]
            
            if lon is not None and lat is not None:
                logger.info(f"  ✓ {device_code} -> {vehicle_code} @ ({lon:.4f}, {lat:.4f})")
                with_location += 1
            elif vehicle_code:
                logger.warning(f"  ⚠ {device_code} -> {vehicle_code} (车辆无位置)")
                without_location += 1
            else:
                logger.error(f"  ✗ {device_code}: 未分配车辆")
                without_location += 1
        
        logger.info(f"\n有位置: {with_location}, 无位置: {without_location}")


def main():
    parser = argparse.ArgumentParser(description='设备位置数据补充脚本')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不执行更新')
    parser.add_argument('--verify', action='store_true', help='仅验证当前状态')
    args = parser.parse_args()
    
    if args.verify:
        asyncio.run(verify_results())
        return
    
    updated, skipped = asyncio.run(seed_equipment_locations(dry_run=args.dry_run))
    
    if not args.dry_run and updated > 0:
        asyncio.run(verify_results())


if __name__ == '__main__':
    main()
