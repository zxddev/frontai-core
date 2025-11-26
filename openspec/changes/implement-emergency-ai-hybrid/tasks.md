# Tasks: 实现应急救灾AI+规则混合系统

## 1. 基础设施准备

- [ ] 1.1 确认vLLM服务可用，测试LLM连接（需要外部服务）
- [ ] 1.2 确认Neo4j服务可用，测试KG连接（需要外部服务）
- [ ] 1.3 确认Qdrant服务可用，测试向量检索（需要外部服务）
- [x] 1.4 安装pyyaml依赖（如未安装）

## 2. LLM工具封装

- [x] 2.1 创建 `src/agents/emergency_ai/tools/__init__.py`
- [x] 2.2 创建 `src/agents/emergency_ai/tools/llm_tools.py`
  - [x] 2.2.1 实现 `parse_disaster_description` 工具
  - [x] 2.2.2 实现 `reason_rescue_priority` 工具
  - [x] 2.2.3 实现 `explain_scheme` 工具
- [ ] 2.3 编写LLM工具单元测试（需要LLM服务）

## 3. RAG工具封装

- [x] 3.1 创建 `src/agents/emergency_ai/tools/rag_tools.py`
  - [x] 3.1.1 实现 `search_similar_cases` 工具
  - [ ] 3.1.2 实现 `search_best_practices` 工具（待补充）
- [x] 3.2 更新 `src/infra/clients/qdrant_client.py` 增加案例检索方法
- [ ] 3.3 编写RAG工具单元测试（需要Qdrant服务）

## 4. 知识图谱工具封装

- [x] 4.1 创建 `src/agents/emergency_ai/tools/kg_tools.py`
  - [x] 4.1.1 实现 `query_trr_rules` 工具
  - [x] 4.1.2 实现 `query_capability_mapping` 工具
  - [ ] 4.1.3 实现 `query_task_dependencies` 工具（待补充）
- [x] 4.2 更新 `src/infra/clients/neo4j_client.py` 增加规则查询方法
- [ ] 4.3 创建Neo4j知识图谱初始化脚本 `scripts/init_kg_rules.cypher`（待补充）
- [ ] 4.4 编写KG工具单元测试（需要Neo4j服务）

## 5. TRR规则引擎

- [x] 5.1 创建 `src/agents/rules/__init__.py`
- [x] 5.2 创建 `src/agents/rules/models.py` - 规则数据模型
  - [x] 5.2.1 定义 `TRRRule` Pydantic模型
  - [x] 5.2.2 定义 `MatchedRule` 结果模型
  - [x] 5.2.3 定义 `HardRule` 硬约束模型
- [x] 5.3 创建 `src/agents/rules/loader.py` - YAML加载器
  - [x] 5.3.1 实现 `load_trr_rules()` 函数
  - [x] 5.3.2 实现 `load_hard_rules()` 函数
- [x] 5.4 创建 `src/agents/rules/engine.py` - 规则引擎
  - [x] 5.4.1 实现 `TRRRuleEngine` 类
  - [x] 5.4.2 实现条件匹配逻辑（AND/OR）
  - [x] 5.4.3 实现规则优先级排序
- [x] 5.5 编写规则引擎单元测试

## 6. TRR规则库编写

- [x] 6.1 创建 `config/rules/` 目录
- [x] 6.2 创建 `config/rules/trr_emergency.yaml` - 应急TRR规则（合并地震等场景）
  - [x] 6.2.1 TRR-EQ-001: 建筑搜救规则
  - [x] 6.2.2 TRR-EQ-002: 火灾处置规则
  - [x] 6.2.3 TRR-EQ-003: 危化品泄漏规则
  - [x] 6.2.4 TRR-EQ-004: 伤员救治规则
  - [x] 6.2.5 TRR-EQ-005: 人员疏散规则
- [x] 6.3 规则文件包含次生灾害处理逻辑
  - [x] 6.3.1 TRR-SD-001: 余震应对规则
  - [x] 6.3.2 TRR-SD-002: 滑坡泥石流规则
  - [x] 6.3.3 TRR-SD-003: 堰塞湖规则
- [x] 6.4 创建 `config/rules/hard_rules.yaml` - 硬约束规则
  - [x] 6.4.1 HR-EM-001: 救援人员安全红线
  - [x] 6.4.2 HR-EM-002: 黄金救援时间
  - [x] 6.4.3 HR-EM-003: 关键能力覆盖
  - [x] 6.4.4 HR-EM-004: 资源可用性

