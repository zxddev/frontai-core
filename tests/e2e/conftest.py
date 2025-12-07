"""
E2E测试配置和fixtures

提供测试所需的HTTP客户端、数据库会话、测试数据等。

运行方式:
    PYTHONPATH=. pytest tests/e2e/ -v
    TEST_API_URL=http://192.168.31.50:8000 pytest tests/e2e/ -v
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# 加载.env文件
from dotenv import load_dotenv
load_dotenv()

# 测试配置
BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/emergency_brain")
)

# API路径前缀
API_V2_PREFIX = "/api/v2"
API_V1_PREFIX = "/api/v1"
AI_PREFIX = f"{API_V2_PREFIX}/ai"


# ============================================================================
# pytest配置
# ============================================================================

def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line("markers", "slow: 标记慢速测试")
    config.addinivalue_line("markers", "llm: 需要LLM服务的测试")
    config.addinivalue_line("markers", "db: 需要数据库的测试")


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环（session级别）"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# HTTP客户端fixtures
# ============================================================================

@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """异步HTTP客户端"""
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=httpx.Timeout(60.0, connect=10.0),
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def ai_client(api_client: httpx.AsyncClient) -> httpx.AsyncClient:
    """AI接口专用客户端（已配置超时）"""
    return api_client


# ============================================================================
# 数据库fixtures
# ============================================================================

@pytest_asyncio.fixture
async def db_engine():
    """数据库引擎"""
    engine = create_async_engine(DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """数据库会话"""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ============================================================================
# 测试数据fixtures
# ============================================================================

@pytest_asyncio.fixture
async def active_scenario(db_session: AsyncSession) -> Dict[str, Any]:
    """获取或创建活跃场景"""
    result = await db_session.execute(
        text("SELECT id, name FROM operational_v2.scenarios_v2 WHERE status = 'active' LIMIT 1")
    )
    row = result.fetchone()
    
    if row:
        return {"id": str(row[0]), "name": row[1]}
    
    # 创建测试场景
    scenario_id = str(uuid.uuid4())
    await db_session.execute(
        text("""
            INSERT INTO operational_v2.scenarios_v2 (id, name, scenario_type, status, created_at)
            VALUES (:id, :name, :type, 'active', NOW())
        """),
        {"id": scenario_id, "name": "E2E测试场景", "type": "earthquake"}
    )
    await db_session.commit()
    
    return {"id": scenario_id, "name": "E2E测试场景"}


@pytest_asyncio.fixture
async def test_event(
    api_client: httpx.AsyncClient,
    active_scenario: Dict[str, Any],
) -> Dict[str, Any]:
    """创建测试事件"""
    event_data = {
        "scenario_id": active_scenario["id"],
        "title": f"E2E测试事件-{datetime.now().strftime('%H%M%S')}",
        "description": "端到端测试用地震事件，某建筑发生倒塌，有人员被困",
        "event_type": "earthquake",
        "priority": "high",
        "status": "confirmed",
        "location": {"lng": 103.85, "lat": 31.68},
        "source": "manual",
    }
    
    resp = await api_client.post(f"{API_V2_PREFIX}/events", json=event_data)
    
    if resp.status_code in [200, 201]:
        event = resp.json()
        return {
            "id": event.get("id"),
            "scenario_id": active_scenario["id"],
            **event_data,
        }
    
    # 如果创建失败，尝试获取现有事件
    resp = await api_client.get(
        f"{API_V2_PREFIX}/events",
        params={"scenario_id": active_scenario["id"], "status": "confirmed"}
    )
    if resp.status_code == 200:
        events = resp.json()
        if isinstance(events, dict):
            events = events.get("items", [])
        if events:
            return events[0]
    
    pytest.skip("无法创建或获取测试事件")


@pytest_asyncio.fixture
async def earthquake_input() -> Dict[str, Any]:
    """地震场景输入数据"""
    return {
        "disaster_description": "四川省成都市发生5.5级地震，某商业综合体发生部分坍塌，预计有20人被困，存在次生火灾风险",
        "structured_input": {
            "disaster_type": "earthquake",
            "magnitude": 5.5,
            "depth_km": 10,
            "location": {"longitude": 104.0657, "latitude": 30.5728},
            "estimated_trapped": 20,
            "has_building_collapse": True,
            "has_secondary_fire": True,
            "building_type": "commercial",
            "time_of_day": "daytime",
        },
        "constraints": {
            "max_response_time_minutes": 30,
            "max_teams": 10,
        },
    }


@pytest_asyncio.fixture
async def fire_input() -> Dict[str, Any]:
    """火灾场景输入数据"""
    return {
        "disaster_description": "某化工厂仓库发生火灾，火势蔓延迅速，现场有危险化学品存储，需要紧急处置",
        "structured_input": {
            "disaster_type": "fire",
            "fire_type": "industrial",
            "location": {"longitude": 104.12, "latitude": 30.65},
            "has_hazmat": True,
            "hazmat_type": "flammable_liquid",
            "building_type": "industrial",
            "estimated_affected_area_m2": 5000,
        },
        "constraints": {
            "max_response_time_minutes": 15,
        },
    }


# ============================================================================
# 工具函数
# ============================================================================

async def poll_task_result(
    client: httpx.AsyncClient,
    task_id: str,
    endpoint: str = "emergency-analyze",
    max_wait: int = 60,
    interval: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """
    轮询任务结果
    
    Args:
        client: HTTP客户端
        task_id: 任务ID
        endpoint: API端点
        max_wait: 最大等待时间(秒)
        interval: 轮询间隔(秒)
        
    Returns:
        任务结果或None
    """
    import time
    start = time.time()
    
    while time.time() - start < max_wait:
        resp = await client.get(f"{AI_PREFIX}/{endpoint}/{task_id}")
        
        if resp.status_code == 200:
            result = resp.json()
            status = result.get("status", "")
            
            if status == "completed":
                return result
            elif status == "failed":
                return result
            elif status == "interrupted":
                return result
        
        await asyncio.sleep(interval)
    
    return None


async def wait_for_analysis(
    client: httpx.AsyncClient,
    event_id: str,
    max_wait: int = 60,
) -> Optional[Dict[str, Any]]:
    """等待事件分析完成"""
    task_id = f"emergency-{event_id}"
    return await poll_task_result(client, task_id, max_wait=max_wait)


# ============================================================================
# ReconScheduler fixtures
# ============================================================================

@pytest_asyncio.fixture
async def recon_client(api_client: httpx.AsyncClient):
    """ReconScheduler API客户端"""
    from .utils.recon_client import ReconSchedulerClient
    return ReconSchedulerClient(api_client, AI_PREFIX)


@pytest.fixture
def sample_recon_target_area() -> Dict[str, Any]:
    """标准侦察目标区域"""
    return {
        "type": "Polygon",
        "coordinates": [[[103.8, 31.6], [103.9, 31.6], [103.9, 31.7], [103.8, 31.7], [103.8, 31.6]]]
    }


# 导出工具函数供测试使用
__all__ = [
    "BASE_URL",
    "API_V2_PREFIX",
    "API_V1_PREFIX",
    "AI_PREFIX",
    "poll_task_result",
    "wait_for_analysis",
]
