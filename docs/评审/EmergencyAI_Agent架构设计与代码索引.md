# EmergencyAI Agent 架构设计与代码索引

> **版本**: 1.0  
> **更新日期**: 2025-12-04  
> **文档性质**: 专家评审技术文档  
> **项目定位**: 应急救援智能决策支持系统

---

## 1. 系统概述

### 1.1 项目背景与使命

本系统是一个面向应急救援场景的AI智能决策支持平台，旨在通过人工智能技术辅助应急指挥人员在灾害发生后快速做出科学、合理的救援决策。系统的核心价值在于：

- **缩短决策时间**：将传统人工决策的小时级响应缩短至分钟级
- **提高决策质量**：基于历史案例、专业规则和多目标优化算法生成最优方案
- **降低人为失误**：通过规则引擎和硬约束检查避免违反救援原则的决策
- **支持人机协同**：关键决策节点保留人工审核，确保最终决策权在指挥员手中

### 1.2 技术架构总览

系统采用**多智能体协作架构**，基于LangGraph状态机框架构建，核心技术栈包括：

| 技术层 | 选型 | 职责 |
|--------|------|------|
| 流程编排 | LangGraph 1.0 | 智能体状态管理、条件分支、人机交互中断 |
| 大语言模型 | vLLM (gpt-oss-120b) | 灾情语义理解、方案解释生成 |
| 检索增强 | Qdrant + Embedding | 相似历史案例检索 |
| 知识图谱 | Neo4j | TRR规则存储、任务依赖关系查询 |
| 空间数据库 | PostgreSQL + PostGIS | 救援资源管理、空间查询、路网数据 |
| 优化算法 | pymoo (NSGA-II) | 多目标Pareto优化 |
| 路径规划 | A*算法 + 真实路网 | 考虑地形的ETA计算 |

### 1.3 智能体矩阵

系统包含以下核心智能体，各司其职、协同工作：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        应急救援智能体矩阵                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ EmergencyAI     │    │ OverallPlan     │    │ EarlyWarning    │     │
│  │ Agent           │    │ Agent           │    │ Agent           │     │
│  │ ─────────────── │    │ ─────────────── │    │ ─────────────── │     │
│  │ 单事件深度分析   │    │ 总体方案生成     │    │ 预警监测与推送   │     │
│  │ 人装物资源调度   │    │ 8章节文档输出    │    │ 风险预测分析     │     │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘     │
│           │                      │                      │               │
│           ▼                      ▼                      ▼               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐     │
│  │ TaskDispatch    │    │ FrontlineRescue │    │ RoutePlanning   │     │
│  │ Agent           │    │ Agent           │    │ Agent           │     │
│  │ ─────────────── │    │ ─────────────── │    │ ─────────────── │     │
│  │ 任务智能分发     │    │ 多事件全局调度   │    │ 路径规划服务     │     │
│  │ 动态调整重分配   │    │ 事件优先级排序   │    │ 真实路网ETA      │     │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```


---

## 2. 核心智能体：EmergencyAI Agent

### 2.1 设计理念

EmergencyAI Agent是系统的核心决策引擎，采用**"AI理解 → 规则推理 → 算法优化 → AI解释"**的混合架构，充分发挥各技术的优势：

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    EmergencyAI 混合决策架构                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   输入层                    处理层                      输出层            │
│   ─────                    ─────                      ─────            │
│                                                                          │
│   ┌─────────┐         ┌─────────────────┐         ┌─────────────┐       │
│   │ 灾情描述 │ ──────▶ │ Phase 1: LLM   │         │ 推荐方案     │       │
│   │ (自然语言)│         │ 语义理解+RAG   │         │ (结构化)     │       │
│   └─────────┘         └────────┬────────┘         └──────▲──────┘       │
│                                │                         │              │
│   ┌─────────┐         ┌────────▼────────┐         ┌──────┴──────┐       │
│   │ 结构化   │ ──────▶ │ Phase 2: KG    │ ──────▶ │ Phase 4:    │       │
│   │ 输入参数 │         │ 规则推理+HTN   │         │ 规则过滤+   │       │
│   └─────────┘         └────────┬────────┘         │ LLM解释     │       │
│                                │                  └──────▲──────┘       │
│   ┌─────────┐         ┌────────▼────────┐                │              │
│   │ 约束条件 │ ──────▶ │ Phase 3: 算法  │ ───────────────┘              │
│   │ (时间/资源)│        │ NSGA-II优化    │                               │
│   └─────────┘         └─────────────────┘                               │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**设计原则**：
1. **LLM负责理解与解释**：发挥大模型在自然语言理解和生成方面的优势
2. **规则引擎负责约束**：确保决策符合应急救援专业规范
3. **优化算法负责求解**：在满足约束的前提下寻找最优解
4. **人工负责最终决策**：关键节点保留人工审核权

### 2.2 四阶段流水线架构

```
START
  │
  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 1: 灾情理解 (Understanding)                                        │
