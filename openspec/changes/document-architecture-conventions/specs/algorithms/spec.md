## ADDED Requirements

### Requirement: 算法基类继承
所有算法 MUST 继承AlgorithmBase抽象基类：

```python
from src.planning.algorithms.base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

class PymooOptimizer(AlgorithmBase):
    def get_default_params(self) -> Dict[str, Any]:
        """返回算法默认参数"""
        return {
            "pop_size": 100,
            "n_generations": 100,
            "algorithm": "auto",
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        """验证输入合法性"""
        if "problem" not in problem:
            return False, "需要提供problem定义"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行求解"""
        # 算法逻辑
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=solutions,
            metrics={"pareto_size": len(solutions)},
            trace={"generations": 100},
            time_ms=0,
        )
```

#### Scenario: 算法执行
- **WHEN** 调用algorithm.run(problem)
- **THEN** 自动执行validate_input→solve
- **AND** 自动记录执行时间
- **AND** 异常自动包装为AlgorithmResult(status=ERROR)

### Requirement: AlgorithmResult结构
算法返回结果 MUST 使用标准结构：

```python
@dataclass
class AlgorithmResult:
    status: AlgorithmStatus      # SUCCESS/PARTIAL/INFEASIBLE/TIMEOUT/ERROR
    solution: Any                # 求解结果
    metrics: Dict[str, float]    # 性能指标
    trace: Dict[str, Any]        # 追溯信息
    time_ms: float               # 执行时间(毫秒)
    message: str = ""            # 附加信息
```

#### Scenario: 算法失败处理
- **WHEN** 算法无法找到可行解
- **THEN** 返回status=INFEASIBLE
- **AND** message说明失败原因
- **AND** 不抛出异常

### Requirement: 现有算法清单
系统 SHALL 包含以下核心算法（共7大类）：

**1. optimization/ - 多目标优化**
| 算法 | 文件 | 用途 |
|-----|------|------|
| PymooOptimizer | pymoo_optimizer.py | NSGA-II/III多目标优化 |
| MCTSPlanner | mcts_planner.py | 蒙特卡洛树搜索 |

**2. routing/ - 路径规划**
| 算法 | 文件 | 用途 |
|-----|------|------|
| DatabaseRouteEngine | db_route_engine.py (28236行) | A*路径规划(PostGIS路网) |
| OffRoadEngine | offroad_engine.py | 越野路径规划 |
| VehicleRouting | vehicle_routing.py | 车辆路径优化 |
| RoutingConfigLoader | routing_config_loader.py | 路径配置加载 |

**3. matching/ - 能力匹配**
| 算法 | 文件 | 用途 |
|-----|------|------|
| CapabilityMatcher | capability_matcher.py | 能力-资源匹配 |
| VehicleCargoMatcher | vehicle_cargo_matcher.py | 车辆货物匹配 |

**4. assessment/ - 灾情评估（5个核心算法）**
| 算法 | 文件 | 用途 |
|-----|------|------|
| DisasterAssessment | disaster_assessment.py (19750行) | 灾情物理模型评估 |
| LossEstimation | loss_estimation.py (15809行) | 损失估算（伤亡、财产） |
| SecondaryHazard | secondary_hazard.py (14701行) | 次生灾害评估（火灾、滑坡） |
| ConfirmationScorer | confirmation_scorer.py (18540行) | 确认评分算法 |
| models/ | models/ | 物理模型（烈度衰减、高斯烟羽等） |

**5. arbitration/ - 冲突仲裁**
| 算法 | 文件 | 用途 |
|-----|------|------|
| ConflictResolver | conflict_resolver.py (11610行) | 资源冲突解决 |
| SceneArbitrator | scene_arbitrator.py (12781行) | 多场景仲裁 |

**6. scheduling/ - 任务调度**
| 算法 | 文件 | 用途 |
|-----|------|------|
| TaskScheduler | task_scheduler.py (16396行) | 任务时序调度 |

