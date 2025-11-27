# Design: 驻扎点选址Agent架构

## Context

### 问题分析

地震救援驻扎点选址不是简单的优化问题，而是**人机协作决策问题**：

1. **输入是非结构化的**
   - 灾情报告："茂县叠溪镇发生7.0级地震，多处道路被滑坡阻断..."
   - 需要LLM理解语义，提取关键约束

2. **决策需要多维度分析**
   - 地形：坡度、稳定性、展开空间
   - 通信：基站覆盖、卫星盲区、应急方案
   - 安全：次生灾害、余震、气象风险

3. **输出需要可解释**
   - 指挥官需要理解"为什么推荐这个点"
   - 需要提供风险警示和备选方案

### 学术论文支撑

| 论文 | 关键观点 | 应用 |
|------|---------|------|
| IncidentResponseGPT (2024) | GenAI生成 + TOPSIS排序验证 | 混合架构设计 |
| HAZARD Challenge (2024) | LLM agent灾难场景决策能力 | 节点设计参考 |
| Making LLMs Reliable (2025) | 5层保护架构 | 安全设计 |
| MCGDM Cloud Models (2020) | 多准则群体决策处理不确定性 | 评分方法 |
| Human-AI Collaboration | 对比解释提升人类决策能力 | 解释节点设计 |

## Goals / Non-Goals

**Goals**:
- 将驻扎点选址重构为LangGraph Agent
- 实现"地形→通信→安全→评分"多步分析流程
- 提供可解释的决策输出和风险警示
- 保留纯算法Service作为降级方案
- 支持人机协作验证

**Non-Goals**:
- 完全替代人类决策（Agent仅提供建议）
- 实时流式更新（当前为请求-响应模式）
- 多队伍协同选址（当前为单队伍）

## Decisions

### 1. 架构模式：Hybrid Agent

**决策**：LangGraph Agent + 算法Tool混合架构

```
┌──────────────────────────────────────────────────────────┐
│              StagingAreaAgent (LangGraph)                │
├──────────────────────────────────────────────────────────┤
│  [灾情理解] → [地形分析] → [通信分析] → [安全分析]       │
│     LLM        LLM+GIS      LLM+Data     LLM+算法       │
│                                                          │
│  [决策解释] ← [评分排序] ← [路径验证] ← [候选搜索]       │
│     LLM        加权算法       A*         PostGIS        │
├──────────────────────────────────────────────────────────┤
│          StagingAreaCore (Tool - 现有实现)               │
└──────────────────────────────────────────────────────────┘
```

**理由**：
- LLM处理语义理解和解释生成（不可算法化的部分）
- 算法处理空间查询和路径规划（可验证的部分）
- 保留现有实现作为Tool，最大化代码复用

### 2. 节点设计

| 节点 | 职责 | 技术 | 输出 |
|------|------|------|------|
| understand_disaster | 解析灾情描述，提取约束 | LLM | ParsedDisaster, Constraints |
| analyze_terrain | 评估地形适宜性 | LLM + GIS数据 | TerrainAssessment |
| analyze_communication | 评估通信可行性 | LLM + 通信数据 | CommunicationAssessment |
| analyze_safety | 综合安全风险判断 | LLM + 算法 | SafetyAssessment |
| evaluate_candidates | 候选点搜索、路径验证、评分 | 算法(Tool) | RankedCandidates |
| explain_decision | 生成推荐理由和风险警示 | LLM | Explanation, RiskWarnings |

### 3. 状态设计

```python
class StagingAreaAgentState(TypedDict):
    # 输入
    disaster_description: str           # 灾情描述（自然语言）
    structured_input: StructuredInput   # 结构化数据（可选）
    team_info: TeamInfo                 # 队伍信息
    rescue_targets: list[RescueTarget]  # 救援目标
    
    # 分析结果
    parsed_constraints: list[Constraint]  # 提取的约束
    terrain_assessment: TerrainAssessment
    comm_assessment: CommunicationAssessment
    safety_assessment: SafetyAssessment
    
    # 候选点
    candidates: list[StagingCandidate]  # 候选点列表
    routes: dict[str, RouteResult]      # 路径验证结果
    
    # 输出
    ranked_sites: list[RankedSite]      # 排序后的推荐
    explanation: str                     # 决策解释
    risk_warnings: list[RiskWarning]    # 风险警示
    alternatives: list[Alternative]     # 备选方案
    
    # 元数据
    confidence: float                    # 置信度
    errors: list[str]                   # 错误信息
```

### 4. 安全设计原则

| 原则 | 实现 |
|------|------|
| LLM输出可验证 | 提取的约束必须映射到可检查的数据 |
| LLM不做最终决策 | 只做分析和建议，排序由算法完成 |
| 人机协作验证 | 所有推荐附带置信度和风险提示 |
| 回退机制 | LLM超时/失败时降级为纯算法Service |
| 透明解释 | 每个推荐必须说明理由 |

### 5. Tool设计

将现有`StagingAreaCore`封装为Tool：

```python
class StagingCoreTool(BaseTool):
    """驻扎点选址核心算法工具"""
    
    name: str = "staging_area_core"
    description: str = "执行驻扎点候选搜索、路径验证和评分排序"
    
    def _run(
        self,
        epicenter: tuple[float, float],
        magnitude: float,
        team_location: tuple[float, float],
        rescue_targets: list[dict],
        constraints: list[dict] | None = None,
    ) -> dict:
        """调用StagingAreaCore执行算法"""
        ...
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| LLM幻觉 | 所有LLM输出必须被数据验证后才能使用 |
| 延迟增加 | 并行执行独立分析节点；保留快速算法接口 |
| 复杂度增加 | 模块化设计，每个节点可独立测试 |
| LLM不可用 | 自动降级到纯算法Service |

## Migration Plan

1. **Phase 1: 创建Agent框架**
   - 创建`src/agents/staging_area/`目录结构
   - 实现State和基础Graph
   - 封装现有Core为Tool

2. **Phase 2: 实现分析节点**
   - understand_disaster节点
   - analyze_terrain节点
   - analyze_communication节点
   - analyze_safety节点

3. **Phase 3: 实现输出节点**
   - evaluate_candidates节点（调用Tool）
   - explain_decision节点

4. **Phase 4: 集成测试**
   - 单元测试每个节点
   - 集成测试完整流程
   - 与纯算法Service对比测试

5. **Phase 5: API注册**
   - 注册Agent路由
   - 更新文档

## Open Questions

- 是否需要支持流式输出（边分析边返回）？
- 地形/通信/安全三个分析节点是否可以并行执行？
- 如何处理LLM分析结果与数据库数据的冲突？
