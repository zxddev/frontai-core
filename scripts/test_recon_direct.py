#!/usr/bin/env python3
"""
直接测试侦察规划 Agent（不通过 HTTP API）

用法: 
  python scripts/test_recon_direct.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 加载环境变量（必须在导入其他模块前）
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

# 设置路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))


async def main():
    # 延迟导入，避免模块冲突
    import asyncpg
    
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("错误: 未设置 POSTGRES_DSN 环境变量")
        return
    
    print("=" * 60)
    print("侦察规划 Agent 直接测试")
    print("=" * 60)
    print()
    
    # 获取想定信息
    conn = await asyncpg.connect(dsn)
    row = await conn.fetchrow("""
        SELECT id, name FROM operational_v2.scenarios_v2 
        WHERE status = 'active' LIMIT 1
    """)
    if not row:
        print("错误: 没有找到生效的想定")
        await conn.close()
        return
    
    scenario_id = str(row["id"])
    scenario_name = row["name"]
    print(f"想定: {scenario_name} ({scenario_id})")
    print()
    
    # 获取设备概况
    devices = await conn.fetch("""
        SELECT device_type, env_type, name, base_capabilities
        FROM operational_v2.devices_v2
        WHERE device_type IN ('drone', 'dog', 'ship')
        ORDER BY device_type, name
    """)
    print(f"数据库无人设备 ({len(devices)} 台):")
    for d in devices:
        caps = d.get("base_capabilities") or ["(无)"]
        print(f"  - {d['name']} ({d['device_type']}, {d['env_type']}) 能力: {caps}")
    print()
    
    await conn.close()
    
    # 导入并运行 Agent
    print("正在执行侦察规划...")
    print()
    
    # 使用 importlib 直接导入特定模块，避免触发 agents/__init__.py
    import importlib.util
    
    def import_module_from_path(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    
    # 导入 state
    state_module = import_module_from_path(
        "agents.reconnaissance.state",
        project_root / "src/agents/reconnaissance/state.py"
    )
    ReconState = state_module.ReconState
    
    # 导入 score_targets（需要先导入依赖）
    score_targets_module = import_module_from_path(
        "agents.reconnaissance.nodes.score_targets",
        project_root / "src/agents/reconnaissance/nodes/score_targets.py"
    )
    score_targets = score_targets_module.score_targets
    
    initial_state: ReconState = {
        "scenario_id": scenario_id,
        "event_id": None,
        "risk_areas": [],
        "devices": [],
        "candidate_targets": [],
        "scored_targets": [],
        "assignments": [],
        "explanation": "",
        "errors": [],
        "trace": {},
        "current_phase": "score_targets_pending",
    }
    
    try:
        result = await score_targets(initial_state)
    except Exception as e:
        print(f"执行失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 显示结果
    print("=" * 60)
    print("执行结果")
    print("=" * 60)
    print()
    
    # 显示设备信息
    devices = result.get("devices", [])
    print(f"【筛选后的侦察设备】共 {len(devices)} 台:")
    for d in devices:
        env_type = d.get("env_type", "未知")
        print(f"  ✓ {d.get('name')} ({d.get('device_type')}, 环境:{env_type})")
    print()
    
    # 显示目标信息
    targets = result.get("scored_targets", [])
    print(f"【侦察目标】共 {len(targets)} 个:")
    
    # 按环境类型分组显示
    land_targets = []
    sea_targets = []
    for t in targets:
        area_type = t.get("_area_type", "")
        if area_type in {"flooded", "poi_reservoir", "poi_dam", "poi_river", "poi_lake"}:
            sea_targets.append(t)
        else:
            land_targets.append(t)
    
    if land_targets:
        print(f"  陆地目标 ({len(land_targets)} 个):")
        for t in land_targets[:5]:
            print(f"    - [{t.get('priority')}] {t.get('name')} (分数:{t.get('score', 0):.2f})")
        if len(land_targets) > 5:
            print(f"    ... 还有 {len(land_targets) - 5} 个")
    
    if sea_targets:
        print(f"  水域目标 ({len(sea_targets)} 个):")
        for t in sea_targets[:5]:
            print(f"    - [{t.get('priority')}] {t.get('name')} (分数:{t.get('score', 0):.2f})")
        if len(sea_targets) > 5:
            print(f"    ... 还有 {len(sea_targets) - 5} 个")
    print()
    
    # 显示分配结果
    assignments = result.get("assignments", [])
    print(f"【设备分配】共 {len(assignments)} 条:")
    for a in assignments:
        device_name = a.get("device_name", "")
        device_type = a.get("device_type", "")
        target_name = a.get("target_name", "")
        reason = a.get("reason", "")
        print(f"  - {device_name} ({device_type}) -> {target_name}")
        print(f"    理由: {reason}")
    print()
    
    # 检查环境匹配
    print("【环境匹配检查】")
    mismatches = []
    for a in assignments:
        device_type = a.get("device_type", "")
        target_name = a.get("target_name", "")
        
        # 找到对应的目标
        target = next((t for t in targets if t.get("name") == target_name), None)
        if target:
            area_type = target.get("_area_type", "")
            is_water_target = area_type in {"flooded", "poi_reservoir", "poi_dam", "poi_river", "poi_lake"}
            
            # ship 只能去水域
            if device_type == "ship" and not is_water_target:
                mismatches.append(f"  ✗ 无人艇 '{a.get('device_name')}' 被分配到陆地目标 '{target_name}'")
            # dog 只能去陆地
            elif device_type == "dog":
                # 找设备信息
                device = next((d for d in devices if d.get("name") == a.get("device_name")), None)
                if device and device.get("env_type") == "land" and is_water_target:
                    mismatches.append(f"  ✗ 机器狗 '{a.get('device_name')}' 被分配到水域目标 '{target_name}'")
    
    if mismatches:
        print("发现环境不匹配的分配:")
        for m in mismatches:
            print(m)
    else:
        print("  ✓ 所有分配环境匹配正确")
    print()
    
    # 显示解释
    explanation = result.get("explanation", "")
    if explanation:
        print("【方案说明】")
        print(explanation[:1500])
        if len(explanation) > 1500:
            print("... (截断)")
    
    if result.get("errors"):
        print()
        print(f"【错误】{result.get('errors')}")
    
    print()
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
