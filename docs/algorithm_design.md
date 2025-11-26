# 应急救灾协同决策系统 - 算法模块设计

> 最后更新: 2024-01  
> 状态: **已实现**

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
│  │ 损失估算     │  │ CSP匹配     │  │ 物资调度    │  │ MCTS搜索    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                 │                 │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐     │
│  │   自实现     │  │ OR-Tools    │  │ OR-Tools    │  │ pymoo       │     │
│  │  (业务逻辑)  │  │ + 贪心备用  │  │ + 自实现    │  │ + 自实现    │     │
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
│         │                 │                 │                                │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐                       │
│  │   自实现     │  │   自实现    │  │   自实现    │                       │
│  │  (规则引擎)  │  │  (业务逻辑) │  │  (灵活注入) │                       │
│  └──────────────┘  └──────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 设计原则

1. **业务逻辑优先**: 当算法核心是业务规则时，自实现比调库更有价值
2. **可解释性**: 决策过程透明，能回答"为什么这样决策"
3. **依赖精简**: 只使用确实需要的开源库（pymoo, ortools）
4. **备用方案**: 关键算法有贪心备用，不依赖外部库也能工作

---

## 二、模块目录结构（实际）

```
src/planning/algorithms/
├── __init__.py                    # 统一导出
├── base.py                        # 基类 + 通用工具
│
├── assessment/                    # 灾情评估 [自实现]
│   ├── __init__.py
│   ├── disaster_assessment.py     # 地震/洪涝/危化品评估
│   ├── secondary_hazard.py        # 次生灾害预测
│   └── loss_estimation.py         # 损失估算
│
├── matching/                      # 资源匹配 [OR-Tools + 贪心]
│   ├── __init__.py
│   ├── rescue_team_selector.py    # 救援队伍智能选择
│   ├── vehicle_cargo_matcher.py   # 车辆-物资匹配
│   └── capability_matcher.py      # CSP能力匹配
│
├── routing/                       # 路径规划 [OR-Tools + 全地形A*]
│   ├── __init__.py
│   ├── vehicle_routing.py         # VRP多车辆路径 (OR-Tools)
│   ├── offroad_engine.py          # 越野A* (DEM+水域+障碍物)
│   ├── road_engine.py             # 路网A* (NetworkX+道路等级)
│   ├── bootstrap.py               # 资源加载器
│   ├── types.py                   # Point/Obstacle等类型
│   └── logistics_scheduler.py     # 物资调度优化
│
├── optimization/                  # 多目标优化 [pymoo + 自实现]
│   ├── __init__.py
│   ├── pymoo_optimizer.py         # NSGA-II/III (pymoo)
│   └── mcts_planner.py            # MCTS任务序列 (自实现)
│
├── arbitration/                   # 冲突仲裁 [自实现]
│   ├── __init__.py
│   ├── conflict_resolver.py       # 资源冲突消解
│   └── scene_arbitrator.py        # 多场景TOPSIS仲裁
│
├── scheduling/                    # 任务调度 [自实现]
│   ├── __init__.py
│   └── task_scheduler.py          # 优先级/关键路径调度
│
└── simulation/                    # 仿真评估 [自实现]
    ├── __init__.py
    └── discrete_event_sim.py      # 离散事件仿真
```

**共计**: 7个模块，15个核心算法文件

---

## 三、核心算法详细说明

### 模块 1: 灾情评估 (`assessment/`)

**实现方式**: 自实现（业务逻辑为主）

#### disaster_assessment.py - 灾情评估

```python
class DisasterAssessment(AlgorithmBase):
    """
    支持三种灾害类型评估:
    - 地震: 烈度衰减模型 I = 1.5M - 1.5log(R) - 0.003R + 3.0
    - 洪涝: 积水深度计算
    - 危化品: 高斯烟羽扩散模型
    """
    
    def assess_earthquake(self, magnitude, depth, epicenter, ...):
        # 1. 烈度衰减计算
        # 2. 影响范围估算
        # 3. 建筑损毁率
        # 4. 伤亡估算
        # 5. 灾情等级判定 (I-IV)
```

#### secondary_hazard.py - 次生灾害预测

```python
class SecondaryHazardPredictor(AlgorithmBase):
    """
    预测四种次生灾害:
    - 火灾: P(fire) = 1 - exp(-λ * risk_score)
    - 滑坡: 安全系数FS计算 + 降雨阈值
    - 余震: Omori法则 n(t) = K(t+c)^(-p)
    - 堰塞湖: 溃坝风险评估
    """
```

#### loss_estimation.py - 损失估算

```python
class LossEstimator(AlgorithmBase):
    """
    四类损失估算:
    - 人员伤亡: 基于建筑损毁分布
    - 建筑损毁: 脆弱性曲线 P(DS>=ds|IM) = Φ((ln(IM)-μ)/σ)
    - 基础设施: 道路/桥梁/电力/供水/通信
    - 经济损失: 直接+间接损失
    """
```

---

### 模块 2: 资源匹配 (`matching/`)

**实现方式**: OR-Tools CP-SAT + 贪心备用

#### capability_matcher.py - CSP能力匹配

