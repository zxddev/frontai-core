"""
战术控制Agent LangGraph定义

处理机器人控制指令，支持中断-确认安全机制。
"""
from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import CommanderAgentState

logger = logging.getLogger(__name__)


# ============================================================================
# 节点函数（骨架）
# ============================================================================

async def parse_command(state: CommanderAgentState) -> dict:
    """
    解析控制指令，提取目标单位和动作
    
    输入: state.query
    输出: parsed_command, target_unit_id, action_type, action_parameters
    """
    logger.info(f"解析控制指令: {state['query'][:50]}")
    
    # TODO: Phase 3 实现
    # 1. 使用LLM解析用户指令
    # 2. 提取目标单位（无人机/机器狗）
    # 3. 提取动作类型和参数
    
    return {
        "parsed_command": {"raw": state["query"]},
        "target_unit_id": None,
        "action_type": None,
        "action_parameters": {},
        "trace": {
            **state.get("trace", {}),
            "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["parse_command"],
        },
    }


async def safety_check(state: CommanderAgentState) -> dict:
    """
    执行安全检查
    
    检查项:
    - 目标位置是否在禁飞区
    - 单位电量是否充足
    - 是否存在任务冲突
    
    输入: state.target_unit_id, state.action_type, state.action_parameters
    输出: safety_check_passed, safety_warnings, safety_blockers
    """
    logger.info(f"执行安全检查: unit={state.get('target_unit_id')}")
    
    # TODO: Phase 3 实现
    # 1. 查询禁飞区数据
    # 2. 查询单位电量
    # 3. 查询当前任务状态
    
    warnings = []
    blockers = []
    
    # 示例：检查目标单位是否存在
    if not state.get("target_unit_id"):
        blockers.append("未能识别目标单位")
    
    passed = len(blockers) == 0
    
    return {
        "safety_check_passed": passed,
        "safety_warnings": warnings,
        "safety_blockers": blockers,
        "trace": {
            **state.get("trace", {}),
            "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["safety_check"],
            "safety_checks": state.get("trace", {}).get("safety_checks", []) + [
                {"passed": passed, "warnings": warnings, "blockers": blockers}
            ],
        },
    }


async def generate_confirmation(state: CommanderAgentState) -> dict:
    """
    生成确认请求
    
    输入: state.target_unit_id, state.action_type, state.action_parameters
    输出: pending_command_id, pending_command, confirmation_request
    """
    from uuid import uuid4
    
    logger.info("生成指令确认请求")
    
    # TODO: Phase 3 实现
    # 1. 构建TacticalCommand
    # 2. 生成人类可读的确认请求文本
    
    command_id = str(uuid4())
    
    # 生成确认请求文本
    unit_id = state.get("target_unit_id", "未知单位")
    action = state.get("action_type", "未知动作")
    
    confirmation_text = f"已准备指令：{action} {unit_id}。请确认执行。"
    
    if state.get("safety_warnings"):
        warnings_text = "、".join(state["safety_warnings"])
        confirmation_text += f" 注意：{warnings_text}"
    
    return {
        "pending_command_id": command_id,
        "pending_command": {
            "id": command_id,
            "target_unit_id": unit_id,
            "action_type": action,
            "parameters": state.get("action_parameters", {}),
        },
        "confirmation_request": confirmation_text,
        "trace": {
            **state.get("trace", {}),
            "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["generate_confirmation"],
        },
    }


