## ADDED Requirements

### Requirement: 业务域目录结构
每个业务域 MUST 遵循标准目录结构：

```
src/domains/{domain_name}/
├── __init__.py          # 导出公共接口
├── service.py           # 业务逻辑（或 {功能}_service.py）
├── repository.py        # 数据访问层
├── schemas.py           # Pydantic请求/响应模型
├── models.py            # SQLAlchemy ORM模型（如需要）
└── router.py            # FastAPI路由（如需要）
```

#### Scenario: 新建业务域
- **WHEN** 需要新增业务功能模块
- **THEN** 在src/domains/下创建独立目录
- **AND** 必须包含__init__.py、schemas.py
- **AND** 涉及数据库访问必须有repository.py

### Requirement: Service层规范
Service负责业务逻辑编排，SHALL 禁止直接操作数据库：

```python
# src/domains/routing/service.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from .repository import PlannedRouteRepository
from .schemas import PlannedRouteCreate, PlannedRouteResponse

class PlannedRouteService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PlannedRouteRepository(db)
    
    async def create_route(
        self,
        data: PlannedRouteCreate,
    ) -> PlannedRouteResponse:
        """创建规划路径"""
        # 业务逻辑
        if not data.waypoints:
            raise ValueError("路径点不能为空")
        
        # 委托给Repository
        entity = await self._repo.create(data)
        return PlannedRouteResponse.model_validate(entity)
    
    async def get_routes_by_scenario(
        self,
        scenario_id: UUID,
    ) -> List[PlannedRouteResponse]:
        """获取想定下的所有路径"""
        entities = await self._repo.find_by_scenario(scenario_id)
        return [PlannedRouteResponse.model_validate(e) for e in entities]
```

#### Scenario: Service依赖注入
- **WHEN** 创建Service实例
- **THEN** 通过构造函数注入AsyncSession
- **AND** Repository在构造函数中创建

### Requirement: Repository层规范
Repository负责数据访问，MUST 封装所有SQL操作：

```python
# src/domains/routing/repository.py
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

class PlannedRouteRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, data: PlannedRouteCreate) -> PlannedRoute:
        """创建实体"""
        entity = PlannedRoute(**data.model_dump())
        self._db.add(entity)
        await self._db.flush()
        return entity
    
    async def find_by_id(self, route_id: UUID) -> Optional[PlannedRoute]:
        """按ID查询"""
        stmt = select(PlannedRoute).where(PlannedRoute.id == route_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def find_by_scenario(self, scenario_id: UUID) -> List[PlannedRoute]:
        """按想定ID查询"""
        stmt = select(PlannedRoute).where(
            PlannedRoute.scenario_id == scenario_id
        ).order_by(PlannedRoute.created_at.desc())
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
```

#### Scenario: Repository禁止业务逻辑
- **WHEN** Repository方法执行
- **THEN** 只进行数据访问操作
- **AND** 不包含业务规则判断
- **AND** 不调用其他Service

### Requirement: Schema定义规范
开发者 MUST 使用Pydantic v2定义请求/响应模型：

```python
# src/domains/routing/schemas.py
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict

class PlannedRouteBase(BaseModel):
    """路径基础字段"""
    scenario_id: UUID
    team_id: UUID
    waypoints: List[dict] = Field(..., min_length=2)
    distance_m: float = Field(..., ge=0)
    duration_seconds: float = Field(..., ge=0)

class PlannedRouteCreate(PlannedRouteBase):
    """创建请求"""
    pass

class PlannedRouteResponse(PlannedRouteBase):
    """响应模型"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
```

#### Scenario: Schema验证
- **WHEN** 接收API请求
- **THEN** 自动使用Pydantic验证
- **AND** 验证失败返回422错误

### Requirement: 现有业务域清单
系统 SHALL 包含以下业务域（共25+个）：

**核心调度域**
| 域 | 路径 | 职责 | 关键文件 |
|---|------|------|----------|
| resource_scheduling | resource_scheduling/ | 人装物资源调度（核心） | core.py(30439行), integrated_core.py, equipment_scheduler.py(20987行), sphere_demand_calculator.py(16264行), demand_calculator.py, service.py |
| routing | routing/ | 路径规划服务 | service.py, db_route_service.py, air_service.py, alternative_routes.py, risk_detection.py, unified_service.py |

**灾情评估域**
| 域 | 路径 | 职责 | 关键文件 |
|---|------|------|----------|
| disaster | disaster/ | 灾情评估（关键！） | casualty_estimator.py(19569行), sphere_standards.py(26875行), phase_requirements.py(14334行), requirement_inferencer.py |

**资源管理域**
| 域 | 路径 | 职责 |
|---|------|------|
| resources/teams | resources/teams/ | 救援队伍管理 |
| resources/vehicles | resources/vehicles/ | 车辆管理 |
| resources/devices | resources/devices/ | 设备管理 |
| supplies | supplies/ | 物资管理 |

**任务与事件域**
| 域 | 路径 | 职责 |
|---|------|------|
| tasks | tasks/ | 任务管理 |
| events | events/ | 事件管理 |
| scenarios | scenarios/ | 想定管理 |

**位置与空间域**
| 域 | 路径 | 职责 |
|---|------|------|
| staging_area | staging_area/ | 集结区管理 |
| shelters | shelters/ | 避难所管理 |
| map_entities | map_entities/ | 地图实体管理 |

**通信与集成域**
| 域 | 路径 | 职责 |
|---|------|------|
| messages | messages/ | 消息管理 |
| websocket | websocket/ | WebSocket服务 |
| integrations | integrations/ | 外部系统集成 |

