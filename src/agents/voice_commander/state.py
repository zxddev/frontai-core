"""
语音指挥Agent状态定义

使用TypedDict定义强类型状态，支持LangGraph消息管理。
"""
from __future__ import annotations

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage


class SpatialAgentState(TypedDict):
    """
    空间查询Agent状态
    
    用于处理位置、距离、区域状态查询。
    """
    # 输入
    query: str                                          # 用户原始查询
    session_id: str                                     # 会话ID
    
    # 消息历史
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 解析结果
    parsed_intent: Optional[Dict[str, Any]]             # 解析的意图和参数
    selected_tool: Optional[str]                        # 选择的工具名称
    tool_input: Optional[Dict[str, Any]]                # 工具输入参数
    
    # 工具执行结果
    tool_results: List[Dict[str, Any]]                  # 工具调用结果列表
    
    # 最终输出
    response: str                                       # 自然语言回复
    
    # 追踪
    trace: Dict[str, Any]                               # 执行追踪
    errors: List[str]                                   # 错误列表


class CommanderAgentState(TypedDict):
    """
    战术控制Agent状态
    
    用于处理机器人控制指令，支持中断-确认模式。
    """
    # 输入
    query: str                                          # 用户原始查询
    session_id: str                                     # 会话ID
    
    # 消息历史
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 指令解析
    parsed_command: Optional[Dict[str, Any]]            # 解析的指令
    target_unit_id: Optional[str]                       # 目标单位ID
    action_type: Optional[str]                          # 动作类型
    action_parameters: Optional[Dict[str, Any]]         # 动作参数
    
    # 安全检查
    safety_check_passed: bool                           # 安全检查是否通过
    safety_warnings: List[str]                          # 安全警告列表
    safety_blockers: List[str]                          # 安全阻断原因
    
    # 待确认指令
    pending_command_id: Optional[str]                   # 待确认指令ID
    pending_command: Optional[Dict[str, Any]]           # 待确认指令内容
    confirmation_request: Optional[str]                 # 确认请求文本
    
    # 确认状态
    confirmation_status: Optional[str]                  # approved/cancelled/timeout
    
    # 执行结果
    execution_result: Optional[Dict[str, Any]]          # 执行结果
    stomp_message_id: Optional[str]                     # STOMP消息ID
    
    # 最终输出
    response: str                                       # 自然语言回复
    
    # 追踪
    trace: Dict[str, Any]                               # 执行追踪
    errors: List[str]                                   # 错误列表


def create_spatial_state(query: str, session_id: str) -> SpatialAgentState:
    """创建空间查询Agent初始状态"""
    return SpatialAgentState(
        query=query,
        session_id=session_id,
        messages=[],
        parsed_intent=None,
        selected_tool=None,
        tool_input=None,
        tool_results=[],
        response="",
        trace={"nodes_executed": [], "tool_calls": []},
        errors=[],
    )


def create_commander_state(query: str, session_id: str) -> CommanderAgentState:
    """创建战术控制Agent初始状态"""
    return CommanderAgentState(
        query=query,
        session_id=session_id,
        messages=[],
        parsed_command=None,
        target_unit_id=None,
        action_type=None,
        action_parameters=None,
        safety_check_passed=False,
        safety_warnings=[],
        safety_blockers=[],
        pending_command_id=None,
        pending_command=None,
        confirmation_request=None,
        confirmation_status=None,
        execution_result=None,
        stomp_message_id=None,
        response="",
        trace={"nodes_executed": [], "safety_checks": []},
        errors=[],
    )
