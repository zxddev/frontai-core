"""
态势标绘对话Agent

基于LangGraph ReAct模式，支持自然语言标绘指令。
"""
from __future__ import annotations

import logging
import os

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

from .tools import plot_point, plot_circle, geocode, delete_plot

logger = logging.getLogger(__name__)

# Agent System Prompt（英文以确保LLM指令遵循能力）
SYSTEM_PROMPT = """You are a situation plotting assistant for emergency command maps.

IMPORTANT: The scenario_id will be provided in the first system message. You MUST use this scenario_id in all tool calls.

Available operations:
1. plot_point - Mark points on map (requires scenario_id)
   - event_point: Event marker icon
   - rescue_target: Rescue target with ripple animation (use for important rescue locations)
   - situation_point: Text label annotation
   - resettle_point: Resettlement/evacuation point
   - resource_point: Resource/supply point

2. plot_circle - Draw circular areas (requires scenario_id)
   - danger_area: Danger zone (rendered in orange)
   - safety_area: Safety zone (rendered in green)
   - command_post_candidate: Command post location (rendered in blue)

3. geocode - Convert address to coordinates
   - Use when user provides address instead of coordinates

4. delete_plot - Remove a plot by entity ID

Workflow:
- Extract the scenario_id from the context (it will be provided)
- When user mentions an address (like "北京市朝阳区"), use geocode first to get coordinates
- Then use plot_point or plot_circle with the coordinates and scenario_id
- Default radius for circle is 500 meters if not specified
- After successful plotting, report the entity name and ID

Response language: Use Chinese when responding to user.
"""


def _get_llm() -> ChatOpenAI:
    """获取LLM客户端（直接从环境变量读取，避免settings强制校验）"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('LLM_REQUEST_TIMEOUT_SECONDS', '120'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        timeout=request_timeout,
        max_retries=0,
    )


def build_situation_plot_agent():
    """构建态势标绘Agent"""
    llm = _get_llm()
    
    tools = [plot_point, plot_circle, geocode, delete_plot]
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )
    
    logger.info("SituationPlotAgent构建完成")
    return agent


# Agent单例
_agent = None


def get_situation_plot_agent():
    """获取单例Agent"""
    global _agent
    if _agent is None:
        _agent = build_situation_plot_agent()
    return _agent
