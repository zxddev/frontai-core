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
from .schemas import (
    EmergencyAnalyzeRequest,
    EmergencyAnalyzeTaskResponse,
    EmergencyAnalyzeResult,
    ConfirmEmergencySchemeRequest,
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
            
    if result:
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
    
    # ========== 3-8. 在事务中执行所有数据库操作 ==========
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
            
            # ========== 5. 创建任务记录 ==========
            new_task_id = uuid_lib.uuid4()
            
            # 获取下一个任务编号
            code_query = text("""
                SELECT COALESCE(MAX(CAST(SUBSTRING(task_code FROM 5) AS INTEGER)), 0) + 1
                FROM operational_v2.tasks_v2
                WHERE scenario_id = :scenario_id
            """)
            code_result = await db.execute(code_query, {"scenario_id": str(scenario_id)})
            next_code = code_result.scalar() or 1
            task_code = f"TSK-{next_code:04d}"
            
            # 任务标题：事件标题 + 救援任务
            task_title = f"{event_title} - 救援任务"
            
            # 任务描述：合并事件描述和AI方案说明
            task_description = f"{event_description}\n\n【AI方案说明】\n{scheme_explanation[:500]}"
            
            insert_task = text("""
                INSERT INTO operational_v2.tasks_v2 (
                    id, scenario_id, event_id, task_code, task_type,
                    title, description, status, priority,
                    target_location, instructions, created_at, updated_at
                ) VALUES (
                    :id, :scenario_id, :event_id, :task_code, 'rescue',
                    :title, :description, 'assigned', :priority,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                    :instructions, now(), now()
                )
            """)
            await db.execute(insert_task, {
                "id": str(new_task_id),
                "scenario_id": str(scenario_id),
                "event_id": str(event_id),
                "task_code": task_code,
                "title": task_title,
                "description": task_description,
                "priority": event_priority,
                "lng": event_lng,
                "lat": event_lat,
                "instructions": scheme_explanation[:1000],
            })
            
            logger.info(f"[EmergencyConfirm] 创建任务 task_id={new_task_id}, task_code={task_code}")
            
            # ========== 6. 创建分配记录 ==========
            for team in available_teams:
                assignment_id = uuid_lib.uuid4()
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
                    "task_id": str(new_task_id),
                    "assignee_id": team["id"],
                    "assignee_name": team["name"],
                    "reason": "AI智能推荐",
                })
            
            logger.info(f"[EmergencyConfirm] 创建分配记录 数量={len(available_teams)}")
            
            # ========== 7. 更新队伍状态 ==========
            team_id_list = [t["id"] for t in available_teams]
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
            update_result = await db.execute(update_teams, {"task_id": str(new_task_id)})
            deployed_rows = update_result.fetchall()
            deployed_info = [{"id": str(r.id), "name": r.name} for r in deployed_rows]
            
            logger.info(f"[EmergencyConfirm] 更新队伍状态 deployed={len(deployed_info)}")
            
            # 刷新事务，确保任务记录对后续外键检查可见
            await db.flush()
            
            # ========== 7.5 为每个队伍生成路径规划 ==========
            logger.info(f"[EmergencyConfirm] 开始路径规划 deployed_info={deployed_info}, event_lng={event_lng}, event_lat={event_lat}")
            route_results: List[Dict[str, Any]] = []
            for team in deployed_info:
                try:
                    route_result = await _generate_team_route(
                        db=db,
                        team_id=UUID(team["id"]),
                        task_id=new_task_id,
                        scenario_id=scenario_id,
                        destination_lng=event_lng,
                        destination_lat=event_lat,
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
                try:
                    # 使用已规划的路径启动移动
                    dispatch_request = TeamDispatchRequest(
                        destination=[event_lng, event_lat],
                        scenario_id=scenario_id,
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
                f"[EmergencyConfirm] 确认成功 task_id={new_task_id}, "
                f"task_code={task_code}, deployed={len(deployed_info)}"
            )
            
            # ========== 9. WebSocket推送 ==========
            try:
                await broadcast_event_update(
                    scenario_id=scenario_id,
                    event_type="rescue_task_created",
                    event_data={
                        "event_id": str(event_id),
                        "task_id": str(new_task_id),
                        "task_code": task_code,
                        "deployed_teams": deployed_info,
                    },
                )
                logger.info("[EmergencyConfirm] WebSocket推送成功")
            except Exception as ws_err:
                logger.warning(f"[EmergencyConfirm] WebSocket推送失败: {ws_err}")
            
            return {
                "success": True,
                "task_id": str(new_task_id),
                "task_code": task_code,
                "deployed_teams": deployed_info,
                "route_results": route_results,
                "message": f"成功创建任务 {task_code}，部署 {len(deployed_info)} 支队伍，生成 {len(route_results)} 条路径",
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
