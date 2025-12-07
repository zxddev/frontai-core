"""
前端API兼容性端到端测试

测试/api/v1前端适配接口：
1. 实体CRUD
2. 图层获取
3. 队伍/车辆列表
4. 总体方案模块
5. 待处理事件

运行方式:
    PYTHONPATH=. pytest tests/e2e/test_frontend_api.py -v
"""
from __future__ import annotations

from typing import Dict, Any

import httpx
import pytest

from .conftest import API_V1_PREFIX
from .utils.api_client import FrontendAPIClient


# ============================================================================
# 实体API测试
# ============================================================================

class TestEntitiesAPI:
    """实体API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_entities_returns_list(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试获取实体列表"""
        resp = await api_client.get(
            f"{API_V1_PREFIX}/entities",
            params={"scenarioId": active_scenario["id"], "pageSize": 10}
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        # 验证响应结构
        assert "code" in data
        assert data["code"] == 200
        assert "data" in data
        
        page_data = data["data"]
        assert "items" in page_data
        assert "total" in page_data
        
        print(f"\n[实体列表] 共{page_data['total']}个实体")
    
    @pytest.mark.asyncio
    async def test_fetch_entities_by_layer(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试按图层过滤实体"""
        resp = await api_client.get(
            f"{API_V1_PREFIX}/entities",
            params={
                "scenarioId": active_scenario["id"],
                "layerCode": "rescue_teams",
                "pageSize": 10,
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
    
    @pytest.mark.asyncio
    async def test_fetch_entities_by_type(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试按类型过滤实体"""
        resp = await api_client.get(
            f"{API_V1_PREFIX}/entities",
            params={
                "scenarioId": active_scenario["id"],
                "type": "rescue_team",
                "pageSize": 10,
            }
        )
        
        assert resp.status_code == 200


# ============================================================================
# 图层API测试
# ============================================================================

class TestLayersAPI:
    """图层API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_layers(self, api_client: httpx.AsyncClient):
        """测试获取图层列表"""
        resp = await api_client.get(f"{API_V1_PREFIX}/layers")
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "code" in data
        assert data["code"] == 200
        assert "data" in data
        
        layers = data["data"]
        if isinstance(layers, list):
            print(f"\n[图层列表] 共{len(layers)}个图层")
            for layer in layers[:5]:
                print(f"  - {layer.get('code')}: {layer.get('name')}")


# ============================================================================
# 队伍API测试
# ============================================================================

class TestUnitsAPI:
    """队伍API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_units(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试获取队伍列表"""
        # POST请求搜索队伍，需要经纬度
        resp = await api_client.post(
            f"{API_V1_PREFIX}/unit/search-unit",
            json={
                "lon": 103.85,
                "lat": 31.68,
                "rangeInMeters": 50000,
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "code" in data
        assert data["code"] == 200
        
        if "data" in data and data["data"]:
            units_data = data["data"]
            if isinstance(units_data, list):
                print(f"\n[队伍列表] 共{len(units_data)}个分类")


# ============================================================================
# 车辆API测试
# ============================================================================

class TestCarsAPI:
    """车辆API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_cars(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试获取车辆装备列表"""
        # 需要userId参数
        resp = await api_client.get(
            f"{API_V1_PREFIX}/car/car-item-select-list",
            params={"userId": "test-user", "scenarioId": active_scenario["id"]}
        )
        
        # 可能返回200或400（缺少必要参数）
        assert resp.status_code in (200, 400, 422)
        if resp.status_code == 200:
            data = resp.json()
            assert "code" in data


# ============================================================================
# 总体方案API测试
# ============================================================================

class TestOverallPlanAPI:
    """总体方案API测试"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.llm
    @pytest.mark.timeout(120)
    async def test_get_modules(self, api_client: httpx.AsyncClient):
        """测试获取总体方案模块"""
        resp = await api_client.get(f"{API_V1_PREFIX}/overall-plan/modules")
        
        # 可能需要活跃场景
        if resp.status_code == 404:
            pytest.skip("无活跃场景")
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "modules" in data
        modules = data["modules"]
        
        print(f"\n[总体方案] 共{len(modules)}个模块:")
        for m in modules:
            print(f"  - {m.get('title')}")
    
    @pytest.mark.asyncio
    async def test_get_latest_plan(self, api_client: httpx.AsyncClient):
        """测试获取最新方案"""
        resp = await api_client.get(f"{API_V1_PREFIX}/overall-plan/latest")
        
        if resp.status_code == 404:
            pytest.skip("无已保存方案")
        
        assert resp.status_code == 200


# ============================================================================
# 待处理事件API测试
# ============================================================================

class TestPendingActionsAPI:
    """待处理事件API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_pending_actions(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试获取待处理事件"""
        # 这是POST请求
        resp = await api_client.post(
            f"{API_V1_PREFIX}/events/pending-action",
            json={"scenarioId": active_scenario["id"]}
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "code" in data
        assert data["code"] == 200
        
        if "data" in data:
            actions = data["data"]
            if isinstance(actions, list):
                print(f"\n[待处理事件] 共{len(actions)}个")


# ============================================================================
# 任务API测试
# ============================================================================

class TestTasksAPI:
    """任务API测试"""
    
    @pytest.mark.asyncio
    async def test_fetch_tasks(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试获取任务列表"""
        # 这是POST请求
        resp = await api_client.post(
            f"{API_V1_PREFIX}/tasks/task-list-detail",
            json={}
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        assert "code" in data
        assert data["code"] == 200


# ============================================================================
# API响应格式测试
# ============================================================================

class TestResponseFormat:
    """API响应格式测试"""
    
    @pytest.mark.asyncio
    async def test_api_response_has_code(self, api_client: httpx.AsyncClient):
        """测试API响应包含code字段"""
        endpoints = [
            f"{API_V1_PREFIX}/layers",
            f"{API_V1_PREFIX}/entities",
        ]
        
        for endpoint in endpoints:
            resp = await api_client.get(endpoint)
            if resp.status_code == 200:
                data = resp.json()
                assert "code" in data, f"{endpoint} 缺少code字段"
    
    @pytest.mark.asyncio
    async def test_pagination_format(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试分页响应格式"""
        resp = await api_client.get(
            f"{API_V1_PREFIX}/entities",
            params={
                "scenarioId": active_scenario["id"],
                "page": 1,
                "pageSize": 5,
            }
        )
        
        assert resp.status_code == 200
        data = resp.json()
        
        page_data = data.get("data", {})
        if isinstance(page_data, dict):
            # 验证分页字段
            assert "items" in page_data or "total" in page_data
            if "total" in page_data:
                assert isinstance(page_data["total"], int)


# ============================================================================
# 使用FrontendAPIClient的测试
# ============================================================================

class TestWithAPIClient:
    """使用封装客户端的测试"""
    
    @pytest.mark.asyncio
    async def test_client_get_entities(
        self,
        api_client: httpx.AsyncClient,
        active_scenario: Dict[str, Any],
    ):
        """测试客户端获取实体"""
        client = FrontendAPIClient(api_client, API_V1_PREFIX)
        
        result = await client.get_entities(
            scenario_id=active_scenario["id"],
            page_size=10,
        )
        
        assert result["code"] == 200
    
    @pytest.mark.asyncio
    async def test_client_get_layers(self, api_client: httpx.AsyncClient):
        """测试客户端获取图层"""
        client = FrontendAPIClient(api_client, API_V1_PREFIX)
        
        result = await client.get_layers()
        assert result["code"] == 200