async def execute_command(state: CommanderAgentState) -> dict:
    """
    执行已确认的指令
    
    调用 adapter-hub 发送机器狗控制命令。
    
    输入: state.pending_command, state.confirmation_status
    输出: execution_result, stomp_message_id, response
    """
    from src.infra.settings import load_settings
    from src.infra.clients.adapter_hub import (
        AdapterHubClient,
        AdapterHubError,
        build_robotdog_command,
    )

    logger.info(f"执行控制指令: status={state.get('confirmation_status')}")
    
    confirmation_status = state.get("confirmation_status")
    
    if confirmation_status == "approved":
        settings = load_settings()
        device_id = state.get("target_unit_id") or settings.default_robotdog_id
        action = state.get("action_type") or "stop"
        
        logger.info(
            "adapter_hub_execute_start",
            extra={"device_id": device_id, "action": action},
        )
        
        try:
            client = AdapterHubClient(settings.adapter_hub_base_url)
            command = build_robotdog_command(device_id, action)
            adapter_response = await client.send_command(command)
            
            logger.info(
                "adapter_hub_execute_success",
                extra={"device_id": device_id, "action": action, "response": adapter_response},
            )
            
            return {
                "execution_result": {
                    "status": "sent",
                    "message": "指令已发送",
                    "adapter_response": adapter_response,
                    "command": command,
                },
                "stomp_message_id": state.get("pending_command_id"),
                "response": f"已向机器狗({device_id})发送动作：{action}。",
                "trace": {
                    **state.get("trace", {}),
                    "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_command"],
                },
            }
        except AdapterHubError as exc:
            logger.error(
                "adapter_hub_execute_failed",
                extra={"device_id": device_id, "action": action, "error": str(exc)},
            )
            return {
                "execution_result": {"status": "error", "message": str(exc)},
                "response": f"机器狗指令发送失败：{exc}",
                "trace": {
                    **state.get("trace", {}),
                    "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_command"],
                },
            }
    
    elif confirmation_status == "cancelled":
        return {
            "execution_result": {"status": "cancelled", "message": "指令已取消"},
            "response": "指令已取消。",
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_command"],
            },
        }
    
    else:  # timeout or unknown
        return {
            "execution_result": {"status": "timeout", "message": "确认超时"},
            "response": "确认超时，指令已取消。",
            "trace": {
                **state.get("trace", {}),
                "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["execute_command"],
            },
        }


async def handle_blocked(state: CommanderAgentState) -> dict:
    """
    处理被安全检查阻断的情况
    
    输入: state.safety_blockers
    输出: response
    """
    blockers = state.get("safety_blockers", [])
    blockers_text = "、".join(blockers) if blockers else "安全检查未通过"
    
    return {
        "response": f"无法执行该指令：{blockers_text}",
        "trace": {
            **state.get("trace", {}),
            "nodes_executed": state.get("trace", {}).get("nodes_executed", []) + ["handle_blocked"],
        },
    }


# ============================================================================
# 条件路由函数
# ============================================================================

def should_continue_after_safety(state: CommanderAgentState) -> Literal["confirm", "blocked"]:
    """判断安全检查后是否继续"""
    if state.get("safety_check_passed"):
        return "confirm"
    return "blocked"


# ============================================================================
# 图构建
# ============================================================================

def build_commander_agent_graph() -> StateGraph:
    """
    构建战术控制Agent状态图
    
    流程:
    ```
    START
      │
      ▼
    parse_command
      │
      ▼
    safety_check
      │
      ▼ (conditional)
    ┌─────────────────────────────┐
    │  passed        │  blocked   │
    │     │          │     │      │
    │     ▼          │     ▼      │
    │ generate_      │ handle_    │
    │ confirmation   │ blocked    │
    │     │          │     │      │
    │     ▼          │     │      │
    │ [INTERRUPT]    │     │      │
    │     │          │     │      │
    │     ▼          │     │      │
    │ execute_       │     │      │
    │ command        │     │      │
    └─────────────────────────────┘
                     │
                     ▼
                    END
    ```
    
    关键: interrupt_before=["execute_command"] 强制人工确认
    """
    logger.info("构建战术控制Agent LangGraph...")
    
    workflow = StateGraph(CommanderAgentState)
    
    # 添加节点
    workflow.add_node("parse_command", parse_command)
    workflow.add_node("safety_check", safety_check)
    workflow.add_node("generate_confirmation", generate_confirmation)
    workflow.add_node("execute_command", execute_command)
    workflow.add_node("handle_blocked", handle_blocked)
    
    # 设置入口
    workflow.set_entry_point("parse_command")
    
    # 添加边
    workflow.add_edge("parse_command", "safety_check")
    
    workflow.add_conditional_edges(
        "safety_check",
        should_continue_after_safety,
        {
            "confirm": "generate_confirmation",
            "blocked": "handle_blocked",
        }
    )
    
    workflow.add_edge("generate_confirmation", "execute_command")
    workflow.add_edge("execute_command", END)
    workflow.add_edge("handle_blocked", END)
    
    logger.info("战术控制Agent LangGraph构建完成")
    
    return workflow


# 编译后的图（懒加载）
_compiled_graph = None


def get_commander_agent_graph():
    """
    获取编译后的战术控制Agent图
    
    配置:
    - checkpointer: MemorySaver (支持状态持久化)
    - interrupt_before: ["execute_command"] (强制人工确认)
    """
    global _compiled_graph
    if _compiled_graph is None:
        workflow = build_commander_agent_graph()
        _compiled_graph = workflow.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["execute_command"],
        )
        logger.info("战术控制Agent图编译完成 (带中断)")
    return _compiled_graph