│ ─────────────────────────────────────────────────────────────────────── │
│ • understand_disaster: LLM解析灾情描述，提取结构化信息                    │
│ • enhance_with_cases: RAG检索相似历史案例，增强理解                       │
│                                                                         │
│ 输出: ParsedDisasterInfo + SimilarCases                                 │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼ (条件判断: 灾情解析成功?)
┌───────────────────────────────────���─────────────────────────────────────┐
│ Phase 2: 规则推理 (Reasoning)                                            │
│ ─────────────────────────────────────────────────────────────────────── │
│ • query_rules: 从Neo4j查询TRR(Trigger-Response-Resource)规则            │
│ • apply_rules: 根据灾情特征匹配适用规则，推导能力需求                      │
│ • htn_decompose: HTN层次任务网络分解，生成任务执行序列                    │
│ • classify_domains: 任务域分类（生命救援/疏散/工程/物资/危险控制）         │
│ • apply_phase_priority: 根据灾害阶段调整任务优先级                        │
│ • assemble_modules: 装配预编组救援模块                                   │
│                                                                         │
│ 输出: MatchedRules + TaskSequence + RecommendedModules                  │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼ (条件判断: 有匹配规则且任务序列非空?)
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 3: 资源匹配 (Matching)                                             │
│ ─────────────────────────────────────────────────────────────────────── │
│ • match_resources: PostGIS空间查询可用队伍，计算真实路径ETA               │
│ • optimize_allocation: NSGA-II多目标优化，生成Pareto最优方案集            │
│ • check_transport: 运力检查，评估运输能力缺口                             │
│                                                                         │
│ 人装物三维调度:                                                          │
│   - 人: 队伍调度 (ResourceSchedulingCore)                                │
│   - 装: 装备调度 (EquipmentScheduler)                                    │
│   - 物: 物资需求计算 (SupplyDemandCalculator, 基于Sphere国际标准)         │
│                                                                         │
│ 输出: AllocationSolutions + EquipmentAllocations + SupplyRequirements   │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼ (条件判断: 有候选方案?)
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 4: 方案优化 (Optimization)                                         │
│ ─────────────────────────────────────────────────────────────────────── │
│ • filter_hard_rules: 硬规则过滤，排除违反强制约束的方案                    │
│ • check_safety_rules: 安全规则检查                                       │
│ • score_soft_rules: 软规则评分，5维评估体系加权计算                       │
│ • explain_scheme: LLM生成人类可读的方案解释                              │
│ • generate_reports: 生成初报/日报等标准报告                              │
│                                                                         │
│ 5维评估体系:                                                             │
│   - 成功率 (0.35): 人命关天，最高权重                                    │
│   - 响应时间 (0.30): 黄金救援期72小时                                    │
│   - 覆盖率 (0.20): 全区域能力覆盖                                        │
│   - 风险 (0.05): 生命优先于风险规避                                      │
│   - 冗余性 (0.10): 备用资源保障                                          │
│                                                                         │
│ 输出: RecommendedScheme + SchemeExplanation + Reports                   │
└─────────────────────────────────────────────────────────────────────────┘
  │
  ▼
generate_output → END
```


### 2.3 状态定义与数据流

EmergencyAI采用强类型状态定义，确保数据流转的类型安全：

```python
# 核心状态类型 (src/agents/emergency_ai/state.py)

class EmergencyAIState(TypedDict):
    """应急AI混合系统状态 - 包含4个阶段的中间结果和最终输出"""
    
    # ========== 输入 ==========
    event_id: str                    # 事件ID
    scenario_id: str                 # 想定ID
    disaster_description: str        # 自然语言灾情描述
    structured_input: Dict           # 结构化输入（含location坐标）
    constraints: Dict                # 约束条件（最大响应时间、最大队伍数等）
    optimization_weights: Dict       # 5维评估权重配置
    
    # ========== Phase 1 输出 ==========
    parsed_disaster: ParsedDisasterInfo   # LLM解析的灾情结构化信息
    similar_cases: List[SimilarCase]      # RAG检索的相似历史案例
    
    # ========== Phase 2 输出 ==========
    matched_rules: List[MatchedTRRRule]   # 匹配的TRR规则
    scene_codes: List[str]                # 场景代码 ["S1", "S2"]
    task_sequence: List[TaskSequenceItem] # 拓扑排序后的任务执行序列
    recommended_modules: List[Module]     # 推荐的预编组模块
    
    # ========== Phase 3 输出 ==========
    resource_candidates: List[...]        # 候选队伍（人）
    allocation_solutions: List[...]       # 分配方案
    equipment_allocations: List[...]      # 装备分配（装）
    supply_requirements: List[...]        # 物资需求（物）
    
    # ========== Phase 4 输出 ==========
    recommended_scheme: AllocationSolution # 推荐方案
    scheme_explanation: str               # 方案解释
    generated_reports: Dict[str, str]     # 生成的报告
    
    # ========== 追踪信息 ==========
    trace: Dict[str, Any]                 # 执行追踪（用于可解释性）
    errors: List[str]                     # 错误列表
```

### 2.4 关键数据结构

#### 2.4.1 灾情解析结果

```python
class ParsedDisasterInfo(TypedDict):
    """LLM解析的灾情结构化信息"""
    disaster_type: str           # 灾害类型: earthquake/fire/hazmat/flood等
    location: Dict[str, float]   # 位置: {longitude, latitude}
    severity: str                # 严重程度: critical/high/medium/low
    magnitude: Optional[float]   # 震级（地震专用）
    has_building_collapse: bool  # 是否有建筑倒塌
    has_trapped_persons: bool    # 是否有被困人员
    estimated_trapped: int       # 预估被困人数
    has_secondary_fire: bool     # 是否有次生火灾
    has_hazmat_leak: bool        # 是否有危化品泄漏
    affected_population: int     # 受影响人口
    disaster_level: str          # 灾情等级(I-IV)
```

#### 2.4.2 任务-资源分配（对齐杀伤链路径概念）

```python
class TaskResourceAssignment(TypedDict):
    """
    任务-资源分配 - 对应军事系统的杀伤链路径概念
    
    军事系统示例: "诱敌开机(UCAV-F_6) → 无源定位(J-35_4) → 稳定跟踪(UCAV-F_6)"
    救援系统示例: "生命探测(搜救队A) → 结构支撑(工程队B) → 伤员救治(医疗队C)"
    """
    task_id: str              # HTN任务ID (如 EM006)
    task_name: str            # 任务名称 (如 "生命探测")
    resource_id: str          # 执行资源ID
    resource_name: str        # 执行资源名称 (如 "消防搜救一队")
    resource_type: str        # 资源类型 (如 "FIRE_TEAM")
    execution_sequence: int   # 执行顺序 (从1开始)
    phase: str                # 任务阶段 (detect/assess/execute等)
    eta_minutes: float        # 预计到达/执行时间(分钟)
    match_score: float        # 任务-资源匹配分数 (0-1)
    match_reason: str         # 匹配原因说明
```

#### 2.4.3 分配方案

```python
class AllocationSolution(TypedDict):
    """资源分配方案"""
    solution_id: str                      # 方案ID
    allocations: List[Dict]               # 分配详情
    task_assignments: List[Dict]          # 任务-资源分配序列
    execution_path: str                   # 执行路径字符串
    total_score: float                    # 5维评估总分
    response_time_min: float              # 预计响应时间(分钟)
    coverage_rate: float                  # 能力覆盖率
    total_rescue_capacity: int            # 总救援容量
    capacity_coverage_rate: float         # 容量覆盖率
    capacity_warning: Optional[str]       # 容量不足警告
