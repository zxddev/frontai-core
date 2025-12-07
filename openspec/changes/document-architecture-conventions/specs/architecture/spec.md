## ADDED Requirements

### Requirement: 项目分层架构
项目 SHALL 采用四层架构，每层职责 MUST 明确分离：

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
│  src/agents/router.py, src/domains/*/router.py               │
├─────────────────────────────────────────────────────────────┤
│                    Agent Layer (LangGraph)                   │
│  src/agents/{agent_name}/                                    │
│  - graph.py: 状态图定义                                       │
│  - state.py: TypedDict状态                                   │
│  - nodes/: 节点实现                                          │
│  - tools/: LLM/KG/RAG工具封装                                │
├─────────────────────────────────────────────────────────────┤
│                  Domain Layer (DDD Services)                 │
│  src/domains/{domain}/                                       │
│  - service.py: 业务逻辑                                      │
│  - repository.py: 数据访问                                   │
│  - schemas.py: Pydantic模型                                  │
├─────────────────────────────────────────────────────────────┤
│                Algorithm Layer (Pure Functions)              │
│  src/planning/algorithms/                                    │
│  - optimization/: NSGA多目标优化                             │
│  - routing/: A*路径规划                                      │
│  - matching/: 能力匹配                                       │
├─────────────────────────────────────────────────────────────┤
│                Infrastructure Layer                          │
│  src/infra/: 外部服务客户端                                   │
│  src/core/: 数据库、Redis、配置                              │
└─────────────────────────────────────────────────────────────┘
```

#### Scenario: 新增功能判断开发位置
- **WHEN** 开发者需要新增一个需要LLM推理的救援决策功能
- **THEN** 应在src/agents/下创建新Agent或扩展现有Agent
- **AND** 纯算法计算部分应放在src/planning/algorithms/
- **AND** 数据库访问应通过src/domains/下的repository实现

#### Scenario: 禁止跨层直接调用
- **WHEN** Agent层需要访问数据库
- **THEN** 必须通过Domain层的Service/Repository
- **AND** 不允许Agent节点直接执行SQL

### Requirement: 目录结构规范
系统目录结构 MUST 遵循以下规范：

```
frontai-core/
├── src/
│   ├── agents/                    # Agent层
│   │   ├── __init__.py            # 导出所有Agent
│   │   ├── base/                  # 基类
│   │   │   ├── agent.py           # BaseAgent抽象类
│   │   │   └── state.py           # 基础状态定义
│   │   ├── shared/                # 共享子图和组件
│   │   │   ├── disaster_analysis.py  # 灾情分析子图
│   │   │   └── priority_scoring.py   # 优先级打分引擎
│   │   ├── services/              # Agent专用服务
│   │   │   ├── config_service.py  # 配置服务
│   │   │   └── gis_service.py     # GIS服务
│   │   ├── utils/                 # Agent工具类
│   │   │   ├── circuit_breaker.py # 熔断器
│   │   │   └── resource_lock.py   # 资源锁（8259行，防止并发冲突）
│   │   ├── rules/                 # TRR规则引擎（双轨系统）
│   │   │   ├── engine.py          # 规则引擎（11797行，本地YAML规则）
│   │   │   ├── loader.py          # 规则加载器（10541行）
│   │   │   └── models.py          # 规则模型（6082行）
│   │   ├── db/                    # 数据库查询工具模块
│   │   │   ├── schemes.py         # 方案查询
│   │   │   ├── spatial.py         # 空间查询
│   │   │   └── teams.py           # 队伍查询
│   │   ├── schemas.py             # Agent层公共Schema
│   │   ├── exceptions.py          # Agent层异常定义
│   │   ├── router.py              # AI API路由
│   │   │
│   │   ├── emergency_ai/          # 应急救援Agent ★核心
│   │   ├── early_warning/         # 预警监测Agent
│   │   ├── recon_scheduler/       # 侦察调度Agent（最复杂，含algorithms/、crewai/）
│   │   ├── recon_agent/           # 侦察规划Agent
│   │   ├── reconnaissance/        # 侦察执行Agent（CrewAI多智能体）
│   │   ├── overall_plan/          # 全局规划Agent（LangGraph+CrewAI+MetaGPT）
│   │   ├── voice_commander/       # 语音指挥Agent（多Agent架构：4个子Agent）
│   │   ├── frontline_rescue/      # 一线救援Agent
│   │   ├── staging_area/          # 集结区Agent
│   │   ├── task_dispatch/         # 任务派发Agent
│   │   ├── equipment_preparation/ # 装备准备Agent
│   │   ├── situation_plot/        # 态势标绘Agent
│   │   ├── scheme_parsing/        # 方案解析Agent
│   │   └── route_planning/        # 路径规划（函数invoke）
│   │
│   ├── domains/                   # 业务域层
│   │   ├── resource_scheduling/   # 资源调度（人装物）
│   │   ├── routing/               # 路径规划服务
│   │   ├── resources/             # 资源管理
│   │   │   ├── teams/             # 队伍
│   │   │   ├── vehicles/          # 车辆
│   │   │   └── devices/           # 设备
│   │   ├── disaster/              # 灾情评估
│   │   ├── tasks/                 # 任务管理
│   │   ├── supplies/              # 物资管理
│   │   ├── scenarios/             # 想定管理
│   │   ├── events/                # 事件管理
│   │   └── frontend_api/          # 前端专用API
│   │
│   ├── planning/                  # 算法层
│   │   ├── __init__.py
│   │   ├── adapters/              # 算法适配器
│   │   └── algorithms/
│   │       ├── base.py            # AlgorithmBase抽象类
│   │       ├── optimization/      # 多目标优化
│   │       │   ├── pymoo_optimizer.py  # NSGA-II/III
│   │       │   └── mcts_planner.py     # MCTS规划
│   │       ├── routing/           # 路径规划
│   │       │   ├── db_route_engine.py  # A*路径引擎
│   │       │   └── offroad_engine.py   # 越野路径
│   │       ├── matching/          # 能力匹配
│   │       │   └── capability_matcher.py
│   │       ├── assessment/        # 灾情评估
│   │       ├── scheduling/        # 调度算法
│   │       ├── simulation/        # 仿真算法
│   │       └── arbitration/       # 冲突仲裁
│   │
│   ├── core/                      # 核心工具层
│   │   ├── database.py            # 数据库连接池
│   │   ├── redis.py               # Redis连接
│   │   ├── config.py              # 配置管理
│   │   ├── dependencies.py        # FastAPI依赖注入
│   │   ├── exceptions.py          # 核心异常
│   │   ├── security.py            # 安全工具
│   │   ├── websocket.py           # WebSocket管理
│   │   ├── coord_transform.py     # 坐标转换
│   │   └── stomp/                 # STOMP消息协议层
│   │       ├── broker.py          # 消息代理（13557行）
│   │       ├── connection.py      # 连接管理（7066行）
│   │       ├── frames.py          # STOMP帧协议（5621行）
│   │       └── router.py          # 消息路由（11090行）
│   │
│   ├── infra/                     # 基础设施层
│   │   ├── settings.py            # 全局Settings dataclass
│   │   ├── clients/               # 外部服务客户端
│   │   │   ├── llm_client.py      # LLM客户端
│   │   │   ├── neo4j_client.py    # Neo4j客户端
│   │   │   ├── qdrant_client.py   # Qdrant客户端
│   │   │   ├── adapter_hub.py     # 设备适配器
│   │   │   ├── amap/              # 高德地图
│   │   │   ├── asr/               # 语音识别
│   │   │   ├── tts/               # 语音合成
│   │   │   └── openmeteo/         # 天气服务
│   │   ├── config/                # 配置加载
│   │   │   └── algorithm_config_service.py  # 算法配置服务（11981行）
│   │   ├── db/                    # 数据库工具
│   │   └── rag/                   # RAG工具
│   │
│   ├── main.py                    # FastAPI应用入口
│   └── tests/                     # 单元测试
│
├── config/                        # 配置文件
│   └── private.yaml               # 私有配置（不提交）
├── data/                          # 静态数据
├── scripts/                       # 运维脚本
├── sql/                           # SQL迁移脚本
├── tests/                         # 集成测试
└── openspec/                      # 规格文档
```

#### Scenario: 新建Agent目录
- **WHEN** 需要创建新的Agent
- **THEN** 必须在src/agents/下创建独立目录
- **AND** 目录内必须包含graph.py、state.py、nodes/、tools/（如需要）
- **AND** 必须在src/agents/__init__.py中导出

### Requirement: 文件命名规范
所有源代码文件 MUST 遵循命名规范：

| 文件类型 | 命名规则 | 示例 |
|---------|---------|------|
| Agent图定义 | graph.py | emergency_ai/graph.py |
| 状态定义 | state.py | emergency_ai/state.py |
| 节点实现 | {功能}.py | nodes/matching.py |
| 工具封装 | {类型}_tools.py | tools/llm_tools.py |
| Service | service.py 或 {功能}_service.py | routing/service.py |
| Repository | repository.py | tasks/repository.py |
| Schema | schemas.py | routing/schemas.py |
| Model | models.py | tasks/models.py |
| 算法 | {算法名}.py | pymoo_optimizer.py |

#### Scenario: 文件过大需拆分
- **WHEN** 单个文件超过500行代码
- **THEN** 必须按功能拆分为多个文件
- **AND** 使用__init__.py统一导出

### Requirement: 类型注解强制
所有Python代码 MUST 使用完整的类型注解：

```python
# 正确示例
from typing import Dict, List, Optional, Any
from uuid import UUID

async def match_resources(
    state: EmergencyAIState,
    db: AsyncSession,
) -> Dict[str, Any]:
    candidates: List[ResourceCandidate] = []
    ...

# 错误示例（禁止）
def match_resources(state, db):
    candidates = []
    ...
```

#### Scenario: 类型检查通过
- **WHEN** 提交代码到仓库
- **THEN** mypy类型检查必须通过
- **AND** 不允许使用Any作为返回类型（除非确实无法确定）

### Requirement: 配置管理规范
系统配置 MUST 集中管理，SHALL 禁止硬编码：

1. **环境配置**: 通过src/infra/settings.py的Settings dataclass管理
2. **业务配置**: 存储在PostgreSQL config schema下的表中
3. **算法参数**: 通过config.algorithm_parameters表配置

#### Scenario: 获取LLM配置
- **WHEN** Agent需要调用LLM
- **THEN** 必须通过Settings获取配置
- **AND** 不允许在代码中硬编码LLM地址或模型名

#### Scenario: 获取评估权重
- **WHEN** 需要获取方案评估权重
- **THEN** 必须通过ConfigService.get_evaluation_weights()
- **AND** 不允许在代码中硬编码权重值

### Requirement: 错误处理规范
系统 SHALL 禁止静默失败，MUST 显式处理错误：

1. **禁止降级**: 不允许在错误时返回默认值或空结果
2. **异常传播**: 底层异常必须传播到上层处理
3. **日志记录**: 所有异常必须记录ERROR级别日志

```python
# 正确示例
async def query_trr_rules(disaster_type: str) -> List[Dict]:
    try:
        result = driver.session().run(cypher, params)
        return list(result)
    except Exception as e:
        logger.error(f"Neo4j查询失败: {e}")
        raise RuntimeError(f"知识图谱查询失败: {e}") from e

# 错误示例（禁止）
async def query_trr_rules(disaster_type: str) -> List[Dict]:
    try:
        result = driver.session().run(cypher, params)
        return list(result)
    except Exception:
        return []  # 静默失败，禁止！
```

#### Scenario: 外部服务不可用
- **WHEN** Neo4j/Qdrant/LLM服务不可用
- **THEN** 必须抛出明确的RuntimeError
- **AND** 上层调用者决定是否重试或中断流程

### Requirement: 数据库查询过滤规范（当前实现现状）
跨场景数据查询 **理论上应包含** scenario_id 过滤，但现有实现存在例外：

- `src/domains/routing/service.py` 调用 `DatabaseRouteEngine` 时未传 `scenario_id`，灾害避障未启用。
- `src/domains/frontend_api/risk_area/service.py` 查询受影响队伍时未强制 `scenario_id` 过滤（仅当 risk_area 没有场景时会跳过）。

建议仍优先在新增代码里添加 `scenario_id` 过滤；对现有接口调用需评估是否会混入跨场景数据。

#### Scenario: 数据隔离验证
- **WHEN** 新增查询或改造接口
- **THEN** 优先包含 scenario_id 过滤条件
- **AND** 若因现有实现无法传入，需在文档中说明跨场景风险并保留现状

#### Scenario: 多场景数据查询
- **WHEN** 确实需要跨场景查询数据
- **THEN** 必须显式说明原因
- **AND** 在函数文档中标注"跨场景查询"

### Requirement: 救援系统关键日志
涉及人命安全的关键决策点 MUST 记录详细日志，便于事后追溯：

| 位置 | 日志内容 | 级别 |
|------|----------|------|
| API层 | 任务接收、完成状态、耗时 | INFO |
| 航线规划 | 区域尺寸、预检查结果、航线统计 | INFO |
| L1验证 | 设备参数、各项检查结果、失败原因 | INFO/WARNING |
| L2验证 | 地形检查、通信覆盖、中继需求 | INFO/WARNING |
| 状态转换 | 节点跳转、重试计数、熔断状态 | INFO |

#### 日志格式示例

```python
# API层
logger.info(f"[API] 接收任务: task_id={task_id}, area_size={area_km2:.2f}km²")
logger.info(f"[API] 任务完成: status={status}, duration={duration_ms}ms, plans={len(plans)}")

# 航线规划
logger.info(f"[FlightPlanning] 区域检查: {lat_span:.0f}m × {lng_span:.0f}m = {area:.2f}km²")
logger.info(f"[FlightPlanning] 预检查: feasible={feasible}, est={est_km:.1f}km, max={max_km:.1f}km")
logger.info(f"[FlightPlanning] 航线: waypoints={wps}, distance={dist_km:.2f}km, time={time_min:.1f}min")

# L1验证
logger.info(f"[L1] 设备 {device_id}: max_endurance={endurance}min, cruise_speed={speed}m/s")
logger.info(f"[L1] 航线 {plan_id} 检查结果: banzone={ok1}, energy={ok2}, time={ok3}")
logger.warning(f"[L1] 验证失败: {error_message}")

# 状态转换
logger.info(f"[Graph] 节点转换: {from_node} → {to_node}, retry={retry_count}")
```

#### Scenario: 日志缺失
- **WHEN** 提交涉及救援决策的代码
- **THEN** 必须包含关键决策点的日志
- **AND** 日志必须包含足够信息用于事后追溯

#### Scenario: 日志级别选择
- **WHEN** 记录正常执行信息
- **THEN** 使用INFO级别
- **WHEN** 记录可恢复的警告
- **THEN** 使用WARNING级别
- **WHEN** 记录导致失败的错误
- **THEN** 使用ERROR级别
