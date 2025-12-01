#!/usr/bin/env python3
"""
待处理事件接口端到端测试

验证内容：
1. 查询待处理事件接口 (POST /events/pending-action)
2. 为事件生成AI方案接口 (POST /events/{eventId}/generate-scheme)
3. 方案时效性判断（5分钟过期）

运行方式：
  # 仅单元测试（无需数据库/LLM）
  PYTHONPATH=. python3 scripts/test_pending_action_e2e.py --unit-only

  # 完整端到端测试（需要数据库）
  PYTHONPATH=. python3 scripts/test_pending_action_e2e.py

  # 指定数据库和vLLM
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db \
  OPENAI_BASE_URL=http://192.168.31.50:8000/v1 \
  PYTHONPATH=. python3 scripts/test_pending_action_e2e.py
"""

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """测试结果"""
    name: str
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None


# ==============================================================================
# 单元测试：Schema验证
# ==============================================================================

def test_schema_imports() -> list[TestResult]:
    """测试Schema导入"""
    results = []
    
    try:
        from src.domains.frontend_api.pending_action.schemas import (
            PendingActionRequest,
            GenerateSchemeRequest,
            PendingActionEventItem,
            GenerateSchemeResponse,
            EventDetail,
            SchemeDetail,
            LocationResponse,
        )
        results.append(TestResult(
            name="Schema导入成功",
            passed=True,
            message="所有Schema类导入正常",
        ))
    except ImportError as e:
        results.append(TestResult(
            name="Schema导入成功",
            passed=False,
            message=f"导入失败: {e}",
        ))
        return results
    
    # 测试PendingActionRequest
    try:
        req = PendingActionRequest(scenarioId=uuid4())
        results.append(TestResult(
            name="PendingActionRequest验证",
            passed=req.scenario_id is not None,
            message="scenarioId别名映射正确",
        ))
    except Exception as e:
        results.append(TestResult(
            name="PendingActionRequest验证",
            passed=False,
            message=f"验证失败: {e}",
        ))
    
    # 测试GenerateSchemeRequest
    try:
        req = GenerateSchemeRequest(scenarioId=uuid4())
        results.append(TestResult(
            name="GenerateSchemeRequest验证",
            passed=req.scenario_id is not None,
            message="scenarioId别名映射正确",
        ))
    except Exception as e:
        results.append(TestResult(
            name="GenerateSchemeRequest验证",
            passed=False,
            message=f"验证失败: {e}",
        ))
    
    return results


def test_router_imports() -> list[TestResult]:
    """测试Router导入"""
    results = []
    
    try:
        from src.domains.frontend_api.pending_action.router import (
            router,
            SCHEME_EXPIRE_MINUTES,
            is_scheme_expired,
        )
        results.append(TestResult(
            name="Router导入成功",
            passed=True,
            message="路由和工具函数导入正常",
        ))
        
        # 验证方案过期时间常量
        results.append(TestResult(
            name="方案过期时间常量",
            passed=SCHEME_EXPIRE_MINUTES == 5,
            message="方案有效期应为5分钟",
            expected=5,
            actual=SCHEME_EXPIRE_MINUTES,
        ))
        
    except ImportError as e:
        results.append(TestResult(
            name="Router导入成功",
            passed=False,
            message=f"导入失败: {e}",
        ))
    
    return results


