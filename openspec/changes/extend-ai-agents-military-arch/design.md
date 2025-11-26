# Design: 扩展AI Agent模块 - 军事版架构实现

## Context

军事版文档（TO XIAOMA 20251124）定义了一套完整的智能决策架构：
1. **语义理解层**：NLP解析→规则推理→HTN规划
2. **约束求解层**：CSP约束满足→能力-装备映射
3. **优化层**：NSGA-II多目标优化→Pareto最优解
4. **过滤层**：硬规则一票否决→软规则加权评分

应急场景虽不需要完整的NLP和HTN，但架构思想值得借鉴。

## Goals

1. 实现TRRRuleEngine规则引擎，支持业务规则驱动
2. 实现SchemeGenerationAgent，自动生成救援方案
3. 实现TaskDispatchAgent，任务拆解和路径规划
4. 保持决策可解释性，所有推理有据可查

## Non-Goals

- 不实现完整NLP语义解析（输入已结构化）
- 不实现完整HTN规划（任务类型相对固定）
- 不实现K-Means聚类（场景已明确）
- 不实现实时动态调整（Phase 3再考虑）

## Decisions

### 1. TRR规则引擎设计

**规则结构（YAML格式）**
```yaml
# config/rules/trr_emergency.yaml
TRR-EM-001:
  name: 地震人员搜救规则
  description: 地震导致建筑倒塌且有被困人员时触发
  trigger:
    conditions:
      - field: disaster_type
        operator: in
        value: [earthquake, building_collapse]
      - field: has_trapped
        operator: eq
        value: true
    logic: AND
  actions:
    task_types: [search_rescue, medical_emergency]
    required_capabilities:
      - code: SEARCH_LIFE_DETECT
        priority: critical
      - code: RESCUE_STRUCTURAL
        priority: critical
      - code: MEDICAL_TRIAGE
        priority: high
    resource_types: [rescue_team, medical_team]
    grouping_pattern: "1搜救队 + 1医疗队"
  priority: critical
  weight: 0.95
```

**规则引擎实现**
```python
# src/agents/rules/engine.py
class TRRRuleEngine:
    """TRR触发规则引擎"""
    
    def __init__(self, rules_path: str = "config/rules/trr_emergency.yaml"):
        self.rules = RuleLoader.load(rules_path)
    
    def evaluate(self, context: Dict[str, Any]) -> List[MatchedRule]:
        """
        评估上下文，返回匹配的规则列表
        
        Args:
            context: 事件上下文（disaster_type, has_trapped, etc.）
            
        Returns:
            按优先级排序的匹配规则列表
        """
        matched = []
        for rule in self.rules:
            if self._check_conditions(rule.trigger.conditions, context, rule.trigger.logic):
                matched.append(MatchedRule(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    actions=rule.actions,
                    priority=rule.priority,
                    weight=rule.weight,
                ))
        return sorted(matched, key=lambda r: r.weight, reverse=True)
    
    def _check_conditions(self, conditions: List[Condition], context: Dict, logic: str) -> bool:
        """检查条件是否满足"""
        results = [self._check_single(cond, context) for cond in conditions]
        if logic == "AND":
            return all(results)
        elif logic == "OR":
            return any(results)
        return False
```

### 2. SchemeGenerationAgent LangGraph设计

**State定义**
```python
# src/agents/scheme_generation/state.py
class SchemeGenerationState(TypedDict):
    """方案生成Agent状态"""
    # 输入
    event_id: str
    scenario_id: str
    event_analysis: Dict[str, Any]  # EventAnalysisAgent输出
    constraints: Dict[str, Any]      # 约束条件
    optimization_weights: Dict[str, float]  # 优化权重
    
    # 规则触发结果
    matched_rules: List[Dict[str, Any]]
    
    # 能力需求
    capability_requirements: List[Dict[str, Any]]
    
    # 资源匹配结果
    resource_candidates: List[Dict[str, Any]]
    resource_allocations: List[Dict[str, Any]]
    
    # 场景仲裁结果（多事件场景）
    scene_priorities: List[Dict[str, Any]]
    conflict_resolutions: List[Dict[str, Any]]
    
    # 优化结果
    pareto_solutions: List[Dict[str, Any]]
    
    # 过滤评分结果
    feasible_schemes: List[Dict[str, Any]]
    scheme_scores: List[Dict[str, Any]]
    recommended_scheme: Dict[str, Any]
    
    # 输出
    scheme_output: Dict[str, Any]
    
    # 追踪
    trace: Dict[str, Any]
    errors: List[str]
```