```


---

## 3. 规则引擎设计

### 3.1 TRR规则体系

TRR (Trigger-Response-Resource) 规则是系统的核心决策依据，存储于Neo4j知识图谱中：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRR规则知识图谱结构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   (:Trigger)                (:Response)               (:Resource)       │
│   ┌─────────┐              ┌───────────┐             ┌───────────┐      │
│   │ type    │──TRIGGERS──▶│ tasks     │──REQUIRES──▶│capabilities│     │
│   │ severity│              │ priority  │             │ quantity  │      │
│   │ context │              │ deadline  │             │ type      │      │
│   └─────────┘              └───────────┘             └───────────┘      │
│                                                                         │
│   示例:                                                                  │
│   (:Trigger {type:"earthquake", severity:"high", has_trapped:true})     │
│       ──[:TRIGGERS]──▶                                                  │
│   (:Response {tasks:["LIFE_DETECTION","STRUCTURAL_RESCUE"]})            │
│       ──[:REQUIRES]──▶                                                  │
│   (:Resource {capabilities:["LIFE_DETECTION"], quantity:2})             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 规则引擎实现

```python
# src/agents/rules/engine.py

class TRRRuleEngine:
    """
    TRR触发规则引擎
    
    基于YAML规则库进行条件匹配，支持：
    - 多条件组合（AND/OR逻辑）
    - 嵌套字段访问（如location.lat）
    - 多种比较操作符（eq/ne/gt/gte/lt/lte/in/contains/regex）
    - 权重排序
    """
    
    def evaluate(self, context: Dict[str, Any]) -> List[MatchedRule]:
        """评估上下文，返回按权重降序排列的匹配规则列表"""
        
    def check_hard_rules(self, scheme_data: Dict) -> List[HardRuleResult]:
        """检查硬约束规则，返回所有规则的检查结果"""
        
    def is_scheme_feasible(self, results: List[HardRuleResult]) -> bool:
        """判断方案是否可行（无否决规则触发）"""
```

### 3.3 硬规则与软规则

| 规则类型 | 作用 | 违反后果 | 示例 |
|---------|------|---------|------|
| **硬规则** | 强制约束 | 方案被否决 | 响应时间不得超过黄金救援期 |
| **软规则** | 评分依据 | 扣分但不否决 | 优先调度距离最近的队伍 |

硬规则检查流程：
```
方案数据 → 硬规则引擎 → 检查结果
                         │
                         ├─ REJECT: 方案被否决，不进入后续评分
                         │
                         └─ WARN: 生成警告，继续评分
```

---

## 4. HTN任务分解

### 4.1 场景-任务映射

系统定义了5类标准场景，每个场景对应一组元任务链：

| 场景代码 | 场景名称 | 触发条件 | 典型任务链 |
|---------|---------|---------|-----------|
| S1 | 地震主灾 | disaster_type=earthquake | EM01→EM02→EM06→EM07→EM10 |
| S2 | 次生火灾 | has_secondary_fire=true | EM03→EM08→EM11 |
| S3 | 危化品泄漏 | has_hazmat_leak=true | EM04→EM09→EM12 |
| S4 | 山洪泥石流 | disaster_type=flood/debris_flow | EM05→EM13→EM14 |
| S5 | 暴雨内涝 | disaster_type=waterlogging | EM15→EM16→EM17 |

### 4.2 元任务库

元任务定义存储于 `config/emergency/mt_library.json`：

```json
{
  "EM01": {
    "name": "无人机广域侦察",
    "category": "sensing",
    "phase": "detect",
    "precondition": "灾害发生",
    "effect": "获取灾区全貌影像",
    "outputs": ["灾区影像", "初步损失评估"],
    "typical_scenes": ["S1", "S2", "S3", "S4", "S5"],
    "duration_range": {"min": 10, "max": 30},
    "required_capabilities": ["UAV_RECONNAISSANCE"],
    "risk_level": "low"
  },
  "EM06": {
    "name": "人员搜救",
    "category": "search_rescue",
    "phase": "execute",
    "precondition": "完成生命探测",
    "effect": "救出被困人员",
    "outputs": ["获救人员", "伤亡统计"],
    "typical_scenes": ["S1"],
    "duration_range": {"min": 60, "max": 480},
    "required_capabilities": ["STRUCTURAL_RESCUE", "LIFE_DETECTION"],
    "risk_level": "high"
  }
}
```

### 4.3 任务拓扑排序

基于Kahn算法进行拓扑排序，确保任务按依赖关系正确执行：

```
输入: 多场景任务链 + 任务依赖关系
      │
      ▼
┌─────────────────────────────────────┐
│ 1. 任务链合并去重                    │
│    S1: [EM01, EM02, EM06]           │
│    S2: [EM03, EM08]                 │
│    合并: [EM01, EM02, EM03, EM06, EM08] │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 2. 构建依赖图                        │
│    EM01 → EM02 → EM06               │
│    EM01 → EM03 → EM08               │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 3. Kahn拓扑排序                      │
│    序列: [EM01, EM02, EM03, EM06, EM08] │
│    并行组: {EM02, EM03} 可并行执行    │
└─────────────────────────────────────┘
      │
      ▼
