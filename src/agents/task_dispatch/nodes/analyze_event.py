"""
Mode 2: 事件分析节点

使用LLM分析分发事件的上下文，理解事件原因和影响。
"""
from __future__ import annotations

import os
import logging
import time
from typing import Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..state import (
    TaskDispatchState,
    DispatchEvent,
    DispatchEventType,
)

logger = logging.getLogger(__name__)


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
        max_tokens=max_tokens,
        temperature=0,
        request_timeout=request_timeout,
    )


# 事件分析系统提示词
EVENT_ANALYSIS_SYSTEM_PROMPT = """你是应急救援任务调度系统的事件分析专家。

你的职责是分析任务执行过程中发生的事件，理解事件的原因、影响范围和紧急程度。

分析时请考虑：
1. 事件发生的直接原因是什么？
2. 事件对当前救援任务的影响有多大？
3. 是否需要立即处理？
4. 处理不当可能带来什么后果？

请用JSON格式输出分析结果：
{
    "event_summary": "事件简述",
    "root_cause": "根本原因分析",
    "impact_level": "high/medium/low",
    "urgency": "immediate/soon/can_wait",
    "affected_tasks": ["受影响的任务ID列表"],
    "potential_risks": ["不处理可能带来的风险"],
    "recommended_action_type": "reassign/retry/escalate/wait",
    "reasoning": "分析推理过程"
}"""


async def analyze_dispatch_event(state: TaskDispatchState) -> Dict[str, Any]:
    """
    分析分发事件
    
    使用LLM理解事件的上下文，评估影响和紧急程度。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[动态调整-1] 分析事件: event_id={state['event_id']}")
    start_time = time.time()
    
    current_event = state.get("current_event")
    if not current_event:
        logger.warning("[动态调整-1] 无当前事件")
        return {
            "errors": state.get("errors", []) + ["无当前事件"],
            "current_phase": "analyze_event",
        }
    
    # 构建事件上下文
    context = _build_event_context(current_event, state)
    
    # 调用LLM分析（禁止降级，失败即报错）
    llm = _get_llm()
    
    messages = [
        SystemMessage(content=EVENT_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = await llm.ainvoke(messages)
    analysis_text = response.content
    
    # 解析LLM响应
    analysis_result = _parse_analysis_response(analysis_text)
    
    logger.info(
        f"[动态调整-1] 事件分析完成: "
        f"impact={analysis_result.get('impact_level')}, "
        f"urgency={analysis_result.get('urgency')}, "
        f"action={analysis_result.get('recommended_action_type')}"
    )
    
    # 更新消息历史
    messages_update = state.get("messages", [])
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["analyze_dispatch_event"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["event_analysis"] = analysis_result
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[动态调整-1] 完成, 耗时{elapsed_ms}ms")
    
    return {
        "trace": trace,
        "current_phase": "analyze_event",
    }


def _build_event_context(event: DispatchEvent, state: TaskDispatchState) -> str:
    """构建事件分析上下文"""
    
    event_type_desc = {
        DispatchEventType.TASK_REJECTED.value: "任务被执行者拒绝",
        DispatchEventType.TASK_FAILED.value: "任务执行失败",
        DispatchEventType.TASK_TIMEOUT.value: "任务执行超时",
        DispatchEventType.RESOURCE_UNAVAILABLE.value: "资源不可用",
        DispatchEventType.NEW_URGENT_TASK.value: "新增紧急任务",
        DispatchEventType.PRIORITY_CHANGE.value: "任务优先级变更",
        DispatchEventType.RESOURCE_STATUS_CHANGE.value: "资源状态变化",
    }.get(event.get("event_type", ""), "未知事件")
    
    # 查找相关任务信息
    task_id = event.get("task_id")
    task_info = None
    if task_id:
        for assignment in state.get("current_assignments", []):
            if assignment.get("task_id") == task_id:
                task_info = assignment
                break
    
    # 查找相关执行者信息
    executor_id = event.get("executor_id")
    executor_info = None
    if executor_id:
        for executor in state.get("available_executors", []):
            if executor.get("executor_id") == executor_id:
                executor_info = executor
                break
    
    # 构建上下文文本
    context = f"""## 事件信息
事件类型: {event_type_desc}
事件ID: {event.get('event_id')}
发生时间: {event.get('occurred_at')}
事件原因: {event.get('reason', '未知')}
事件优先级: {event.get('priority', 'medium')}
事件详情: {event.get('details', {})}

## 相关任务
"""
    
    if task_info:
        context += f"""任务ID: {task_info.get('task_id')}
任务名称: {task_info.get('task_name')}
任务优先级: {task_info.get('task_priority')}
当前状态: {task_info.get('status')}
计划时间: {task_info.get('scheduled_start')} - {task_info.get('scheduled_end')}
"""
    else:
        context += "无关联任务信息\n"
    
    context += "\n## 相关执行者\n"
    
    if executor_info:
        context += f"""执行者ID: {executor_info.get('executor_id')}
执行者名称: {executor_info.get('executor_name')}
执行者类型: {executor_info.get('executor_type')}
当前状态: {executor_info.get('status')}
当前负载: {executor_info.get('current_load')}/{executor_info.get('max_load')}
"""
    else:
        context += "无关联执行者信息\n"
    
    # 添加当前分配概况
    assignments = state.get("current_assignments", [])
    context += f"\n## 当前分配概况\n"
    context += f"总任务数: {len(assignments)}\n"
    
    status_count: Dict[str, int] = {}
    for a in assignments:
        s = a.get("status", "unknown")
        status_count[s] = status_count.get(s, 0) + 1
    
    for status, count in status_count.items():
        context += f"- {status}: {count}个\n"
    
    return context


def _parse_analysis_response(response_text: str) -> Dict[str, Any]:
    """解析LLM分析响应"""
    import json
    
    # 尝试提取JSON
    try:
        # 查找JSON块
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 解析失败，返回默认结构
    logger.warning("[动态调整-1] LLM响应解析失败，使用默认分析结果")
    return {
        "event_summary": "事件分析结果解析失败",
        "root_cause": "unknown",
        "impact_level": "medium",
        "urgency": "soon",
        "affected_tasks": [],
        "potential_risks": ["分析不完整可能导致决策偏差"],
        "recommended_action_type": "escalate",
        "reasoning": response_text[:500] if response_text else "无响应",
    }



