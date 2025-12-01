"""Situational Awareness Node - 使用CrewAI生成所有8个模块

业务场景：向省级指挥大厅汇报态势并申请资源

此节点使用CrewAI的8个Agent协作生成完整的总体方案。
"""

import asyncio
import logging
from functools import partial
from typing import Any

from crewai import LLM

from src.agents.overall_plan.crewai.crew import (
    OverallPlanCrewError,
    create_overall_plan_crew,
    prepare_crew_inputs,
    parse_crew_output,
)
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)

# 兼容旧代码
SituationalAwarenessError = OverallPlanCrewError


async def situational_awareness_node(
    state: OverallPlanState,
    llm: LLM | None = None,
) -> dict[str, Any]:
    """使用CrewAI生成所有8个模块的态势汇报
    
    将数据库数据传给CrewAI，让各Agent基于真实数据生成汇报内容。

    Args:
        state: 当前工作流状态（包含数据库数据）
        llm: LLM实例

    Returns:
        包含8个模块内容的状态更新
    """
    event_id = state.get("event_id", "unknown")
    logger.info(f"Starting overall plan generation for event {event_id}")

    try:
        # 创建LLM
        if llm is None:
            llm = _create_default_llm()

        # 创建Crew
        crew = create_overall_plan_crew(llm)

        # 准备输入数据（从state获取数据库数据）
        event_data = state.get("event_data", {})
        scenario_data = state.get("scenario_data", {})
        available_teams = state.get("available_teams", [])
        available_supplies = state.get("available_supplies", [])
        
        inputs = prepare_crew_inputs(
            event_data=event_data,
            scenario_data=scenario_data,
            available_teams=available_teams,
            available_supplies=available_supplies,
        )

        logger.info(
            f"Prepared inputs: trapped={inputs['trapped_count']}, "
            f"teams={len(available_teams)}, supplies={len(available_supplies)}"
        )

        # 在线程池中运行CrewAI（避免事件循环冲突）
        loop = asyncio.get_event_loop()
        crew_output = await loop.run_in_executor(
            None,
            partial(crew.kickoff, inputs=inputs),
        )

        # 解析输出
        modules = parse_crew_output(crew_output)

        logger.info(f"Overall plan generation completed for event {event_id}")

        return {
            **modules,
            "current_phase": "situational_awareness_completed",
        }

    except OverallPlanCrewError:
        raise
    except Exception as e:
        logger.exception(f"Overall plan generation failed for event {event_id}")
        raise OverallPlanCrewError(f"Overall plan generation failed: {e}") from e


def _create_default_llm() -> LLM:
    """创建默认LLM实例"""
    import os

    # vLLM返回的model id是完整路径，如"/models/openai/gpt-oss-120b"
    # LiteLLM需要格式: openai/<vllm_model_id>
    llm_model = os.environ.get("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "180"))

    # LiteLLM格式: openai/<model_id>
    # 如果llm_model已包含openai前缀，直接使用；否则添加
    if llm_model.startswith("openai/"):
        model = llm_model
    else:
        model = f"openai/{llm_model}"
    
    return LLM(
        model=model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=request_timeout,
    )
