# Tasks: 扩展AI Agent模块 - 军事版架构实现

## Phase 1: 规则引擎和方案生成（P0，约5天）

### 1. TRR规则引擎

- [x] 1.1 创建 `config/rules/trr_emergency.yaml` - TRR触发规则库
  - 定义TRR-EM-001~TRR-EM-020（约20条核心规则）
  - 规则结构：trigger.conditions + actions
  - 参考：军事版TRR-001规则库设计

- [x] 1.2 创建 `config/rules/hard_rules.yaml` - 硬约束规则库
  - 定义HR-EM-001~HR-EM-010
  - 硬规则：一票否决检查条件

- [x] 1.3 创建 `src/agents/rules/__init__.py`
- [x] 1.4 创建 `src/agents/rules/models.py` - 规则数据模型
  - TRRRule, Condition, Action, MatchedRule
  - HardRule, HardRuleResult
  - 使用Pydantic v2 + 强类型

- [x] 1.5 创建 `src/agents/rules/loader.py` - YAML规则加载器
  - load_trr_rules(path) -> List[TRRRule]
  - load_hard_rules(path) -> List[HardRule]
  - 规则校验和错误报告

- [x] 1.6 创建 `src/agents/rules/engine.py` - TRRRuleEngine
  - evaluate(context) -> List[MatchedRule]
  - check_hard_rules(scheme) -> List[HardRuleResult]
  - 完整日志记录

### 2. SchemeGenerationAgent

- [x] 2.1 创建 `src/agents/scheme_generation/__init__.py`
- [x] 2.2 创建 `src/agents/scheme_generation/state.py` - SchemeGenerationState
  - TypedDict定义
  - 所有字段强类型注解

- [x] 2.3 创建 `src/agents/scheme_generation/nodes/__init__.py`
- [x] 2.4 创建 `src/agents/scheme_generation/nodes/rules.py`
  - apply_trr_rules(state) -> state更新
  - 调用TRRRuleEngine.evaluate()
  - 日志：匹配的规则数量和详情

- [x] 2.5 创建 `src/agents/scheme_generation/nodes/capabilities.py`
  - extract_capabilities(state) -> state更新
  - 调用CapabilityMappingProvider
  - 合并规则触发的能力需求

- [x] 2.6 创建 `src/agents/scheme_generation/nodes/matching.py`
  - match_resources(state) -> state更新
  - 调用RescueTeamSelector
  - 调用CapabilityMatcher（CSP求解）
  - 日志：候选资源数量、匹配得分

- [x] 2.7 创建 `src/agents/scheme_generation/nodes/arbitration.py`
  - arbitrate_scenes(state) -> state更新
  - 调用SceneArbitrator（多事件场景）
  - 调用ConflictResolver（资源冲突）

- [x] 2.8 创建 `src/agents/scheme_generation/nodes/optimization.py`
  - optimize_scheme(state) -> state更新
  - 调用PymooOptimizer（NSGA-II）
  - 日志：Pareto解数量、迭代次数

- [x] 2.9 创建 `src/agents/scheme_generation/nodes/filtering.py`
  - filter_hard_rules(state) -> state更新
  - 调用TRRRuleEngine.check_hard_rules()
  - score_soft_rules(state) -> state更新
  - 使用TOPSIS综合评分
  - 日志：被过滤方案数、最终排名

- [x] 2.10 创建 `src/agents/scheme_generation/nodes/output.py`
  - generate_output(state) -> state更新
  - 格式化方案JSON
  - 生成推荐理由（rationale）

- [x] 2.11 创建 `src/agents/scheme_generation/graph.py`
  - 定义StateGraph
  - 添加8个节点和边
  - 编译图

- [x] 2.12 创建 `src/agents/scheme_generation/agent.py`
  - SchemeGenerationAgent类
  - 继承BaseAgent
  - 实现prepare_input, process_output

### 3. API扩展 - Phase 1

- [x] 3.1 更新 `src/agents/schemas.py`
  - GenerateSchemeRequest, GenerateSchemeResponse
  - SchemeConstraints, GenerationOptions
  - SchemeResult, ResourceAllocationResult

- [x] 3.2 更新 `src/agents/router.py`
  - POST /ai/generate-scheme
  - GET /ai/generate-scheme/{task_id}
  - 异步执行 + BackgroundTasks

