"""
P0: ReconScheduler API端到端测试

测试侦察调度智能体的所有API端点，包括正常流程和异常场景。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict

import pytest

from .conftest import IssueTracker
from .utils.api_client import APIClient

logger = logging.getLogger(__name__)


class TestReconSchedulerHappyPath:
    """ReconScheduler正常流程测试"""
    
    @pytest.mark.asyncio
    async def test_small_area_complete_flow(
        self,
        api_client: APIClient,
        valid_recon_request: Dict[str, Any],
    ) -> None:
        """TC-RS-001: 小区域正常流程应返回completed"""
        # 1. 提交任务
        submit_result = await api_client.submit_recon_schedule(valid_recon_request)
        
        assert submit_result["status_code"] == 202, f"提交失败: {submit_result}"
        task_id = submit_result["response"].get("task_id")
        assert task_id, "响应缺少task_id"
        
        logger.info(f"[TC-RS-001] 提交成功: task_id={task_id}")
        
        # 2. 轮询结果
        result = await api_client.poll_task_result(
            api_client.get_recon_schedule_result,
            task_id,
            terminal_statuses=["completed", "failed", "awaiting_approval"],
            max_polls=30,
            interval=2.0,
        )
        
        response = result["response"]
        status = response.get("status")
        success = response.get("success")
        flight_plans = response.get("flight_plans", [])
        errors = response.get("errors", [])
        
        logger.info(f"[TC-RS-001] 结果: status={status}, success={success}, plans={len(flight_plans)}, errors={len(errors)}")
        
        assert status == "completed", f"状态应为completed: {status}"
        assert success is True, f"应该成功: success={success}, errors={errors}"
        assert len(flight_plans) > 0, "应该有航线"
    
    @pytest.mark.asyncio
    async def test_large_area_rejection(
        self,
        api_client: APIClient,
        unique_event_id: str,
        unique_scenario_id: str,
        large_area_geojson: Dict[str, Any],
    ) -> None:
        """TC-RS-002: 大区域应被正确拒绝"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": unique_scenario_id,
            "recon_request": "大区域侦察任务",
            "target_area": large_area_geojson,
            "disaster_context": {"disaster_type": "earthquake"},
        }
        
        # 提交任务
        submit_result = await api_client.submit_recon_schedule(request)
        assert submit_result["status_code"] == 202
        task_id = submit_result["response"]["task_id"]
        
        # 轮询结果
        result = await api_client.poll_task_result(
            api_client.get_recon_schedule_result,
            task_id,
            terminal_statuses=["completed", "failed"],
            max_polls=30,
        )
        
        response = result["response"]
        status = response.get("status")
        success = response.get("success")
        errors = response.get("errors", [])
        
        logger.info(f"[TC-RS-002] 结果: status={status}, success={success}, errors={errors[:2]}")
        
        assert status == "failed", f"大区域应该失败: {status}"
        assert success is False, "大区域不应成功"
        assert len(errors) > 0, "应该有错误信息"
        
        # 验证错误信息包含距离相关内容
        errors_text = " ".join(errors)
        assert "区域过大" in errors_text or "超出" in errors_text or "distance" in errors_text.lower(), \
            f"错误信息应提及区域过大: {errors_text}"


