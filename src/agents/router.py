"""
AI Agent API路由

接口前缀: /ai
支持数据库集成：从数据库查询队伍、保存方案到数据库
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.websocket import broadcast_event_update
from src.domains.ai_decisions import AIDecisionLogRepository, CreateAIDecisionLogRequest
from .exceptions import AITaskNotFoundError, AISchemeNotFoundError
from src.agents.schemas import (
    EmergencyAnalyzeRequest,
    EmergencyAnalyzeTaskResponse,
    EmergencyAnalyzeResult,
    ConfirmEmergencySchemeRequest,
    RoutePlanningRequest,
    RoutePlanningTaskResponse,
    RoutePlanningResult,
)
from src.domains.audit import AuditService, OperatorInfo, ActionInfo
from .route_planning import invoke as route_planning_invoke
from .emergency_ai.agent import get_emergency_ai_agent
from .task_coordinator.agent import run_task_coordinator
from .task_coordinator.schemas import TaskAllocation, TeamInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# 任务结果缓存（内存L1缓存，Redis为主存储）
# 注意：多实例部署时内存缓存可能不一致，但不影响正确性（Redis为准）
# 缓存大小限制防止内存泄漏
_task_results: Dict[str, Dict[str, Any]] = {}
_TASK_CACHE_MAX_SIZE = 100  # 最多缓存100个任务结果


def _cleanup_task_cache() -> None:
    """清理内存缓存，保留最近的任务结果"""
    global _task_results
    if len(_task_results) > _TASK_CACHE_MAX_SIZE:
        # 删除最老的一半条目（简单策略，无需复杂LRU）
        items = list(_task_results.items())
        _task_results = dict(items[len(items) // 2:])
        logger.info(f"[缓存清理] 内存缓存已清理，剩余 {len(_task_results)} 条")


# Redis配置
EMERGENCY_RESULT_PREFIX = "emergency_ai_result:"
EMERGENCY_RESULT_TTL = 36000  # 结果保存10小时




async def _save_result_to_redis(task_id: str, result: Dict[str, Any]) -> bool:
    """保存结果到Redis"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        
        key = f"{EMERGENCY_RESULT_PREFIX}{task_id}"
        await redis_client.setex(key, EMERGENCY_RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
        # 统一管理的Redis客户端不需要每次手动close，由连接池管理
        # await redis_client.close() 
        logger.info(f"[EmergencyAI] 结果已保存到Redis: {key}")
        return True
    except Exception as e:
        logger.warning(f"[EmergencyAI] Redis保存失败: {e}")
        return False


async def _get_result_from_redis(task_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取结果"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        
        key = f"{EMERGENCY_RESULT_PREFIX}{task_id}"
        data = await redis_client.get(key)
        # await redis_client.close()
        if data:
            logger.info(f"[EmergencyAI] 从Redis获取结果: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"[EmergencyAI] Redis读取失败: {e}")
        return None


async def _run_task_coordinator_for_result(
    event_id: str,
    ai_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    从 emergency_ai 结果中提取队伍信息，调用 task_coordinator 生成步骤级协作方案

    Args:
        event_id: 事件ID
        ai_result: emergency_ai 的分析结果

    Returns:
        task_coordinator 输出（dict格式），失败时返回 None
    """
    # 提取灾害类型
    understanding = ai_result.get("understanding", {})
    parsed_disaster = understanding.get("parsed_disaster", {})
    disaster_type = parsed_disaster.get("disaster_type", "unknown")
    scene_code = parsed_disaster.get("scene_code")

    # 提取队伍列表
    recommended_scheme = ai_result.get("recommended_scheme", {})
    allocations = recommended_scheme.get("allocations", [])

    if not allocations:
        logger.info(f"[TaskCoordinator] 无队伍分配，跳过协调: event_id={event_id}")
        return None

    # 构建 TeamInfo 列表（所有队伍作为一个整体）
    team_infos = []
    for alloc in allocations:
        team_id = alloc.get("resource_id", "")
        if not team_id:
            continue
        team_infos.append(TeamInfo(
            team_id=str(team_id),
            team_name=alloc.get("resource_name", ""),
            capabilities=alloc.get("assigned_capabilities", []),
            equipment=[e.get("name", "") for e in alloc.get("equipments", []) if e.get("name")],
        ))

    if not team_infos:
        logger.info(f"[TaskCoordinator] 无有效队伍，跳过协调: event_id={event_id}")
        return None

    # 构建 TaskAllocation
    task_allocation = TaskAllocation(
        task_id=f"task-{event_id[:8]}",
        task_name=ai_result.get("event_title", "救援任务"),
        disaster_type=disaster_type,
        scene_code=scene_code,
        allocated_teams=team_infos,
    )

    logger.info(
        f"[TaskCoordinator] 开始协调: event_id={event_id}, "
        f"teams={len(team_infos)}, disaster_type={disaster_type}"
    )

    # 调用 task_coordinator
    output = await run_task_coordinator(
        event_id=event_id,
        task_allocation=task_allocation,
        disaster_info={"disaster_type": disaster_type, "scene_code": scene_code},
    )

    # 转换为 dict 格式
    result = {
        "task_id": output.task_id,
        "task_name": output.task_name,
        "sop_template": output.sop_template,
        "total_steps": output.total_steps,
        "estimated_duration_minutes": output.estimated_duration_minutes,
        "step_instructions": [
            {
                "step_id": inst.step_id,
                "step_name": inst.step_name,
                "sequence": inst.sequence,
                "teams": [
                    {
                        "team_id": t.team_id,
                        "team_name": t.team_name,
                        "role": t.role.value if hasattr(t.role, 'value') else str(t.role),
                        "responsibilities": t.responsibilities,
                        "equipment": t.equipment,
                    }
                    for t in inst.teams
                ],
                "cooperation_mode": inst.cooperation_mode,
                "depends_on": inst.depends_on,
                "estimated_duration": inst.estimated_duration,
                "completion_criteria": inst.completion_criteria,
                "safety_notes": inst.safety_notes,
            }
            for inst in output.step_instructions
        ],
        "warnings": output.warnings,
    }

    logger.info(
        f"[TaskCoordinator] 协调完成: event_id={event_id}, "
        f"steps={output.total_steps}, duration={output.estimated_duration_minutes}min"
    )

    return result





def _to_serializable(obj: Any) -> Any:
    """
    将对象转换为JSON可序列化的格式
    
    处理dataclass、自定义对象等无法直接JSON序列化的类型
    """
    import dataclasses
    
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if hasattr(obj, "__dict__"):
        return {k: _to_serializable(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


# ============================================================================
# 规则管理接口
# ============================================================================

@router.post("/rules/reload")
async def reload_rules() -> Dict[str, Any]:
    """
    热更新规则
    
    清除规则缓存，下次调用时自动重新加载最新规则文件
    适用场景：修改YAML规则文件后，无需重启服务即可生效
    """
    from .rules import clear_rules_cache, get_cache_stats, RuleLoader
    
    # 获取更新前的统计
    before_stats = get_cache_stats()
    
    # 清除缓存
    clear_rules_cache()
    
    # 预加载规则（验证规则文件有效性）
    try:
        trr_rules = RuleLoader.load_trr_rules(use_cache=False)
        hard_rules = RuleLoader.load_hard_rules(use_cache=False)
        
        return {
            "success": True,
            "message": "规则热更新成功",
            "before": {
                "trr_cache_entries": before_stats["cache_size"]["trr_entries"],
                "hard_cache_entries": before_stats["cache_size"]["hard_entries"],
            },
            "after": {
                "trr_rules_count": len(trr_rules),
                "hard_rules_count": len(hard_rules),
            },
        }
    except Exception as e:
        logger.error(f"规则热更新失败: {e}")
        return {
            "success": False,
            "message": f"规则加载失败: {e}",
            "error": str(e),
        }


@router.get("/rules/stats")
async def get_rules_stats() -> Dict[str, Any]:
    """
    获取规则缓存统计信息
    
    返回缓存命中率、规则数量等统计数据
    """
    from .rules import get_cache_stats, RuleLoader
    
    stats = get_cache_stats()
    
    # 获取当前加载的规则数量
    trr_rules = RuleLoader.load_trr_rules()
    hard_rules = RuleLoader.load_hard_rules()
    
    return {
        "cache_stats": stats,
        "rules_loaded": {
            "trr_rules_count": len(trr_rules),
            "hard_rules_count": len(hard_rules),
        },
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    AI模块健康检查
    
    检查内容：
    - 规则文件存在性
    - 规则缓存状态
    - 熔断器状态
    - Redis连接（资源锁）
    - 数据库连接
    """
    from pathlib import Path
    from .rules import get_cache_stats
    from .utils.circuit_breaker import get_all_circuit_breakers_stats
    from src.core.redis import check_redis_health
    
    checks = {
        "status": "healthy",
        "module": "ai-agents",
        "version": "2.2.0",
        "checks": {},
    }
    
    # 检查TRR规则文件
    trr_path = Path("config/rules/trr_emergency.yaml")
    checks["checks"]["trr_rules_file"] = {
        "exists": trr_path.exists(),
        "path": str(trr_path),
    }
    
    # 检查硬规则文件
    hard_path = Path("config/rules/hard_rules.yaml")
    checks["checks"]["hard_rules_file"] = {
        "exists": hard_path.exists(),
        "path": str(hard_path),
    }
    
    # 缓存统计
    checks["cache_stats"] = get_cache_stats()
    
    # 熔断器状态
    breaker_stats = get_all_circuit_breakers_stats()
    checks["circuit_breakers"] = breaker_stats
    
    # 检查是否有熔断器处于open状态
    open_breakers = [name for name, stats in breaker_stats.items() if stats.get("state") == "open"]
    if open_breakers:
        checks["status"] = "degraded"
        checks["checks"]["circuit_breakers"] = {
            "healthy": False,
            "open_breakers": open_breakers,
        }
    else:
        checks["checks"]["circuit_breakers"] = {"healthy": True}
    
    # 检查Redis连接
    redis_health = await check_redis_health()
    checks["checks"]["redis"] = redis_health
    if not redis_health.get("connected"):
        # Redis不可用时降级（资源锁将使用数据库锁）
        checks["status"] = "degraded" if checks["status"] == "healthy" else checks["status"]
    
    # 检查数据库连接
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import text
            await db.execute(text("SELECT 1"))
            checks["checks"]["database"] = {"connected": True}
    except Exception as e:
        checks["checks"]["database"] = {"connected": False, "error": str(e)}
        checks["status"] = "degraded"
    
    # 如果规则文件不存在，降级状态
    if not trr_path.exists() or not hard_path.exists():
        checks["status"] = "degraded"
    
    return checks


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers() -> Dict[str, Any]:
    """
    重置所有熔断器
    
    将所有熔断器状态重置为CLOSED，清除失败计数
    """
    from .utils.circuit_breaker import reset_all_circuit_breakers, get_all_circuit_breakers_stats
    
    before = get_all_circuit_breakers_stats()
    reset_all_circuit_breakers()
    after = get_all_circuit_breakers_stats()
    
    return {
        "success": True,
        "message": "所有熔断器已重置",
        "before": before,
        "after": after,
    }


# ============================================================================
# 应急AI混合分析接口
# ============================================================================

async def _run_emergency_analysis(
    task_id: str,
    request: EmergencyAnalyzeRequest,
) -> None:
    """
    后台执行应急AI分析任务
    
    Args:
        task_id: 任务ID
        request: 分析请求
    """
    import traceback
    
    logger.info(
        f"[EmergencyAI] 开始执行分析任务 task_id={task_id} event_id={request.event_id}"
    )
    logger.info(
        f"[EmergencyAI] 灾情描述: {request.disaster_description[:100]}..."
    )
    
    try:
        logger.info(f"[EmergencyAI] 初始化Agent...")
        agent = get_emergency_ai_agent()
        logger.info(f"[EmergencyAI] Agent初始化完成，开始分析...")
        
        # 将rescue_points放入structured_input以传递给agent
        structured_input = request.structured_input or {}
        if request.rescue_points:
            structured_input["rescue_points"] = [
                p.model_dump() for p in request.rescue_points
            ]
            logger.info(f"[EmergencyAI] 传递{len(request.rescue_points)}个救援点到分析流程")
        
        result = await agent.analyze(
            event_id=str(request.event_id),
            scenario_id=str(request.scenario_id),
            disaster_description=request.disaster_description,
            structured_input=structured_input,
            constraints=request.constraints,
            optimization_weights=request.optimization_weights,
        )

        logger.info(f"[EmergencyAI] 分析完成，准备调用 task_coordinator task_id={task_id}")

        # 调用 task_coordinator 生成步骤级协作方案（优雅降级：失败不阻塞主流程）
        if result.get("success"):
            try:
                coordinator_result = await _run_task_coordinator_for_result(
                    event_id=str(request.event_id),
                    ai_result=result,
                )
                if coordinator_result:
                    result["task_coordinator"] = coordinator_result
                    logger.info(f"[EmergencyAI] task_coordinator 结果已合并 task_id={task_id}")
            except Exception as coord_err:
                logger.warning(f"[EmergencyAI] task_coordinator 调用失败（不影响主流程）: {coord_err}")

        logger.info(f"[EmergencyAI] 保存结果到 Redis task_id={task_id}")

        # 保存到内存和Redis
        _task_results[task_id] = result
        _cleanup_task_cache()
        await _save_result_to_redis(task_id, result)
        
        logger.info(
            f"[EmergencyAI] 任务成功 task_id={task_id} "
            f"success={result.get('success')} "
            f"execution_time_ms={result.get('execution_time_ms')}"
        )
        
        # 保存决策日志
        try:
            await _save_emergency_decision_log(request, result)
        except Exception as log_err:
            logger.warning(f"[EmergencyAI] 保存决策日志失败: {log_err}")
        
        # WebSocket推送
        try:
            await _broadcast_emergency_result(request, result)
        except Exception as ws_err:
            logger.warning(f"[EmergencyAI] WebSocket推送失败: {ws_err}")
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(
            f"[EmergencyAI] 任务失败 task_id={task_id} error={str(e)}\n{error_detail}"
        )
        
        error_result = {
            "success": False,
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scenario_id": str(request.scenario_id),
            "status": "failed",
            "errors": [str(e), error_detail],
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }
        # 保存到内存和Redis
        _task_results[task_id] = error_result
        _cleanup_task_cache()
        await _save_result_to_redis(task_id, error_result)
        logger.info(f"[EmergencyAI] 错误结果已保存 task_id={task_id}")


async def _save_emergency_decision_log(
    request: EmergencyAnalyzeRequest,
    result: Dict[str, Any],
) -> Optional[UUID]:
    """保存应急AI决策日志"""
    logger.info(
        "保存应急AI决策日志",
        extra={"event_id": str(request.event_id)}
    )
    
    try:
        async with AsyncSessionLocal() as db:
            repo = AIDecisionLogRepository(db)
            
            recommended = result.get("recommended_scheme", {})
            confidence = recommended.get("total_score") if recommended else None
            
            log_data = CreateAIDecisionLogRequest(
                scenario_id=request.scenario_id,
                event_id=request.event_id,
                scheme_id=None,
                decision_type="emergency_ai_analysis",
                algorithm_used="LLM+RAG+KG+Rules",
                input_snapshot=_to_serializable({
                    "disaster_description": request.disaster_description[:500],
                    "constraints": request.constraints,
                }),
                output_result=_to_serializable({
                    "success": result.get("success"),
                    "matched_rules_count": len(result.get("reasoning", {}).get("matched_rules", [])),
                    "recommended_scheme_id": recommended.get("solution_id") if recommended else None,
                }),
                confidence_score=Decimal(str(confidence)) if confidence else None,
                reasoning_chain=_to_serializable(result.get("trace", {})),
                processing_time_ms=result.get("execution_time_ms"),
            )
            
            log_entry = await repo.create(log_data)
            await db.commit()
            
            logger.info(
                "应急AI决策日志保存成功",
                extra={"log_id": str(log_entry.id), "event_id": str(request.event_id)}
            )
            return log_entry.id
            
    except Exception as e:
        logger.exception(
            "应急AI决策日志保存失败",
            extra={"event_id": str(request.event_id), "error": str(e)}
        )
        return None


async def _broadcast_emergency_result(
    request: EmergencyAnalyzeRequest,
    result: Dict[str, Any],
) -> None:
    """WebSocket推送应急AI分析结果"""
    try:
        await broadcast_event_update(
            scenario_id=request.scenario_id,
            event_type="emergency_ai_analysis_completed",
            event_data={
                "event_id": str(request.event_id),
                "success": result.get("success"),
                "has_recommendation": result.get("recommended_scheme") is not None,
                "execution_time_ms": result.get("execution_time_ms"),
            },
        )
        logger.info("应急AI分析结果推送成功")
    except Exception as e:
        logger.warning("应急AI分析结果推送失败", extra={"error": str(e)})


@router.post("/emergency-analyze", response_model=EmergencyAnalyzeTaskResponse, status_code=202)
async def emergency_analyze(
    request: EmergencyAnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> EmergencyAnalyzeTaskResponse:
    """
    提交应急AI分析任务

    使用AI+规则混合架构进行灾情分析：
    - 阶段1: LLM灾情理解 + RAG案例增强
    - 阶段2: 知识图谱规则查询 + TRR引擎匹配
    - 阶段3: CSP资源匹配 + NSGA-II优化
    - 阶段4: 硬/软规则过滤 + LLM方案解释

    Args:
        request: 分析请求

    Returns:
        任务提交响应，包含task_id用于查询结果
    """
    task_id = f"emergency-{request.event_id}"
    created_at = datetime.utcnow()

    logger.info(
        "收到应急AI分析请求",
        extra={
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scenario_id": str(request.scenario_id),
        },
    )

    # 立即保存processing状态到缓存，让by-event接口能查到正在执行的任务
    processing_state = {
        "task_id": task_id,
        "event_id": str(request.event_id),
        "scenario_id": str(request.scenario_id),
        "status": "processing",
        "created_at": created_at.isoformat() + "Z",
    }
    _task_results[task_id] = processing_state
    await _save_result_to_redis(task_id, processing_state)
    logger.info(f"[EmergencyAI] 已保存processing状态 task_id={task_id}")

    # 提交后台任务
    background_tasks.add_task(_run_emergency_analysis, task_id, request)

    return EmergencyAnalyzeTaskResponse(
        success=True,
        task_id=task_id,
        event_id=str(request.event_id),
        status="processing",
        message="应急AI分析任务已提交，预计完成时间5-15秒",
        created_at=created_at,
    )


@router.get("/emergency-analyze/by-event/{event_id}")
async def get_analysis_by_event_id(event_id: str) -> Dict[str, Any]:
    """
    通过事件ID查询分析状态和结果
    支持页面刷新后的状态恢复
    """
    task_id = f"emergency-{event_id}"
    
    # 尝试获取结果
    result = _task_results.get(task_id)
    if result is None:
        result = await _get_result_from_redis(task_id)
        if result:
             # 同步到内存缓存
            _task_results[task_id] = result
            _cleanup_task_cache()
            
    if result:
        # 调试：检查 resource_gaps 数据
        resource_gaps = result.get("resource_gaps", {})
        supply_shortages_count = len(resource_gaps.get("supply_shortages", []))
        logger.info(
            f"[API] 返回分析结果 event_id={event_id}, "
            f"物资缺口={supply_shortages_count}种, "
            f"status={result.get('status')}"
        )
        
        return {
            "found": True,
            "task_id": task_id,
            "status": result.get("status", "unknown"),
            "result": result if result.get("status") == "completed" else None,
            "created_at": result.get("created_at"),
            "completed_at": result.get("completed_at"),
            "updated_time": result.get("completed_at") or result.get("created_at")
        }
    else:
        # 返回默认空状态而不是404错误
        return {
            "found": False,
            "task_id": task_id,
            "status": "none",
            "result": None
        }


@router.get("/emergency-analyze/{task_id}")
async def get_emergency_analyze_result(task_id: str) -> EmergencyAnalyzeResult:
    """
    查询应急AI分析结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        分析结果
        
    Raises:
        AITaskNotFoundError: 任务不存在
    """
    # 优先从内存获取
    result = _task_results.get(task_id)
    
    # 内存没有则从Redis获取
    if result is None:
        result = await _get_result_from_redis(task_id)
        if result:
            # 同步到内存缓存
            _task_results[task_id] = result
            _cleanup_task_cache()
    
    if result is None:
        raise AITaskNotFoundError(task_id)
    
    return EmergencyAnalyzeResult(
        success=result.get("success", False),
        event_id=result.get("event_id", ""),
        scenario_id=result.get("scenario_id", ""),
        status=result.get("status", "unknown"),
        completed_at=result.get("completed_at"),
        understanding=result.get("understanding"),
        reasoning=result.get("reasoning"),
        htn_decomposition=result.get("htn_decomposition"),
        strategic=result.get("strategic"),
        matching=result.get("matching"),
        optimization=result.get("optimization"),
        multi_point_allocation=result.get("multi_point_allocation"),
        recommended_scheme=result.get("recommended_scheme"),
        scheme_explanation=result.get("scheme_explanation"),
        trace=result.get("trace"),
        errors=result.get("errors", []),
        execution_time_ms=result.get("execution_time_ms"),
    )


@router.post("/emergency-analyze/{task_id}/confirm")
async def confirm_emergency_scheme(
    task_id: str,
    request: ConfirmEmergencySchemeRequest,
) -> Dict[str, Any]:
    """
    确认部署AI推荐方案
    
    完整流程：
    1. 获取AI分析结果
    2. 查询事件详情
    3. 校验队伍状态
    4. 创建任务记录 (tasks_v2)
    5. 创建分配记录 (task_assignments_v2)
    6. 更新队伍状态 (rescue_teams_v2)
    7. 更新事件状态 (events_v2)
    8. WebSocket推送通知
    
    Args:
        task_id: AI分析任务ID (格式: emergency-{event_id})
        request: 确认请求，包含用户选中的队伍ID列表
        
    Returns:
        确认结果，包含创建的任务ID和部署的队伍信息
    """
    from sqlalchemy import text
    import uuid as uuid_lib
    
    logger.info(f"[EmergencyConfirm] 收到确认请求 task_id={task_id}, team_ids={request.team_ids}")
    
    # ========== 1. 获取AI分析结果 ==========
    ai_result = _task_results.get(task_id)
    if ai_result is None:
        ai_result = await _get_result_from_redis(task_id)
    
    if ai_result is None:
        raise AITaskNotFoundError(task_id)
    
    if not ai_result.get("success"):
        return {
            "success": False,
            "error": "AI分析未成功，无法确认方案",
            "errors": ai_result.get("errors", []),
        }
    
    # 提取关键信息
    event_id_str: str = ai_result.get("event_id", "")
    scenario_id_str: str = ai_result.get("scenario_id", "")
    scheme_explanation: str = ai_result.get("scheme_explanation", "AI推荐救援方案")
    
    if not event_id_str or not scenario_id_str:
        return {
            "success": False,
            "error": "AI结果中缺少event_id或scenario_id",
        }
    
    # 转换UUID
    try:
        event_id = UUID(event_id_str)
        scenario_id = UUID(scenario_id_str)
    except ValueError as e:
        return {
            "success": False,
            "error": f"无效的event_id或scenario_id格式: {e}",
        }
    
    # ========== 2. 校验前端传的队伍ID格式 ==========
    validated_team_ids: List[str] = []
    for tid in request.team_ids:
        try:
            validated_team_ids.append(str(UUID(tid)))
        except ValueError:
            return {
                "success": False,
                "error": f"无效的队伍ID格式: {tid}",
            }
    
    if not validated_team_ids:
        return {
            "success": False,
            "error": "未选择任何队伍",
        }
    
    logger.info(f"[EmergencyConfirm] 校验通过 event_id={event_id}, 队伍数={len(validated_team_ids)}")
    
    # ========== 3. Break Glass 审计检查并记录（如需） ==========
    if not ai_result.get("recommended_scheme"):
        return {
            "success": False,
            "error": "缺少推荐方案，无法确认执行",
        }

    recommended_scheme = ai_result["recommended_scheme"]
    bg_rules = recommended_scheme.get("break_glass_rules") or recommended_scheme.get("safety_classification", {}).get("break_glass", [])

    audit_override_ids: List[str] = []

    if bg_rules:
        # 演示环境：若未提供操作者信息，仅记录警告，不阻断。正式环境应从token获取并强制审计。
        if not (request.operator_id and request.operator_name and request.operator_role and request.auth_method):
            logger.warning("[EmergencyConfirm] 缺少操作者信息，跳过 Break Glass 审计(演示模式)")
        else:
            allocations = recommended_scheme.get("allocations", [])
            selected_allocations = [a for a in allocations if a.get("resource_id") in validated_team_ids]
            if not selected_allocations:
                logger.warning("[EmergencyConfirm] 无匹配分配，跳过 Break Glass 审计(演示模式)")
            else:
                operator = OperatorInfo(
                    operator_id=request.operator_id,
                    operator_name=request.operator_name,
                    operator_role=request.operator_role,
                    auth_method=request.auth_method,
                )

                action = ActionInfo(
                    action_type="execute_scheme",
                    target_resource={
                        "team_ids": validated_team_ids,
                        "allocations": selected_allocations,
                    },
                    target_event={
                        "event_id": str(event_id),
                        "scenario_id": str(scenario_id),
                    },
                )

                async with AsyncSessionLocal() as audit_db:
                    audit_service = AuditService(audit_db)
                    for rule in bg_rules:
                        rule_id = rule.get("rule_id") or rule.get("id")
                        rule_name = rule.get("rule_name") or rule.get("name") or ""
                        risk_desc = rule.get("risk_description") or rule.get("message") or ""
                        if not rule_id or not rule_name or not risk_desc:
                            logger.warning("[EmergencyConfirm] Break Glass 规则信息不完整，跳过审计记录")
                            continue
                        record = await audit_service.record_break_glass(
                            operator=operator,
                            rule_id=rule_id,
                            rule_name=rule_name,
                            risk_overridden=risk_desc,
                            action=action,
                            ai_recommendation=None,
                            context={
                                "scheme_id": recommended_scheme.get("solution_id"),
                                "event_id": str(event_id),
                                "scenario_id": str(scenario_id),
                                "task_id": task_id,
                            },
                            was_adopted=False,
                        )
                        audit_override_ids.append(str(record.id))

    # ========== 4-8. 在事务中执行所有数据库操作 ==========
    async with AsyncSessionLocal() as db:
        try:
            # 3. 查询事件详情
            event_query = text("""
                SELECT id, title, description, priority, status,
                       ST_X(location::geometry) as lng, ST_Y(location::geometry) as lat
                FROM operational_v2.events_v2
                WHERE id = :event_id
            """)
            event_result = await db.execute(event_query, {"event_id": str(event_id)})
            event_row = event_result.fetchone()
            
            if not event_row:
                return {
                    "success": False,
                    "error": f"事件不存在: {event_id}",
                }
            
            event_title: str = event_row.title or "救援任务"
            event_description: str = event_row.description or ""
            event_priority: str = event_row.priority or "medium"
            event_status: str = event_row.status
            event_lng: float = event_row.lng
            event_lat: float = event_row.lat
            
            logger.info(f"[EmergencyConfirm] 事件详情 title={event_title}, status={event_status}")
            
            # 4. 查询队伍信息并校验状态
            placeholders = ','.join(f"'{tid}'" for tid in validated_team_ids)
            team_query = text(f"""
                SELECT id, name, status
                FROM operational_v2.rescue_teams_v2
                WHERE id IN ({placeholders})
            """)
            team_result = await db.execute(team_query)
            teams = team_result.fetchall()
            
            # 构建队伍信息映射
            team_info_map: Dict[str, Dict[str, Any]] = {}
            unavailable_teams: List[Dict[str, Any]] = []
            available_teams: List[Dict[str, Any]] = []
            
            for team in teams:
                team_id_str = str(team.id)
                team_info_map[team_id_str] = {
                    "id": team_id_str,
                    "name": team.name,
                    "status": team.status,
                }
                if team.status != "standby":
                    unavailable_teams.append({
                        "id": team_id_str,
                        "name": team.name,
                        "current_status": team.status,
                    })
                else:
                    available_teams.append({
                        "id": team_id_str,
                        "name": team.name,
                    })
            
            # 检查未找到的队伍
            found_ids = set(team_info_map.keys())
            for tid in validated_team_ids:
                if tid not in found_ids:
                    unavailable_teams.append({
                        "id": tid,
                        "name": "未知队伍",
                        "current_status": "not_found",
                    })
            
            # 如果有不可用队伍，返回冲突
            if unavailable_teams:
                logger.warning(f"[EmergencyConfirm] 存在冲突 不可用队伍={len(unavailable_teams)}")
                return {
                    "success": False,
                    "conflict": True,
                    "unavailable_teams": unavailable_teams,
                    "available_teams": [t["id"] for t in available_teams],
                    "message": f"有 {len(unavailable_teams)} 支队伍不可用",
                }
            
            # ========== 5. 创建方案记录(schemes_v2) ==========
            scheme_id = uuid_lib.uuid4()
            scheme_code = f"SCH-{datetime.now().strftime('%Y%m%d')}-{uuid_lib.uuid4().hex[:4].upper()}"
            
            insert_scheme = text("""
                INSERT INTO operational_v2.schemes_v2 (
                    id, scenario_id, event_id, scheme_code, scheme_type,
                    title, objective, status, source, ai_reasoning,
                    created_at, updated_at
                ) VALUES (
                    :id, :scenario_id, :event_id, :scheme_code, 'search_rescue',
                    :title, :objective, 'approved', 'ai_generated', :ai_reasoning,
                    now(), now()
                )
            """)
            await db.execute(insert_scheme, {
                "id": str(scheme_id),
                "scenario_id": str(scenario_id),
                "event_id": str(event_id),
                "scheme_code": scheme_code,
                "title": f"{event_title} - 救援方案",
                "objective": f"针对{event_title}事件，快速响应并完成救援任务",
                "ai_reasoning": scheme_explanation[:2000],
            })
            logger.info(f"[EmergencyConfirm] 创建方案 scheme_id={scheme_id}, scheme_code={scheme_code}")
            
            # ========== 5.5 检查多点位分配结果 ==========
            multi_point = ai_result.get("multi_point_allocation", {})
            rescue_points_alloc = multi_point.get("rescue_points", []) if multi_point.get("enabled") else []
            
            # 获取下一个任务编号
            code_query = text("""
                SELECT COALESCE(MAX(CAST(SUBSTRING(task_code FROM 5) AS INTEGER)), 0) + 1
                FROM operational_v2.tasks_v2
                WHERE scenario_id = :scenario_id
            """)
            code_result = await db.execute(code_query, {"scenario_id": str(scenario_id)})
            next_code = code_result.scalar() or 1
            
            created_tasks: List[Dict[str, Any]] = []
            task_team_map: Dict[str, List[Dict[str, Any]]] = {}  # task_id -> teams
            
            if rescue_points_alloc:
                # ========== 多救援点模式：为每个救援点创建任务 ==========
                logger.info(f"[EmergencyConfirm] 多救援点模式: {len(rescue_points_alloc)} 个救援点")
                
                for idx, point_alloc in enumerate(rescue_points_alloc):
                    point_id = point_alloc.get("rescue_point_id")
                    point_name = point_alloc.get("rescue_point_name", f"救援点{idx+1}")
                    point_location = point_alloc.get("location", {})
                    point_lat = point_location.get("latitude", event_lat)
                    point_lng = point_location.get("longitude", event_lng)
                    victims = point_alloc.get("estimated_victims", 0)
                    priority = point_alloc.get("priority", event_priority)
                    assigned_teams = point_alloc.get("assigned_teams", [])
                    
                    # 过滤出用户选中的队伍
                    selected_teams = [
                        t for t in assigned_teams 
                        if t.get("team_id") in validated_team_ids
                    ]
                    
                    if not selected_teams:
                        logger.info(f"[EmergencyConfirm] 救援点'{point_name}'无选中队伍，跳过")
                        continue
                    
                    new_task_id = uuid_lib.uuid4()
                    task_code = f"TSK-{next_code:04d}"
                    next_code += 1
                    
                    task_title = f"{point_name}救援任务（{victims}人被困）" if victims > 0 else f"{point_name}救援任务"
                    task_description = f"{event_description}\n\n【救援点】{point_name}\n预估被困: {victims}人\n\n【AI方案说明】\n{scheme_explanation[:300]}"
                    
                    insert_task = text("""
                        INSERT INTO operational_v2.tasks_v2 (
                            id, scenario_id, event_id, scheme_id, rescue_point_id, task_code, task_type,
                            title, description, status, priority,
                            target_location, instructions, created_at, updated_at
                        ) VALUES (
                            :id, :scenario_id, :event_id, :scheme_id, :rescue_point_id, :task_code, 'rescue',
                            :title, :description, 'assigned', :priority,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                            :instructions, now(), now()
                        )
                    """)
                    await db.execute(insert_task, {
                        "id": str(new_task_id),
                        "scenario_id": str(scenario_id),
                        "event_id": str(event_id),
                        "scheme_id": str(scheme_id),
                        "rescue_point_id": point_id,
                        "task_code": task_code,
                        "title": task_title,
                        "description": task_description,
                        "priority": priority,
                        "lng": point_lng,
                        "lat": point_lat,
                        "instructions": f"前往{point_name}执行救援",
                    })
                    
                    created_tasks.append({
                        "task_id": str(new_task_id),
                        "task_code": task_code,
                        "rescue_point_id": point_id,
                        "rescue_point_name": point_name,
                        "location": {"lat": point_lat, "lng": point_lng},
                    })
                    task_team_map[str(new_task_id)] = selected_teams
                    
                    logger.info(f"[EmergencyConfirm] 创建任务 task_code={task_code} for '{point_name}', 队伍数={len(selected_teams)}")
            else:
                # ========== 单任务模式（向后兼容） ==========
                new_task_id = uuid_lib.uuid4()
                task_code = f"TSK-{next_code:04d}"
                task_title = f"{event_title} - 救援任务"
                task_description = f"{event_description}\n\n【AI方案说明】\n{scheme_explanation[:500]}"
                
                insert_task = text("""
                    INSERT INTO operational_v2.tasks_v2 (
                        id, scenario_id, event_id, scheme_id, task_code, task_type,
                        title, description, status, priority,
                        target_location, instructions, created_at, updated_at
                    ) VALUES (
                        :id, :scenario_id, :event_id, :scheme_id, :task_code, 'rescue',
                        :title, :description, 'assigned', :priority,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                        :instructions, now(), now()
                    )
                """)
                await db.execute(insert_task, {
                    "id": str(new_task_id),
                    "scenario_id": str(scenario_id),
                    "event_id": str(event_id),
                    "scheme_id": str(scheme_id),
                    "task_code": task_code,
                    "title": task_title,
                    "description": task_description,
                    "priority": event_priority,
                    "lng": event_lng,
                    "lat": event_lat,
                    "instructions": scheme_explanation[:1000],
                })
                
                created_tasks.append({
                    "task_id": str(new_task_id),
                    "task_code": task_code,
                    "location": {"lat": event_lat, "lng": event_lng},
                })
                task_team_map[str(new_task_id)] = [{"team_id": t["id"], "team_name": t["name"], "task_description": "AI智能推荐"} for t in available_teams]
                
                logger.info(f"[EmergencyConfirm] 创建任务 task_id={new_task_id}, task_code={task_code}")
            
            # ========== 6. 创建分配记录（使用AI生成的task_description） ==========
            total_assignments = 0
            all_deployed_teams: List[Dict[str, Any]] = []
            
            for task_id_str, teams in task_team_map.items():
                for team in teams:
                    assignment_id = uuid_lib.uuid4()
                    team_id = team.get("team_id") or team.get("id")
                    team_name = team.get("team_name") or team.get("name")
                    task_desc = team.get("task_description", "AI智能推荐")
                    
                    insert_assignment = text("""
                        INSERT INTO operational_v2.task_assignments_v2 (
                            id, task_id, assignee_type, assignee_id, assignee_name,
                            assignment_source, assignment_reason, status,
                            assigned_at, created_at, updated_at
                        ) VALUES (
                            :id, :task_id, 'team', :assignee_id, :assignee_name,
                            'ai_recommended', :reason, 'pending',
                            now(), now(), now()
                        )
                    """)
                    await db.execute(insert_assignment, {
                        "id": str(assignment_id),
                        "task_id": task_id_str,
                        "assignee_id": team_id,
                        "assignee_name": team_name,
                        "reason": task_desc,
                    })
                    total_assignments += 1
                    
                    if team_id not in [t["id"] for t in all_deployed_teams]:
                        all_deployed_teams.append({"id": team_id, "name": team_name})
            
            logger.info(f"[EmergencyConfirm] 创建分配记录 数量={total_assignments}")
            
            # ========== 7. 更新队伍状态 ==========
            # 在多任务模式下，每个队伍关联到其第一个任务
            first_task_id = created_tasks[0]["task_id"] if created_tasks else str(new_task_id)
            team_id_list = [t["id"] for t in all_deployed_teams] if all_deployed_teams else [t["id"] for t in available_teams]
            
            if team_id_list:
                placeholders = ','.join(f"'{tid}'" for tid in team_id_list)
                update_teams = text(f"""
                    UPDATE operational_v2.rescue_teams_v2
                    SET status = 'deployed',
                        current_task_id = :task_id,
                        updated_at = now()
                    WHERE id IN ({placeholders})
                      AND status = 'standby'
                    RETURNING id, name
                """)
                update_result = await db.execute(update_teams, {"task_id": first_task_id})
                deployed_rows = update_result.fetchall()
                deployed_info = [{"id": str(r.id), "name": r.name} for r in deployed_rows]
            else:
                deployed_info = []
            
            logger.info(f"[EmergencyConfirm] 更新队伍状态 deployed={len(deployed_info)}")
            
            # 刷新事务，确保任务记录对后续外键检查可见
            await db.flush()
            
            # ========== 7.5 为每个队伍生成路径规划（到对应救援点） ==========
            # 构建队伍到目的地的映射
            team_destination_map: Dict[str, Dict[str, float]] = {}
            for task in created_tasks:
                task_id_str = task["task_id"]
                task_location = task.get("location", {})
                dest_lat = task_location.get("lat", event_lat)
                dest_lng = task_location.get("lng", event_lng)
                
                for team in task_team_map.get(task_id_str, []):
                    team_id = team.get("team_id") or team.get("id")
                    if team_id and team_id not in team_destination_map:
                        team_destination_map[team_id] = {"lat": dest_lat, "lng": dest_lng, "task_id": task_id_str}
            
            logger.info(f"[EmergencyConfirm] 开始路径规划 deployed_info={deployed_info}")
            route_results: List[Dict[str, Any]] = []
            for team in deployed_info:
                dest = team_destination_map.get(team["id"], {"lat": event_lat, "lng": event_lng, "task_id": first_task_id})
                try:
                    route_result = await _generate_team_route(
                        db=db,
                        team_id=UUID(team["id"]),
                        task_id=UUID(dest["task_id"]),
                        scenario_id=scenario_id,
                        destination_lng=dest["lng"],
                        destination_lat=dest["lat"],
                    )
                    if route_result:
                        route_results.append({
                            "team_id": team["id"],
                            "team_name": team["name"],
                            **route_result,
                        })
                        logger.info(
                            f"[EmergencyConfirm] 队伍路径规划成功: team={team['name']}, "
                            f"route_id={route_result.get('route_id')}, "
                            f"distance={route_result.get('distance_m', 0)/1000:.1f}km"
                        )
                except Exception as route_err:
                    logger.warning(
                        f"[EmergencyConfirm] 队伍路径规划失败: team={team['name']}, error={route_err}"
                    )
            
            logger.info(f"[EmergencyConfirm] 路径规划完成 成功={len(route_results)}/{len(deployed_info)}")
            
            # ========== 7.6 启动队伍移动仿真 ==========
            from src.domains.movement_simulation.team_dispatch_service import TeamDispatchService
            from src.domains.movement_simulation.schemas import TeamDispatchRequest
            
            dispatch_service = TeamDispatchService(db)
            movement_sessions = []
            for route in route_results:
                dest = team_destination_map.get(route["team_id"], {"lat": event_lat, "lng": event_lng, "task_id": first_task_id})
                try:
                    # 使用已规划的路径启动移动
                    task_id_for_dispatch = UUID(dest["task_id"]) if dest.get("task_id") else None
                    dispatch_request = TeamDispatchRequest(
                        destination=[dest["lng"], dest["lat"]],
                        scenario_id=scenario_id,
                        task_id=task_id_for_dispatch,
                        speed_mps=15.0,  # 救援车辆默认速度 54km/h
                    )
                    dispatch_response = await dispatch_service.dispatch_team(
                        team_id=UUID(route["team_id"]),
                        request=dispatch_request,
                    )
                    movement_sessions.append({
                        "team_id": route["team_id"],
                        "team_name": route["team_name"],
                        "session_id": dispatch_response.session_id,
                    })
                    logger.info(
                        f"[EmergencyConfirm] 队伍移动启动: team={route['team_name']}, "
                        f"session={dispatch_response.session_id}"
                    )
                except Exception as move_err:
                    logger.warning(
                        f"[EmergencyConfirm] 队伍移动启动失败: team={route.get('team_name')}, error={move_err}"
                    )
            
            logger.info(f"[EmergencyConfirm] 移动仿真启动完成 成功={len(movement_sessions)}/{len(route_results)}")
            
            # ========== 8. 更新事件状态 ==========
            # 状态转换: confirmed → planning
            if event_status == "confirmed":
                update_event = text("""
                    UPDATE operational_v2.events_v2
                    SET status = 'planning', updated_at = now()
                    WHERE id = :event_id
                """)
                await db.execute(update_event, {"event_id": str(event_id)})
                logger.info(f"[EmergencyConfirm] 事件状态更新 {event_status} → planning")
            elif event_status == "planning":
                # 已经是planning状态，可以保持或更新为executing
                pass
            
            # 提交事务
            await db.commit()
            
            logger.info(
                f"[EmergencyConfirm] 确认成功 tasks={len(created_tasks)}, "
                f"deployed={len(deployed_info)}"
            )
            
            # ========== 9. WebSocket推送 ==========
            try:
                await broadcast_event_update(
                    scenario_id=scenario_id,
                    event_type="rescue_task_created",
                    event_data={
                        "event_id": str(event_id),
                        "scheme_id": str(scheme_id),
                        "scheme_code": scheme_code,
                        "tasks": created_tasks,
                        "deployed_teams": deployed_info,
                    },
                )
                logger.info("[EmergencyConfirm] WebSocket推送成功")
            except Exception as ws_err:
                logger.warning(f"[EmergencyConfirm] WebSocket推送失败: {ws_err}")

            # ========== 10. APP用户任务推送 ==========
            # 推送目标: 1) 所有internal用户(admin/commander等) 2) 任务分配队伍的队长
            # 消息格式: 符合APP端TaskPushMessage接口
            try:
                from src.core.stomp.broker import stomp_broker
                import re
                import asyncio

                def normalize_phone(phone: str) -> str:
                    """规范化手机号，去除空格、连字符、前导+86等"""
                    if not phone:
                        return ""
                    normalized = re.sub(r'[\s\-+]', '', phone)
                    if normalized.startswith('86') and len(normalized) > 11:
                        normalized = normalized[2:]
                    return normalized

                async def send_with_retry(
                    user_id: str,
                    destination: str,
                    data: dict,
                    max_retries: int = 3
                ) -> bool:
                    """带重试的推送，失败时最多重试max_retries次"""
                    for attempt in range(max_retries):
                        try:
                            await stomp_broker.send_to_user(user_id, destination, data)
                            logger.debug(f"[TaskPush] 推送成功: user_id={user_id}, attempt={attempt+1}")
                            return True
                        except Exception as e:
                            logger.warning(f"[TaskPush] 推送失败(attempt={attempt+1}): user_id={user_id}, error={e}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(0.5 * (attempt + 1))
                    return False

                # 查询所有 internal 用户（前突指挥车队人员，需要收到所有任务通知）
                internal_users_sql = text("""
                    SELECT id, username, real_name
                    FROM operational_v2.users_v2
                    WHERE user_type = 'internal' AND status = 'active'
                """)
                internal_result = await db.execute(internal_users_sql)
                internal_users = internal_result.fetchall()

                # 查询任务分配队伍的队员/队长（通过规范化手机号匹配）
                # deployed_info 结构: {"id": team_id, "name": team_name}
                team_ids = [team.get("id") for team in deployed_info if team.get("id")]
                leader_users: list[Any] = []
                if team_ids:
                    team_ids_str = ",".join([f"'{tid}'" for tid in team_ids])
                    # 1) 队伍队员：team_members_v2.contact_phone
                    member_sql = text(f"""
                        SELECT DISTINCT u.id, u.username, u.real_name, m.team_id as team_id, t.name as team_name
                        FROM operational_v2.users_v2 u
                        JOIN operational_v2.team_members_v2 m
                            ON REGEXP_REPLACE(REGEXP_REPLACE(u.phone, '[\\s\\-+]', '', 'g'), '^86', '') =
                               REGEXP_REPLACE(REGEXP_REPLACE(m.contact_phone, '[\\s\\-+]', '', 'g'), '^86', '')
                        JOIN operational_v2.rescue_teams_v2 t ON m.team_id = t.id
                        WHERE m.team_id IN ({team_ids_str})
                        AND u.status = 'active'
                        AND u.phone IS NOT NULL
                        AND m.contact_phone IS NOT NULL
                    """)
                    member_result = await db.execute(member_sql)
                    member_users = member_result.fetchall()

                    # 使用REGEXP_REPLACE规范化手机号进行匹配
                    leader_sql = text(f"""
                        SELECT u.id, u.username, u.real_name, t.id as team_id, t.name as team_name
                        FROM operational_v2.users_v2 u
                        JOIN operational_v2.rescue_teams_v2 t
                            ON REGEXP_REPLACE(REGEXP_REPLACE(u.phone, '[\\s\\-+]', '', 'g'), '^86', '') =
                               REGEXP_REPLACE(REGEXP_REPLACE(t.contact_phone, '[\\s\\-+]', '', 'g'), '^86', '')
                        WHERE t.id IN ({team_ids_str})
                        AND u.status = 'active'
                        AND u.phone IS NOT NULL
                        AND t.contact_phone IS NOT NULL
                    """)
                    leader_result = await db.execute(leader_sql)
                    leader_users = leader_result.fetchall()
                    logger.info(
                        f"[TaskPush] 队伍用户匹配结果: team_ids={team_ids}, "
                        f"members={len(member_users)}, leaders={len(leader_users)}"
                    )
                else:
                    member_users = []

                # 构建任务ID到队伍的映射
                task_to_teams: dict[str, list[dict]] = {}
                for task in created_tasks:
                    task_id = task.get("task_id")
                    if task_id and task_id in task_team_map:
                        task_to_teams[task_id] = task_team_map[task_id]

                # 为每个任务构建符合APP端TaskPushMessage格式的消息
                notified_user_ids: set[str] = set()
                push_success_count = 0
                push_fail_count = 0

                for task in created_tasks:
                    task_id = task.get("task_id")
                    task_code = task.get("task_code", "")
                    location = task.get("location", {})
                    point_name = task.get("rescue_point_name", "")

                    # 获取该任务分配的队伍
                    assigned_teams = task_to_teams.get(task_id, [])
                    units = [
                        {"team_id": str(t.get("team_id") or t.get("id")), "team_name": t.get("team_name") or t.get("name", "")}
                        for t in assigned_teams
                    ]

                    # 构建符合APP端TaskPushMessage接口的消息
                    task_push_message = {
                        "task_id": task_id,
                        "event_id": str(event_id),
                        "task_code": task_code,
                        "title": f"{event_title} - {point_name}" if point_name else event_title,
                        "priority": event_priority,
                        "target_location": {"longitude": location.get("lng"), "latitude": location.get("lat")} if location else None,
                        "target_address": point_name or "",
                        "units": units,
                        "created_at": datetime.utcnow().isoformat() + "Z",
                        "scenario_id": str(scenario_id),
                    }

                    # 场景广播：让已连接且带 scenario_id 的客户端可以收到任务下发（/topic/scenario.task.triggered）
                    try:
                        await stomp_broker.broadcast_task(task_push_message, scenario_id)
                    except Exception as broadcast_err:
                        logger.warning(f"[TaskPush] 场景任务广播失败: task_id={task_id}, error={broadcast_err}")

                    # 推送给 internal 用户
                    for user in internal_users:
                        user_id_str = str(user.id)
                        if user_id_str not in notified_user_ids:
                            success = await send_with_retry(user_id_str, "/task/assigned", task_push_message)
                            if success:
                                push_success_count += 1
                            else:
                                push_fail_count += 1
                            notified_user_ids.add(user_id_str)

                    # 推送给该任务分配队伍的队长
                    assigned_team_ids = {str(t.get("team_id") or t.get("id")) for t in assigned_teams}

                    # 推送给该任务分配队伍的队员
                    for member in member_users:
                        member_team_id = str(member.team_id)
                        if member_team_id in assigned_team_ids:
                            user_id_str = str(member.id)
                            if user_id_str not in notified_user_ids:
                                success = await send_with_retry(user_id_str, "/task/assigned", task_push_message)
                                if success:
                                    push_success_count += 1
                                else:
                                    push_fail_count += 1
                                notified_user_ids.add(user_id_str)

                    for leader in leader_users:
                        leader_team_id = str(leader.team_id)
                        if leader_team_id in assigned_team_ids:
                            user_id_str = str(leader.id)
                            if user_id_str not in notified_user_ids:
                                success = await send_with_retry(user_id_str, "/task/assigned", task_push_message)
                                if success:
                                    push_success_count += 1
                                else:
                                    push_fail_count += 1
                                notified_user_ids.add(user_id_str)

                # 更新 task_assignments_v2.notified_at
                if team_ids:
                    for task in created_tasks:
                        task_id = task.get("task_id")
                        if task_id:
                            update_notified = text("""
                                UPDATE operational_v2.task_assignments_v2
                                SET notified_at = now()
                                WHERE task_id = :task_id AND notified_at IS NULL
                            """)
                            await db.execute(update_notified, {"task_id": task_id})
                    await db.commit()

                logger.info(
                    f"[EmergencyConfirm] APP用户推送完成: "
                    f"internal={len(internal_users)}, leaders={len(leader_users)}, "
                    f"total_notified={len(notified_user_ids)}, "
                    f"success={push_success_count}, fail={push_fail_count}"
                )
            except Exception as push_err:
                logger.warning(f"[EmergencyConfirm] APP用户推送失败: {push_err}")
            
            # 构建返回结果
            primary_task = created_tasks[0] if created_tasks else {}
            return {
                "success": True,
                "scheme_id": str(scheme_id),
                "scheme_code": scheme_code,
                "task_id": primary_task.get("task_id"),  # 向后兼容：返回第一个任务ID
                "task_code": primary_task.get("task_code"),  # 向后兼容：返回第一个任务编号
                "tasks": created_tasks,  # 新增：所有创建的任务
                "deployed_teams": deployed_info,
                "route_results": route_results,
                "audit_overrides": audit_override_ids,
                "message": f"成功创建方案 {scheme_code}，{len(created_tasks)} 个任务，部署 {len(deployed_info)} 支队伍",
            }
            
        except Exception as e:
            await db.rollback()
            logger.exception(f"[EmergencyConfirm] 确认失败: {e}")
            return {
                "success": False,
                "error": f"确认部署失败: {str(e)}",
            }


async def _generate_team_route(
    db: AsyncSession,
    team_id: UUID,
    task_id: UUID,
    scenario_id: UUID,
    destination_lng: float,
    destination_lat: float,
) -> Optional[Dict[str, Any]]:
    """
    为队伍生成路径规划
    
    查询队伍驻地位置和关联设备，调用路径规划服务生成路径。
    
    Args:
        db: 数据库会话
        team_id: 队伍ID
        task_id: 任务ID（用于关联路径）
        scenario_id: 场景ID（用于风险检测）
        destination_lng: 目的地经度
        destination_lat: 目的地纬度
        
    Returns:
        路径规划结果，包含 route_id, distance_m, has_risk 等
    """
    from sqlalchemy import text
    from src.domains.routing.planned_route_service import PlannedRouteService
    from src.domains.routing.schemas import Point
    
    logger.info(
        f"[_generate_team_route] 开始规划: team_id={team_id}, "
        f"task_id={task_id}, dest=({destination_lng},{destination_lat})"
    )
    
    # 1. 查询队伍位置和关联设备（优先选择陆地设备用于路径规划）
    team_query = text("""
        SELECT 
            t.id as team_id,
            t.name as team_name,
            ST_X(t.base_location::geometry) as base_lng,
            ST_Y(t.base_location::geometry) as base_lat,
            d.id as device_id,
            d.env_type as device_env_type
        FROM operational_v2.rescue_teams_v2 t
        LEFT JOIN operational_v2.team_vehicles_v2 tv ON tv.team_id = t.id AND tv.is_primary = true
        LEFT JOIN operational_v2.vehicles_v2 v ON tv.vehicle_id = v.id
        LEFT JOIN operational_v2.devices_v2 d ON d.in_vehicle_id = v.id AND d.env_type = 'land'
        WHERE t.id = :team_id
        LIMIT 1
    """)
    
    result = await db.execute(team_query, {"team_id": str(team_id)})
    row = result.fetchone()
    
    if not row:
        logger.warning(f"[_generate_team_route] 队伍不存在: team_id={team_id}")
        return None
    
    logger.info(
        f"[_generate_team_route] 查询结果: team={row.team_name}, "
        f"origin=({row.base_lng},{row.base_lat}), device_id={row.device_id}"
    )
    
    # 检查队伍位置
    if row.base_lng is None or row.base_lat is None:
        logger.warning(f"[_generate_team_route] 队伍无位置信息: team={row.team_name}")
        return None
    
    origin_lng: float = row.base_lng
    origin_lat: float = row.base_lat
    device_id: Optional[UUID] = row.device_id
    
    # 如果没有关联设备，查询任意可用的陆地设备
    if device_id is None:
        logger.info(f"[_generate_team_route] 队伍无关联陆地设备，查询备用设备")
        device_query = text("""
            SELECT id FROM operational_v2.devices_v2
            WHERE env_type = 'land' AND status = 'available'
            LIMIT 1
        """)
        device_result = await db.execute(device_query)
        device_row = device_result.fetchone()
        if device_row:
            device_id = device_row.id
            logger.info(f"[_generate_team_route] 使用备用设备: device_id={device_id}")
        else:
            logger.warning(f"[_generate_team_route] 无可用设备: team={row.team_name}")
            return None
    
    logger.info(f"[_generate_team_route] 最终使用设备: device_id={device_id}")
    
    # 2. 调用路径规划服务
    route_service = PlannedRouteService(db)
    
    origin = Point(lon=origin_lng, lat=origin_lat)
    destination = Point(lon=destination_lng, lat=destination_lat)
    
    logger.info(
        f"[_generate_team_route] 调用 plan_and_save: "
        f"origin=({origin.lon},{origin.lat}), dest=({destination.lon},{destination.lat})"
    )
    
    try:
        plan_result = await route_service.plan_and_save(
            device_id=device_id,
            origin=origin,
            destination=destination,
            task_id=task_id,
            team_id=team_id,
            scenario_id=scenario_id,
        )
        
        logger.info(f"[_generate_team_route] plan_and_save 返回: success={plan_result.get('success')}, route_id={plan_result.get('route_id')}")
        
        if not plan_result.get("success"):
            logger.warning(
                f"[_generate_team_route] 路径规划失败: team={row.team_name}, "
                f"error={plan_result.get('error')}"
            )
            return None
    except Exception as e:
        logger.exception(f"[_generate_team_route] plan_and_save 异常: team={row.team_name}, error={e}")
        return None
    
    # 提取 polyline 用于前端渲染
    polyline = plan_result.get("route", {}).get("polyline", [])
    
    # 3. 如果检测到风险，广播 STOMP 预警消息
    broadcast_sent = False
    if plan_result.get("has_risk") and plan_result.get("risk_areas"):
        try:
            from src.core.stomp.broker import stomp_broker
            await stomp_broker.broadcast_alert(
                alert_data={
                    "event_type": "route_risk_warning",
                    "task_id": str(task_id),
                    "team_id": str(team_id),
                    "team_name": row.team_name,
                    "route_id": plan_result.get("route_id"),
                    "risk_areas": plan_result.get("risk_areas"),
                    "origin": {"lon": origin_lng, "lat": origin_lat},
                    "destination": {"lon": destination_lng, "lat": destination_lat},
                    "requires_decision": True,
                    "available_actions": ["continue", "detour", "standby"],
                },
                scenario_id=scenario_id,
            )
            broadcast_sent = True
            logger.info(
                f"[_generate_team_route] 已广播风险预警: team={row.team_name}, "
                f"风险区域数={len(plan_result.get('risk_areas', []))}"
            )
        except Exception as ws_err:
            logger.warning(f"[_generate_team_route] 风险预警广播失败: {ws_err}")
    
    # 4. 记录风险检测日志到 ai_decision_logs_v2 表
    try:
        from src.domains.ai_decisions import AIDecisionLogRepository, CreateAIDecisionLogRequest
        import time
        
        log_request = CreateAIDecisionLogRequest(
            scenario_id=scenario_id,
            event_id=None,
            decision_type="risk_detection",
            algorithm_used="PostGIS_ST_Intersects_UNION",
            input_snapshot={
                "team_id": str(team_id),
                "team_name": row.team_name,
                "task_id": str(task_id),
                "origin": {"lon": origin_lng, "lat": origin_lat},
                "destination": {"lon": destination_lng, "lat": destination_lat},
                "polyline_points_count": len(polyline),
                "route_id": plan_result.get("route_id"),
            },
            output_result={
                "has_risk": plan_result.get("has_risk", False),
                "risk_areas_count": len(plan_result.get("risk_areas", [])),
                "risk_areas": plan_result.get("risk_areas", []),
                "broadcast_sent": broadcast_sent,
            },
        )
        
        log_repo = AIDecisionLogRepository(db)
        await log_repo.create(log_request)
        await db.commit()
        logger.info(
            f"[_generate_team_route] 风险检测日志已记录: team={row.team_name}, "
            f"has_risk={plan_result.get('has_risk')}, broadcast_sent={broadcast_sent}"
        )
    except Exception as log_err:
        logger.warning(f"[_generate_team_route] 风险检测日志记录失败: {log_err}")
    
    return {
        "route_id": plan_result.get("route_id"),
        "distance_m": plan_result.get("route", {}).get("total_distance_m", 0),
        "duration_s": plan_result.get("route", {}).get("total_duration_s", 0),
        "has_risk": plan_result.get("has_risk", False),
        "risk_areas": plan_result.get("risk_areas", []),
        "polyline": polyline,  # 路径坐标点列表 [{lon, lat}, ...]
    }


# ============================================================================
# 路径规划智能体接口
# ============================================================================

# 路径规划结果缓存
_route_planning_results: Dict[str, Dict[str, Any]] = {}
ROUTE_PLANNING_PREFIX = "route_planning_result:"


async def _save_route_result_to_redis(task_id: str, result: Dict[str, Any]) -> bool:
    """保存路径规划结果到Redis"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        key = f"{ROUTE_PLANNING_PREFIX}{task_id}"
        await redis_client.setex(key, EMERGENCY_RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
        logger.info(f"[RoutePlanning] 结果已保存到Redis: {key}")
        return True
    except Exception as e:
        logger.warning(f"[RoutePlanning] Redis保存失败: {e}")
        return False


async def _get_route_result_from_redis(task_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取路径规划结果"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        key = f"{ROUTE_PLANNING_PREFIX}{task_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"[RoutePlanning] Redis读取失败: {e}")
        return None


async def _run_route_planning(
    task_id: str,
    request: RoutePlanningRequest,
) -> None:
    """后台执行路径规划任务"""
    import traceback
    
    logger.info(f"[RoutePlanning] 开始执行 task_id={task_id} type={request.request_type}")
    
    try:
        # 构建参数
        start = {"lon": request.start.lon, "lat": request.start.lat} if request.start else None
        end = {"lon": request.end.lon, "lat": request.end.lat} if request.end else None
        depot = {"lon": request.depot_location.lon, "lat": request.depot_location.lat} if request.depot_location else None
        
        vehicles = None
        if request.vehicles:
            vehicles = [
                {
                    "vehicle_id": v.vehicle_id,
                    "vehicle_code": v.vehicle_code,
                    "vehicle_type": v.vehicle_type,
                    "max_speed_kmh": v.max_speed_kmh,
                    "is_all_terrain": v.is_all_terrain,
                    "capacity": v.capacity,
                    "current_location": {"lon": v.current_location.lon, "lat": v.current_location.lat},
                }
                for v in request.vehicles
            ]
        
        task_points = None
        if request.task_points:
            task_points = [
                {
                    "id": tp.id,
                    "location": {"lon": tp.location.lon, "lat": tp.location.lat},
                    "demand": tp.demand,
                    "priority": tp.priority,
                    "time_window_start": tp.time_window_start,
                    "time_window_end": tp.time_window_end,
                    "service_time_min": tp.service_time_min,
                }
                for tp in request.task_points
            ]
        
        disaster_context = None
        if request.disaster_context:
            disaster_context = {
                "disaster_type": request.disaster_context.disaster_type,
                "severity": request.disaster_context.severity,
                "urgency_level": request.disaster_context.urgency_level,
                "affected_roads": request.disaster_context.affected_roads,
                "blocked_areas": request.disaster_context.blocked_areas,
                "weather_conditions": request.disaster_context.weather_conditions,
            }
        
        # 调用路径规划智能体
        result = await route_planning_invoke(
            request_type=request.request_type,
            start=start,
            end=end,
            vehicle_id=request.vehicle_id,
            vehicles=vehicles,
            task_points=task_points,
            depot_location=depot,
            scenario_id=request.scenario_id,
            constraints=request.constraints,
            disaster_context=disaster_context,
            natural_language_request=request.natural_language_request,
            request_id=task_id,
        )
        
        logger.info(f"[RoutePlanning] 完成 task_id={task_id} success={result.get('success')}")
        
        # 保存结果
        _route_planning_results[task_id] = result
        await _save_route_result_to_redis(task_id, result)
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"[RoutePlanning] 失败 task_id={task_id} error={e}\n{error_detail}")
        
        error_result = {
            "request_id": task_id,
            "request_type": request.request_type,
            "success": False,
            "errors": [str(e)],
        }
        _route_planning_results[task_id] = error_result
        await _save_route_result_to_redis(task_id, error_result)


@router.post("/route-planning", response_model=RoutePlanningTaskResponse, status_code=202)
async def route_planning(
    request: RoutePlanningRequest,
    background_tasks: BackgroundTasks,
) -> RoutePlanningTaskResponse:
    """
    提交路径规划任务
    
    使用LLM增强的双频架构进行路径规划：
    - 低频层(LLM): 场景分析、策略选择、结果评估、路径解释
    - 高频层(算法): A*路网规划、VRP多车调度
    
    支持三种规划类型：
    - single: 单车点对点规划
    - multi: 多车多点VRP规划
    - replan: 动态重规划
    
    Args:
        request: 规划请求
        
    Returns:
        任务提交响应
    """
    import uuid
    task_id = f"route-{uuid.uuid4().hex[:8]}"
    
    logger.info(f"[RoutePlanning] 收到请求 task_id={task_id} type={request.request_type}")
    
    # 提交后台任务
    background_tasks.add_task(_run_route_planning, task_id, request)
    
    return RoutePlanningTaskResponse(
        success=True,
        task_id=task_id,
        request_type=request.request_type,
        status="processing",
        message="路径规划任务已提交，预计完成时间3-10秒",
        created_at=datetime.utcnow(),
    )


@router.get("/route-planning/{task_id}", response_model=RoutePlanningResult)
async def get_route_planning_result(task_id: str) -> RoutePlanningResult:
    """
    查询路径规划结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        规划结果
    """
    # 优先从内存获取
    result = _route_planning_results.get(task_id)
    
    # 内存没有则从Redis获取
    if result is None:
        result = await _get_route_result_from_redis(task_id)
        if result:
            _route_planning_results[task_id] = result
    
    if result is None:
        raise AITaskNotFoundError(task_id)
    
    return RoutePlanningResult(
        request_id=result.get("request_id", task_id),
        request_type=result.get("request_type", "unknown"),
        success=result.get("success", False),
        route=result.get("route"),
        multi_route=result.get("multi_route"),
        explanation=result.get("explanation"),
        trace=result.get("trace"),
        errors=result.get("errors", []),
    )


# ============ 预警监测智能体路由 ============
from .early_warning.router import router as early_warning_router
router.include_router(early_warning_router)

# ============ 应急监控路由 ============
from .early_warning.monitor_router import router as emergency_monitor_router
router.include_router(emergency_monitor_router)

# ============ 驻扎点选址智能体路由 ============
from .staging_area.router import router as staging_area_agent_router
router.include_router(staging_area_agent_router)

# ============ 任务分发智能体路由 ============
from .task_dispatch.router import router as task_dispatch_router
router.include_router(task_dispatch_router)


# ============================================================================
# 态势标绘API
# ============================================================================

from src.domains.plotting.service import PlottingService
from src.domains.plotting.schemas import (
    PlotPointRequest, PlotCircleRequest, PlotPolygonRequest,
    PlotRouteRequest, PlottingResponse,
    PlotEventRangeRequest, PlotWeatherAreaRequest
)
from .situation_plot import get_situation_plot_agent
from .situation_plot.schemas import SituationPlotRequest, SituationPlotResponse


@router.post("/plotting/point", response_model=PlottingResponse)
async def plot_point_api(request: PlotPointRequest) -> PlottingResponse:
    """
    标绘点位
    
    支持类型:
    - event_point: 事件点
    - rescue_target: 救援目标(波纹动画)
    - situation_point: 态势标注(文字)
    - resettle_point: 安置点
    - resource_point: 资源点
    """
    return await PlottingService.plot_point(request)


@router.post("/plotting/circle", response_model=PlottingResponse)
async def plot_circle_api(request: PlotCircleRequest) -> PlottingResponse:
    """
    标绘圆形区域
    
    支持类型:
    - danger_area: 危险区(橙色)
    - safety_area: 安全区(绿色)
    - command_post_candidate: 指挥点(蓝色)
    """
    return await PlottingService.plot_circle(request)


@router.post("/plotting/polygon", response_model=PlottingResponse)
async def plot_polygon_api(request: PlotPolygonRequest) -> PlottingResponse:
    """标绘多边形区域"""
    return await PlottingService.plot_polygon(request)


@router.post("/plotting/route", response_model=PlottingResponse)
async def plot_route_api(request: PlotRouteRequest) -> PlottingResponse:
    """标绘规划路线"""
    return await PlottingService.plot_route(request)


@router.delete("/plotting/{entity_id}", response_model=PlottingResponse)
async def delete_plot_api(entity_id: UUID) -> PlottingResponse:
    """删除标绘"""
    return await PlottingService.delete_plot(entity_id)


@router.post("/plotting/event-range", response_model=PlottingResponse)
async def plot_event_range_api(request: PlotEventRangeRequest) -> PlottingResponse:
    """
    标绘事件区域范围（三层多边形）
    
    用于标注灾害影响范围的外/中/内三层区域
    """
    return await PlottingService.plot_event_range(request)


@router.post("/plotting/weather", response_model=PlottingResponse)
async def plot_weather_area_api(request: PlotWeatherAreaRequest) -> PlottingResponse:
    """
    标绘天气区域（雨区）
    
    用于标注降雨/恶劣天气影响区域，会显示雨区粒子特效
    """
    return await PlottingService.plot_weather_area(request)


@router.post("/situation-plot", response_model=SituationPlotResponse)
async def situation_plot_dialog(request: SituationPlotRequest) -> SituationPlotResponse:
    """
    对话式态势标绘
    
    通过自然语言指令在地图上创建/删除标绘。
    
    示例:
    - "在北京市朝阳区标一个救援点"
    - "画一个500米的危险区，位置在116.4,39.9"
    - "删除标绘xxx-xxx-xxx"
    """
    agent = get_situation_plot_agent()
    
    # 将scenario_id注入到用户消息中供LLM提取
    user_message = f"[Context: scenario_id={request.scenario_id}]\n\n{request.message}"
    
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": user_message}]},
    )
    
    # 提取最后一条AI消息
    ai_message = result["messages"][-1]
    
    return SituationPlotResponse(
        success=True,
        response=ai_message.content,
    )


# ============================================================================
# 侦察调度接口 (ReconScheduler V2.1)
# ============================================================================

from .schemas import (
    ReconScheduleRequest,
    ReconScheduleTaskResponse,
    ReconScheduleResult,
    ReconApproveRequest,
    ReconCheckpointResponse,
    ReconResumeRequest,
)

# 侦察任务结果缓存
RECON_RESULT_PREFIX = "recon_schedule_result:"
RECON_RESULT_TTL = 36000  # 10小时
_recon_task_results: Dict[str, Dict[str, Any]] = {}


async def _save_recon_result_to_redis(task_id: str, result: Dict[str, Any]) -> bool:
    """保存侦察任务结果到Redis"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        key = f"{RECON_RESULT_PREFIX}{task_id}"
        await redis_client.setex(key, RECON_RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
        logger.info(f"[ReconScheduler] 结果已保存到Redis: {key}")
        return True
    except Exception as e:
        logger.warning(f"[ReconScheduler] Redis保存失败: {e}")
        return False


async def _get_recon_result_from_redis(task_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取侦察任务结果"""
    try:
        from src.core.redis import get_redis_client
        redis_client = await get_redis_client()
        key = f"{RECON_RESULT_PREFIX}{task_id}"
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"[ReconScheduler] Redis读取失败: {e}")
        return None


async def _run_recon_schedule_task(
    task_id: str,
    request: ReconScheduleRequest,
) -> None:
    """后台执行侦察调度任务"""
    from .recon_scheduler import get_recon_scheduler_agent
    
    logger.info(f"[ReconScheduler] 开始执行任务: {task_id}")
    
    try:
        agent = get_recon_scheduler_agent()
        
        # 执行调度
        result = await agent.schedule(
            event_id=request.event_id,
            scenario_id=request.scenario_id,
            recon_request=request.recon_request,
            target_area=request.target_area,
            disaster_context=request.disaster_context,
        )
        
        # 构建结果
        task_result = {
            "task_id": task_id,
            "status": "completed" if result.get("success", False) else "failed",
            "success": result.get("success", False),
            "flight_plans": result.get("flight_plans", []),
            "execution_package": result.get("execution_package"),
            "validation_results": {
                "l1_result": result.get("l1_result"),
                "l2_result": result.get("l2_result"),
            },
            "breaker_state": result.get("breaker_state", "closed"),
            "approval_status": result.get("approval_status"),
            "degradation_options": result.get("degradation_options", []),
            "progress_percent": 100.0 if result.get("success") else result.get("progress_percent", 0),
            "current_phase": result.get("current_phase"),
            "retry_count": result.get("retry_count", 0),
            "warnings": result.get("warnings", []),
            "errors": result.get("errors", []),
            "completed_at": datetime.now().isoformat(),
        }
        
        # 检查是否需要审批
        if result.get("approval_status") == "pending":
            task_result["status"] = "awaiting_approval"
        
    except Exception as e:
        logger.error(f"[ReconScheduler] 任务执行失败: {task_id}, error={e}")
        task_result = {
            "task_id": task_id,
            "status": "failed",
            "success": False,
            "flight_plans": [],
            "errors": [str(e)],
            "completed_at": datetime.now().isoformat(),
        }
    
    # 保存结果
    _recon_task_results[task_id] = task_result
    await _save_recon_result_to_redis(task_id, task_result)
    
    logger.info(f"[ReconScheduler] 任务完成: {task_id}, status={task_result['status']}")


@router.post("/recon-schedule", response_model=ReconScheduleTaskResponse, status_code=202)
async def submit_recon_schedule(
    request: ReconScheduleRequest,
    background_tasks: BackgroundTasks,
) -> ReconScheduleTaskResponse:
    """
    提交侦察调度任务
    
    异步执行，返回task_id用于后续查询结果。
    
    支持配置项:
    - max_retries: 最大重试次数 (默认3)
    - initial_battery_percent: 初始电量 (默认95)
    """
    import uuid
    task_id = f"recon-{uuid.uuid4().hex[:12]}"
    
    logger.info(f"[ReconScheduler] 提交任务: {task_id}, event_id={request.event_id}")
    
    # 初始化任务状态
    _recon_task_results[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "success": False,
        "created_at": datetime.now().isoformat(),
    }
    
    # 后台执行
    background_tasks.add_task(_run_recon_schedule_task, task_id, request)
    
    return ReconScheduleTaskResponse(
        success=True,
        task_id=task_id,
        status="processing",
        message="侦察调度任务已提交，正在处理中",
    )


@router.get("/recon-schedule/{task_id}", response_model=ReconScheduleResult)
async def get_recon_schedule_result(task_id: str) -> ReconScheduleResult:
    """
    获取侦察调度任务结果
    
    轮询此接口直到status变为completed/failed/awaiting_approval
    """
    # 先查内存缓存
    if task_id in _recon_task_results:
        result = _recon_task_results[task_id]
    else:
        # 查Redis
        result = await _get_recon_result_from_redis(task_id)
        if result:
            _recon_task_results[task_id] = result
    
    if not result:
        raise AITaskNotFoundError(f"任务不存在: {task_id}")
    
    return ReconScheduleResult(**result)


@router.post("/recon-schedule/{task_id}/checkpoint", response_model=ReconCheckpointResponse)
async def save_recon_checkpoint(task_id: str) -> ReconCheckpointResponse:
    """
    保存任务检查点
    
    用于中断后恢复任务
    """
    from .recon_scheduler.checkpoint import save_checkpoint, CheckpointPayload
    
    # 获取当前任务状态
    if task_id not in _recon_task_results:
        result = await _get_recon_result_from_redis(task_id)
        if not result:
            raise AITaskNotFoundError(f"任务不存在: {task_id}")
        _recon_task_results[task_id] = result
    else:
        result = _recon_task_results[task_id]
    
    # 保存检查点
    checkpoint_id = await save_checkpoint(result)
    
    return ReconCheckpointResponse(
        success=True,
        checkpoint_id=checkpoint_id,
        mission_id=task_id,
        progress_percent=result.get("progress_percent", 0),
        timestamp=datetime.now().isoformat(),
    )


@router.post("/recon-schedule/{task_id}/resume")
async def resume_recon_task(
    task_id: str,
    request: ReconResumeRequest,
    background_tasks: BackgroundTasks,
) -> ReconScheduleTaskResponse:
    """
    从检查点恢复任务
    
    恢复后会重新规划剩余部分
    """
    from .recon_scheduler.checkpoint import resume_mission, MissionLockedError
    
    try:
        # 恢复任务
        resumed_state = await resume_mission(task_id)
        
        # 更新任务状态
        _recon_task_results[task_id] = {
            **resumed_state,
            "task_id": task_id,
            "status": "processing",
            "resumed_at": datetime.now().isoformat(),
        }
        
        # TODO: 重新启动后台任务
        
        return ReconScheduleTaskResponse(
            success=True,
            task_id=task_id,
            status="processing",
            message=f"任务已从检查点恢复，进度={resumed_state.get('progress_percent', 0):.1f}%",
        )
        
    except MissionLockedError as e:
        return ReconScheduleTaskResponse(
            success=False,
            task_id=task_id,
            status="locked",
            message=f"任务被锁定: {e}",
        )
    except Exception as e:
        return ReconScheduleTaskResponse(
            success=False,
            task_id=task_id,
            status="failed",
            message=f"恢复失败: {e}",
        )


@router.post("/recon-schedule/{task_id}/approve")
async def approve_recon_degradation(
    task_id: str,
    request: ReconApproveRequest,
    background_tasks: BackgroundTasks,
) -> ReconScheduleTaskResponse:
    """
    人工审批降级方案
    
    当任务进入awaiting_approval状态时，需要人工选择降级方案
    """
    from .recon_scheduler.nodes.approval_flow import execute_degradation_node
    
    # 获取当前任务状态
    if task_id not in _recon_task_results:
        result = await _get_recon_result_from_redis(task_id)
        if not result:
            raise AITaskNotFoundError(f"任务不存在: {task_id}")
        _recon_task_results[task_id] = result
    else:
        result = _recon_task_results[task_id]
    
    # 检查状态
    if result.get("status") != "awaiting_approval":
        return ReconScheduleTaskResponse(
            success=False,
            task_id=task_id,
            status=result.get("status", "unknown"),
            message=f"任务状态不是awaiting_approval，当前状态: {result.get('status')}",
        )
    
    # 验证降级选项
    valid_options = result.get("degradation_options", [])
    if request.approved_degradation not in valid_options:
        return ReconScheduleTaskResponse(
            success=False,
            task_id=task_id,
            status="awaiting_approval",
            message=f"无效的降级选项: {request.approved_degradation}，可用选项: {valid_options}",
        )
    
    # 执行降级
    result["approved_degradation"] = request.approved_degradation
    result["approval_comment"] = request.comment
    result["approval_status"] = "approved"
    result["status"] = "processing"
    
    # 更新缓存
    _recon_task_results[task_id] = result
    await _save_recon_result_to_redis(task_id, result)
    
    logger.info(f"[ReconScheduler] 审批通过: {task_id}, degradation={request.approved_degradation}")
    
    return ReconScheduleTaskResponse(
        success=True,
        task_id=task_id,
        status="processing",
        message=f"已批准降级方案: {request.approved_degradation}，任务继续执行",
    )
