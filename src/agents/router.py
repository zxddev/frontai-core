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
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
import redis.asyncio as aioredis

from src.core.database import AsyncSessionLocal
from src.core.websocket import broadcast_event_update
from src.domains.ai_decisions import AIDecisionLogRepository, CreateAIDecisionLogRequest
from .exceptions import AITaskNotFoundError, AISchemeNotFoundError
from .schemas import (
    AnalyzeEventRequest,
    AnalyzeEventTaskResponse,
    AnalyzeEventResult,
    GenerateSchemeRequest,
    GenerateSchemeTaskResponse,
    BatchGenerateSchemeRequest,
    BatchGenerateSchemeResponse,
    EmergencyAnalyzeRequest,
    EmergencyAnalyzeTaskResponse,
    EmergencyAnalyzeResult,
    DispatchTasksRequest,
    DispatchTasksTaskResponse,
    DispatchTasksResult,
)
from .event_analysis import EventAnalysisAgent
from .scheme_generation import SchemeGenerationAgent
from .emergency_ai import EmergencyAIAgent, get_emergency_ai_agent
from .task_dispatch import TaskDispatchAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# 任务结果缓存（内存备份）
_task_results: Dict[str, Dict[str, Any]] = {}

# Redis配置
REDIS_URL = "redis://192.168.31.50:6379/0"
EMERGENCY_RESULT_PREFIX = "emergency_ai_result:"
EMERGENCY_RESULT_TTL = 3600  # 结果保存1小时

# Agent实例（延迟初始化）
_event_analysis_agent: EventAnalysisAgent | None = None
_scheme_generation_agent: SchemeGenerationAgent | None = None
_task_dispatch_agent: TaskDispatchAgent | None = None


