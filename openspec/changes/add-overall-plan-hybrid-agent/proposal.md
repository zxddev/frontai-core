# Change: 总体救灾方案生成混合Agent

## Why

当前系统前端有"总体救灾方案要素设置"功能，需要生成**向上级汇报灾情+申请资源**的9个模块。后端接口 `/disaster-plan/{id}/modules` 返回静态mock数据，无法满足实际业务需求。

**业务场景**：前线指挥组抵达灾区后，需要向上级（省应急指挥中心）提交：
1. **灾情态势汇报**：当前灾区是什么状况
2. **资源申请方案**：需要调集哪些救援力量、物资、设备

根据架构选型文档分析，这9个模块分为两类性质完全不同的任务：
1. **态势感知类**（模块0、5）：非结构化、需要从多源信息综合 → 适合**CrewAI**
2. **资源计算类**（模块1-4、6-8）：需要精确计算、SOP执行 → 适合**MetaGPT**

**单一框架无法完美覆盖全流程**，必须采用"分步异构、中枢编排"的混合架构。

现有问题：
1. **返回静态模板**：【】占位符需要指挥员手工填写
2. **未利用系统数据**：未利用EmergencyAI分析结果和资源库数据
3. **缺乏专业估算**：未使用SPHERE等国际人道主义标准计算资源需求
4. **无审批流程**：缺少指挥官审核环节（HITL）
5. **错误处理不透明**：Agent失败时缺少统一状态机与错误暴露机制，存在静默降级或仅返回模板兜底的风险

## What Changes

### ADDED

**混合Agent编排核心**
- `src/agents/overall_plan/graph.py` - LangGraph状态图（指挥台）
- `src/agents/overall_plan/state.py` - 全局状态定义
- `src/agents/overall_plan/schemas.py` - Pydantic数据契约
- `src/agents/overall_plan/agent.py` - OverallPlanAgent主类

**CrewAI态势感知子图（侦察兵）**
- `src/agents/overall_plan/crewai/crew.py` - 态势感知Crew定义
- `src/agents/overall_plan/crewai/agents.py` - 情报指挥官、灾情分析员Agent
- `src/agents/overall_plan/crewai/tasks.py` - 态势汇报Task定义
- → 输出：模块0(灾情基本情况) + 模块5(次生灾害)

**MetaGPT资源计算子图（参谋长）**
- `src/agents/overall_plan/metagpt/roles.py` - 资源规划师Role（含Data Interpreter）
- `src/agents/overall_plan/metagpt/actions.py` - 资源计算Action
- `src/agents/overall_plan/metagpt/estimators.py` - SPHERE标准估算公式
- → 输出：模块1-4, 6-8(资源申请)

**MetaGPT公文生成（文书专员）**
- `src/agents/overall_plan/metagpt/scribe.py` - 公文秘书Role
- → 输出：整合后的正式方案文档

**LangGraph节点实现**
- `src/agents/overall_plan/nodes/load_context.py` - 数据聚合
- `src/agents/overall_plan/nodes/situational_awareness.py` - CrewAI态势感知节点
- `src/agents/overall_plan/nodes/resource_calculation.py` - MetaGPT资源计算节点
- `src/agents/overall_plan/nodes/human_review.py` - HITL审核节点（interrupt）
- `src/agents/overall_plan/nodes/document_generation.py` - 正式文件生成节点

**错误处理与任务标识**
- 统一总体方案生成的工作流状态：`pending`、`running`、`awaiting_approval`、`completed`、`failed`
- 为每次方案生成创建独立的 `task_id` 并与 LangGraph 的 `thread_id` 一一对应
- 当 CrewAI / MetaGPT / SPHERE 估算或上下游集成任意一步失败时，采用 fail-fast 策略，直接将工作流标记为 `failed`
- 明确禁止在失败时返回带占位符的模板或单次 LLM fallback 输出，错误信息通过状态查询接口统一对外暴露

**API端点**
- `src/domains/frontend_api/overall_plan/router.py` - API路由
  - `GET /api/overall-plan/{event_id}/modules` - 触发总体方案生成，创建 `task_id` 并返回初始状态
  - `GET /api/overall-plan/{event_id}/status` - 基于 `event_id` + `task_id` 查询指定run的流程状态与9个模块内容
  - `PUT /api/overall-plan/{event_id}/approve` - 指挥官审批指定 `task_id` 的方案，可携带修改与"批准/退回"决策
  - `GET /api/overall-plan/{event_id}/document` - 基于 `event_id` + `task_id` 获取最终文档内容

### MODIFIED

- `pyproject.toml` - 添加crewai、metagpt依赖
- `src/domains/frontend_api/router.py` - 注册overall_plan路由
- `src/agents/__init__.py` - 导出OverallPlanAgent

## Impact

- **Affected specs**: 新增 `overall-plan` capability
- **Affected code**:
  - 新增 `src/agents/overall_plan/` 模块（~20个文件）
  - 新增 `src/domains/frontend_api/overall_plan/` API
  - 更新依赖和路由注册
- **Affected tables**: 使用现有表
  - `events_v2` - 事件信息
  - `ai_decision_logs_v2` - AI决策日志（用于状态持久化）

## Dependencies

**现有依赖**：
- `langgraph>=1.0.0` - 状态图编排
- `langchain>=0.3.0` - LLM工具封装
- `langchain-openai>=0.2.0` - OpenAI兼容客户端

**新增依赖**：
- `crewai>=0.30.0` - 态势感知Agent框架
- `crewai-tools>=0.4.0` - CrewAI工具集
- `metagpt>=0.8.0` - 资源计算Agent框架

## Architecture Alignment

与架构选型文档对应：

| 任务阶段 | 框架选择 | 理由 |
|---------|---------|------|
| 态势感知（模块0、5） | CrewAI | 非结构化信息处理、动态任务委派、灵活协作 |
| 资源计算（模块1-4、6-8） | MetaGPT | Data Interpreter精确计算、SOP执行、结构化输出 |
| 指挥审核 | LangGraph | Checkpoint持久化、interrupt/resume、HITL |
| 公文生成 | MetaGPT | 模板填充、工程化输出、格式合规 |

## References

- 架构选型文档：`docs/agent架构选型/LangGraph 集成专业 Agent 框架.md`
- 工具选择文档：`docs/agent架构选型/灾害预测与汇报LLM工具选择.md`
- 前端组件：`emergency-rescue-brain/src/view/modal/overall-rescue-modal.jsx`
- 前端模板：`emergency-rescue-brain/public/data/overallPlanPreview.json`
