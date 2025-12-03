# EmergencyAI Agent 完整技术文档

## 1. 系统概述

### 1.1 定位
EmergencyAI 是一个 **AI+规则混合决策系统**，集成 LLM/RAG/知识图谱/规则引擎/NSGA-II多目标优化算法，实现自然语言灾情输入到救援方案输出的全自动化处理。

### 1.2 核心特性
- **Neuro-Symbolic架构**：LLM语义理解 + 符号规则推理 + 物理模型校准
- **5阶段流水线**：灾情理解(物理模型) → 规则推理 → HTN任务分解 → 资源匹配(NSGA-II) → 方案优化
- **双重验证**：LLM解析结果经过 Earthquake/Hazmat/Flood 物理模型二次校准
- **战略层扩展**：任务域分类、阶段优先级、模块装配、运力检查、安全规则、报告生成
- **5维方案评估**：成功率(0.35) + 响应时间(0.30) + 覆盖率(0.20) + 风险(0.05) + 冗余性(0.10)

### 1.3 技术栈
| 组件 | 技术 |
|------|------|
| 流程编排 | LangGraph 1.0 (StateGraph) |
| LLM | GPT-OSS-120B (兼容 OpenAI API) |
| 物理模型 | USGS ShakeMap(地震), Gaussian Plume(危化品), Sphere(物资) |
| 向量检索 | Qdrant (RAG案例库) |
| 知识图谱 | Neo4j (TRR规则/HTN任务/能力映射) |
| 关系数据库 | PostgreSQL (资源/配置/日志) |
| 优化算法 | NSGA-II (pymoo) |

---

## 2. API 接口

### 2.1 发起分析请求
```http
POST /api/v2/ai/emergency-analyze
Content-Type: application/json

{
  "event_id": "UUID",            // 必填：事件ID
  "scenario_id": "UUID",         // 必填：想定ID
  "disaster_description": "string", // 必填：灾情描述（自然语言，>=10字符）
  "structured_input": {          // 可选：结构化输入
    "location": {
      "longitude": 103.85,
      "latitude": 31.68
    },
    "occurred_at": "2025-12-02T10:00:00Z"
  },
  "constraints": {               // 可选：约束条件
    "max_response_time_hours": 2,
    "max_teams": 10
  },
  "optimization_weights": {      // 可选：自定义权重
    "success_rate": 0.35,
    "response_time": 0.30,
    "coverage_rate": 0.20,
    "risk": 0.05,
    "redundancy": 0.10
  }
}
```

**响应** (202 Accepted):
```json
{
  "success": true,
  "task_id": "emergency-{event_id}",
  "status": "processing",
  "message": "应急AI分析任务已提交，预计完成时间5-15秒"
}
```

### 2.2 查询分析结果
```http
GET /api/v2/ai/emergency-analyze/{task_id}
```

**轮询策略**: 每3秒查询一次，直到 `status === "completed"` 或 `status === "failed"`

---

## 3. 执行流程 (LangGraph)

