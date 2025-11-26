"""
前端阶段状态API路由

接口路径: /phase/*
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter

from src.domains.frontend_api.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase", tags=["前端-阶段状态"])


class PhaseItem(BaseModel):
    """阶段项"""
    id: str
    name: str
    status: str = "pending"  # pending/active/completed
    order: int = 0


class PhaseListResponse(BaseModel):
    """阶段列表响应"""
    currentPhase: str = "preparation"
    phases: list[PhaseItem] = Field(default_factory=list)


@router.get("/list", response_model=ApiResponse[PhaseListResponse])
async def get_phase_list() -> ApiResponse[PhaseListResponse]:
    """
    获取训练/演练阶段列表
    """
    logger.info("获取阶段列表")
    
    phases = [
        PhaseItem(id="preparation", name="准备阶段", status="completed", order=1),
        PhaseItem(id="reconnaissance", name="侦察阶段", status="active", order=2),
        PhaseItem(id="rescue", name="救援阶段", status="pending", order=3),
        PhaseItem(id="summary", name="总结阶段", status="pending", order=4),
    ]
    
    return ApiResponse.success(PhaseListResponse(
        currentPhase="reconnaissance",
        phases=phases,
    ))