**AI决策域**
| 域 | 路径 | 职责 |
|---|------|------|
| ai_decisions | ai_decisions/ | AI决策日志 |
| equipment_recommendation | equipment_recommendation/ | 装备推荐 |
| schemes | schemes/ | 方案管理 |

**仿真与绘图域**
| 域 | 路径 | 职责 |
|---|------|------|
| simulation | simulation/ | 仿真服务 |
| movement_simulation | movement_simulation/ | 移动仿真 |
| plotting | plotting/ | 绘图服务 |

**其他服务域**
| 域 | 路径 | 职责 |
|---|------|------|
| auth | auth/ | 认证授权 |
| voice | voice/ | 语音服务 |
| weather | weather/ | 天气服务 |

#### Scenario: 域选择
- **WHEN** 需要调度救援队伍
- **THEN** 使用resource_scheduling域
- **WHEN** 需要管理队伍基础信息
- **THEN** 使用resources/teams域
- **WHEN** 需要评估灾情伤亡
- **THEN** 使用disaster域的casualty_estimator
- **WHEN** 需要计算物资需求
- **THEN** 使用disaster域的sphere_standards + requirement_inferencer

### Requirement: 整合调度核心
IntegratedResourceSchedulingCore SHALL 作为资源调度的统一入口：

```python
from src.domains.resource_scheduling import (
    IntegratedResourceSchedulingCore,
    IntegratedSchedulingRequest,
    DisasterContext,
    CapabilityRequirement,
)

async def schedule_resources(db: AsyncSession) -> IntegratedSchedulingResult:
    core = IntegratedResourceSchedulingCore(db)
    
    request = IntegratedSchedulingRequest(
        context=DisasterContext(
            disaster_type="earthquake",
            center_lon=104.06,
            center_lat=30.67,
            trapped_count=50,
        ),
        capability_requirements=[
            CapabilityRequirement(
                capability_code="SEARCH_LIFE_DETECT",
                priority=PriorityLevel.CRITICAL,
            ),
        ],
        include_team_scheduling=True,
        include_equipment_scheduling=True,
        include_supply_calculation=True,
    )
    
    result = await core.schedule(request)
    return result
```

#### Scenario: 整合调度内容
- **WHEN** 调用IntegratedResourceSchedulingCore.schedule()
- **THEN** 并行执行队伍调度、装备调度、物资计算
- **AND** 结果包含team_result、equipment_result、supply_demand

### Requirement: 配置服务
ConfigService SHALL 提供数据库配置的统一访问：

```python
from src.agents.services.config_service import ConfigService

# 异步接口
hard_rules = await ConfigService.get_hard_rules()
weights = await ConfigService.get_evaluation_weights("earthquake")
enum_map = await ConfigService.get_enum_mappings("severity")

# 同步接口（带缓存）
from src.agents.services.config_service import ConfigServiceSync
hard_rules = ConfigServiceSync.get_hard_rules()
```

#### Scenario: 配置缓存
- **WHEN** 使用ConfigServiceSync
- **THEN** 结果自动缓存（lru_cache）
- **AND** 需要刷新时调用cache_clear()

### Requirement: AlgorithmConfigService使用规范（现状）
AlgorithmConfigService 的行为分两类：
- `get_all_by_category()` 会将独立列（name/name_cn/reference/description）合并进返回的 params。
- `get_or_raise()` 当前只返回 params JSONB，不合并独立列（name_cn 等不会出现在返回值）。

```python
# config.algorithm_parameters 表结构
# 独立列: name, name_cn, reference, description
# JSONB列: params

from src.infra.config.algorithm_config_service import AlgorithmConfigService

async def load_sphere_configs(db: AsyncSession) -> dict[str, dict]:
    service = AlgorithmConfigService(db)
    
    # get_all_by_category() 自动合并独立列到params
    configs = await service.get_all_by_category("sphere")
    # configs[code] 包含 params + name + name_cn + reference + description
    
    # 调用方可直接获取中文名（仅在 get_all_by_category 返回值中）
    for code, params in configs.items():
        name_cn = params.get("name_cn", "")
        unit = params.get("unit", "")
```

#### Scenario: 配置字段获取
- **WHEN** 需要获取 name_cn 等独立列字段
- **THEN** 直接从返回的 params dict 中获取
- **AND** 不需要单独查询数据库

#### Scenario: 配置缺失处理
- **WHEN** 请求的算法配置不存在
- **THEN** AlgorithmConfigService 抛出 ConfigurationMissingError
- **AND** 不使用硬编码默认值
- **AND** 调用方必须处理此异常或让其传播

### Requirement: 前端API域
frontend_api域 SHALL 专门处理前端交互需求：

```
src/domains/frontend_api/
├── car/               # 车辆相关API
├── entities/          # 实体查询API
├── event/             # 事件API
├── layers/            # 图层API
├── message/           # 消息API
├── pending_action/    # 待处理动作API
├── recon_plan/        # 侦察计划API
├── risk_area/         # 风险区域API
├── task/              # 任务API
├── unit/              # 单位API
└── user/              # 用户API
```

#### Scenario: 前端API职责
- **WHEN** 前端需要特定格式的数据
- **THEN** 在frontend_api域中封装
- **AND** 调用底层域的Service获取数据
- **AND** 转换为前端所需格式

> 现状说明：`frontend_api/risk_area/service.py` 在查询受影响队伍时未强制 `scenario_id` 过滤，若 risk_area 缺少场景会直接跳过通知；新增接口时请评估是否需要补充场景隔离。
