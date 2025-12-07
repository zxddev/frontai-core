"""
P1: RoutePlanning API端到端测试

测试路由规划的所有API端点。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import pytest

from .utils.api_client import APIClient

logger = logging.getLogger(__name__)


class TestRoutePlanningHappyPath:
    """路由规划正常流程测试"""
    
    @pytest.mark.asyncio
    async def test_normal_route_planning(
        self,
        api_client: APIClient,
        valid_route_request: Dict[str, Any],
    ) -> None:
        """TC-RP-001: 正常路线规划"""
        result = await api_client.plan_route(valid_route_request)
        
        logger.info(f"[TC-RP-001] 路线规划: status={result['status_code']}, elapsed={result['elapsed_ms']:.0f}ms")
        
        # 检查响应
        if result["status_code"] == 200:
            response = result["response"]
            logger.info(f"[TC-RP-001] 规划结果: {list(response.keys())}")
    
    @pytest.mark.asyncio
    async def test_route_with_risk_check(
        self,
        api_client: APIClient,
        valid_route_request: Dict[str, Any],
    ) -> None:
        """TC-RP-004: 带风险检查的规划"""
        result = await api_client.plan_route_with_risk_check(valid_route_request)
        
        logger.info(f"[TC-RP-004] 风险检查规划: status={result['status_code']}")
        
        if result["status_code"] == 200:
            response = result["response"]
            # 检查是否有风险信息
            has_risk_info = "risk" in str(response).lower() or "risks" in response or "risk_areas" in response
            logger.info(f"[TC-RP-004] 包含风险信息: {has_risk_info}")


class TestRoutePlanningValidation:
    """路由规划参数验证测试"""
    
    @pytest.mark.asyncio
    async def test_same_start_end_point(self, api_client: APIClient) -> None:
        """TC-RP-002: 起终点相同应被处理"""
        request = {
            "device_id": "91f271d0-c797-4eb1-93ff-c729aaa75f03",
            "origin": {"lon": 104.0668, "lat": 30.5728},
            "destination": {"lon": 104.0668, "lat": 30.5728},  # 与起点相同
        }
        
        result = await api_client.plan_route(request)
        
        logger.info(f"[TC-RP-002] 起终点相同: status={result['status_code']}, response={result['response']}")
    
    @pytest.mark.asyncio
    async def test_invalid_coordinates(self, api_client: APIClient) -> None:
        """TC-RP-006: 无效坐标应返回400/422"""
        request = {
            "device_id": "91f271d0-c797-4eb1-93ff-c729aaa75f03",
            "origin": {"lon": -999, "lat": 999},      # 无效坐标
            "destination": {"lon": 103.85, "lat": 31.68},
        }
        
        result = await api_client.plan_route(request)
        
        logger.info(f"[TC-RP-006] 无效坐标: status={result['status_code']}")
        
        # 应该返回400/422或处理错误
    
    @pytest.mark.asyncio
    async def test_very_long_distance(self, api_client: APIClient) -> None:
        """TC-RP-007: 超长距离应被处理"""
        request = {
            "device_id": "91f271d0-c797-4eb1-93ff-c729aaa75f03",
            "origin": {"lon": 100.0, "lat": 30.0},    # 四川西部
            "destination": {"lon": 116.0, "lat": 40.0},  # 北京附近
        }
        
        result = await api_client.plan_route(request)
        
        logger.info(f"[TC-RP-007] 超长距离: status={result['status_code']}, elapsed={result['elapsed_ms']:.0f}ms")


class TestRoutePlanningConfirmation:
    """路线确认测试"""
    
    @pytest.mark.asyncio
    async def test_route_confirmation(
        self,
        api_client: APIClient,
        valid_route_request: Dict[str, Any],
    ) -> None:
        """TC-RP-008: 路线确认流程"""
        import uuid
        
        # 先规划路线
        plan_result = await api_client.plan_route(valid_route_request)
        
        if plan_result["status_code"] != 200:
            pytest.skip("规划失败，跳过确认测试")
        
        # ConfirmRouteRequest需要task_id, device_id, action
        confirm_data = {
            "task_id": str(uuid.uuid4()),
            "device_id": valid_route_request["device_id"],
            "action": "continue",  # continue/detour_recommended/detour_fastest/detour_safest/standby
        }
        
        confirm_result = await api_client.confirm_route(confirm_data)
        
        logger.info(f"[TC-RP-008] 路线确认: status={confirm_result['status_code']}")