输出: TaskSequence + ParallelGroups
```


---

## 5. 人装物三维资源调度

### 5.1 整体架构

基于学术研究（OR-LLM-Agent, PLOS ONE 2025）的三层架构设计：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    人装物三维资源调度架构                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                  IntegratedResourceSchedulingCore                │   │
│   │                       (整合调度入口)                              │   │
│   └───────────────────────────┬─────────────────────────────────────┘   │
│                               │                                         │
│           ┌───────────────────┼───────────────────┐                     │
│           ▼                   ▼                   ▼                     │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐            │
│   │ 人: 队伍调度   │   │ 装: 装备调度   │   │ 物: 物资计算   │            │
│   │ ───────────── │   │ ───────────── │   │ ───────────── │            │
│   │ PostGIS查询   │   │ 能力→装备映射  │   │ Sphere标准    │            │
│   │ 真实路径ETA   │   │ 贪心分配策略   │   │ 人均/天计算   │            │
│   │ NSGA-II优化   │   │ 优先级排序     │   │ 5种灾害类型   │            │
│   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘            │
│           │                   │                   │                     │
│           └───────────────────┼───────────────────┘                     │
│                               ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                   DatabaseRouteEngine                            │   │
│   │              (PostGIS路网 + A*路径规划)                           │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 队伍调度（人）

#### 5.2.1 ETA计算改进

**旧方案（已废弃）**：
```python
eta = 直线距离 × 1.4 / 平均速度  # 简单估算，误差大
```

**新方案（真实路径规划）**：
```python
# 考虑因素：
# 1. 真实路网拓扑
# 2. 道路类型（高速/国道/山路）
# 3. 地形坡度
# 4. 车辆类型（全地形/普通）
# 5. 灾害影响区域绕行

route = DatabaseRouteEngine.plan_route(
    origin=team.base_location,
    destination=disaster_location,
    vehicle=team.primary_vehicle
)
eta = route.duration_seconds / 60  # 分钟
```

#### 5.2.2 车辆参数配置

```python
TEAM_VEHICLE_PROFILES = {
    "fire_rescue": VehicleProfile(
        speed_kmh=60.0,           # 消防车城市道路速度
        mountain_speed_kmh=35.0,  # 山区道路降速
        is_all_terrain=True,      # 消防车通常有越野能力
        road_factor=1.3,          # 城市道路系数
    ),
    "medical": VehicleProfile(
        speed_kmh=70.0,           # 救护车速度较快
        mountain_speed_kmh=40.0,
        is_all_terrain=False,     # 标准救护车非全地形
        road_factor=1.25,
    ),
    "engineering": VehicleProfile(
        speed_kmh=50.0,           # 工程车辆速度较慢
        mountain_speed_kmh=30.0,
        is_all_terrain=True,      # 工程车辆通常有越野能力
        road_factor=1.4,
    ),
}
```

#### 5.2.3 NSGA-II多目标优化

优化目标：
1. **最小化响应时间**：所有队伍到达的最大ETA
2. **最大化能力覆盖**：覆盖所有需求能力
3. **最小化资源消耗**：调度最少的队伍数量
4. **最大化冗余性**：关键能力有备份

```python
# pymoo NSGA-II配置
algorithm = NSGA2(
    pop_size=100,
    n_offsprings=50,
    sampling=IntegerRandomSampling(),
    crossover=SBX(prob=0.9, eta=15),
    mutation=PM(eta=20),
    eliminate_duplicates=True
)
```

### 5.3 装备调度（装）

#### 5.3.1 能力-装备映射

```sql
-- capability_equipment_v2 表
| 能力代码 | 装备类型 | 装备名称 | 最少数量 | 优先级 |
|----------|---------|----------|---------|--------|
| LIFE_DETECTION | supply | 雷达生命探测仪 | 1 | required |
| LIFE_DETECTION | device | 搜救机器狗 | 1 | optional |
| STRUCTURAL_RESCUE | supply | 液压破拆工具组 | 2 | required |
| WATER_RESCUE | supply | 冲锋舟 | 1 | required |
| WATER_RESCUE | device | 救援无人艇 | 1 | optional |
```

#### 5.3.2 分配策略

```python
class EquipmentScheduler:
    """装备调度器 - 贪心策略"""
    
    async def schedule(self, capability_requirements):
        # 1. 查询能力→装备映射
        mappings = await self._get_capability_mappings(capability_requirements)
        
        # 2. 按优先级排序（required > recommended > optional）
        sorted_mappings = sorted(mappings, key=lambda m: PRIORITY_ORDER[m.priority])
        
        # 3. 贪心分配（距离最近优先）
        allocations = []
        for mapping in sorted_mappings:
            available = await self._find_available_equipment(
                mapping.equipment_code,
                destination=self.disaster_location
            )
            if available:
                allocations.append(self._allocate(available[0], mapping))
        
        return EquipmentSchedulingResult(allocations=allocations)
```

### 5.4 物资需求计算（物）

#### 5.4.1 Sphere国际人道主义标准

系统采用Sphere标准（人道主义宪章和人道主义响应最低标准）计算物资需求：

```python
class SphereDemandCalculator:
    """基于Sphere标准的物资需求计算器"""
    
    # 标准配置（参考GB/T 29426）
    STANDARDS = {
        "earthquake": {
            "饮用水": {"per_person_per_day": 2.5, "unit": "liter", "priority": "critical"},
            "应急食品": {"per_person_per_day": 0.5, "unit": "kg", "priority": "critical"},
            "救灾帐篷": {"per_person_per_day": 0.2, "unit": "unit", "priority": "high"},
            "棉被": {"per_person_per_day": 1.0, "unit": "piece", "priority": "high"},
        },
        "flood": {
            "救生衣": {"per_person_per_day": 1.0, "unit": "piece", "priority": "critical"},
            "饮用水": {"per_person_per_day": 3.0, "unit": "liter", "priority": "critical"},
        },
    }
    
    def calculate(self, disaster_type, affected_count, duration_days):
        """
        计算物资需求
        
        公式: 需求量 = 受灾人数 × 人均每天 × 持续天数
        """
        requirements = []
        standards = self.STANDARDS.get(disaster_type, {})
        
        for supply_name, config in standards.items():
            quantity = affected_count * config["per_person_per_day"] * duration_days
            requirements.append(SupplyRequirement(
                supply_name=supply_name,
                quantity=quantity,
                unit=config["unit"],
                priority=config["priority"]
            ))
        
        return requirements
