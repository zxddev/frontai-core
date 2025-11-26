"""
阶段1: 灾情理解节点

使用LLM解析灾情描述，使用RAG检索相似案例。
支持LLM和RAG并行调用以提高性能。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, Tuple, List, Optional

from langchain_core.messages import HumanMessage, AIMessage

from ..state import EmergencyAIState, ParsedDisasterInfo
from ..tools.llm_tools import parse_disaster_description_async
from ..tools.rag_tools import search_similar_cases_async

logger = logging.getLogger(__name__)


async def _parse_disaster_with_llm(
    description: str,
    structured_input: Dict[str, Any],
) -> Tuple[Optional[ParsedDisasterInfo], Optional[str]]:
    """LLM解析灾情（内部函数，用于并行调用）"""
    try:
        parsed_result = await parse_disaster_description_async(
            description=description,
            context=structured_input,
        )
        
        parsed_disaster: ParsedDisasterInfo = {
            "disaster_type": parsed_result.get("disaster_type", "unknown"),
            "location": structured_input.get("location", {"longitude": 0, "latitude": 0}),
            "severity": parsed_result.get("severity", "medium"),
            "magnitude": parsed_result.get("magnitude"),  # 震级（地震专用）
            "has_building_collapse": parsed_result.get("has_building_collapse", False),
            "has_trapped_persons": parsed_result.get("has_trapped_persons", False),
            "estimated_trapped": parsed_result.get("estimated_trapped", 0),
            "has_secondary_fire": parsed_result.get("has_secondary_fire", False),
            "has_hazmat_leak": parsed_result.get("has_hazmat_leak", False),
            "has_road_damage": parsed_result.get("has_road_damage", False),
            "affected_population": parsed_result.get("affected_population", 0),
            "building_damage_level": parsed_result.get("building_damage_level", "unknown"),
            "additional_info": {
                "key_entities": parsed_result.get("key_entities", []),
                "urgency_factors": parsed_result.get("urgency_factors", []),
            },
        }
        return parsed_disaster, None
    except Exception as e:
        return None, str(e)


async def _search_cases_with_rag(
    description: str,
    disaster_type: str,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """RAG检索相似案例（内部函数，用于并行调用）"""
    try:
        cases = await search_similar_cases_async(
            query=description,
            disaster_type=disaster_type,
            top_k=5,
        )
        return cases, None
    except Exception as e:
        return [], str(e)


async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    """
    灾情理解节点：使用LLM解析灾情描述
    
    并行执行LLM解析和RAG检索以提高性能。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    logger.info(
        "执行灾情理解节点（并行模式）",
        extra={"event_id": state["event_id"], "description_length": len(state["disaster_description"])}
    )
    start_time = time.time()
    
    description = state["disaster_description"]
    structured_input = state.get("structured_input", {})
    
    # 从structured_input获取灾害类型（用于RAG预搜索）
    hint_disaster_type = structured_input.get("disaster_type", "earthquake")
    
    # 并行执行LLM解析和RAG检索
    logger.info("[并行] 同时启动LLM解析和RAG检索...")
    llm_task = _parse_disaster_with_llm(description, structured_input)
    rag_task = _search_cases_with_rag(description, hint_disaster_type)
    
    (parsed_disaster, llm_error), (cases, rag_error) = await asyncio.gather(llm_task, rag_task)
    
    parallel_time = int((time.time() - start_time) * 1000)
    logger.info(f"[并行] LLM和RAG并行完成，耗时{parallel_time}ms")
    
    # 处理LLM结果
    errors: List[str] = list(state.get("errors", []))
    if llm_error:
        logger.error(f"LLM解析失败: {llm_error}")
        errors.append(f"灾情理解失败: {llm_error}")
        return {
            "errors": errors,
            "current_phase": "understanding_failed",
        }
    
    if rag_error:
        logger.warning(f"RAG检索失败（不阻塞流程）: {rag_error}")
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["understand_disaster"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["rag_calls"] = trace.get("rag_calls", 0) + 1
    trace["parallel_optimization"] = True
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "灾情理解完成（并行模式）",
        extra={
            "disaster_type": parsed_disaster["disaster_type"],
            "severity": parsed_disaster["severity"],
            "cases_found": len(cases),
            "elapsed_ms": elapsed_ms,
        }
    )
    
    return {
        "parsed_disaster": parsed_disaster,
        "similar_cases": cases,  # 直接返回案例，跳过enhance_with_cases
        "current_phase": "understanding",
        "trace": trace,
        "messages": [
            HumanMessage(content=f"请分析灾情：{description}"),
            AIMessage(content=f"灾情分析完成：类型={parsed_disaster['disaster_type']}，严重程度={parsed_disaster['severity']}"),
        ],
    }


