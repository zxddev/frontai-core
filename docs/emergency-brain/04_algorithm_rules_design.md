# 应急救灾AI大脑 - 算法与规则设计

> 版本: 2.0  
> 更新时间: 2025-11-25  
> 状态: 已实现

---

## 一、算法体系总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           算法层 (Algorithm Layer)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  感知与评估  │  │  资源匹配   │  │  路径调度   │  │  优化搜索   │     │
│  │  Assessment  │  │  Matching   │  │  Routing    │  │  Optimization│     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                 │                 │                 │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐     │
│  │ 灾情评估     │  │ 救援队选择  │  │ VRP路径规划 │  │ NSGA-II/III │     │
│  │ 次生灾害预测 │  │ 车辆-物资   │  │ A*/Dijkstra │  │ (pymoo)     │     │
│  │ 损失估算     │  │ CSP匹配     │  │ 全地形规划  │  │ MCTS搜索    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                       │
│  │  冲突仲裁   │  │  任务调度   │  │  仿真评估   │                       │
│  │  Arbitration │  │  Scheduling │  │  Simulation │                       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                       │
│         │                 │                 │                                │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐                       │
│  │ 资源冲突消解 │  │ 优先级调度  │  │ 离散事件仿真│                       │
│  │ 场景优先级   │  │ 关键路径法  │  │ 蒙特卡洛    │                       │
│  │ TOPSIS仲裁  │  │ 甘特图生成  │  │ 方案评估    │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **业务逻辑优先**: 当算法核心是业务规则时，自实现比调库更有价值
2. **可解释性**: 决策过程透明，能回答"为什么这样决策"
3. **依赖精简**: 只使用确实需要的开源库（pymoo, ortools）
4. **备用方案**: 关键算法有贪心备用，不依赖外部库也能工作

---

## 二、算法模块目录结构

```
src/planning/algorithms/
├── __init__.py                    # 统一导出
├── base.py                        # 基类 + 通用工具
│
├── assessment/                    # 灾情评估 [自实现]
│   ├── disaster_assessment.py     # 地震/洪涝/危化品评估
│   ├── secondary_hazard.py        # 次生灾害预测
│   └── loss_estimation.py         # 损失估算
│
├── matching/                      # 资源匹配 [OR-Tools + 贪心]
│   ├── rescue_team_selector.py    # 救援队伍智能选择
│   ├── vehicle_cargo_matcher.py   # 车辆-物资匹配
│   └── capability_matcher.py      # CSP能力匹配
│
├── routing/                       # 路径规划 [OR-Tools + 全地形A*]
│   ├── vehicle_routing.py         # VRP多车辆路径 (OR-Tools)
│   ├── offroad_engine.py          # 越野A* (DEM+水域+障碍物)
│   ├── road_engine.py             # 路网A* (道路优先)
│   ├── bootstrap.py               # 资源加载器
│   ├── types.py                   # 数据类型定义
│   └── logistics_scheduler.py     # 物资调度优化
│
├── optimization/                  # 多目标优化 [pymoo + 自实现]
│   ├── pymoo_optimizer.py         # NSGA-II/III (pymoo)
│   └── mcts_planner.py            # MCTS任务序列 (自实现)
│
├── arbitration/                   # 冲突仲裁 [自实现]
│   ├── conflict_resolver.py       # 资源冲突消解
│   └── scene_arbitrator.py        # 多场景TOPSIS仲裁
│
├── scheduling/                    # 任务调度 [自实现]
│   └── task_scheduler.py          # 优先级/关键路径调度
│
└── simulation/                    # 仿真评估 [自实现]
    └── discrete_event_sim.py      # 离散事件仿真
```

**共计**: 7个模块，15个核心算法文件

---

## 三、核心算法详细说明

### 3.1 灾情评估模块 (`assessment/`)

**实现方式**: 自实现（业务逻辑为主）

#### disaster_assessment.py - 灾情评估

支持三种灾害类型评估：

| 灾害类型 | 评估模型 | 输出 |
|---------|---------|------|
| 地震 | 烈度衰减模型 `I = 1.5M - 1.5log(R) - 0.003R + 3.0` | 影响范围、建筑损毁率、伤亡估算 |
| 洪涝 | 积水深度计算 | 积水范围、交通影响、受困人数 |
| 危化品 | 高斯烟羽扩散模型 | 扩散范围、浓度分布、危险等级 |

