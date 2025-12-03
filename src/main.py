from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from src.core.config import settings
from src.core.exceptions import AppException
from src.domains.scenarios import router as scenarios_router
from src.domains.resources import vehicles_router, teams_router, devices_router
from src.domains.events import router as events_router
from src.domains.schemes import router as schemes_router
from src.domains.tasks import router as tasks_router
from src.domains.websocket import router as websocket_router

from src.domains.map_entities import entity_router, layer_router
from src.domains.auth import auth_router
from src.domains.users import users_router
from src.domains.shelters import router as shelters_router
from src.domains.supplies import router as supplies_router
from src.domains.messages import router as messages_router
from src.domains.integrations import integrations_router
from src.domains.staging_area import router as staging_area_router
from src.domains.movement_simulation import movement_router
from src.domains.simulation import simulation_router
from src.domains.equipment_recommendation import router as equipment_rec_router
from src.agents import router as ai_router
from src.domains.frontend_api import frontend_router
from src.domains.frontend_api.websocket import frontend_ws_router
from src.domains.voice import voice_router, tts_router
from src.core.stomp import stomp_router, stomp_broker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Emergency Brain API",
    description="应急救援智能决策系统 API",
    version="2.0.0",
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "details": str(exc) if settings.debug else None,
        },
    )


api_router_v2 = FastAPI()
api_router_v2.include_router(scenarios_router)
api_router_v2.include_router(vehicles_router)
api_router_v2.include_router(teams_router)
api_router_v2.include_router(devices_router)
api_router_v2.include_router(events_router)
api_router_v2.include_router(schemes_router)
api_router_v2.include_router(tasks_router)
api_router_v2.include_router(websocket_router)

api_router_v2.include_router(entity_router)
api_router_v2.include_router(layer_router)
api_router_v2.include_router(auth_router)
api_router_v2.include_router(users_router)
api_router_v2.include_router(shelters_router)
api_router_v2.include_router(supplies_router)
api_router_v2.include_router(messages_router)
api_router_v2.include_router(integrations_router)
api_router_v2.include_router(staging_area_router)
api_router_v2.include_router(movement_router)
api_router_v2.include_router(simulation_router)
api_router_v2.include_router(equipment_rec_router)
api_router_v2.include_router(ai_router)
api_router_v2.include_router(tts_router)

app.mount(settings.api_prefix, api_router_v2)
# 添加 /web-api 前缀的挂载，适配前端代理
app.mount("/web-api" + settings.api_prefix, api_router_v2)

# 前端API适配层，兼容原Java后端接口路径
frontend_app = FastAPI(title="Frontend API", description="前端适配API")
frontend_app.include_router(frontend_router)
app.mount("/api/v1", frontend_app)
app.mount("/web-api/api/v1", frontend_app)

# 前端WebSocket端点 (简化STOMP协议)
# /ws/real-time 和 /web-api/ws/real-time
app.include_router(frontend_ws_router, prefix="/ws")
app.include_router(frontend_ws_router, prefix="/web-api/ws")

# 语音对话WebSocket端点
# /ws/voice/chat - 实时语音识别和对话
app.include_router(voice_router, prefix="/ws/voice")

# v2 STOMP WebSocket端点 (基于Redis Pub/Sub)
# /ws/stomp - 完整STOMP协议支持
app.include_router(stomp_router, prefix="/ws")
app.include_router(stomp_router, prefix="/web-api/ws")


@app.on_event("startup")
async def startup_event():
    """启动时初始化STOMP消息代理和移动仿真管理器"""
    await stomp_broker.start()
    logger.info("STOMP broker started")
    
    # 启动移动仿真管理器
    from src.domains.movement_simulation import get_movement_manager
    await get_movement_manager()
    logger.info("Movement simulation manager started")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时停止STOMP消息代理和移动仿真管理器"""
    # 停止移动仿真管理器
    from src.domains.movement_simulation import shutdown_movement_manager
    await shutdown_movement_manager()
    logger.info("Movement simulation manager stopped")
    
    await stomp_broker.stop()
    logger.info("STOMP broker stopped")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


@app.get("/")
async def root():
    return {
        "name": "Emergency Brain API",
        "version": "2.0.0",
        "docs": f"{settings.api_prefix}/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
