"""
任务分发API路由

提供任务卡生成、确认、下发等接口。
"""
from __future__ import annotations

import hashlib
import logging
import uuid as uuid_lib
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.core.websocket import broadcast_event_update
from .agent import get_task_dispatch_agent
from src.agents.scheme_parsing import SchemeParsingAgent, ParsedScheme

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/task-dispatch", tags=["task-dispatch"])


# ============================================================================
# Request/Response Models
# ============================================================================

class GeoLocation(BaseModel):
    """地理位置"""
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class TaskDispatchGenerateRequest(BaseModel):
    """生成任务卡请求"""
    event_id: str = Field(..., description="应急事件ID")
    scheme_id: str = Field(..., description="方案ID")
    scheme_text: str = Field(..., description="当前方案文本（可能被用户编辑）", min_length=10)
    scheme_text_hash: str = Field(..., description="原始方案文本的MD5哈希")
    original_structured_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="原始结构化数据（未修改时直接使用）"
    )
    event_location: GeoLocation = Field(..., description="事发地点坐标")
    available_teams: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="可用救援队伍列表"
    )


class TaskCard(BaseModel):
    """任务卡"""
    card_id: str = Field(..., description="任务卡ID")
    task_id: str = Field(..., description="任务类型ID")
    task_name: str = Field(..., description="任务名称")
    priority: str = Field(..., description="优先级")
    executor_id: str = Field(..., description="执行单位ID")
    executor_name: str = Field(..., description="执行单位名称")
    target_location: Optional[GeoLocation] = Field(None, description="目标位置")
    rally_point: Optional[GeoLocation] = Field(None, description="集结点")
    route_suggestion: Optional[str] = Field(None, description="路线建议")
    scheduled_start: Optional[str] = Field(None, description="计划开始时间")
    scheduled_end: Optional[str] = Field(None, description="计划结束时间")
    instructions: str = Field("", description="执行指令")
    status: str = Field("draft", description="状态：draft/pending/dispatched/...")


class TaskDispatchGenerateResponse(BaseModel):
    """生成任务卡响应"""
    success: bool
    dispatch_id: str = Field(..., description="分发批次ID")
    is_text_modified: bool = Field(..., description="方案文本是否被修改")
    parsing_confidence: Optional[float] = Field(None, description="解析置信度（仅当文本被修改时）")
    task_cards: List[TaskCard]
    gantt_data: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    execution_time_ms: int


class TaskDispatchRequest(BaseModel):
    """下发任务请求"""
    task_card_ids: List[str] = Field(
        default_factory=list, 
        description="要下发的任务卡ID列表，空=全部"
    )


class TaskDispatchResponse(BaseModel):
    """下发任务响应"""
    success: bool
    dispatched_count: int
    notifications_sent: List[Dict[str, Any]]
    errors: List[str] = Field(default_factory=list)


# ============================================================================
# In-Memory Storage (生产环境应使用数据库)
# ============================================================================