- [x] 3.3 更新 `src/agents/__init__.py`
  - 导出SchemeGenerationAgent

## Phase 2: 任务调度（P1，约3天）

### 4. TaskDispatchAgent

- [ ] 4.1 创建 `src/agents/task_dispatch/__init__.py`
- [ ] 4.2 创建 `src/agents/task_dispatch/state.py` - TaskDispatchState
  - TypedDict定义
  - 所有字段强类型注解

- [ ] 4.3 创建 `src/agents/task_dispatch/nodes/__init__.py`
- [ ] 4.4 创建 `src/agents/task_dispatch/nodes/decompose.py`
  - decompose_tasks(state) -> state更新
  - 方案→任务列表
  - 任务依赖关系生成

- [ ] 4.5 创建 `src/agents/task_dispatch/nodes/schedule.py`
  - schedule_tasks(state) -> state更新
  - 调用TaskScheduler
  - 关键路径分析

- [ ] 4.6 创建 `src/agents/task_dispatch/nodes/routing.py`
  - plan_routes(state) -> state更新
  - 调用VehicleRoutingPlanner
  - 调用RoadNetworkEngine / OffroadEngine
  - 日志：路径距离、预计时间

- [ ] 4.7 创建 `src/agents/task_dispatch/nodes/dispatch.py`
  - assign_executors(state) -> state更新
  - 为每个任务分配执行者
  - generate_dispatch_result(state) -> state更新
  - 格式化调度单JSON

- [ ] 4.8 创建 `src/agents/task_dispatch/graph.py`
  - 定义StateGraph
  - 添加4个节点和边
  - 编译图

- [ ] 4.9 创建 `src/agents/task_dispatch/agent.py`
  - TaskDispatchAgent类
  - 继承BaseAgent
  - 实现prepare_input, process_output

### 5. API扩展 - Phase 2

- [ ] 5.1 更新 `src/agents/schemas.py`
  - DispatchTasksRequest, DispatchTasksResponse
  - RoutingConfig
  - TaskResult, RouteResult, AssignmentResult

- [ ] 5.2 更新 `src/agents/router.py`
  - POST /ai/dispatch-tasks
  - GET /ai/dispatch-tasks/{task_id}

- [ ] 5.3 更新 `src/agents/__init__.py`
  - 导出TaskDispatchAgent

## Phase 3: 集成测试

- [x] 6.1 语法检查（py_compile所有新文件）
- [x] 6.2 规则引擎单元测试
  - 测试TRRRuleEngine.evaluate()
  - 测试TRRRuleEngine.check_hard_rules()

- [x] 6.3 SchemeGenerationAgent集成测试
  - 测试地震场景方案生成
  - 验证规则触发、资源匹配、优化结果

- [ ] 6.4 TaskDispatchAgent集成测试（依赖Phase 2完成）
  - 测试任务拆解和调度
  - 验证路径规划、执行者分配

- [x] 6.5 API端点测试（generate-scheme部分）
  - 测试 POST /ai/generate-scheme
  - [ ] 测试 POST /ai/dispatch-tasks（依赖Phase 2完成）
  - 验证异步执行和结果查询

- [x] 6.6 AI决策日志验证
  - 验证ai_decision_logs_v2记录完整
  - 验证schemes_v2.ai_reasoning字段

## 依赖关系

```
1.1~1.6 (规则引擎)
    ↓
2.1~2.12 (SchemeGenerationAgent)
    ↓
3.1~3.3 (API Phase 1)
    ↓
4.1~4.9 (TaskDispatchAgent)  ← 依赖SchemeGeneration输出
    ↓
5.1~5.3 (API Phase 2)
    ↓
6.1~6.6 (集成测试)
```

## 验收标准

| 任务 | 验收标准 |
|-----|---------|
| TRRRuleEngine | 地震场景触发TRR-EM-001规则 |
| SchemeGenerationAgent | 返回≥3个备选方案 |
| 硬规则过滤 | 危险方案被正确否决 |
| Pareto优化 | 返回非支配解集 |
| TaskDispatchAgent | 任务依赖关系正确 |
| 路径规划 | VRP解有效，路径可行 |
| API响应时间 | < 5秒 |
| 决策日志 | 追踪信息完整可查 |
