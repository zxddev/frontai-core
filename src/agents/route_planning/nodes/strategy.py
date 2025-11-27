"""
策略选择节点

根据场景分析结果，由LLM选择最优规划策略，并生成算法参数。
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

from ..state import RoutePlanningState, StrategySelection, PlanningStrategy

logger = logging.getLogger(__name__)


class StrategySelectionOutput(BaseModel):
    """策略选择输出结构"""
    primary_strategy: str = Field(
        description="主要策略: fastest/safest/balanced/capacity/fuel"
    )
    optimization_weights: dict[str, float] = Field(
        description="优化权重: {time: 0-1, safety: 0-1, distance: 0-1, fuel: 0-1}，总和为1"
    )
    algorithm_params: dict[str, Any] = Field(
        description="算法参数调整: {search_radius_km, speed_factor, risk_tolerance}"
    )
    fallback_strategy: str | None = Field(
        default=None,
        description="备选策略，主策略失败时使用"
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


# 预定义策略配置，用于无LLM场景或快速回退
STRATEGY_PRESETS: Dict[str, StrategySelection] = {
    PlanningStrategy.FASTEST.value: {
        "primary_strategy": "fastest",
        "optimization_weights": {"time": 0.7, "safety": 0.1, "distance": 0.1, "fuel": 0.1},
        "algorithm_params": {"search_radius_km": 50.0, "speed_factor": 1.2, "risk_tolerance": 0.7},
        "fallback_strategy": "balanced",
    },
    PlanningStrategy.SAFEST.value: {
        "primary_strategy": "safest",
        "optimization_weights": {"time": 0.1, "safety": 0.7, "distance": 0.1, "fuel": 0.1},
        "algorithm_params": {"search_radius_km": 100.0, "speed_factor": 0.8, "risk_tolerance": 0.2},
        "fallback_strategy": "balanced",
    },
    PlanningStrategy.BALANCED.value: {
        "primary_strategy": "balanced",
        "optimization_weights": {"time": 0.4, "safety": 0.3, "distance": 0.2, "fuel": 0.1},
        "algorithm_params": {"search_radius_km": 80.0, "speed_factor": 1.0, "risk_tolerance": 0.5},
        "fallback_strategy": None,
    },
    PlanningStrategy.CAPACITY.value: {
        "primary_strategy": "capacity",
        "optimization_weights": {"time": 0.2, "safety": 0.3, "distance": 0.2, "fuel": 0.3},
        "algorithm_params": {"search_radius_km": 100.0, "speed_factor": 0.7, "risk_tolerance": 0.3},
        "fallback_strategy": "safest",
    },
    PlanningStrategy.FUEL_EFFICIENT.value: {
        "primary_strategy": "fuel",
        "optimization_weights": {"time": 0.2, "safety": 0.2, "distance": 0.3, "fuel": 0.3},
        "algorithm_params": {"search_radius_km": 120.0, "speed_factor": 0.9, "risk_tolerance": 0.4},
        "fallback_strategy": "balanced",
    },
}


async def select_strategy(state: RoutePlanningState) -> Dict[str, Any]:
    """
    策略选择节点
    
    根据场景分析结果，选择最优规划策略并生成算法参数。
    如果已有场景分析推荐策略且无特殊约束，直接使用预设配置，
    否则调用LLM进行精细化策略调整。
    
    输入：
        - scenario_analysis: 场景分析结果
        - constraints: 用户约束条件
        - natural_language_request: 自然语言请求
        
    输出：
        - strategy_selection: 策略选择结果
        - current_strategy: 当前策略
    """
    start_time = time.perf_counter()
    logger.info(f"[策略选择] 开始 request_id={state['request_id']}")
    
    scenario_analysis = state.get("scenario_analysis")
    constraints = state.get("constraints", {})
    nl_request = state.get("natural_language_request")
    
    # 场景分析已有推荐策略，且无复杂约束，使用预设配置
    if scenario_analysis and not nl_request and not constraints.get("avoid_areas"):
        recommended = scenario_analysis.get("recommended_strategy", "balanced")
        if recommended in STRATEGY_PRESETS:
            strategy = STRATEGY_PRESETS[recommended]
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.info(f"[策略选择] 使用预设配置 strategy={recommended} 耗时={elapsed:.1f}ms")
            return {
                "strategy_selection": strategy,
                "current_strategy": strategy["primary_strategy"],
                "current_phase": "strategy_selected",
                "trace": {
                    **state.get("trace", {}),
                    "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["select_strategy"],
                },
            }
    
    # 有复杂约束或自然语言请求，调用LLM进行精细化调整
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=StrategySelectionOutput)
    
    system_prompt = """你是应急救援路径规划策略专家。

根据场景分析和约束条件，选择最优策略并调整算法参数。

策略说明：
- fastest: 时间最优，适用于生命危急
- safest: 安全最优，适用于危险环境
- balanced: 时间与安全平衡
- capacity: 道路承载力优先，适用于重型设备
- fuel: 燃油效率优先，适用于长距离

参数说明：
- search_radius_km: 搜索半径，越大越可能找到路径但计算慢
- speed_factor: 速度系数，1.0为标准，>1加速，<1减速
- risk_tolerance: 风险容忍度，0-1，越高越愿意走风险路段

{format_instructions}"""

    human_prompt = """【场景分析结果】
紧急程度: {urgency}
关键风险: {risks}
推荐策略: {recommended}
策略理由: {reason}
特殊注意: {considerations}

【用户约束】
{constraints}

【自然语言请求】
{nl_request}

【重规划次数】
当前第{replan_count}次规划

请选择策略并调整参数。如果是重规划，考虑调整参数以找到可行路径。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 准备输入
    analysis = scenario_analysis or {}
    constraints_str = json.dumps(constraints, ensure_ascii=False, indent=2) if constraints else "无"
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "urgency": analysis.get("urgency_assessment", "medium"),
            "risks": ", ".join(analysis.get("key_risks", [])),
            "recommended": analysis.get("recommended_strategy", "balanced"),
            "reason": analysis.get("strategy_reason", ""),
            "considerations": ", ".join(analysis.get("special_considerations", [])),
            "constraints": constraints_str,
            "nl_request": nl_request or "无",
            "replan_count": state.get("replan_count", 0),
            "format_instructions": parser.get_format_instructions(),
        })
        
        strategy_selection: StrategySelection = {
            "primary_strategy": result.get("primary_strategy", "balanced"),
            "optimization_weights": result.get("optimization_weights", STRATEGY_PRESETS["balanced"]["optimization_weights"]),
            "algorithm_params": result.get("algorithm_params", STRATEGY_PRESETS["balanced"]["algorithm_params"]),
            "fallback_strategy": result.get("fallback_strategy"),
        }
        
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[策略选择] 完成 strategy={strategy_selection['primary_strategy']} "
            f"耗时={elapsed:.1f}ms"
        )
        
        return {
            "strategy_selection": strategy_selection,
            "current_strategy": strategy_selection["primary_strategy"],
            "current_phase": "strategy_selected",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["select_strategy"],
                "llm_calls": state.get("trace", {}).get("llm_calls", 0) + 1,
            },
        }
        
    except Exception as e:
        logger.error(f"[策略选择] LLM调用失败: {e}")
        raise RuntimeError(f"策略选择LLM调用失败: {e}") from e
