"""
任务查询Agent

处理任务状态查询、进度统计等请求。
返回结果包含UI联动动作（打开任务面板等）。
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
    open_panel,
    show_notification,
    NotificationLevel,
    UIActionUnion,
)
from .tools.task_tools import (
    query_task_summary,
    query_tasks_by_type,
    query_tasks_by_status,
)

logger = logging.getLogger(__name__)


class TaskAgentState(TypedDict, total=False):
    """任务Agent状态"""
    query: str                          # 用户查询
    session_id: str                     # 会话ID
    parsed_intent: Optional[str]        # 解析的意图
    tool_name: Optional[str]            # 选择的工具
    tool_params: Dict[str, Any]         # 工具参数
    tool_result: Optional[Dict]         # 工具执行结果
    response_text: str                  # 回复文本
    ui_actions: List[Dict[str, Any]]    # UI动作列表
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
PARSE_INTENT_PROMPT = """你是任务查询助手。分析用户查询，确定要执行的操作。

可用操作:
1. query_task_summary - 查询任务总体统计（"任务进度怎么样"、"有多少任务"）
2. query_tasks_by_type - 按类型查询（"搜救任务有多少"、"侦察任务完成了吗"）
3. query_tasks_by_status - 按状态查询（"正在执行什么任务"、"完成了哪些任务"）

返回JSON格式:
{"tool": "工具名", "params": {"参数名": "值"}}

示例:
- "任务进度怎么样" → {"tool": "query_task_summary", "params": {}}
- "搜救任务有多少" → {"tool": "query_tasks_by_type", "params": {"task_type": "rescue"}}
- "正在执行什么任务" → {"tool": "query_tasks_by_status", "params": {"status": "in_progress"}}

只返回JSON，不要解释。"""


# 回复格式化提示词
FORMAT_RESPONSE_PROMPT = """你是应急救援指挥助手。根据任务查询结果，生成简洁的语音回复。

要求:
1. 回复控制在50字以内，适合语音播报
2. 突出关键数字（总数、进行中数量、完成率）
3. 如有进行中的任务，简要提及
4. 语气专业简洁

查询结果:
{result}

生成自然语言回复:"""


async def parse_query(state: TaskAgentState) -> Dict[str, Any]:
    """解析用户查询，确定工具和参数"""
    query = state["query"]
    start_ts = time.time()
    
    logger.info(f"解析任务查询: {query}")
    
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
        tool_name = parsed.get("tool", "query_task_summary")
        tool_params = parsed.get("params", {})
        
        latency = time.time() - start_ts
        logger.info(f"解析完成: tool={tool_name}, latency={latency*1000:.0f}ms")
        
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
            "tool_name": "query_task_summary",
            "tool_params": {},
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "parse_error": str(e),
            },
        }


async def execute_tool(state: TaskAgentState) -> Dict[str, Any]:
    """执行任务查询工具"""
    tool_name = state.get("tool_name", "query_task_summary")
    tool_params = state.get("tool_params", {})
    start_ts = time.time()
    
    logger.info(f"执行任务工具: {tool_name}, params={tool_params}")
    
    # 工具映射
    tool_map = {
        "query_task_summary": query_task_summary,
        "query_tasks_by_type": query_tasks_by_type,
        "query_tasks_by_status": query_tasks_by_status,
    }
    
    tool = tool_map.get(tool_name)
    if not tool:
        logger.warning(f"未知工具: {tool_name}, 使用默认summary")
        tool = query_task_summary
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


async def format_response(state: TaskAgentState) -> Dict[str, Any]:
    """格式化响应，生成文本和UI动作"""
    tool_result = state.get("tool_result", {})
    start_ts = time.time()
    
    logger.info(f"格式化任务查询回复")
    
    # 生成UI动作：打开任务面板
    ui_actions: List[UIActionUnion] = [
        open_panel(PanelType.TASK_LIST),
    ]
    
    # 如果查询失败
    if not tool_result.get("success"):
        error = tool_result.get("error", "查询失败")
        return {
            "response_text": f"抱歉，{error}",
            "ui_actions": [],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
    
    # 使用LLM格式化回复
    llm = _get_llm()
    
    try:
        # 简化结果用于提示
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
        
        response = await llm.ainvoke([
            {"role": "system", "content": FORMAT_RESPONSE_PROMPT.format(result=result_str)},
        ])
        
        response_text = response.content.strip()
        
        # 添加面板提示
        response_text += " 已为您打开任务面板。"
        
        latency = time.time() - start_ts
        logger.info(f"回复格式化完成: latency={latency*1000:.0f}ms")
        
        return {
            "response_text": response_text,
            "ui_actions": [a.model_dump(exclude_none=True) for a in ui_actions],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
                "format_latency_ms": int(latency * 1000),
            },
        }
        
    except Exception as e:
        logger.error(f"格式化失败: {e}")
        
        # 降级到简单格式
        total = tool_result.get("total", 0)
        in_progress = tool_result.get("in_progress_count", 0)
        completion_rate = tool_result.get("completion_rate", 0)
        
        response_text = f"当前共有{total}个任务，{in_progress}个正在执行，完成率{completion_rate}%。已为您打开任务面板。"
        
        return {
            "response_text": response_text,
            "ui_actions": [a.model_dump(exclude_none=True) for a in ui_actions],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
                "format_error": str(e),
            },
        }


def build_task_agent_graph() -> StateGraph:
    """构建任务查询Agent图"""
    logger.info("构建任务查询Agent LangGraph...")
    
    workflow = StateGraph(TaskAgentState)
    
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_node("format_response", format_response)
    
    workflow.set_entry_point("parse_query")
    workflow.add_edge("parse_query", "execute_tool")
    workflow.add_edge("execute_tool", "format_response")
    workflow.add_edge("format_response", END)
    
    logger.info("任务查询Agent LangGraph构建完成")
    return workflow


# 编译后的图（懒加载）
_compiled_graph = None


def get_task_agent_graph():
    """获取编译后的任务Agent图"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_task_agent_graph()
        _compiled_graph = workflow.compile()
        logger.info("任务查询Agent图编译完成")
    return _compiled_graph


async def run_task_agent(query: str, session_id: str) -> AIResponse:
    """
    运行任务查询Agent
    
    Args:
        query: 用户查询
        session_id: 会话ID
        
    Returns:
        AI响应（包含文本和UI动作）
    """
    graph = get_task_agent_graph()
    
    initial_state: TaskAgentState = {
        "query": query,
        "session_id": session_id,
        "parsed_intent": None,
        "tool_name": None,
        "tool_params": {},
        "tool_result": None,
        "response_text": "",
        "ui_actions": [],
        "trace": {},
    }
    
    result = await graph.ainvoke(initial_state)
    
    return AIResponse(
        text=result.get("response_text", ""),
        ui_actions=result.get("ui_actions", []),
    )