```python
class CapabilityMatcher(AlgorithmBase):
    """
    使用OR-Tools CP-SAT求解约束满足问题
    
    决策变量: assignment[i][j] = 1 表示资源j分配给需求i
    约束: 能力覆盖、距离限制、容量限制
    目标: 最小化总距离 或 最大化匹配质量
    
    备用: 贪心算法（OR-Tools不可用时）
    """
    
    def _solve_with_ortools(self, needs, resources, constraints):
        from ortools.sat.python import cp_model
        model = cp_model.CpModel()
        # ... CSP建模
        
    def _solve_greedy(self, needs, resources, constraints):
        # 按重要性排序，贪心分配
```

#### rescue_team_selector.py - 救援队伍选择

```python
class RescueTeamSelector(AlgorithmBase):
    """
    算法流程:
    1. 灾情特征提取 (向量化)
    2. 能力需求推断 (规则引擎)
    3. 队伍-需求匹配评分 (覆盖度*距离衰减*专业度)
    4. 组合优化 (加权集合覆盖贪心)
    """
```

---

### 模块 3: 路径规划 (`routing/`)

**实现方式**: VRP用OR-Tools，全地形路径自实现（DEM+路网+水域）

#### vehicle_routing.py - VRP多车辆路径

```python
class VehicleRoutingPlanner(AlgorithmBase):
    """
    使用OR-Tools Routing求解器
    
    支持:
    - CVRP: 容量约束
    - VRPTW: 时间窗约束
    - 多depot
    
    启发式: PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH
    备用: 贪心算法
    """
```

#### offroad_engine.py - 越野A*全地形路径规划

```python
class OffroadEngine:
    """
    基于DEM的越野A*引擎，用于路网不可达时的地面规划
    
    核心能力:
    - DEM坡度计算: 3x3窗口梯度，车辆爬坡能力约束
    - 水域规避: Shapely多边形相交检测
    - 障碍物处理: 硬约束/软约束分级
    - 车辆能力约束: 坡度、涉水深度、续航
    
    算法:
    - A*搜索: f(n) = g(n) + h(n)
    - 8方向移动，80m分辨率
    - 地理坐标系(经纬度)直接计算
    """
```

#### road_engine.py - 路网A*引擎

```python
class RoadNetworkEngine:
    """
    基于OSM路网的A*引擎，道路优先路径规划
    
    核心能力:
    - 路网图构建: Fiona读取Shapefile + NetworkX图
    - 道路等级权重: 高速1.0 → 小路2.5
    - 坡度采样: 路段端点+中点三点采样
    - 障碍物过滤: 路段级硬约束剔除
    
    与OffroadEngine配合:
    - 路网优先: 先尝试道路规划
    - 越野兜底: 道路不通时自动切换越野
    """
```

#### bootstrap.py - 路由资源加载

```python
def load_routing_resources(dem_path, roads_path, water_path) -> RoutingResources:
    """
    加载全地形路径规划所需资源:
    - DEM: rasterio读取GeoTIFF高程数据
    - 道路: Fiona读取OSM roads Shapefile  
    - 水域: Shapely多边形集合
    """
```

---

### 模块 4: 多目标优化 (`optimization/`)

**实现方式**: pymoo（多目标）+ 自实现MCTS（序列优化）

#### pymoo_optimizer.py - NSGA-II/III优化

```python
class PymooOptimizer(AlgorithmBase):
    """
    基于pymoo的多目标优化器
    
    自动选择算法:
    - 2-3个目标: NSGA-II
    - >3个目标: NSGA-III（参考点关联）
    
    应急场景目标:
    - 最小化响应时间
    - 最大化救援覆盖率
    - 最小化资源成本
    - 最小化风险
    """
    
    def solve(self, problem):
        from pymoo.algorithms.moo.nsga2 import NSGA2
        from pymoo.algorithms.moo.nsga3 import NSGA3
        # 根据目标数自动选择
```

#### mcts_planner.py - MCTS任务序列优化

```python
class MCTSPlanner(AlgorithmBase):
    """
    自实现原因: 80%是业务逻辑（状态/动作/奖励），库只是壳
    
    四阶段:
    1. Selection: UCB1选择
    2. Expansion: 扩展新节点
    3. Simulation: 随机模拟到终态
    4. Backpropagation: 回传更新
    
    应用: 任务序列优化、动态重规划
    """
```

---

### 模块 5: 冲突仲裁 (`arbitration/`)

**实现方式**: 自实现（规则引擎，不是约束问题）

#### conflict_resolver.py - 资源冲突消解

```python
class ConflictResolver(AlgorithmBase):
    """
    自实现原因: 这是业务规则问题，不是约束求解问题
    
    冲突类型:
    - 独占冲突: 多任务需要同一唯一资源
    - 容量冲突: 资源总需求超过容量
    - 时间冲突: 使用时间窗重叠
    
    消解策略:
    - 优先级: 高优先级任务优先
    - 抢占: 从低优先级任务回收
    - 延迟: 推迟低优先级任务
    - 替代: 寻找替代资源
    """
```

#### scene_arbitrator.py - 多场景优先级仲裁