```

#### 5.4.2 计算示例

**场景**：地震，1000人受灾，预计持续3天

| 物资 | 人均/天 | 计算 | 需求量 |
|------|--------|------|--------|
| 饮用水 | 2.5升 | 1000 × 2.5 × 3 | 7,500升 |
| 应急食品 | 0.5kg | 1000 × 0.5 × 3 | 1,500kg |
| 救灾帐篷 | 0.2顶 | 1000 × 0.2 × 3 | 600顶 |
| 棉被 | 1.0条 | 1000 × 1.0 × 3 | 3,000条 |


---

## 6. 其他核心智能体

### 6.1 OverallPlanAgent - 总体方案生成

**职责**：生成符合应急预案模板的8章节正式文档

**技术特点**：
- 集成CrewAI进行态势感知
- 集成MetaGPT进行资源计算
- Human-in-the-loop审批流程
- 支持状态持久化和恢复

```python
# src/agents/overall_plan/agent.py

class OverallPlanAgent:
    """总体救灾方案生成Agent"""
    
    async def trigger(self, scenario_id: str) -> TriggerPlanResponse:
        """触发方案生成"""
        
    async def get_status(self, task_id: str) -> PlanStatusResponse:
        """查询生成状态"""
        
    async def approve(self, task_id: str, decision: str) -> ApproveResponse:
        """处理指挥员审批"""
        
    async def get_document(self, task_id: str) -> DocumentResponse:
        """获取最终文档"""
```

**工作流程**：
```
load_context → situational_awareness → resource_calculation 
    → human_review (HITL中断) → document_generation → END
```

**输出章节**：
1. 总体描述
2. 当前灾情初步评估
3. 组织指挥
4. 救援力量部署与任务分工
5. 次生灾害预防与安全措施
6. 通信与信息保障
7. 物资调配与运输保障
8. 救援力量自身保障

### 6.2 EarlyWarningAgent - 预警监测

**职责**：实时监测灾害数据变化，生成预警并推送

**技术特点**：
- 支持预警流程和风险预测两种模式
- 基于距离的预警级别判定
- WebSocket实时推送

```python
# src/agents/early_warning/agent.py

class EarlyWarningAgent:
    """预警监测智能体"""
    
    def process_disaster_update(self, disaster_data: Dict) -> Dict:
        """处理灾害数据更新，生成预警"""
        
    def get_warning_level(self, distance_m: float) -> str:
        """根据距离获取预警级别"""
        # < 1000m: red
        # < 3000m: orange
        # < 5000m: yellow
        # >= 5000m: blue
```

**工作流程**：
```
预警流程: ingest → analyze → decide → generate → notify → END
预测流程: predict_path_risk → predict_operation_risk → predict_disaster_spread → human_review → END
```

### 6.3 TaskDispatchAgent - 任务智能分发

**职责**：将方案任务分配给执行者，支持动态调整

**技术特点**：
- 两种运行模式：初始分配 / 动态调整
- Human-in-the-loop重大决策审核
- 状态持久化支持服务重启恢复

```python
# src/agents/task_dispatch/agent.py

class TaskDispatchAgent:
    """任务智能分发Agent"""
    
    async def initial_dispatch(
        self,
        event_id: str,
        scheme_id: str,
        scheme_tasks: List[Dict],
        allocated_teams: List[Dict],
    ) -> Dict:
        """Mode 1: 初始分配"""
        
    async def handle_event(
        self,
        event_id: str,
        event_type: str,  # task_rejected/task_failed/resource_unavailable等
        task_id: str,
        reason: str,
    ) -> Dict:
        """Mode 2: 动态调整"""
        
    async def resume_with_human_decision(
        self,
        thread_id: str,
        decision: str,  # approve/reject/modify
    ) -> Dict:
        """人工决策后恢复执行"""
```

**事件类型**：
| 事件类型 | 优先级 | 处理策略 |
|---------|--------|---------|
| task_failed | high | 重新分配或升级 |
| task_rejected | high | 寻找替代执行者 |
| resource_unavailable | high | 资源重新调度 |
| new_urgent_task | critical | 立即插入调度 |
| task_timeout | medium | 催促或重分配 |

### 6.4 FrontlineRescueAgent - 多事件全局调度

**职责**：处理多个并发事件的全局资源调度

**技术特点**：
- 事件优先级排序
- 资源冲突避免
- 全局最优分配

```python
# src/agents/frontline_rescue/agent.py

class FrontlineRescueAgent:
    """多事件一线救援调度Agent"""
    
    async def plan(self, scenario_id: str) -> Dict:
        """执行多事件调度规划"""
```

**工作流程**：
```
load_context → prioritize_events → allocate_resources 
    → hard_rules_check → human_review → END
