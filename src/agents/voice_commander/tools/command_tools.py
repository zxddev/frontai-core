"""
控制指令工具

提供机器人控制能力，所有写操作需要人工确认。
"""
from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from ..schemas import TacticalCommand, PendingCommand, ActionType

logger = logging.getLogger(__name__)


@tool
async def prepare_dispatch_command(
    unit_id: str,
    target: str,
    action: str = "NAVIGATE_TO",
    config: Optional[RunnableConfig] = None,
) -> dict:
    """
    准备派遣指令（不执行，仅生成待确认指令）
    
    生成控制指令并执行安全检查，但不实际执行。
    需要用户确认后才会发送到机器人。
    
    Args:
        unit_id: 目标单位ID，如"drone-01"、"robot-dog-02"
        target: 目标位置，可以是地名或坐标
        action: 动作类型，NAVIGATE_TO/PATROL/RETURN_HOME/STOP/FOLLOW
        
    Returns:
        待确认指令信息:
        - command_id: 待确认指令ID
        - description: 人类可读描述
        - safety_passed: 安全检查是否通过
        - safety_warnings: 安全警告列表
        - requires_confirmation: True
    """
    logger.info(f"准备派遣指令: unit={unit_id}, target={target}, action={action}")
    
    # TODO: Phase 3 实现
    # 1. 验证unit_id是否存在
    # 2. 解析target为坐标
    # 3. 执行安全检查
    # 4. 生成PendingCommand
    
    return {
        "success": False,
        "error": "功能尚未实现",
        "unit_id": unit_id,
        "target": target,
        "action": action,
        "requires_confirmation": True,
    }


@tool
async def execute_confirmed_command(
    pending_command_id: str,
    config: Optional[RunnableConfig] = None,
) -> dict:
    """
    执行已确认的指令
    
    仅在用户明确确认后调用，通过STOMP发送控制指令到机器人。
    
    Args:
        pending_command_id: 待确认指令ID
        
    Returns:
        执行结果:
        - success: 是否成功
        - stomp_message_id: STOMP消息ID
        - unit_id: 目标单位ID
        - action: 执行的动作
    """
    logger.info(f"执行已确认指令: command_id={pending_command_id}")
    
    # TODO: Phase 3 实现
    # 1. 从缓存获取PendingCommand
    # 2. 验证是否过期
    # 3. 构建STOMP消息
    # 4. 发送到对应topic
    # 5. 记录执行日志
    
    return {
        "success": False,
        "error": "功能尚未实现",
        "pending_command_id": pending_command_id,
    }
