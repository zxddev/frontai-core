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
from src.planning.algorithms.assessment.disaster_assessment import DisasterAssessment, AlgorithmStatus

logger = logging.getLogger(__name__)


def _assess_with_physics_model(
    parsed_disaster: ParsedDisasterInfo,
    structured_input: Dict[str, Any]
) -> ParsedDisasterInfo:
    """
    使用物理模型校准灾情评估
    
    利用src/planning中的高精度物理模型（烈度衰减、高斯烟羽等）
    对LLM提取的参数进行二次计算和校准。
    """
    try:
        assessor = DisasterAssessment()
        disaster_type = parsed_disaster.get("disaster_type", "unknown")
        
        # 构造评估参数
        params = {}
        
        # 统一位置格式
        location = structured_input.get("location", {"latitude": 0, "longitude": 0})
        if "lat" in location: location["latitude"] = location["lat"]
        if "lng" in location: location["longitude"] = location["lng"]
        
        if disaster_type == "earthquake":
            # 尝试从parsed_disaster或structured_input获取震级
            magnitude = parsed_disaster.get("magnitude")
            if magnitude is None:
                magnitude = structured_input.get("magnitude", 5.0)
                
            params = {
                "magnitude": float(magnitude),
                "depth_km": float(parsed_disaster.get("depth_km") or structured_input.get("depth_km", 10.0)),
                "epicenter": location,
                "population_density": float(structured_input.get("population_density", 1000)),
                "building_vulnerability": float(structured_input.get("building_vulnerability", 0.5)),
            }
            
        elif disaster_type == "flood":
             params = {
                "rainfall_mm": float(structured_input.get("rainfall_mm", 100.0)),
                "duration_hours": float(structured_input.get("duration_hours", 24.0)),
                "affected_area_km2": float(structured_input.get("affected_area_km2", 10.0)),
                "population_density": float(structured_input.get("population_density", 3000)),
             }
             
        elif disaster_type == "hazmat":
             # 尝试从additional_info提取化学品类型
             chemical_type = "unknown"
             if "additional_info" in parsed_disaster:
                 chemical_type = parsed_disaster["additional_info"].get("chemical_type", "unknown")
                 
             params = {
                 "chemical_type": chemical_type,
                 "leak_rate_kg_s": float(structured_input.get("leak_rate", 1.0)),
                 "wind_speed_ms": float(structured_input.get("wind_speed", 2.0)),
                 "wind_direction": float(structured_input.get("wind_direction", 0.0)),
                 "source_location": location,
             }
        
        if params:
            logger.info(f"[物理模型] 启动评估: type={disaster_type}, params={params}")
            result = assessor.run({
                "disaster_type": disaster_type,
                "params": params
            })
            
            if result.status == AlgorithmStatus.SUCCESS and result.solution:
                solution = result.solution
                
                # 校准数据 (覆盖LLM的估算值)
                parsed_disaster["affected_area_km2"] = solution.affected_area_km2
                parsed_disaster["affected_population"] = solution.affected_population
                parsed_disaster["estimated_casualties"] = solution.estimated_casualties
                parsed_disaster["disaster_level"] = solution.level.value
                
                # 标记校准状态
                if "additional_info" not in parsed_disaster:
                    parsed_disaster["additional_info"] = {}
                parsed_disaster["additional_info"]["physics_model_calibrated"] = True
                parsed_disaster["additional_info"]["calibration_source"] = "src.planning.algorithms.assessment"
                
                logger.info(
                    f"[物理模型] 校准成功: "
                    f"面积={solution.affected_area_km2:.2f}km2, "
                    f"人口={solution.affected_population}, "
                    f"等级={solution.level.value}"
                )
            else:
                logger.warning(f"[物理模型] 评估未成功: {result.message}")
        else:
            logger.info(f"[物理模型] 跳过: 不支持的灾害类型或参数缺失 ({disaster_type})")
                
    except Exception as e:
        logger.warning(f"[物理模型] 执行异常: {e}", exc_info=True)
        
    return parsed_disaster


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
    
    # 【安全修复】RAG失败时降级运行，不终止流程
    # 救灾系统必须具备鲁棒性，RAG故障不应阻止救援决策
    if rag_error:
        logger.warning(f"[降级模式] RAG检索失败: {rag_error}，继续使用纯LLM结果")
        cases = []  # 使用空案例列表继续
    
    # 使用物理模型进行二次校准
    if parsed_disaster:
        parsed_disaster = _assess_with_physics_model(parsed_disaster, structured_input)
    
    # 更新追踪信息
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["understand_disaster"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["rag_calls"] = trace.get("rag_calls", 0) + 1
    trace["parallel_optimization"] = True
    if parsed_disaster.get("additional_info", {}).get("physics_model_calibrated"):
        trace["physics_model_used"] = True
    
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
        # RAG检索失败直接报错，不允许降级
        logger.error("案例检索失败", extra={"error": str(e)})
        raise RuntimeError(f"RAG案例检索失败: {e}") from e