```


---

## 7. 代码索引

### 7.1 智能体模块

| 模块路径 | 核心文件 | 职责 | 代码行数 |
|---------|---------|------|---------|
| `src/agents/emergency_ai/` | agent.py, graph.py, state.py | 单事件深度分析 | ~3000行 |
| `src/agents/overall_plan/` | agent.py, graph.py | 总体方案生成 | ~800行 |
| `src/agents/early_warning/` | agent.py, graph.py | 预警监测 | ~600行 |
| `src/agents/task_dispatch/` | agent.py, graph.py | 任务分发 | ~700行 |
| `src/agents/frontline_rescue/` | agent.py, graph.py | 多事件调度 | ~400行 |
| `src/agents/route_planning/` | agent.py, graph.py | 路径规划 | ~300行 |
| `src/agents/staging_area/` | agent.py, graph.py | 集结点规划 | ~500行 |
| `src/agents/voice_commander/` | commander_graph.py | 语音指挥 | ~600行 |

### 7.2 EmergencyAI节点详情

| 节点文件 | 职责 | 关键算法/技术 |
|---------|------|-------------|
| `nodes/understanding.py` | 灾情理解 | LLM解析 + RAG检索 |
| `nodes/reasoning.py` | 规则推理 | Neo4j查询 + TRR匹配 |
| `nodes/htn_decompose.py` | HTN分解 | Kahn拓扑排序 |
| `nodes/domain_classifier.py` | 任务域分类 | 规则映射 |
| `nodes/phase_manager.py` | 阶段管理 | 优先级调整 |
| `nodes/module_assembler.py` | 模块装配 | 预编组匹配 |
| `nodes/matching.py` | 资源匹配 | PostGIS + NSGA-II |
| `nodes/transport_checker.py` | 运力检查 | 容量计算 |
| `nodes/optimization.py` | 方案优化 | 硬规则过滤 + 5维评分 |
| `nodes/safety_checker.py` | 安全检查 | 安全规则引擎 |
| `nodes/report_generator.py` | 报告生成 | 模板渲染 |
| `nodes/simulation.py` | 仿真闭环 | 预留接口 |
| `nodes/output.py` | 输出生成 | 结果封装 |

### 7.3 领域服务模块

| 模块路径 | 核心文件 | 职责 |
|---------|---------|------|
| `src/domains/resource_scheduling/` | core.py, service.py | 资源调度核心 |
| `src/domains/equipment_recommendation/` | scheduler.py | 装备调度 |
| `src/domains/supplies/` | demand_calculator.py | 物资需求计算 |
| `src/domains/routing/` | service.py | 路径规划服务 |
| `src/domains/events/` | service.py, repository.py | 事件管理 |
| `src/domains/schemes/` | service.py, repository.py | 方案管理 |
| `src/domains/tasks/` | service.py, repository.py | 任务管理 |
| `src/domains/ai_decisions/` | repository.py | AI决策日志 |

### 7.4 规则与算法模块

| 模块路径 | 核心文件 | 职责 |
|---------|---------|------|
| `src/agents/rules/` | engine.py, loader.py, models.py | TRR规则引擎 |
| `src/planning/algorithms/routing/` | db_route_engine.py | A*路径规划 |
| `src/planning/algorithms/optimization/` | nsga2_optimizer.py | NSGA-II优化 |
| `src/planning/algorithms/matching/` | capability_matcher.py | 能力匹配 |

### 7.5 基础设施模块

| 模块路径 | 核心文件 | 职责 |
|---------|---------|------|
| `src/core/` | database.py, config.py | 数据库连接、配置管理 |
| `src/infra/clients/` | llm_client.py, neo4j_client.py, qdrant_client.py | 外部服务客户端 |
| `src/infra/config/` | algorithm_config_service.py | 算法配置服务 |

### 7.6 配置文件

| 配置路径 | 用途 |
|---------|------|
| `config/emergency/mt_library.json` | 元任务库定义 |
| `config/emergency/trr_rules.json` | TRR触发规则 |
| `config/emergency/hard_rules.json` | 硬约束规则 |
| `config/emergency/decision_weights.yaml` | 5维评估权重 |
| `config/emergency/rescue_teams.yaml` | 救援队伍配置 |
| `config/emergency/disaster_types.yaml` | 灾害类型定义 |
| `config/private.yaml` | 私有配置（LLM/数据库连接等） |


---

## 8. 数据库设计

### 8.1 核心表结构

#### 8.1.1 救援资源表

```sql
-- 救援队伍
rescue_teams_v2 (
    id UUID PRIMARY KEY,
    code VARCHAR(50),              -- 队伍编码
    name VARCHAR(200),             -- 队伍名称
    team_type team_type_enum,      -- 队伍类型
    base_location GEOGRAPHY,       -- 驻地位置（PostGIS）
    total_personnel INT,           -- 总人数
    available_personnel INT,       -- 可用人数
    capability_level INT,          -- 能力等级(1-5)
    status VARCHAR(20)             -- 状态
)

-- 队伍能力
team_capabilities_v2 (
    team_id UUID REFERENCES rescue_teams_v2,
    capability_code VARCHAR(50),   -- 能力编码
    capability_name VARCHAR(100),  -- 能力名称
    proficiency_level INT,         -- 熟练度(1-5)
    max_capacity INT               -- 最大处理能力
)

-- 队伍车辆关联
team_vehicles_v2 (
    team_id UUID REFERENCES rescue_teams_v2,
    vehicle_id UUID REFERENCES vehicles_v2,
    is_primary BOOLEAN,            -- 是否主要车辆
    status VARCHAR(20)
)

-- 车辆
vehicles_v2 (
    id UUID PRIMARY KEY,
    code VARCHAR(50),
    name VARCHAR(200),
    max_speed_kmh INT,             -- 最大速度
    is_all_terrain BOOLEAN,        -- 是否全地形
    terrain_capabilities TEXT[],   -- 地形能力列表
    terrain_speed_factors JSONB    -- 地形速度系数
)
```

#### 8.1.2 装备与物资表

```sql
-- 能力→装备映射
capability_equipment_v2 (
    id UUID PRIMARY KEY,
    capability_code VARCHAR(50),   -- 能力编码
    equipment_type VARCHAR(20),    -- device/supply
    equipment_code VARCHAR(50),    -- 装备编码
    equipment_name VARCHAR(200),
    min_quantity INT DEFAULT 1,    -- 最少需求数量
    priority VARCHAR(20)           -- required/recommended/optional
)

-- 物资需求标准（参考Sphere/GB/T 29426）
supply_standards_v2 (
    id UUID PRIMARY KEY,
    disaster_type VARCHAR(50),     -- 灾害类型
    supply_code VARCHAR(50),       -- 物资编码
    supply_name VARCHAR(200),
    per_person_per_day DECIMAL,    -- 人均每天需求量
    unit VARCHAR(20),              -- 计量单位
    priority VARCHAR(20)           -- critical/high/medium/low
)

-- 装备库存
equipment_inventory_v2 (
    id UUID PRIMARY KEY,
    equipment_type VARCHAR(20),
    equipment_id UUID,
    equipment_code VARCHAR(50),
    location_type VARCHAR(20),     -- shelter/team/vehicle/warehouse
    location_id UUID,
    total_quantity INT,
    available_quantity INT
)
```

#### 8.1.3 路网表

```sql
-- 路网边
road_edges_v2 (
    id UUID PRIMARY KEY,
    from_node_id UUID,
    to_node_id UUID,
    geometry GEOGRAPHY,            -- 线段几何
    length_m FLOAT,                -- 长度(米)
    max_speed_kmh INT,             -- 限速
    road_type VARCHAR(50),         -- 道路类型
    terrain_type VARCHAR(50),      -- 地形类型
    max_gradient_percent FLOAT,    -- 最大坡度
    is_accessible BOOLEAN          -- 是否可通行
)

