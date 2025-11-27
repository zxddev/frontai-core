"""
TaskDispatchAgent主类

封装LangGraph流程，提供统一的任务分发接口。
支持两种运行模式：
- 初始分配：从EmergencyAI方案生成任务分配
- 动态调整：响应任务状态变化进行重新分配
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from langgraph.types import Command

from .state import (
    TaskDispatchState,
    create_initial_dispatch_state,
    create_dynamic_dispatch_state,
    DispatchEvent,
    DispatchEventType,
    TaskAssignment,
)
from .graph import get_task_dispatch_graph

logger = logging.getLogger(__name__)


class TaskDispatchAgent:
    """
    任务智能分发Agent
    
    基于LangGraph实现，支持：
    - Mode 1: 初始分配 - 将方案任务批量分配给执行者
    - Mode 2: 动态调整 - 响应任务失败/拒绝等事件进行重新分配
    - Human-in-the-loop: 重大决策暂停等待人工确认
    - 状态持久化: 支持服务重启后恢复
    
    Example:
        ```python
        agent = TaskDispatchAgent()
        
        # Mode 1: 初始分配
        result = await agent.initial_dispatch(
            event_id="evt-001",
            scheme_id="sch-001",
            scheme_tasks=[...],
            allocated_teams=[...],
        )
        
        # Mode 2: 动态调整
        result = await agent.handle_event(
            event_id="evt-001",
            event_type="task_rejected",
            task_id="EM06",
            reason="执行者设备故障",
        )
        ```
    """
    
    def __init__(self, use_checkpointer: bool = True) -> None:
        """
        初始化Agent
        
        Args:
            use_checkpointer: 是否启用状态持久化
        """
        self._graph = get_task_dispatch_graph(use_checkpointer=use_checkpointer)
        self._use_checkpointer = use_checkpointer
        logger.info("TaskDispatchAgent初始化完成")
    
    async def initial_dispatch(
        self,
        event_id: str,
        scheme_id: str,
        scheme_tasks: List[Dict[str, Any]],
        allocated_teams: List[Dict[str, Any]],
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行初始分配（Mode 1）
        
        将EmergencyAI生成的方案任务批量分配给执行者。
        
        Args:
            event_id: 应急事件ID
            scheme_id: 方案ID
            scheme_tasks: 方案任务列表（来自HTN分解）
            allocated_teams: 已分配的救援队伍（来自资源匹配）
            thread_id: 线程ID（用于状态持久化）
            
        Returns:
            分发结果，包含：
            - success: 是否成功
            - assignments: 任务分配列表
            - dispatch_orders: 调度指令列表
            - gantt_data: 甘特图数据
            - trace: 执行追踪
            - errors: 错误列表
        """
        logger.info(
            f"开始初始分配: event_id={event_id}, scheme_id={scheme_id}, "
            f"tasks={len(scheme_tasks)}, teams={len(allocated_teams)}"
        )
        start_time = time.time()
        
        # 创建初始状态
        initial_state = create_initial_dispatch_state(
            event_id=event_id,
            scheme_id=scheme_id,
            scheme_tasks=scheme_tasks,
            allocated_teams=allocated_teams,
        )
        
        # 配置
        config = {}
        if self._use_checkpointer:
            config["configurable"] = {
                "thread_id": thread_id or f"dispatch-{event_id}-{scheme_id}"
            }
        
        # 执行图
        try:
            final_state = await self._graph.ainvoke(initial_state, config)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            result = self._build_initial_dispatch_result(final_state, elapsed_ms)
            
            logger.info(
                f"初始分配完成: assignments={len(result.get('assignments', []))}, "
                f"orders={len(result.get('dispatch_orders', []))}, "
                f"耗时{elapsed_ms}ms"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"初始分配失败: {e}")
            return {
                "success": False,
                "assignments": [],
                "dispatch_orders": [],
                "gantt_data": [],
                "trace": {},
                "errors": [str(e)],
            }
    
    async def handle_event(
        self,
        event_id: str,
        event_type: str,
        task_id: Optional[str] = None,
        executor_id: Optional[str] = None,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
        current_assignments: Optional[List[TaskAssignment]] = None,
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理分发事件（Mode 2）
        
        响应任务状态变化事件，进行动态调整。
        
        Args:
            event_id: 应急事件ID
            event_type: 事件类型（task_rejected/task_failed/...）
            task_id: 关联任务ID
            executor_id: 关联执行者ID
            reason: 事件原因
            details: 事件详情
            current_assignments: 当前分配状态
            thread_id: 线程ID（用于状态恢复）
            
        Returns:
            处理结果，包含：
            - success: 是否成功
            - action_taken: 采取的行动
            - new_assignments: 更新后的分配
            - dispatch_orders: 新生成的调度指令
            - requires_human_approval: 是否需要人工确认（如果为True，结果不完整）
            - trace: 执行追踪
            - errors: 错误列表
        """
        logger.info(
            f"处理分发事件: event_id={event_id}, type={event_type}, "
            f"task_id={task_id}, executor_id={executor_id}"
        )
        start_time = time.time()
        
        # 构建事件
        dispatch_event: DispatchEvent = {
            "event_id": f"de-{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "task_id": task_id,
            "executor_id": executor_id,
            "reason": reason,
            "details": details or {},
            "occurred_at": datetime.utcnow().isoformat(),
            "priority": self._determine_event_priority(event_type, task_id, current_assignments),
        }
        
        # 创建动态调整状态
        initial_state = create_dynamic_dispatch_state(
            event_id=event_id,
            current_assignments=current_assignments or [],
            dispatch_event=dispatch_event,
        )
        
        # 配置
        config = {}
        if self._use_checkpointer:
            config["configurable"] = {
                "thread_id": thread_id or f"dispatch-{event_id}-dynamic"
            }
        
        # 执行图（使用astream支持interrupt）
        try:
            final_state = None
            interrupted = False
            interrupt_info = None
            
            async for event in self._graph.astream(initial_state, config, stream_mode="values"):
                final_state = event
                
            # 检查是否被interrupt暂停
            if self._use_checkpointer:
                state = await self._graph.aget_state(config)
                if state.next:  # 还有下一个节点，说明被暂停了
                    interrupted = True
                    # 从tasks中提取interrupt信息
                    for task in state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            interrupt_info = task.interrupts[0].value
                            break
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if interrupted:
                logger.info(f"事件处理暂停等待人工审核: thread_id={config.get('configurable', {}).get('thread_id')}")
                return {
                    "success": True,
                    "action_taken": final_state.get("proposed_action", {}).get("action_type") if final_state else None,
                    "new_assignments": [],
                    "dispatch_orders": [],
                    "requires_human_approval": True,
                    "interrupted": True,
                    "interrupt_info": interrupt_info,
                    "thread_id": config.get("configurable", {}).get("thread_id"),
                    "trace": final_state.get("trace", {}) if final_state else {},
                    "execution_time_ms": elapsed_ms,
                    "errors": [],
                }
            
            result = self._build_dynamic_dispatch_result(final_state, elapsed_ms)
            
            logger.info(
                f"事件处理完成: action={result.get('action_taken')}, "
                f"requires_human={result.get('requires_human_approval')}, "
                f"耗时{elapsed_ms}ms"
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"事件处理失败: {e}")
            return {
                "success": False,
                "action_taken": None,
                "new_assignments": [],
                "dispatch_orders": [],
                "requires_human_approval": True,
                "trace": {},
                "errors": [str(e)],
            }
    
    async def resume_with_human_decision(
        self,
        thread_id: str,
        decision: str,
        modified_action: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        人工决策后恢复执行
        
        在human-in-the-loop暂停后，提供人工决策并恢复执行。
        
        Args:
            thread_id: 线程ID
            decision: 人工决策（approve/reject/modify）
            modified_action: 如果decision为modify，提供修改后的行动
            
        Returns:
            恢复执行后的结果
        """
        logger.info(f"恢复执行: thread_id={thread_id}, decision={decision}")
        
        if not self._use_checkpointer:
            return {
                "success": False,
                "errors": ["未启用checkpointer，无法恢复执行"],
            }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # 构建恢复命令
        resume_value = {
            "decision": decision,
        }
        if modified_action:
            resume_value["modified_action"] = modified_action
        
        try:
            final_state = await self._graph.ainvoke(
                Command(resume=resume_value),
                config
            )
            
            return self._build_dynamic_dispatch_result(final_state, 0)
            
        except Exception as e:
            logger.exception(f"恢复执行失败: {e}")
            return {
                "success": False,
                "errors": [str(e)],
            }
    
    def _determine_event_priority(
        self,
        event_type: str,
        task_id: Optional[str],
        assignments: Optional[List[TaskAssignment]],
    ) -> str:
        """确定事件优先级"""
        
        # 基于事件类型的基础优先级
        type_priority = {
            DispatchEventType.TASK_FAILED.value: "high",
            DispatchEventType.TASK_REJECTED.value: "high",
            DispatchEventType.RESOURCE_UNAVAILABLE.value: "high",
            DispatchEventType.NEW_URGENT_TASK.value: "critical",
            DispatchEventType.TASK_TIMEOUT.value: "medium",
            DispatchEventType.PRIORITY_CHANGE.value: "medium",
            DispatchEventType.RESOURCE_STATUS_CHANGE.value: "low",
        }.get(event_type, "medium")
        
        # 如果关联任务是critical，提升事件优先级
        if task_id and assignments:
            for assignment in assignments:
                if assignment.get("task_id") == task_id:
                    if assignment.get("task_priority") == "critical":
                        return "critical"
                    break
        
        return type_priority
    
    def _build_initial_dispatch_result(
        self,
        state: TaskDispatchState,
        elapsed_ms: int
    ) -> Dict[str, Any]:
        """构建初始分配结果"""
        
        errors = state.get("errors", [])
        assignments = state.get("current_assignments", [])
        orders = state.get("dispatch_orders", [])
        trace = state.get("trace", {})
        
        return {
            "success": len(errors) == 0 and len(assignments) > 0,
            "assignments": assignments,
            "dispatch_orders": orders,
            "gantt_data": trace.get("gantt_data", []),
            "notifications_sent": state.get("notifications_sent", []),
            "trace": {
                "phases_executed": trace.get("phases_executed", []),
                "algorithms_used": trace.get("algorithms_used", []),
                "capability_summary": trace.get("capability_summary", {}),
                "executors_found": trace.get("executors_found", 0),
                "match_metrics": trace.get("match_metrics", {}),
                "schedule_metrics": trace.get("schedule_metrics", {}),
            },
            "errors": errors,
            "execution_time_ms": elapsed_ms,
        }
    
    def _build_dynamic_dispatch_result(
        self,
        state: TaskDispatchState,
        elapsed_ms: int
    ) -> Dict[str, Any]:
        """构建动态调整结果"""
        
        errors = state.get("errors", [])
        proposed_action = state.get("proposed_action", {})
        trace = state.get("trace", {})
        
        return {
            "success": len(errors) == 0,
            "action_taken": proposed_action.get("action_type") if proposed_action else None,
            "action_details": proposed_action,
            "new_assignments": state.get("current_assignments", []),
            "dispatch_orders": state.get("dispatch_orders", []),
            "notifications_sent": state.get("notifications_sent", []),
            "requires_human_approval": state.get("requires_human_approval", False),
            "human_decision": state.get("human_decision"),
            "trace": {
                "phases_executed": trace.get("phases_executed", []),
                "event_analysis": trace.get("event_analysis", {}),
                "decisions_made": trace.get("decisions_made", []),
                "action_result": trace.get("action_result", {}),
            },
            "errors": errors,
            "execution_time_ms": elapsed_ms,
        }


def get_task_dispatch_agent(use_checkpointer: bool = True) -> TaskDispatchAgent:
    """
    获取TaskDispatchAgent实例
    
    Args:
        use_checkpointer: 是否启用状态持久化
        
    Returns:
        TaskDispatchAgent实例
    """
    return TaskDispatchAgent(use_checkpointer=use_checkpointer)
