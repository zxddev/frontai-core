"""
灾情去重策略

实现来源去重和时空去重两种策略。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID

from src.domains.events.models import Event

logger = logging.getLogger(__name__)

# 去重参数配置
DEDUP_DISTANCE_METERS: float = 100.0  # 时空去重距离阈值（米）
DEDUP_TIME_WINDOW_HOURS: int = 1  # 时空去重时间窗口（小时）


@dataclass
class DeduplicationResult:
    """去重检查结果"""
    is_duplicate: bool
    duplicate_event_id: Optional[UUID] = None
    duplicate_event_code: Optional[str] = None
    reason: Optional[str] = None


async def check_source_duplicate(
    db: AsyncSession,
    source_system: str,
    source_event_id: str,
) -> DeduplicationResult:
    """
    来源去重检查
    
    基于 source_system + source_event_id 组合检查是否已存在相同上报。
    
    Args:
        db: 数据库会话
        source_system: 来源系统标识
        source_event_id: 来源系统事件ID
    
    Returns:
        去重检查结果
    """
    logger.debug(f"来源去重检查: source_system={source_system}, source_event_id={source_event_id}")
    
    # 查询source_detail中匹配的事件
    # source_detail结构: {"source_system": "xxx", "source_event_id": "xxx", ...}
    stmt = select(Event).where(
        and_(
            Event.source_detail["source_system"].astext == source_system,
            Event.source_detail["source_event_id"].astext == source_event_id,
        )
    ).limit(1)
    
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()
    
    if existing_event:
        logger.info(
            f"来源去重命中: source_system={source_system}, "
            f"source_event_id={source_event_id}, existing_event_id={existing_event.id}"
        )
        return DeduplicationResult(
            is_duplicate=True,
            duplicate_event_id=existing_event.id,
            duplicate_event_code=existing_event.event_code,
            reason=f"相同来源已上报: {source_system}/{source_event_id}",
        )
    
    return DeduplicationResult(is_duplicate=False)


async def check_spatiotemporal_duplicate(
    db: AsyncSession,
    scenario_id: UUID,
    longitude: float,
    latitude: float,
    disaster_type: str,
    occurred_at: Optional[datetime] = None,
    distance_meters: float = DEDUP_DISTANCE_METERS,
    time_window_hours: int = DEDUP_TIME_WINDOW_HOURS,
) -> DeduplicationResult:
    """
    时空去重检查
    
    检查指定范围内（距离 + 时间窗口 + 相同灾情类型）是否已存在事件。
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        longitude: 经度
        latitude: 纬度
        disaster_type: 灾情类型
        occurred_at: 发生时间（默认当前时间）
        distance_meters: 距离阈值（米）
        time_window_hours: 时间窗口（小时）
    
    Returns:
        去重检查结果
    """
    check_time = occurred_at or datetime.utcnow()
    time_start = check_time - timedelta(hours=time_window_hours)
    
    logger.debug(
        f"时空去重检查: scenario_id={scenario_id}, "
        f"location=({longitude}, {latitude}), disaster_type={disaster_type}, "
        f"time_range=[{time_start}, {check_time}], distance={distance_meters}m"
    )
    
    # 构建空间点
    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    
    # 查询条件：相同想定 + 相同灾情类型 + 时间窗口内 + 距离范围内 + 非取消状态
    stmt = select(Event).where(
        and_(
            Event.scenario_id == scenario_id,
            Event.event_type == disaster_type,
            Event.reported_at >= time_start,
            Event.reported_at <= check_time,
            Event.status.notin_(['cancelled']),
            ST_DWithin(
                Event.location,
                point,
                distance_meters,  # PostGIS ST_DWithin使用度数，需要转换
                use_spheroid=True,
            ),
        )
    ).order_by(Event.reported_at.desc()).limit(1)
    
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()
    
    if existing_event:
        logger.info(
            f"时空去重命中: scenario_id={scenario_id}, "
            f"disaster_type={disaster_type}, existing_event_id={existing_event.id}"
        )
        return DeduplicationResult(
            is_duplicate=True,
            duplicate_event_id=existing_event.id,
            duplicate_event_code=existing_event.event_code,
            reason=f"附近已有相同类型灾情: {distance_meters}m内/{time_window_hours}h内",
        )
    
    return DeduplicationResult(is_duplicate=False)


async def check_duplicate(
    db: AsyncSession,
    scenario_id: UUID,
    source_system: str,
    source_event_id: str,
    longitude: float,
    latitude: float,
    disaster_type: str,
    occurred_at: Optional[datetime] = None,
) -> DeduplicationResult:
    """
    综合去重检查
    
    依次执行来源去重和时空去重。
    
    Args:
        db: 数据库会话
        scenario_id: 想定ID
        source_system: 来源系统
        source_event_id: 来源事件ID
        longitude: 经度
        latitude: 纬度
        disaster_type: 灾情类型
        occurred_at: 发生时间
    
    Returns:
        去重检查结果
    """
    # 来源去重（优先级高）
    source_result = await check_source_duplicate(db, source_system, source_event_id)
    if source_result.is_duplicate:
        return source_result
    
    # 时空去重
    spatiotemporal_result = await check_spatiotemporal_duplicate(
        db, scenario_id, longitude, latitude, disaster_type, occurred_at
    )
    if spatiotemporal_result.is_duplicate:
        return spatiotemporal_result
    
    return DeduplicationResult(is_duplicate=False)
