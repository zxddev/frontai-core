# Design: 应急救灾AI+规则混合系统

## Context

参考军事版文档（TO XIAOMA 20251124）的4阶段架构，设计应急救灾场景的AI+规则混合系统。

**军事版架构**：
1. 作战任务分解：NLP语义解析 → 场景识别 → HTN任务分解
2. 能力需求评估：规则推理 → 能力需求映射
3. 能力-装备映射：CSP约束满足 → NSGA-II多目标优化
4. 杀伤链寻优：硬规则过滤 → 软规则评分

**应急版映射**：
1. 灾情理解：LLM语义解析 + RAG案例增强
2. 规则推理：KG规则查询 + TRR引擎匹配
3. 资源匹配：CSP约束满足 + NSGA-II优化
4. 方案优化：硬/软规则过滤 + LLM解释生成

## Goals

1. 实现真正的LLM调用，具备语义理解能力
2. 集成RAG检索，支持历史案例和最佳实践查询
3. 集成知识图谱，支持动态规则查询
4. 保持决策可解释性，所有推理有据可查
5. 使用LangGraph 1.0最新API实现

## Non-Goals

- 不实现完整HTN规划（使用简化任务模板）
- 不实现K-Means聚类（场景已明确）
- 不实现实时动态调整（Phase 3再考虑）
- 不替换现有EventAnalysisAgent（新增独立Agent）

## Decisions

### 1. LangGraph 1.0架构设计

**State定义**（强类型）
```python
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class EmergencyAIState(TypedDict):
    """应急AI混合系统状态"""
    # 输入
    event_id: str
    scenario_id: str
    disaster_description: str  # 自然语言灾情描述
    structured_data: Dict[str, Any]  # 结构化输入
    constraints: Dict[str, Any]  # 约束条件
    
    # 消息历史（LLM对话）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 阶段1: 灾情理解
    parsed_entities: Dict[str, Any]  # LLM提取的实体
    similar_cases: List[Dict[str, Any]]  # RAG检索的案例
    understanding_report: Dict[str, Any]  # 理解报告
    
    # 阶段2: 规则推理
    matched_rules: List[Dict[str, Any]]  # 匹配的TRR规则
    task_requirements: List[Dict[str, Any]]  # 任务需求
    capability_requirements: List[Dict[str, Any]]  # 能力需求
    
    # 阶段3: 资源匹配
    resource_candidates: List[Dict[str, Any]]  # 候选资源
    allocation_solutions: List[Dict[str, Any]]  # 分配方案
    pareto_solutions: List[Dict[str, Any]]  # Pareto最优解
    
    # 阶段4: 方案优化
    feasible_schemes: List[Dict[str, Any]]  # 可行方案
    scheme_scores: List[Dict[str, Any]]  # 方案评分
    recommended_scheme: Dict[str, Any]  # 推荐方案
    scheme_explanation: str  # LLM生成的解释
    
    # 输出
    final_output: Dict[str, Any]
    
    # 追踪
    trace: Dict[str, Any]
    errors: List[str]
```

**LangGraph流程图**
```
START
  │
  ▼
┌─────────────────────────────────────┐
│ Phase 1: 灾情理解                   │
│ ├─ understand_disaster (LLM)        │
│ └─ enhance_with_cases (RAG)         │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ Phase 2: 规则推理                   │
│ ├─ query_rules (KG)                 │
│ └─ apply_rules (TRREngine)          │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ Phase 3: 资源匹配                   │
│ ├─ match_resources (CSP)            │
│ └─ optimize_allocation (NSGA-II)    │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ Phase 4: 方案优化                   │
│ ├─ filter_hard_rules (Rules)        │
│ ├─ score_soft_rules (Rules)         │
│ └─ explain_scheme (LLM)             │
└─────────────────────────────────────┘
  │
  ▼
generate_output
  │
  ▼
END
```

### 2. LLM工具设计

**工具定义（使用LangChain工具装饰器）**
```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class DisasterParseInput(BaseModel):
    """灾情解析输入"""
    description: str = Field(..., description="灾情描述文本")
    context: Dict[str, Any] = Field(default_factory=dict, description="上下文信息")

class DisasterParseOutput(BaseModel):
    """灾情解析输出"""
    disaster_type: str = Field(..., description="灾害类型")
    location: Dict[str, float] = Field(..., description="位置坐标")
    severity: str = Field(..., description="严重程度")
    affected_entities: List[Dict[str, Any]] = Field(..., description="受影响实体")
    constraints: List[str] = Field(..., description="约束条件")
    urgency_level: str = Field(..., description="紧急程度")

@tool
def parse_disaster_description(
    description: str,
    context: Dict[str, Any] | None = None
) -> DisasterParseOutput:
    """
    解析灾情描述文本，提取结构化信息。
    
    Args:
        description: 灾情描述文本（自然语言）
        context: 可选上下文信息
        
    Returns:
        结构化的灾情信息
    """
    # LLM调用实现
    pass
```

### 3. RAG工具设计