**LangGraph流程**
```
START
  │
  ▼
apply_trr_rules ─────────────────┐
  │                              │
  ▼                              │
extract_capabilities             │  Phase 1: 需求分析
  │                              │
  ▼                              │
match_resources ─────────────────┘
  │
  ▼
arbitrate_scenes ────────────────┐
  │                              │
  ▼                              │  Phase 2: 优化求解
optimize_scheme ─────────────────┘
  │
  ▼
filter_hard_rules ───────────────┐
  │                              │
  ▼                              │  Phase 3: 过滤评分
score_soft_rules ────────────────┘
  │
  ▼
generate_output
  │
  ▼
END
```

### 3. 硬规则和软规则设计

**硬规则（一票否决）**
```yaml
# config/rules/hard_rules.yaml
HR-EM-001:
  name: 人员安全红线
  check: rescue_risk > 0.10
  action: reject
  message: 救援人员伤亡风险超过10%，方案否决

HR-EM-002:
  name: 响应时效性
  check: response_time > golden_hour_deadline
  action: reject
  message: 响应时间超过黄金救援时间

HR-EM-003:
  name: 关键能力覆盖
  check: critical_capabilities_coverage < 1.0
  action: reject
  message: 关键能力未完全覆盖

HR-EM-004:
  name: 资源可用性
  check: unavailable_critical_resources > 0
  action: reject
  message: 关键资源不可用
```

**软规则（加权评分）**
```python
# 默认权重（可通过API传入覆盖）
SOFT_RULE_WEIGHTS = {
    "response_time": 0.35,     # 响应时间（越短越好）
    "coverage_rate": 0.30,     # 覆盖率（越高越好）
    "cost": 0.15,              # 成本（越低越好）
    "risk": 0.20,              # 风险（越低越好）
}

# 场景差异化权重
SCENARIO_WEIGHTS = {
    "earthquake": {"response_time": 0.40, "coverage_rate": 0.30, "cost": 0.10, "risk": 0.20},
    "hazmat": {"risk": 0.40, "coverage_rate": 0.30, "response_time": 0.20, "cost": 0.10},
}
```

### 4. TaskDispatchAgent设计

**State定义**
```python
class TaskDispatchState(TypedDict):
    """任务调度Agent状态"""
    # 输入
    scheme_id: str
    scheme: Dict[str, Any]  # SchemeGenerationAgent输出
    routing_config: Dict[str, Any]
    
    # 任务拆解结果
    tasks: List[Dict[str, Any]]
    task_dependencies: Dict[str, List[str]]  # task_id -> [depends_on]
    
    # 调度结果
    schedule: Dict[str, Any]  # 甘特图数据
    critical_path: List[str]
    
    # 路径规划结果
    routes: List[Dict[str, Any]]
    vrp_solution: Dict[str, Any]
    
    # 执行者分配
    assignments: List[Dict[str, Any]]
    
    # 输出
    dispatch_result: Dict[str, Any]
    
    # 追踪
    trace: Dict[str, Any]
    errors: List[str]
```

**简化版任务依赖（替代完整HTN）**
```python
# 任务依赖模板
TASK_DEPENDENCIES = {
    "search_rescue": {
        "depends_on": ["reconnaissance"],  # 搜救前需要侦察
        "enables": ["medical_treatment"],   # 搜救使能医疗
    },
    "medical_treatment": {
        "depends_on": ["search_rescue"],
        "enables": ["evacuation"],
    },
    "evacuation": {
        "depends_on": ["medical_treatment"],
        "enables": [],
    },
    "reconnaissance": {
        "depends_on": [],
        "enables": ["search_rescue", "hazard_assessment"],
    },
}
```

### 5. API设计