-- 路网节点
road_nodes_v2 (
    id UUID PRIMARY KEY,
    lon FLOAT,
    lat FLOAT
)
```

#### 8.1.4 AI决策日志表

```sql
-- AI决策日志（用于可解释性和审计）
ai_decision_logs (
    id UUID PRIMARY KEY,
    scenario_id UUID,
    event_id UUID,
    scheme_id UUID,
    decision_type VARCHAR(50),     -- 决策类型
    algorithm_used VARCHAR(100),   -- 使用的算法
    input_snapshot JSONB,          -- 输入快照
    output_result JSONB,           -- 输出结果
    confidence_score DECIMAL,      -- 置信度
    reasoning_chain JSONB,         -- 推理链（可解释性）
    processing_time_ms INT,        -- 处理时间
    created_at TIMESTAMP
)
```

### 8.2 空间查询示例

```sql
-- 查询距离灾害点50km内的可用救援队伍
SELECT 
    t.id,
    t.name,
    t.team_type,
    ST_Distance(t.base_location::geography, 
                ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326)::geography) / 1000 AS distance_km
FROM rescue_teams_v2 t
WHERE t.status = 'available'
  AND ST_DWithin(
        t.base_location::geography,
        ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326)::geography,
        50000  -- 50km
      )
ORDER BY distance_km;
```


---

## 9. API接口设计

### 9.1 EmergencyAI分析接口

**路径**: `POST /api/v1/agents/emergency/analyze`

**请求体**:
```json
{
  "event_id": "evt-001",
  "scenario_id": "scn-001",
  "disaster_description": "茂县发生6.5级地震，多处建筑倒塌，约150人被困，部分区域发生次生火灾",
  "structured_input": {
    "location": {"longitude": 103.8537, "latitude": 31.6815},
    "disaster_type": "earthquake",
    "occurred_at": "2025-12-04T10:30:00Z"
  },
  "constraints": {
    "max_response_time_hours": 2.0,
    "max_teams": 200
  },
  "optimization_weights": {
    "success_rate": 0.35,
    "response_time": 0.30,
    "coverage_rate": 0.20,
    "risk": 0.05,
    "redundancy": 0.10
  }
}
```

**响应体**:
```json
{
  "success": true,
  "event_id": "evt-001",
  "understanding": {
    "disaster_type": "earthquake",
    "severity": "critical",
    "magnitude": 6.5,
    "estimated_trapped": 150,
    "has_building_collapse": true,
    "has_secondary_fire": true,
    "affected_population": 5000
  },
  "task_sequence": [
    {"task_id": "EM01", "task_name": "无人机广域侦察", "sequence": 1, "phase": "detect"},
    {"task_id": "EM02", "task_name": "生命探测", "sequence": 2, "phase": "detect"},
    {"task_id": "EM06", "task_name": "人员搜救", "sequence": 3, "phase": "execute"}
  ],
  "recommended_scheme": {
    "solution_id": "nsga-abc123",
    "allocations": [
      {
        "resource_id": "team-001",
        "resource_name": "茂县消防救援大队",
        "assigned_capabilities": ["STRUCTURAL_RESCUE", "LIFE_DETECTION"],
        "eta_minutes": 12.5,
        "rescue_capacity": 30
      }
    ],
    "total_score": 0.87,
    "response_time_min": 25.3,
    "coverage_rate": 1.0,
    "total_rescue_capacity": 521,
    "capacity_coverage_rate": 3.47
  },
  "equipment_allocations": [
    {
      "equipment_code": "SP-RESCUE-DETECTOR",
      "equipment_name": "雷达生命探测仪",
      "allocated_quantity": 2,
      "source_name": "茂县应急物资仓库",
      "for_capability": "LIFE_DETECTION"
    }
  ],
  "supply_requirements": [
    {
      "supply_code": "SP-LIFE-WATER",
      "supply_name": "饮用水",
      "quantity": 37500.0,
      "unit": "liter",
      "priority": "critical",
      "calculation": "5000人 × 2.5升/人/天 × 3天"
    }
  ],
  "scheme_explanation": "本方案调度8支救援队伍，总救援容量521人，可在25分钟内完成首批力量到达...",
  "trace": {
    "phases_executed": ["understanding", "reasoning", "htn_decompose", "matching", "optimization"],
    "llm_calls": 2,
    "algorithms_used": ["NSGA-II", "A*", "Kahn"],
    "execution_time_ms": 4523
  },
  "errors": []
}
```

### 9.2 总体方案生成接口

**触发生成**: `POST /api/v1/agents/overall-plan/trigger`
```json
{
  "scenario_id": "scn-001"
}
```

**查询状态**: `GET /api/v1/agents/overall-plan/status/{task_id}`

**审批**: `POST /api/v1/agents/overall-plan/approve`
```json
{
  "task_id": "task-xxx",
  "decision": "approve",
  "feedback": "方案可行，同意执行"
}
```

**获取文档**: `GET /api/v1/agents/overall-plan/document/{task_id}`

### 9.3 预警接口

**处理灾害更新**: `POST /api/v1/agents/early-warning/process`
```json
{
  "disaster_data": {
    "boundary": {"type": "Polygon", "coordinates": [...]},
    "disaster_type": "earthquake",
    "severity": "high"
  },
  "scenario_id": "scn-001"
}
```

### 9.4 任务分发接口

**初始分配**: `POST /api/v1/agents/task-dispatch/initial`
```json
{
  "event_id": "evt-001",
  "scheme_id": "sch-001",
  "scheme_tasks": [...],
  "allocated_teams": [...]
}
```

**处理事件**: `POST /api/v1/agents/task-dispatch/event`
```json
{
  "event_id": "evt-001",
  "event_type": "task_rejected",
  "task_id": "EM06",
  "executor_id": "team-001",
  "reason": "执行者设备故障"
}
```


---

## 10. 架构层次与调用规范

### 10.1 分层架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         入口层 (Adapters)                                │
│   frontend_api/router   │   agents/router   │   domains/*/router        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      应用服务层 (Service)                                │
│   domains/*/service.py                                                  │
│   - 编排业务流程                                                         │
│   - 管理事务边界                                                         │
│   - 实例化 Repository 和 Core                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────────┐
│   Core (核心)      │   │   Repository      │   │   External Client     │
│   纯业务逻辑       │   │   数据访问接口     │   │   外部服务客户端       │
│   无 IO 依赖       │   │                   │   │                       │
└───────────────────┘   └───────────────────┘   └───────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        Algorithm (算法)                                │
│   planning/algorithms                                                  │
│   纯函数，无状态                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

### 10.2 核心原则

1. **依赖方向单向向下**
   ```
   入口层 → Service → Core → Algorithm
                    → Repository
                    → External Client
   ```

2. **Core层纯净**
   - ❌ 不能持有数据库会话
   - ❌ 不能持有HTTP客户端
   - ✅ 只接收Repository接口
   - ✅ 只接收领域实体/值对象

3. **Service层负责编排**
   - 实例化Repository和Core
   - 管理事务边界
   - 参数校验和错误处理

### 10.3 Agent节点调用规范

```python
# 正确示例：Agent节点调用Service
async def matching_node(state: EmergencyAIState, db: AsyncSession) -> dict:
    """Agent节点调用Service"""
    
    # 1. 使用Pydantic校验LLM输出（防止幻觉）
    try:
        request = ScheduleRequest(
            destination=state.parsed_location,
            requirements=state.capability_requirements,
        )
    except ValidationError as e:
        return {"error": f"数据校验失败: {e}"}
    
    # 2. 调用Service
    service = ResourceSchedulingService(db)
    result = await service.schedule(request)
    
    return {"scheduling_result": result}
