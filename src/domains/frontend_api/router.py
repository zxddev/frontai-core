"""
前端API主路由

挂载所有前端适配接口，统一前缀 /api/v1 和 /web-api/api/v1
"""

from fastapi import APIRouter

from .message import message_router
from .event import event_router
from .user import user_router
from .scheme import scheme_router
from .task import task_router
from .debug import debug_router
from .unit import unit_router
from .car import car_router
from .layers import layers_router
from .entities import entities_router
from .phase import phase_router
from .disaster_plan import disaster_plan_router
from .risk_area import router as risk_area_router
from .websocket import frontend_ws_router


frontend_router = APIRouter()

# 消息/事件/用户
frontend_router.include_router(message_router)
frontend_router.include_router(event_router)
frontend_router.include_router(user_router)

# 方案/任务
frontend_router.include_router(scheme_router)
frontend_router.include_router(task_router)

# 资源/车辆
frontend_router.include_router(unit_router)
frontend_router.include_router(car_router)

# 图层/实体
frontend_router.include_router(layers_router)
frontend_router.include_router(entities_router)

# 阶段状态
frontend_router.include_router(phase_router)

# 灾害预案
frontend_router.include_router(disaster_plan_router)

# 风险区域
frontend_router.include_router(risk_area_router)

# 调试接口
frontend_router.include_router(debug_router)

# WebSocket路由单独导出，需要在main.py中单独挂载
__all__ = ["frontend_router", "frontend_ws_router"]