### 3.1 流程图
```
START
  │
  ▼
┌─────────────────────────────────────────────┐
│ Phase 1: 灾情理解                           │
│ understand_disaster ─→ enhance_with_cases   │
│   - LLM解析灾情描述                         │
│   - 物理模型校准(DisasterAssessment)        │
│   - RAG检索相似案例                         │
│   - 并行执行优化                            │
└─────────────────────────────────────────────┘
  │
  ▼ (conditional: parsed_disaster != null?)
┌─────────────────────────────────────────────┐
│ Phase 2: 规则推理                           │
│ query_rules ─→ apply_rules                  │
│   - Neo4j查询TRR规则                        │
│   - 条件匹配提取能力需求                    │
└─────────────────────────────────────────────┘
  │
  ▼ (conditional: matched_rules.length > 0?)
┌─────────────────────────────────────────────┐
│ Phase 2.5: HTN任务分解                      │
│ htn_decompose                               │
│   - 场景识别(Neo4j Scene节点)               │
│   - 任务链加载(TaskChain节点)               │
│   - Kahn拓扑排序                            │
│   - 并行任务识别                            │
└─────────────────────────────────────────────┘
  │
  ▼ (conditional: task_sequence.length > 0?)
┌─────────────────────────────────────────────┐
│ Phase 2.6: 战略层 - 任务域/阶段/模块        │
│ classify_domains ─→ apply_phase_priority    │
│ ─→ assemble_modules                         │
│   - 从TRRRule.domain提取任务域              │
│   - 根据时间计算灾害阶段                    │
│   - 推荐预编组救援模块                      │
└─────────────────────────────────────────────┘
  │
  ▼ (conditional: recommended_modules > 0?)
┌─────────────────────────────────────────────┐
│ Phase 3: 资源匹配                           │
│ match_resources ─→ optimize_allocation      │
│   - 数据库查询候选队伍                      │
│   - 能力匹配计算                            │
│   - NSGA-II多目标优化生成Pareto解           │
│   - 装备调度/物资需求(Sphere标准)           │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ Phase 3.5: 战略层 - 运力检查                │
│ check_transport                             │
│   - PostgreSQL查询运力参数                  │
│   - 计算运力缺口                            │
│   - 生成运力警告                            │
└─────────────────────────────────────────────┘
  │
  ▼ (conditional: allocation_solutions > 0?)
┌─────────────────────────────────────────────┐
│ Phase 4: 方案优化                           │
│ filter_hard_rules ─→ check_safety_rules     │
│ ─→ score_soft_rules ─→ explain_scheme       │
│   - 硬规则过滤(一票否决)                    │
│   - 安全规则检查(JSON条件)                  │
│   - 5维软规则评分                           │
│   - LLM生成方案解释                         │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ Phase 4.5: 战略层 - 报告生成                │
│ generate_reports                            │
│   - 灾情初报/续报/日报模板渲染              │
└─────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────┐
│ 输出生成                                    │
│ generate_output                             │
│   - 组装最终JSON结果                        │
│   - 生成方案文本(供指挥员编辑)              │
└─────────────────────────────────────────────┘
  │
  ▼
END
```

### 3.2 节点清单 (17个)

| 阶段 | 节点函数 | 文件 | 功能 |
|------|----------|------|------|
| 1 | understand_disaster | understanding.py | LLM解析 + 物理模型校准 |
| 1 | enhance_with_cases | understanding.py | RAG案例检索 |
| 2 | query_rules | reasoning.py | Neo4j查询TRR规则 |
| 2 | apply_rules | reasoning.py | 规则条件匹配 |
| 2.5 | htn_decompose | htn_decompose.py | HTN任务分解 |
| 2.6 | classify_domains | domain_classifier.py | 任务域分类 |
| 2.6 | apply_phase_priority | phase_manager.py | 阶段优先级 |
| 2.6 | assemble_modules | module_assembler.py | 模块装配 |
| 3 | match_resources | matching.py | 资源匹配 |
| 3 | optimize_allocation | matching.py | NSGA-II优化(调用planning库) |
| 3.5 | check_transport | transport_checker.py | 运力检查 |
| 4 | filter_hard_rules | optimization.py | 硬规则过滤 |
| 4.1 | check_safety_rules | safety_checker.py | 安全规则 |
| 4 | score_soft_rules | optimization.py | 5维评分 |
| 4 | explain_scheme | optimization.py | LLM方案解释 |
| 4.5 | generate_reports | report_generator.py | 报告生成 |
| 5 | generate_output | output.py | 输出组装 |

---

## 4. 状态定义 (EmergencyAIState)

### 4.1 输入字段
```python
event_id: str                    # 事件ID
scenario_id: str                 # 想定ID
disaster_description: str        # 灾情描述(自然语言)
structured_input: Dict           # 结构化输入(位置等)
constraints: Dict                # 约束条件
optimization_weights: Dict       # 优化权重
```