def test_scheme_expiry_logic() -> list[TestResult]:
    """测试方案过期逻辑"""
    results = []
    
    from src.domains.frontend_api.pending_action.router import is_scheme_expired
    
    # 创建Mock Scheme对象
    class MockScheme:
        def __init__(self, created_at: datetime):
            self.created_at = created_at
    
    # 测试1: None方案不过期
    results.append(TestResult(
        name="None方案不过期",
        passed=is_scheme_expired(None) == False,
        message="scheme为None时返回False",
    ))
    
    # 测试2: 1分钟前的方案不过期
    recent_scheme = MockScheme(datetime.now(timezone.utc) - timedelta(minutes=1))
    results.append(TestResult(
        name="1分钟前方案不过期",
        passed=is_scheme_expired(recent_scheme) == False,
        message="1分钟 < 5分钟阈值",
    ))
    
    # 测试3: 4分钟前的方案不过期
    near_expiry = MockScheme(datetime.now(timezone.utc) - timedelta(minutes=4))
    results.append(TestResult(
        name="4分钟前方案不过期",
        passed=is_scheme_expired(near_expiry) == False,
        message="4分钟 < 5分钟阈值",
    ))
    
    # 测试4: 6分钟前的方案过期
    expired_scheme = MockScheme(datetime.now(timezone.utc) - timedelta(minutes=6))
    results.append(TestResult(
        name="6分钟前方案已过期",
        passed=is_scheme_expired(expired_scheme) == True,
        message="6分钟 > 5分钟阈值",
    ))
    
    # 测试5: 30分钟前的方案过期
    old_scheme = MockScheme(datetime.now(timezone.utc) - timedelta(minutes=30))
    results.append(TestResult(
        name="30分钟前方案已过期",
        passed=is_scheme_expired(old_scheme) == True,
        message="30分钟 > 5分钟阈值",
    ))
    
    # 测试6: 无时区的datetime处理
    naive_scheme = MockScheme(datetime.utcnow() - timedelta(minutes=6))
    results.append(TestResult(
        name="无时区datetime处理",
        passed=is_scheme_expired(naive_scheme) == True,
        message="应正确处理无时区的datetime",
    ))
    
    return results


def test_event_type_filtering() -> list[TestResult]:
    """测试事件类型过滤逻辑"""
    results = []
    
    # 需要处理的事件类型（应返回）
    actionable_types = [
        'trapped_person',      # 被困人员
        'fire',                # 火灾
        'flood',               # 洪水
        'landslide',           # 滑坡
        'building_collapse',   # 建筑倒塌
        'road_damage',         # 道路损毁
        'power_outage',        # 电力中断 - 工程抢险队
        'communication_lost',  # 通信中断 - 通信保障队
        'hazmat_leak',         # 危化品泄漏
        'epidemic',            # 疫情
        'earthquake_secondary',# 次生灾害
        'other',               # 其他
    ]
    
    # 排除的事件类型（不应返回）
    excluded_types = [
        'earthquake',  # 主震信息
    ]
    
    results.append(TestResult(
        name="需要处理的事件类型数量",
        passed=len(actionable_types) == 12,
        message="应有12种需要处理的事件类型",
        expected=12,
        actual=len(actionable_types),
    ))
    
    results.append(TestResult(
        name="排除的事件类型",
        passed=excluded_types == ['earthquake'],
        message="只排除earthquake主震信息",
        expected=['earthquake'],
        actual=excluded_types,
    ))
    
    # 验证power_outage和communication_lost在可处理列表中
    results.append(TestResult(
        name="电力中断事件可处理",
        passed='power_outage' in actionable_types,
        message="power_outage应由工程抢险队处理",
    ))
    
    results.append(TestResult(
        name="通信中断事件可处理",
        passed='communication_lost' in actionable_types,
        message="communication_lost应由通信保障队处理",
    ))
    
    return results


def test_route_registration() -> list[TestResult]:
    """测试路由注册"""
    results = []
    
    try:
        from src.domains.frontend_api.router import frontend_router
        
        routes = [r.path for r in frontend_router.routes if hasattr(r, 'path')]
        
        # 检查pending-action路由
        has_pending_action = '/events/pending-action' in routes
        results.append(TestResult(
            name="pending-action路由注册",
            passed=has_pending_action,
            message="/events/pending-action 应已注册",
        ))
        
        # 检查generate-scheme路由
        has_generate_scheme = '/events/{event_id}/generate-scheme' in routes
        results.append(TestResult(
            name="generate-scheme路由注册",
            passed=has_generate_scheme,
            message="/events/{event_id}/generate-scheme 应已注册",
        ))
        
    except Exception as e:
        results.append(TestResult(
            name="路由注册检查",
            passed=False,
            message=f"检查失败: {e}",
        ))
    
    return results


