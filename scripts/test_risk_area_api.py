#!/usr/bin/env python3
"""
风险区域管理接口 端到端测试

测试流程：
1. POST /api/v1/risk-area → 创建风险区域
2. GET /api/v1/risk-area → 获取列表
3. GET /api/v1/risk-area/{id} → 获取详情
4. PUT /api/v1/risk-area/{id} → 更新属性
5. PATCH /api/v1/risk-area/{id}/passage-status → 更新通行状态
6. DELETE /api/v1/risk-area/{id} → 删除区域
7. 数据库验证

前置条件：
- FastAPI 服务已启动 (python -m src.main)
- 数据库已执行 v15_passage_status_extension.sql 迁移

用法: 
  python scripts/test_risk_area_api.py [--base-url http://localhost:8000]
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import asyncpg


# 默认配置
DEFAULT_BASE_URL = "http://localhost:8000"
# 从环境变量读取，或使用默认值（请在环境变量中设置实际密码）
import os
DSN = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/emergency_agent")

# 测试标记
TEST_NAME_PREFIX = "E2E测试风险区域"


async def get_or_create_scenario(conn: asyncpg.Connection) -> str:
    """获取或创建测试想定"""
    existing = await conn.fetchrow("""
        SELECT id FROM operational_v2.scenarios_v2 
        WHERE status = 'active' 
        LIMIT 1
    """)
    
    if existing:
        print(f"[INFO] 使用已存在的想定: {existing['id']}")
        return str(existing['id'])
    
    new_id = uuid4()
    await conn.execute("""
        INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status)
        VALUES ($1, '风险区域E2E测试想定', 'earthquake', 'active')
    """, new_id)
    print(f"[INFO] 创建新想定: {new_id}")
    return str(new_id)


async def test_create_risk_area(client: httpx.AsyncClient, scenario_id: str) -> dict:
    """测试1: 创建风险区域"""
    print("\n" + "=" * 60)
    print("测试1: POST /api/v1/risk-area")
    print("=" * 60)
    
    request_data = {
        "scenarioId": scenario_id,
        "name": f"{TEST_NAME_PREFIX}-滑坡危险区",
        "areaType": "landslide",
        "riskLevel": 9,
        "severity": "critical",
        "passageStatus": "confirmed_blocked",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[104.5, 31.2], [104.6, 31.2], [104.6, 31.3], [104.5, 31.3], [104.5, 31.2]]]
        },
        "passable": False,
        "speedReductionPercent": 100,
        "reconnaissanceRequired": False,
        "description": "E2E测试创建的滑坡危险区"
    }
    
    print(f"请求: scenarioId={scenario_id}, name={request_data['name']}")
    
    try:
        response = await client.post(
            "/api/v1/risk-area",
            json=request_data,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                area_id = data.get("id")
                print(f"[OK] 风险区域创建成功: id={area_id}")
                print(f"  - 名称: {data.get('name')}")
                print(f"  - 类型: {data.get('areaType')}")
                print(f"  - 风险等级: {data.get('riskLevel')}")
                print(f"  - 通行状态: {data.get('passageStatus')}")
                return {"success": True, "area_id": area_id, "data": data}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
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


async def test_list_risk_areas(client: httpx.AsyncClient, scenario_id: str) -> dict:
    """测试2: 获取风险区域列表"""
    print("\n" + "=" * 60)
    print("测试2: GET /api/v1/risk-area")
    print("=" * 60)
    
    try:
        response = await client.get(
            "/api/v1/risk-area",
            params={"scenarioId": scenario_id},
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                items = data.get("items", [])
                total = data.get("total", 0)
                print(f"[OK] 获取成功，共 {total} 条记录")
                
                for item in items[:5]:
                    print(f"  - {item.get('name')}: riskLevel={item.get('riskLevel')}, status={item.get('passageStatus')}")
                
                return {"success": True, "total": total, "items": items}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_get_risk_area(client: httpx.AsyncClient, area_id: str) -> dict:
    """测试3: 获取风险区域详情"""
    print("\n" + "=" * 60)
    print(f"测试3: GET /api/v1/risk-area/{area_id}")
    print("=" * 60)
    
    try:
        response = await client.get(
            f"/api/v1/risk-area/{area_id}",
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                print(f"[OK] 获取成功: {data.get('name')}")
                print(f"  - ID: {data.get('id')}")
                print(f"  - 类型: {data.get('areaType')}")
                print(f"  - 风险等级: {data.get('riskLevel')}")
                print(f"  - 通行状态: {data.get('passageStatus')}")
                print(f"  - 几何数据: {'有' if data.get('geometry') else '无'}")
                return {"success": True, "data": data}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_update_risk_area(client: httpx.AsyncClient, area_id: str) -> dict:
    """测试4: 更新风险区域"""
    print("\n" + "=" * 60)
    print(f"测试4: PUT /api/v1/risk-area/{area_id}")
    print("=" * 60)
    
    update_data = {
        "riskLevel": 7,
        "severity": "high",
        "description": "E2E测试更新：风险降级，部分路段已清理"
    }
    
    print(f"更新内容: riskLevel=7, severity=high")
    
    try:
        response = await client.put(
            f"/api/v1/risk-area/{area_id}",
            json=update_data,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                print(f"[OK] 更新成功")
                print(f"  - 新风险等级: {data.get('riskLevel')}")
                print(f"  - 新严重程度: {data.get('severity')}")
                
                # 验证更新是否生效
                if data.get("riskLevel") == 7 and data.get("severity") == "high":
                    return {"success": True, "data": data}
                else:
                    print("[WARN] 更新值与预期不符")
                    return {"success": False, "error": "更新值不符"}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_update_passage_status(client: httpx.AsyncClient, area_id: str) -> dict:
    """测试5: 更新通行状态"""
    print("\n" + "=" * 60)
    print(f"测试5: PATCH /api/v1/risk-area/{area_id}/passage-status")
    print("=" * 60)
    
    update_data = {
        "passageStatus": "passable_with_caution"
    }
    
    print(f"更新通行状态: passable_with_caution")
    
    try:
        response = await client.patch(
            f"/api/v1/risk-area/{area_id}/passage-status",
            json=update_data,
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                print(f"[OK] 通行状态更新成功: {data.get('passageStatus')}")
                print(f"  - 最后验证时间: {data.get('lastVerifiedAt')}")
                
                if data.get("passageStatus") == "passable_with_caution":
                    return {"success": True, "data": data}
                else:
                    return {"success": False, "error": "状态值不符"}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_verify_database(conn: asyncpg.Connection, area_id: str) -> dict:
    """测试6: 验证数据库数据"""
    print("\n" + "=" * 60)
    print("测试6: 验证数据库数据")
    print("=" * 60)
    
    try:
        row = await conn.fetchrow("""
            SELECT id, name, area_type, risk_level, severity, passage_status,
                   passable, speed_reduction_percent, reconnaissance_required,
                   last_verified_at
            FROM operational_v2.disaster_affected_areas_v2
            WHERE id = $1
        """, area_id)
        
        if not row:
            print(f"[FAIL] 数据库中未找到记录: {area_id}")
            return {"success": False, "error": "记录不存在"}
        
        print(f"[OK] 数据库验证成功")
        print(f"  - ID: {row['id']}")
        print(f"  - 名称: {row['name']}")
        print(f"  - 类型: {row['area_type']}")
        print(f"  - 风险等级: {row['risk_level']}")
        print(f"  - 通行状态: {row['passage_status']}")
        print(f"  - 最后验证: {row['last_verified_at']}")
        
        # 验证更新后的值
        if row['risk_level'] == 7 and row['passage_status'] == 'passable_with_caution':
            print("[OK] 数据库值与API更新一致")
            return {"success": True}
        else:
            print("[WARN] 数据库值与预期不符")
            return {"success": False, "error": "值不一致"}
            
    except Exception as e:
        print(f"[FAIL] 数据库查询失败: {e}")
        return {"success": False, "error": str(e)}


async def test_delete_risk_area(client: httpx.AsyncClient, area_id: str) -> dict:
    """测试7: 删除风险区域"""
    print("\n" + "=" * 60)
    print(f"测试7: DELETE /api/v1/risk-area/{area_id}")
    print("=" * 60)
    
    try:
        response = await client.delete(
            f"/api/v1/risk-area/{area_id}",
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 200:
                print("[OK] 删除成功")
                return {"success": True}
            else:
                print(f"[FAIL] API返回失败: {result.get('message')}")
                return {"success": False, "error": result.get("message")}
        else:
            print(f"[FAIL] HTTP错误: {response.status_code}")
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        return {"success": False, "error": str(e)}


async def test_verify_deletion(conn: asyncpg.Connection, area_id: str) -> dict:
    """测试8: 验证删除"""
    print("\n" + "=" * 60)
    print("测试8: 验证数据已删除")
    print("=" * 60)
    
    try:
        row = await conn.fetchrow("""
            SELECT id FROM operational_v2.disaster_affected_areas_v2
            WHERE id = $1
        """, area_id)
        
        if row:
            print(f"[FAIL] 记录仍然存在: {area_id}")
            return {"success": False, "error": "删除失败"}
        else:
            print("[OK] 数据已成功删除")
            return {"success": True}
            
    except Exception as e:
        print(f"[FAIL] 验证失败: {e}")
        return {"success": False, "error": str(e)}


async def cleanup_test_data(conn: asyncpg.Connection, scenario_id: str):
    """清理测试数据"""
    print("\n" + "=" * 60)
    print("清理测试数据")
    print("=" * 60)
    
    try:
        result = await conn.execute("""
            DELETE FROM operational_v2.disaster_affected_areas_v2
            WHERE scenario_id = $1
            AND name LIKE $2
        """, scenario_id, f"{TEST_NAME_PREFIX}%")
        print(f"[OK] 清理测试数据: {result}")
    except Exception as e:
        print(f"[WARN] 清理失败: {e}")


async def main(base_url: str):
    """主测试流程"""
    print("=" * 60)
    print("风险区域管理接口 端到端测试")
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
    area_id = None
    
    async with httpx.AsyncClient(base_url=base_url) as client:
        # 测试1: 创建
        r1 = await test_create_risk_area(client, scenario_id)
        results.append(("创建风险区域 API", r1["success"]))
        
        if r1["success"]:
            area_id = r1["area_id"]
            
            # 测试2: 列表
            r2 = await test_list_risk_areas(client, scenario_id)
            results.append(("获取风险区域列表 API", r2["success"]))
            
            # 测试3: 详情
            r3 = await test_get_risk_area(client, area_id)
            results.append(("获取风险区域详情 API", r3["success"]))
            
            # 测试4: 更新
            r4 = await test_update_risk_area(client, area_id)
            results.append(("更新风险区域 API", r4["success"]))
            
            # 测试5: 更新通行状态
            r5 = await test_update_passage_status(client, area_id)
            results.append(("更新通行状态 API", r5["success"]))
            
            # 测试6: 数据库验证
            from uuid import UUID
            r6 = await test_verify_database(conn, UUID(area_id))
            results.append(("数据库数据验证", r6["success"]))
            
            # 测试7: 删除
            r7 = await test_delete_risk_area(client, area_id)
            results.append(("删除风险区域 API", r7["success"]))
            
            # 测试8: 验证删除
            r8 = await test_verify_deletion(conn, UUID(area_id))
            results.append(("验证删除成功", r8["success"]))
        else:
            # 创建失败，跳过后续测试
            for name in ["获取列表", "获取详情", "更新属性", "更新通行状态", 
                        "数据库验证", "删除", "验证删除"]:
                results.append((f"{name} API", False))
    
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
    parser = argparse.ArgumentParser(description="风险区域管理接口 端到端测试")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 基础地址 (默认: {DEFAULT_BASE_URL})"
    )
    args = parser.parse_args()
    
    sys.exit(asyncio.run(main(args.base_url)))
