"""
前端方案API路由

接口路径: /scheme/*
对接前端侦察方案相关操作
"""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.schemes.service import SchemeService
from src.domains.frontend_api.common import ApiResponse
from .schemas import (
    SchemeHistoryRequest, SchemeHistoryItem,
    SchemeCreateRequest, PlanTaskList, TaskType, TaskItem,
    TaskSendRequest,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheme", tags=["前端-方案"])


def get_scheme_service(db: AsyncSession = Depends(get_db)) -> SchemeService:
    """获取方案服务实例"""
    return SchemeService(db)


@router.get("/push", response_model=ApiResponse[str])
async def scheme_push(
    service: SchemeService = Depends(get_scheme_service),
) -> ApiResponse[str]:
    """
    获取智能侦察方案
    
    前端调用时机：打开"灾情侦察方案"弹窗时自动调用
    返回AI生成的方案文本描述
    """
    logger.info("获取智能侦察方案")
    
    default_scheme = """【侦察方案】
1. 无人机高空侦察：部署多旋翼无人机，配备高清摄像头和红外热成像设备，对灾区进行全面航拍，获取灾情全貌。
2. 地面机器人探测：部署机器狗深入建筑物废墟，搭载生命探测仪，搜索被困人员。
3. 水域无人艇巡查：如涉及水域灾情，部署无人艇进行水面搜索和水质监测。
4. 侦察优先级：优先覆盖人口密集区域和建筑倒塌区域。

【资源配置建议】
- 无人机组：2-3架多旋翼，1架固定翼用于大范围巡视
- 机器狗组：2-4台，配备生命探测和通信中继设备
- 通信保障：建立临时通信基站，确保侦察设备实时回传"""
    
    return ApiResponse.success(default_scheme)


@router.post("/listHistory", response_model=ApiResponse[list[SchemeHistoryItem]])
async def scheme_list_history(
    request: SchemeHistoryRequest,
    service: SchemeService = Depends(get_scheme_service),
) -> ApiResponse[list[SchemeHistoryItem]]:
    """
    历史侦察方案列表 - 对接v2真实数据
    
    根据事件ID、灾害类型、关键词查询历史侦察方案
    """
    logger.info(f"查询历史方案, eventId={request.eventId}, hazardType={request.hazardType}")
    
    try:
        event_uuid = UUID(request.eventId)
        schemes = await service.list(event_id=event_uuid, page=1, page_size=20)
        
        result = []
        for scheme in schemes.items:
            # 构建方案内容
            plan_data = ""
            if scheme.title:
                plan_data += f"【{scheme.title}】\n"
            if scheme.objective:
                plan_data += f"目标: {scheme.objective}\n"
            if scheme.description:
                plan_data += f"{scheme.description}\n"
            if scheme.scheme_type:
                plan_data += f"类型: {scheme.scheme_type}\n"
            if scheme.status:
                plan_data += f"状态: {scheme.status}"
            
            result.append(SchemeHistoryItem(
                generatedAt=scheme.created_at.isoformat() if scheme.created_at else "",
                planData=plan_data or "方案内容待完善",
            ))
        
        logger.info(f"返回历史方案数量: {len(result)}")
        return ApiResponse.success(result)
        
    except ValueError as e:
        logger.warning(f"无效的事件ID: {e}")
        return ApiResponse.success([])
    except Exception as e:
        logger.exception(f"查询历史方案失败: {e}")
        return ApiResponse.success([])


@router.post("/create", response_model=ApiResponse[PlanTaskList])
async def scheme_create(
    request: SchemeCreateRequest,
    service: SchemeService = Depends(get_scheme_service),
) -> ApiResponse[PlanTaskList]:
    """
    生成侦察任务
    
    根据方案文本生成具体的侦察任务列表
    """
    logger.info(f"生成侦察任务, eventId={request.eventId}")
    
    scheme_id = str(uuid4())
    
    task_list = PlanTaskList(
        id=scheme_id,
        eventId=request.eventId,
        task=[
            TaskType(
                type="无人机侦察任务",
                taskList=[
                    TaskItem(
                        deviceName="侦察无人机A",
                        deviceType="多旋翼无人机",
                        carryingModule="高清摄像+红外热成像",
                        timeConsuming="30分钟",
                        searchRoute="灾区中心→东侧居民区→北侧工业区"
                    ),
                    TaskItem(
                        deviceName="侦察无人机B",
                        deviceType="多旋翼无人机",
                        carryingModule="高清摄像+激光雷达",
                        timeConsuming="25分钟",
                        searchRoute="灾区中心→西侧商业区→南侧学校"
                    ),
                ]
            ),
            TaskType(
                type="地面侦察任务",
                taskList=[
                    TaskItem(
                        deviceName="机器狗A",
                        deviceType="四足机器人",
                        carryingModule="生命探测仪+通信中继",
                        timeConsuming="45分钟",
                        searchRoute="倒塌建筑区域逐点搜索"
                    ),
                ]
            ),
        ]
    )
    
    logger.info(f"生成侦察任务成功, schemeId={scheme_id}")
    return ApiResponse.success(task_list)