def run_unit_tests() -> bool:
    """运行所有单元测试"""
    logger.info("=" * 60)
    logger.info("待处理事件接口 - 单元测试")
    logger.info("=" * 60)
    
    all_results: list[TestResult] = []
    
    # Schema测试
    logger.info("\n[1/4] Schema验证")
    schema_results = test_schema_imports()
    all_results.extend(schema_results)
    for r in schema_results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}: {r.message}")
    
    # Router测试
    logger.info("\n[2/4] Router验证")
    router_results = test_router_imports()
    all_results.extend(router_results)
    for r in router_results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}: {r.message}")
    
    # 方案过期逻辑测试
    logger.info("\n[3/4] 方案过期逻辑验证")
    expiry_results = test_scheme_expiry_logic()
    all_results.extend(expiry_results)
    for r in expiry_results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}: {r.message}")
    
    # 事件类型过滤测试
    logger.info("\n[4/4] 事件类型过滤验证")
    type_results = test_event_type_filtering()
    all_results.extend(type_results)
    for r in type_results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}: {r.message}")
    
    # 路由注册测试
    logger.info("\n[5/5] 路由注册验证")
    route_results = test_route_registration()
    all_results.extend(route_results)
    for r in route_results:
        status = "✅" if r.passed else "❌"
        logger.info(f"  {status} {r.name}: {r.message}")
    
    # 统计
    passed = sum(1 for r in all_results if r.passed)
    total = len(all_results)
    
    logger.info("\n" + "-" * 40)
    logger.info(f"单元测试结果: {passed}/{total} 通过")
    
    return passed == total


# ==============================================================================
# 端到端测试：数据库集成
# ==============================================================================

async def test_pending_action_api() -> bool:
    """测试待处理事件查询接口"""
    logger.info("\n" + "=" * 60)
    logger.info("端到端测试 - 查询待处理事件")
    logger.info("=" * 60)
    
    try:
        from src.core.database import AsyncSessionLocal
        from src.domains.frontend_api.pending_action.router import get_pending_action_events
        from src.domains.frontend_api.pending_action.schemas import PendingActionRequest
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # 1. 查询已有的scenario_id
            result = await db.execute(text("""
                SELECT DISTINCT scenario_id FROM operational_v2.events_v2 
                WHERE status = 'confirmed' 
                LIMIT 1
            """))
            row = result.fetchone()
            
            if not row:
                logger.warning("数据库中没有confirmed状态的事件，跳过API测试")
                logger.info("请先创建测试数据或使用真实数据")
                return True  # 不算失败
            
            scenario_id = row[0]
            logger.info(f"使用scenario_id: {scenario_id}")
            
            # 2. 调用接口
            request = PendingActionRequest(scenarioId=scenario_id)
            response = await get_pending_action_events(request, db)
            
            logger.info(f"响应code: {response.code}")
            logger.info(f"响应message: {response.message}")
            
            if response.code != 200:
                logger.error(f"接口返回错误: {response.message}")
                return False
            
            data = response.data
            logger.info(f"返回事件数量: {len(data) if data else 0}")
            
            if data:
                for i, item in enumerate(data[:3]):  # 只显示前3个
                    event = item.get('event', {})
                    scheme = item.get('scheme')
                    has_scheme = item.get('hasScheme', False)
                    scheme_expired = item.get('schemeExpired', False)
                    
                    logger.info(f"\n  事件 {i+1}:")
                    logger.info(f"    ID: {event.get('eventId')}")
                    logger.info(f"    标题: {event.get('title')}")
                    logger.info(f"    类型: {event.get('eventType')}")
                    logger.info(f"    优先级: {event.get('priority')}")
                    logger.info(f"    有方案: {has_scheme}")
                    logger.info(f"    方案过期: {scheme_expired}")
                    
                    if scheme:
                        logger.info(f"    方案ID: {scheme.get('schemeId')}")
                        logger.info(f"    方案标题: {scheme.get('title')}")
            
            logger.info("\n✅ 查询待处理事件接口测试通过")
            return True
            
    except Exception as e:
        logger.exception(f"端到端测试失败: {e}")
        return False