#### secondary_hazard.py - 次生灾害预测

预测四种次生灾害：

| 次生灾害 | 预测模型 |
|---------|---------|
| 火灾 | `P(fire) = 1 - exp(-λ * risk_score)` |
| 滑坡 | 安全系数FS计算 + 降雨阈值 |
| 余震 | Omori法则 `n(t) = K(t+c)^(-p)` |
| 堰塞湖 | 溃坝风险评估 |

#### loss_estimation.py - 损失估算

四类损失估算：
- **人员伤亡**: 基于建筑损毁分布
- **建筑损毁**: 脆弱性曲线 `P(DS>=ds|IM) = Φ((ln(IM)-μ)/σ)`
- **基础设施**: 道路/桥梁/电力/供水/通信
- **经济损失**: 直接+间接损失

---

### 3.2 资源匹配模块 (`matching/`)

**实现方式**: OR-Tools CP-SAT + 贪心备用

#### capability_matcher.py - CSP能力匹配

```
决策变量: assignment[i][j] = 1 表示资源j分配给需求i
约束条件: 能力覆盖、距离限制、容量限制
优化目标: 最小化总距离 或 最大化匹配质量
备用方案: 贪心算法（OR-Tools不可用时）
```

#### rescue_team_selector.py - 救援队伍选择

算法流程：
1. 灾情特征提取（向量化）
2. 能力需求推断（规则引擎）
3. 队伍-需求匹配评分（覆盖度 × 距离衰减 × 专业度）
4. 组合优化（加权集合覆盖贪心）

---

### 3.3 路径规划模块 (`routing/`)

**实现方式**: VRP用OR-Tools，全地形路径自实现

#### vehicle_routing.py - VRP多车辆路径

使用OR-Tools Routing求解器，支持：
- **CVRP**: 容量约束
- **VRPTW**: 时间窗约束
- **多depot**: 多起点调度

#### offroad_engine.py - 越野A*全地形规划

基于DEM的越野A*引擎，用于路网不可达时的地面规划：

```python
核心能力:
- DEM坡度计算: 3x3窗口梯度，车辆爬坡能力约束
- 水域规避: Shapely多边形相交检测
- 障碍物处理: 硬约束/软约束分级
- 车辆能力约束: 坡度、涉水深度、续航

算法参数:
- A*搜索: f(n) = g(n) + h(n)
- 8方向移动，80m分辨率
- 地理坐标系(经纬度)直接计算
```

#### road_engine.py - 路网A*引擎

基于OSM路网的A*引擎，道路优先路径规划：

| 道路等级 | 权重系数 |
|---------|---------|
| 高速公路 | 1.0 |
| 国道 | 1.2 |
| 省道 | 1.5 |
| 县道 | 1.8 |
| 乡道/小路 | 2.5 |

**路网优先 + 越野兜底策略**：先尝试道路规划，不通时自动切换越野。

---

### 3.4 多目标优化模块 (`optimization/`)

#### pymoo_optimizer.py - NSGA-II/III优化

自动选择算法：
- 2-3个目标: NSGA-II
- >3个目标: NSGA-III（参考点关联）

应急场景目标：
- 最小化响应时间
- 最大化救援覆盖率
- 最小化资源成本
- 最小化风险

#### mcts_planner.py - MCTS任务序列优化

自实现原因：80%是业务逻辑（状态/动作/奖励），库只是壳

四阶段：
1. **Selection**: UCB1选择
2. **Expansion**: 扩展新节点
3. **Simulation**: 随机模拟到终态
4. **Backpropagation**: 回传更新

---

### 3.5 冲突仲裁模块 (`arbitration/`)

#### conflict_resolver.py - 资源冲突消解

冲突类型与消解策略：

| 冲突类型 | 描述 | 消解策略 |
|---------|------|---------|
| 独占冲突 | 多任务需要同一唯一资源 | 优先级抢占 |
| 容量冲突 | 资源总需求超过容量 | 部分分配+排队 |
| 时间冲突 | 使用时间窗重叠 | 延迟低优先级 |

#### scene_arbitrator.py - 多场景优先级仲裁

使用TOPSIS多准则决策分析：

