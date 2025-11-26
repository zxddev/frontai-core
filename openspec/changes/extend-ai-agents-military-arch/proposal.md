# Change: 扩展AI Agent模块 - 军事版架构实现

## Why

当前系统已实现EventAnalysisAgent（第一阶段），但缺少完整的AI决策链路：

1. **缺少规则引擎**：无法基于业务规则自动触发任务和能力需求
2. **缺少方案生成**：无法自动生成救援方案（军事版核心能力）
3. **缺少任务调度**：无法将方案分解为可执行任务并规划路径
4. **缺少多目标优化**：无法在多个可行方案中选择最优解

参考军事版文档（TO XIAOMA 20251124）的4阶段架构：
- 作战任务分解 → EventAnalysis + TRRRuleEngine
- 能力需求评估 → CapabilityExtraction
- 能力-装备映射 → ResourceMatching
- 杀伤链寻优 → SchemeOptimization + TaskDispatch

## What Changes

### ADDED

**规则引擎层**
- `config/rules/trr_emergency.yaml` - TRR触发规则库（~50条规则）
- `config/rules/hard_rules.yaml` - 硬约束规则库（HR-001~HR-010）
- `src/agents/rules/engine.py` - TRRRuleEngine规则引擎
- `src/agents/rules/loader.py` - YAML规则加载器
- `src/agents/rules/models.py` - 规则数据模型

**SchemeGenerationAgent**
- `src/agents/scheme_generation/agent.py` - 方案生成Agent
- `src/agents/scheme_generation/graph.py` - LangGraph定义（8节点流程）
- `src/agents/scheme_generation/state.py` - SchemeGenerationState
- `src/agents/scheme_generation/nodes/` - 8个节点函数
  - `rules.py` - apply_trr_rules
  - `capabilities.py` - extract_capabilities
  - `matching.py` - match_resources
  - `arbitration.py` - arbitrate_scenes
  - `optimization.py` - optimize_scheme
  - `filtering.py` - filter_hard_rules + score_soft_rules
  - `output.py` - generate_output

**TaskDispatchAgent**
- `src/agents/task_dispatch/agent.py` - 任务调度Agent
- `src/agents/task_dispatch/graph.py` - LangGraph定义
- `src/agents/task_dispatch/state.py` - TaskDispatchState
- `src/agents/task_dispatch/nodes/` - 4个节点函数
  - `decompose.py` - decompose_tasks
  - `schedule.py` - schedule_tasks
  - `routing.py` - plan_routes
  - `dispatch.py` - assign_executors

**API扩展**
- `POST /api/v2/ai/generate-scheme` - 生成救援方案
- `GET /api/v2/ai/generate-scheme/{task_id}` - 查询方案结果
- `POST /api/v2/ai/dispatch-tasks` - 任务调度
- `GET /api/v2/ai/dispatch-tasks/{task_id}` - 查询调度结果

### MODIFIED

- `src/agents/router.py` - 添加新API端点
- `src/agents/schemas.py` - 添加新Pydantic模型
- `src/agents/__init__.py` - 导出新Agent

## Impact

- **Affected specs**: 扩展 `ai-agents` capability
- **Affected code**:
  - 新增 `src/agents/rules/` 模块（4个文件）
  - 新增 `src/agents/scheme_generation/` 模块（~12个文件）
  - 新增 `src/agents/task_dispatch/` 模块（~8个文件）
  - 新增 `config/rules/` 规则库（2个YAML文件）
  - 更新 `src/agents/router.py`、`schemas.py`
- **Affected tables**: 使用现有表
  - `schemes_v2` - 存储生成的方案
  - `scheme_resource_allocations_v2` - 存储资源分配（含AI推荐理由）
  - `tasks_v2` - 存储调度的任务
  - `ai_decision_logs_v2` - 记录AI决策

## SQL Tables

**无需新增SQL** - 现有表结构已满足需求：
- `schemes_v2.ai_input_snapshot` - 存储AI输入快照
- `schemes_v2.ai_confidence_score` - 存储AI置信度
- `schemes_v2.ai_reasoning` - 存储AI推理说明
- `scheme_resource_allocations_v2.*_reason` - 存储各维度推荐理由

## Dependencies

现有依赖已满足：
- `langgraph>=0.3.27` - 状态图编排
- `pymoo>=0.6.0` - 多目标优化（NSGA-II）
- `pyyaml>=6.0` - YAML规则加载
- `ortools>=9.0` - CSP约束求解（已用于CapabilityMatcher）

## Architecture Alignment

本设计与军事版架构对应关系：

| 军事版阶段 | 应急版实现 | 状态 |
|-----------|-----------|------|
| 作战任务分解（NLP+HTN） | EventAnalysisAgent + TRRRuleEngine | ✅ 已实现 + 🆕 新增 |
| 能力需求评估 | CapabilityMappingProvider | ✅ 已存在 |
| 能力-装备映射（CSP+NSGA-II） | SchemeGenerationAgent | 🆕 新增 |
| 杀伤链寻优（硬规则+软规则） | TaskDispatchAgent + Optimization | 🆕 新增 |

## References

- 军事版文档：`docs/TO XIAOMA 20251124(2).docx`
- AI接口设计：`docs/emergency-brain/接口设计/02_AI_Agent接口设计.md`
- 操作手册：`docs/应急大脑系统-操作手册1.1.pdf`
- 现有算法：`src/planning/algorithms/`