async def enhance_with_cases(state: EmergencyAIState) -> Dict[str, Any]:
    """
    案例增强节点：使用RAG检索相似历史案例
    
    从向量数据库中检索相似案例，提取经验教训和最佳实践。
    如果 understand_disaster 已并行检索了案例，则直接跳过。
    
    Args:
        state: 当前状态
        
    Returns:
        更新的状态字段
    """
    # 如果已有案例（并行模式），直接生成总结并返回
    existing_cases = state.get("similar_cases", [])
    if existing_cases:
        logger.info(f"[跳过] 案例已由并行模式检索，共{len(existing_cases)}个案例")
        parsed_disaster = state.get("parsed_disaster", {})
        disaster_type = parsed_disaster.get("disaster_type", "unknown")
        
        summary_parts = [f"灾害类型: {disaster_type}"]
        if parsed_disaster.get("has_building_collapse"):
            summary_parts.append(f"建筑倒塌，预估被困{parsed_disaster.get('estimated_trapped', 0)}人")
        if existing_cases:
            summary_parts.append(f"找到{len(existing_cases)}个相似历史案例可供参考")
        
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["enhance_with_cases"]
        
        return {
            "understanding_summary": "；".join(summary_parts),
            "trace": trace,
        }
    
    logger.info("执行案例增强节点", extra={"event_id": state["event_id"]})
    start_time = time.time()
    
    # 获取灾情信息
    parsed_disaster = state.get("parsed_disaster")
    if not parsed_disaster:
        logger.warning("无灾情解析结果，跳过案例检索")
        return {"similar_cases": []}
    
    disaster_type = parsed_disaster.get("disaster_type", "earthquake")
    description = state["disaster_description"]
    
    # 调用RAG检索
    try:
        cases = await search_similar_cases_async(
            query=description,
            disaster_type=disaster_type,
            top_k=5,
        )
        
        # 生成理解总结
        summary_parts = [
            f"灾害类型: {disaster_type}",
            f"严重程度: {parsed_disaster.get('severity', 'unknown')}",
        ]
        
        if parsed_disaster.get("has_building_collapse"):
            summary_parts.append(f"建筑倒塌，预估被困{parsed_disaster.get('estimated_trapped', 0)}人")
        if parsed_disaster.get("has_secondary_fire"):
            summary_parts.append("存在次生火灾")
        if parsed_disaster.get("has_hazmat_leak"):
            summary_parts.append("存在危化品泄漏")
            
        if cases:
            summary_parts.append(f"找到{len(cases)}个相似历史案例可供参考")
        
        understanding_summary = "；".join(summary_parts)
        
        # 更新追踪信息
        trace = state.get("trace", {})
        trace["phases_executed"] = trace.get("phases_executed", []) + ["enhance_with_cases"]
        trace["rag_calls"] = trace.get("rag_calls", 0) + 1
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "案例增强完成",
            extra={"cases_found": len(cases), "elapsed_ms": elapsed_ms}
        )
        
        return {
            "similar_cases": cases,
            "understanding_summary": understanding_summary,
            "trace": trace,
        }
        
    except Exception as e:
        # RAG检索失败不阻塞流程，记录警告继续
        logger.warning("案例检索失败，继续后续流程", extra={"error": str(e)})
        return {
            "similar_cases": [],
            "understanding_summary": f"灾害类型: {disaster_type}",
        }