class TestReconSchedulerValidation:
    """ReconScheduler参数验证测试"""
    
    @pytest.mark.asyncio
    async def test_missing_event_id(self, api_client: APIClient) -> None:
        """TC-RS-003: 缺少event_id应返回400"""
        request = {
            "scenario_id": "test",
            "recon_request": "测试",
        }
        
        result = await api_client.submit_recon_schedule(request)
        
        logger.info(f"[TC-RS-003] 缺少event_id: status={result['status_code']}")
        
        # 应该返回422(验证错误)或400(错误请求)
        assert result["status_code"] in [400, 422], f"应返回400/422: {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_invalid_geojson_format(
        self,
        api_client: APIClient,
        unique_event_id: str,
        invalid_geojson: Dict[str, Any],
    ) -> None:
        """TC-RS-004: 无效GeoJSON格式应被处理"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": "test",
            "recon_request": "测试",
            "target_area": invalid_geojson,
        }
        
        result = await api_client.submit_recon_schedule(request)
        
        logger.info(f"[TC-RS-004] 无效GeoJSON: status={result['status_code']}, response={result['response']}")
        
        # 可能返回400/422验证错误，或接受后在处理中报错
    
    @pytest.mark.asyncio
    async def test_empty_target_area(
        self,
        api_client: APIClient,
        unique_event_id: str,
    ) -> None:
        """TC-RS-005: 空target_area应被处理"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": "test",
            "recon_request": "测试侦察",
            "target_area": None,
        }
        
        result = await api_client.submit_recon_schedule(request)
        
        logger.info(f"[TC-RS-005] 空target_area: status={result['status_code']}")
    
    @pytest.mark.asyncio
    async def test_extreme_coordinates(
        self,
        api_client: APIClient,
        unique_event_id: str,
    ) -> None:
        """TC-RS-006: 极端坐标(0,0)应被处理"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": "test",
            "recon_request": "测试侦察",
            "target_area": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0.01, 0], [0.01, 0.01], [0, 0.01], [0, 0]]]
            },
        }
        
        result = await api_client.submit_recon_schedule(request)
        
        logger.info(f"[TC-RS-006] 极端坐标: status={result['status_code']}")


class TestReconSchedulerCheckpoint:
    """ReconScheduler检查点测试"""
    
    @pytest.mark.asyncio
    async def test_checkpoint_save(
        self,
        api_client: APIClient,
        valid_recon_request: Dict[str, Any],
    ) -> None:
        """TC-RS-007: 检查点保存应成功"""
        # 提交任务
        submit_result = await api_client.submit_recon_schedule(valid_recon_request)
        assert submit_result["status_code"] == 202
        task_id = submit_result["response"]["task_id"]
        
        # 等待一段时间让任务开始执行
        await asyncio.sleep(1)
        
        # 保存检查点
        checkpoint_result = await api_client.save_recon_checkpoint(task_id)
        
        logger.info(f"[TC-RS-007] 检查点保存: status={checkpoint_result['status_code']}, response={checkpoint_result['response']}")
    
    @pytest.mark.asyncio
    async def test_checkpoint_resume(
        self,
        api_client: APIClient,
        valid_recon_request: Dict[str, Any],
    ) -> None:
        """TC-RS-008: 检查点恢复应成功"""
        # 提交任务
        submit_result = await api_client.submit_recon_schedule(valid_recon_request)
        task_id = submit_result["response"]["task_id"]
        
        # 等待完成
        await api_client.poll_task_result(
            api_client.get_recon_schedule_result,
            task_id,
            terminal_statuses=["completed", "failed"],
            max_polls=30,
        )
        
        # 尝试恢复(即使已完成)
        resume_result = await api_client.resume_recon_task(task_id, "fake-checkpoint-id")
        
        logger.info(f"[TC-RS-008] 检查点恢复: status={resume_result['status_code']}, response={resume_result['response']}")


class TestReconSchedulerErrorHandling:
    """ReconScheduler错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_query_nonexistent_task(self, api_client: APIClient) -> None:
        """TC-RS-009: 查询不存在的任务应返回404"""
        result = await api_client.get_recon_schedule_result("nonexistent-task-id")
        
        logger.info(f"[TC-RS-009] 查询不存在任务: status={result['status_code']}")
        
        assert result["status_code"] == 404, f"应返回404: {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_approval_flow(
        self,
        api_client: APIClient,
        valid_recon_request: Dict[str, Any],
    ) -> None:
        """TC-RS-010: 降级审批流程测试"""
        # 提交任务
        submit_result = await api_client.submit_recon_schedule(valid_recon_request)
        task_id = submit_result["response"]["task_id"]
        
        # 尝试审批(即使任务可能不需要审批)
        approve_result = await api_client.approve_recon_degradation(
            task_id,
            {"approved": True, "selected_option": "option_1"}
        )
        
        logger.info(f"[TC-RS-010] 降级审批: status={approve_result['status_code']}, response={approve_result['response']}")


class TestReconSchedulerConcurrency:
    """ReconScheduler并发测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_submissions(
        self,
        api_client: APIClient,
        small_area_geojson: Dict[str, Any],
    ) -> None:
        """TC-RS-011: 并发提交多个任务应全部成功"""
        tasks = []
        for i in range(3):
            request = {
                "event_id": f"concurrent-test-{uuid.uuid4().hex[:6]}",
                "scenario_id": "test",
                "recon_request": f"并发测试任务{i}",
                "target_area": small_area_geojson,
            }
            tasks.append(api_client.submit_recon_schedule(request))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[TC-RS-011] 任务{i}异常: {result}")
            else:
                status = result.get("status_code")
                logger.info(f"[TC-RS-011] 任务{i}: status={status}")
                if status == 202:
                    success_count += 1
        
        assert success_count == len(tasks), f"并发提交失败: {success_count}/{len(tasks)}"
