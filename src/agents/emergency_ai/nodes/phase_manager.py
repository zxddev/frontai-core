"""
战略层节点: 阶段优先级管理

根据灾害发生时间确定当前阶段，并应用相应的任务域优先级。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from ..state import EmergencyAIState, TaskDomainInfo

logger = logging.getLogger(__name__)


async def apply_phase_priority(state: EmergencyAIState) -> Dict[str, Any]:
    """
    阶段优先级节点：根据灾害阶段设置任务域优先级
    
    1. 根据灾害发生时间计算当前阶段
    2. 从Neo4j查询该阶段的任务域优先级顺序
    3. 按优先级排序激活的任务域
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 disaster_phase, domain_priorities
    """
    event_id = state["event_id"]
    active_domains = state.get("active_domains", [])
    
    logger.info(
        "【阶段优先级】开始执行",
        extra={
            "event_id": event_id,
            "active_domains": active_domains,
        }
    )
    start_time = time.time()
    
    if not active_domains:
        raise ValueError(f"【阶段优先级】无激活任务域，event_id={event_id}")
    
    # 计算当前阶段
    # 从 structured_input 或 constraints 获取事件时间
    structured_input = state.get("structured_input", {})
    event_time_str = structured_input.get("event_time") or structured_input.get("disaster_time")
    
    if event_time_str:
        try:
            if isinstance(event_time_str, str):
                event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
            else:
                event_time = event_time_str
        except Exception as e:
            logger.warning(f"【阶段优先级】解析事件时间失败: {e}，使用当前时间")
            event_time = datetime.now(timezone.utc)
    else:
        logger.warning("【阶段优先级】未提供事件时间，假设刚发生（initial阶段）")
        event_time = datetime.now(timezone.utc)
    
    # 计算经过小时数
    now = datetime.now(timezone.utc)
    hours_elapsed = (now - event_time).total_seconds() / 3600
    
    # 确定阶段
    if hours_elapsed < 2:
        phase_id = "initial"
    elif hours_elapsed < 24:
        phase_id = "golden"
    elif hours_elapsed < 72:
        phase_id = "intensive"
    else:
        phase_id = "recovery"
    
    logger.info(
        "【阶段优先级】计算当前阶段",
        extra={
            "event_time": str(event_time),
            "hours_elapsed": round(hours_elapsed, 2),
            "phase_id": phase_id,
        }
    )
    
    # 从Neo4j查询阶段优先级
    from ..tools.kg_tools import query_phase_priorities_async, query_phase_info_async
    
    logger.info(
        "【Neo4j】查询阶段优先级",
        extra={"phase_id": phase_id}
    )
    
    records = await query_phase_priorities_async(phase_id)
    
    logger.info(
        "【Neo4j】查询结果",
        extra={"count": len(records), "data": records}
    )
    
    if not records:
        raise ValueError(f"【阶段优先级】Neo4j未返回阶段优先级配置，phase_id={phase_id}")
    
    # 查询阶段名称
    phase_info = await query_phase_info_async(phase_id)
    phase_name = phase_info["name"] if phase_info else phase_id
    
    # 构建优先级列表（只包含激活的任务域）
    domain_priorities: List[TaskDomainInfo] = []
    for record in records:
        domain_id = record["domain_id"]
        if domain_id in active_domains:
            domain_priorities.append(TaskDomainInfo(
                domain_id=domain_id,
                name=record["name"],
                priority=record["rank"],
                description=record.get("description", ""),
            ))
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["apply_phase_priority"]
    trace["kg_calls"] = trace.get("kg_calls", 0) + 2
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【阶段优先级】执行完成",
        extra={
            "event_id": event_id,
            "disaster_phase": phase_id,
            "disaster_phase_name": phase_name,
            "domain_priorities": [d["domain_id"] for d in domain_priorities],
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "disaster_phase": phase_id,
        "disaster_phase_name": phase_name,
        "domain_priorities": domain_priorities,
        "trace": trace,
        "current_phase": "strategic_phase",
    }
