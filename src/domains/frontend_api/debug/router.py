"""
前端调试/测试API路由

接口路径: /debug/test/*
对接前端调试测试相关操作
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.domains.frontend_api.task.schemas import (
    RescueDetailResponse, RescueTask, Location,
    UnitTask, EquipmentTask,
)
from src.domains.events.service import EventService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug/test", tags=["前端-调试"])


class RescueDetailRequest:
    eventId: str


@router.post("/rescueDetail", response_model=ApiResponse[RescueDetailResponse])
async def rescue_detail(
    request: dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RescueDetailResponse]:
    """
    生成救援方案

    根据事件ID获取单个救援点的救援方案详情
    """
    event_id = request.get("eventId", "")
    regenerate = request.get("regenerate", False)
    logger.info(f"获取救援方案详情, eventId={event_id}, regenerate={regenerate}")

    # 查询真实事件数据
    event = None
    if event_id:
        try:
            event_service = EventService(db)
            event = await event_service.get_by_id(UUID(event_id))
        except Exception as e:
            logger.warning(f"查询事件失败: {e}")

    # 如果找到事件，使用真实数据
    if event:
        response = RescueDetailResponse(
            time=event.reported_at.isoformat() if event.reported_at else datetime.now().isoformat(),
            textContent=event.description or event.title,
            locationName=event.address or "未知位置",
            location=Location(
                longitude=event.location.longitude,
                latitude=event.location.latitude
            ),
            origin=event.source_type.value if hasattr(event.source_type, 'value') else str(event.source_type),
            image="",
            # 救援任务暂时使用模板数据（后续可以根据事件类型动态生成）
            rescueTask=[
                RescueTask(
                    units=[
                        UnitTask(
                            id=f"unit-{event_id[:8]}",
                            name="应急救援队",
                            description="负责现场救援",
                            location=Location(
                                longitude=event.location.longitude,
                                latitude=event.location.latitude
                            ),
                            supplieList=["救援设备", "医疗物资", "通信设备"]
                        ),
                    ],
                    equipmentList=[
                        EquipmentTask(
                            deviceName="侦察无人机",
                            deviceType="多旋翼无人机",
                            carryingModule="高清摄像头+红外热成像",
                            timeConsuming="15分钟",
                            searchRoute="事件区域周边巡查"
                        ),
                    ]
                )
            ]
        )
    else:
        # 事件不存在时返回空数据
        response = RescueDetailResponse(
            time=datetime.now().isoformat(),
            textContent="未找到事件信息",
            locationName="未知",
            location=Location(longitude=0, latitude=0),
            origin="系统",
            image="",
            rescueTask=[]
        )

    return ApiResponse.success(response)


@router.post("/rescue-confirm", response_model=ApiResponse)
async def rescue_confirm(
    request: dict[str, Any],
) -> ApiResponse:
    """
    救援点确认
    
    确认救援点信息，准备进入救援任务生成阶段
    """
    logger.info(f"救援点确认, request={request}")
    
    return ApiResponse.success(None, "救援点确认成功")


@router.post("/addRescue", response_model=ApiResponse)
async def add_rescue(
    request: dict[str, Any],
) -> ApiResponse:
    """
    新建救援任务
    
    手动添加新的救援任务点
    """
    logger.info(f"新建救援任务, request={request}")
    
    return ApiResponse.success({"rescueId": "rescue-new-001"}, "救援点添加成功")


@router.get("/detourRoute", response_model=ApiResponse)
async def detour_route() -> ApiResponse:
    """
    车辆绕行
    
    触发车辆路线重新规划
    """
    logger.info("车辆绕行请求")
    return ApiResponse.success(None, "绕行路线已规划")


@router.get("/continueDrive", response_model=ApiResponse)
async def continue_drive() -> ApiResponse:
    """
    车辆继续行驶
    
    恢复车辆行驶状态
    """
    logger.info("继续行驶请求")
    return ApiResponse.success(None, "已恢复行驶")


@router.get("/selectCommandPoint", response_model=ApiResponse)
async def select_command_point() -> ApiResponse:
    """
    选择指挥点
    
    确定现场指挥位置
    """
    logger.info("选择指挥点请求")
    return ApiResponse.success({
        "pointId": "cp-001",
        "location": {"longitude": 104.0657, "latitude": 30.6595},
        "name": "现场指挥点A"
    }, "指挥点已选定")


# ============================================================================
# 场景事件推送测试
# ============================================================================

@router.post("/scenario/{event_type}", response_model=ApiResponse)
async def test_scenario_event(
    event_type: str,
    request: dict[str, Any],
) -> ApiResponse:
    """
    测试场景事件推送
    
    event_type: disaster | task | prompt
    """
    from src.core.stomp.broker import stomp_broker
    
    topic_map = {
        "disaster": "/topic/scenario.disaster.triggered",
        "task": "/topic/scenario.task.triggered", 
        "prompt": "/topic/scenario.prompt.triggered",
    }
    
    topic = topic_map.get(event_type)
    if not topic:
        return ApiResponse.error(400, f"无效的事件类型: {event_type}")
    
    await stomp_broker.send_to_destination(topic, {"payload": request})
    logger.info(f"场景事件已发送: {event_type} -> {topic}")
    
    return ApiResponse.success(None, f"场景事件 {event_type} 已推送")
