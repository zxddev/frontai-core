# Design: 集成P2功能

## 1. 知识库检索设计

### 1.1 架构

```
ManualSearchRequest
        │
        ▼
RescueWorkflowService.search_manuals()
        │
        ▼
RagClientWrapper.search()
        │
        ▼
LlamaIndexRag.similarity_search()
        │
        ▼
Qdrant向量检索
        │
        ▼
List[ManualRecommendation]
```

### 1.2 RAG客户端封装

```python
# src/domains/rescue_workflow/rag_client.py

from typing import List, Optional
from uuid import uuid4

from src.infra.settings import load_settings
from src.infra.rag.llama_index_client import LlamaIndexRag
from .schemas import ManualRecommendation

_rag_client: Optional[LlamaIndexRag] = None

def get_rag_client() -> LlamaIndexRag:
    """获取RAG客户端单例"""
    global _rag_client
    if _rag_client is None:
        settings = load_settings()
        _rag_client = LlamaIndexRag(settings)
    return _rag_client

def search_manuals_rag(query: str, limit: int = 10) -> List[ManualRecommendation]:
    """调用RAG检索并转换结果"""
    client = get_rag_client()
    results = client.similarity_search(query)  # 检索为空会抛异常
    
    recommendations: List[ManualRecommendation] = []
    for text, score, metadata in results[:limit]:
        rec = ManualRecommendation(
            manual_id=metadata.get("manual_id", uuid4()),
            title=metadata.get("title", "未知手册"),
            relevance_score=score,
            matched_keywords=metadata.get("keywords", []),
            summary=text[:500],  # 截取前500字符作为摘要
        )
        recommendations.append(rec)
    
    return recommendations
```

### 1.3 Qdrant数据结构假设

payload应包含：
- `manual_id`: UUID - 手册ID
- `title`: str - 手册标题
- `text`: str - 手册内容
- `keywords`: List[str] - 关键词
- `disaster_type`: str - 关联灾害类型

## 2. 路径规划设计

### 2.1 架构

```
RouteRequest
        │
        ▼
RescueWorkflowService.plan_route()
        │
        ▼
RoutePlannerWrapper.plan()
        │
        ▼
VehicleRoutingPlanner.run()
        │
        ▼
RouteResponse
```

### 2.2 Location格式转换

```python
# rescue_workflow: Location(longitude=x, latitude=y)
# planning:        Location(lat=y, lng=x)

def workflow_to_planning(loc: WorkflowLocation) -> PlanningLocation:
    return PlanningLocation(lat=loc.latitude, lng=loc.longitude)

def planning_to_workflow(loc: PlanningLocation) -> WorkflowLocation:
    return WorkflowLocation(longitude=loc.lng, latitude=loc.lat)
```

### 2.3 VRP输入构造

plan_route是单车辆、单起终点的简化场景：

```python
vrp_input = {
    "depots": [{
        "id": "origin",
        "location": {"lat": origin.latitude, "lng": origin.longitude},
        "name": "起点"
    }],
    "tasks": [{
        "id": "destination",
        "location": {"lat": dest.latitude, "lng": dest.longitude},
        "demand": 1,
        "service_time_min": 0
    }],
    "vehicles": [{
        "id": str(vehicle_id),
        "name": "救援车辆",
        "depot_id": "origin",
        "capacity": 10,
        "max_distance_km": 500,
        "max_time_min": 600,
        "speed_kmh": 40
    }],
    "constraints": {
        "time_limit_sec": 10
    }
}
```

### 2.4 RouteResponse构造

VehicleRoutingPlanner返回的solution包含stops列表，需要转换为segments：

```python
# VRP返回
solution = [{
    "vehicle_id": "...",
    "stops": [{"task_id": "destination", "location": (lat, lng)}],
    "total_distance_km": 5.2,
    "total_time_min": 13
}]

# 转换为RouteResponse
RouteResponse(
    route_id=uuid4(),
    event_id=request.event_id,
    vehicle_id=request.vehicle_id,
    total_distance_meters=solution[0]["total_distance_km"] * 1000,
    total_duration_seconds=solution[0]["total_time_min"] * 60,
    segments=[RouteSegment(
        start_point=request.origin,
        end_point=request.destination,
        distance_meters=solution[0]["total_distance_km"] * 1000,
        duration_seconds=solution[0]["total_time_min"] * 60,
        road_name=None,  # VRP不提供详细路名
        risk_level=RiskLevel.low,
        instructions="沿路线行驶"
    )],
    risk_areas=[],
    alternative_routes=None
)
```

## 3. 异常处理

### 3.1 RAG异常

LlamaIndexRag.similarity_search()检索为空时抛出RuntimeError，不降级。

### 3.2 VRP异常

VehicleRoutingPlanner.run()返回AlgorithmResult，检查status：
- SUCCESS: 正常返回
- PARTIAL/INFEASIBLE/ERROR: 抛出异常

## 4. 配置依赖

### 4.1 RAG配置（Settings）

```yaml
# config/private.yaml
EMBEDDING_BASE_URL: http://localhost:8001/v1
EMBEDDING_MODEL: text-embedding-3-small
QDRANT_URL: http://localhost:6333
QDRANT_COLLECTION: emergency_manuals
RAG_TOP_K: 4
```

### 4.2 VRP配置

无外部依赖，OR-Tools为本地计算。
