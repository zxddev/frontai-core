"""
灾情分析共享子图

从 emergency_ai 提取的可复用灾情分析能力，供多个智能体使用：
- emergency_ai: 现场救援方案生成
- equipment_preparation: 出发前装备准备
- 其他需要灾情分析的智能体

功能：
1. LLM解析灾情描述
2. RAG检索相似案例
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, START, END

logger = logging.getLogger(__name__)


# ============================================================================
# 状态定义
# ============================================================================

class ParsedDisasterInfo(TypedDict, total=False):
    """解析后的灾情信息"""
    disaster_type: str           # 灾害类型: earthquake/flood/fire/landslide等
    location: Dict[str, float]   # 位置 {longitude, latitude}
    severity: str                # 严重程度: critical/high/medium/low
    magnitude: Optional[float]   # 震级（地震专用）
    has_building_collapse: bool  # 是否有建筑倒塌
    has_trapped_persons: bool    # 是否有被困人员
    estimated_trapped: int       # 预估被困人数
    has_secondary_fire: bool     # 是否有次生火灾
    has_hazmat_leak: bool        # 是否有危化品泄漏
    has_road_damage: bool        # 是否有道路损毁
    affected_population: int     # 受影响人口
    building_damage_level: str   # 建筑损毁等级
    additional_info: Dict[str, Any]  # 附加信息


class SimilarCase(TypedDict, total=False):
    """相似案例"""
    case_id: str
    title: str
    disaster_type: str
    similarity_score: float
    lessons_learned: List[str]
    best_practices: List[str]


class DisasterAnalysisState(TypedDict, total=False):
    """灾情分析子图状态"""
    # 输入
    disaster_description: str       # 灾情描述文本
    structured_input: Dict[str, Any]  # 结构化输入（位置、类型提示等）
    
    # 输出
    parsed_disaster: Optional[ParsedDisasterInfo]  # 解析结果
    similar_cases: List[SimilarCase]  # 相似案例
    understanding_summary: str        # 理解摘要
    
    # 追踪
    errors: List[str]
    trace: Dict[str, Any]


# ============================================================================
# 节点实现
# ============================================================================

async def understand_disaster(state: DisasterAnalysisState) -> Dict[str, Any]:
    """
    灾情理解节点：使用LLM解析灾情描述
    
    并行执行LLM解析和RAG检索以提高性能。
    """
    logger.info("执行灾情理解节点（共享子图）")
    start_time = time.time()
    
    description = state["disaster_description"]
    structured_input = state.get("structured_input", {})
    
    # 从structured_input获取灾害类型提示
    hint_disaster_type = structured_input.get("disaster_type", "earthquake")
    
    # 并行执行LLM解析和RAG检索
    llm_task = _parse_disaster_with_llm(description, structured_input)
    rag_task = _search_cases_with_rag(description, hint_disaster_type)
    
    (parsed_disaster, llm_error), (cases, rag_error) = await asyncio.gather(
        llm_task, rag_task
    )
    
    parallel_time = int((time.time() - start_time) * 1000)
    logger.info(f"灾情分析并行完成，耗时{parallel_time}ms")
    
    # 处理错误
    errors: List[str] = list(state.get("errors", []))
    if llm_error:
        logger.error(f"LLM解析失败: {llm_error}")
        errors.append(f"灾情理解失败: {llm_error}")
        return {
            "errors": errors,
            "parsed_disaster": None,
        }
    
    # RAG失败时直接报错，不允许降级
    if rag_error:
        logger.error(f"RAG检索失败: {rag_error}")
        errors.append(f"RAG检索失败: {rag_error}")
        return {
            "errors": errors,
            "parsed_disaster": parsed_disaster,
            "similar_cases": [],
        }
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["understand_disaster"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["rag_calls"] = trace.get("rag_calls", 0) + 1
    
    return {
        "parsed_disaster": parsed_disaster,
        "similar_cases": cases,
        "trace": trace,
    }


async def generate_summary(state: DisasterAnalysisState) -> Dict[str, Any]:
    """
    生成灾情理解摘要
    """
    parsed_disaster = state.get("parsed_disaster")
    cases = state.get("similar_cases", [])
    
    if not parsed_disaster:
        return {"understanding_summary": "灾情解析失败"}
    
    summary_parts = [
        f"灾害类型: {parsed_disaster.get('disaster_type', 'unknown')}",
        f"严重程度: {parsed_disaster.get('severity', 'unknown')}",
    ]
    
    if parsed_disaster.get("has_building_collapse"):
        summary_parts.append(
            f"建筑倒塌，预估被困{parsed_disaster.get('estimated_trapped', 0)}人"
        )
    if parsed_disaster.get("has_secondary_fire"):
        summary_parts.append("存在次生火灾")
    if parsed_disaster.get("has_hazmat_leak"):
        summary_parts.append("存在危化品泄漏")
    if parsed_disaster.get("has_road_damage"):
        summary_parts.append("道路损毁")
    if cases:
        summary_parts.append(f"找到{len(cases)}个相似历史案例")
    
    # 更新追踪
    trace = state.get("trace", {})
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_summary"]
    
    return {
        "understanding_summary": "；".join(summary_parts),
        "trace": trace,
    }


# ============================================================================
# 内部辅助函数
# ============================================================================

async def _parse_disaster_with_llm(
    description: str,
    structured_input: Dict[str, Any],
) -> tuple[Optional[ParsedDisasterInfo], Optional[str]]:
    """LLM解析灾情"""
    try:
        # 导入LLM工具（延迟导入避免循环依赖）
        from src.agents.emergency_ai.tools.llm_tools import parse_disaster_description_async
        
        parsed_result = await parse_disaster_description_async(
            description=description,
            context=structured_input,
        )
        
        parsed_disaster: ParsedDisasterInfo = {
            "disaster_type": parsed_result.get("disaster_type", "unknown"),
            "location": structured_input.get("location", {"longitude": 0, "latitude": 0}),
            "severity": parsed_result.get("severity", "medium"),
            "magnitude": parsed_result.get("magnitude"),
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
        logger.exception("LLM解析灾情异常")
        return None, str(e)


async def _search_cases_with_rag(
    description: str,
    disaster_type: str,
) -> tuple[List[SimilarCase], Optional[str]]:
    """RAG检索相似案例，失败时返回错误信息"""
    try:
        from src.agents.emergency_ai.tools.rag_tools import search_similar_cases_async
        
        logger.info(
            "开始RAG案例检索",
            extra={"disaster_type": disaster_type, "query_length": len(description)}
        )
        cases = await search_similar_cases_async(
            query=description,
            disaster_type=disaster_type,
            top_k=5,
        )
        logger.info(f"RAG案例检索完成，找到{len(cases)}个案例")
        return cases, None
    except Exception as e:
        # 记录错误并返回错误信息，由上层决定是否中断流程
        logger.error(f"RAG检索异常: {e}")
        return [], str(e)


# ============================================================================
# 子图构建
# ============================================================================

def build_disaster_analysis_subgraph() -> StateGraph:
    """
    构建灾情分析子图
    
    流程：
    ```
    START → understand_disaster → generate_summary → END
    ```
    
    Returns:
        未编译的StateGraph，可嵌入其他图中
    """
    logger.info("构建灾情分析子图...")
    
    workflow = StateGraph(DisasterAnalysisState)
    
    # 添加节点
    workflow.add_node("understand_disaster", understand_disaster)
    workflow.add_node("generate_summary", generate_summary)
    
    # 定义边
    workflow.add_edge(START, "understand_disaster")
    workflow.add_edge("understand_disaster", "generate_summary")
    workflow.add_edge("generate_summary", END)
    
    return workflow


# 编译后的子图（单例）
_compiled_subgraph = None


def get_disaster_analysis_subgraph():
    """获取编译后的灾情分析子图（单例）"""
    global _compiled_subgraph
    if _compiled_subgraph is None:
        workflow = build_disaster_analysis_subgraph()
        _compiled_subgraph = workflow.compile()
        logger.info("灾情分析子图编译完成")
    return _compiled_subgraph
