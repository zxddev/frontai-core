"""
空间查询Agent LangGraph定义

处理位置、距离、区域状态等只读空间查询。
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Literal, Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END

from .state import SpatialAgentState
from .tools.spatial_tools import (
    find_entity_location,
    find_nearest_unit,
    get_area_status,
)

logger = logging.getLogger(__name__)


def _get_llm(max_tokens: int = 1024) -> ChatOpenAI:
    """获取LLM客户端实例"""
    llm_model = os.environ.get('LLM_MODEL', '/models/openai/gpt-oss-120b')
    openai_base_url = os.environ.get('OPENAI_BASE_URL', 'http://192.168.31.50:8000/v1')
    openai_api_key = os.environ.get('OPENAI_API_KEY', 'dummy_key')
    request_timeout = int(os.environ.get('REQUEST_TIMEOUT', '60'))
    return ChatOpenAI(
        model=llm_model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        max_tokens=max_tokens,
        temperature=0,
        request_timeout=request_timeout,
    )


# 查询解析系统提示词
PARSE_QUERY_PROMPT = """你是空间查询解析器，负责解析用户的位置/空间相关问题。

可用的查询工具：
1. find_entity_location: 查询实体位置（队伍、车辆、设备）
   - 参数: entity_name(名称), entity_type(可选: TEAM/VEHICLE/DEVICE/DRONE/ROBOT_DOG)
2. find_nearest_unit: 查找最近的单位
   - 参数: reference_point(参考点，地名或坐标), target_type(TEAM/VEHICLE), count(数量), status_filter(可选)
3. get_area_status: 查询区域内单位分布
   - 参数: area_id(区域ID)

请分析用户查询，返回JSON格式：
{
  "tool": "工具名称",
  "params": {参数字典},
  "intent_summary": "意图简述"
}

如果无法解析，返回：
{"tool": null, "params": {}, "intent_summary": "无法理解的查询"}"""


# 回复格式化系统提示词
FORMAT_RESPONSE_PROMPT = """你是语音助手，负责将空间查询结果转换为简洁自然的中文回复。

要求：
1. 语言简洁明了，适合语音播报
2. 重点信息放在前面
3. 距离用公里或米表示
4. 如果查询失败，给出友好提示

