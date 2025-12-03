"""
战略层节点: 任务域分类

根据匹配的TRR规则识别激活的任务域。
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Any, List

from ..state import EmergencyAIState

logger = logging.getLogger(__name__)


async def classify_domains(state: EmergencyAIState) -> Dict[str, Any]:
    """
    任务域分类节点：根据匹配规则识别激活的任务域
    
    从Neo4j查询匹配规则的domain属性，确定需要激活哪些任务域。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段，包含 active_domains
    """
    event_id = state["event_id"]
    matched_rules = state.get("matched_rules", [])
    
    logger.info(
        "【任务域分类】开始执行",
        extra={
            "event_id": event_id,
            "matched_rules_count": len(matched_rules),
        }
    )
    start_time = time.time()
    
    if not matched_rules:
        raise ValueError(f"【任务域分类】无匹配规则，无法分类任务域，event_id={event_id}")
    
    # 从Neo4j查询规则的domain属性
    from ..tools.kg_tools import query_rule_domains_async
    
    rule_ids = [r["rule_id"] for r in matched_rules]
    
    logger.info(
        "【Neo4j】查询规则任务域",
        extra={"rule_ids": rule_ids}
    )
    
    records = await query_rule_domains_async(rule_ids)
    
    logger.info(
        "【Neo4j】查询结果",
        extra={"count": len(records), "data": records}
    )
    
    if not records:
        raise ValueError(f"【任务域分类】Neo4j未返回任何规则domain，rule_ids={rule_ids}")
    
    # 提取唯一的任务域
    domains_set = set()
    for record in records:
        domain = record.get("domain")
        if domain:
            domains_set.add(domain)
    
    if not domains_set:
        raise ValueError(f"【任务域分类】所有规则的domain为空，rule_ids={rule_ids}")
    
    active_domains = list(domains_set)
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["classify_domains"]
    trace["kg_calls"] = trace.get("kg_calls", 0) + 1
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【任务域分类】执行完成",
        extra={
            "event_id": event_id,
            "active_domains": active_domains,
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "active_domains": active_domains,
        "trace": trace,
        "current_phase": "strategic_domain",
    }
