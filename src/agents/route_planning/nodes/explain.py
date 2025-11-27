"""
路径解释节点

使用LLM为指挥员生成自然语言的路径说明。
"""
from __future__ import annotations

import os
import json
import logging
import time
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from ..state import RoutePlanningState, RouteExplanation

logger = logging.getLogger(__name__)


class RouteExplanationOutput(BaseModel):
    """路径解释输出结构"""
    summary: str = Field(
        description="路径摘要，50-100字，概述整体路线"
    )
    route_description: str = Field(
        description="详细路线描述，包括主要道路和方向"
    )
    key_waypoints: list[str] = Field(
        description="关键途经点说明列表"
    )
    risk_warnings: list[str] = Field(
        description="风险提醒列表"
    )
    time_estimate: str = Field(
        description="时间估计说明，包括可能的延误因素"
    )
    alternative_options: list[str] = Field(
        description="备选方案说明"
    )
    commander_notes: str = Field(
        description="指挥员注意事项，决策要点"
    )


def _get_llm(max_tokens: int = 4096) -> ChatOpenAI:
    """获取LLM客户端实例"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('REQUEST_TIMEOUT', '180'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        timeout=request_timeout,
        max_tokens=max_tokens,
        max_retries=0,
    )


async def explain_route(state: RoutePlanningState) -> Dict[str, Any]:
    """
    路径解释节点
    
    为指挥员生成自然语言的路径说明，包括：
    - 路径摘要和详细描述
    - 关键途经点
    - 风险提醒
    - 时间估计
    - 备选方案
    
    输入：
        - route_result / multi_route_result: 路径规划结果
        - scenario_analysis: 场景分析
        - route_evaluation: 路径评估结果
        
    输出：
        - route_explanation: 路径解释
        - final_output: 最终输出
    """
    start_time = time.perf_counter()
    logger.info(f"[路径解释] 开始 request_id={state['request_id']}")
    
    route_result = state.get("route_result")
    multi_route_result = state.get("multi_route_result")
    
    # 无规划结果时生成失败说明
    if route_result is None and multi_route_result is None:
        explanation: RouteExplanation = {
            "summary": "路径规划失败，未能找到可行路线",
            "route_description": "系统多次尝试后仍无法找到从起点到终点的可行路径",
            "key_waypoints": [],
            "risk_warnings": ["当前道路条件可能不支持车辆通行"],
            "time_estimate": "无法估计",
            "alternative_options": ["建议使用直升机", "建议人工规划备选路线", "建议等待道路恢复"],
            "commander_notes": "需要人工介入，考虑其他交通方式或等待道路条件改善",
        }
        
        return {
            "route_explanation": explanation,
            "final_output": _build_final_output(state, explanation),
            "success": False,
            "current_phase": "completed",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["explain_route"],
            },
        }
    
    # 调用LLM生成解释
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=RouteExplanationOutput)
    
    system_prompt = """你是应急救援指挥通信员，负责向指挥员报告路径规划结果。

请用清晰、专业的语言描述规划路径，确保指挥员能快速理解关键信息。

报告要求：
1. 简明扼要，突出重点
2. 使用方位词（东南西北）描述方向
3. 明确标注风险点和注意事项
4. 给出可操作的建议

{format_instructions}"""

    human_prompt = """【任务背景】
灾情: {disaster_type}
紧急程度: {urgency}
规划策略: {strategy}

【规划结果】
类型: {result_type}
起点: {start}
终点: {end}
总距离: {distance_km:.2f}公里
预计时间: {duration_min:.0f}分钟
途经点数: {waypoint_count}
风险评分: {risk_score:.1f}/1.0

【路径评估】
{evaluation_summary}
优点: {strengths}
不足: {weaknesses}

【警告信息】
{warnings}

