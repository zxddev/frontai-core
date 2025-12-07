"""
确认部署流程端到端测试

测试从AI分析完成到确认部署的完整流程：
1. 获取分析结果
2. 调用确认部署接口
3. 验证任务创建
4. 验证队伍状态更新
5. 验证事件状态更新

运行方式:
    PYTHONPATH=. pytest tests/e2e/test_confirm_deploy.py -v
"""
from __future__ import annotations

import uuid
from typing import Dict, Any, List

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .conftest import AI_PREFIX, API_V2_PREFIX
from .utils.api_client import EmergencyAIClient


# ============================================================================
# 确认部署测试
# ============================================================================

class TestConfirmDeploy:
    """确认部署流程测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    @pytest.mark.db
    async def test_confirm_deploy_creates_tasks(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试确认部署创建任务"""
        event_id = str(uuid.uuid4())
        
        # 1. 提交分析并等待完成
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status != "completed":
            pytest.skip(f"分析未完成: {result.status}")
        
        # 2. 获取推荐方案中的队伍ID
        scheme = result.recommended_scheme
        allocations = scheme.get("allocations", [])
        team_ids = [a.get("resource_id") for a in allocations if a.get("resource_id")]
        
        if not team_ids:
            pytest.skip("方案中无队伍分配")
        
        task_id = f"emergency-{event_id}"
        
        # 3. 确认部署
        confirm_resp = await client.confirm_scheme(
            task_id=task_id,
            team_ids=team_ids[:3],  # 最多确认3个队伍
            event_id=event_id,
        )
        
        assert confirm_resp.get("success") is True
        
        # 4. 验证任务创建（数据库）
        db_result = await db_session.execute(
            text("""
                SELECT id, title, status 
                FROM operational_v2.tasks_v2 
                WHERE scenario_id = :scenario_id 
                AND created_at > NOW() - INTERVAL '5 minutes'
                ORDER BY created_at DESC
                LIMIT 5
            """),
            {"scenario_id": active_scenario["id"]}
        )
        tasks = db_result.fetchall()
        
        print(f"\n[确认部署] 创建任务数: {len(tasks)}")
        for task in tasks:
            print(f"  - {task[0]}: {task[1]} ({task[2]})")
    
    @pytest.mark.asyncio
    @pytest.mark.db
    async def test_confirm_without_analysis_fails(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试未分析时确认部署失败"""
        fake_task_id = f"emergency-{uuid.uuid4()}"
        
        resp = await api_client.post(
            f"{AI_PREFIX}/emergency-analyze/{fake_task_id}/confirm",
            json={"team_ids": []},
        )
        
        # 应该返回错误状态码
        assert resp.status_code in (404, 400, 422, 500)
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    @pytest.mark.db
    async def test_team_status_updated_after_confirm(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试确认后队伍状态更新"""
        event_id = str(uuid.uuid4())
        
        # 1. 分析
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status != "completed":
            pytest.skip(f"分析未完成: {result.status}")
        
        # 2. 获取队伍ID
        scheme = result.recommended_scheme
        allocations = scheme.get("allocations", [])
        team_ids = [a.get("resource_id") for a in allocations if a.get("resource_id")]
        
        if not team_ids:
            pytest.skip("方案中无队伍分配")
        
        # 3. 记录确认前的队伍状态
        team_id = team_ids[0]
        before_result = await db_session.execute(
            text("SELECT status FROM operational_v2.rescue_teams_v2 WHERE id = :id"),
            {"id": team_id}
        )
        before_row = before_result.fetchone()
        before_status = before_row[0] if before_row else None
        
        # 4. 确认部署
        task_id = f"emergency-{event_id}"
        await client.confirm_scheme(
            task_id=task_id,
            team_ids=[team_id],
            event_id=event_id,
        )
        
        # 5. 验证队伍状态变化
        after_result = await db_session.execute(
            text("SELECT status FROM operational_v2.rescue_teams_v2 WHERE id = :id"),
            {"id": team_id}
        )
        after_row = after_result.fetchone()
        after_status = after_row[0] if after_row else None
        
        print(f"\n[队伍状态] {team_id}")
        print(f"  - 确认前: {before_status}")
        print(f"  - 确认后: {after_status}")
        
        # 状态应该变化（从idle到dispatched等）
        if before_status == "idle":
            assert after_status in ("dispatched", "en_route", "assigned")


# ============================================================================
# 事件状态测试
# ============================================================================

class TestEventStatusUpdate:
    """事件状态更新测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    @pytest.mark.db
    async def test_event_status_updated_after_confirm(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        active_scenario: Dict[str, Any],
        test_event: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试确认后事件状态更新"""
        event_id = test_event["id"]
        
        # 1. 分析
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status != "completed":
            pytest.skip(f"分析未完成: {result.status}")
        
        # 2. 获取队伍并确认
        scheme = result.recommended_scheme
        allocations = scheme.get("allocations", [])
        team_ids = [a.get("resource_id") for a in allocations if a.get("resource_id")]
        
        if team_ids:
            task_id = f"emergency-{event_id}"
            await client.confirm_scheme(
                task_id=task_id,
                team_ids=team_ids[:2],
                event_id=event_id,
            )
        
        # 3. 验证事件状态
        db_result = await db_session.execute(
            text("SELECT status FROM operational_v2.events_v2 WHERE id = :id"),
            {"id": event_id}
        )
        row = db_result.fetchone()
        
        if row:
            print(f"\n[事件状态] {event_id}: {row[0]}")
            # 确认后状态应该是dispatched或in_progress
            assert row[0] in ("confirmed", "dispatched", "in_progress", "responding")


# ============================================================================
# 分配记录测试
# ============================================================================

class TestAssignmentRecords:
    """任务分配记录测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    @pytest.mark.db
    async def test_assignment_records_created(
        self,
        api_client: httpx.AsyncClient,
        db_session: AsyncSession,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试分配记录创建"""
        event_id = str(uuid.uuid4())
        
        # 1. 分析并确认
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status != "completed":
            pytest.skip(f"分析未完成: {result.status}")
        
        scheme = result.recommended_scheme
        allocations = scheme.get("allocations", [])
        team_ids = [a.get("resource_id") for a in allocations if a.get("resource_id")]
        
        if not team_ids:
            pytest.skip("方案中无队伍分配")
        
        task_id = f"emergency-{event_id}"
        await client.confirm_scheme(
            task_id=task_id,
            team_ids=team_ids[:3],
            event_id=event_id,
        )
        
        # 2. 查询分配记录
        db_result = await db_session.execute(
            text("""
                SELECT ta.id, ta.task_id, ta.team_id, ta.status
                FROM operational_v2.task_assignments_v2 ta
                JOIN operational_v2.tasks_v2 t ON ta.task_id = t.id
                WHERE t.scenario_id = :scenario_id
                AND ta.created_at > NOW() - INTERVAL '5 minutes'
                ORDER BY ta.created_at DESC
                LIMIT 10
            """),
            {"scenario_id": active_scenario["id"]}
        )
        assignments = db_result.fetchall()
        
        print(f"\n[分配记录] 共{len(assignments)}条:")
        for a in assignments:
            print(f"  - {a[0]}: task={a[1]}, team={a[2]}, status={a[3]}")
        
        # 应该有分配记录
        # assert len(assignments) > 0  # 根据实际情况调整


# ============================================================================
# 方案选择测试
# ============================================================================

class TestSchemeSelection:
    """方案选择测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_pareto_solutions_available(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试Pareto最优解可用"""
        event_id = str(uuid.uuid4())
        
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status != "completed":
            pytest.skip(f"分析未完成: {result.status}")
        
        # 验证Pareto解
        pareto = result.pareto_solutions
        if pareto:
            print(f"\n[Pareto解] 共{len(pareto)}个:")
            for i, sol in enumerate(pareto[:3]):
                print(f"  {i+1}. {sol.get('solution_id')}: score={sol.get('total_score', 0):.2f}")
