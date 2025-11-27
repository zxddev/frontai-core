"""
场景分析节点

使用LLM分析灾情场景，理解紧急程度和关键风险，为策略选择提供依据。
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

from ..state import RoutePlanningState, ScenarioAnalysis

logger = logging.getLogger(__name__)


class ScenarioAnalysisOutput(BaseModel):
    """场景分析输出结构"""
    urgency_assessment: str = Field(
        description="紧急程度评估: critical/high/medium/low，需说明判断依据"
    )
    key_risks: list[str] = Field(
        description="关键风险点列表，至少3条"
    )
    recommended_strategy: str = Field(
        description="推荐策略: fastest/safest/balanced/capacity/fuel"
    )
    strategy_reason: str = Field(
        description="策略选择理由，结合灾情和任务特点"
    )
    special_considerations: list[str] = Field(
        description="特殊注意事项列表"
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


async def analyze_scenario(state: RoutePlanningState) -> Dict[str, Any]:
    """
    场景分析节点
    
    分析灾情上下文和自然语言请求，评估紧急程度，识别关键风险，
    为后续策略选择提供决策依据。
    
    输入：
        - disaster_context: 灾情上下文
        - natural_language_request: 自然语言请求
        - request_type: 规划类型
        
    输出：
        - scenario_analysis: 场景分析结果
        
    参考：DynamicRouteGPT论文的场景理解模块
    """
    start_time = time.perf_counter()
    logger.info(f"[场景分析] 开始 request_id={state['request_id']}")
    
    # 无灾情上下文且无自然语言请求时，使用默认分析
    disaster_context = state.get("disaster_context")
    nl_request = state.get("natural_language_request")
    
    if not disaster_context and not nl_request:
        logger.info("[场景分析] 无灾情上下文，使用默认配置")
        default_analysis: ScenarioAnalysis = {
            "urgency_assessment": "medium",
            "key_risks": ["常规任务，无特殊风险"],
            "recommended_strategy": "balanced",
            "strategy_reason": "无特殊灾情信息，采用平衡策略",
            "special_considerations": [],
        }
        elapsed = (time.perf_counter() - start_time) * 1000
        return {
            "scenario_analysis": default_analysis,
            "current_phase": "scenario_analyzed",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["analyze_scenario"],
            },
        }
    
    # 构建LLM分析
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=ScenarioAnalysisOutput)
    
    system_prompt = """你是应急救援路径规划专家，负责分析救援场景。

请根据灾情信息和任务需求，进行场景分析：

1. 紧急程度评估（critical/high/medium/low）
   - critical: 生命危急，分秒必争
   - high: 紧急但有一定时间窗口
   - medium: 重要但非紧急
   - low: 常规任务

2. 关键风险识别
   - 道路风险（塌方、积水、拥堵）
   - 环境风险（次生灾害、危化品）
   - 时间风险（黄金救援期）

3. 策略推荐
   - fastest: 生命危急时使用
   - safest: 危险环境或贵重设备运输
   - balanced: 一般救援任务
   - capacity: 重型设备运输
   - fuel: 长距离运输

{format_instructions}"""

    human_prompt = """【规划类型】
{request_type}

【灾情上下文】
{disaster_context}

【任务请求】
{nl_request}

【车辆/任务信息】
起点: {start}
终点: {end}
车辆数: {vehicle_count}
任务点数: {task_count}

请分析场景并给出建议。"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])
    
    # 准备输入数据
    disaster_context_str = json.dumps(disaster_context, ensure_ascii=False, indent=2) if disaster_context else "无"
    nl_request_str = nl_request if nl_request else "无"
    start_str = f"({state['start']['lon']:.4f}, {state['start']['lat']:.4f})" if state.get("start") else "未指定"
    end_str = f"({state['end']['lon']:.4f}, {state['end']['lat']:.4f})" if state.get("end") else "未指定"
    
    chain = prompt | llm | parser
    
    try:
        result = await chain.ainvoke({
            "request_type": state["request_type"],
            "disaster_context": disaster_context_str,
            "nl_request": nl_request_str,
            "start": start_str,
            "end": end_str,
            "vehicle_count": len(state.get("vehicles", [])) or 1,
            "task_count": len(state.get("task_points", [])),
            "format_instructions": parser.get_format_instructions(),
        })
        
        scenario_analysis: ScenarioAnalysis = {
            "urgency_assessment": result.get("urgency_assessment", "medium"),
            "key_risks": result.get("key_risks", []),
            "recommended_strategy": result.get("recommended_strategy", "balanced"),
            "strategy_reason": result.get("strategy_reason", ""),
            "special_considerations": result.get("special_considerations", []),
        }
        
        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[场景分析] 完成 urgency={scenario_analysis['urgency_assessment']} "
            f"strategy={scenario_analysis['recommended_strategy']} 耗时={elapsed:.1f}ms"
        )
        
        return {
            "scenario_analysis": scenario_analysis,
            "current_phase": "scenario_analyzed",
            "trace": {
                **state.get("trace", {}),
                "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["analyze_scenario"],
                "llm_calls": state.get("trace", {}).get("llm_calls", 0) + 1,
            },
        }
        
    except Exception as e:
        logger.error(f"[场景分析] LLM调用失败: {e}")
        # 不做降级，直接抛出异常
        raise RuntimeError(f"场景分析LLM调用失败: {e}") from e
