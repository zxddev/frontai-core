"""
结果评估节点

使用LLM评估路径规划结果是否满足场景需求，决定是否需要重新规划。
这是实现"评估-重规划循环"的关键节点。
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

from ..state import RoutePlanningState, RouteEvaluation

logger = logging.getLogger(__name__)


class RouteEvaluationOutput(BaseModel):
    """路径评估输出结构"""
    meets_requirements: bool = Field(
        description="是否满足场景需求"
    )
    evaluation_summary: str = Field(
        description="评估摘要，100字以内"
    )
    strengths: list[str] = Field(
        description="路径优点列表"
    )
    weaknesses: list[str] = Field(
        description="路径不足列表"
    )
    improvement_suggestions: list[str] = Field(
        description="改进建议列表"
    )
    should_replan: bool = Field(
        description="是否需要重新规划"
    )
    replan_reason: str | None = Field(
        default=None,
        description="重规划原因（should_replan=true时必填）"
    )


def _get_llm(max_tokens: int = 2048) -> ChatOpenAI:
    """获取LLM客户端实例"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('REQUEST_TIMEOUT', '120'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        timeout=request_timeout,
        max_tokens=max_tokens,
        max_retries=0,
    )


async def evaluate_result(state: RoutePlanningState) -> Dict[str, Any]:
    """
    结果评估节点
    
    评估路径规划结果是否满足场景需求。
    如果规划失败或结果不满足需求，可触发重规划循环。
    
    输入：
        - route_result / multi_route_result: 路径规划结果
        - scenario_analysis: 场景分析结果
        - strategy_selection: 策略配置
        - replan_count: 当前重规划次数
        
    输出：
        - route_evaluation: 评估结果
        - should_replan: 是否需要重规划（用于条件路由）
        
    参考：StuckSolver论文的self-reasoning机制
    """
    start_time = time.perf_counter()
    logger.info(f"[结果评估] 开始 request_id={state['request_id']}")
    
    route_result = state.get("route_result")
    multi_route_result = state.get("multi_route_result")
    replan_count = state.get("replan_count", 0)
    max_replan = state.get("max_replan_attempts", 3)
    
    # 规划失败（无结果）
    if route_result is None and multi_route_result is None:
        if replan_count < max_replan:
            logger.info(f"[结果评估] 规划失败，触发重规划 attempt={replan_count+1}/{max_replan}")
            evaluation: RouteEvaluation = {
                "meets_requirements": False,
                "evaluation_summary": "路径规划失败，未找到可行路径",
                "strengths": [],
                "weaknesses": ["无法找到从起点到终点的可行路径"],
                "improvement_suggestions": ["扩大搜索范围", "降低约束条件", "检查是否有备选路线"],
                "should_replan": True,
                "replan_reason": "规划算法未能找到可行路径，需要调整参数重试",
            }
        else:
            logger.warning(f"[结果评估] 规划失败且已达最大重试次数")
            evaluation = {
                "meets_requirements": False,
                "evaluation_summary": f"路径规划失败，已尝试{replan_count}次",
                "strengths": [],
                "weaknesses": ["多次尝试均无法找到可行路径"],
                "improvement_suggestions": ["建议人工介入", "考虑备选交通方式"],
                "should_replan": False,
                "replan_reason": None,
            }
        
        return {
            "route_evaluation": evaluation,
            "current_phase": "route_evaluated",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["evaluate_result"],
            },
        }
    
    # 有规划结果，调用LLM评估
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=RouteEvaluationOutput)
    
    system_prompt = """你是应急救援路径评估专家。

请评估路径规划结果是否满足救援场景需求。

评估维度：
1. 时间满足度：是否在可接受时间内到达
2. 安全性：路径风险是否可控
3. 覆盖率（多车）：是否覆盖所有任务点
4. 资源效率：是否合理利用车辆能力

重规划判断标准：
- 时间超出预期50%以上
- 风险评分>0.7
- 覆盖率<80%
- 存在明显更优路径
- 但已达最大重试次数则不再重规划

{format_instructions}"""

    human_prompt = """【场景分析】
紧急程度: {urgency}
关键风险: {risks}
策略: {strategy}

【规划结果】
类型: {result_type}
总距离: {distance_km:.2f}km
预计时间: {duration_min:.1f}分钟
风险评分: {risk_score:.2f}
覆盖率: {coverage:.0%}
警告: {warnings}

【重规划状态】
当前尝试: {replan_count}/{max_replan}

请评估此路径是否满足场景需求。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 提取结果数据
    scenario = state.get("scenario_analysis", {})
    strategy = state.get("strategy_selection", {})
    
    if route_result:
        result_type = "单车路径"
        distance_km = route_result["total_distance_m"] / 1000
        duration_min = route_result["total_duration_seconds"] / 60
        risk_score = route_result.get("risk_score", 0.3)
        coverage = 1.0
        warnings = route_result.get("warnings", [])
    else:
        result_type = "多车路径"
        distance_km = multi_route_result["total_distance_m"] / 1000
        duration_min = multi_route_result["total_duration_seconds"] / 60
        risk_score = 0.3
        coverage = multi_route_result.get("coverage_rate", 1.0)
        warnings = []
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "urgency": scenario.get("urgency_assessment", "medium"),
            "risks": ", ".join(scenario.get("key_risks", [])),
            "strategy": strategy.get("primary_strategy", "balanced"),
            "result_type": result_type,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "risk_score": risk_score,
            "coverage": coverage,
            "warnings": ", ".join(warnings) if warnings else "无",
            "replan_count": replan_count,
            "max_replan": max_replan,
            "format_instructions": parser.get_format_instructions(),
        })
        
        # 强制检查重规划次数限制
        should_replan = result.get("should_replan", False)
        if should_replan and replan_count >= max_replan:
            logger.info(f"[结果评估] LLM建议重规划但已达上限，不再重规划")
            should_replan = False
        
        evaluation: RouteEvaluation = {
            "meets_requirements": result.get("meets_requirements", True),
            "evaluation_summary": result.get("evaluation_summary", ""),
            "strengths": result.get("strengths", []),
            "weaknesses": result.get("weaknesses", []),
            "improvement_suggestions": result.get("improvement_suggestions", []),
            "should_replan": should_replan,
            "replan_reason": result.get("replan_reason") if should_replan else None,
        }
        
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[结果评估] 完成 meets={evaluation['meets_requirements']} "
            f"replan={evaluation['should_replan']} 耗时={elapsed:.1f}ms"
        )
        
        return {
            "route_evaluation": evaluation,
            "current_phase": "route_evaluated",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["evaluate_result"],
                "llm_calls": state.get("trace", {}).get("llm_calls", 0) + 1,
            },
        }
        
    except Exception as e:
        logger.error(f"[结果评估] LLM调用失败: {e}")
        raise RuntimeError(f"结果评估LLM调用失败: {e}") from e
