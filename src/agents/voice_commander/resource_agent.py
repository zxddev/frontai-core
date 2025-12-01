"""
资源查询Agent

处理队伍状态查询、空闲资源查询等请求。
返回结果包含UI联动动作（地图定位、高亮等）。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from src.infra.settings import load_settings
from .ui_actions import (
    AIResponse,
    PanelType,
    fly_to_entity,
    highlight_entities,
    show_entity_detail,
    open_panel,
    UIActionUnion,
)
from .tools.resource_tools import (
    query_team_status,
    query_available_teams,
    query_team_summary,
)

logger = logging.getLogger(__name__)


class ResourceAgentState(TypedDict, total=False):
    """资源Agent状态"""
    query: str                          # 用户查询
    session_id: str                     # 会话ID
    parsed_intent: Optional[str]        # 解析的意图
    tool_name: Optional[str]            # 选择的工具
    tool_params: Dict[str, Any]         # 工具参数
    tool_result: Optional[Dict]         # 工具执行结果
    response_text: str                  # 回复文本
    ui_actions: List[Dict[str, Any]]    # UI动作列表
    mentioned_entities: List[str]       # 提到的实体ID（用于上下文）
    trace: Dict[str, Any]               # 执行追踪


def _get_llm() -> ChatOpenAI:
    """获取LLM实例"""
    settings = load_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        temperature=0,
        request_timeout=30,
    )


# 意图解析提示词
PARSE_INTENT_PROMPT = """你是资源查询助手。分析用户查询，确定要执行的操作。

可用操作:
1. query_team_status - 查询特定队伍状态（"消防队在干什么"、"一号车队状态"）
2. query_available_teams - 查询空闲/可用队伍（"还有哪些队伍可用"、"哪些队伍空闲"）
3. query_team_summary - 查询队伍总体统计（"有多少队伍"、"资源情况"）

返回JSON格式:
{"tool": "工具名", "params": {"参数名": "值"}}

示例:
- "消防队在干什么" → {"tool": "query_team_status", "params": {"team_name": "消防"}}
- "还有哪些队伍可用" → {"tool": "query_available_teams", "params": {}}
- "有多少消防队伍可用" → {"tool": "query_available_teams", "params": {"team_type": "fire"}}
- "当前有多少队伍" → {"tool": "query_team_summary", "params": {}}

只返回JSON，不要解释。"""


# 回复格式化提示词
FORMAT_RESPONSE_PROMPT = """你是应急救援指挥助手。根据资源查询结果，生成简洁的语音回复。

要求:
1. 回复控制在50字以内，适合语音播报
2. 如查询特定队伍，说明其状态和当前任务
3. 如查询空闲队伍，说明数量
4. 语气专业简洁

查询结果:
{result}