示例：
- "茂县消防大队位于茂县城区，当前状态为待命。"
- "距离最近的医疗队是县医院急救队，距您约3.5公里。"
- "A区当前有3支队伍和5辆车辆。"
"""


# ============================================================================
# 节点函数
# ============================================================================

async def parse_query(state: SpatialAgentState) -> dict:
    """
    解析用户查询，提取意图和参数
    
    使用LLM解析用户的自然语言查询，提取工具和参数。
    """
    query = state.get("query", "")
    logger.info(f"解析空间查询: {query[:50]}")
    start_ts = time.time()
    
    try:
        llm = _get_llm()
        messages = [
            SystemMessage(content=PARSE_QUERY_PROMPT),
            HumanMessage(content=f"用户查询: {query}"),
        ]
        
        response = await llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # 解析JSON
        # 尝试提取JSON（处理可能的markdown代码块）
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        parsed = json.loads(response_text)
        tool_name = parsed.get("tool")
        tool_params = parsed.get("params", {})
        intent_summary = parsed.get("intent_summary", "")
        
        latency_ms = int((time.time() - start_ts) * 1000)
        logger.info(f"解析完成: tool={tool_name}, latency={latency_ms}ms")
        
        return {
            "parsed_intent": {"summary": intent_summary, "raw": parsed},
            "selected_tool": tool_name,
            "tool_input": tool_params,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "parse_latency_ms": latency_ms,
            },
        }
        
    except json.JSONDecodeError as e:
        logger.warning(f"解析JSON失败: {e}")
        return {
            "parsed_intent": {"error": "JSON解析失败"},
            "selected_tool": None,
            "tool_input": {},
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "error": str(e),
            },
        }
    except Exception as e:
        logger.exception(f"解析查询失败: {e}")
        return {
            "parsed_intent": {"error": str(e)},
            "selected_tool": None,
            "tool_input": {},
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_query"],
                "error": str(e),
            },
        }


async def execute_tool(state: SpatialAgentState) -> dict:
    """
    执行选定的空间查询工具
    """
    tool_name = state.get("selected_tool", "")
    tool_input = state.get("tool_input", {})
    
    logger.info(f"执行空间工具: {tool_name}, params={tool_input}")
    start_ts = time.time()
    
    try:
        # 调用对应工具
        if tool_name == "find_entity_location":
            result = await find_entity_location.ainvoke(tool_input)
        elif tool_name == "find_nearest_unit":
            result = await find_nearest_unit.ainvoke(tool_input)
        elif tool_name == "get_area_status":
            result = await get_area_status.ainvoke(tool_input)
        else:
            result = {"success": False, "error": f"未知工具: {tool_name}"}
        
        latency_ms = int((time.time() - start_ts) * 1000)
        logger.info(f"工具执行完成: success={result.get('success')}, latency={latency_ms}ms")
        
        tool_result = {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "success": result.get("success", False),
            "latency_ms": latency_ms,
        }
        
        return {
            "tool_results": state.get("tool_results", []) + [tool_result],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_tool"],
                "tool_calls": state.get("trace", {}).get("tool_calls", []) + [tool_name],
                "tool_latency_ms": latency_ms,
            },
        }
        
    except Exception as e:
        logger.exception(f"工具执行失败: {e}")
        tool_result = {
            "tool": tool_name,
            "input": tool_input,
            "output": {"error": str(e)},
            "success": False,
        }
        return {
            "tool_results": state.get("tool_results", []) + [tool_result],
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_tool"],
                "error": str(e),
            },
        }


async def format_response(state: SpatialAgentState) -> dict:
    """
    格式化最终回复
    
    使用LLM将工具结果转换为自然语言回复。
    """
    tool_results = state.get("tool_results", [])
    query = state.get("query", "")
    
    logger.info(f"格式化空间查询回复: {len(tool_results)} 个结果")
    
    # 如果没有工具结果或全部失败，返回错误提示
    if not tool_results:
        return {
            "response": "抱歉，我无法理解您的空间查询请求。",
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
    
    last_result = tool_results[-1]
    if not last_result.get("success"):
        error_msg = last_result.get("output", {}).get("error", "未知错误")
        return {
            "response": f"查询失败: {error_msg}",
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
    
    # 使用LLM格式化回复
    try:
        llm = _get_llm(max_tokens=512)
        result_json = json.dumps(last_result.get("output", {}), ensure_ascii=False, indent=2)
        
        messages = [
            SystemMessage(content=FORMAT_RESPONSE_PROMPT),
            HumanMessage(content=f"用户问题: {query}\n\n查询结果:\n{result_json}"),
        ]
        
        response = await llm.ainvoke(messages)
        formatted = response.content.strip()
        
        return {
            "response": formatted,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }
        
    except Exception as e:
        logger.warning(f"格式化回复失败，使用简单格式: {e}")
        # 简单格式化回退
        output = last_result.get("output", {})
        if "entities" in output and output["entities"]:
            entity = output["entities"][0]
            response = f"{entity.get('name', '未知')}的位置已查询到。"
        elif "units" in output and output["units"]:
            unit = output["units"][0]
            dist = unit.get("distance_text", "未知")
            response = f"最近的{unit.get('sub_type', '单位')}是{unit.get('name', '未知')}，距离{dist}。"
        else:
            response = "查询完成。"
        
        return {
            "response": response,
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["format_response"],
            },
        }


# ============================================================================
# 条件路由函数
# ============================================================================

def should_execute_tool(state: SpatialAgentState) -> Literal["execute", "error"]:
    """判断是否应该执行工具"""
    if state.get("selected_tool") and state.get("tool_input"):
        return "execute"
    return "error"


# ============================================================================
# 图构建
# ============================================================================

def build_spatial_agent_graph() -> StateGraph:
    """
    构建空间查询Agent状态图
    
    流程:
    ```
    START
      │
      ▼
    parse_query
      │
      ▼ (conditional)
    execute_tool ───────► format_response
      │                        │
      └────────────────────────┘
                               │
                               ▼
                              END
    ```
    """
    logger.info("构建空间查询Agent LangGraph...")
    
    workflow = StateGraph(SpatialAgentState)
    
    # 添加节点
    workflow.add_node("parse_query", parse_query)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_node("format_response", format_response)
    
    # 设置入口
    workflow.set_entry_point("parse_query")
    
    # 添加边
    workflow.add_conditional_edges(
        "parse_query",
        should_execute_tool,
        {
            "execute": "execute_tool",
            "error": "format_response",
        }
    )
    workflow.add_edge("execute_tool", "format_response")
    workflow.add_edge("format_response", END)
    
    logger.info("空间查询Agent LangGraph构建完成")
    
    return workflow


# 编译后的图（懒加载）
_compiled_graph = None


def get_spatial_agent_graph():
    """获取编译后的空间查询Agent图"""
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_spatial_agent_graph()
        _compiled_graph = workflow.compile()
        logger.info("空间查询Agent图编译完成")
    return _compiled_graph
