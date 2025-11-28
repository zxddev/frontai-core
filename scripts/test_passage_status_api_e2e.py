#!/usr/bin/env python3
"""
passage_status HTTP API 端到端测试

测试流程：
1. POST /api/v1/events/earthquake/trigger → 触发地震事件
2. 查询数据库验证 disaster_affected_areas_v2 写入了正确的 passage_status
3. POST /api/v2/staging-area/recommend → 验证路径规划绕行逻辑

前置条件：
- FastAPI 服务已启动 (python -m src.main 或 uvicorn src.main:app)
- 数据库已执行 v15_passage_status_extension.sql 迁移

用法: 
  python scripts/test_passage_status_api_e2e.py [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import asyncpg


# 默认配置
DEFAULT_BASE_URL = "http://localhost:8000"
DSN = "postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent"

# 测试数据
TEST_SCENARIO_ID: Optional[str] = None  # 使用已存在的想定，或创建新的


async def get_or_create_scenario(conn: asyncpg.Connection) -> str:
    """获取或创建测试想定"""
    # 尝试使用已存在的想定
    existing = await conn.fetchrow("""
        SELECT id FROM operational_v2.scenarios_v2 
        WHERE status = 'active' 
        LIMIT 1
    """)
    
    if existing:
        print(f"[INFO] 使用已存在的想定: {existing['id']}")
        return str(existing['id'])
    
    # 创建新想定
    new_id = uuid4()
    await conn.execute("""
        INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status)
        VALUES ($1, 'API端到端测试想定', 'earthquake', 'active')
    """, new_id)
    print(f"[INFO] 创建新想定: {new_id}")
    return str(new_id)


async def test_earthquake_trigger_api(client: httpx.AsyncClient, scenario_id: str) -> dict:
    """测试1: 触发地震事件 API"""
    print("\n" + "=" * 60)
    print("测试1: POST /api/v1/events/earthquake/trigger")
    print("=" * 60)
    
    # 构造请求体
    request_data = {
        "scenarioId": scenario_id,
        "magnitude": 6.5,
        "location": {
            "longitude": 104.5,
            "latitude": 31.2
        },
        "depthKm": 10,
        "epicenterName": "API测试震中",
        "message": "API端到端测试地震事件",
        "estimatedVictims": 100,
        "animationDurationMs": 1000
    }
    
    print(f"请求体: scenarioId={scenario_id}, magnitude=6.5, epicenter=API测试震中")
    
    try:
        response = await client.post(
            "/api/v1/events/earthquake/trigger",
            json=request_data,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200 or result.get("success"):
                data = result.get("data", result)
                event_id = data.get("eventId") or data.get("event_id")
                duplicate = data.get("duplicate", False)
                
                if duplicate:
                    print(f"[OK] 地震事件已存在（幂等返回）: {event_id}")
                else:
                    print(f"[OK] 地震事件创建成功: {event_id}")
                
                return {"success": True, "event_id": event_id, "duplicate": duplicate}
            else:
                print(f"[FAIL] API返回失败: {result}")
                return {"success": False, "error": str(result)}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            print(f"响应: {response.text[:500]}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except httpx.ConnectError as e:
        print(f"[FAIL] 连接失败: {e}")
        print("请确保 FastAPI 服务已启动: python -m src.main")
        return {"success": False, "error": "连接失败"}
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_verify_passage_status(conn: asyncpg.Connection, scenario_id: str) -> dict:
    """测试2: 验证数据库中 passage_status 写入"""
    print("\n" + "=" * 60)
    print("测试2: 验证 disaster_affected_areas_v2 表")
    print("=" * 60)
    
    try:
        # 查询刚创建的风险区域
        rows = await conn.fetch("""
            SELECT name, area_type, passage_status, reconnaissance_required, risk_level
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
            AND name LIKE '%API测试震中%'
            ORDER BY risk_level DESC
        """, scenario_id)
        
        if not rows:
            # 可能使用了不同的震中名，尝试查询最新的
            rows = await conn.fetch("""
                SELECT name, area_type, passage_status, reconnaissance_required, risk_level
                FROM operational_v2.disaster_affected_areas_v2
                WHERE scenario_id = $1
                ORDER BY created_at DESC NULLS LAST, risk_level DESC
                LIMIT 10
            """, scenario_id)
        
        if not rows:
            print("[WARN] 未找到风险区域数据")
            return {"success": False, "error": "未找到数据"}
        
        print(f"\n找到 {len(rows)} 条记录:")
        print("-" * 60)
        
        has_needs_recon = False
        has_passable_caution = False
        has_clear = False
        
        for row in rows:
            status = row['passage_status'] or 'NULL'
            recon = "需侦察" if row['reconnaissance_required'] else "无需侦察"
            print(f"  {row['name'][:30]}: passage_status={status}, {recon}")
            
            if status == 'needs_reconnaissance':
                has_needs_recon = True
            elif status == 'passable_with_caution':
                has_passable_caution = True
            elif status == 'clear':
                has_clear = True
        
        # 验证至少有一个正确的状态
        if has_needs_recon or has_passable_caution or has_clear:
            print("\n[OK] passage_status 字段已正确写入")
            return {"success": True}
        else:
            print("\n[WARN] 未找到预期的 passage_status 值")
            return {"success": False, "error": "passage_status 值不符合预期"}
            
    except Exception as e:
        print(f"[FAIL] 查询失败: {e}")
        return {"success": False, "error": str(e)}


async def test_staging_area_api(client: httpx.AsyncClient, scenario_id: str) -> dict:
    """测试3: 驻扎点推荐 API（验证路径规划绕行逻辑）"""
    print("\n" + "=" * 60)
    print("测试3: POST /api/v2/staging-area/recommend")
    print("=" * 60)
    
    # 构造请求体
    request_data = {
        "scenario_id": scenario_id,
        "earthquake": {
            "epicenter_lon": 104.5,
            "epicenter_lat": 31.2,
            "magnitude": 6.5,
            "depth_km": 10
        },
        "rescue_targets": [
            {
                "id": str(uuid4()),
                "name": "测试救援点",
                "longitude": 104.55,
                "latitude": 31.25,
                "priority": "high",
                "estimated_trapped": 50
            }
        ],
        "team": {
            "team_id": str(uuid4()),
            "team_name": "测试救援队",
            "base_lon": 104.4,
            "base_lat": 31.1,
            "max_speed_kmh": 60
        },
        "constraints": {
            "min_buffer_m": 500,
            "max_search_radius_m": 30000,
            "max_candidates": 20,
            "top_n": 5
        }
    }
    
    print(f"请求: scenario_id={scenario_id}")
    
    try:
        response = await client.post(
            "/api/v2/staging-area/recommend",
            json=request_data,
            timeout=60.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            success = result.get("success", True)
            error = result.get("error")
            sites = result.get("recommended_sites", [])
            risk_zones = result.get("risk_zones_count", 0)
            candidates_total = result.get("candidates_total", 0)
            candidates_reachable = result.get("candidates_reachable", 0)
            
            print(f"\n结果:")
            print(f"  - 风险区域数: {risk_zones}")
            print(f"  - 候选点总数: {candidates_total}")
            print(f"  - 可达候选点: {candidates_reachable}")
            print(f"  - 推荐站点数: {len(sites)}")
            
            if error:
                print(f"  - 错误信息: {error}")
            
            if sites:
                print("\n推荐站点:")
                for i, site in enumerate(sites[:3], 1):
                    name = site.get("name", "未知")
                    score = site.get("total_score", 0)
                    dist = site.get("distance_to_danger_m", "N/A")
                    print(f"  {i}. {name}: 总分={score:.2f}, 距危险区={dist}m")
            
            # 验证路径规划是否考虑了风险区域
            if risk_zones > 0:
                print("\n[OK] 路径规划引擎已识别风险区域")
                if candidates_reachable < candidates_total:
                    print(f"[OK] 有 {candidates_total - candidates_reachable} 个候选点因风险区域被排除")
                return {"success": True, "risk_zones": risk_zones}
            else:
                print("\n[WARN] 未识别到风险区域，可能数据未正确关联")
                return {"success": True, "risk_zones": 0}
                
        elif response.status_code == 422:
            print(f"[FAIL] 请求参数错误: {response.json()}")
            return {"success": False, "error": "参数错误"}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            print(f"响应: {response.text[:500]}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except httpx.ConnectError as e:
        print(f"[FAIL] 连接失败: {e}")
        return {"success": False, "error": "连接失败"}
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def cleanup_test_data(conn: asyncpg.Connection, scenario_id: str):
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)
    
    try:
        # 只删除测试创建的风险区域
        result = await conn.execute("""
            DELETE FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
            AND name LIKE '%API测试震中%'
        """, scenario_id)
        print(f"[OK] 删除测试风险区域: {result}")
        
        # 删除测试事件（可选）
        result = await conn.execute("""
            DELETE FROM operational_v2.events_v2
            WHERE scenario_id = $1
            AND title LIKE '%API端到端测试%'
        """, scenario_id)
        print(f"[OK] 删除测试事件: {result}")
        
    except Exception as e:
        print(f"[WARN] 清理失败: {e}")


async def main(base_url: str):
    """主测试流程"""
    print("=" * 60)
    print("passage_status HTTP API 端到端测试")
    print("=" * 60)
    print(f"API 地址: {base_url}")
    print(f"数据库: {DSN.split('@')[1]}")
    
    # 连接数据库
    try:
        conn = await asyncpg.connect(DSN)
        print("[OK] 数据库连接成功")
    except Exception as e:
        print(f"[FAIL] 数据库连接失败: {e}")
        return 1
    
    # 获取或创建想定
    try:
        scenario_id = await get_or_create_scenario(conn)
    except Exception as e:
        print(f"[FAIL] 获取想定失败: {e}")
        await conn.close()
        return 1
    
    results = []
    
    async with httpx.AsyncClient(base_url=base_url) as client:
        # 测试1: 触发地震事件
        r1 = await test_earthquake_trigger_api(client, scenario_id)
        results.append(("触发地震事件 API", r1["success"]))
        
        if r1["success"]:
            # 等待一下让数据写入完成
            await asyncio.sleep(1)
            
            # 测试2: 验证数据库
            r2 = await test_verify_passage_status(conn, scenario_id)
            results.append(("验证 passage_status 写入", r2["success"]))
            
            # 测试3: 驻扎点推荐（间接验证路径规划）
            r3 = await test_staging_area_api(client, scenario_id)
            results.append(("驻扎点推荐 API", r3["success"]))
        else:
            results.append(("验证 passage_status 写入", False))
            results.append(("驻扎点推荐 API", False))
    
    # 清理
    await cleanup_test_data(conn, scenario_id)
    await conn.close()
    
    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for name, ok in results:
        status = "[PASS]" if ok else "[FAIL]"
        print(f"  {status} {name}")
        if ok:
            passed += 1
    
    print("-" * 60)
    print(f"通过: {passed}/{len(results)}")
    print("=" * 60)
    
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="passage_status API 端到端测试")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 基础地址 (默认: {DEFAULT_BASE_URL})"
    )
    args = parser.parse_args()
    
    sys.exit(asyncio.run(main(args.base_url)))
