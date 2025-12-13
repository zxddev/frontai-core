"""调试 score_targets 函数"""
import asyncio
import sys
sys.path.insert(0, '/home/dev/gitcode/frontai/frontai-core')

from src.agents.reconnaissance.nodes.score_targets import score_targets


async def main():
    # 模拟 ReconState
    state = {
        "scenario_id": "182c4b66-f368-4763-84a1-84b44c2439d9",
        "event_id": "411196cf-f923-48c2-b19c-00ab770553a6",
    }
    
    print("=== 调试 score_targets ===")
    print(f"scenario_id: {state['scenario_id']}")
    print(f"event_id: {state['event_id']}")
    print()
    
    result = await score_targets(state)
    
    print(f"=== 结果 ===")
    print(f"current_phase: {result.get('current_phase')}")
    print(f"风险区域数量: {len(result.get('risk_areas', []))}")
    print(f"POI数量: {len(result.get('pois', []))}")
    print(f"救援集结点数量: {len(result.get('staging_sites', []))}")
    print(f"设备数量: {len(result.get('devices', []))}")
    print(f"目标数量: {len(result.get('scored_targets', []))}")
    print(f"设备分配数量: {len(result.get('assignments', []))}")
    print()
    
    # 显示目标详情
    targets = result.get('scored_targets', [])
    print(f"=== 目标详情 (前10个) ===")
    for i, t in enumerate(targets[:10]):
        print(f"{i+1}. {t.get('name')} (type={t.get('_target_type')}, priority={t.get('priority')}, score={t.get('score'):.2f})")
    
    # 显示设备分配详情
    assignments = result.get('assignments', [])
    print(f"\n=== 设备分配详情 ===")
    if not assignments:
        print("没有设备分配！")
    for a in assignments:
        print(f"- {a.get('device_name')} ({a.get('device_type')}) -> {a.get('target_name')}")
    
    # 显示设备详情
    devices = result.get('devices', [])
    print(f"\n=== 侦察设备详情 (前10个) ===")
    for i, d in enumerate(devices[:10]):
        print(f"{i+1}. {d.get('name')} (type={d.get('device_type')}, env={d.get('env_type')})")


if __name__ == "__main__":
    asyncio.run(main())
