# Change: 集成P2功能（知识库检索 + 路径规划）

## Why

rescue_workflow模块中有8个P2功能返回Mock数据或空列表，其中两个功能的基础设施已存在但未集成：

### 1. 知识库检索（search_manuals / get_manual_recommendations）
- **基础设施**：`src/infra/rag/llama_index_client.py` 已实现LlamaIndexRag
- **当前状态**：返回空列表 `[]`
- **影响**：用户无法获取操作手册推荐，影响救援指导

### 2. 路径规划（plan_route）
- **基础设施**：`src/planning/algorithms/routing/vehicle_routing.py` 已实现VehicleRoutingPlanner
- **当前状态**：返回Mock数据
- **影响**：无法提供实际路径规划，影响途中导航

**参考代码**:
- `src/domains/rescue_workflow/service.py` L311-330: search_manuals/get_manual_recommendations返回空
- `src/domains/rescue_workflow/service.py` L159-181: plan_route返回Mock
- `src/infra/rag/llama_index_client.py`: RAG实现
- `src/planning/algorithms/routing/vehicle_routing.py`: VRP实现

## What Changes

### MODIFIED

- **src/domains/rescue_workflow/service.py**
  - `get_manual_recommendations()` - 调用LlamaIndexRag检索相关手册
  - `search_manuals()` - 调用LlamaIndexRag检索
  - `plan_route()` - 调用VehicleRoutingPlanner计算路径

### ADDED

- **src/domains/rescue_workflow/rag_client.py**
  - `RagClientWrapper` - RAG客户端封装，单例模式
  - `get_rag_client()` - 获取RAG客户端实例

- **src/domains/rescue_workflow/route_planner.py**
  - `RoutePlannerWrapper` - 路径规划封装
  - `get_route_planner()` - 获取路径规划实例
  - 格式转换：rescue_workflow Location ↔ planning Location

## Constraints

1. **强类型Python** - 所有代码必须使用类型注解
2. **不降级/不Mock** - 检索为空或算法失败直接抛异常
3. **单例模式** - 避免每次请求都初始化客户端

## Dependencies

- `src/infra/settings.py` - Settings配置
- `src/infra/rag/llama_index_client.py` - LlamaIndexRag
- `src/planning/algorithms/routing/vehicle_routing.py` - VehicleRoutingPlanner

## Related Changes

- `harden-ai-agents` - AI模块加固（已完成）
- `implement-rescue-workflow` - rescue_workflow实现（已完成）
