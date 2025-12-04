#!/usr/bin/env python3
"""
路径规划接口 端到端测试

测试接口：
1. POST /routing/plan-and-save - 规划并存储路径
2. POST /routing/alternative-routes - 生成绕行方案
3. POST /routing/confirm-route-by-id - 按ID确认路径
4. GET /routing/routes/{task_id} - 查询任务路径
5. GET /routing/routes/{task_id}/active - 获取任务活跃路径

前置条件：
- FastAPI 服务已启动 (python -m src.main)
- 数据库中有设备和任务数据

用法:
  python scripts/test_routing_api_e2e.py [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import asyncpg


# 默认配置
DEFAULT_BASE_URL = "http://localhost:8000/api/v2"
# asyncpg 需要 postgresql:// 格式（不是 postgresql+asyncpg://）
DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent")

# 测试坐标（茂县地区）
ORIGIN = {"lon": 103.8537, "lat": 31.6815}
DESTINATION = {"lon": 103.8720, "lat": 31.6580}

# 测试结果统计
test_results = {"passed": 0, "failed": 0, "skipped": 0}


def log_ok(msg: str):
    print(f"  [OK] {msg}")
    test_results["passed"] += 1


def log_fail(msg: str):
    print(f"  [FAIL] {msg}")
    test_results["failed"] += 1


def log_skip(msg: str):
    print(f"  [SKIP] {msg}")
    test_results["skipped"] += 1


def log_info(msg: str):
    print(f"  [INFO] {msg}")


# ============================================================================
# 数据准备
# ============================================================================

async def get_or_create_scenario(conn: asyncpg.Connection) -> Optional[str]:
    """获取或创建测试想定"""
    existing = await conn.fetchrow("""
        SELECT id FROM operational_v2.scenarios_v2
        WHERE status = 'active'
        LIMIT 1
    """)
    
    if existing:
        return str(existing['id'])
    
    new_id = uuid4()
    await conn.execute("""
        INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status)
        VALUES ($1, '路径规划E2E测试想定', 'earthquake', 'active')
    """, new_id)
    return str(new_id)


async def get_test_device(conn: asyncpg.Connection, env_type: str = "land") -> Optional[Dict[str, Any]]:
    """获取测试设备（排除 equipment 类型，因为 ORM 枚举不支持）"""
    row = await conn.fetchrow("""
        SELECT id, name, env_type, device_type
        FROM operational_v2.devices_v2
        WHERE env_type = $1 AND device_type IN ('drone', 'dog', 'ship', 'robot')
        LIMIT 1
    """, env_type)
    
    if row:
        return {"id": str(row['id']), "name": row['name'], "env_type": row['env_type']}
    return None


async def get_or_create_task(conn: asyncpg.Connection, scenario_id: str) -> Optional[str]:
    """获取或创建测试任务"""
    existing = await conn.fetchrow("""
        SELECT id FROM operational_v2.task_requirements_v2
        WHERE scenario_id = $1
        LIMIT 1
    """, UUID(scenario_id))
    
    if existing:
        return str(existing['id'])
    
    new_id = uuid4()
    await conn.execute("""
        INSERT INTO operational_v2.task_requirements_v2 (
            id, scenario_id, task_code, task_name, task_type, priority,
            location, location_address, status, required_capabilities
        ) VALUES (
            $1, $2, 'TEST-ROUTE-001', '路径规划测试任务', 'rescue', 'high',
            ST_GeogFromText('POINT(103.87 31.66)'), '茂县测试地点', 'pending',
            ARRAY['RESCUE_STRUCTURAL']::text[]
        )
    """, new_id, UUID(scenario_id))
    return str(new_id)


async def get_risk_area(conn: asyncpg.Connection, scenario_id: str) -> Optional[str]:
    """获取风险区域（用于绕行测试）"""
    row = await conn.fetchrow("""
        SELECT id FROM operational_v2.disaster_affected_areas_v2
        WHERE scenario_id = $1 AND passable = false
        LIMIT 1
    """, UUID(scenario_id))
    
    if row:
        return str(row['id'])
    return None


async def setup_test_data(conn: asyncpg.Connection) -> Dict[str, Any]:
    """准备测试数据"""
    print("\n[准备] 获取测试数据...")
    
    # 1. 获取场景
    scenario_id = await get_or_create_scenario(conn)
    if not scenario_id:
        raise Exception("无法获取测试场景")
    log_info(f"场景ID: {scenario_id}")
    
    # 2. 获取设备
    device = await get_test_device(conn, "land")
    if not device:
        # 尝试获取任意设备
        device = await get_test_device(conn, "air")
    if not device:
        raise Exception("无可用测试设备，请先导入设备数据")
    log_info(f"设备: {device['name']} (env_type={device['env_type']})")
    
    # 3. 获取/创建任务
    task_id = await get_or_create_task(conn, scenario_id)
    if not task_id:
        raise Exception("无法创建测试任务")
    log_info(f"任务ID: {task_id}")
    
    # 4. 获取风险区域（可选）
    risk_area_id = await get_risk_area(conn, scenario_id)
    if risk_area_id:
        log_info(f"风险区域ID: {risk_area_id}")
    else:
        log_info("无风险区域数据（绕行测试将跳过）")
    
    return {
        "scenario_id": scenario_id,
        "device_id": device['id'],
        "device_env_type": device['env_type'],
        "task_id": task_id,
        "risk_area_id": risk_area_id,
    }


# ============================================================================
# 测试用例
# ============================================================================

async def test_plan_and_save(
    client: httpx.AsyncClient,
    device_id: str,
    task_id: str,
    scenario_id: Optional[str] = None,
) -> Optional[str]:
    """T1: 规划并存储路径"""
    print("\n" + "=" * 60)
    print("T1: POST /routing/plan-and-save (规划并存储路径)")
    print("=" * 60)
    
    request_data = {
        "device_id": device_id,
        "origin": ORIGIN,
        "destination": DESTINATION,
        "task_id": task_id,
    }
    if scenario_id:
        request_data["scenario_id"] = scenario_id
    
    try:
        response = await client.post(
            "/routing/plan-and-save",
            json=request_data,
            timeout=30.0
        )
        
        log_info(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                route_id = data.get("route_id")
                route = data.get("route", {})
                distance_km = route.get("total_distance_m", 0) / 1000
                log_ok(f"路径规划成功: route_id={route_id}, distance={distance_km:.2f}km")
                return route_id
            else:
                log_fail(f"规划失败: {data.get('error')}")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            print(f"  响应: {response.text[:200]}")
            
    except httpx.ConnectError:
        log_fail("连接失败，请确保服务已启动")
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return None


async def test_plan_with_risk_check(
    client: httpx.AsyncClient,
    device_id: str,
    task_id: str,
    scenario_id: str,
) -> Dict[str, Any]:
    """T2: 规划路径带风险检测"""
    print("\n" + "=" * 60)
    print("T2: POST /routing/plan-and-save (带风险检测)")
    print("=" * 60)
    
    try:
        response = await client.post(
            "/routing/plan-and-save",
            json={
                "device_id": device_id,
                "origin": ORIGIN,
                "destination": DESTINATION,
                "task_id": task_id,
                "scenario_id": scenario_id,
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                has_risk = data.get("has_risk", False)
                risk_areas = data.get("risk_areas", [])
                
                if has_risk:
                    log_ok(f"检测到 {len(risk_areas)} 个风险区域, has_risk=True")
                else:
                    log_ok(f"无风险区域, has_risk=False")
                
                return {
                    "route_id": data.get("route_id"),
                    "has_risk": has_risk,
                    "risk_areas": risk_areas,
                }
            else:
                log_fail(f"规划失败: {data.get('error')}")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return {}


async def test_query_routes(
    client: httpx.AsyncClient,
    task_id: str,
) -> List[Dict[str, Any]]:
    """T3: 查询任务路径列表"""
    print("\n" + "=" * 60)
    print(f"T3: GET /routing/routes/{task_id}")
    print("=" * 60)
    
    try:
        response = await client.get(
            f"/routing/routes/{task_id}",
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])
            total = data.get("total", 0)
            
            log_ok(f"查询到 {total} 条路径记录")
            for route in routes[:3]:
                log_info(f"  - {route['route_id'][:8]}... status={route['status']}, distance={route['total_distance_m']/1000:.2f}km")
            
            return routes
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return []


async def test_get_active_route(
    client: httpx.AsyncClient,
    task_id: str,
    expect_found: bool = True,
) -> Optional[Dict[str, Any]]:
    """T4: 获取任务活跃路径"""
    print("\n" + "=" * 60)
    print(f"T4: GET /routing/routes/{task_id}/active")
    print("=" * 60)
    
    try:
        response = await client.get(
            f"/routing/routes/{task_id}/active",
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if expect_found:
                log_ok(f"活跃路径: route_id={data['route_id'][:8]}..., status={data['status']}")
                return data
            else:
                log_fail("预期404但返回了200")
        elif response.status_code == 404:
            if not expect_found:
                log_ok("无活跃路径，返回404符合预期")
            else:
                log_fail("预期有活跃路径但返回404")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return None


async def test_generate_alternatives(
    client: httpx.AsyncClient,
    task_id: str,
    risk_area_ids: List[str],
) -> List[Dict[str, Any]]:
    """T5: 生成绕行方案"""
    print("\n" + "=" * 60)
    print("T5: POST /routing/alternative-routes")
    print("=" * 60)
    
    if not risk_area_ids:
        log_skip("无风险区域数据，跳过绕行方案测试")
        return []
    
    try:
        response = await client.post(
            "/routing/alternative-routes",
            json={
                "task_id": task_id,
                "origin": ORIGIN,
                "destination": DESTINATION,
                "risk_area_ids": risk_area_ids,
            },
            timeout=60.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                alternatives = data.get("alternatives", [])
                count = data.get("alternative_count", 0)
                log_ok(f"生成 {count} 个绕行方案")
                
                for alt in alternatives:
                    log_info(f"  - {alt['strategy_name']}: {alt['distance_m']/1000:.2f}km, {alt['duration_s']/60:.1f}min")
                
                return alternatives
            else:
                log_fail(f"生成失败: {data.get('error')}")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return []


async def test_confirm_route(
    client: httpx.AsyncClient,
    route_id: str,
    task_id: str,
) -> bool:
    """T6: 确认使用某条路径"""
    print("\n" + "=" * 60)
    print("T6: POST /routing/confirm-route-by-id")
    print("=" * 60)
    
    try:
        response = await client.post(
            "/routing/confirm-route-by-id",
            json={
                "route_id": route_id,
                "task_id": task_id,
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                log_ok(f"路径已确认: {data.get('message')}")
                return True
            else:
                log_fail(f"确认失败: {data.get('message')}")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return False


async def test_verify_status_changes(
    client: httpx.AsyncClient,
    task_id: str,
) -> bool:
    """T7: 验证状态变更"""
    print("\n" + "=" * 60)
    print("T7: GET /routing/routes/{task_id} (验证状态变更)")
    print("=" * 60)
    
    try:
        response = await client.get(
            f"/routing/routes/{task_id}",
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])
            
            status_counts = {}
            for route in routes:
                status = route.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            log_info(f"路径状态统计: {status_counts}")
            
            # 验证：应该有且仅有1个active
            active_count = status_counts.get("active", 0)
            if active_count == 1:
                log_ok(f"状态验证通过: active={active_count}")
                return True
            else:
                log_fail(f"active路径数异常: {active_count}")
        else:
            log_fail(f"HTTP错误: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")
    
    return False


async def test_invalid_device(client: httpx.AsyncClient, task_id: str):
    """T8: 无效设备ID测试"""
    print("\n" + "=" * 60)
    print("T8: POST /routing/plan-and-save (无效设备ID)")
    print("=" * 60)
    
    fake_device_id = str(uuid4())
    
    try:
        response = await client.post(
            "/routing/plan-and-save",
            json={
                "device_id": fake_device_id,
                "origin": ORIGIN,
                "destination": DESTINATION,
                "task_id": task_id,
            },
            timeout=30.0
        )
        
        if response.status_code in (400, 404, 422):
            log_ok(f"无效设备ID返回 {response.status_code} 符合预期")
        elif response.status_code == 200:
            data = response.json()
            if not data.get("success"):
                log_ok(f"返回失败响应: {data.get('error')}")
            else:
                log_fail("无效设备ID不应返回成功")
        else:
            log_fail(f"意外的状态码: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")


async def test_no_active_route(client: httpx.AsyncClient):
    """T9: 无活跃路径返回404"""
    print("\n" + "=" * 60)
    print("T9: GET /routing/routes/{task_id}/active (无记录)")
    print("=" * 60)
    
    fake_task_id = str(uuid4())
    
    try:
        response = await client.get(
            f"/routing/routes/{fake_task_id}/active",
            timeout=30.0
        )
        
        if response.status_code == 404:
            log_ok("无活跃路径返回404符合预期")
        else:
            log_fail(f"预期404，实际: {response.status_code}")
            
    except Exception as e:
        log_fail(f"异常: {e}")


# ============================================================================
# 数据库验证
# ============================================================================

async def verify_route_in_db(conn: asyncpg.Connection, route_id: str) -> bool:
    """验证路径已存储到数据库"""
    row = await conn.fetchrow("""
        SELECT id, task_id, status, total_distance_m
        FROM operational_v2.planned_routes_v2
        WHERE id = $1
    """, UUID(route_id))
    
    if row:
        log_info(f"DB验证: route_id={route_id[:8]}..., status={row['status']}, distance={row['total_distance_m']}m")
        return True
    else:
        log_info(f"DB验证: 未找到 route_id={route_id}")
        return False


# ============================================================================
# 清理
# ============================================================================

async def cleanup_test_routes(conn: asyncpg.Connection, task_id: str):
    """清理测试创建的路径"""
    print("\n[清理] 删除测试路径...")
    
    result = await conn.execute("""
        DELETE FROM operational_v2.planned_routes_v2
        WHERE task_id = $1
    """, UUID(task_id))
    
    print(f"  已删除测试路径: {result}")


# ============================================================================
# 主函数
# ============================================================================

async def main(base_url: str):
    print("=" * 60)
    print("路径规划接口 E2E 测试")
    print("=" * 60)
    print(f"服务地址: {base_url}")
    print(f"数据库: {DSN.split('@')[1] if '@' in DSN else DSN}")
    
    # 连接数据库
    print("\n连接数据库...")
    try:
        conn = await asyncpg.connect(DSN)
        await conn.execute("SET search_path TO operational_v2, public;")
        print("数据库连接成功")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)
    
    # HTTP客户端
    async with httpx.AsyncClient(base_url=base_url) as client:
        try:
            # 准备测试数据
            test_data = await setup_test_data(conn)
            
            device_id = test_data["device_id"]
            task_id = test_data["task_id"]
            scenario_id = test_data["scenario_id"]
            risk_area_id = test_data.get("risk_area_id")
            
            # T1: 规划并存储路径
            route_id_1 = await test_plan_and_save(client, device_id, task_id)
            
            if route_id_1:
                await verify_route_in_db(conn, route_id_1)
            
            # T2: 带风险检测的规划
            result_2 = await test_plan_with_risk_check(client, device_id, task_id, scenario_id)
            
            # T3: 查询任务路径
            routes = await test_query_routes(client, task_id)
            
            # T4: 获取活跃路径
            active_route = await test_get_active_route(client, task_id, expect_found=len(routes) > 0)
            
            # T5: 生成绕行方案
            risk_area_ids = [risk_area_id] if risk_area_id else []
            alternatives = await test_generate_alternatives(client, task_id, risk_area_ids)
            
            # T6: 确认使用绕行路径
            if alternatives:
                alt_route_id = alternatives[0].get("route_id")
                if alt_route_id:
                    await test_confirm_route(client, alt_route_id, task_id)
                    
                    # T7: 验证状态变更
                    await test_verify_status_changes(client, task_id)
            else:
                log_skip("无绕行方案，跳过确认和验证测试")
                test_results["skipped"] += 2
            
            # T8: 无效设备ID
            await test_invalid_device(client, task_id)
            
            # T9: 无活跃路径返回404
            await test_no_active_route(client)
            
            # 清理测试数据
            await cleanup_test_routes(conn, task_id)
            
        except Exception as e:
            print(f"\n[ERROR] 测试异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            await conn.close()
    
    # 打印测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"通过: {test_results['passed']}")
    print(f"失败: {test_results['failed']}")
    print(f"跳过: {test_results['skipped']}")
    
    if test_results['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="路径规划接口E2E测试")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"服务地址 (默认: {DEFAULT_BASE_URL})"
    )
    args = parser.parse_args()
    
    asyncio.run(main(args.base_url))