_dispatch_store: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/generate", response_model=TaskDispatchGenerateResponse)
async def generate_task_cards(request: TaskDispatchGenerateRequest) -> TaskDispatchGenerateResponse:
    """
    生成任务卡
    
    根据方案文本生成可执行的任务卡。
    
    流程：
    1. 比较当前文本哈希与原始哈希
    2. 如果未修改，直接使用original_structured_data
    3. 如果已修改，调用SchemeParsingAgent解析
    4. 调用TaskDispatchAgent生成任务卡
    5. 添加地理要素和路线建议
    """
    import time
    start_time = time.time()
    
    logger.info(
        f"[TaskDispatch] 开始生成任务卡: event_id={request.event_id}, "
        f"scheme_id={request.scheme_id}"
    )
    
    warnings: List[str] = []
    parsing_confidence: Optional[float] = None
    
    # 步骤1: 检测方案文本是否被修改
    current_hash = hashlib.md5(request.scheme_text.encode("utf-8")).hexdigest()
    is_modified = current_hash != request.scheme_text_hash
    
    logger.info(f"[TaskDispatch] 方案文本修改检测: modified={is_modified}")
    
    # 步骤2: 获取结构化数据
    if is_modified:
        # 调用SchemeParsingAgent解析修改后的文本
        logger.info("[TaskDispatch] 文本已修改，调用LLM解析")
        
        parsing_agent = SchemeParsingAgent()
        parsed: ParsedScheme = await parsing_agent.parse(
            scheme_text=request.scheme_text,
            available_teams=request.available_teams,
        )
        
        parsing_confidence = parsed.parsing_confidence
        warnings.extend(parsed.warnings)
        
        # 转换为TaskDispatchAgent需要的格式
        scheme_tasks = [
            {
                "task_id": task.task_type,
                "task_name": task.task_name,
                "priority": task.priority,
                "sequence": i + 1,
                "depends_on": task.depends_on,
                "required_capabilities": [],
                "duration_min": task.duration_min,
            }
            for i, task in enumerate(parsed.tasks)
        ]
        
        allocated_teams = [
            {
                "resource_id": f"team-{uuid_lib.uuid4().hex[:8]}",
                "resource_name": assignment.team_name,
                "capabilities": assignment.capabilities,
                "eta_minutes": assignment.estimated_eta_min or 30,
                "distance_km": assignment.distance_km or 10,
            }
            for assignment in parsed.team_assignments
        ]
        
        logger.info(
            f"[TaskDispatch] LLM解析完成: {len(scheme_tasks)}个任务, "
            f"{len(allocated_teams)}个队伍, confidence={parsing_confidence:.2f}"
        )
        
    else:
        # 直接使用原始结构化数据
        logger.info("[TaskDispatch] 文本未修改，使用原始结构化数据")
        
        if not request.original_structured_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文本未修改但未提供original_structured_data",
            )
        
        # 从EmergencyAI输出格式提取
        htn_data = request.original_structured_data.get("htn_decomposition", {})
        scheme_tasks = htn_data.get("task_sequence", [])
        
        recommended = request.original_structured_data.get("recommended_scheme", {})
        allocated_teams = recommended.get("allocations", [])
    
    # 步骤3: 调用TaskDispatchAgent生成任务分配
    dispatch_agent = get_task_dispatch_agent(use_checkpointer=False)
    
    dispatch_result = await dispatch_agent.initial_dispatch(
        event_id=request.event_id,
        scheme_id=request.scheme_id,
        scheme_tasks=scheme_tasks,
        allocated_teams=allocated_teams,
    )
    
    if not dispatch_result.get("success"):
        errors = dispatch_result.get("errors", ["未知错误"])
        logger.error(f"[TaskDispatch] 任务分配失败: {errors}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"任务分配失败: {', '.join(errors)}",
        )
    
    # 步骤4: 转换为TaskCard格式，添加地理要素
    dispatch_id = f"dispatch-{uuid_lib.uuid4().hex[:12]}"
    task_cards: List[TaskCard] = []
    
    for order in dispatch_result.get("dispatch_orders", []):
        card = TaskCard(
            card_id=order.get("order_id", str(uuid_lib.uuid4())),
            task_id=order.get("task_id", ""),
            task_name=order.get("task_name", ""),
            priority=order.get("priority", "medium"),
            executor_id=order.get("executor_id", ""),
            executor_name=order.get("executor_name", ""),
            target_location=GeoLocation(
                lat=request.event_location.lat,
                lng=request.event_location.lng,
            ),
            rally_point=None,  # TODO: 集成集结点选择算法
            route_suggestion=None,  # TODO: 集成路径规划
            scheduled_start=order.get("scheduled_start"),
            scheduled_end=order.get("scheduled_end"),
            instructions=order.get("instructions", ""),
            status="draft",
        )
        task_cards.append(card)
    
    # 存储分发批次
    _dispatch_store[dispatch_id] = {
        "dispatch_id": dispatch_id,
        "event_id": request.event_id,
        "scheme_id": request.scheme_id,
        "task_cards": [c.model_dump() for c in task_cards],
        "gantt_data": dispatch_result.get("gantt_data", []),
        "status": "draft",
        "created_at": datetime.utcnow().isoformat(),
    }
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        f"[TaskDispatch] 任务卡生成完成: dispatch_id={dispatch_id}, "
        f"cards={len(task_cards)}, elapsed={elapsed_ms}ms"
    )
    
    return TaskDispatchGenerateResponse(
        success=True,
        dispatch_id=dispatch_id,
        is_text_modified=is_modified,
        parsing_confidence=parsing_confidence,
        task_cards=task_cards,
        gantt_data=dispatch_result.get("gantt_data", []),
        warnings=warnings,
        execution_time_ms=elapsed_ms,
    )


@router.get("/{dispatch_id}")
async def get_dispatch_status(dispatch_id: str) -> Dict[str, Any]:
    """
    查询分发批次状态
    
    Args:
        dispatch_id: 分发批次ID
        
    Returns:
        分发批次详情
    """
    if dispatch_id not in _dispatch_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分发批次 {dispatch_id} 不存在",
        )
    
    return _dispatch_store[dispatch_id]


