"""Overall Plan API Router.

前端"总体救灾方案要素设置"窗口对接的API接口：
- GET /modules: 同步生成8个模块内容（自动获取active想定）
- PUT /modules/save: 保存编辑后的模块内容到数据库
- GET /latest: 获取最新已保存的方案
- GET /document: 获取最终文档
"""

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
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


class LatestPlanResponse(BaseModel):
    """GET /latest 响应"""
    plan_id: str = Field(..., description="方案ID")
    scenario_id: str = Field(..., description="想定ID")
    modules: list[dict[str, Any]] = Field(..., description="模块列表")
    created_at: str = Field(..., description="创建时间")


# ============================================================================
# 数据库操作函数
# ============================================================================

def _format_modules_to_content(modules: list[dict[str, Any]]) -> str:
    """将modules数组转换为Markdown格式的文本内容
    
    用于存储在 recon_plans.plan_content 字段，供前端直接展示或导出。
    
    Args:
        modules: 模块列表，每个模块包含 title 和 value 字段
        
    Returns:
        格式化后的Markdown文本
    """
    lines: list[str] = []
    lines.append("# 总体救灾方案")
    lines.append("")
    
    for idx, module in enumerate(modules):
        title = module.get("title", f"模块{idx}")
        value = module.get("value", "")
        
        # 第一个模块（基本灾情）的value可能是dict结构
        if isinstance(value, dict):
            lines.append(f"## {title}")
            lines.append("")
            # 递归处理嵌套字典
            lines.append(_format_dict_to_markdown(value))
        else:
            lines.append(f"## {title}")
            lines.append("")
            lines.append(str(value) if value else "（待完善）")
        
        lines.append("")
    
    return "\n".join(lines)


def _format_dict_to_markdown(data: dict[str, Any], indent: int = 0) -> str:
    """将字典结构转换为Markdown格式
    
    Args:
        data: 字典数据
        indent: 缩进级别
        
    Returns:
        格式化后的Markdown文本
    """
    lines: list[str] = []
    prefix = "  " * indent
    
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}**:")
            lines.append(_format_dict_to_markdown(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}**: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{prefix}**{key}**: {value}")
    
    return "\n".join(lines)


async def _save_overall_plan(
    db: AsyncSession,
    scenario_id: str,
    modules: list[dict[str, Any]],
) -> str:
    """保存总体方案到 recon_plans 表
    
    复用 recon_plans 表，通过 plan_type='overall_plan' 区分。
    参考: src/domains/frontend_api/recon_plan/router.py 的 _save_recon_plan 实现
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        modules: 模块列表
        
    Returns:
        生成的方案ID (plan_id)
        
    Raises:
        Exception: 数据库写入失败时抛出异常
    """
    plan_id = str(uuid.uuid4())
    
    # 生成方案标题（取第一个模块的标题或默认值）
    plan_title = "总体救灾方案"
    if modules and modules[0].get("title"):
        plan_title = f"总体救灾方案 - {modules[0].get('title', '')}"
    
    # 格式化为可读文本
    plan_content = _format_modules_to_content(modules)
    
    # 构造plan_data结构化数据
    plan_data_dict: dict[str, Any] = {
        "plan_id": plan_id,
        "scenario_id": scenario_id,
        "modules": modules,
        "module_count": len(modules),
    }
    plan_data_json = json.dumps(plan_data_dict, ensure_ascii=False, default=str)
    
    sql = text("""
        INSERT INTO operational_v2.recon_plans (
            plan_id, plan_type, plan_subtype, plan_title,
            plan_content, plan_data, status, created_by, created_at, updated_at
        ) VALUES (
            :plan_id, 'overall_plan', 'rescue_plan', :plan_title,
            :plan_content, CAST(:plan_data AS jsonb), 'draft', 'system', NOW(), NOW()
        )
    """)
    
    await db.execute(
        sql,
        {
            "plan_id": plan_id,
            "plan_title": plan_title[:200] if len(plan_title) > 200 else plan_title,
            "plan_content": plan_content,
            "plan_data": plan_data_json,
        },
    )
    await db.commit()
    
    logger.info(
        "[OverallPlan] 方案已保存到数据库",
        extra={
            "plan_id": plan_id,
            "scenario_id": scenario_id,
            "module_count": len(modules),
        },
    )
    
    return plan_id


async def _get_latest_overall_plan(
    db: AsyncSession,
    scenario_id: str,
) -> Optional[tuple[str, dict[str, Any], str]]:
    """从数据库获取最新的总体方案
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        
    Returns:
        (plan_id, plan_data, created_at) 元组，如果没有找到则返回 None
    """
    sql = text("""
        SELECT plan_id, plan_data, created_at 
        FROM operational_v2.recon_plans 
        WHERE plan_type = 'overall_plan'
          AND plan_data->>'scenario_id' = :scenario_id
          AND (is_deleted = false OR is_deleted IS NULL)
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    
    result = await db.execute(sql, {"scenario_id": scenario_id})
    row = result.fetchone()
    
    if not row:
        return None
    
    plan_id, plan_data, created_at = row
    return str(plan_id), plan_data, str(created_at)


async def _get_latest_plan_content(
    db: AsyncSession,
    scenario_id: str,
) -> Optional[str]:
    """从数据库获取最新总体方案的文本内容
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        
    Returns:
        plan_content 文本，如果没有找到则返回 None
    """
    sql = text("""
        SELECT plan_content 
        FROM operational_v2.recon_plans 
        WHERE plan_type = 'overall_plan'
          AND plan_data->>'scenario_id' = :scenario_id
          AND (is_deleted = false OR is_deleted IS NULL)
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    
    result = await db.execute(sql, {"scenario_id": scenario_id})
    row = result.fetchone()
    
    return row[0] if row else None


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
    description="保存指挥员编辑后的模块内容到数据库，用于预览和后续文档生成",
)
async def save_modules(
    modules: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db),
) -> SaveModulesResponse:
    """保存编辑后的模块内容到数据库
    
    前端编辑完成后调用此接口保存，数据持久化到 recon_plans 表。
    请求体直接是modules数组: [{title, value}, ...]
    
    参考实现: src/domains/frontend_api/recon_plan/router.py
    """
    scenario_id = await get_active_scenario_id(db)
    
    logger.info(
        "[OverallPlan] 收到保存请求",
        extra={"scenario_id": scenario_id, "module_count": len(modules)},
    )
    
    try:
        plan_id = await _save_overall_plan(
            db=db,
            scenario_id=scenario_id,
            modules=modules,
        )
        
        logger.info(
            "[OverallPlan] 保存成功",
            extra={"plan_id": plan_id, "scenario_id": scenario_id},
        )
        
        return SaveModulesResponse(
            code=200,
            message="success",
            data=modules,
        )
    except Exception as e:
        logger.exception("[OverallPlan] 保存方案到数据库失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存方案失败: {e}",
        )


