"""
EmergencyAI 安全与 GRA 端到端测试。

覆盖目标：
1) Break Glass 路径审计写入。
2) 缺操作者信息时不写审计。
3) Reject 场景应阻断确认（暴露缺陷也接受）。
4) 缺坐标/任务起点必须报错。
5) GRA 配置缺失应导致分析失败，不可降级。
6) 审计查询接口可读。

方法：直接注入 _task_results 构造方案，必要时真实调用 /emergency-analyze 触发完整链路。
"""
from __future__ import annotations

import importlib
import json
import uuid
from datetime import datetime
import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg
import httpx
from httpx import ASGITransport
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from src.core.config import settings

from tests.e2e.conftest import AI_PREFIX
ai_router_module = importlib.import_module("src.agents.router")
from tests.e2e.utils.api_client import EmergencyAIClient

pytestmark = pytest.mark.anyio("asyncio")


def _dsn_for_asyncpg() -> str:
    """转换 SQLAlchemy DSN 为 asyncpg 可用 DSN。"""
    return settings.database_url.replace("+asyncpg", "")


def _fake_allocation(resource_id: str) -> Dict[str, Any]:
    """构造包含位置信息的分配，满足 GRA 输入要求。"""
    return {
        "resource_id": resource_id,
        "task_id": f"task-{uuid.uuid4().hex[:8]}",
        "task_name": "测试任务",
        "task_code": "TEST",
        "task_start": {"lat": 30.0, "lng": 120.0},
        "resource_state": {
            "current_position": [30.1, 120.1],
            "home_position": [30.2, 120.2],
            "remaining_capacity": 80.0,
            "max_range": 200.0,
            "current_task_progress": 0.0,
        },
        "priority": 2,
        "is_preemptible": True,
    }


def _inject_task_result(
    task_id: str,
    recommended_scheme: Dict[str, Any],
    *,
    event_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
) -> None:
    """向内存缓存注入 AI 结果，避免真实长链调用。"""
    ai_router_module._task_results[task_id] = {
        "success": True,
        "event_id": event_id or str(uuid.uuid4()),
        "scenario_id": scenario_id or str(uuid.uuid4()),
        "status": "completed",
        "recommended_scheme": recommended_scheme,
        "trace": {"phases_executed": ["matching", "optimization"]},
    }