@router.post("/{dispatch_id}/dispatch", response_model=TaskDispatchResponse)
async def dispatch_tasks(
    dispatch_id: str,
    request: TaskDispatchRequest,
) -> TaskDispatchResponse:
    """
    下发任务
    
    将任务卡下发给执行单位，通过WebSocket推送通知。
    
    Args:
        dispatch_id: 分发批次ID
        request: 下发请求（可指定部分任务卡）
    """
    if dispatch_id not in _dispatch_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分发批次 {dispatch_id} 不存在",
        )
    
    dispatch_data = _dispatch_store[dispatch_id]
    task_cards = dispatch_data.get("task_cards", [])
    
    # 筛选要下发的任务卡
    cards_to_dispatch = []
    if request.task_card_ids:
        cards_to_dispatch = [
            c for c in task_cards 
            if c.get("card_id") in request.task_card_ids
        ]
    else:
        cards_to_dispatch = task_cards
    
    if not cards_to_dispatch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可下发的任务卡",
        )
    
    # 更新状态
    notifications = []
    errors = []
    
    for card in cards_to_dispatch:
        card["status"] = "dispatched"
        card["dispatched_at"] = datetime.utcnow().isoformat()
        
        # 构建通知
        notification = {
            "type": "task_dispatch",
            "card_id": card.get("card_id"),
            "task_name": card.get("task_name"),
            "executor_id": card.get("executor_id"),
            "executor_name": card.get("executor_name"),
            "priority": card.get("priority"),
            "instructions": card.get("instructions"),
            "dispatched_at": card.get("dispatched_at"),
        }
        notifications.append(notification)
        
        # WebSocket推送
        try:
            event_id = dispatch_data.get("event_id", "")
            # 尝试转换为UUID，如果失败则跳过推送
            try:
                scenario_uuid = UUID(event_id) if event_id else None
            except (ValueError, TypeError):
                scenario_uuid = None
            
            if scenario_uuid:
                await broadcast_event_update(
                    scenario_id=scenario_uuid,
                    event_type="task_dispatched",
                    event_data=notification,
                )
        except Exception as e:
            logger.warning(f"[TaskDispatch] WebSocket推送失败: {e}")
            errors.append(f"通知推送失败: {card.get('card_id')}")
    
    # 更新分发批次状态
    all_dispatched = all(c.get("status") == "dispatched" for c in task_cards)
    dispatch_data["status"] = "dispatched" if all_dispatched else "partial"
    dispatch_data["updated_at"] = datetime.utcnow().isoformat()
    
    logger.info(
        f"[TaskDispatch] 任务下发完成: dispatch_id={dispatch_id}, "
        f"dispatched={len(cards_to_dispatch)}"
    )
    
    return TaskDispatchResponse(
        success=len(errors) == 0,
        dispatched_count=len(cards_to_dispatch),
        notifications_sent=notifications,
        errors=errors,
    )


@router.post("/{dispatch_id}/cards/{card_id}/status")
async def update_card_status(
    dispatch_id: str,
    card_id: str,
    new_status: str,
) -> Dict[str, Any]:
    """
    更新任务卡状态
    
    执行单位反馈状态时调用。
    
    Args:
        dispatch_id: 分发批次ID
        card_id: 任务卡ID
        new_status: 新状态（accepted/rejected/in_progress/completed/failed）
    """
    if dispatch_id not in _dispatch_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"分发批次 {dispatch_id} 不存在",
        )
    
    valid_statuses = ["accepted", "rejected", "in_progress", "completed", "failed"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效状态，可选: {valid_statuses}",
        )
    
    dispatch_data = _dispatch_store[dispatch_id]
    task_cards = dispatch_data.get("task_cards", [])
    
    # 查找并更新任务卡
    card_found = False
    for card in task_cards:
        if card.get("card_id") == card_id:
            card["status"] = new_status
            card["status_updated_at"] = datetime.utcnow().isoformat()
            card_found = True
            break
    
    if not card_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务卡 {card_id} 不存在",
        )
    
    # WebSocket推送状态变更
    try:
        event_id = dispatch_data.get("event_id", "")
        try:
            scenario_uuid = UUID(event_id) if event_id else None
        except (ValueError, TypeError):
            scenario_uuid = None
        
        if scenario_uuid:
            await broadcast_event_update(
                scenario_id=scenario_uuid,
                event_type="task_status_changed",
                event_data={
                    "dispatch_id": dispatch_id,
                    "card_id": card_id,
                    "new_status": new_status,
                },
            )
    except Exception as e:
        logger.warning(f"[TaskDispatch] 状态变更推送失败: {e}")
    
    logger.info(
        f"[TaskDispatch] 任务卡状态更新: card_id={card_id}, status={new_status}"
    )
    
    return {
        "success": True,
        "card_id": card_id,
        "new_status": new_status,
    }
