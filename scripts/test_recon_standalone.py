#!/usr/bin/env python3
"""
独立测试侦察规划逻辑（不导入项目模块）

用法: 
  python scripts/test_recon_standalone.py
  
设置 RECON_SKIP_PLAN=true 可跳过方案生成（快速测试）
"""
import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

# 加载环境变量
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

import asyncpg

# ======== 从 score_targets.py 复制的核心逻辑 ========

RECON_CAPABILITIES = {
    "aerial_recon", "ground_recon", "water_recon", "3d_mapping",
    "video_stream", "thermal_imaging", "life_detection", "environment_analysis",
}

NON_RECON_CAPABILITIES = {
    "cargo_delivery", "cargo_transport", "medical_delivery",
    "water_rescue", "search_rescue", "communication_relay",
}

RECON_NAME_KEYWORDS = {"侦察", "热成像", "扫图", "建模", "分析"}
NON_RECON_NAME_KEYWORDS = {"投送", "搜救", "救援", "组网", "运输"}


def is_recon_device(device_data: Dict[str, Any]) -> bool:
    """基于 base_capabilities 判断设备是否适合侦察任务"""
    capabilities = set(device_data.get("base_capabilities") or [])
    name = device_data.get("name", "")
    
    if capabilities:
        has_recon = bool(capabilities & RECON_CAPABILITIES)
        only_non_recon = capabilities.issubset(NON_RECON_CAPABILITIES)
        
        if has_recon:
            return True
        if only_non_recon:
            return False
    
    # 回退：根据名称关键词判断
    if any(kw in name for kw in NON_RECON_NAME_KEYWORDS):
        return False
    if any(kw in name for kw in RECON_NAME_KEYWORDS):
        return True
    
    return False


def get_target_env_type(area_type: str) -> str:
    """根据目标类型推断其环境类型"""
    water_area_types = {
        "flooded", "poi_reservoir", "poi_dam", "poi_river", "poi_lake",
    }
    if area_type in water_area_types:
        return "sea"
    return "land"


def is_device_env_compatible(device_env: str, target_env: str) -> bool:
    """判断设备环境类型是否与目标兼容"""
    if device_env == "air":
        return True  # 无人机万能
    return device_env == target_env


AREA_TYPE_DEVICE_PREFERENCE = {
    "landslide": ["drone", "dog"],
    "flooded": ["drone", "ship"],
    "seismic_red": ["drone", "dog"],
    "seismic_orange": ["drone"],
    "contaminated": ["drone"],
    "blocked": ["drone", "dog"],
    "danger_zone": ["drone", "dog"],
    "damaged": ["drone"],
    "poi_hospital": ["drone", "dog"],
    "poi_school": ["drone", "dog"],
    "poi_reservoir": ["drone", "ship"],
}


def match_device_for_target(
    target: Dict[str, Any],
    available_devices: List[Dict[str, Any]],
) -> tuple:
    """为目标匹配最合适的设备"""
    if not available_devices:
        return None, ""
    
    area_type = target.get("area_type", "")
    target_env = get_target_env_type(area_type)
    
    # 过滤环境兼容的设备
    compatible_devices = [
        d for d in available_devices
        if is_device_env_compatible(d.get("env_type", "land"), target_env)
    ]
    
    if not compatible_devices:
        return None, f"无兼容设备 (目标环境: {target_env})"
    
    # 按推荐顺序查找
    preferred_types = AREA_TYPE_DEVICE_PREFERENCE.get(area_type, ["drone"])
    
    for device_type in preferred_types:
        for device in compatible_devices:
            if device.get("device_type") == device_type:
                return device, f"推荐用于 {area_type} 类型目标"
    
    # 回退
    return compatible_devices[0], "作为通用侦察力量"


# ======== 测试主逻辑 ========

