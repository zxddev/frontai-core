# Change: 重构驻扎点选址为LangGraph Agent

## Why

当前`add-staging-area-planning`实现了纯算法Service，但经过深度分析（基于45+篇学术论文和10层推理），这一设计存在根本性缺陷：

**原始需求描述**：
> "指挥所选址 │ 高 │ 地形→通信→安全→评分 │ 是 │ ✅ 独立Agent"

原始需求明确要求：
1. **独立Agent**架构
2. **多步分析流程**：地形→通信→安全→评分
3. **高优先级**：这是救援系统，错误可能导致人员伤亡

**当前实现的致命缺陷**：
| 缺陷 | 风险 |
|------|------|
| 无法理解非结构化灾情描述 | 错过关键约束（如"道路可能被滑坡阻断"） |
| 权重硬编码 | 无法适应不同灾难场景 |
| 无推理解释 | 指挥官无法验证决策依据 |
| 无风险警示 | 可能推荐位于堰塞湖下游的"高分"位置 |

**论文支撑**：
- IncidentResponseGPT (2024): GenAI生成+TOPSIS验证的混合架构
- HAZARD Challenge (2024): LLM在灾难场景需要推理能力
- Making LLMs Reliable (2025): 高风险决策需要5层保护架构

## What Changes

- **ADDED**: `src/agents/staging_area/` LangGraph Agent模块
  - `graph.py`: 6节点工作流
  - `state.py`: TypedDict状态定义
  - `agent.py`: Agent入口
  - `nodes/`: 各分析节点实现
    - `understand.py`: 灾情理解节点 (LLM)
    - `terrain.py`: 地形分析节点 (LLM+GIS)
    - `communication.py`: 通信分析节点 (LLM+Data)
    - `safety.py`: 安全分析节点 (LLM+算法)
    - `evaluate.py`: 评分排序节点 (算法为主)
    - `explain.py`: 决策解释节点 (LLM)
  - `tools/`: Agent工具
    - `staging_core_tool.py`: 封装现有StagingAreaCore
- **MODIFIED**: `src/domains/staging_area/core.py` 
  - 调整为Agent的底层Tool
  - 增加可解释性输出接口
- **ADDED**: API端点 `POST /api/v2/ai/staging-area` (Agent入口)
- **RETAINED**: `POST /api/v1/staging-area/recommend` (保留纯算法接口作为降级)

## Impact

- Affected specs: staging-area
- Affected code:
  - `src/agents/staging_area/` (新增)
  - `src/domains/staging_area/core.py` (修改)
  - `src/agents/router.py` (注册Agent)
  - `src/main.py` (注册路由)
- Breaking changes: 无（新增Agent，保留原Service）