| 维度 | 权重 | 说明 |
|-----|------|------|
| 生命威胁 | 0.35 | 人命关天 |
| 时间紧迫 | 0.25 | 黄金救援时间 |
| 影响人口 | 0.20 | 受灾人数 |
| 成功概率 | 0.20 | 救援可行性 |

---

### 3.6 任务调度模块 (`scheduling/`)

#### task_scheduler.py - 任务调度器

调度策略：
- **priority_list**: 优先级列表调度（贪心）
- **critical_path**: 关键路径法（拓扑排序）

输出：
- 调度时隙列表
- 甘特图数据
- Makespan和资源利用率

---

### 3.7 仿真评估模块 (`simulation/`)

#### discrete_event_sim.py - 离散事件仿真

自实现原因：SimPy偏确定性流程，救灾需要随机性和灵活性

事件类型：
- 任务开始/完成
- 资源到达/释放
- 灾情更新（恶化）
- 道路中断

评估方式：蒙特卡洛多次仿真  
输出：平均完成时间、成功率、置信区间

---

## 四、规则体系设计

### 4.1 灾害类型与等级

| 等级 | 颜色 | 响应级别 | 伤亡标准 | 影响人口 |
|-----|------|---------|---------|---------|
| I级 | 红色 | 国家级 | ≥30人死亡或≥100人重伤 | ≥10万人 |
| II级 | 橙色 | 省级 | ≥10人死亡或≥50人重伤 | ≥5万人 |
| III级 | 黄色 | 市级 | ≥3人死亡或≥10人重伤 | ≥1万人 |
| IV级 | 蓝色 | 区县级 | <3人死亡 | <1万人 |

### 4.2 触发规则 (TRR - Trigger-Response Rules)

#### 救援队伍派遣规则示例

```json
{
  "id": "TRR-EM-001",
  "name": "地震人员搜救规则",
  "if": [
    "灾害类型 = 地震",
    "建筑倒塌 = 是",
    "被困人员 >= 1",
    "黄金72小时内 = 是"
  ],
  "then": [
    "派遣队伍: 地震救援队(USAR)",
    "派遣队伍: 医疗急救队(MEDICAL)",
    "优先级: 最高",
    "携带装备: 生命探测仪、液压破拆、医疗急救包"
  ],
  "rationale": "建筑倒塌后72小时是救援黄金期，需立即派遣专业搜救力量"
}
```

#### 无人设备派遣规则示例

```json
{
  "id": "UAV-RULE-001",
  "name": "灾情侦察优先规则",
  "if": [
    "灾情态势 = 不明",
    "人员进入风险 = 高",
    "侦察无人机可用 = 是"
  ],
  "then": [
    "立即起飞: 侦察无人机(UAV-001)",
    "任务: 全景侦察 + 热成像搜索",
    "实时回传: 指挥中心",
    "禁止: 人员先行进入"
  ],
  "rationale": "人员进入前必须先用无人机侦察"
}
```

### 4.3 硬约束规则 (一票否决)

| 规则ID | 名称 | 条件 | 决策 |
|-------|------|------|------|
| HR-EM-001 | 人员安全红线 | 方案导致救援人员伤亡概率>10% | 一票否决 |
| HR-EM-002 | 二次伤害禁止 | 方案可能导致被困人员二次伤害 | 一票否决 |
| HR-EM-003 | 救援时效性 | 方案执行时间>黄金救援时间 | 一票否决 |
| HR-EM-004 | 资源可用性 | 方案所需资源>实际可用资源 | 一票否决 |
| HR-EM-005 | 道路可达性 | 救援路线不可通行且无替代 | 一票否决 |
| HR-EM-006 | 危险区域管控 | 无防护人员进入高危区域 | 一票否决 |
| HR-EM-007 | 气象条件限制 | 风力>6级且需要无人机作业 | 一票否决 |
| HR-EM-008 | 通信保障 | 方案区域无任何通信手段 | 一票否决 |

### 4.4 编组规则

| 编组ID | 模式 | 定义 | 适用场景 |
|-------|------|------|---------|
| GROUP-EM-001 | 搜救+医疗 | 1搜救队+1医疗队 | 地震搜救、建筑倒塌 |
| GROUP-EM-002 | 消防+医疗+通信 | 2消防车+1救护车+1通信车 | 建筑火灾 |
| GROUP-EM-003 | 无人协同 | 2无人机+1机器人+1指挥车 | 危化品侦察、高危区域 |
| GROUP-EM-004 | 危化品处置 | 1危化队+1消防队+1医疗队+1环保监测 | 化学品泄漏 |
| GROUP-EM-005 | 水域救援 | 2冲锋舟+1无人船+1无人机+1救护车 | 洪涝救援 |

