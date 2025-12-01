#!/usr/bin/env python3
"""
侦察规划 API 端到端测试

测试 /api/v2/frontend/recon-plan/initial-scan 接口

前置条件：
- FastAPI 服务已启动 (python -m src.main)
- 数据库有生效的想定和风险区域数据

用法: 
  python scripts/test_recon_api.py [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import asyncpg


DEFAULT_BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"  # 前端 API 前缀
DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:password@localhost:5432/emergency_agent")


async def get_active_scenario(conn: asyncpg.Connection) -> dict:
    """获取当前生效的想定"""
    row = await conn.fetchrow("""
        SELECT id, name FROM operational_v2.scenarios_v2 
        WHERE status = 'active' 
        LIMIT 1
    """)
    if not row:
        return None
    return {"id": str(row["id"]), "name": row["name"]}


async def get_devices_summary(conn: asyncpg.Connection) -> dict:
    """获取设备概况"""
    rows = await conn.fetch("""
        SELECT device_type, env_type, name, base_capabilities
        FROM operational_v2.devices_v2
        WHERE device_type IN ('drone', 'dog', 'ship')
        ORDER BY device_type, name
    """)
    return [dict(r) for r in rows]


async def test_recon_api(base_url: str):
    """测试侦察规划 API"""
    print("=" * 60)
    print("侦察规划 API 测试")
    print("=" * 60)
    print()
    
    # 连接数据库获取测试数据
    conn = await asyncpg.connect(DSN)
    
    try:
        # 1. 获取想定信息
        scenario = await get_active_scenario(conn)
        if not scenario:
            print("错误: 没有找到生效的想定")
            return False
        
        print(f"想定: {scenario['name']} ({scenario['id']})")
        print()
        
        # 2. 获取设备概况
        devices = await get_devices_summary(conn)
        print(f"数据库中的无人设备 ({len(devices)} 台):")
        for d in devices:
            caps = d.get("base_capabilities") or ["(无)"]
            print(f"  - {d['name']} ({d['device_type']}, {d['env_type']}) 能力: {caps}")
        print()
        
    finally:
        await conn.close()
    
    # 3. 调用 API
    api_url = f"{base_url}{API_PREFIX}/recon-plan/initial-scan"
    print(f"调用 API: POST {api_url}")
    print()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                api_url,
                json={"scenarioId": scenario["id"]},
            )
        except httpx.RequestError as e:
            print(f"请求失败: {e}")
            print("请确保 FastAPI 服务已启动: python -m src.main")
            return False
    
    print(f"响应状态: {response.status_code}")
    
    if response.status_code != 200:
        print(f"错误响应: {response.text}")
        return False
    
    data = response.json()
    
    if data.get("code") != 0:
        print(f"API 返回错误: {data.get('message')}")
        print(f"错误详情: {data.get('data')}")
        return False
    
    result = data.get("data", {})
    
    # 4. 显示结果
    print()
    print("=" * 60)
    print("API 返回结果")
    print("=" * 60)
    print()
    
    # 显示设备信息
    devices = result.get("devices", [])
    print(f"【筛选后的侦察设备】共 {len(devices)} 台:")
    for d in devices:
        env_type = d.get("env_type", d.get("envType", "未知"))
        print(f"  ✓ {d.get('name')} ({d.get('device_type', d.get('deviceType'))}, 环境:{env_type})")
    print()
    
    # 显示目标信息
    targets = result.get("targets", [])
    print(f"【侦察目标】共 {len(targets)} 个:")
    for t in targets[:10]:
        priority = t.get("priority", "medium")
        score = t.get("score", 0)
        print(f"  - [{priority}] {t.get('name')} (分数:{score:.2f})")
    if len(targets) > 10:
        print(f"  ... 还有 {len(targets) - 10} 个目标")
    print()
    
    # 显示分配结果
    assignments = result.get("assignments", [])
    print(f"【设备分配】共 {len(assignments)} 条:")
    for a in assignments:
        device_name = a.get("deviceName", a.get("device_name", ""))
        target_name = a.get("targetName", a.get("target_name", ""))
        reason = a.get("reason", "")
        print(f"  - {device_name} -> {target_name}")
        print(f"    理由: {reason}")
    print()
    
    # 显示解释
    explanation = result.get("explanation", "")
    if explanation:
        print("【方案说明】")
        print(explanation[:1200])
        if len(explanation) > 1200:
            print("... (截断)")
    
    print()
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)
    
    return True


def main():
    parser = argparse.ArgumentParser(description="侦察规划 API 测试")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 基础地址 (默认: {DEFAULT_BASE_URL})",
    )
    args = parser.parse_args()
    
    success = asyncio.run(test_recon_api(args.base_url))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