async def _seed_team() -> str:
    """确保存在可用队伍，返回队伍ID，满足必填列约束。"""
    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        row = await conn.fetchrow(
            """
            SELECT id
            FROM operational_v2.rescue_teams_v2
            WHERE status='standby'
            LIMIT 1
            """
        )
        if row:
            return str(row["id"])

        team_id = str(uuid.uuid4())
        code = f"E2E-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            """
            INSERT INTO operational_v2.rescue_teams_v2 (
              id, code, name, status, team_type, created_at
            ) VALUES (
              $1, $2, $3, 'standby', 'search_rescue', NOW()
            )
            """,
            team_id,
            code,
            "E2E队伍",
        )
        return team_id
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def api_client() -> httpx.AsyncClient:
    """使用本地应用的 ASGI 客户端，确保共享内存态结果。"""
    from src.main import app
    from src.core.database import get_db

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
        TestSession = async_sessionmaker(
            test_engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False
        )
        async with TestSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        await test_engine.dispose()

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_event() -> Dict[str, Any]:
    """在本地数据库创建测试事件和场景，填充必填列。"""
    scenario_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    event_code = f"E2E-CODE-{uuid.uuid4().hex[:6]}"
    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        await conn.execute(
            """
            INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status, created_at)
            VALUES ($1, 'E2E场景', 'earthquake', 'active', NOW())
            ON CONFLICT (id) DO NOTHING;
            """,
            scenario_id,
        )
        await conn.execute(
            """
            INSERT INTO operational_v2.events_v2 (
              id, scenario_id, event_code, event_type, title, description,
              priority, status, location, source_type, source_detail,
              media_attachments, reported_at, created_at, updated_at
            ) VALUES (
              $1, $2, $3, 'earthquake', 'E2E事件', '用于端到端测试',
              'medium', 'confirmed', ST_SetSRID(ST_MakePoint(120.0,30.0),4326),
              'manual_report', '{}'::jsonb, '[]'::jsonb, NOW(), NOW(), NOW()
            )
            ON CONFLICT (id) DO NOTHING;
            """,
            event_id,
            scenario_id,
            event_code,
        )
    finally:
        await conn.close()
    return {"id": event_id, "scenario_id": scenario_id, "event_code": event_code}


@pytest.mark.asyncio
@pytest.mark.db
async def test_break_glass_audit_insert(
    api_client: httpx.AsyncClient,
    test_event: Dict[str, Any],
) -> None:
    """命中 Break Glass 后应写入审计表和视图可查询。"""
    team_id = await _seed_team()
    task_id = f"emergency-{uuid.uuid4()}"
    scheme = {
        "solution_id": f"sol-{uuid.uuid4().hex[:6]}",
        "allocations": [_fake_allocation(team_id)],
        "break_glass_rules": [
            {
                "rule_id": "BG_TEST_001",
                "rule_name": "E2E强制BreakGlass",
                "risk_description": "E2E测试强制触发Break Glass",
                "message": "E2E触发",
            }
        ],
        "safety_classification": {
            "reject": [],
            "break_glass": [
                {
                    "rule_id": "BG_TEST_001",
                    "rule_name": "E2E强制BreakGlass",
                    "risk_description": "E2E测试强制触发Break Glass",
                    "message": "E2E触发",
                }
            ],
            "warn": [],
        },
    }
    _inject_task_result(
        task_id,
        scheme,
        event_id=test_event["id"],
        scenario_id=test_event["scenario_id"],
    )

    resp = await api_client.post(
        f"{AI_PREFIX}/emergency-analyze/{task_id}/confirm",
        json={
            "team_ids": [team_id],
            "operator_id": "op-test",
            "operator_name": "审计员",
            "operator_role": "commander",
            "auth_method": "long_press_5s",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True

    # 验证审计写入
    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        rec = await conn.fetchrow(
            """
            SELECT rule_id, operator_id
            FROM audit.safety_overrides
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        assert rec is not None
        assert rec["rule_id"] == "BG_TEST_001"

        view_rec = await conn.fetchrow(
            """
            SELECT rule_id
            FROM audit.recent_overrides
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        assert view_rec is not None
        assert view_rec["rule_id"] == "BG_TEST_001"
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_break_glass_missing_operator_no_audit(
    api_client: httpx.AsyncClient,
    test_event: Dict[str, Any],
) -> None:
    """缺操作者信息时应告警但不写审计。"""
    team_id = await _seed_team()
    task_id = f"emergency-{uuid.uuid4()}"
    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        count_before = await conn.fetchval(
            """
            SELECT count(1) FROM audit.safety_overrides WHERE rule_id='BG_TEST_001'
            """
        )
    finally:
        await conn.close()
    scheme = {
        "solution_id": f"sol-{uuid.uuid4().hex[:6]}",
        "allocations": [_fake_allocation(team_id)],
        "break_glass_rules": [
            {
                "rule_id": "BG_TEST_001",
                "rule_name": "E2E强制BreakGlass",
                "risk_description": "E2E测试强制触发Break Glass",
            }
        ],
    }
    _inject_task_result(
        task_id,
        scheme,
        event_id=test_event["id"],
        scenario_id=test_event["scenario_id"],
    )

    resp = await api_client.post(
        f"{AI_PREFIX}/emergency-analyze/{task_id}/confirm",
        json={"team_ids": [team_id]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True

    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        count_after = await conn.fetchval(
            """
            SELECT count(1)
            FROM audit.safety_overrides
            WHERE rule_id='BG_TEST_001' AND created_at > NOW() - INTERVAL '10 minutes'
            """
        )
    finally:
        await conn.close()
    assert count_after == count_before  # 不应新增审计记录


@pytest.mark.asyncio
async def test_reject_should_block_confirm(api_client: httpx.AsyncClient, test_event: Dict[str, Any]) -> None:
    """classification.reject 存在时应拒绝确认（若未阻断则暴露缺陷）。"""
    team_id = await _seed_team()
    task_id = f"emergency-{uuid.uuid4()}"
    scheme = {
        "solution_id": f"sol-{uuid.uuid4().hex[:6]}",
        "allocations": [_fake_allocation(team_id)],
        "safety_classification": {
            "reject": [
                {
                    "rule_id": "RJ_TEST_001",
                    "rule_name": "E2E强制Reject",
                    "message": "E2E触发拒绝",
                    "action": "reject",
                }
            ],
            "break_glass": [],
            "warn": [],
        },
    }
    _inject_task_result(
        task_id,
        scheme,
        event_id=test_event["id"],
        scenario_id=test_event["scenario_id"],
    )

    resp = await api_client.post(
        f"{AI_PREFIX}/emergency-analyze/{task_id}/confirm",
        json={"team_ids": [team_id]},
    )
    assert resp.status_code in (400, 409, 500)
    body = resp.json()
    assert body.get("success") is False or body.get("conflict") is True


@pytest.mark.asyncio
async def test_missing_positions_should_fail(api_client: httpx.AsyncClient, test_event: Dict[str, Any]) -> None:
    """缺少任务起点或资源坐标时应报错，不得降级。"""
    team_id = await _seed_team()
    task_id = f"emergency-{uuid.uuid4()}"
    bad_alloc = {
        "resource_id": team_id,
        "task_id": "task-missing-pos",
        "task_start": None,
        "resource_state": {"current_position": [30.1, 120.1]},
    }
    scheme = {
        "solution_id": f"sol-{uuid.uuid4().hex[:6]}",
        "allocations": [bad_alloc],
    }
    _inject_task_result(
        task_id,
        scheme,
        event_id=test_event["id"],
        scenario_id=test_event["scenario_id"],
    )

    resp = await api_client.post(
        f"{AI_PREFIX}/emergency-analyze/{task_id}/confirm",
        json={"team_ids": [team_id]},
    )
    body = resp.json()
    assert resp.status_code in (400, 500) or body.get("success") is False


@pytest.mark.asyncio
async def test_gra_config_missing_should_error(
    api_client: httpx.AsyncClient,
    test_event: Dict[str, Any],
) -> None:
    """删除 GRA 配置后触发分析应失败，禁止静默降级。"""
    conn = await asyncpg.connect(_dsn_for_asyncpg())
    try:
        original = await conn.fetch(
            """
            SELECT id, code, name, name_cn, params, description, is_active
            FROM config.algorithm_parameters
            WHERE category='gra'
            """
        )
        await conn.execute("DELETE FROM config.algorithm_parameters WHERE category='gra'")
    finally:
        await conn.close()

    client = EmergencyAIClient(api_client, AI_PREFIX)
    event_id = test_event["id"]
    scenario_id = test_event["scenario_id"]
    try:
        submit = await client.submit_analyze(
            event_id=event_id,
            scenario_id=scenario_id,
            disaster_description="E2E GRA缺配置测试",
            structured_input={"location": {"longitude": 120.0, "latitude": 30.0}},
        )
        result = await client.poll_result(submit.get("task_id", ""), max_wait=15, interval=3.0)
        assert result.status in ("failed", "interrupted", "timeout"), result.raw
    finally:
        conn_restore = await asyncpg.connect(_dsn_for_asyncpg())
        try:
            for row in original:
                await conn_restore.execute(
                    """
                    INSERT INTO config.algorithm_parameters (
                      id, category, code, name, name_cn, params, description, is_active
                    ) VALUES (
                      $1, 'gra', $2, $3, $4, $5, $6, $7
                    )
                    ON CONFLICT (id)
                    DO UPDATE SET params = EXCLUDED.params, is_active = EXCLUDED.is_active
                    """,
                    row["id"],
                    row["code"],
                    row["name"],
                    row["name_cn"],
                    row["params"],
                    row["description"],
                    row["is_active"],
                )
        finally:
            await conn_restore.close()


@pytest.mark.asyncio
async def test_audit_query(api_client: httpx.AsyncClient) -> None:
    """验证审计查询接口可返回记录。"""
    resp = await api_client.get("/api/v2/api/audit/break-glass", params={"limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # 允许空，但若有记录应包含 rule_id
    if data:
        assert "rule_id" in data[0]