**POST /api/v2/ai/generate-scheme**
```python
class GenerateSchemeRequest(BaseModel):
    event_id: UUID
    scenario_id: UUID
    constraints: Optional[SchemeConstraints] = None
    optimization_weights: Optional[Dict[str, float]] = None
    options: Optional[GenerationOptions] = None

class SchemeConstraints(BaseModel):
    max_response_time_min: int = 30
    max_teams: int = 10
    reserve_ratio: float = 0.2
    priority_zones: List[str] = []

class GenerationOptions(BaseModel):
    generate_alternatives: int = 3
    include_rationale: bool = True
    include_pareto: bool = True
```

**响应结构**
```json
{
    "success": true,
    "task_id": "scheme-task-xxx",
    "status": "completed",
    "schemes": [
        {
            "scheme_id": "scheme-001",
            "rank": 1,
            "score": 0.92,
            "tasks": [...],
            "resource_allocations": [...],
            "triggered_rules": [...],
            "estimated_metrics": {...},
            "rationale": "..."
        }
    ],
    "pareto_solutions": [...],
    "trace": {
        "algorithms_used": [...],
        "trr_rules_matched": [...],
        "hard_rules_checked": [...],
        "execution_time_ms": 892
    }
}
```

### 6. 目录结构

```
src/agents/
├── base/                       # ✅ 已实现
├── event_analysis/             # ✅ 已实现
├── scheme_generation/          # 🆕 新增
│   ├── __init__.py
│   ├── agent.py                # SchemeGenerationAgent
│   ├── graph.py                # LangGraph定义
│   ├── state.py                # SchemeGenerationState
│   └── nodes/
│       ├── __init__.py
│       ├── rules.py            # apply_trr_rules
│       ├── capabilities.py     # extract_capabilities
│       ├── matching.py         # match_resources
│       ├── arbitration.py      # arbitrate_scenes
│       ├── optimization.py     # optimize_scheme
│       ├── filtering.py        # filter_hard_rules + score_soft_rules
│       └── output.py           # generate_output
├── task_dispatch/              # 🆕 新增
│   ├── __init__.py
│   ├── agent.py                # TaskDispatchAgent
│   ├── graph.py                # LangGraph定义
│   ├── state.py                # TaskDispatchState
│   └── nodes/
│       ├── __init__.py
│       ├── decompose.py        # decompose_tasks
│       ├── schedule.py         # schedule_tasks
│       ├── routing.py          # plan_routes
│       └── dispatch.py         # assign_executors
├── rules/                      # 🆕 规则引擎
│   ├── __init__.py
│   ├── engine.py               # TRRRuleEngine
│   ├── loader.py               # YAML规则加载器
│   └── models.py               # 规则数据模型
├── router.py                   # 🔄 更新
└── schemas.py                  # 🔄 更新

config/rules/
├── trr_emergency.yaml          # 🆕 TRR触发规则库
└── hard_rules.yaml             # 🆕 硬约束规则库
```

## Risks / Trade-offs

| 风险 | 严重程度 | 缓解措施 |
|-----|---------|---------|
| 规则库设计质量 | 高 | 需要领域专家参与定义规则 |
| 多目标优化调参 | 中 | 使用pymoo默认参数，后续调优 |
| 算法执行超时 | 中 | 设置30秒硬超时，缓存中间结果 |
| 资源冲突处理 | 低 | 已有SceneArbitrator处理 |

## Migration Plan

**Phase 1（P0，约5天）**
1. 实现TRRRuleEngine规则引擎
2. 实现SchemeGenerationAgent
3. 扩展API端点

**Phase 2（P1，约3天）**
4. 实现TaskDispatchAgent
5. 扩展API端点

**Phase 3（P2，后续迭代）**
6. 实现EmergencyPlanningOrchestrator多Agent协调
7. 实现动态调整能力

## Validation Criteria

1. `POST /ai/generate-scheme` 返回完整方案
2. 方案包含：任务列表、资源分配、推荐理由、Pareto解集
3. 方案通过所有硬规则检查
4. 资源分配包含匹配得分和推荐理由
5. AI决策日志记录完整追踪信息
6. 响应时间 < 5秒

## Open Questions

1. 规则库是否需要支持运行时热更新？（建议Phase 3实现）
2. 是否需要支持方案版本比较？（建议后续迭代）
3. 多事件并发场景资源冲突如何处理？（已有SceneArbitrator）