### 4.2 阶段1: 灾情理解
```python
parsed_disaster: ParsedDisasterInfo  # LLM + 物理模型结果
  - disaster_type: str           # earthquake/fire/flood/hazmat/landslide
  - severity: str                # critical/high/medium/low
  - magnitude: float             # 震级(地震专用)
  - affected_area_km2: float     # 物理模型计算的受影响面积
  - disaster_level: str          # 物理模型判定的等级(I-IV)
  - estimated_casualties: Dict   # 物理模型估算的伤亡
  - has_building_collapse: bool
  - has_trapped_persons: bool
  - estimated_trapped: int
  - has_secondary_fire: bool
  - has_hazmat_leak: bool
  - has_road_damage: bool
  - affected_population: int
similar_cases: List[SimilarCase]     # RAG检索的历史案例
```

### 4.3 阶段2: 规则推理
```python
matched_rules: List[MatchedTRRRule]      # 匹配的TRR规则
task_requirements: List[Dict]             # 任务需求
capability_requirements: List[CapabilityRequirement]  # 能力需求
  - capability_code: str         # 如 LIFE_DETECTION
  - capability_name: str         # 如 生命探测
  - priority: str
  - provided_by: List[str]       # 可提供该能力的资源类型
```

### 4.4 阶段2.5: HTN任务分解
```python
scene_codes: List[str]                # 识别的场景代码 ["S1", "S4"]
task_sequence: List[TaskSequenceItem] # 拓扑排序后的任务序列
  - task_id: str                 # EM01, EM02...
  - task_name: str
  - sequence: int                # 执行顺序
  - depends_on: List[str]        # 依赖任务
  - golden_hour: int             # 黄金时间(分钟)
  - phase: str                   # detect/assess/plan/execute
  - is_parallel: bool
parallel_tasks: List[ParallelTaskGroup]  # 并行任务组
```

### 4.5 阶段2.6: 战略层
```python
active_domains: List[str]              # 激活的任务域 ["life_rescue", "engineering"]
domain_priorities: List[TaskDomainInfo] # 优先级排序
disaster_phase: str                     # initial/golden/intensive/recovery
disaster_phase_name: str                # 初期响应/黄金救援期/...
recommended_modules: List[RecommendedModule]  # 推荐模块
  - module_id: str
  - module_name: str
  - personnel: int
  - dogs: int
  - vehicles: int
  - provided_capabilities: List[str]
  - equipment_list: List[Dict]
transport_plans: List[TransportPlan]    # 运力规划
transport_warnings: List[str]           # 运力警告
safety_violations: List[SafetyViolation] # 安全违规
generated_reports: Dict[str, str]       # 生成的报告
```

### 4.6 阶段3: 资源匹配
```python
resource_candidates: List[ResourceCandidate]  # 候选资源
  - resource_id: str
  - resource_name: str
  - resource_type: str
  - capabilities: List[str]
  - distance_km: float
  - eta_minutes: float
  - match_score: float
  - rescue_capacity: int
allocation_solutions: List[AllocationSolution]  # 分配方案
pareto_solutions: List[AllocationSolution]      # Pareto最优解
```

### 4.7 阶段4: 方案优化
```python
scheme_scores: List[SchemeScore]        # 方案评分
  - scheme_id: str
  - hard_rule_passed: bool
  - hard_rule_violations: List[str]
  - soft_rule_scores: Dict[str, float]  # 5维评分
  - weighted_score: float
  - rank: int
recommended_scheme: AllocationSolution  # 推荐方案
scheme_explanation: str                  # LLM生成的方案解释
```

---

## 5. 数据库Schema

### 5.1 Neo4j 知识图谱

