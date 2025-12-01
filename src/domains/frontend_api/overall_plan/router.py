"""Overall Plan API Router.

前端"总体救灾方案要素设置"窗口对接的API接口：
- GET /modules: 同步生成8个模块内容（自动获取active想定）
- PUT /modules/save: 保存编辑后的模块内容
- GET /document: 获取最终文档
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.overall_plan.agent import OverallPlanAgent
from src.agents.overall_plan.schemas import PlanModuleItem
from src.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/overall-plan", tags=["overall-plan"])

# Singleton agent instance
_agent: OverallPlanAgent | None = None


def get_agent() -> OverallPlanAgent:
    """Get or create the OverallPlanAgent instance."""
    global _agent
    if _agent is None:
        _agent = OverallPlanAgent()
    return _agent


async def get_active_scenario_id(db: AsyncSession) -> str:
    """获取当前生效的想定ID（status='active'）"""
    result = await db.execute(
        text("SELECT id FROM operational_v2.scenarios_v2 WHERE status = 'active' LIMIT 1")
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有找到生效的想定，请先创建或激活一个想定",
        )
    return str(row[0])


# ============================================================================
# Response/Request Models
# ============================================================================

class ModulesResponse(BaseModel):
    """GET /modules 响应"""
    modules: list[PlanModuleItem]
    scenario_id: str


class SaveModulesRequest(BaseModel):
    """PUT /modules/save 请求体 - 兼容前端直接传数组"""
    pass  # 使用list[dict]直接接收


class SaveModulesResponse(BaseModel):
    """PUT /modules/save 响应"""
    code: int = 200
    message: str = "success"
    data: list[dict[str, Any]]


class DocumentResponse(BaseModel):
    """GET /document 响应"""
    document: str
    scenario_id: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/modules",
    response_model=ModulesResponse,
    summary="获取AI生成的8个模块内容",
    description="同步调用AI生成总体救灾方案的8个模块内容，自动获取当前生效的想定",
)
async def get_modules(
    db: AsyncSession = Depends(get_db),
    agent: OverallPlanAgent = Depends(get_agent),
) -> ModulesResponse:
    """同步生成8个模块内容
    
    业务流程：
    1. 自动获取当前生效的想定（status='active'）
    2. 调用AI生成8个模块内容
    3. 等待生成完成（最多10分钟）
    4. 返回modules数组供前端展示和编辑
    """
    import asyncio
    
    scenario_id = await get_active_scenario_id(db)
    logger.info(f"Generating modules for active scenario {scenario_id}")
    
    try:
        # 调用agent触发生成
        result = await agent.trigger(scenario_id=scenario_id, event_id="")
        task_id = result.task_id
        
        # 等待生成完成或超时（10分钟）
        max_wait_seconds = 600
        poll_interval = 3
        elapsed = 0
        
        while elapsed < max_wait_seconds:
            status_result = await agent.get_status(scenario_id, task_id)
            
            # 如果到达human_review中断点，说明modules已生成
            if status_result.status == "awaiting_approval":
                logger.info(f"Modules ready for scenario {scenario_id}")
                if status_result.modules:
                    return ModulesResponse(
                        modules=status_result.modules,
                        scenario_id=scenario_id,
                    )
            
            # 如果失败，立即返回错误
            if status_result.status == "failed":
                errors = status_result.errors or ["Unknown error"]
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"生成失败: {'; '.join(errors)}",
                )
            
            # 如果已完成，返回modules
            if status_result.status == "completed":
                if status_result.modules:
                    return ModulesResponse(
                        modules=status_result.modules,
                        scenario_id=scenario_id,
                    )
            
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            logger.debug(f"Waiting for modules... {elapsed}s elapsed")
        
        # 超时
        logger.warning(f"Timeout waiting for modules for scenario {scenario_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="生成超时，请稍后重试",
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to generate modules for scenario {scenario_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成方案模块失败: {str(e)}",
        )


@router.put(
    "/modules/save",
    response_model=SaveModulesResponse,
    summary="保存编辑后的模块内容",
    description="保存指挥员编辑后的模块内容，用于预览",
)
async def save_modules(
    modules: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db),
) -> SaveModulesResponse:
    """保存编辑后的模块内容
    
    前端编辑完成后调用此接口保存，返回格式化后的预览数据。
    请求体直接是modules数组: [{title, value}, ...]
    """
    # TODO: 可以将数据保存到数据库
    # 目前直接返回传入的数据作为预览
    return SaveModulesResponse(
        code=200,
        message="success",
        data=modules,
    )


@router.get(
    "/document",
    response_model=DocumentResponse,
    summary="获取最终文档",
    description="获取生成的总体救灾方案文档",
)
async def get_document(
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """获取最终文档
    
    TODO: 实现文档生成逻辑，目前返回占位内容
    """
    scenario_id = await get_active_scenario_id(db)
    
    # TODO: 从数据库或agent获取最终文档
    document = "总体救灾方案文档生成中..."
    
    return DocumentResponse(
        document=document,
        scenario_id=scenario_id,
    )