async def main():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("错误: 未设置 POSTGRES_DSN 环境变量")
        return
    
    print("=" * 60)
    print("侦察规划逻辑测试")
    print("=" * 60)
    print()
    
    conn = await asyncpg.connect(dsn)
    
    try:
        # 获取想定
        row = await conn.fetchrow("""
            SELECT id, name FROM operational_v2.scenarios_v2 
            WHERE status = 'active' LIMIT 1
        """)
        if not row:
            print("错误: 没有找到生效的想定")
            return
        
        scenario_id = str(row["id"])
        scenario_name = row["name"]
        print(f"想定: {scenario_name}")
        print()
        
        # 获取所有无人设备
        devices = await conn.fetch("""
            SELECT id, code, name, device_type, env_type, base_capabilities
            FROM operational_v2.devices_v2
            WHERE device_type IN ('drone', 'dog', 'ship')
              AND status = 'available'
            ORDER BY device_type, name
        """)
        
        all_devices = []
        recon_devices = []
        
        for d in devices:
            device_data = {
                "id": str(d["id"]),
                "code": d["code"],
                "name": d["name"],
                "device_type": d["device_type"],
                "env_type": d["env_type"],
                "base_capabilities": d["base_capabilities"] or [],
            }
            all_devices.append(device_data)
            
            if is_recon_device(device_data):
                recon_devices.append(device_data)
        
        print(f"【设备筛选】")
        print(f"  总设备: {len(all_devices)} 台")
        print(f"  侦察设备: {len(recon_devices)} 台")
        print()
        
        print("侦察设备列表:")
        for d in recon_devices:
            caps = d["base_capabilities"] or ["(无标签)"]
            print(f"  ✓ {d['name']} ({d['device_type']}, {d['env_type']}) 能力: {caps}")
        print()
        
        print("排除的设备:")
        excluded = [d for d in all_devices if d not in recon_devices]
        for d in excluded:
            caps = d["base_capabilities"] or ["(无标签)"]
            print(f"  ✗ {d['name']} ({d['device_type']}, {d['env_type']}) 能力: {caps}")
        print()
        
        # 获取风险区域作为侦察目标
        targets = await conn.fetch("""
            SELECT id, name, area_type, risk_level, passage_status
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
              AND (reconnaissance_required = true OR risk_level >= 5)
            ORDER BY risk_level DESC
            LIMIT 15
        """, UUID(scenario_id))
        
        target_list = []
        for t in targets:
            target_list.append({
                "id": str(t["id"]),
                "name": t["name"],
                "area_type": t["area_type"],
                "risk_level": t["risk_level"],
                "env_type": get_target_env_type(t["area_type"]),
            })
        
        print(f"【侦察目标】共 {len(target_list)} 个")
        
        # 按环境分组
        land_targets = [t for t in target_list if t["env_type"] == "land"]
        sea_targets = [t for t in target_list if t["env_type"] == "sea"]
        
        if land_targets:
            print(f"  陆地目标 ({len(land_targets)} 个):")
            for t in land_targets[:5]:
                print(f"    - {t['name']} ({t['area_type']}, 风险:{t['risk_level']})")
        
        if sea_targets:
            print(f"  水域目标 ({len(sea_targets)} 个):")
            for t in sea_targets[:5]:
                print(f"    - {t['name']} ({t['area_type']}, 风险:{t['risk_level']})")
        print()
        
        # 执行设备分配
        print("【设备分配】")
        assignments = []
        used_device_ids = set()
        
        for target in target_list:
            available = [d for d in recon_devices if d["id"] not in used_device_ids]
            device, reason = match_device_for_target(target, available)
            
            if device:
                used_device_ids.add(device["id"])
                assignments.append({
                    "device": device,
                    "target": target,
                    "reason": reason,
                })
        
        print(f"成功分配 {len(assignments)} 条:")
        for a in assignments:
            device = a["device"]
            target = a["target"]
            target_env = target["env_type"]
            device_env = device["env_type"]
            
            # 检查环境匹配
            match_ok = is_device_env_compatible(device_env, target_env)
            status = "✓" if match_ok else "✗ 环境不匹配!"
            
            print(f"  {status} {device['name']} ({device_env}) -> {target['name']} ({target_env})")
            print(f"      理由: {a['reason']}")
        
        # 未分配的目标
        assigned_target_ids = {a["target"]["id"] for a in assignments}
        unassigned = [t for t in target_list if t["id"] not in assigned_target_ids]
        if unassigned:
            print()
            print(f"未分配设备的目标 ({len(unassigned)} 个):")
            for t in unassigned[:5]:
                print(f"    - {t['name']} ({t['env_type']})")
        
        print()
        print("=" * 60)
        print("测试完成!")
        print("=" * 60)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
