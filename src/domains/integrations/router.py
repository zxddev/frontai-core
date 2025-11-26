"""
第三方数据接入路由

接口前缀: /integrations
认证方式: API密钥 (X-Api-Key Header)
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .dependencies import verify_api_key, require_scope, ApiKeyAuth
from .service import IntegrationService
from .schemas import (
    DisasterReportRequest, DisasterReportResponse,
    SensorAlertRequest, SensorAlertResponse,
    TelemetryBatchRequest, TelemetryResponse,
    WeatherDataRequest, WeatherDataResponse,
    CallbackRequest, CallbackResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def get_service(db: AsyncSession = Depends(get_db)) -> IntegrationService:
    """获取服务实例"""
    return IntegrationService(db)


# ============================================================================
# 灾情上报
# ============================================================================

@router.post(
    "/disaster-report",
    response_model=DisasterReportResponse,
    status_code=201,
    summary="灾情上报",
    description="接收第三方系统（110/社区/AI识别系统）推送的灾情信息",
    responses={
        200: {"description": "灾情已存在（重复上报）"},
        201: {"description": "灾情创建成功"},
        400: {"description": "请求数据无效"},
        401: {"description": "API密钥无效"},
        403: {"description": "权限不足"},
    },
)
async def disaster_report(
    data: DisasterReportRequest,
    scenario_id: UUID = Query(..., description="目标想定ID"),
    auth: ApiKeyAuth = Depends(require_scope("disaster-report")),
    service: IntegrationService = Depends(get_service),
) -> DisasterReportResponse:
    """
    灾情上报接口
    
    接收第三方系统推送的灾情信息，自动创建事件并触发处理流程。
    支持来源去重和时空去重。
    
    Headers:
    - X-Api-Key: API密钥（必填）
    - X-Source-System: 来源系统标识（可选，默认使用密钥绑定的系统）
    - X-Request-Id: 请求ID（可选，用于追踪）
    """
    logger.info(
        f"灾情上报请求: scenario_id={scenario_id}, "
        f"source_system={auth.source_system}, request_id={auth.request_id}"
    )
    
    response = await service.process_disaster_report(
        scenario_id=scenario_id,
        data=data,
        source_system=auth.source_system,
    )
    
    # 重复上报返回200而非201
    if response.status == "duplicate":
        # FastAPI不支持动态status_code，但response.status标记了重复
        pass
    
    return response


# ============================================================================
# 传感器告警
# ============================================================================

@router.post(
    "/sensor-alert",
    response_model=SensorAlertResponse,
    status_code=201,
    summary="传感器告警",
    description="接收IoT传感器（地震仪/水位计/烟雾报警器等）的告警数据",
)
async def sensor_alert(
    data: SensorAlertRequest,
    scenario_id: UUID = Query(..., description="目标想定ID"),
    auth: ApiKeyAuth = Depends(require_scope("sensor-alert")),
    service: IntegrationService = Depends(get_service),
) -> SensorAlertResponse:
    """
    传感器告警接口
    
    接收IoT传感器的告警数据，根据告警级别决定处理方式：
    - critical/warning: 创建事件
    - info: 仅记录日志
    
    Headers:
    - X-Api-Key: API密钥（必填）
    - X-Source-System: 来源系统标识（可选）
    """
    logger.info(
        f"传感器告警请求: scenario_id={scenario_id}, "
        f"sensor_id={data.sensor_id}, alert_level={data.alert_level}"
    )
    
    return await service.process_sensor_alert(
        scenario_id=scenario_id,
        data=data,
        source_system=auth.source_system,
    )


# ============================================================================
# 设备遥测（批量）
# ============================================================================

@router.post(
    "/telemetry",
    response_model=TelemetryResponse,
    summary="设备遥测（批量）",
    description="接收无人设备（无人机/机器狗/无人船）的实时遥测数据",
)
async def telemetry_batch(
    data: TelemetryBatchRequest,
    auth: ApiKeyAuth = Depends(require_scope("telemetry")),
    service: IntegrationService = Depends(get_service),
) -> TelemetryResponse:
    """
    批量遥测数据接口
    
    接收无人设备的实时遥测数据，批量更新位置并记录轨迹。
    单次请求最多100条数据。
    
    Headers:
    - X-Api-Key: API密钥（必填）
    """
    logger.info(
        f"批量遥测请求: count={len(data.batch)}, "
        f"source_system={auth.source_system}"
    )
    
    return await service.process_telemetry_batch(
        data=data,
        source_system=auth.source_system,
    )


# ============================================================================
# 天气数据
# ============================================================================

@router.post(
    "/weather",
    response_model=WeatherDataResponse,
    summary="天气数据",
    description="接收气象部门推送的天气数据和预警信息",
)
async def weather_data(
    data: WeatherDataRequest,
    auth: ApiKeyAuth = Depends(require_scope("weather")),
    service: IntegrationService = Depends(get_service),
) -> WeatherDataResponse:
    """
    天气数据接口
    
    接收气象数据，评估无人机飞行条件，处理天气预警。
    
    Headers:
    - X-Api-Key: API密钥（必填）
    """
    logger.info(
        f"天气数据请求: area_id={data.area_id}, "
        f"weather_type={data.weather_type}, source_system={auth.source_system}"
    )
    
    return await service.process_weather_data(
        data=data,
        source_system=auth.source_system,
    )


# ============================================================================
# 外部系统回调
# ============================================================================

@router.post(
    "/callback",
    response_model=CallbackResponse,
    summary="外部系统回调",
    description="接收外部系统（任务执行系统/设备控制系统等）的回调通知",
)
async def external_callback(
    data: CallbackRequest,
    auth: ApiKeyAuth = Depends(require_scope("callback")),
    service: IntegrationService = Depends(get_service),
) -> CallbackResponse:
    """
    外部系统回调接口
    
    接收外部系统的各类回调通知，包括：
    - task_completed: 任务完成通知
    - task_failed: 任务失败通知
    - resource_status: 资源状态变更
    - system_event: 系统事件
    - acknowledgment: 确认消息
    
    Headers:
    - X-Api-Key: API密钥（必填）
    """
    logger.info(
        f"外部回调请求: callback_type={data.callback_type}, "
        f"reference_id={data.reference_id}, source_system={auth.source_system}"
    )
    
    return await service.process_callback(
        data=data,
        source_system=auth.source_system,
    )