### 4.5 决策权重配置

```yaml
decision_weights:
  # 方案评估维度权重
  evaluation_dimensions:
    life_safety:      0.40  # 生命安全
    time_efficiency:  0.25  # 时间效率
    resource_cost:    0.15  # 资源消耗
    success_rate:     0.15  # 成功概率
    secondary_risk:   0.05  # 次生风险
    
  # 场景优先级仲裁权重 (TOPSIS)
  scene_priority:
    life_threat:      0.35  # 生命威胁程度
    time_urgency:     0.25  # 时间紧迫性
    affected_people:  0.20  # 影响人数
    success_prob:     0.20  # 救援成功率
```

---

## 五、LangGraph规划流程

### 5.1 流程节点

```
START
  │
  ↓
scene_decomposition ──→ 场景拆解、AFSIM解析、语义提取
  │
  ↓
rule_application ──→ TRR规则匹配、任务推导
  │
  ↓
capability_extraction ──→ HTN任务分解、能力需求提取
  │
  ↓
resource_matching ──→ CSP资源匹配、编组生成
  │
  ↓
planning_optimization ──→ NSGA-II优化、硬规则过滤、软评分
  │
  ↓
evaluation ──→ 综合评分、结果输出
  │
  ↓
END
```

### 5.2 状态定义

```python
class PlanningState(TypedDict):
    raw_intent: str              # 原始意图
    afsim_payload: dict          # AFSIM态势数据
    scene: str                   # 场景ID
    scene_facts: List[dict]      # 场景事实
    tasks: List[str]             # 任务ID列表
    capabilities: List[str]      # 能力需求
    task_capability_map: dict    # 任务-能力映射
    grouping: List[str]          # 编组ID列表
    resource_allocation: List[str] # 资源分配
    rules: List[str]             # 命中规则
    score: float                 # 综合评分
    best_path_id: str            # 最优路径ID
    trace: List[str]             # 追溯日志
    messages: List[str]          # 消息列表
```

---

## 六、统一接口规范

### 6.1 算法基类

```python
class AlgorithmBase(ABC):
    """所有算法的基类"""
    
    @abstractmethod
    def solve(self, problem: Dict) -> AlgorithmResult:
        """求解问题"""
        pass
    
    @abstractmethod
    def validate_input(self, problem: Dict) -> Tuple[bool, str]:
        """验证输入"""
        pass
    
    @abstractmethod
    def get_default_params(self) -> Dict:
        """默认参数"""
        pass
    
    def run(self, problem: Dict) -> AlgorithmResult:
        """执行（带计时和异常处理）"""
        ...
```

### 6.2 算法结果

```python
@dataclass
class AlgorithmResult:
    status: AlgorithmStatus  # SUCCESS / PARTIAL / INFEASIBLE / ERROR
    solution: Any            # 解
    metrics: Dict[str, float]  # 指标
    trace: Dict[str, Any]    # 追溯信息（可解释性）
    time_ms: float           # 求解时间
    message: str = ""
```

---

## 七、依赖库

```python
# 多目标优化
pymoo>=0.6.1              # NSGA-II/III

# 约束求解/路径规划
ortools>=9.7.0            # VRP, CSP

# 数学计算
scipy>=1.10.0             # 优化、插值

# 全地形路径规划
networkx>=3.0             # 路网图结构
rasterio>=1.3.0           # DEM高程数据读取
fiona>=1.9.0              # Shapefile读取
shapely>=2.0.0            # 几何计算(水域多边形)

# 以下不需要（自实现替代）
# simpy - 离散事件仿真自实现，更灵活
# mctspy - MCTS自实现，业务逻辑占主导
```

---

## 八、使用示例

### 8.1 多目标优化

```python
from src.planning.algorithms import PymooOptimizer

optimizer = PymooOptimizer()
result = optimizer.run({
    "problem": EmergencyPlanProblem.create(),
    "n_generations": 100,
    "objective_names": ["响应时间", "成本", "覆盖率", "风险"]
})

for sol in result.solution[:3]:
    print(f"{sol['id']}: {sol['objectives']}")
```