生成自然语言回复:"""


async def parse_query(state: ResourceAgentState) -> Dict[str, Any]:
    """解析用户查询，确定工具和参数"""
    query = state["query"]
    start_ts = time.time()
    
    logger.info(f"解析资源查询: {query}")
    
    llm = _get_llm()
    
    try:
        response = await llm.ainvoke([
            {"role": "system", "content": PARSE_INTENT_PROMPT},
            {"role": "user", "content": query},
        ])
        
        result_text = response.content.strip()
        
        # 提取JSON
        if "```" in result_text:
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        
        parsed = json.loads(result_text)
        tool_name = parsed.get("tool", "query_team_summary")
        tool_params = parsed.get("params", {})
        
        latency = time.time() - start_ts
        logger.info(f"解析完成: tool={tool_name}, params={tool_params}, latency={latency*1000:.0f}ms")
        
        return {
            "tool_name": tool_name,
            "tool_params": tool_params,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "parse_latency_ms": int(latency * 1000),
            },
        }
        
    except Exception as e:
        logger.error(f"解析失败: {e}, 默认使用summary")
        return {
            "tool_name": "query_team_summary",
            "tool_params": {},
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "parse_error": str(e),
            },
        }


async def execute_tool(state: ResourceAgentState) -> Dict[str, Any]:
    """执行资源查询工具"""
    tool_name = state.get("tool_name", "query_team_summary")
    tool_params = state.get("tool_params", {})
    start_ts = time.time()
    
    logger.info(f"执行资源工具: {tool_name}, params={tool_params}")
    
    # 工具映射
    tool_map = {
        "query_team_status": query_team_status,
        "query_available_teams": query_available_teams,
        "query_team_summary": query_team_summary,
    }
    
    tool = tool_map.get(tool_name)
    if not tool:
        logger.warning(f"未知工具: {tool_name}, 使用默认summary")
        tool = query_team_summary
        tool_params = {}
    
    try:
        result = await tool.ainvoke(tool_params)
        latency = time.time() - start_ts
        
        logger.info(f"工具执行完成: success={result.get('success')}, latency={latency*1000:.0f}ms")
        
        return {
            "tool_result": result,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_tool"],
                "tool_calls": state.get("trace", {}).get("tool_calls", []) + [tool_name],
                "tool_latency_ms": int(latency * 1000),
            },
        }
        
    except Exception as e:
        logger.exception(f"工具执行失败: {e}")
        return {
            "tool_result": {"success": False, "error": str(e)},
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_tool"],
                "tool_error": str(e),
            },
        }


async def format_response(state: ResourceAgentState) -> Dict[str, Any]:
    """格式化响应，生成文本和UI动作"""
    tool_result = state.get("tool_result", {})
    tool_name = state.get("tool_name", "")
    start_ts = time.time()
    
    logger.info(f"格式化资源查询回复: tool={tool_name}")
    
    ui_actions: List[UIActionUnion] = []
    mentioned_entities: List[str] = []
    
    # 根据查询类型生成UI动作
    if tool_name == "query_team_status" and tool_result.get("found"):
        # 单个队伍查询：定位 + 高亮 + 详情
        team = tool_result.get("team", {})
        entity_id = f"team-{team.get('id')}"
        mentioned_entities.append(entity_id)
        
        ui_actions.append(fly_to_entity(entity_id, zoom=14))
        ui_actions.append(highlight_entities([entity_id], duration=8000))
        ui_actions.append(show_entity_detail(entity_id, entity_type="team"))
        
    elif tool_name == "query_available_teams":
        # 多个队伍：高亮所有
        entity_ids = tool_result.get("entity_ids", [])
        if entity_ids:
            mentioned_entities.extend(entity_ids)
            ui_actions.append(highlight_entities(entity_ids, duration=8000))
            # 定位到第一个
            if entity_ids:
                ui_actions.append(fly_to_entity(entity_ids[0], zoom=12))
    
    # 如果查询失败
    if not tool_result.get("success"):
        error = tool_result.get("error", "查询失败")
        return {
            "response_text": f"抱歉，{error}",
            "ui_actions": [],
            "mentioned_entities": [],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
    
    # 特殊处理：队伍未找到
    if tool_name == "query_team_status" and not tool_result.get("found"):
        return {
            "response_text": tool_result.get("message", "未找到该队伍"),
            "ui_actions": [],
            "mentioned_entities": [],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
    
    # 使用LLM格式化回复
    llm = _get_llm()
    
    try:
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
        
        response = await llm.ainvoke([
            {"role": "system", "content": FORMAT_RESPONSE_PROMPT.format(result=result_str)},
        ])
        
        response_text = response.content.strip()
        
        # 添加地图提示
        if ui_actions:
            response_text += " 已在地图上标注。"
        
        latency = time.time() - start_ts
        logger.info(f"回复格式化完成: latency={latency*1000:.0f}ms")
        
        return {
            "response_text": response_text,
            "ui_actions": [a.model_dump(exclude_none=True) for a in ui_actions],
            "mentioned_entities": mentioned_entities,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
                "format_latency_ms": int(latency * 1000),
            },
        }
        
    except Exception as e:
        logger.error(f"格式化失败: {e}")
        
        # 降级到简单格式
        if tool_name == "query_team_status":
            team = tool_result.get("team", {})
            task_count = tool_result.get("task_count", 0)
            status = team.get("status", "未知")
            if task_count > 0:
                response_text = f"{team.get('name')}当前{status}，正在执行{task_count}个任务。已在地图上标注。"
            else:
                response_text = f"{team.get('name')}当前{status}，没有正在执行的任务。已在地图上标注。"
        elif tool_name == "query_available_teams":
            total = tool_result.get("total", 0)
            response_text = f"当前有{total}支队伍待命可用。已在地图上标注。"
        else:
            total = tool_result.get("total", 0)
            available = tool_result.get("available_count", 0)
            response_text = f"当前共有{total}支队伍，其中{available}支待命。"
        
        return {
            "response_text": response_text,
            "ui_actions": [a.model_dump(exclude_none=True) for a in ui_actions],
            "mentioned_entities": mentioned_entities,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
                "format_error": str(e),
            },
        }


def build_resource_agent_graph() -> StateGraph:
    """构建资源查询Agent图"""
    logger.info("构建资源查询Agent LangGraph...")
    
    workflow = StateGraph(ResourceAgentState)
    
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_node("format_response", format_response)
    
    workflow.set_entry_point("parse_query")
    workflow.add_edge("parse_query", "execute_tool")
    workflow.add_edge("execute_tool", "format_response")
    workflow.add_edge("format_response", END)
    
    logger.info("资源查询Agent LangGraph构建完成")
    return workflow


# 编译后的图（懒加载）
_compiled_graph = None


def get_resource_agent_graph():
    """获取编译后的资源Agent图"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_resource_agent_graph()
        _compiled_graph = workflow.compile()
        logger.info("资源查询Agent图编译完成")
    return _compiled_graph


async def run_resource_agent(query: str, session_id: str) -> AIResponse:
    """
    运行资源查询Agent
    
    Args:
        query: 用户查询
        session_id: 会话ID
        
    Returns:
        AI响应（包含文本和UI动作）
    """
    graph = get_resource_agent_graph()
    
    initial_state: ResourceAgentState = {
        "query": query,
        "session_id": session_id,
        "parsed_intent": None,
        "tool_name": None,
        "tool_params": {},
        "tool_result": None,
        "response_text": "",
        "ui_actions": [],
        "mentioned_entities": [],
        "trace": {},
    }
    
    result = await graph.ainvoke(initial_state)
    
    return AIResponse(
        text=result.get("response_text", ""),
        ui_actions=result.get("ui_actions", []),
        context={
            "mentioned_entities": result.get("mentioned_entities", []),
        } if result.get("mentioned_entities") else None,
    )