@router.get(
    "/latest",
    response_model=LatestPlanResponse,
    summary="获取最新已保存的方案",
    description="从数据库获取当前想定最新保存的总体方案",
)
async def get_latest_plan(
    db: AsyncSession = Depends(get_db),
) -> LatestPlanResponse:
    """获取最新已保存的总体方案
    
    从数据库查询当前生效想定的最新保存方案，避免重复调用AI生成。
    参考实现: src/domains/frontend_api/recon_plan/router.py 的 get_latest_recon_plan
    """
    scenario_id = await get_active_scenario_id(db)
    
    logger.info(
        "[OverallPlan] 查询最新方案",
        extra={"scenario_id": scenario_id},
    )
    
    result = await _get_latest_overall_plan(db, scenario_id)
    
    if not result:
        logger.info("[OverallPlan] 未找到已保存的方案")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="暂无已保存的总体方案",
        )
    
    plan_id, plan_data, created_at = result
    modules = plan_data.get("modules", [])
    
    logger.info(
        "[OverallPlan] 找到已保存的方案",
        extra={"plan_id": plan_id, "created_at": created_at},
    )
    
    return LatestPlanResponse(
        plan_id=plan_id,
        scenario_id=scenario_id,
        modules=modules,
        created_at=created_at,
    )


@router.get(
    "/document",
    response_model=DocumentResponse,
    summary="获取最终文档",
    description="获取生成的总体救灾方案文档（从数据库读取）",
)
async def get_document(
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """获取最终文档
    
    从数据库读取最新保存方案的 plan_content 字段返回。
    如果没有保存的方案，返回提示信息。
    """
    scenario_id = await get_active_scenario_id(db)
    
    logger.info(
        "[OverallPlan] 获取文档",
        extra={"scenario_id": scenario_id},
    )
    
    document = await _get_latest_plan_content(db, scenario_id)
    
    if not document:
        logger.info("[OverallPlan] 未找到已保存的方案文档")
        document = "暂无已保存的方案文档，请先编辑并保存方案要素。"
    
    return DocumentResponse(
        document=document,
        scenario_id=scenario_id,
    )
