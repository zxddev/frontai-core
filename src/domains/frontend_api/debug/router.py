"""
前端调试/测试API路由

接口路径: /debug/test/*
对接前端调试测试相关操作
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from src.domains.frontend_api.common import ApiResponse
from src.domains.frontend_api.task.schemas import (
    RescueDetailResponse, RescueTask, Location,
    UnitTask, EquipmentTask,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug/test", tags=["前端-调试"])


class RescueDetailRequest:
    eventId: str


@router.post("/rescueDetail", response_model=ApiResponse[RescueDetailResponse])
async def rescue_detail(
    request: dict[str, Any],
) -> ApiResponse[RescueDetailResponse]:
    """
    生成救援方案
    
    根据事件ID获取单个救援点的救援方案详情
    """
    event_id = request.get("eventId", "")
    logger.info(f"获取救援方案详情, eventId={event_id}")
    
    mock_response = RescueDetailResponse(
        time=datetime.now().isoformat(),
        textContent="地震导致居民楼部分倒塌，预计被困人员5-10人，需紧急救援",
        locationName="新华路123号居民楼",
        location=Location(longitude=104.0657, latitude=30.6595),
        origin="无人机侦察",
        image="",
        rescueTask=[
            RescueTask(
                units=[
                    UnitTask(
                        id="unit-fire-1",
                        name="消防救援一中队",
                        description="负责建筑搜救",
                        location=Location(longitude=104.0657, latitude=30.6595),
                        supplieList=["生命探测仪", "破拆工具", "担架", "照明设备"]
                    ),
                    UnitTask(
                        id="unit-medical-1",
                        name="医疗救护组",
                        description="负责伤员救治",
                        location=Location(longitude=104.0657, latitude=30.6595),
                        supplieList=["急救包", "担架", "氧气瓶", "止血带"]
                    ),
                ],
                equipmentList=[
                    EquipmentTask(
                        deviceName="搜救机器狗A",
                        deviceType="四足机器人",
                        carryingModule="生命探测仪+摄像头+通信中继",
                        timeConsuming="45分钟",
                        searchRoute="倒塌区域1层→2层→3层逐层搜索"
                    ),
                    EquipmentTask(
                        deviceName="搜救无人机B",
                        deviceType="多旋翼无人机",
                        carryingModule="红外热成像+喊话器",
                        timeConsuming="20分钟",
                        searchRoute="建筑周边空中巡查"
                    ),
                ]
            )
        ]
    )
    
    return ApiResponse.success(mock_response)


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