#### 节点类型
| 标签 | 说明 | 关键属性 |
|------|------|----------|
| TRRRule | TRR触发规则 | rule_id, disaster_type, trigger_conditions, priority |
| Capability | 能力定义 | code, name |
| TaskType | 任务类型 | code, name |
| Scene | 灾害场景 | scene_code, scene_name, disaster_type, triggers |
| TaskChain | 任务链 | chain_id, chain_name |
| MetaTask | 元任务 | task_id, name, phase, required_capabilities |
| TaskDomain | 任务域 | domain_id, name, priority_base |
| DisasterPhase | 灾害阶段 | phase_id, name, hours_start, hours_end |
| RescueModule | 救援模块 | module_id, name, personnel, dogs, vehicles |

#### 关系类型
| 关系 | 起点 → 终点 | 说明 |
|------|------------|------|
| REQUIRES_CAPABILITY | TRRRule → Capability | 规则需要的能力 |
| TRIGGERS | TRRRule → TaskType | 规则触发的任务 |
| HAS_CHAIN | Scene → TaskChain | 场景对应的任务链 |
| CONTAINS | TaskChain → MetaTask | 任务链包含的元任务 |
| DEPENDS_ON | MetaTask → MetaTask | 任务依赖 |
| BELONGS_TO | TRRRule → TaskDomain | 规则所属任务域 |
| PRIORITY_ORDER | DisasterPhase → TaskDomain | 阶段优先级 |
| PROVIDES | RescueModule → Capability | 模块提供的能力 |

### 5.2 PostgreSQL 配置表

#### config.safety_rules - 安全规则
```sql
rule_id VARCHAR(50) PRIMARY KEY,
rule_type VARCHAR(10),        -- 'hard'/'soft'
name VARCHAR(200),
condition JSONB,              -- JSON条件表达式
action VARCHAR(20),           -- 'block'/'warn'
message TEXT,
priority INT
```

#### config.transport_capacity - 运力参数
```sql
transport_type VARCHAR(50) PRIMARY KEY,
name VARCHAR(100),
capacity_per_unit INT,
speed_kmh INT,
constraints JSONB
```

#### config.report_templates - 报告模板
```sql
template_id VARCHAR(50) PRIMARY KEY,
report_type VARCHAR(20),      -- 'initial'/'update'/'daily'
name VARCHAR(100),
template TEXT,                -- 模板文本(支持变量)
variables JSONB
```

#### config.rescue_module_equipment - 模块装备清单
```sql
module_id VARCHAR(50),
equipment_type VARCHAR(50),
equipment_name VARCHAR(100),
quantity INT,
unit VARCHAR(20),
is_essential BOOLEAN
```

---

## 6. 返回数据结构

### 6.1 完整响应
```typescript
interface EmergencyAnalyzeResult {
  success: boolean;
  event_id: string;
  scenario_id: string;
  status: "processing" | "completed" | "failed";
  completed_at: string;
  execution_time_ms: number;
  errors: string[];
  
  understanding: {
    parsed_disaster: ParsedDisasterInfo;
    similar_cases_count: number;
    summary: string;
  };
  
  reasoning: {
    matched_rules: MatchedRuleInfo[];
    task_requirements: TaskRequirement[];
    capability_requirements: CapabilityRequirement[];
  };
  
  htn_decomposition: {
    scene_codes: string[];
    task_sequence: TaskSequenceItem[];
    parallel_tasks: ParallelTaskGroup[];
  };
  
  strategic: {
    active_domains: string[];
    domain_priorities: TaskDomainInfo[];
    disaster_phase: string;
    disaster_phase_name: string;
    recommended_modules: RecommendedModule[];
    transport_plans: TransportPlan[];
    transport_warnings: string[];
    safety_violations: SafetyViolation[];
    generated_reports: Record<string, string>;
  };
  
  matching: {
    candidates_count: number;
    solutions_count: number;
    pareto_solutions_count: number;
    candidates_detail: ResourceCandidate[];
  };
  
  optimization: {
    scheme_scores: SchemeScore[];
  };
  
  recommended_scheme: AllocationSolution;
  scheme_explanation: string;
  trace: ExecutionTrace;
}
```

---

## 7. 核心算法

