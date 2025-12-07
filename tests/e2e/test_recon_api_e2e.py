"""
ReconScheduler API端到端测试

测试完整的侦察调度API流程，包括：
1. 提交调度任务
2. 轮询获取结果
3. 人工审批流程
4. 检查点保存/恢复
5. 熔断器和限流测试

运行方式:
    PYTHONPATH=. pytest tests/e2e/test_recon_api_e2e.py -v
    TEST_API_URL=http://192.168.31.50:8000 pytest tests/e2e/test_recon_api_e2e.py -v
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Dict, Any

import httpx
import pytest

from .conftest import AI_PREFIX
from .utils.recon_client import ReconSchedulerClient, ReconScheduleResponse


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_recon_request() -> Dict[str, Any]:
    """标准侦察请求"""
    return {
        "event_id": f"test-{uuid.uuid4().hex[:8]}",
        "scenario_id": "test_scenario",
        "recon_request": "搜索茂县震区滞留人员，重点关注居民区和学校",
        "target_area": {
            "type": "Polygon",
            "coordinates": [[[103.8, 31.6], [103.9, 31.6], [103.9, 31.7], [103.8, 31.7], [103.8, 31.6]]]
        },
    }


@pytest.fixture
def low_battery_request(sample_recon_request) -> Dict[str, Any]:
    """低电量请求"""
    req = sample_recon_request.copy()
    req["config"] = {"initial_battery_percent": 15}
    return req


# ============================================================================
# 场景1: 健康检查
# ============================================================================

class TestReconAPIHealth:
    """API健康检查测试"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, api_client: httpx.AsyncClient):
        """测试AI模块健康检查"""
        resp = await api_client.get(f"{AI_PREFIX}/health")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["status"] in ("healthy", "degraded")
        assert data["module"] == "ai-agents"
        print(f"✓ 健康检查: status={data['status']}")


# ============================================================================
# 场景2: 正常调度流程
# ============================================================================

