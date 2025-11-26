# Tasks: 集成P2功能

## Phase 1: 知识库检索集成

### T1.1 创建RAG客户端封装
- 创建 `src/domains/rescue_workflow/rag_client.py`
- 实现单例模式获取LlamaIndexRag
- 添加结果转换函数：(text, score, metadata) → ManualRecommendation

### T1.2 修改search_manuals
- 修改 `src/domains/rescue_workflow/service.py`
- 调用RAG客户端检索
- 转换结果为ManualRecommendation列表

### T1.3 修改get_manual_recommendations
- 修改 `src/domains/rescue_workflow/service.py`
- 根据event_id获取事件信息构造查询
- 调用RAG检索并返回推荐列表

## Phase 2: 路径规划集成

### T2.1 创建路径规划封装
- 创建 `src/domains/rescue_workflow/route_planner.py`
- 实现Location格式转换
- 封装VehicleRoutingPlanner调用

### T2.2 修改plan_route
- 修改 `src/domains/rescue_workflow/service.py`
- 转换RouteRequest为VRP输入格式
- 调用VehicleRoutingPlanner
- 转换结果为RouteResponse

## Phase 3: 测试验证

### T3.1 集成测试
- 测试search_manuals接口
- 测试get_manual_recommendations接口
- 测试plan_route接口
- 验证异常处理（RAG为空、规划失败）

## Dependencies

```
T1.1 → T1.2 → T1.3
T2.1 → T2.2
T1.3 + T2.2 → T3.1
```

## Estimated Time

- Phase 1: 2小时
- Phase 2: 2小时
- Phase 3: 1小时
- 总计: 5小时
