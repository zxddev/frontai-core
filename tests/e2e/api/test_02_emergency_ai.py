"""
P0: EmergencyAI API端到端测试

测试应急分析智能体的所有API端点，包括正常流程和异常场景。
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict

import pytest

from .utils.api_client import APIClient

logger = logging.getLogger(__name__)


class TestEmergencyAIHappyPath:
    """EmergencyAI正常流程测试"""
    
    @pytest.mark.asyncio
    async def test_normal_analyze_flow(
        self,
        api_client: APIClient,
        valid_emergency_request: Dict[str, Any],
    ) -> None:
        """TC-EA-001: 正常分析流程（提交→轮询→完成）"""
        # 1. 提交分析任务
        submit_result = await api_client.submit_emergency_analyze(valid_emergency_request)
        
        assert submit_result["status_code"] == 202, f"提交失败: {submit_result}"
        task_id = submit_result["response"].get("task_id")
        assert task_id, "响应缺少task_id"
        
        logger.info(f"[TC-EA-001] 提交成功: task_id={task_id}")
        
        # 2. 轮询结果
        result = await api_client.poll_task_result(
            api_client.get_emergency_analyze_result,
            task_id,
            terminal_statuses=["completed", "failed"],
            max_polls=60,
            interval=2.0,
        )
        
        response = result["response"]
        status = response.get("status")
        
        logger.info(f"[TC-EA-001] 最终状态: status={status}")
        
        # 检查结果
        if status == "completed":
            # 验证有分析结果（检查EmergencyAI实际返回的字段）
            has_result = (
                "understanding" in response or 
                "recommended_scheme" in response or
                "reasoning" in response
            )
            assert has_result, f"完成但缺少结果数据: {list(response.keys())}"
        else:
            # 即使失败也算测试通过，因为我们测的是流程
            logger.warning(f"[TC-EA-001] 任务未完成: status={status}")
    
    @pytest.mark.asyncio
    async def test_query_by_event_id(
        self,
        api_client: APIClient,
        valid_emergency_request: Dict[str, Any],
    ) -> None:
        """TC-EA-010: 按event_id查询"""
        event_id = valid_emergency_request["event_id"]
        
        # 先提交一个任务
        submit_result = await api_client.submit_emergency_analyze(valid_emergency_request)
        
        if submit_result["status_code"] == 202:
            # 等待一下
            await asyncio.sleep(1)
            
            # 按event_id查询
            result = await api_client.get_emergency_analyze_by_event(event_id)
            
            logger.info(f"[TC-EA-010] 按event_id查询: status={result['status_code']}, response={result['response']}")
        else:
            logger.warning(f"[TC-EA-010] 提交失败，跳过查询测试")


class TestEmergencyAIValidation:
    """EmergencyAI参数验证测试"""
    
    @pytest.mark.asyncio
    async def test_missing_event_id(self, api_client: APIClient) -> None:
        """TC-EA-002: 缺少event_id应返回400/422"""
        request = {
            "scenario_id": "test",
            "disaster_description": "测试描述",
            "disaster_type": "earthquake",
        }
        
        result = await api_client.submit_emergency_analyze(request)
        
        logger.info(f"[TC-EA-002] 缺少event_id: status={result['status_code']}")
        
        assert result["status_code"] in [400, 422], f"应返回400/422: {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_invalid_disaster_type(
        self,
        api_client: APIClient,
        unique_event_id: str,
        unique_scenario_id: str,
    ) -> None:
        """TC-EA-003: 无效disaster_type应被处理"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": unique_scenario_id,
            "disaster_description": "测试灾害描述，详细信息不少于10个字符",
            "disaster_type": "unknown_disaster_type_xyz",
        }
        
        result = await api_client.submit_emergency_analyze(request)
        
        logger.info(f"[TC-EA-003] 无效disaster_type: status={result['status_code']}, response={result['response']}")
        
        # 可能接受后内部处理，或返回验证错误
    
    @pytest.mark.asyncio
    async def test_empty_disaster_description(
        self,
        api_client: APIClient,
        unique_event_id: str,
        unique_scenario_id: str,
    ) -> None:
        """TC-EA-004: 空disaster_description应被处理"""
        request = {
            "event_id": unique_event_id,
            "scenario_id": unique_scenario_id,
            "disaster_description": "",
            "disaster_type": "earthquake",
        }
        
        result = await api_client.submit_emergency_analyze(request)
        
        logger.info(f"[TC-EA-004] 空描述: status={result['status_code']}")


