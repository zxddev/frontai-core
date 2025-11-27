# Tasks: 重构驻扎点选址为LangGraph Agent

## 复用说明

以下组件已实现，**直接复用不重写**：
- `DatabaseRouteEngine` (`src/planning/algorithms/routing/db_route_engine.py`) - A*路径规划
- `StagingAreaCore._validate_routes_batch()` - 批量路径验证
- `StagingAreaCore.recommend()` - 核心算法流程
- `DisasterAssessment` - 烈度评估
- `SecondaryHazardPredictor` - 次生灾害预测

## 1. Agent框架搭建

- [ ] 1.1 创建目录结构 `src/agents/staging_area/`
- [ ] 1.2 定义State类型 `state.py` (StagingAreaAgentState)
- [ ] 1.3 创建Agent入口 `agent.py` (StagingAreaAgent)
- [ ] 1.4 搭建Graph骨架 `graph.py` (build_staging_area_graph)

## 2. Tool封装（封装现有实现，不重写）

- [ ] 2.1 创建Tool目录 `tools/`
- [ ] 2.2 封装StagingAreaCore为Tool `staging_core_tool.py` (调用现有recommend方法)
- [ ] 2.3 封装地形数据查询 `terrain_tool.py` (调用repository)
- [ ] 2.4 封装通信数据查询 `communication_tool.py` (调用repository)
- [ ] 2.5 封装SecondaryHazardPredictor `hazard_tool.py` (调用现有predictor)

## 3. 分析节点实现

- [ ] 3.1 实现灾情理解节点 `nodes/understand.py`
  - 输入：自然语言灾情描述 + 结构化数据
  - 输出：提取的约束条件、关键信息
  - LLM：解析语义，识别特殊约束
  
- [ ] 3.2 实现地形分析节点 `nodes/terrain.py`
  - 输入：候选点列表、地形数据
  - 输出：地形适宜性评估
  - LLM：综合判断地形是否适合展开
  
- [ ] 3.3 实现通信分析节点 `nodes/communication.py`
  - 输入：候选点列表、通信覆盖数据
  - 输出：通信可行性评估
  - LLM：评估通信冗余方案
  
- [ ] 3.4 实现安全分析节点 `nodes/safety.py`
  - 输入：候选点列表、风险区域数据
  - 输出：安全等级评估、风险警示
  - LLM：综合判断安全风险

## 4. 核心节点实现

- [ ] 4.1 实现候选评估节点 `nodes/evaluate.py`
  - 调用StagingCoreTool执行算法
  - 整合各分析节点结果调整权重
  - 输出排序后的候选点列表
  
- [ ] 4.2 实现决策解释节点 `nodes/explain.py`
  - 输入：排序结果、各分析评估
  - 输出：推荐理由、风险警示、备选方案
  - LLM：生成可读性强的解释

## 5. Graph流程编排

- [ ] 5.1 实现Graph流程 `graph.py`
  - 入口：understand_disaster
  - 分析：terrain → communication → safety (可考虑并行)
  - 评估：evaluate_candidates
  - 输出：explain_decision
  
- [ ] 5.2 实现条件边判断函数
  - should_continue_after_understand
  - should_continue_after_analysis
  - should_explain
  
- [ ] 5.3 实现降级逻辑
  - LLM超时/失败时调用纯算法Service

## 6. API集成

- [ ] 6.1 创建Agent路由 `router.py`
- [ ] 6.2 定义请求/响应Schema
- [ ] 6.3 注册到 `src/agents/router.py`
- [ ] 6.4 注册到 `src/main.py`

## 7. 测试

- [ ] 7.1 创建节点单元测试 `tests/agents/staging_area/`
  - test_understand.py
  - test_terrain.py
  - test_communication.py
  - test_safety.py
  - test_evaluate.py
  - test_explain.py
  
- [ ] 7.2 创建Graph集成测试 `test_graph.py`
- [ ] 7.3 创建端到端测试 `scripts/test_staging_area_agent.py`
- [ ] 7.4 对比测试：Agent vs 纯算法Service

## 8. 文档与监控

- [ ] 8.1 更新OpenSpec规格
- [ ] 8.2 添加日志和监控点
- [ ] 8.3 记录降级事件

## Dependencies

- Task 1 必须先完成，其他任务依赖框架
- Task 2 (Tool封装) 可与 Task 3 并行
- Task 3.1 (understand) 必须先完成，其他分析节点依赖其输出
- Task 3.2-3.4 (分析节点) 可并行开发
- Task 4-5 依赖 Task 2-3
- Task 6-8 依赖 Task 5

## Parallelizable Work

- Tool封装 (2.2-2.5) 可并行
- 分析节点 (3.2-3.4) 可并行
- 单元测试 (7.1) 可与开发并行
