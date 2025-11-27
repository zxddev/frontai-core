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
    EmergencyAnalyzeRequest,
    EmergencyAnalyzeTaskResponse,
    EmergencyAnalyzeResult,
    RoutePlanningRequest,
    RoutePlanningTaskResponse,
    RoutePlanningResult,
)
from .emergency_ai import EmergencyAIAgent, get_emergency_ai_agent
from .route_planning import invoke as route_planning_invoke

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# 任务结果缓存（内存备份）
_task_results: Dict[str, Dict[str, Any]] = {}

# Redis配置
REDIS_URL = "redis://192.168.31.50:6379/0"
EMERGENCY_RESULT_PREFIX = "emergency_ai_result:"
EMERGENCY_RESULT_TTL = 3600  # 结果保存1小时




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
# 路径规划智能体接口
# ============================================================================

# 路径规划结果缓存
_route_planning_results: Dict[str, Dict[str, Any]] = {}
ROUTE_PLANNING_PREFIX = "route_planning_result:"


async def _save_route_result_to_redis(task_id: str, result: Dict[str, Any]) -> bool:
    """保存路径规划结果到Redis"""
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        key = f"{ROUTE_PLANNING_PREFIX}{task_id}"
        await redis_client.setex(key, EMERGENCY_RESULT_TTL, json.dumps(result, ensure_ascii=False, default=str))
        await redis_client.close()
        logger.info(f"[RoutePlanning] 结果已保存到Redis: {key}")
        return True
    except Exception as e:
        logger.warning(f"[RoutePlanning] Redis保存失败: {e}")
        return False


async def _get_route_result_from_redis(task_id: str) -> Optional[Dict[str, Any]]:
    """从Redis获取路径规划结果"""
    try:
        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        key = f"{ROUTE_PLANNING_PREFIX}{task_id}"
        data = await redis_client.get(key)
        await redis_client.close()
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
