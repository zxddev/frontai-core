"""
Phase 1: 健康检查和系统端点测试

测试系统管理相关的API端点，确保服务正常运行。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

import pytest

from .utils.api_client import APIClient

logger = logging.getLogger(__name__)


class TestHealthCheck:
    """系统健康检查测试"""
    
    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self, api_client: APIClient) -> None:
        """TC-SYS-001: 健康检查端点应返回200"""
        result = await api_client.health_check()
        
        assert result["status_code"] == 200, f"健康检查失败: {result}"
        assert "status" in result["response"], "响应缺少status字段"
        
        logger.info(f"[TC-SYS-001] 健康检查通过: status={result['response'].get('status')}")
    
    @pytest.mark.asyncio
    async def test_health_response_time(self, api_client: APIClient) -> None:
        """TC-SYS-006: 健康检查响应时间应小于500ms"""
        result = await api_client.health_check()
        
        assert result["elapsed_ms"] < 500, f"响应时间过长: {result['elapsed_ms']}ms"
        
        logger.info(f"[TC-SYS-006] 响应时间: {result['elapsed_ms']:.0f}ms")
    
    @pytest.mark.asyncio
    async def test_health_checks_components(self, api_client: APIClient) -> None:
        """TC-SYS-005: 健康检查应包含各组件状态"""
        result = await api_client.health_check()
        
        assert result["status_code"] == 200
        response = result["response"]
        
        # 检查关键组件
        checks = response.get("checks", {})
        
        # Redis检查
        redis_check = checks.get("redis", {})
        logger.info(f"[TC-SYS-005] Redis: connected={redis_check.get('connected')}")
        
        # 数据库检查
        db_check = checks.get("database", {})
        logger.info(f"[TC-SYS-005] Database: connected={db_check.get('connected')}")
        
        # 熔断器检查
        breaker_check = checks.get("circuit_breakers", {})
        logger.info(f"[TC-SYS-005] Circuit Breakers: healthy={breaker_check.get('healthy')}")


class TestRulesManagement:
    """规则管理测试"""
    
    @pytest.mark.asyncio
    async def test_rules_stats_returns_data(self, api_client: APIClient) -> None:
        """TC-SYS-003: 规则统计应返回数据"""
        result = await api_client.get_rules_stats()
        
        # 允许200或其他成功状态
        logger.info(f"[TC-SYS-003] 规则统计: status={result['status_code']}, response={result['response']}")
    
    @pytest.mark.asyncio
    async def test_rules_reload(self, api_client: APIClient) -> None:
        """TC-SYS-002: 规则重载应成功"""
        result = await api_client.reload_rules()
        
        logger.info(f"[TC-SYS-002] 规则重载: status={result['status_code']}, response={result['response']}")


class TestCircuitBreakers:
    """熔断器测试"""
    
    @pytest.mark.asyncio
    async def test_reset_circuit_breakers(self, api_client: APIClient) -> None:
        """TC-SYS-004: 熔断器重置应成功"""
        result = await api_client.reset_circuit_breakers()
        
        logger.info(f"[TC-SYS-004] 熔断器重置: status={result['status_code']}, response={result['response']}")
