"""
待处理事件API路由

接口路径: /events/*
提供未分配任务事件的查询和AI方案生成功能
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from shapely import wkb

from src.core.database import get_db
from src.domains.frontend_api.common import ApiResponse
from src.domains.events.models import Event
from src.domains.schemes.models import Scheme
from .schemas import (
    PendingActionRequest,
    GenerateSchemeRequest,
    PendingActionEventItem,
    GenerateSchemeResponse,
    EventDetail,
    SchemeDetail,
    LocationResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["前端-待处理事件"])

# 方案有效期（分钟）- 超过此时间标记为过期
SCHEME_EXPIRE_MINUTES = 5


def is_scheme_expired(scheme: Scheme) -> bool:
    """
    检查方案是否过期
    
    灾情会随时间变化，超过5分钟的方案需要重新生成以确保时效性
    """
    if not scheme or not scheme.created_at:
        return False
    
    now = datetime.now(timezone.utc)
    scheme_time = scheme.created_at
    if scheme_time.tzinfo is None:
        scheme_time = scheme_time.replace(tzinfo=timezone.utc)
    
    age_seconds = (now - scheme_time).total_seconds()
    return age_seconds > SCHEME_EXPIRE_MINUTES * 60


def _event_to_detail(event: Event) -> EventDetail:
    """将Event ORM对象转换为响应模型"""
    point = wkb.loads(bytes(event.location.data))
    location = LocationResponse(longitude=point.x, latitude=point.y)
    
    return EventDetail(
        id=event.id,
        event_code=event.event_code,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        location=location,
        address=event.address,
        status=event.status,
        priority=event.priority,
        estimated_victims=event.estimated_victims or 0,
        is_time_critical=event.is_time_critical or False,
        golden_hour_deadline=event.golden_hour_deadline,
        reported_at=event.reported_at,
        created_at=event.created_at,
    )


def _scheme_to_detail(scheme: Scheme) -> SchemeDetail:
    """将Scheme ORM对象转换为响应模型"""
    allocations = []
    if scheme.allocations:
        for alloc in scheme.allocations:
            allocations.append({
                "id": str(alloc.id),
                "resourceType": alloc.resource_type,
                "resourceId": str(alloc.resource_id),
                "resourceName": alloc.resource_name,
                "assignedRole": alloc.assigned_role,
                "matchScore": float(alloc.match_score) if alloc.match_score else None,
                "recommendationReason": alloc.full_recommendation_reason,
            })
    
    return SchemeDetail(
        id=scheme.id,
        scheme_code=scheme.scheme_code,
        scheme_type=scheme.scheme_type,
        title=scheme.title,
        objective=scheme.objective,
        description=scheme.description,
        status=scheme.status,
        ai_confidence_score=float(scheme.ai_confidence_score) if scheme.ai_confidence_score else None,
        ai_reasoning=scheme.ai_reasoning,
        estimated_duration_minutes=scheme.estimated_duration_minutes,
        created_at=scheme.created_at,
        allocations=allocations,
    )


@router.post("/pending-action", response_model=ApiResponse[list[PendingActionEventItem]])
async def get_pending_action_events(
    request: PendingActionRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[PendingActionEventItem]]:
    """
    查询待处理事件列表
    
    返回已确认但未分配任务的事件，每个事件附带AI方案（如有）。
    
    筛选条件：
    - status = confirmed（已确认）
    - event_type != earthquake（排除主震信息，保留次生灾害和其他需要处理的类型）
    - 无关联任务（NOT EXISTS tasks）
    
    方案时效性：
    - scheme.created_at 超过5分钟标记 schemeExpired: true
    - 前端可根据此字段决定是否重新生成方案
    """
    logger.info(f"查询待处理事件, scenarioId={request.scenario_id}")
    
    try:
        # 查询符合条件的事件（使用原生SQL确保NOT EXISTS正确执行）
        # 只排除earthquake（主震信息），保留所有其他需要处理的事件类型
        sql = text("""
            SELECT e.id as event_id
            FROM operational_v2.events_v2 e
            WHERE e.scenario_id = :scenario_id
              AND e.status = 'confirmed'
              AND e.event_type != 'earthquake'
              AND NOT EXISTS (
                SELECT 1 FROM operational_v2.tasks_v2 t 
                WHERE t.event_id = e.id
              )
            ORDER BY 
              CASE e.priority 
                WHEN 'critical' THEN 1 
                WHEN 'high' THEN 2 
                WHEN 'medium' THEN 3 
                WHEN 'low' THEN 4 
              END,
              e.reported_at ASC
        """)
        
        result = await db.execute(sql, {"scenario_id": str(request.scenario_id)})
        event_ids = [row.event_id for row in result.fetchall()]
        
        if not event_ids:
            logger.info("没有待处理事件")
            return ApiResponse.success([])
        
        # 批量查询事件详情
        events_result = await db.execute(
            select(Event).where(Event.id.in_(event_ids))
        )
        events = {e.id: e for e in events_result.scalars().all()}
        
        # 批量查询关联的方案（取每个事件最新的有效方案）
        schemes_sql = text("""
            SELECT DISTINCT ON (s.event_id) s.id as scheme_id, s.event_id
            FROM operational_v2.schemes_v2 s
            WHERE s.event_id = ANY(:event_ids)
              AND s.status NOT IN ('cancelled', 'superseded')
            ORDER BY s.event_id, s.created_at DESC
        """)
        schemes_result = await db.execute(schemes_sql, {"event_ids": event_ids})
        scheme_event_map = {row.event_id: row.scheme_id for row in schemes_result.fetchall()}
        
        # 批量查询方案详情（带allocations）
        scheme_ids = list(scheme_event_map.values())
        schemes = {}
        if scheme_ids:
            from sqlalchemy.orm import selectinload
            schemes_detail_result = await db.execute(
                select(Scheme)
                .options(selectinload(Scheme.allocations))
                .where(Scheme.id.in_(scheme_ids))
            )
            schemes = {s.id: s for s in schemes_detail_result.scalars().all()}
        
        # 组装响应
        items: list[PendingActionEventItem] = []
        for event_id in event_ids:
            event = events.get(event_id)
            if not event:
                continue
            
            scheme_id = scheme_event_map.get(event_id)
            scheme = schemes.get(scheme_id) if scheme_id else None
            
            has_scheme = scheme is not None
            scheme_expired = is_scheme_expired(scheme) if scheme else False
            
            item = PendingActionEventItem(
                event=_event_to_detail(event),
                scheme=_scheme_to_detail(scheme) if scheme else None,
                has_scheme=has_scheme,
                scheme_expired=scheme_expired,
            )
            items.append(item)
        
        logger.info(f"返回待处理事件数量: {len(items)}")
        return ApiResponse.success([item.model_dump(by_alias=True) for item in items])
        
    except Exception as e:
        logger.exception(f"查询待处理事件失败: {e}")
        return ApiResponse.error(500, f"查询失败: {str(e)}")


@router.post("/{event_id}/generate-scheme", response_model=ApiResponse[GenerateSchemeResponse])
async def generate_scheme_for_event(
    event_id: UUID,
    request: GenerateSchemeRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[GenerateSchemeResponse]:
    """
    为事件生成AI方案
    
    调用EmergencyAIAgent分析事件并生成救援方案，方案会保存到数据库。
    如果事件已有方案，会生成新版本方案。
    
    业务流程：
    1. 验证事件存在且状态正确
    2. 调用EmergencyAIAgent.analyze()进行AI分析
    3. 通过SchemePersister保存方案到数据库
    4. 返回生成的方案详情
    """
    logger.info(f"为事件生成AI方案, eventId={event_id}, scenarioId={request.scenario_id}")
    
    try:
        # 1. 查询事件
        event_result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = event_result.scalar_one_or_none()
        
        if not event:
            return ApiResponse.error(404, f"事件不存在: {event_id}")
        
        if event.scenario_id != request.scenario_id:
            return ApiResponse.error(400, "事件不属于指定想定")
        
        if event.status not in ("confirmed", "planning"):
            return ApiResponse.error(400, f"事件状态不允许生成方案: {event.status}")
        
        # 2. 构建灾情描述
        point = wkb.loads(bytes(event.location.data))
        disaster_description = f"{event.title}"
        if event.description:
            disaster_description += f"\n{event.description}"
        if event.address:
            disaster_description += f"\n位置: {event.address}"
        if event.estimated_victims:
            disaster_description += f"\n预估受困人数: {event.estimated_victims}人"
        
        structured_input = {
            "disaster_type": event.event_type,
            "location": {
                "longitude": point.x,
                "latitude": point.y,
            },
            "severity": event.priority,
            "estimated_victims": event.estimated_victims or 0,
            "is_time_critical": event.is_time_critical or False,
        }
        
        # 3. 调用AI Agent生成方案
        from src.agents.emergency_ai.agent import get_emergency_ai_agent
        
        agent = get_emergency_ai_agent()
        ai_result = await agent.analyze(
            event_id=str(event_id),
            scenario_id=str(request.scenario_id),
            disaster_description=disaster_description,
            structured_input=structured_input,
        )
        
        if not ai_result.get("success"):
            error_msg = ai_result.get("errors", ["AI分析失败"])[0]
            logger.error(f"AI方案生成失败: {error_msg}")
            return ApiResponse.error(500, f"AI方案生成失败: {error_msg}")
        
        # 4. 保存方案到数据库
        from src.agents.db.schemes import SchemePersister
        
        persister = SchemePersister(db)
        
        # 提取AI输出
        scheme_output = ai_result.get("recommended_scheme", {})
        event_analysis = ai_result.get("understanding", {})
        resource_allocations = ai_result.get("matching", {}).get("allocations", [])
        
        save_result = await persister.save_scheme(
            event_id=str(event_id),
            scenario_id=str(request.scenario_id),
            scheme_output=scheme_output,
            event_analysis=event_analysis,
            resource_allocations=resource_allocations,
        )
        
        if not save_result.get("success"):
            error_msg = save_result.get("error", "保存方案失败")
            logger.error(f"方案保存失败: {error_msg}")
            return ApiResponse.error(500, f"方案保存失败: {error_msg}")
        
        scheme_id = UUID(save_result["scheme_id"])
        
        # 5. 查询保存的方案详情
        from sqlalchemy.orm import selectinload
        scheme_result = await db.execute(
            select(Scheme)
            .options(selectinload(Scheme.allocations))
            .where(Scheme.id == scheme_id)
        )
        scheme = scheme_result.scalar_one_or_none()
        
        if not scheme:
            return ApiResponse.error(500, "方案保存后查询失败")
        
        response = GenerateSchemeResponse(
            event_id=event_id,
            scheme_id=scheme_id,
            scheme=_scheme_to_detail(scheme),
            generated_at=datetime.now(timezone.utc),
        )
        
        logger.info(f"AI方案生成成功: eventId={event_id}, schemeId={scheme_id}")
        return ApiResponse.success(response.model_dump(by_alias=True))
        
    except Exception as e:
        logger.exception(f"生成AI方案失败: {e}")
        return ApiResponse.error(500, f"生成方案失败: {str(e)}")