async def _save_result_to_redis(task_id: str, result: Dict[str, Any]) -> bool:
    """保存结果到Redis"""
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        key = f"{EMERGENCY_RESULT_PREFIX}{task_id}"
        await redis_client.setex(key, EMERGENCY_RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
        await redis_client.close()
        logger.info(f"[EmergencyAI] 结果已保存到Redis: {key}")
        return True
    except Exception as e:
        logger.warning(f"[EmergencyAI] Redis保存失败: {e}")
        return False


async def _get_result_from_redis(task_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取结果"""
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        key = f"{EMERGENCY_RESULT_PREFIX}{task_id}"
        data = await redis_client.get(key)
        await redis_client.close()
        if data:
            logger.info(f"[EmergencyAI] 从Redis获取结果: {key}")
            return json.loads(data)
        return None
    except Exception as e:
        logger.warning(f"[EmergencyAI] Redis读取失败: {e}")
        return None


def get_event_analysis_agent() -> EventAnalysisAgent:
    """获取EventAnalysisAgent单例"""
    global _event_analysis_agent
    if _event_analysis_agent is None:
        _event_analysis_agent = EventAnalysisAgent()
    return _event_analysis_agent


def get_scheme_generation_agent() -> SchemeGenerationAgent:
    """获取SchemeGenerationAgent单例"""
    global _scheme_generation_agent
    if _scheme_generation_agent is None:
        _scheme_generation_agent = SchemeGenerationAgent()
    return _scheme_generation_agent


def get_task_dispatch_agent() -> TaskDispatchAgent:
    """获取TaskDispatchAgent单例"""
    global _task_dispatch_agent
    if _task_dispatch_agent is None:
        _task_dispatch_agent = TaskDispatchAgent()
    return _task_dispatch_agent


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


async def _save_decision_log(
    request: AnalyzeEventRequest,
    result: Dict[str, Any],
) -> Optional[UUID]:
    """
    保存AI决策日志到数据库
    
    Args:
        request: 原始分析请求
        result: 分析结果
        
    Returns:
        日志ID或None（保存失败时）
    """
    logger.info(
        "开始保存AI决策日志",
        extra={"event_id": str(request.event_id), "scenario_id": str(request.scenario_id) if request.scenario_id else None}
    )
    
    if not request.scenario_id:
        logger.warning("scenario_id为空，跳过决策日志保存")
        return None
    
    try:
        async with AsyncSessionLocal() as db:
            repo = AIDecisionLogRepository(db)
            
            trace = result.get("trace", {})
            algorithms = trace.get("algorithms_used", [])
            confirmation = result.get("confirmation_decision", {})
            
            # 将结果转换为可序列化格式
            analysis_result = _to_serializable(result.get("analysis_result"))
            confirmation_serializable = _to_serializable(confirmation)
            event_status = _to_serializable(result.get("event_status_update"))
            
            log_data = CreateAIDecisionLogRequest(
                scenario_id=request.scenario_id,
                event_id=request.event_id,
                scheme_id=None,
                decision_type="event_analysis",
                algorithm_used=",".join(algorithms) if algorithms else None,
                input_snapshot={
                    "event_id": str(request.event_id),
                    "disaster_type": request.disaster_type,
                    "location": {
                        "longitude": request.location.longitude,
                        "latitude": request.location.latitude,
                    },
                    "initial_data": request.initial_data,
                    "source_system": request.source_system,
                    "source_type": request.source_type,
                    "source_trust_level": request.source_trust_level,
                    "is_urgent": request.is_urgent,
                    "estimated_victims": request.estimated_victims,
                    "priority": request.priority,
                },
                output_result={
                    "analysis_result": analysis_result,
                    "confirmation_decision": confirmation_serializable,
                    "event_status_update": event_status,
                },
                confidence_score=Decimal(str(confirmation.get("confirmation_score", 0))) if confirmation.get("confirmation_score") is not None else None,
                reasoning_chain={
                    "nodes_executed": trace.get("nodes_executed", []),
                    "algorithms_used": algorithms,
                    "rationale": confirmation.get("rationale", ""),
                    "matched_rules": confirmation.get("matched_auto_confirm_rules", []),
                },
                processing_time_ms=int(result.get("execution_time_ms", 0)) if result.get("execution_time_ms") else None,
            )
            
            log_entry = await repo.create(log_data)
            await db.commit()
            
            logger.info(
                "AI决策日志保存成功",
                extra={
                    "log_id": str(log_entry.id),
                    "event_id": str(request.event_id),
                    "decision_type": "event_analysis",
                }
            )
            
            return log_entry.id
            
    except Exception as e:
        logger.exception(
            "AI决策日志保存失败",
            extra={"event_id": str(request.event_id), "error": str(e)}
        )
        return None


async def _broadcast_analysis_result(
    request: AnalyzeEventRequest,
    result: Dict[str, Any],
) -> None:
    """
    通过WebSocket广播分析结果
    
    Args:
        request: 原始分析请求
        result: 分析结果
    """
    if not request.scenario_id:
        logger.debug("scenario_id为空，跳过WebSocket推送")
        return
    
    try:
        confirmation = result.get("confirmation_decision", {})
        event_status = result.get("event_status_update", {})
        
        await broadcast_event_update(
            scenario_id=request.scenario_id,
            event_type="event_analyzed",
            event_data={
                "event_id": str(request.event_id),
                "task_id": result.get("task_id"),
                "status": event_status.get("new_status", "pending"),
                "auto_confirmed": confirmation.get("auto_confirmed", False),
                "confirmation_score": confirmation.get("confirmation_score"),
                "matched_rules": confirmation.get("matched_auto_confirm_rules", []),
                "analysis_result": result.get("analysis_result"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )
        
        logger.info(
            "WebSocket分析结果推送成功",
            extra={
                "event_id": str(request.event_id),
                "scenario_id": str(request.scenario_id),
                "new_status": event_status.get("new_status"),
            }
        )
        
    except Exception as e:
        logger.exception(
            "WebSocket推送失败",
            extra={"event_id": str(request.event_id), "error": str(e)}
        )


async def _run_event_analysis(task_id: str, request: AnalyzeEventRequest) -> None:
    """
    后台执行事件分析
    
    执行流程:
    1. 调用EventAnalysisAgent执行分析
    2. 保存AI决策日志到ai_decision_logs_v2表
    3. 通过WebSocket推送分析结果
    
    Args:
        task_id: 任务ID
        request: 分析请求
    """
    logger.info(
        "开始后台事件分析任务",
        extra={"task_id": task_id, "event_id": str(request.event_id)},
    )
    
    try:
        agent = get_event_analysis_agent()
        
        result = await agent.arun(
            task_id=task_id,
            event_id=request.event_id,
            scenario_id=request.scenario_id,
            disaster_type=request.disaster_type,
            location={
                "longitude": request.location.longitude,
                "latitude": request.location.latitude,
            },
            initial_data=request.initial_data,
            source_system=request.source_system,
            source_type=request.source_type,
            source_trust_level=request.source_trust_level,
            is_urgent=request.is_urgent,
            estimated_victims=request.estimated_victims,
            priority=request.priority,
            context=request.context,
            nearby_events=request.nearby_events,
        )
        
        _task_results[task_id] = result
        
        logger.info(
            "事件分析任务完成",
            extra={
                "task_id": task_id,
                "status": result.get("status"),
                "auto_confirmed": result.get("confirmation_decision", {}).get("auto_confirmed"),
            },
        )
        
        await _save_decision_log(request, result)
        
        await _broadcast_analysis_result(request, result)
        
    except Exception as e:
        logger.exception(
            "事件分析任务失败",
            extra={"task_id": task_id, "error": str(e)},
        )
        
        _task_results[task_id] = {
            "success": False,
            "task_id": task_id,
            "event_id": str(request.event_id),
            "status": "failed",
            "errors": [str(e)],
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }


@router.post("/analyze-event", response_model=AnalyzeEventTaskResponse, status_code=202)
async def analyze_event(
    request: AnalyzeEventRequest,
    background_tasks: BackgroundTasks,
) -> AnalyzeEventTaskResponse:
    """
    提交事件分析任务
    
    异步执行事件分析，立即返回task_id。
    分析完成后通过WebSocket推送结果，也可通过GET接口查询。
    
    分析内容:
    1. 灾情评估 - 评估灾情等级、影响范围、预估伤亡
    2. 次生灾害预测 - 预测火灾、滑坡等次生灾害风险
    3. 损失估算 - 估算经济损失和基础设施损毁
    4. 确认评分 - 计算确认评分，决定事件状态流转(confirmed/pre_confirmed/pending)
    """
    task_id = f"task-{request.event_id}"
    
    logger.info(
        "收到事件分析请求",
        extra={
            "task_id": task_id,
            "event_id": str(request.event_id),
            "disaster_type": request.disaster_type,
            "source_system": request.source_system,
        },
    )
    
    # 检查是否已有相同任务在执行
    if task_id in _task_results:
        existing = _task_results[task_id]
        if existing.get("status") == "processing":
            return AnalyzeEventTaskResponse(
                success=True,
                task_id=task_id,
                event_id=str(request.event_id),
                status="processing",
                message="分析任务正在执行中",
                created_at=datetime.utcnow(),
            )
    
    # 初始化任务状态
    _task_results[task_id] = {
        "success": True,
        "task_id": task_id,
        "event_id": str(request.event_id),
        "status": "processing",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # 添加后台任务
    background_tasks.add_task(_run_event_analysis, task_id, request)
    
    return AnalyzeEventTaskResponse(
        success=True,
        task_id=task_id,
        event_id=str(request.event_id),
        status="processing",
        message="分析任务已提交，预计完成时间2-5秒",
        created_at=datetime.utcnow(),
    )


@router.get("/analyze-event/{task_id}")
async def get_analysis_result(task_id: str) -> Dict[str, Any]:
    """
    查询事件分析任务结果
    
    Args:
        task_id: 任务ID (格式: task-{event_id})
        
    Returns:
        分析结果或任务状态
    """
    logger.info("查询分析任务结果", extra={"task_id": task_id})
    
    if task_id not in _task_results:
        raise AITaskNotFoundError(task_id)
    
    result = _task_results[task_id]
    return result


async def _run_scheme_generation(task_id: str, request: GenerateSchemeRequest) -> None:
    """
    后台执行方案生成
    
    使用数据库集成：
    1. 从数据库查询可用队伍
    2. 执行方案生成
    3. 保存方案到数据库
    
    Args:
        task_id: 任务ID
        request: 生成请求
    """
    logger.info(
        "开始后台方案生成任务",
        extra={"task_id": task_id, "event_id": str(request.event_id)},
    )
    
    try:
        agent = get_scheme_generation_agent()
        
        # 使用数据库集成运行
        async with AsyncSessionLocal() as db:
            result = await agent.run_with_db(
                db=db,
                event_id=str(request.event_id),
                scenario_id=str(request.scenario_id) if request.scenario_id else "",
                event_analysis=request.event_analysis,
                constraints=request.constraints or {},
                optimization_weights=request.optimization_weights or {},
                options=request.options or {},
                save_to_db=True,
            )
        
        # 缓存结果
        _task_results[task_id] = result
        
        db_persist = result.get("db_persist", {})
        logger.info(
            "方案生成任务完成",
            extra={
                "task_id": task_id,
                "scheme_count": result.get("scheme_count", 0),
                "db_saved": db_persist.get("success", False),
                "db_scheme_id": db_persist.get("scheme_id"),
            },
        )
        
    except Exception as e:
        logger.exception(
            "方案生成任务失败",
            extra={"task_id": task_id, "error": str(e)},
        )
        
        _task_results[task_id] = {
            "success": False,
            "task_id": task_id,
            "event_id": str(request.event_id),
            "status": "failed",
            "errors": [str(e)],
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }


@router.post("/generate-scheme", response_model=GenerateSchemeTaskResponse, status_code=202)
async def generate_scheme(
    request: GenerateSchemeRequest,
    background_tasks: BackgroundTasks,
) -> GenerateSchemeTaskResponse:
    """
    提交方案生成任务
    
    基于事件分析结果，生成救援方案。包含：
    1. 规则触发 - 根据灾情匹配TRR规则
    2. 能力提取 - 提取所需救援能力
    3. 资源匹配 - 匹配可用救援力量
    4. 多目标优化 - NSGA-II生成Pareto最优解
    5. 硬规则过滤 - 过滤不可行方案
    6. TOPSIS评分 - 综合评分排序
    """
    task_id = f"scheme-{request.event_id}"
    
    logger.info(
        "收到方案生成请求",
        extra={
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scenario_id": str(request.scenario_id) if request.scenario_id else None,
        },
    )
    
    # 检查是否已有相同任务在执行
    if task_id in _task_results:
        existing = _task_results[task_id]
        if existing.get("status") == "processing":
            return GenerateSchemeTaskResponse(
                success=True,
                task_id=task_id,
                event_id=str(request.event_id),
                status="processing",
                message="方案生成任务正在执行中",
                created_at=datetime.utcnow(),
            )
    
    # 初始化任务状态
    _task_results[task_id] = {
        "success": True,
        "task_id": task_id,
        "event_id": str(request.event_id),
        "status": "processing",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # 添加后台任务
    background_tasks.add_task(_run_scheme_generation, task_id, request)
    
    return GenerateSchemeTaskResponse(
        success=True,
        task_id=task_id,
        event_id=str(request.event_id),
        status="processing",
        message="方案生成任务已提交，预计完成时间3-10秒",
        created_at=datetime.utcnow(),
    )


@router.get("/generate-scheme/{task_id}")
async def get_scheme_result(task_id: str) -> Dict[str, Any]:
    """
    查询方案生成任务结果
    
    Args:
        task_id: 任务ID (格式: scheme-{event_id})
        
    Returns:
        生成结果或任务状态
    """
    logger.info("查询方案生成结果", extra={"task_id": task_id})
    
    if task_id not in _task_results:
        raise AISchemeNotFoundError(task_id)
    
    return _task_results[task_id]


@router.post("/generate-schemes/batch", response_model=BatchGenerateSchemeResponse)
async def generate_schemes_batch(
    request: BatchGenerateSchemeRequest,
) -> BatchGenerateSchemeResponse:
    """
    批量生成方案
    
    同时为多个事件生成方案，支持并行/串行执行。
    最多支持10个事件同时处理。
    
    Args:
        request: 批量请求，包含多个GenerateSchemeRequest
        
    Returns:
        批量结果，包含每个请求的执行结果
    """
    import asyncio
    import time
    
    start_time = time.time()
    
    logger.info(
        "收到批量方案生成请求",
        extra={
            "total_requests": len(request.requests),
            "parallel": request.parallel,
        },
    )
    
    agent = get_scheme_generation_agent()
    results: list[Dict[str, Any]] = []
    
    async def run_single(req: GenerateSchemeRequest) -> Dict[str, Any]:
        """执行单个方案生成"""
        try:
            async with AsyncSessionLocal() as db:
                result = await agent.run_with_db(
                    db=db,
                    event_id=str(req.event_id),
                    scenario_id=str(req.scenario_id) if req.scenario_id else "",
                    event_analysis=req.event_analysis,
                    constraints=req.constraints or {},
                    optimization_weights=req.optimization_weights or {},
                    options=req.options or {},
                    save_to_db=True,
                )
            return {
                "event_id": str(req.event_id),
                "success": result.get("success", False),
                "scheme_count": result.get("scheme_count", 0),
                "execution_time_ms": result.get("execution_time_ms"),
                "errors": result.get("errors", []),
            }
        except Exception as e:
            logger.error(f"批量生成失败: event_id={req.event_id}, error={e}")
            return {
                "event_id": str(req.event_id),
                "success": False,
                "scheme_count": 0,
                "errors": [str(e)],
            }
    
    if request.parallel:
        # 并行执行
        tasks = [run_single(req) for req in request.requests]
        results = await asyncio.gather(*tasks)
    else:
        # 串行执行
        for req in request.requests:
            result = await run_single(req)
            results.append(result)
    
    # 统计结果
    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded
    total_time_ms = (time.time() - start_time) * 1000
    
    logger.info(
        "批量方案生成完成",
        extra={
            "total": len(results),
            "succeeded": succeeded,
            "failed": failed,
            "execution_time_ms": total_time_ms,
        },
    )
    
    return BatchGenerateSchemeResponse(
        success=failed == 0,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
        execution_time_ms=round(total_time_ms, 2),
    )


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
        
        result = await agent.analyze(
            event_id=str(request.event_id),
            scenario_id=str(request.scenario_id),
            disaster_description=request.disaster_description,
            structured_input=request.structured_input,
            constraints=request.constraints,
            optimization_weights=request.optimization_weights,
        )
        
        logger.info(f"[EmergencyAI] 分析完成，保存结果 task_id={task_id}")
        
        # 保存到内存和Redis
        _task_results[task_id] = result
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
            scenario_id=str(request.scenario_id),
            event_type="emergency_ai_analysis_completed",
            data={
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
    
    logger.info(
        "收到应急AI分析请求",
        extra={
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scenario_id": str(request.scenario_id),
        },
    )
    
    # 提交后台任务
    background_tasks.add_task(_run_emergency_analysis, task_id, request)
    
    return EmergencyAnalyzeTaskResponse(
        success=True,
        task_id=task_id,
        event_id=str(request.event_id),
        status="processing",
        message="应急AI分析任务已提交，预计完成时间5-15秒",
        created_at=datetime.utcnow(),
    )


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
        matching=result.get("matching"),
        optimization=result.get("optimization"),
        recommended_scheme=result.get("recommended_scheme"),
        scheme_explanation=result.get("scheme_explanation"),
        trace=result.get("trace"),
        errors=result.get("errors", []),
        execution_time_ms=result.get("execution_time_ms"),
    )


# ============================================================================
# 任务调度接口
# ============================================================================

async def _run_task_dispatch(
    task_id: str,
    request: DispatchTasksRequest,
) -> None:
    """
    后台执行任务调度
    
    Args:
        task_id: 任务ID
        request: 调度请求
    """
    import traceback
    
    logger.info(
        f"[TaskDispatch] 开始执行任务调度 task_id={task_id} scheme_id={request.scheme_id}"
    )
    
    try:
        agent = get_task_dispatch_agent()
        
        # 构建调度配置
        dispatch_config = {}
        if request.dispatch_config:
            dispatch_config = request.dispatch_config.model_dump()
        
        result = agent.run(
            event_id=str(request.event_id),
            scenario_id=str(request.scenario_id),
            scheme_id=str(request.scheme_id),
            scheme_data=request.scheme_data,
            dispatch_config=dispatch_config,
        )
        
        # 保存结果
        _task_results[task_id] = result
        await _save_result_to_redis(task_id, result)
        
        logger.info(
            f"[TaskDispatch] 任务调度完成 task_id={task_id} "
            f"success={result.get('success')} "
            f"order_count={result.get('summary', {}).get('order_count', 0)}"
        )
        
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(
            f"[TaskDispatch] 任务调度失败 task_id={task_id} error={str(e)}\n{error_detail}"
        )
        
        error_result = {
            "success": False,
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scenario_id": str(request.scenario_id),
            "scheme_id": str(request.scheme_id),
            "status": "failed",
            "errors": [str(e)],
            "completed_at": datetime.utcnow().isoformat() + "Z",
        }
        _task_results[task_id] = error_result
        await _save_result_to_redis(task_id, error_result)


@router.post("/dispatch-tasks", response_model=DispatchTasksTaskResponse, status_code=202)
async def dispatch_tasks(
    request: DispatchTasksRequest,
    background_tasks: BackgroundTasks,
) -> DispatchTasksTaskResponse:
    """
    提交任务调度请求
    
    基于方案生成结果，执行任务调度：
    - 方案拆解为具体任务
    - 任务依赖排序和时间调度
    - 多车辆路径规划
    - 执行者分配
    - 生成调度单
    
    Args:
        request: 调度请求
        
    Returns:
        任务提交响应，包含task_id用于查询结果
    """
    task_id = f"dispatch-{request.scheme_id}"
    
    logger.info(
        "收到任务调度请求",
        extra={
            "task_id": task_id,
            "event_id": str(request.event_id),
            "scheme_id": str(request.scheme_id),
        },
    )
    
    # 检查是否已有相同任务在执行
    if task_id in _task_results:
        existing = _task_results[task_id]
        if existing.get("status") == "processing":
            return DispatchTasksTaskResponse(
                success=True,
                task_id=task_id,
                event_id=str(request.event_id),
                scheme_id=str(request.scheme_id),
                status="processing",
                message="任务调度正在执行中",
                created_at=datetime.utcnow(),
            )
    
    # 初始化任务状态
    _task_results[task_id] = {
        "success": True,
        "task_id": task_id,
        "event_id": str(request.event_id),
        "scheme_id": str(request.scheme_id),
        "status": "processing",
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    
    # 提交后台任务
    background_tasks.add_task(_run_task_dispatch, task_id, request)
    
    return DispatchTasksTaskResponse(
        success=True,
        task_id=task_id,
        event_id=str(request.event_id),
        scheme_id=str(request.scheme_id),
        status="processing",
        message="任务调度已提交，预计完成时间5-15秒",
        created_at=datetime.utcnow(),
    )


@router.get("/dispatch-tasks/{task_id}")
async def get_dispatch_tasks_result(task_id: str) -> DispatchTasksResult:
    """
    查询任务调度结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        调度结果
        
    Raises:
        AITaskNotFoundError: 任务不存在
    """
    # 优先从内存获取
    result = _task_results.get(task_id)
    
    # 内存没有则从Redis获取
    if result is None:
        result = await _get_result_from_redis(task_id)
        if result:
            _task_results[task_id] = result
    
    if result is None:
        raise AITaskNotFoundError(task_id)
    
    # 构建摘要
    summary = result.get("summary", {})
    if not summary:
        summary = {
            "task_count": 0,
            "scheduled_count": 0,
            "order_count": len(result.get("dispatch_orders", [])),
            "route_count": len(result.get("planned_routes", [])),
            "makespan_min": result.get("makespan_min", 0),
            "total_distance_km": result.get("total_travel_distance_km", 0),
            "total_travel_time_min": result.get("total_travel_time_min", 0),
            "critical_path_tasks": result.get("critical_path_tasks", []),
        }
    
    return DispatchTasksResult(
        success=result.get("success", False),
        event_id=result.get("event_id", ""),
        scenario_id=result.get("scenario_id", ""),
        scheme_id=result.get("scheme_id", ""),
        summary=summary,
        dispatch_orders=result.get("dispatch_orders", []),
        scheduled_tasks=result.get("scheduled_tasks", []),
        planned_routes=result.get("planned_routes", []),
        executor_assignments=result.get("executor_assignments", []),
        gantt_data=result.get("gantt_data", []),
        trace=result.get("trace"),
        errors=result.get("errors", []),
        execution_time_ms=result.get("execution_time_ms"),
        started_at=result.get("started_at"),
        completed_at=result.get("completed_at"),
    )