**案例检索**
```python
class CaseSearchInput(BaseModel):
    """案例检索输入"""
    query: str = Field(..., description="检索查询")
    disaster_type: str = Field(..., description="灾害类型")
    top_k: int = Field(default=5, description="返回数量")

class SimilarCase(BaseModel):
    """相似案例"""
    case_id: str
    title: str
    description: str
    disaster_type: str
    lessons_learned: List[str]
    best_practices: List[str]
    similarity_score: float

@tool
def search_similar_cases(
    query: str,
    disaster_type: str,
    top_k: int = 5
) -> List[SimilarCase]:
    """
    检索相似历史案例。
    
    Args:
        query: 检索查询（灾情描述）
        disaster_type: 灾害类型过滤
        top_k: 返回最相似的K个案例
        
    Returns:
        相似案例列表
    """
    # Qdrant检索实现
    pass
```

### 4. 知识图谱工具设计

**规则查询**
```python
class RuleQueryInput(BaseModel):
    """规则查询输入"""
    disaster_type: str = Field(..., description="灾害类型")
    conditions: Dict[str, Any] = Field(..., description="条件参数")

class TRRRule(BaseModel):
    """TRR规则"""
    rule_id: str
    rule_name: str
    trigger_conditions: List[Dict[str, Any]]
    required_tasks: List[str]
    required_capabilities: List[str]
    priority: str
    weight: float

@tool
def query_trr_rules(
    disaster_type: str,
    conditions: Dict[str, Any]
) -> List[TRRRule]:
    """
    查询TRR触发规则。
    
    Args:
        disaster_type: 灾害类型
        conditions: 触发条件
        
    Returns:
        匹配的TRR规则列表
    """
    # Neo4j查询实现
    pass
```

### 5. 节点函数设计

**灾情理解节点**
```python
async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    """
    阶段1: 灾情理解
    
    1. 调用LLM解析灾情描述
    2. 调用RAG检索相似案例
    3. 整合生成理解报告
    """
    # 获取LLM实例
    llm = get_chat_model()
    
    # 绑定工具
    llm_with_tools = llm.bind_tools([
        parse_disaster_description,
        search_similar_cases,
    ])
    
    # 构建提示
    system_prompt = """你是应急救灾AI助手，负责分析灾情信息。
    请使用工具解析灾情描述并检索相似案例。"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请分析以下灾情：{state['disaster_description']}")
    ]
    
    # 调用LLM
    response = await llm_with_tools.ainvoke(messages)
    
    # 处理工具调用
    # ...
    
    return {
        "parsed_entities": parsed_result,
        "similar_cases": cases,
        "understanding_report": report,
        "messages": [response],
    }
```

**规则推理节点**
```python
async def apply_rules(state: EmergencyAIState) -> Dict[str, Any]:
    """
    阶段2: 规则推理
    
    1. 查询知识图谱获取TRR规则
    2. 使用规则引擎匹配规则
    3. 生成任务和能力需求
    """
    # 查询知识图谱
    kg_client = get_neo4j_client()
    rules = kg_client.read("""
        MATCH (r:TRRRule)-[:TRIGGERS]->(t:Task)
        WHERE r.disaster_type = $disaster_type
        RETURN r, collect(t) as tasks
    """, {"disaster_type": state["understanding_report"]["disaster_type"]})
    
    # 规则引擎匹配
    engine = TRRRuleEngine()
    matched = engine.evaluate(state["understanding_report"])
    
    # 生成需求
    task_requirements = extract_task_requirements(matched)
    capability_requirements = extract_capability_requirements(matched)
    
    return {
        "matched_rules": matched,
        "task_requirements": task_requirements,
        "capability_requirements": capability_requirements,
    }
```

### 6. TRR规则YAML设计

**地震TRR规则库**
```yaml
# config/rules/trr_earthquake.yaml
TRR-EQ-001:
  name: 地震建筑搜救规则
  description: 地震导致建筑倒塌且有被困人员时触发搜救任务
  disaster_type: earthquake
  trigger:
    conditions:
      - field: has_building_collapse
        operator: eq
        value: true
      - field: has_trapped_persons
        operator: eq
        value: true
    logic: AND
  actions:
    tasks:
      - type: search_rescue
        priority: critical
        golden_hour: 72  # 小时
    capabilities:
      - code: LIFE_DETECTION
        priority: critical
      - code: STRUCTURAL_RESCUE
        priority: critical
      - code: MEDICAL_TRIAGE
        priority: high
    resource_types:
      - rescue_team
      - medical_team
      - heavy_equipment
  priority: critical
  weight: 0.95

TRR-EQ-002:
  name: 地震火灾处置规则
  description: 地震引发火灾时触发消防任务
  disaster_type: earthquake
  trigger:
    conditions:
      - field: has_secondary_fire
        operator: eq
        value: true
    logic: AND
  actions:
    tasks:
      - type: fire_suppression
        priority: critical
    capabilities:
      - code: FIRE_FIGHTING
        priority: critical
      - code: HAZMAT_HANDLING
        priority: high
    resource_types:
      - fire_team
      - hazmat_team
  priority: critical
  weight: 0.90

TRR-EQ-003:
  name: 地震危化品泄漏规则
  description: 地震导致危化品泄漏时触发应急处置
  disaster_type: earthquake
  trigger:
    conditions:
      - field: has_hazmat_leak
        operator: eq
        value: true
    logic: AND
  actions:
    tasks:
      - type: hazmat_containment
        priority: critical
      - type: evacuation
        priority: high
    capabilities:
      - code: HAZMAT_DETECTION
        priority: critical
      - code: HAZMAT_CONTAINMENT
        priority: critical
      - code: EVACUATION_COORDINATION
        priority: high
    resource_types:
      - hazmat_team
      - evacuation_team
  priority: critical
  weight: 0.92
```