```

---

## 11. 性能指标与监控

### 11.1 性能目标

| 指标 | 目标值 | 实测值 | 说明 |
|-----|-------|-------|------|
| 端到端延迟 | <60s | ~45s | 从输入到输出完整流程 |
| LLM调用次数 | ≤3 | 2 | 并行执行理解和解释 |
| 能力覆盖率 | ≥95% | 100% | 需求能力被满足的比例 |
| 装备满足率 | ≥80% | 90%+ | 必需装备被分配的比例 |
| 冗余度 | ≥0.5 | 0.69 | 关键能力的备份覆盖 |

### 11.2 追踪与可解释性

每次决策都记录完整的追踪信息：

```python
trace = {
    "phases_executed": ["understanding", "reasoning", "matching", "optimization"],
    "llm_calls": 2,
    "rag_calls": 1,
    "kg_calls": 3,
    "algorithms_used": ["NSGA-II", "A*", "Kahn"],
    "execution_time_ms": 4523,
    "decisions_made": [
        {"phase": "matching", "decision": "选择8支队伍", "reason": "覆盖所有能力需求"},
        {"phase": "optimization", "decision": "方案A最优", "reason": "5维评分最高"}
    ]
}
```

### 11.3 错误处理

系统采用多层错误处理机制：

1. **节点级别**：每个节点捕获异常，记录到state.errors
2. **图级别**：条件边检查错误状态，跳转到输出节点
3. **Agent级别**：统一异常处理，返回标准错误响应
4. **日志级别**：结构化日志记录，支持问题追溯

```python
# 条件边示例：检查错误后跳转
def should_continue_after_understanding(state) -> Literal["query_rules", "generate_output"]:
    if state.get("parsed_disaster") is None:
        logger.warning("灾情解析失败，跳转到输出")
        return "generate_output"
    return "query_rules"
```

---

## 12. 部署架构

### 12.1 服务组件

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           部署架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │ FastAPI     │    │ vLLM        │    │ Qdrant      │                │
│   │ Backend     │    │ LLM Server  │    │ Vector DB   │                │
│   │ :8000       │    │ :8001       │    │ :6333       │                │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │
│          │                  │                  │                        │
│          └──────────────────┼──────────────────┘                        │
│                             │                                           │
│   ┌─────────────┐    ┌──────┴──────┐    ┌─────────────┐                │
│   │ PostgreSQL  │    │ Neo4j       │    │ Redis       │                │
│   │ + PostGIS   │    │ Graph DB    │    │ Cache       │                │
│   │ :5432       │    │ :7687       │    │ :6379       │                │
│   └─────────────┘    └─────────────┘    └─────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 配置示例

```yaml
# config/private.yaml
# LLM配置
OPENAI_BASE_URL: "http://192.168.31.50:8000/v1"
LLM_MODEL: "/models/gpt-oss-120b"

# RAG配置
QDRANT_URL: "http://192.168.31.50:6333"
EMBEDDING_MODEL: "text-embedding-ada-002"

# Neo4j配置
NEO4J_URI: "bolt://192.168.31.50:7687"
NEO4J_USER: "neo4j"
NEO4J_PASSWORD: "xxx"

# PostgreSQL配置
POSTGRES_DSN: "postgresql://postgres:xxx@192.168.31.40:5432/emergency_agent"

# Redis配置
REDIS_URL: "redis://192.168.31.40:6379/0"
```

---

## 13. 总结

### 13.1 技术亮点

1. **混合决策架构**：LLM理解 + 规则约束 + 算法优化 + LLM解释，充分发挥各技术优势
2. **人装物三维调度**：完整覆盖救援资源的三个维度，基于国际标准计算物资需求
3. **真实路径规划**：基于PostGIS路网和A*算法，考虑地形和车辆特性计算ETA
4. **多目标优化**：NSGA-II生成Pareto最优解，5维评估体系量化方案质量
5. **Human-in-the-loop**：关键决策节点保留人工审核，确保最终决策权在指挥员手中
6. **可解释性**：完整的决策追踪和推理链记录，支持事后审计和复盘

### 13.2 设计原则

1. **生命至上**：成功率权重最高(0.35)，响应时间次之(0.30)
2. **规则优先**：硬规则不可违反，确保决策符合专业规范
3. **算法兜底**：在满足约束的前提下，通过优化算法寻找最优解
4. **人机协同**：AI辅助决策，人工最终把关

### 13.3 未来演进

1. **仿真闭环**：集成仿真系统，验证方案可行性
2. **学习优化**：基于历史决策数据优化规则和权重
3. **多智能体协作**：增强智能体间的协调和信息共享
4. **实时态势感知**：集成更多传感器数据，提升态势感知能力

---

> **文档维护**: 本文档随代码更新同步维护，如有疑问请联系开发团队。