**7. simulation/ - 仿真算法**
| 算法 | 文件 | 用途 |
|-----|------|------|
| DiscreteEventSim | discrete_event_sim.py (20710行) | 离散事件仿真 |

#### Scenario: 算法选择
- **WHEN** 需要多目标资源优化(时间、成本、覆盖率)
- **THEN** 使用PymooOptimizer(NSGA-III)
- **WHEN** 需要规划避障路径
- **THEN** 使用DatabaseRouteEngine
- **WHEN** 需要评估灾情损失
- **THEN** 使用assessment/下的评估算法组合
- **WHEN** 需要解决资源冲突
- **THEN** 使用ConflictResolver或SceneArbitrator
- **WHEN** 需要仿真验证方案
- **THEN** 使用DiscreteEventSim

### Requirement: 多目标优化规范
使用PymooOptimizer时 MUST 遵循：

```python
from src.planning.algorithms.optimization.pymoo_optimizer import PymooOptimizer

optimizer = PymooOptimizer()
result = optimizer.run({
    "problem": EmergencyPlanProblem(),  # pymoo Problem对象
    "n_generations": 100,
    "pop_size": 100,
    "algorithm": "nsga3",  # 或 "nsga2"/"auto"
    "objective_names": ["response_time", "cost", "coverage"],
    "time_budget_seconds": 30,  # 可选：时间预算
})

# 结果处理
if result.status == AlgorithmStatus.SUCCESS:
    pareto_solutions = result.solution  # Pareto前沿解集
    for sol in pareto_solutions:
        print(f"方案{sol['id']}: 时间={sol['objectives']['response_time']}")
```

#### Scenario: 目标数量选择算法
- **WHEN** 优化目标≤3个
- **THEN** 自动选择NSGA-II
- **WHEN** 优化目标>3个
- **THEN** 自动选择NSGA-III

### Requirement: 路径规划规范
使用DatabaseRouteEngine时 MUST 遵循：

```python
from src.planning.algorithms.routing.db_route_engine import (
    DatabaseRouteEngine,
    VehicleCapability,
    Point,
)

async def plan_team_route(
    db: AsyncSession,
    start: Point,
    end: Point,
    vehicle: VehicleCapability,
    scenario_id: UUID,
) -> RouteResult:
    engine = DatabaseRouteEngine(db)
    
    result = await engine.plan_route(
        start=start,
        end=end,
        vehicle=vehicle,
        scenario_id=scenario_id,  # 用于查询灾害避障区
        search_radius_km=100.0,
    )
    
    return result
```

#### Scenario: 灾害区域避障
- **WHEN** 规划路径时提供scenario_id
- **THEN** 自动查询disaster_affected_areas表
- **AND** 不可通行区域完全排除
- **AND** 风险区域增加路径代价

### Requirement: 能力匹配规范
使用CapabilityMatcher时 MUST 遵循：

```python
from src.planning.algorithms.matching.capability_matcher import CapabilityMatcher

matcher = CapabilityMatcher()
result = matcher.run({
    "required_capabilities": ["SEARCH_LIFE_DETECT", "RESCUE_TRAPPED"],
    "candidate_resources": resource_list,
    "weights": {
        "capability_coverage": 0.4,
        "distance": 0.3,
        "availability": 0.3,
    },
})

# 结果：按匹配分数排序的资源列表
matched = result.solution
```

#### Scenario: 能力缺口报告
- **WHEN** 无法完全覆盖所需能力
- **THEN** 返回status=PARTIAL
- **AND** trace中包含capability_gap字段
- **AND** 列出缺失的能力代码

### Requirement: 算法性能要求
所有算法 MUST 满足性能约束：

| 算法 | 最大执行时间 | 说明 |
|-----|------------|------|
| PymooOptimizer | 60秒 | 使用time_budget_seconds控制 |
| DatabaseRouteEngine | 10秒 | 单条路径规划 |
| CapabilityMatcher | 5秒 | 匹配计算 |

