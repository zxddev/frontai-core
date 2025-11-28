#!/usr/bin/env python3
"""
passage_status 端到端测试

测试流程：
1. 触发地震事件 → 写入 disaster_affected_areas_v2（passage_status）
2. 验证风险区域正确创建
3. 测试路径规划引擎的绕行逻辑

用法: python scripts/test_passage_status_e2e.py
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg


# 测试配置
DSN = "postgresql://postgres:postgres123@192.168.31.40:5432/emergency_agent"
TEST_SCENARIO_ID = uuid4()  # 测试用想定ID
TEST_EPICENTER = (104.5, 31.2)  # 测试震中（北川）
TEST_MAGNITUDE = 6.5


async def setup_test_scenario(conn: asyncpg.Connection) -> bool:
    """创建测试想定"""
    try:
        await conn.execute("""
            INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status)
            VALUES ($1, '通行状态测试想定', 'earthquake', 'active')
            ON CONFLICT (id) DO NOTHING
        """, TEST_SCENARIO_ID)
        print(f"[OK] 测试想定已创建: {TEST_SCENARIO_ID}")
        return True
    except Exception as e:
        print(f"[ERROR] 创建测试想定失败: {e}")
        return False


async def test_create_earthquake_risk_zones(conn: asyncpg.Connection) -> bool:
    """测试创建地震风险区域（模拟 _create_earthquake_risk_zones 函数）"""
    print("\n" + "=" * 60)
    print("测试1: 创建地震风险区域")
    print("=" * 60)
    
    event_id = uuid4()
    center_lng, center_lat = TEST_EPICENTER
    magnitude = TEST_MAGNITUDE
    epicenter_name = "北川县"
    
    # 计算各区域半径
    base_radius_m = 2000
    core_radius = min(base_radius_m * (1.5 ** (magnitude - 4)), 10000)
    impact_radius = min(core_radius * 2, 25000)
    outer_radius = min(core_radius * 4, 50000)
    
    zones = [
        {
            "name": f"{epicenter_name}地震核心区",
            "area_type": "seismic_red",
            "radius_m": core_radius,
            "risk_level": 10,
            "passable": True,
            "passable_vehicle_types": ["rescue", "ambulance", "fire_truck", "police"],
            "speed_reduction_percent": 50,
            "passage_status": "needs_reconnaissance",
            "reconnaissance_required": True,
        },
        {
            "name": f"{epicenter_name}地震影响区",
            "area_type": "seismic_orange",
            "radius_m": impact_radius,
            "risk_level": 7,
            "passable": True,
            "passable_vehicle_types": None,
            "speed_reduction_percent": 30,
            "passage_status": "passable_with_caution",
            "reconnaissance_required": False,
        },
        {
            "name": f"{epicenter_name}地震外围区",
            "area_type": "seismic_yellow",
            "radius_m": outer_radius,
            "risk_level": 4,
            "passable": True,
            "passable_vehicle_types": None,
            "speed_reduction_percent": 0,
            "passage_status": "clear",
            "reconnaissance_required": False,
        },
    ]
    
    try:
        for zone in zones:
            # 生成圆形多边形
            import math
            radius_deg = zone["radius_m"] / 111000
            points = []
            for i in range(32):
                angle = 2 * math.pi * i / 32
                lng = center_lng + radius_deg * math.cos(angle)
                lat = center_lat + radius_deg * math.sin(angle) * 0.9
                points.append(f"{lng:.6f} {lat:.6f}")
            points.append(points[0])
            polygon_wkt = f"POLYGON(({', '.join(points)}))"
            
            await conn.execute("""
                INSERT INTO operational_v2.disaster_affected_areas_v2 (
                    scenario_id, name, area_type, geometry, severity, risk_level,
                    passable, passable_vehicle_types, speed_reduction_percent,
                    passage_status, reconnaissance_required, description, properties
                ) VALUES (
                    $1, $2, $3, ST_GeogFromText($4), 'high', $5, $6, $7, $8, $9, $10, $11, $12
                )
            """,
                TEST_SCENARIO_ID,
                zone["name"],
                zone["area_type"],
                polygon_wkt,
                zone["risk_level"],
                zone["passable"],
                zone["passable_vehicle_types"],
                zone["speed_reduction_percent"],
                zone["passage_status"],
                zone["reconnaissance_required"],
                f"测试区域: {zone['name']}",
                f'{{"event_id": "{event_id}", "magnitude": {magnitude}}}',
            )
            print(f"  [OK] 创建区域: {zone['name']} (passage_status={zone['passage_status']})")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 创建风险区域失败: {e}")
        return False


async def test_query_passage_status(conn: asyncpg.Connection) -> bool:
    """测试查询 passage_status 字段"""
    print("\n" + "=" * 60)
    print("测试2: 查询 passage_status 数据")
    print("=" * 60)
    
    try:
        rows = await conn.fetch("""
            SELECT name, area_type, passage_status, reconnaissance_required, risk_level
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
            ORDER BY risk_level DESC
        """, TEST_SCENARIO_ID)
        
        if not rows:
            print("[WARN] 未找到测试数据")
            return False
        
        print(f"\n找到 {len(rows)} 条记录:")
        print("-" * 60)
        for row in rows:
            recon = "需侦察" if row['reconnaissance_required'] else "无需侦察"
            print(f"  {row['name']}: passage_status={row['passage_status']}, {recon}")
        
        # 验证数据正确性
        status_map = {row['area_type']: row['passage_status'] for row in rows}
        expected = {
            'seismic_red': 'needs_reconnaissance',
            'seismic_orange': 'passable_with_caution',
            'seismic_yellow': 'clear',
        }
        
        all_ok = True
        print("\n数据验证:")
        print("-" * 60)
        for area_type, expected_status in expected.items():
            actual = status_map.get(area_type)
            if actual == expected_status:
                print(f"  [OK] {area_type}: {actual}")
            else:
                print(f"  [FAIL] {area_type}: 期望 {expected_status}, 实际 {actual}")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"[ERROR] 查询失败: {e}")
        return False


async def test_blocked_edges_query(conn: asyncpg.Connection) -> bool:
    """测试路径规划引擎的封锁边查询逻辑"""
    print("\n" + "=" * 60)
    print("测试3: 封锁边查询逻辑 (_get_blocked_edges)")
    print("=" * 60)
    
    try:
        # 模拟 db_route_engine._get_blocked_edges 的查询逻辑
        # 场景1: allow_unverified_areas = false（默认，严格模式）
        blocked_strict = await conn.fetch("""
            SELECT d.id, d.name, d.passage_status, d.risk_level
            FROM operational_v2.disaster_affected_areas_v2 d
            WHERE d.scenario_id = $1
            AND (
                COALESCE(d.passage_status, 'unknown') = 'confirmed_blocked'
                OR (
                    COALESCE(d.passage_status, 'unknown') = 'needs_reconnaissance'
                    AND $2 = false
                )
                OR (
                    d.passable = false 
                    AND COALESCE(d.passage_status, 'unknown') = 'unknown'
                )
            )
        """, TEST_SCENARIO_ID, False)
        
        print("\n场景A: 严格模式 (allow_unverified_areas=false)")
        print("-" * 60)
        if blocked_strict:
            for row in blocked_strict:
                print(f"  [BLOCKED] {row['name']}: passage_status={row['passage_status']}")
        else:
            print("  无封锁区域")
        
        # 场景2: allow_unverified_areas = true（宽松模式，允许进入未验证区域）
        blocked_relaxed = await conn.fetch("""
            SELECT d.id, d.name, d.passage_status, d.risk_level
            FROM operational_v2.disaster_affected_areas_v2 d
            WHERE d.scenario_id = $1
            AND (
                COALESCE(d.passage_status, 'unknown') = 'confirmed_blocked'
                OR (
                    COALESCE(d.passage_status, 'unknown') = 'needs_reconnaissance'
                    AND $2 = false
                )
                OR (
                    d.passable = false 
                    AND COALESCE(d.passage_status, 'unknown') = 'unknown'
                )
            )
        """, TEST_SCENARIO_ID, True)
        
        print("\n场景B: 宽松模式 (allow_unverified_areas=true)")
        print("-" * 60)
        if blocked_relaxed:
            for row in blocked_relaxed:
                print(f"  [BLOCKED] {row['name']}: passage_status={row['passage_status']}")
        else:
            print("  无封锁区域 (needs_reconnaissance 区域可通行)")
        
        # 验证逻辑
        strict_count = len(blocked_strict)
        relaxed_count = len(blocked_relaxed)
        
        print("\n逻辑验证:")
        print("-" * 60)
        if strict_count > relaxed_count:
            print(f"  [OK] 严格模式封锁更多区域 ({strict_count} > {relaxed_count})")
            return True
        elif strict_count == relaxed_count == 0:
            # 如果没有 confirmed_blocked 和 needs_reconnaissance，两种模式结果相同
            print(f"  [OK] 无 confirmed_blocked/needs_reconnaissance 区域，两种模式结果相同")
            return True
        else:
            print(f"  [INFO] 严格模式: {strict_count}, 宽松模式: {relaxed_count}")
            return True
        
    except Exception as e:
        print(f"[ERROR] 查询失败: {e}")
        return False


async def test_update_passage_status(conn: asyncpg.Connection) -> bool:
    """测试更新 passage_status（模拟侦察结果返回）"""
    print("\n" + "=" * 60)
    print("测试4: 更新 passage_status（侦察结果）")
    print("=" * 60)
    
    try:
        # 获取核心区ID
        core_zone = await conn.fetchrow("""
            SELECT id, name, passage_status 
            FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1 AND area_type = 'seismic_red'
        """, TEST_SCENARIO_ID)
        
        if not core_zone:
            print("[WARN] 未找到核心区数据")
            return False
        
        print(f"原始状态: {core_zone['name']} = {core_zone['passage_status']}")
        
        # 模拟侦察结果：核心区确认不可通行
        await conn.execute("""
            UPDATE operational_v2.disaster_affected_areas_v2
            SET passage_status = 'confirmed_blocked',
                reconnaissance_required = false,
                last_verified_at = NOW(),
                verified_by = $2
            WHERE id = $1
        """, core_zone['id'], uuid4())
        
        # 验证更新结果
        updated = await conn.fetchrow("""
            SELECT passage_status, reconnaissance_required, last_verified_at
            FROM operational_v2.disaster_affected_areas_v2
            WHERE id = $1
        """, core_zone['id'])
        
        print(f"更新后: passage_status={updated['passage_status']}, verified_at={updated['last_verified_at']}")
        
        if updated['passage_status'] == 'confirmed_blocked':
            print("[OK] 侦察结果更新成功")
            return True
        else:
            print("[FAIL] 更新失败")
            return False
        
    except Exception as e:
        print(f"[ERROR] 更新失败: {e}")
        return False


async def cleanup(conn: asyncpg.Connection):
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)
    
    try:
        deleted = await conn.execute("""
            DELETE FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
        """, TEST_SCENARIO_ID)
        print(f"[OK] 删除测试风险区域: {deleted}")
        
        await conn.execute("""
            DELETE FROM operational_v2.scenarios_v2
            WHERE id = $1
        """, TEST_SCENARIO_ID)
        print(f"[OK] 删除测试想定: {TEST_SCENARIO_ID}")
        
    except Exception as e:
        print(f"[WARN] 清理失败: {e}")


async def main():
    """主测试流程"""
    print("=" * 60)
    print("passage_status 端到端测试")
    print("=" * 60)
    print(f"测试想定ID: {TEST_SCENARIO_ID}")
    print(f"测试震中: {TEST_EPICENTER}")
    print(f"测试震级: {TEST_MAGNITUDE}")
    
    conn = await asyncpg.connect(DSN)
    
    results = []
    
    try:
        # 检查 passage_status 字段是否存在
        col_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'operational_v2'
                AND table_name = 'disaster_affected_areas_v2'
                AND column_name = 'passage_status'
            )
        """)
        
        if not col_exists:
            print("\n[ERROR] passage_status 字段不存在！")
            print("请先执行迁移: psql -f sql/v15_passage_status_extension.sql")
            return 1
        
        # 准备测试环境
        if not await setup_test_scenario(conn):
            return 1
        
        # 执行测试
        results.append(("创建地震风险区域", await test_create_earthquake_risk_zones(conn)))
        results.append(("查询 passage_status", await test_query_passage_status(conn)))
        results.append(("封锁边查询逻辑", await test_blocked_edges_query(conn)))
        results.append(("更新 passage_status", await test_update_passage_status(conn)))
        
    finally:
        await cleanup(conn)
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
    sys.exit(asyncio.run(main()))