## 7. EmergencyAIAgent核心模块

- [x] 7.1 创建 `src/agents/emergency_ai/__init__.py`
- [x] 7.2 创建 `src/agents/emergency_ai/state.py` - 状态定义
  - [x] 7.2.1 定义 `EmergencyAIState` TypedDict
  - [x] 7.2.2 定义状态字段注释
- [x] 7.3 创建 `src/agents/emergency_ai/nodes/__init__.py`
- [x] 7.4 创建 `src/agents/emergency_ai/nodes/understanding.py` - 灾情理解
  - [x] 7.4.1 实现 `understand_disaster()` 节点（LLM解析）
  - [x] 7.4.2 实现 `enhance_with_cases()` 节点（RAG增强）
- [x] 7.5 创建 `src/agents/emergency_ai/nodes/reasoning.py` - 规则推理
  - [x] 7.5.1 实现 `query_rules()` 节点（KG查询）
  - [x] 7.5.2 实现 `apply_rules()` 节点（规则引擎）
- [x] 7.6 创建 `src/agents/emergency_ai/nodes/matching.py` - 资源匹配
  - [x] 7.6.1 实现 `match_resources()` 节点（CSP求解）
  - [x] 7.6.2 实现 `optimize_allocation()` 节点（NSGA-II）
- [x] 7.7 创建 `src/agents/emergency_ai/nodes/optimization.py` - 方案优化
  - [x] 7.7.1 实现 `filter_hard_rules()` 节点
  - [x] 7.7.2 实现 `score_soft_rules()` 节点
  - [x] 7.7.3 实现 `explain_scheme()` 节点（LLM解释）
- [x] 7.8 创建 `src/agents/emergency_ai/nodes/output.py` - 输出格式化
  - [x] 7.8.1 实现 `generate_output()` 节点

## 8. LangGraph定义

- [x] 8.1 创建 `src/agents/emergency_ai/graph.py`
  - [x] 8.1.1 定义 `build_emergency_ai_graph()` 函数
  - [x] 8.1.2 添加所有节点到StateGraph
  - [x] 8.1.3 定义边和条件边
  - [x] 8.1.4 编译图
- [x] 8.2 创建 `src/agents/emergency_ai/agent.py`
  - [x] 8.2.1 实现 `EmergencyAIAgent` 类
  - [x] 8.2.2 实现 `analyze()` 方法
  - [x] 8.2.3 实现结果存储到 `ai_decision_logs_v2`

## 9. API端点扩展

- [x] 9.1 更新 `src/agents/schemas.py`
  - [x] 9.1.1 添加 `EmergencyAnalyzeRequest` 模型
  - [x] 9.1.2 添加 `EmergencyAnalyzeResponse` 模型
  - [x] 9.1.3 添加 `EmergencyAnalyzeTaskResponse` 模型
- [x] 9.2 更新 `src/agents/router.py`
  - [x] 9.2.1 添加 `POST /api/v2/ai/emergency-analyze` 端点
  - [x] 9.2.2 添加 `GET /api/v2/ai/emergency-analyze/{task_id}` 端点
  - [x] 9.2.3 添加后台任务处理函数

## 10. 集成测试

- [ ] 10.1 编写端到端测试用例（需要完整环境）
  - [ ] 10.1.1 地震建筑倒塌场景测试
  - [ ] 10.1.2 地震次生火灾场景测试
  - [ ] 10.1.3 地震危化品泄漏场景测试
- [ ] 10.2 验证LLM调用成功（需要LLM服务）
- [ ] 10.3 验证RAG检索成功（需要Qdrant服务）
- [ ] 10.4 验证KG查询成功（需要Neo4j服务）
- [x] 10.5 验证规则引擎匹配正确
- [x] 10.6 验证AI决策日志记录完整

## 11. 文档和清理

- [x] 11.1 更新 `src/agents/__init__.py` 导出新Agent
- [x] 11.2 确认所有代码使用强类型注解
- [x] 11.3 确认所有关键位置有日志输出
- [ ] 11.4 运行类型检查（mypy/pyright）
- [ ] 11.5 运行代码格式化（black/ruff）
