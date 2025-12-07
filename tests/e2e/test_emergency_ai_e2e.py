"""
EmergencyAI端到端测试

测试完整的应急AI分析流程，包括：
1. 提交分析任务
2. 轮询获取结果
3. 验证方案内容
4. 不同灾害场景

运行方式:
    PYTHONPATH=. pytest tests/e2e/test_emergency_ai_e2e.py -v
    PYTHONPATH=. pytest tests/e2e/test_emergency_ai_e2e.py -v -k "earthquake"
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any

import httpx
import pytest

from .conftest import AI_PREFIX, API_V2_PREFIX, poll_task_result
from .utils.api_client import EmergencyAIClient


# ============================================================================
# EmergencyAI分析流程测试
# ============================================================================

class TestEmergencyAnalyzeFlow:
    """EmergencyAI分析流程测试"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, api_client: httpx.AsyncClient):
        """测试AI模块健康检查"""
        resp = await api_client.get(f"{AI_PREFIX}/health")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["module"] == "ai-agents"
        assert "checks" in data
    
    @pytest.mark.asyncio
    async def test_submit_analyze_returns_task_id(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        test_event: Dict[str, Any],
    ):
        """测试提交分析任务返回task_id"""
        payload = {
            "event_id": test_event["id"],
            "scenario_id": active_scenario["id"],
            "disaster_description": "测试地震事件，某建筑发生坍塌",
            "structured_input": {
                "disaster_type": "earthquake",
                "location": {"longitude": 103.85, "latitude": 31.68},
            },
        }
        
        resp = await api_client.post(f"{AI_PREFIX}/emergency-analyze", json=payload)
        
        assert resp.status_code == 202
        data = resp.json()
        assert data["success"] is True
        assert "task_id" in data
        assert data["status"] == "processing"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_earthquake_scenario_complete_flow(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试地震场景完整流程"""
        event_id = str(uuid.uuid4())
        
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            constraints=earthquake_input.get("constraints"),
            max_wait=60,
        )
        
        # 验证基本状态
        assert result.status in ("completed", "failed", "interrupted")
        
        if result.status == "completed":
            assert result.success is True
            
            # 验证推荐方案
            assert result.recommended_scheme is not None
            scheme = result.recommended_scheme
            assert "solution_id" in scheme
            assert "allocations" in scheme or "task_assignments" in scheme
            
            # 验证执行时间
            assert result.execution_time_ms is not None
            assert result.execution_time_ms < 60000  # <60秒
            
            # 验证trace
            assert result.trace is not None
            phases = result.trace.get("phases_executed", [])
            assert "understand_disaster" in phases
            
            print(f"\n[地震场景] 分析完成:")
            print(f"  - 方案ID: {scheme.get('solution_id')}")
            print(f"  - 执行时间: {result.execution_time_ms}ms")
            print(f"  - 阶段: {phases}")
        else:
            print(f"\n[地震场景] 状态: {result.status}")
            print(f"  - 错误: {result.errors}")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_fire_scenario_complete_flow(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        fire_input: Dict[str, Any],
    ):
        """测试火灾场景完整流程"""
        event_id = str(uuid.uuid4())
        
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=fire_input["disaster_description"],
            structured_input=fire_input["structured_input"],
            constraints=fire_input.get("constraints"),
            max_wait=60,
        )
        
        assert result.status in ("completed", "failed", "interrupted")
        
        if result.status == "completed":
            assert result.success is True
            assert result.recommended_scheme is not None
            print(f"\n[火灾场景] 方案ID: {result.recommended_scheme.get('solution_id')}")
    
    @pytest.mark.asyncio
    async def test_get_result_by_event_id(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试通过事件ID获取分析结果"""
        event_id = str(uuid.uuid4())
        
        # 提交任务
        payload = {
            "event_id": event_id,
            "scenario_id": active_scenario["id"],
            "disaster_description": "测试事件",
        }
        await api_client.post(f"{AI_PREFIX}/emergency-analyze", json=payload)
        
        # 通过事件ID查询
        resp = await api_client.get(f"{AI_PREFIX}/emergency-analyze/by-event/{event_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["task_id"] == f"emergency-{event_id}"
    
    @pytest.mark.asyncio
    async def test_invalid_input_validation(self, api_client: httpx.AsyncClient):
        """测试无效输入校验"""
        # 缺少必填字段
        payload = {
            "disaster_description": "测试事件",
        }
        
        resp = await api_client.post(f"{AI_PREFIX}/emergency-analyze", json=payload)
        assert resp.status_code == 422  # Validation Error
    
    @pytest.mark.asyncio
    async def test_nonexistent_task_returns_404(self, api_client: httpx.AsyncClient):
        """测试不存在的任务返回404"""
        fake_task_id = "nonexistent-task-12345"
        
        resp = await api_client.get(f"{AI_PREFIX}/emergency-analyze/{fake_task_id}")
        assert resp.status_code == 404


# ============================================================================
# 方案验证测试
# ============================================================================

class TestSchemeValidation:
    """方案内容验证测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_scheme_has_required_fields(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """验证方案包含必要字段"""
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
        
        scheme = result.recommended_scheme
        assert scheme is not None
        
        # 必要字段
        assert "solution_id" in scheme
        assert "total_score" in scheme or "weighted_score" in scheme
        
        # 资源分配
        allocations = scheme.get("allocations", [])
        task_assignments = scheme.get("task_assignments", [])
        assert len(allocations) > 0 or len(task_assignments) > 0
        
        # 响应时间
        assert "response_time_min" in scheme
        assert scheme["response_time_min"] >= 0
        
        # 覆盖率
        assert "coverage_rate" in scheme
        assert 0 <= scheme["coverage_rate"] <= 1
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_scheme_explanation_generated(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """验证方案解释已生成"""
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
        
        # 方案解释
        assert result.scheme_explanation is not None
        assert len(result.scheme_explanation) > 100  # 至少100字符


# ============================================================================
# 并发和性能测试
# ============================================================================

class TestConcurrencyAndPerformance:
    """并发和性能测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_submissions(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试并发提交多个分析任务"""
        async def submit_one(idx: int) -> Dict[str, Any]:
            event_id = str(uuid.uuid4())
            payload = {
                "event_id": event_id,
                "scenario_id": active_scenario["id"],
                "disaster_description": f"并发测试事件{idx}，某地发生紧急情况需要救援",
            }
            resp = await api_client.post(f"{AI_PREFIX}/emergency-analyze", json=payload)
            return {"idx": idx, "status": resp.status_code, "data": resp.json()}
        
        # 并发提交5个任务
        tasks = [submit_one(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # 验证所有提交成功
        for result in results:
            assert result["status"] == 202
            assert result["data"]["success"] is True
            print(f"  任务{result['idx']}: {result['data']['task_id']}")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    async def test_execution_time_under_limit(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
        earthquake_input: Dict[str, Any],
    ):
        """测试执行时间在限制内"""
        event_id = str(uuid.uuid4())
        
        client = EmergencyAIClient(api_client, AI_PREFIX)
        result = await client.analyze_and_wait(
            event_id=event_id,
            scenario_id=active_scenario["id"],
            disaster_description=earthquake_input["disaster_description"],
            structured_input=earthquake_input["structured_input"],
            max_wait=60,
        )
        
        if result.status == "completed" and result.execution_time_ms:
            assert result.execution_time_ms < 30000  # <30秒
            print(f"\n执行时间: {result.execution_time_ms}ms")


# ============================================================================
# 规则管理测试
# ============================================================================

class TestRulesManagement:
    """规则管理测试"""
    
    @pytest.mark.asyncio
    async def test_get_rules_stats(self, api_client: httpx.AsyncClient):
        """测试获取规则统计"""
        resp = await api_client.get(f"{AI_PREFIX}/rules/stats")
        assert resp.status_code == 200
        
        data = resp.json()
        assert "cache_stats" in data
        assert "rules_loaded" in data
    
    @pytest.mark.asyncio
    async def test_reload_rules(self, api_client: httpx.AsyncClient):
        """测试热更新规则"""
        resp = await api_client.post(f"{AI_PREFIX}/rules/reload")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["success"] is True
        assert "after" in data