### 8.2 全地形路径规划

```python
from src.planning.algorithms.routing import (
    OffroadEngine, RoadNetworkEngine,
    load_routing_resources, Point, CapabilityMetrics
)

# 加载地理数据
resources = load_routing_resources(
    dem_path="data/四川省.tif",
    roads_path="data/roads/gis_osm_roads_free_1.shp",
    water_path="data/roads/gis_osm_water_a_free_1.shp"
)

# 创建引擎
road_engine = RoadNetworkEngine(roads_path, resources.dem_dataset)
offroad_engine = OffroadEngine(resources.dem_dataset, resources.water_polygons)

# 路径规划（道路优先+越野兜底）
start = Point(lon=103.5, lat=30.5)
end = Point(lon=103.8, lat=30.7)
capability = CapabilityMetrics(slope_deg=25.0, range_km=100.0)

result = road_engine.plan_segment(start, end, capability=capability)
if result is None:
    result = offroad_engine.plan(start, end, capability=capability)

print(f"路径距离: {result.distance_m:.0f}m")
```

### 8.3 场景仲裁

```python
from src.planning.algorithms import SceneArbitrator

arbitrator = SceneArbitrator()
result = arbitrator.run({
    "scenes": [
        {"id": "S1", "name": "居民楼坍塌", "life_threat_level": 0.9, ...},
        {"id": "S2", "name": "化工厂泄漏", "life_threat_level": 0.7, ...}
    ],
    "available_resources": {...}
})

for s in result.solution:
    print(f"#{s['rank']} {s['scene_name']}: {s['rationale']}")
```

---

## 九、配置文件清单

```
config/emergency/
├── disaster_types.yaml          # 灾害类型与等级定义
├── rescue_teams.yaml            # 救援队伍能力库
├── unmanned_equipment.yaml      # 无人设备能力库
├── trr_rules.json              # 触发规则
├── hard_rules.json             # 硬约束规则
├── grouping_rules.json         # 编组规则
├── evacuation_rules.yaml       # 疏散规则
├── safe_shelter_criteria.yaml  # 安全地点标准
└── decision_weights.yaml       # 决策权重配置
```

---

## 十、开发状态

| 模块 | 文件 | 状态 | 实现方式 |
|------|------|------|----------|
| assessment | disaster_assessment.py | ✅ 完成 | 自实现 |
| assessment | secondary_hazard.py | ✅ 完成 | 自实现 |
| assessment | loss_estimation.py | ✅ 完成 | 自实现 |
| matching | rescue_team_selector.py | ✅ 完成 | 自实现 |
| matching | vehicle_cargo_matcher.py | ✅ 完成 | 自实现 |
| matching | capability_matcher.py | ✅ 完成 | OR-Tools + 贪心 |
| routing | vehicle_routing.py | ✅ 完成 | OR-Tools + 贪心 |
| routing | offroad_engine.py | ✅ 完成 | 自实现 全地形A* |
| routing | road_engine.py | ✅ 完成 | NetworkX + A* |
| optimization | pymoo_optimizer.py | ✅ 完成 | pymoo |
| optimization | mcts_planner.py | ✅ 完成 | 自实现 |
| arbitration | conflict_resolver.py | ✅ 完成 | 自实现 |
| arbitration | scene_arbitrator.py | ✅ 完成 | 自实现 TOPSIS |
| scheduling | task_scheduler.py | ✅ 完成 | 自实现 |
| simulation | discrete_event_sim.py | ✅ 完成 | 自实现 |

---

## 十一、设计决策说明

### 为什么大部分算法自实现？

1. **业务逻辑占主导**: 救灾决策系统的核心是"为什么这样决策"，不是"算法多先进"
2. **可解释性要求**: 开源库是黑盒，无法输出决策理由
3. **领域特定性**: 通用库解决的是"工厂排产"问题，不是"应急救援"问题
4. **依赖风险**: 减少版本兼容、API变更、调试困难等问题
5. **这些算法不难**: A*、MCTS、事件仿真都是教科书级别

### 什么时候用开源库？

- **pymoo**: 多目标优化算法复杂，NSGA-III需要正确的参考点关联
- **ortools**: VRP/CSP有C++核心，性能关键

### 一句话总结

> 当系统需要回答"为什么这样决策"时，自实现比调库更有价值。