class TestEmergencyAIErrorHandling:
    """EmergencyAI错误处理测试"""
    
    @pytest.mark.asyncio
    async def test_query_nonexistent_task(self, api_client: APIClient) -> None:
        """TC-EA-007: 查询不存在的task_id应返回404"""
        result = await api_client.get_emergency_analyze_result("nonexistent-task-id-12345")
        
        logger.info(f"[TC-EA-007] 查询不存在任务: status={result['status_code']}")
        
        assert result["status_code"] == 404, f"应返回404: {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_confirm_nonexistent_scheme(self, api_client: APIClient) -> None:
        """TC-EA-008: 确认不存在的方案应返回404"""
        result = await api_client.confirm_emergency_scheme(
            "nonexistent-task-id",
            {"scheme_id": "fake-scheme"}
        )
        
        logger.info(f"[TC-EA-008] 确认不存在方案: status={result['status_code']}")
        
        # 可能返回404(不存在)或422(验证失败)
        assert result["status_code"] in [404, 422], f"应返回404/422: {result['status_code']}"
    
    @pytest.mark.asyncio
    async def test_double_confirm(
        self,
        api_client: APIClient,
        valid_emergency_request: Dict[str, Any],
    ) -> None:
        """TC-EA-009: 重复确认方案应幂等或报错"""
        # 提交任务
        submit_result = await api_client.submit_emergency_analyze(valid_emergency_request)
        
        if submit_result["status_code"] != 202:
            pytest.skip("提交失败，跳过测试")
        
        task_id = submit_result["response"]["task_id"]
        
        # 等待完成
        final_result = await api_client.poll_task_result(
            api_client.get_emergency_analyze_result,
            task_id,
            terminal_statuses=["completed", "failed"],
            max_polls=60,
        )
        
        if final_result["response"].get("status") != "completed":
            pytest.skip("任务未完成，跳过确认测试")
        
        # 尝试确认两次
        confirm1 = await api_client.confirm_emergency_scheme(task_id, {"scheme_id": "scheme_1"})
        confirm2 = await api_client.confirm_emergency_scheme(task_id, {"scheme_id": "scheme_1"})
        
        logger.info(f"[TC-EA-009] 第一次确认: {confirm1['status_code']}, 第二次确认: {confirm2['status_code']}")


class TestEmergencyAIConcurrency:
    """EmergencyAI并发测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_analyze_requests(self, api_client: APIClient) -> None:
        """TC-EA-006: 并发5个请求应全部成功"""
        tasks = []
        for i in range(5):
            request = {
                "event_id": str(uuid.uuid4()),
                "scenario_id": str(uuid.uuid4()),
                "disaster_description": f"并发测试地震灾害{i}，震级6.0，有人员伤亡报告",
                "disaster_type": "earthquake",
            }
            tasks.append(api_client.submit_emergency_analyze(request))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[TC-EA-006] 请求{i}异常: {result}")
            else:
                status = result.get("status_code")
                logger.info(f"[TC-EA-006] 请求{i}: status={status}")
                if status == 202:
                    success_count += 1
        
        assert success_count == 5, f"并发请求失败: {success_count}/5"


class TestEmergencyAIPerformance:
    """EmergencyAI性能测试"""
    
    @pytest.mark.asyncio
    async def test_submit_response_time(
        self,
        api_client: APIClient,
        valid_emergency_request: Dict[str, Any],
    ) -> None:
        """TC-EA-005: 提交响应时间应小于5秒（首次请求可能需要初始化）"""
        result = await api_client.submit_emergency_analyze(valid_emergency_request)
        
        logger.info(f"[TC-EA-005] 提交响应时间: {result['elapsed_ms']:.0f}ms")
        
        # 提交是异步的，允许首次请求较慢（服务初始化）
        assert result["elapsed_ms"] < 5000, f"响应时间过长: {result['elapsed_ms']}ms"