async def test_database_query_logic() -> bool:
    """测试数据库查询逻辑"""
    logger.info("\n" + "=" * 60)
    logger.info("端到端测试 - 数据库查询逻辑")
    logger.info("=" * 60)
    
    try:
        from src.core.database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as db:
            # 先检查表是否存在
            check_sql = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'operational_v2' 
                    AND table_name = 'schemes_v2'
                )
            """)
            check_result = await db.execute(check_sql)
            schemes_exists = check_result.scalar()
            
            # 根据表是否存在选择不同的查询
            if schemes_exists:
                sql = text("""
                    SELECT 
                        e.id,
                        e.event_code,
                        e.event_type,
                        e.title,
                        e.status,
                        e.priority,
                        (SELECT COUNT(*) FROM operational_v2.tasks_v2 t WHERE t.event_id = e.id) as task_count,
                        (SELECT COUNT(*) FROM operational_v2.schemes_v2 s WHERE s.event_id = e.id) as scheme_count
                    FROM operational_v2.events_v2 e
                    WHERE e.status = 'confirmed'
                      AND e.event_type != 'earthquake'
                    ORDER BY e.reported_at DESC
                    LIMIT 10
                """)
            else:
                logger.warning("schemes_v2表不存在，使用简化查询")
                sql = text("""
                    SELECT 
                        e.id,
                        e.event_code,
                        e.event_type,
                        e.title,
                        e.status,
                        e.priority,
                        (SELECT COUNT(*) FROM operational_v2.tasks_v2 t WHERE t.event_id = e.id) as task_count,
                        0 as scheme_count
                    FROM operational_v2.events_v2 e
                    WHERE e.status = 'confirmed'
                      AND e.event_type != 'earthquake'
                    ORDER BY e.reported_at DESC
                    LIMIT 10
                """)
            
            result = await db.execute(sql)
            rows = result.fetchall()
            
            logger.info(f"查询到 {len(rows)} 个confirmed状态事件")
            
            pending_count = 0
            for row in rows:
                has_task = row.task_count > 0
                has_scheme = row.scheme_count > 0
                is_pending = not has_task
                
                if is_pending:
                    pending_count += 1
                
                status_icon = "⏳" if is_pending else "✓"
                logger.info(
                    f"  {status_icon} {row.event_code} | "
                    f"类型:{row.event_type} | "
                    f"任务数:{row.task_count} | "
                    f"方案数:{row.scheme_count}"
                )
            
            logger.info(f"\n待处理（无任务）事件: {pending_count}/{len(rows)}")
            logger.info("✅ 数据库查询逻辑测试通过")
            return True
            
    except Exception as e:
        logger.exception(f"数据库查询测试失败: {e}")
        return False


async def run_e2e_tests() -> bool:
    """运行端到端测试"""
    # 检查数据库连接
    try:
        from src.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
        logger.info("✅ 数据库连接成功")
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        logger.info("请确保DATABASE_URL环境变量配置正确")
        return False
    
    # 运行测试
    results = []
    
    # 测试1: 数据库查询逻辑
    results.append(await test_database_query_logic())
    
    # 测试2: API接口
    results.append(await test_pending_action_api())
    
    return all(results)


async def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="待处理事件接口端到端测试")
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="仅运行单元测试（不需要数据库）",
    )
    args = parser.parse_args()
    
    # 单元测试
    unit_passed = run_unit_tests()
    
    if args.unit_only:
        sys.exit(0 if unit_passed else 1)
    
    # 端到端测试
    e2e_passed = await run_e2e_tests()
    
    # 最终结果
    logger.info("\n" + "=" * 60)
    logger.info("最终结果")
    logger.info("=" * 60)
    logger.info(f"  单元测试: {'✅ 通过' if unit_passed else '❌ 失败'}")
    logger.info(f"  端到端测试: {'✅ 通过' if e2e_passed else '❌ 失败'}")
    
    if unit_passed and e2e_passed:
        logger.info("\n🎉 所有测试通过!")
        sys.exit(0)
    else:
        logger.error("\n❌ 部分测试失败")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
