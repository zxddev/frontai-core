# Change: 实现应急救灾AI+规则混合系统

## Why

当前系统EventAnalysisAgent仅使用纯数学模型（灾情评估公式、规则评分），未真正集成LLM/RAG/知识图谱。

用户要求实现"AI+规则"混合架构，参考军事版文档（TO XIAOMA 20251124）的4阶段设计，应用于应急救灾场景（地震及次生灾害）。

现有问题：
1. **无LLM调用**：所有节点都是纯算法实现，无语义理解能力
2. **无RAG检索**：无历史案例检索，无法借鉴最佳实践
3. **无知识图谱推理**：规则硬编码在代码中，无法动态查询
4. **缺乏可解释性**：决策过程缺少自然语言解释

## What Changes

### ADDED

**AI混合Agent核心模块**
- `src/agents/emergency_ai/agent.py` - EmergencyAIAgent主类
- `src/agents/emergency_ai/graph.py` - LangGraph 1.0状态图定义
- `src/agents/emergency_ai/state.py` - EmergencyAIState强类型状态
- `src/agents/emergency_ai/nodes/` - 节点函数目录
  - `understanding.py` - LLM语义解析 + RAG案例增强
  - `reasoning.py` - KG规则查询 + 规则引擎推理
  - `matching.py` - CSP资源匹配 + NSGA-II优化
  - `optimization.py` - 硬/软规则过滤 + LLM方案解释
  - `output.py` - 输出格式化

**LLM工具封装**
- `src/agents/emergency_ai/tools/llm_tools.py` - LLM工具定义
  - `parse_disaster_description` - 解析灾情描述
  - `reason_rescue_priority` - 推理救援优先级
  - `explain_scheme` - 生成方案解释

**RAG工具封装**
- `src/agents/emergency_ai/tools/rag_tools.py` - RAG工具定义
  - `search_similar_cases` - 检索相似历史案例
  - `search_best_practices` - 检索最佳实践

**知识图谱工具封装**
- `src/agents/emergency_ai/tools/kg_tools.py` - KG工具定义
  - `query_trr_rules` - 查询TRR触发规则
  - `query_capability_mapping` - 查询能力-资源映射
  - `query_task_dependencies` - 查询任务依赖关系

**规则引擎扩展**
- `config/rules/trr_earthquake.yaml` - 地震TRR规则库
- `config/rules/trr_secondary.yaml` - 次生灾害TRR规则库
- `src/agents/rules/engine.py` - TRRRuleEngine规则引擎
- `src/agents/rules/loader.py` - YAML规则加载器
- `src/agents/rules/models.py` - 规则数据模型

**API端点**
- `POST /api/v2/ai/emergency-analyze` - AI混合分析
- `GET /api/v2/ai/emergency-analyze/{task_id}` - 查询分析结果

### MODIFIED

- `src/agents/router.py` - 添加新API端点
- `src/agents/schemas.py` - 添加请求/响应模型
- `src/infra/clients/llm_client.py` - 增强LLM工具绑定支持
- `src/infra/clients/neo4j_client.py` - 增加规则查询方法
- `src/infra/clients/qdrant_client.py` - 增加案例检索方法

## Impact

- **Affected specs**: 新增 `emergency-ai` capability
- **Affected code**:
  - 新增 `src/agents/emergency_ai/` 模块（~15个文件）
  - 新增 `src/agents/rules/` 模块（3个文件）
  - 新增 `config/rules/` 规则库（2个YAML文件）
  - 更新 `src/agents/router.py`、`schemas.py`
  - 更新 `src/infra/clients/` 客户端
- **Affected tables**: 使用现有表
  - `ai_decision_logs_v2` - 记录AI决策

## SQL Tables

**无需新增SQL** - 现有表结构已满足需求：
- `events_v2` - 事件信息
- `schemes_v2.ai_reasoning` - 存储AI推理说明
- `ai_decision_logs_v2` - 完整决策日志

## Dependencies

**现有依赖**：
- `langgraph>=1.0.0` - 状态图编排
- `langchain>=0.3.0` - LLM工具封装
- `langchain-openai>=0.2.0` - OpenAI兼容客户端
- `neo4j>=5.0` - 知识图谱查询
- `qdrant-client>=1.0` - 向量检索

**新增依赖**：
- `pyyaml>=6.0` - YAML规则加载

## Architecture Alignment

与TO XIAOMA军事版文档对应：

| 军事版阶段 | 应急版实现 | 核心技术 |
|-----------|-----------|---------|
| 目标深度解析（NLP） | DisasterUnderstandingNode | LLM + RAG |
| 规则推理（Rete） | RuleReasoningNode | KG + TRREngine |
| 能力-装备映射（CSP） | ResourceMatchingNode | CSP + NSGA-II |
| 杀伤链寻优（硬/软规则） | SchemeOptimizationNode | Rules + LLM解释 |

## References

- 军事版文档：`docs/TO XIAOMA 20251124(2).docx`
- LangGraph 1.0文档：https://github.com/langchain-ai/langgraph
- project.md技术栈定义
