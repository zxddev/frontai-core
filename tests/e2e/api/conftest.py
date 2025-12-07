"""
API端到端测试共享Fixtures

提供测试客户端、测试数据和公共配置。
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, Generator

import pytest
import pytest_asyncio

from .utils.api_client import APIClient

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def api_client() -> APIClient:
    """提供API客户端实例"""
    async with APIClient() as client:
        yield client


@pytest.fixture
def unique_event_id() -> str:
    """生成唯一事件ID (UUID格式)"""
    return str(uuid.uuid4())


@pytest.fixture
def unique_scenario_id() -> str:
    """生成唯一场景ID (UUID格式)"""
    return str(uuid.uuid4())


@pytest.fixture
def small_area_geojson() -> Dict[str, Any]:
    """小区域GeoJSON (约1km x 1km)"""
    return {
        "type": "Polygon",
        "coordinates": [[[103.85, 31.65], [103.86, 31.65], [103.86, 31.66], [103.85, 31.66], [103.85, 31.65]]]
    }


@pytest.fixture
def large_area_geojson() -> Dict[str, Any]:
    """大区域GeoJSON (约11km x 11km)"""
    return {
        "type": "Polygon",
        "coordinates": [[[103.8, 31.6], [103.9, 31.6], [103.9, 31.7], [103.8, 31.7], [103.8, 31.6]]]
    }


@pytest.fixture
def invalid_geojson() -> Dict[str, Any]:
    """无效GeoJSON"""
    return {
        "type": "InvalidType",
        "coordinates": "not-an-array"
    }


@pytest.fixture
def valid_emergency_request(unique_event_id: str, unique_scenario_id: str) -> Dict[str, Any]:
    """有效的应急分析请求"""
    return {
        "event_id": unique_event_id,
        "scenario_id": unique_scenario_id,
        "disaster_description": "四川省阿坝州茂县发生里氏6.5级地震，震源深度10公里，多栋建筑倒塌，疑似有人员被困。",
        "disaster_type": "earthquake",
        "priority": "high",
    }


@pytest.fixture
def valid_recon_request(unique_event_id: str, unique_scenario_id: str, small_area_geojson: Dict[str, Any]) -> Dict[str, Any]:
    """有效的侦察调度请求"""
    return {
        "event_id": unique_event_id,
        "scenario_id": unique_scenario_id,
        "recon_request": "对地震灾区进行全面侦察，搜索被困人员，评估建筑损毁情况",
        "target_area": small_area_geojson,
        "disaster_context": {
            "disaster_type": "earthquake",
            "severity": "moderate",
        }
    }


@pytest.fixture
def valid_route_request() -> Dict[str, Any]:
    """有效的路由规划请求（符合RoutePlanRequest schema）"""
    return {
        "device_id": "91f271d0-c797-4eb1-93ff-c729aaa75f03",  # 绝影X30工业巡检机器狗
        "origin": {"lon": 104.0668, "lat": 30.5728},          # 成都坐标
        "destination": {"lon": 103.85, "lat": 31.68},         # 阿坝坐标
    }


# 问题追踪
class IssueTracker:
    """测试问题追踪器"""
    
    def __init__(self) -> None:
        self.issues: list[Dict[str, Any]] = []
    
    def add_issue(
        self,
        endpoint: str,
        description: str,
        severity: str,
        details: Dict[str, Any],
    ) -> None:
        issue = {
            "id": f"ISSUE-{len(self.issues) + 1:03d}",
            "endpoint": endpoint,
            "description": description,
            "severity": severity,  # critical, major, minor, trivial
            "details": details,
            "status": "open",
        }
        self.issues.append(issue)
        logger.error(f"[ISSUE] {issue['id']}: {endpoint} - {description} ({severity})")
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total": len(self.issues),
            "critical": len([i for i in self.issues if i["severity"] == "critical"]),
            "major": len([i for i in self.issues if i["severity"] == "major"]),
            "minor": len([i for i in self.issues if i["severity"] == "minor"]),
            "issues": self.issues,
        }


@pytest.fixture(scope="session")
def issue_tracker() -> IssueTracker:
    """会话级别的问题追踪器"""
    return IssueTracker()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """测试会话结束时输出问题汇总"""
    logger.info("=" * 60)
    logger.info("API E2E TEST COMPLETED")
    logger.info("=" * 60)