请生成路径说明报告。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 提取数据
    scenario = state.get("scenario_analysis", {})
    disaster_ctx = state.get("disaster_context", {})
    evaluation = state.get("route_evaluation", {})
    
    if route_result:
        result_type = "单车路径"
        start_point = state.get("start", {})
        end_point = state.get("end", {})
        start_str = f"({start_point.get('lon', 0):.4f}, {start_point.get('lat', 0):.4f})"
        end_str = f"({end_point.get('lon', 0):.4f}, {end_point.get('lat', 0):.4f})"
        distance_km = route_result["total_distance_m"] / 1000
        duration_min = route_result["total_duration_seconds"] / 60
        waypoint_count = len(route_result.get("path_points", []))
        risk_score = route_result.get("risk_score", 0.3)
        warnings = route_result.get("warnings", [])
    else:
        result_type = f"多车路径（{len(multi_route_result.get('routes', []))}辆车）"
        start_str = "各车辆出发点"
        end_str = f"{multi_route_result.get('served_tasks', 0)}个任务点"
        distance_km = multi_route_result["total_distance_m"] / 1000
        duration_min = multi_route_result["total_duration_seconds"] / 60
        waypoint_count = multi_route_result.get("served_tasks", 0)
        risk_score = 0.3
        warnings = []
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "disaster_type": disaster_ctx.get("disaster_type", "未知") if disaster_ctx else "未知",
            "urgency": scenario.get("urgency_assessment", "medium"),
            "strategy": state.get("current_strategy", "balanced"),
            "result_type": result_type,
            "start": start_str,
            "end": end_str,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "waypoint_count": waypoint_count,
            "risk_score": risk_score,
            "evaluation_summary": evaluation.get("evaluation_summary", ""),
            "strengths": ", ".join(evaluation.get("strengths", [])),
            "weaknesses": ", ".join(evaluation.get("weaknesses", [])),
            "warnings": ", ".join(warnings) if warnings else "无",
            "format_instructions": parser.get_format_instructions(),
        })
        
        explanation: RouteExplanation = {
            "summary": result.get("summary", ""),
            "route_description": result.get("route_description", ""),
            "key_waypoints": result.get("key_waypoints", []),
            "risk_warnings": result.get("risk_warnings", []),
            "time_estimate": result.get("time_estimate", ""),
            "alternative_options": result.get("alternative_options", []),
            "commander_notes": result.get("commander_notes", ""),
        }
        
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(f"[路径解释] 完成 耗时={elapsed:.1f}ms")
        
        return {
            "route_explanation": explanation,
            "final_output": _build_final_output(state, explanation),
            "success": True,
            "current_phase": "completed",
            "execution_time_ms": int(time.perf_counter() * 1000 - state.get("trace", {}).get("start_time_ms", 0)),
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["explain_route"],
                "llm_calls": state.get("trace", {}).get("llm_calls", 0) + 1,
            },
        }
        
    except Exception as e:
        logger.error(f"[路径解释] LLM调用失败: {e}")
        raise RuntimeError(f"路径解释LLM调用失败: {e}") from e


def _build_final_output(
    state: RoutePlanningState,
    explanation: RouteExplanation,
) -> Dict[str, Any]:
    """构建最终输出"""
    route_result = state.get("route_result")
    multi_route_result = state.get("multi_route_result")
    
    output: Dict[str, Any] = {
        "request_id": state["request_id"],
        "request_type": state["request_type"],
        "success": route_result is not None or multi_route_result is not None,
        "explanation": explanation,
    }
    
    if route_result:
        output["route"] = {
            "route_id": route_result["route_id"],
            "vehicle_id": route_result["vehicle_id"],
            "path_points": route_result["path_points"],
            "total_distance_m": route_result["total_distance_m"],
            "total_duration_seconds": route_result["total_duration_seconds"],
            "risk_score": route_result.get("risk_score", 0),
            "warnings": route_result.get("warnings", []),
        }
    
    if multi_route_result:
        output["multi_route"] = {
            "solution_id": multi_route_result["solution_id"],
            "routes": [
                {
                    "route_id": r["route_id"],
                    "vehicle_id": r["vehicle_id"],
                    "path_points": r["path_points"],
                    "total_distance_m": r["total_distance_m"],
                    "total_duration_seconds": r["total_duration_seconds"],
                }
                for r in multi_route_result.get("routes", [])
            ],
            "total_distance_m": multi_route_result["total_distance_m"],
            "total_duration_seconds": multi_route_result["total_duration_seconds"],
            "served_tasks": multi_route_result["served_tasks"],
            "total_tasks": multi_route_result["total_tasks"],
            "coverage_rate": multi_route_result["coverage_rate"],
        }
    
    output["trace"] = {
        "phases_executed": state.get("trace", {}).get("phases_executed", []),
        "llm_calls": state.get("trace", {}).get("llm_calls", 0),
        "algorithm_calls": state.get("trace", {}).get("algorithm_calls", 0),
        "replan_count": state.get("replan_count", 0),
    }
    
    return output