### 7.1 HTN任务分解 (Kahn拓扑排序)
```python
def kahn_topological_sort(tasks, dependencies):
    """
    Kahn算法: 从DAG生成拓扑排序
    1. 计算所有节点入度
    2. 入度为0的节点入队
    3. 循环: 出队→更新后继入度→入度变0则入队
    4. 检测环: 输出数量 < 节点数量则有环
    """
```

### 7.2 NSGA-II多目标优化
```python
# 调用 src.planning.algorithms.optimization.pymoo_optimizer.PymooOptimizer
def nsga2_optimize(candidates, capability_requirements, n_solutions=5):
    """
    目标函数(最小化):
    - f1: 响应时间(最大ETA)
    - f2: 覆盖率缺口(1 - coverage_rate)
    - f3: 队伍数量
    
    约束: coverage_rate >= 0.7
    
    输出: Pareto前沿解集
    """
```

### 7.3 5维方案评估
```python
def score_scheme(solution, weights):
    """
    dimensions = {
        'success_rate': 救援成功率(容量覆盖率, 权重0.35)
        'response_time': 响应时间(ETA归一化, 权重0.30)
        'coverage_rate': 能力覆盖率(权重0.20)
        'risk': 风险等级(1-risk_level, 权重0.05)
        'redundancy': 冗余性(多资源覆盖比例, 权重0.10)
    }
    weighted_score = Σ(dimension_score × weight)
    """
```

---

## 8. 配置项

### 8.1 环境变量
```bash
# LLM配置
LLM_MODEL=/models/openai/gpt-oss-120b
OPENAI_BASE_URL=http://192.168.31.50:8000/v1
OPENAI_API_KEY=dummy_key
REQUEST_TIMEOUT=180

# Neo4j配置
NEO4J_URI=bolt://192.168.31.50:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxx

# Qdrant配置
QDRANT_HOST=192.168.31.50
QDRANT_PORT=6333

# Redis配置
REDIS_URL=redis://192.168.31.50:6379/0
```

### 8.2 默认优化权重
```python
default_weights = {
    "success_rate": 0.35,   # 人命关天，最高权重
    "response_time": 0.30,  # 黄金救援期72小时
    "coverage_rate": 0.20,  # 全区域覆盖
    "risk": 0.05,           # 生命优先于风险规避
    "redundancy": 0.10,     # 备用资源保障
}
```

---

## 9. 错误处理

### 9.1 设计原则
- **不降级**: 任何组件失败直接报错，不使用mock数据
- **详细日志**: 所有数据库操作记录日志
- **快速失败**: 早期阶段失败时跳转到输出节点

### 9.2 常见错误
| 错误 | 原因 | 解决方案 |
|------|------|----------|
| LLM解析失败 | 超时/模型不可用 | 检查LLM服务状态 |
| RAG检索失败 | Qdrant不可用 | 检查Qdrant服务 |
| Neo4j查询失败 | 连接/数据问题 | 检查Neo4j服务和数据 |
| 无匹配规则 | 规则条件不满足 | 检查规则trigger_conditions |
| 无能力需求 | 规则未关联能力 | 检查REQUIRES_CAPABILITY关系 |
| 无候选资源 | 位置/能力不匹配 | 扩大搜索范围 |

---

## 10. 性能指标

### 10.1 典型耗时
| 阶段 | 耗时 | 说明 |
|------|------|------|
| Phase 1: 灾情理解 | 8-12秒 | LLM+RAG并行+物理模型计算 |
| Phase 2: 规则推理 | 100-300ms | Neo4j查询 |
| Phase 2.5: HTN分解 | 100-400ms | Neo4j查询+排序 |
| Phase 2.6: 战略层 | 200-500ms | Neo4j+PG查询 |
| Phase 3: 资源匹配 | 500-800ms | PG查询+NSGA-II |
| Phase 4: 方案优化 | 5-10秒 | LLM方案解释 |
| **总计** | **40-60秒** | |

### 10.2 战略层开销
新增6个战略层节点总开销约 **1-2秒**，符合设计预期。
