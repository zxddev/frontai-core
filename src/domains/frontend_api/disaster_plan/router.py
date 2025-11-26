"""
灾害预案/应急预案模块
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Query
from pydantic import BaseModel
from ..common import ApiResponse

router = APIRouter(prefix="/disaster-plan", tags=["灾害预案"])


class PlanModule(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str] = None
    content: Optional[dict] = None
    order: int = 0


@router.get("/{plan_id}/modules", response_model=ApiResponse)
async def get_plan_modules(
    plan_id: str,
):
    """
    获取预案模块列表
    """
    modules = [
        PlanModule(
            id="mod-1",
            name="态势分析",
            type="situation",
            description="当前态势分析报告",
            order=1,
            content={
                "analysisTime": "2025-01-01T10:00:00Z",
                "threatLevel": "medium",
                "summary": "态势分析内容"
            }
        ),
        PlanModule(
            id="mod-2", 
            name="力量部署",
            type="deployment",
            description="力量部署方案",
            order=2,
            content={
                "units": [],
                "positions": []
            }
        ),
        PlanModule(
            id="mod-3",
            name="任务分配",
            type="task",
            description="任务分配表",
            order=3,
            content={
                "tasks": []
            }
        ),
        PlanModule(
            id="mod-4",
            name="通信联络",
            type="communication",
            description="通信联络计划",
            order=4,
            content={
                "channels": [],
                "contacts": []
            }
        ),
        PlanModule(
            id="mod-5",
            name="保障计划",
            type="logistics",
            description="后勤保障计划",
            order=5,
            content={
                "supplies": [],
                "routes": []
            }
        ),
    ]
    
    return ApiResponse(
        code=200,
        message="success",
        data={
            "planId": plan_id,
            "modules": [m.model_dump() for m in modules],
            "total": len(modules)
        }
    )


@router.get("/{plan_id}", response_model=ApiResponse)
async def get_plan_detail(plan_id: str):
    """获取预案详情"""
    return ApiResponse(
        code=200,
        message="success",
        data={
            "id": plan_id,
            "name": "应急预案",
            "type": "emergency",
            "status": "active",
            "version": "1.0",
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "description": "应急处置预案",
        }
    )
