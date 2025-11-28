# Tasks: 重构驻扎点选址为LangGraph Agent

## 复用说明

以下组件已实现，**直接复用不重写**：
- `DatabaseRouteEngine` (`src/planning/algorithms/routing/db_route_engine.py`) - A*路径规划
- `StagingAreaCore._validate_routes_batch()` - 批量路径验证
- `StagingAreaCore.recommend()` - 核心算法流程
- `DisasterAssessment` - 烈度评估
- `SecondaryHazardPredictor` - 次生灾害预测

## 0. Core层重构（前置，遵循调用规范）

- [x] 0.1 重构 `StagingAreaCore.__init__` 接收Repository而非db
- [x] 0.2 调整内部方法使用 `self._repo` 获取数据
- [x] 0.3 更新Service层实例化方式
- [x] 0.4 更新Router层调用Service

## 1. Agent框架搭建

- [x] 1.1 创建目录结构 `src/agents/staging_area/`
- [x] 1.2 定义State类型 `state.py` (StagingAreaAgentState)
- [x] 1.3 创建Agent入口 `agent.py` (StagingAreaAgent)
- [x] 1.4 搭建Graph骨架 `graph.py` (build_staging_area_graph)

## 2. Tool封装（通过Service调用复用现有实现）

- [x] 2.1 创建Tool目录 `tools/`
- [x] 2.2 评估节点直接调用StagingAreaService (无需单独Tool)
- [x] 2.3-2.5 暂不需要单独Tool，通过Service调用

## 3. 分析节点实现

- [x] 3.1 实现灾情理解节点 `nodes/understand.py`
  - 输入：自然语言灾情描述 + 结构化数据
  - 输出：提取的约束条件、关键信息
  - LLM：解析语义，识别特殊约束
  
- [x] 3.2 实现地形分析节点 `nodes/terrain.py`
  - 输入：候选点列表、地形数据
  - 输出：地形适宜性评估
  - LLM：综合判断地形是否适合展开
  
- [x] 3.3 实现通信分析节点 `nodes/communication.py`
  - 输入：候选点列表、通信覆盖数据
  - 输出：通信可行性评估
  - LLM：评估通信冗余方案
  
- [x] 3.4 实现安全分析节点 `nodes/safety.py`
  - 输入：候选点列表、风险区域数据
  - 输出：安全等级评估、风险警示
  - LLM：综合判断安全风险

## 4. 核心节点实现

- [x] 4.1 实现候选评估节点 `nodes/evaluate.py`
  - 调用StagingAreaService执行算法
  - 整合各分析节点结果调整权重（动态权重）
  - 输出排序后的候选点列表
  
- [x] 4.2 实现决策解释节点 `nodes/explain.py`
  - 输入：排序结果、各分析评估
  - 输出：推荐理由、风险警示、备选方案
  - LLM：生成可读性强的解释

## 5. Graph流程编排

- [x] 5.1 实现Graph流程 `graph.py`
  - 入口：understand_disaster
  - 分析：terrain | communication | safety (并行执行)
  - 评估：evaluate_candidates
  - 输出：explain_decision
  
- [x] 5.2 实现条件边判断函数
  - route_after_understand（支持并行分发）
  - should_continue_after_evaluate
  
- [x] 5.3 实现降级逻辑
  - skip_llm_analysis=True跳过分析节点
  - 单节点失败时捕获异常继续

## 6. API集成

- [x] 6.1 创建Agent路由 `router.py`
- [x] 6.2 定义请求/响应Schema
- [x] 6.3 注册到 `src/agents/router.py`
- [x] 6.4 导出到 `src/agents/__init__.py`

## 7. 测试

- [ ] 7.1 创建节点单元测试 `tests/agents/staging_area/`
  - test_understand.py
  - test_terrain.py
  - test_communication.py
  - test_safety.py
  - test_evaluate.py
  - test_explain.py
  
- [ ] 7.2 创建Graph集成测试 `test_graph.py`
- [x] 7.3 创建端到端测试 `scripts/test_staging_area_agent.py`
- [ ] 7.4 对比测试：Agent vs 纯算法Service

## 8. 文档与监控

- [x] 8.1 更新架构文档 `docs/智能体规划/驻扎点选址智能体架构设计.md`
- [x] 8.2 添加日志和监控点
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
