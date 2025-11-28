"""
仿真推演模块

架构说明：
- 仿真使用真实数据表 + 事务快照还原
- 事件注入直接调用真实的 EventService
- 仿真结束后 ROLLBACK TO SAVEPOINT 还原数据

核心组件：
- SimulationService: 仿真服务
- SimulationClock: 仿真时钟
- SimulationScenario: 仿真场景ORM模型

使用示例:
```python
from src.domains.simulation import SimulationService, SimulationScenarioCreate

# 创建仿真场景
service = SimulationService(db)
scenario = await service.create_scenario(SimulationScenarioCreate(
    name="茂县地震救援演练",
    scenario_id=scenario_uuid,
    time_scale=Decimal("2.0"),
))

# 启动仿真（创建 SAVEPOINT）
await service.start_simulation(scenario.id)

# 调整时间倍率
await service.update_time_scale(scenario.id, TimeScaleUpdateRequest(time_scale=Decimal("4.0")))

# 注入事件（直接写入真实事件表）
event_id = await service.inject_event(scenario.id, ImmediateInjectionRequest(
    event=EventTemplate(title="余震", event_type="landslide", priority="critical"),
))

# 停止仿真（ROLLBACK 还原数据）
await service.stop_simulation(scenario.id, rollback=True)

# 生成评估
await service.create_assessment(scenario.id, AssessmentCreateRequest())
```
"""

from .schemas import (
    SimulationStatus,
    SimulationSourceType,
    SimulationParticipant,
    SimulationScenarioCreate,
    SimulationScenarioResponse,
    SimulationListResponse,
    EventTemplate,
    ScheduledInjection,
    InjectionEventCreate,
    InjectionQueueResponse,
    ImmediateInjectionRequest,
    TimeScaleUpdateRequest,
    SimulationTimeResponse,
    AssessmentGrade,
    AssessmentResult,
    AssessmentResponse,
    AssessmentCreateRequest,
)
from .models import (
    SimulationScenario,
    DrillAssessment,
)
from .clock import SimulationClock
from .service import SimulationService
from .router import router as simulation_router


__all__ = [
    # 数据模型
    "SimulationStatus",
    "SimulationSourceType",
    "SimulationParticipant",
    "SimulationScenarioCreate",
    "SimulationScenarioResponse",
    "SimulationListResponse",
    "EventTemplate",
    "ScheduledInjection",
    "InjectionEventCreate",
    "InjectionQueueResponse",
    "ImmediateInjectionRequest",
    "TimeScaleUpdateRequest",
    "SimulationTimeResponse",
    "AssessmentGrade",
    "AssessmentResult",
    "AssessmentResponse",
    "AssessmentCreateRequest",
    # ORM模型
    "SimulationScenario",
    "DrillAssessment",
    # 服务
    "SimulationClock",
    "SimulationService",
    # 路由
    "simulation_router",
]
