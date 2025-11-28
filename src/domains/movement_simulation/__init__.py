"""
移动仿真模块

提供车辆、无人设备、救援队伍的路径移动仿真能力。

核心组件：
- MovementSimulationManager: 移动仿真核心管理器
- BatchMovementService: 批量移动服务（编队）
- RouteInterpolator: 路径插值算法
- SpeedResolver: 速度获取
- MovementPersistence: Redis状态持久化

使用示例:
```python
from src.domains.movement_simulation import (
    get_movement_manager,
    MovementStartRequest,
    EntityType,
)

# 获取管理器
manager = await get_movement_manager()

# 启动移动
request = MovementStartRequest(
    entity_id=entity_uuid,
    entity_type=EntityType.VEHICLE,
    resource_id=vehicle_uuid,
    route=[[103.85, 31.68], [103.86, 31.69], [103.87, 31.70]],
)
response = await manager.start_movement(request, db)

# 控制移动
await manager.pause_movement(response.session_id)
await manager.resume_movement(response.session_id)
await manager.cancel_movement(response.session_id)
```
"""

from .schemas import (
    MovementState,
    EntityType,
    FormationType,
    Point,
    Waypoint,
    MovementSession,
    BatchMovementSession,
    MovementStartRequest,
    MovementStartResponse,
    BatchMovementStartRequest,
    BatchMovementStartResponse,
    MovementStatusResponse,
    ActiveSessionsResponse,
)
from .service import (
    MovementSimulationManager,
    get_movement_manager,
    shutdown_movement_manager,
)
from .batch_service import (
    BatchMovementService,
    get_batch_service,
)
from .interpolator import RouteInterpolator
from .speed_resolver import SpeedResolver, get_speed_resolver
from .persistence import MovementPersistence, get_persistence
from .router import router as movement_router


__all__ = [
    # 数据模型
    "MovementState",
    "EntityType",
    "FormationType",
    "Point",
    "Waypoint",
    "MovementSession",
    "BatchMovementSession",
    "MovementStartRequest",
    "MovementStartResponse",
    "BatchMovementStartRequest",
    "BatchMovementStartResponse",
    "MovementStatusResponse",
    "ActiveSessionsResponse",
    # 核心服务
    "MovementSimulationManager",
    "get_movement_manager",
    "shutdown_movement_manager",
    "BatchMovementService",
    "get_batch_service",
    # 工具类
    "RouteInterpolator",
    "SpeedResolver",
    "get_speed_resolver",
    "MovementPersistence",
    "get_persistence",
    # 路由
    "movement_router",
]
