"""
Mode 2: 行动决策节点

使用LLM决定具体的分发行动，选择最佳的重新分配方案。
"""
from __future__ import annotations

import os
import logging
import time
import uuid
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from ..state import (
    TaskDispatchState,
    DispatchAction,
    DispatchActionType,
    ExecutorInfo,
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


# 行动决策系统提示词
ACTION_DECISION_SYSTEM_PROMPT = """你是应急救援任务调度系统的行动决策专家。

基于事件分析结果，你需要决定具体的调度行动：
1. reassign（重新分配）: 将任务分配给其他执行者
2. retry（重试）: 让原执行者重试
3. escalate（上报）: 上报给人工处理
4. preempt（抢占）: 抢占其他任务的资源
5. wait（等待）: 暂时等待，观察后续变化
6. cancel（取消）: 取消该任务

决策时请考虑：
1. 可用执行者的能力是否匹配任务需求
2. 执行者当前的负载情况
3. 任务的紧急程度和黄金救援时间
4. 重新分配的时间成本
5. 对其他任务的影响

请用JSON格式输出决策结果：
{
    "action_type": "reassign/retry/escalate/preempt/wait/cancel",
    "task_id": "任务ID",
    "old_executor_id": "原执行者ID（如适用）",
    "new_executor_id": "新执行者ID（如适用）",
    "reasoning": "决策理由",
    "confidence": 0.0-1.0,
    "requires_human_approval": true/false,
    "estimated_impact": {
        "time_delay_min": 预计延迟分钟数,
        "affected_tasks_count": 受影响任务数,
        "risk_level": "high/medium/low"
    }
}"""


async def decide_dispatch_action(state: TaskDispatchState) -> Dict[str, Any]:
    """
    决定分发行动
    
    基于事件分析结果，使用LLM决定具体的调度行动。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[动态调整-2] 行动决策: event_id={state['event_id']}")
    start_time = time.time()
    
    current_event = state.get("current_event")
    event_analysis = state.get("trace", {}).get("event_analysis", {})
    
    if not current_event:
        logger.warning("[动态调整-2] 无当前事件")
        return {
            "errors": state.get("errors", []) + ["无当前事件"],
            "current_phase": "decide_action",
        }
    
    # 构建决策上下文
    context = _build_decision_context(current_event, event_analysis, state)
    
    # 调用LLM决策（禁止降级，失败即报错）
    llm = _get_llm()
    
    messages = [
        SystemMessage(content=ACTION_DECISION_SYSTEM_PROMPT),
        HumanMessage(content=context),
    ]
    
    response = await llm.ainvoke(messages)
    decision_text = response.content
    
    # 解析LLM响应
    decision_result = _parse_decision_response(decision_text)
    
    logger.info(
        f"[动态调整-2] 决策完成: "
        f"action={decision_result.get('action_type')}, "
        f"confidence={decision_result.get('confidence')}, "
        f"requires_human={decision_result.get('requires_human_approval')}"
    )
    
    # 构建DispatchAction
    proposed_action: DispatchAction = {
        "action_type": decision_result.get("action_type", DispatchActionType.ESCALATE.value),
        "task_id": decision_result.get("task_id", current_event.get("task_id", "")),
        "old_executor_id": decision_result.get("old_executor_id"),
        "new_executor_id": decision_result.get("new_executor_id"),
        "reasoning": decision_result.get("reasoning", ""),
        "confidence": decision_result.get("confidence", 0.5),
        "estimated_impact": decision_result.get("estimated_impact", {}),
    }
    
    # 判断是否需要人工确认
    requires_human = _should_require_human_approval(proposed_action, current_event, state)
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["decide_dispatch_action"]
    trace["llm_calls"] = trace.get("llm_calls", 0) + 1
    trace["decisions_made"] = trace.get("decisions_made", []) + [{
        "event_id": current_event.get("event_id"),
        "action": proposed_action["action_type"],
        "reasoning": proposed_action["reasoning"],
        "confidence": proposed_action["confidence"],
    }]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[动态调整-2] 完成: action={proposed_action['action_type']}, "
        f"requires_human={requires_human}, 耗时{elapsed_ms}ms"
    )
    
    return {
        "proposed_action": proposed_action,
        "requires_human_approval": requires_human,
        "trace": trace,
        "current_phase": "decide_action",
    }


def _build_decision_context(
    event: Dict[str, Any],
    analysis: Dict[str, Any],
    state: TaskDispatchState
) -> str:
    """构建决策上下文"""
    
    task_id = event.get("task_id")
    
    # 查找任务信息
    task_info = None
    for assignment in state.get("current_assignments", []):
        if assignment.get("task_id") == task_id:
            task_info = assignment
            break
    
    # 获取可用执行者
    available_executors = _get_available_executors_for_task(task_info, state)
    
    context = f"""## 事件分析结果
事件摘要: {analysis.get('event_summary', '未知')}
根本原因: {analysis.get('root_cause', '未知')}
影响级别: {analysis.get('impact_level', 'medium')}
紧急程度: {analysis.get('urgency', 'soon')}
建议行动类型: {analysis.get('recommended_action_type', 'unknown')}
分析推理: {analysis.get('reasoning', '')}

## 当前任务信息
"""
    
    if task_info:
        context += f"""任务ID: {task_info.get('task_id')}
任务名称: {task_info.get('task_name')}
任务优先级: {task_info.get('task_priority')}
当前执行者: {task_info.get('executor_name')} (ID: {task_info.get('executor_id')})
当前状态: {task_info.get('status')}
"""
    else:
        context += "无任务信息\n"
    
    context += f"\n## 可用替代执行者 ({len(available_executors)}个)\n"
    
    for i, executor in enumerate(available_executors[:5], 1):  # 最多显示5个
        context += f"""{i}. {executor.get('executor_name')}
   - ID: {executor.get('executor_id')}
   - 类型: {executor.get('executor_type')}
   - 能力: {', '.join(executor.get('capabilities', [])[:5])}
   - 负载: {executor.get('current_load')}/{executor.get('max_load')}
   - 状态: {executor.get('status')}
"""
    
    if not available_executors:
        context += "无可用替代执行者\n"
    
    # 添加约束条件
    context += "\n## 约束条件\n"
    context += "- 关键任务(critical)必须优先处理\n"
    context += "- 执行者负载不能超过最大值\n"
    context += "- 需要考虑任务依赖关系\n"
    
    return context


def _get_available_executors_for_task(
    task_info: Optional[Dict[str, Any]],
    state: TaskDispatchState
) -> List[ExecutorInfo]:
    """获取任务可用的替代执行者"""
    
    all_executors = state.get("available_executors", [])
    current_executor_id = task_info.get("executor_id") if task_info else None
    
    available: List[ExecutorInfo] = []
    
    for executor in all_executors:
        # 排除当前执行者
        if executor.get("executor_id") == current_executor_id:
            continue
        
        # 检查状态
        if executor.get("status") != "available":
            continue
        
        # 检查负载
        if executor.get("current_load", 0) >= executor.get("max_load", 1):
            continue
        
        available.append(executor)
    
    # 按负载排序（负载低的优先）
    available.sort(key=lambda x: x.get("current_load", 0))
    
    return available


def _parse_decision_response(response_text: str) -> Dict[str, Any]:
    """解析LLM决策响应"""
    import json
    
    # 尝试提取JSON
    try:
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = response_text[start:end]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    
    # 解析失败，返回默认结构
    logger.warning("[动态调整-2] LLM响应解析失败，使用默认决策结果")
    return {
        "action_type": DispatchActionType.ESCALATE.value,
        "task_id": "",
        "reasoning": "LLM响应解析失败，建议人工处理",
        "confidence": 0.3,
        "requires_human_approval": True,
        "estimated_impact": {
            "time_delay_min": 0,
            "affected_tasks_count": 1,
            "risk_level": "medium",
        },
    }


def _should_require_human_approval(
    action: DispatchAction,
    event: Dict[str, Any],
    state: TaskDispatchState
) -> bool:
    """判断是否需要人工确认"""
    
    # 规则1: 低置信度决策需要人工确认
    if action.get("confidence", 0) < 0.6:
        return True
    
    # 规则2: 关键任务的重新分配需要人工确认
    task_id = action.get("task_id")
    for assignment in state.get("current_assignments", []):
        if assignment.get("task_id") == task_id:
            if assignment.get("task_priority") == "critical":
                return True
            break
    
    # 规则3: 上报类型行动需要人工处理
    if action.get("action_type") == DispatchActionType.ESCALATE.value:
        return True
    
    # 规则4: 抢占类型行动需要人工确认
    if action.get("action_type") == DispatchActionType.PREEMPT.value:
        return True
    
    # 规则5: 高风险影响需要人工确认
    impact = action.get("estimated_impact", {})
    if impact.get("risk_level") == "high":
        return True
    
    return False