```python
class SceneArbitrator(AlgorithmBase):
    """
    使用TOPSIS多准则决策分析
    
    优先级维度:
    - 生命威胁 (权重0.35)
    - 时间紧迫 (权重0.25)
    - 影响人口 (权重0.20)
    - 成功概率 (权重0.20)
    
    输出: 场景优先级排序 + 资源分配方案 + 决策说明
    """
```

---

### 模块 6: 任务调度 (`scheduling/`)

**实现方式**: 自实现（业务语义清晰）

#### task_scheduler.py - 任务调度器

```python
class TaskScheduler(AlgorithmBase):
    """
    自实现原因: 通用调度库不贴合救援场景
    
    调度策略:
    - priority_list: 优先级列表调度（贪心）
    - critical_path: 关键路径法（拓扑排序）
    
    输出:
    - 调度时隙列表
    - 甘特图数据
    - Makespan和资源利用率
    """
```

---

### 模块 7: 仿真评估 (`simulation/`)

**实现方式**: 自实现（需要灵活的随机事件注入）

#### discrete_event_sim.py - 离散事件仿真

```python
class DiscreteEventSimulator(AlgorithmBase):
    """
    自实现原因: SimPy偏确定性流程，救灾需要随机性和灵活性
    
    事件类型:
    - 任务开始/完成
    - 资源到达/释放
    - 灾情更新（恶化）
    - 道路中断
    
    评估方式: 蒙特卡洛多次仿真
    输出: 平均完成时间、成功率、置信区间
    """
```

---

## 四、统一接口规范

```python
class AlgorithmBase(ABC):
    """所有算法的基类"""
    
    def __init__(self, params: Dict = None):
        self.params = {**self.get_default_params(), **(params or {})}
    
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
        valid, msg = self.validate_input(problem)
        if not valid:
            return AlgorithmResult(status=ERROR, message=msg)
        
        start = time.time()
        result = self.solve(problem)
        result.time_ms = (time.time() - start) * 1000
        return result


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

## 五、依赖库（精简版）

```python
# requirements.txt 中算法相关依赖

# 多目标优化 - 必需
pymoo>=0.6.1              # NSGA-II/III

# 约束求解/路径规划 - 必需
ortools>=9.7.0            # VRP, CSP

# 数学计算 - 必需
scipy>=1.10.0             # 优化、插值

# 全地形路径规划 - 必需
networkx>=3.0             # 路网图结构
rasterio>=1.3.0           # DEM高程数据读取
fiona>=1.9.0              # Shapefile读取
shapely>=2.0.0            # 几何计算(水域多边形)

# 以下不需要（自实现替代）
# simpy - 离散事件仿真自实现，更灵活
# mctspy - MCTS自实现，业务逻辑占主导
```

---

## 六、开发状态

| 模块 | 文件 | 状态 | 实现方式 |
|------|------|------|----------|
| assessment | disaster_assessment.py | ✅ 完成 | 自实现 |
| assessment | secondary_hazard.py | ✅ 完成 | 自实现 |
| assessment | loss_estimation.py | ✅ 完成 | 自实现 |
| matching | rescue_team_selector.py | ✅ 完成 | 自实现 |
| matching | vehicle_cargo_matcher.py | ✅ 完成 | 自实现 |
| matching | capability_matcher.py | ✅ 完成 | OR-Tools + 贪心 |
| routing | vehicle_routing.py | ✅ 完成 | OR-Tools + 贪心 |
| routing | offroad_engine.py | ✅ 完成 | 自实现 全地形A* (DEM+水域) |
| routing | road_engine.py | ✅ 完成 | NetworkX + A* |
| routing | bootstrap.py | ✅ 完成 | 资源加载器 |
| routing | types.py | ✅ 完成 | 类型定义 |
| routing | logistics_scheduler.py | ✅ 完成 | 自实现 |
| optimization | pymoo_optimizer.py | ✅ 完成 | pymoo |
| optimization | mcts_planner.py | ✅ 完成 | 自实现 |
| arbitration | conflict_resolver.py | ✅ 完成 | 自实现 |
| arbitration | scene_arbitrator.py | ✅ 完成 | 自实现 TOPSIS |
| scheduling | task_scheduler.py | ✅ 完成 | 自实现 |
| simulation | discrete_event_sim.py | ✅ 完成 | 自实现 |

---

## 七、使用示例

### 多目标优化

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

### VRP路径规划

```python
from src.planning.algorithms import VehicleRoutingPlanner

planner = VehicleRoutingPlanner()
result = planner.run({
    "depots": [{"id": "D1", "location": {"lat": 31.2, "lng": 121.4}}],
    "tasks": [{"id": "T1", "location": {...}, "demand": 1, "time_window": {"start": 0, "end": 120}}],
    "vehicles": [{"id": "V1", "depot_id": "D1", "capacity": 5}],
    "constraints": {"use_time_windows": True}
})

for route in result.solution:
    print(f"车辆 {route['vehicle_id']}: {len(route['stops'])} 个任务点")
```

### 场景仲裁

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

## 八、设计决策说明

### 为什么大部分算法自实现？

经过 Linus 式思考分析：

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