### 7. 硬规则和软规则设计

**硬规则（一票否决）**
```yaml
# config/rules/hard_rules_emergency.yaml
HR-EM-001:
  name: 救援人员安全红线
  check: rescuer_risk_rate > 0.15
  action: reject
  message: 救援人员伤亡风险超过15%，方案否决

HR-EM-002:
  name: 黄金救援时间
  check: estimated_response_time > golden_hour_deadline
  action: reject
  message: 预计响应时间超过黄金救援时间

HR-EM-003:
  name: 关键能力覆盖
  check: critical_capability_coverage < 1.0
  action: reject
  message: 关键能力未完全覆盖

HR-EM-004:
  name: 资源可用性
  check: critical_resource_unavailable > 0
  action: reject
  message: 关键资源不可用
```

**软规则（加权评分）**
```python
SOFT_RULE_WEIGHTS = {
    "response_time": 0.35,     # 响应时间（越短越好）
    "coverage_rate": 0.30,     # 覆盖率（越高越好）
    "cost": 0.15,              # 成本（越低越好）
    "risk": 0.20,              # 风险（越低越好）
}

# 地震场景权重
EARTHQUAKE_WEIGHTS = {
    "response_time": 0.40,
    "coverage_rate": 0.30,
    "cost": 0.10,
    "risk": 0.20,
}
```

### 8. 目录结构

```
src/agents/
├── emergency_ai/               # 🆕 新增
│   ├── __init__.py
│   ├── agent.py                # EmergencyAIAgent
│   ├── graph.py                # LangGraph定义
│   ├── state.py                # EmergencyAIState
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── llm_tools.py        # LLM工具
│   │   ├── rag_tools.py        # RAG工具
│   │   └── kg_tools.py         # KG工具
│   └── nodes/
│       ├── __init__.py
│       ├── understanding.py    # 灾情理解
│       ├── reasoning.py        # 规则推理
│       ├── matching.py         # 资源匹配
│       ├── optimization.py     # 方案优化
│       └── output.py           # 输出格式化
├── rules/                      # 🆕 新增
│   ├── __init__.py
│   ├── engine.py               # TRRRuleEngine
│   ├── loader.py               # YAML加载器
│   └── models.py               # 规则模型
├── event_analysis/             # 现有
├── scheme_generation/          # 现有
├── router.py                   # 🔄 更新
└── schemas.py                  # 🔄 更新

config/rules/
├── trr_earthquake.yaml         # 🆕 地震TRR规则
├── trr_secondary.yaml          # 🆕 次生灾害TRR规则
└── hard_rules_emergency.yaml   # 🆕 硬约束规则
```

## Risks / Trade-offs

| 风险 | 严重程度 | 缓解措施 |
|-----|---------|---------|
| LLM响应延迟 | 高 | 设置超时，关键路径可并行 |
| LLM输出不稳定 | 高 | 结构化输出+验证，禁止幻觉 |
| RAG检索质量 | 中 | 案例库质量管理，相似度阈值 |
| KG数据完整性 | 中 | 规则预校验，缺失时报错 |
| 规则冲突 | 低 | 优先级排序，冲突检测 |

## Migration Plan

**Phase 1（P0，约7天）**
1. 实现LLM工具封装（llm_tools.py）
2. 实现RAG工具封装（rag_tools.py）
3. 实现KG工具封装（kg_tools.py）
4. 实现TRR规则引擎

**Phase 2（P1，约5天）**
5. 实现EmergencyAIAgent LangGraph流程
6. 实现4个阶段节点函数
7. 扩展API端点

**Phase 3（P2，约3天）**
8. 编写地震/次生灾害TRR规则库
9. 集成测试
10. 性能优化

## Validation Criteria

1. LLM成功调用并返回结构化输出
2. RAG成功检索相似案例
3. KG成功查询TRR规则
4. 规则引擎正确匹配规则
5. 方案包含LLM生成的解释
6. AI决策日志记录完整追踪
7. 响应时间 < 10秒

## Open Questions

1. 是否需要支持多轮对话澄清意图？（建议Phase 3）
2. 知识图谱数据如何初始化？（需要提供Neo4j初始化脚本）
3. RAG案例库如何维护？（需要案例录入流程）