#### Scenario: 超时处理
- **WHEN** 算法执行超过时间限制
- **THEN** 返回status=TIMEOUT
- **AND** solution包含当前最优解（如果有）

### Requirement: 算法配置外部化
算法参数 MUST 支持外部配置：

```python
# 从数据库config.algorithm_parameters获取
from src.infra.config.algorithm_config_service import AlgorithmConfigService

async def get_optimizer_params(disaster_type: str) -> Dict[str, Any]:
    service = AlgorithmConfigService(db)
    params = await service.get_or_raise(
        category="optimization",
        code=f"NSGA_{disaster_type.upper()}_V1",
    )
    return params
```

#### Scenario: 配置缺失
- **WHEN** 请求的算法配置不存在
- **THEN** AlgorithmConfigService抛出异常
- **AND** 不使用硬编码默认值

### Requirement: 通用数据结构
算法层 SHALL 使用统一的数据结构：

```python
from src.planning.algorithms.base import Location, TimeWindow, Resource, Task

@dataclass
class Location:
    lat: float
    lng: float
    
@dataclass  
class TimeWindow:
    start: int  # 分钟
    end: int    # 分钟

@dataclass
class Resource:
    id: str
    name: str
    type: str
    capabilities: List[str]
    location: Location
    status: str

@dataclass
class Task:
    id: str
    name: str
    required_capabilities: List[str]
    location: Optional[Location]
    priority: int
```

#### Scenario: 坐标使用
- **WHEN** 算法需要处理坐标
- **THEN** 使用Location dataclass
- **AND** 内部计算使用UTM坐标
- **AND** 输入输出使用WGS84

### Requirement: SPHERE物资需求计算规范
使用SphereDemandCalculator时 MUST 遵循国际人道主义SPHERE标准：

```python
from src.domains.disaster.sphere_demand_calculator import SphereDemandCalculator
from src.domains.disaster.schemas import CasualtyEstimate, ResponsePhase, ClimateType

async def calculate_supply_demand(
    db: AsyncSession,
    config_service: AlgorithmConfigService,
    affected_population: int,
) -> SphereDemandResult:
    # 必须检查受灾人口
    if not affected_population or affected_population <= 0:
        raise ResourceDemandError("受灾人口(affected_population)未设置")
    
    calculator = SphereDemandCalculator(db, config_service)
    
    result = await calculator.calculate(
        phase=ResponsePhase.IMMEDIATE,  # 立即响应阶段
        casualty_estimate=CasualtyEstimate(
            affected_population=affected_population,
            deaths=deaths,
            injuries=injuries,
            trapped=trapped,
        ),
        duration_days=3,  # 3天应急期
        climate=ClimateType.TEMPERATE,
    )
    
    # result.requirements 包含物资需求列表
    # 每项包含: supply_code, supply_name, quantity, unit, priority
    return result
```

SPHERE标准计算公式示例：
- 饮用水: affected_population × 20升 × duration_days
- 干粮: affected_population × 0.6kg × duration_days
- 帐篷: displaced_population ÷ 5人/顶

#### Scenario: 受灾人口为零
- **WHEN** affected_population = 0 或 NULL
- **THEN** 抛出 ResourceDemandError
- **AND** 不允许使用估算公式（如 deaths*10）替代数据库值

#### Scenario: SPHERE配置缺失
- **WHEN** config.algorithm_parameters 表缺少 sphere 类别配置
- **THEN** 抛出 ConfigurationMissingError
- **AND** 不使用硬编码默认值

#### Scenario: 物资名称显示
- **WHEN** 需要显示物资中文名称
- **THEN** 使用 AlgorithmConfigService 返回的 name_cn 字段
- **AND** 不依赖 params JSONB 中的 name_cn（可能不存在）