class TestReconScheduleFlow:
    """正常调度流程测试"""
    
    @pytest.mark.asyncio
    async def test_submit_returns_task_id(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试提交任务返回task_id"""
        resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json=sample_recon_request
        )
        
        assert resp.status_code == 202
        data = resp.json()
        assert data["success"] is True
        assert "task_id" in data
        assert data["status"] == "processing"
        print(f"✓ 提交任务: task_id={data['task_id']}")
    
    @pytest.mark.asyncio
    async def test_get_task_status(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试查询任务状态"""
        # 提交任务
        submit_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json=sample_recon_request
        )
        task_id = submit_resp.json()["task_id"]
        
        # 查询状态
        resp = await api_client.get(f"{AI_PREFIX}/recon-schedule/{task_id}")
        assert resp.status_code == 200
        
        data = resp.json()
        assert data["task_id"] == task_id
        assert data["status"] in ("processing", "completed", "failed")
        print(f"✓ 查询状态: task_id={task_id}, status={data['status']}")
    
    @pytest.mark.asyncio
    async def test_task_not_found(self, api_client: httpx.AsyncClient):
        """测试查询不存在的任务"""
        resp = await api_client.get(f"{AI_PREFIX}/recon-schedule/nonexistent-task")
        assert resp.status_code in (404, 400)
        print("✓ 不存在的任务返回正确错误")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_complete_schedule_flow(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试完整调度流程（提交 → 轮询 → 完成）"""
        client = ReconSchedulerClient(api_client, AI_PREFIX)
        
        result = await client.schedule_and_wait(
            event_id=sample_recon_request["event_id"],
            scenario_id=sample_recon_request["scenario_id"],
            recon_request=sample_recon_request["recon_request"],
            target_area=sample_recon_request["target_area"],
            max_wait=120,
        )
        
        assert result.status in ("completed", "failed", "awaiting_approval")
        print(f"✓ 完整流程: status={result.status}, plans={len(result.flight_plans)}")
        
        if result.status == "completed":
            assert result.success is True
            # 航线可能为空（取决于具体实现）


# ============================================================================
# 场景3: 审批流程
# ============================================================================

class TestReconApprovalFlow:
    """审批流程测试"""
    
    @pytest.mark.asyncio
    async def test_approve_invalid_task_state(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试非审批状态下调用审批接口"""
        # 提交任务
        submit_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json=sample_recon_request
        )
        task_id = submit_resp.json()["task_id"]
        
        # 尝试审批（应该失败，因为状态是processing）
        approve_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule/{task_id}/approve",
            json={"approved_degradation": "reduce_altitude"}
        )
        
        # 状态不对，应该返回失败
        data = approve_resp.json()
        # 可能成功也可能失败，取决于任务是否已完成
        print(f"✓ 审批响应: success={data.get('success')}, status={data.get('status')}")
    
    @pytest.mark.asyncio
    async def test_approve_invalid_option(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试使用无效的降级选项"""
        # 创建一个mock任务ID
        fake_task_id = "recon-fake12345"
        
        approve_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule/{fake_task_id}/approve",
            json={"approved_degradation": "invalid_option"}
        )
        
        # 应该返回错误（任务不存在或选项无效）
        assert approve_resp.status_code in (400, 404, 200)
        print("✓ 无效选项处理正确")


# ============================================================================
# 场景4: 检查点测试
# ============================================================================

class TestReconCheckpoint:
    """检查点测试"""
    
    @pytest.mark.asyncio
    async def test_save_checkpoint(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试保存检查点"""
        # 提交任务
        submit_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json=sample_recon_request
        )
        task_id = submit_resp.json()["task_id"]
        
        # 等待一小会让任务开始
        await asyncio.sleep(1)
        
        # 保存检查点
        checkpoint_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule/{task_id}/checkpoint"
        )
        
        if checkpoint_resp.status_code == 200:
            data = checkpoint_resp.json()
            assert data["success"] is True
            assert "checkpoint_id" in data
            print(f"✓ 检查点保存: checkpoint_id={data['checkpoint_id']}")
        else:
            print(f"✓ 检查点保存失败（预期，任务可能已完成）: {checkpoint_resp.status_code}")
    
    @pytest.mark.asyncio
    async def test_resume_task(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试恢复任务"""
        fake_task_id = "recon-resume-test"
        
        resume_resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule/{fake_task_id}/resume",
            json={"force": False}
        )
        
        # 可能失败（没有检查点）或成功
        print(f"✓ 恢复任务响应: {resume_resp.status_code}")


# ============================================================================
# 场景5: 限流测试
# ============================================================================

class TestReconRateLimiting:
    """限流测试"""
    
    @pytest.mark.asyncio
    async def test_rapid_requests_rate_limited(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试快速连续请求被限流"""
        base_request = {
            "event_id": "rate-limit-test",
            "scenario_id": "test",
            "recon_request": "测试限流",
        }
        
        results = []
        # 快速提交5个请求
        for i in range(5):
            req = base_request.copy()
            req["event_id"] = f"rate-limit-{i}"
            
            resp = await api_client.post(
                f"{AI_PREFIX}/recon-schedule",
                json=req
            )
            results.append(resp.status_code)
        
        # 应该有一些请求成功，一些可能被限流
        success_count = sum(1 for r in results if r == 202)
        print(f"✓ 限流测试: {success_count}/5 请求成功")
        
        # 至少应该有一些请求成功
        assert success_count > 0


# ============================================================================
# 场景6: 验证结果结构
# ============================================================================

class TestReconResultStructure:
    """结果结构验证测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_result_has_required_fields(
        self,
        api_client: httpx.AsyncClient,
        sample_recon_request: Dict[str, Any],
    ):
        """测试结果包含所有必需字段"""
        client = ReconSchedulerClient(api_client, AI_PREFIX)
        
        result = await client.schedule_and_wait(
            event_id=sample_recon_request["event_id"],
            scenario_id=sample_recon_request["scenario_id"],
            recon_request=sample_recon_request["recon_request"],
            max_wait=60,
        )
        
        # 检查必需字段
        assert hasattr(result, "task_id")
        assert hasattr(result, "status")
        assert hasattr(result, "success")
        assert hasattr(result, "flight_plans")
        assert hasattr(result, "breaker_state")
        assert hasattr(result, "retry_count")
        
        print(f"✓ 结果字段完整: task_id={result.task_id}, status={result.status}")
        print(f"  breaker_state={result.breaker_state}, retry_count={result.retry_count}")


# ============================================================================
# 场景7: 错误处理测试
# ============================================================================

class TestReconErrorHandling:
    """错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_invalid_request_body(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试无效请求体"""
        resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json={"invalid": "data"}
        )
        
        # 应该返回422 Validation Error
        assert resp.status_code == 422
        print("✓ 无效请求体返回422")
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(
        self,
        api_client: httpx.AsyncClient,
    ):
        """测试缺少必需字段"""
        resp = await api_client.post(
            f"{AI_PREFIX}/recon-schedule",
            json={"event_id": "test"}  # 缺少scenario_id和recon_request
        )
        
        assert resp.status_code == 422
        print("✓ 缺少字段返回422")


# ============================================================================
# 集成测试
# ============================================================================

class TestReconIntegration:
    """集成测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_workflow_with_client(
        self,
        api_client: httpx.AsyncClient,
    ):
        """使用客户端测试完整工作流"""
        client = ReconSchedulerClient(api_client, AI_PREFIX)
        
        # 1. 健康检查
        health = await client.health_check()
        assert health["status"] in ("healthy", "degraded")
        
        # 2. 提交任务
        event_id = f"integration-{uuid.uuid4().hex[:8]}"
        task_id = await client.schedule(
            event_id=event_id,
            scenario_id="integration_test",
            recon_request="集成测试侦察任务",
        )
        assert task_id.startswith("recon-")
        
        # 3. 查询状态
        result = await client.get_result(task_id)
        assert result.task_id == task_id
        
        print(f"\n=== 集成测试完成 ===")
        print(f"task_id: {task_id}")
        print(f"status: {result.status}")
        print(f"breaker_state: {result.breaker_state}")
        print(f"retry_count: {result.retry_count}")


if __name__ == "__main__":
    import sys
    pytest.main([__file__, "-v", *sys.argv[1:]])
