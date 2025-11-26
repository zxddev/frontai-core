"""
任务调度Agent

封装LangGraph执行，提供同步和异步接口
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import BaseAgent
from .state import TaskDispatchState
from .graph import build_task_dispatch_graph

logger = logging.getLogger(__name__)

# 默认调度配置
DEFAULT_DISPATCH_CONFIG: Dict[str, Any] = {
    "strategy": "critical_path",
    "vehicle_capacity": 10,
    "max_distance_km": 100,
    "max_time_min": 480,
    "speed_kmh": 40,
}


class TaskDispatchAgent(BaseAgent[TaskDispatchState]):
    """
    任务调度Agent
    
    基于SchemeGenerationAgent输出的方案，执行任务调度：
    1. 方案拆解 - 将方案转换为具体任务
    2. 任务调度 - 依赖排序和时间安排
    3. 路径规划 - 多车辆VRP
    4. 执行者分配 - 为任务指定执行者
    5. 调度单生成 - 输出调度指令
    
    使用示例:
    ```python
    agent = TaskDispatchAgent()
    result = agent.run(
        event_id="event-001",
        scenario_id="scenario-001",
        scheme_id="scheme-001",
        scheme_data=scheme_generation_result,
    )
    ```
    """
    
    def __init__(self) -> None:
        """初始化任务调度Agent"""
        super().__init__(name="TaskDispatchAgent")
    
    def build_graph(self) -> CompiledStateGraph:
        """构建LangGraph"""
        return build_task_dispatch_graph()
    
    def prepare_input(self, **kwargs: Any) -> TaskDispatchState:
        """
        准备输入状态
        
        Args:
            event_id: 事件ID
            scenario_id: 想定ID
            scheme_id: 方案ID
            scheme_data: 方案数据（来自SchemeGenerationAgent）
            available_resources: 可用资源列表
            dispatch_config: 调度配置
            
        Returns:
            初始化的状态
        """
        # 处理ID
        event_id = kwargs.get("event_id", "")
        if isinstance(event_id, UUID):
            event_id = str(event_id)
        
        scenario_id = kwargs.get("scenario_id", "")
        if isinstance(scenario_id, UUID):
            scenario_id = str(scenario_id)
        
        scheme_id = kwargs.get("scheme_id", "")
        if isinstance(scheme_id, UUID):
            scheme_id = str(scheme_id)
        
        # 合并调度配置
        dispatch_config = {**DEFAULT_DISPATCH_CONFIG, **kwargs.get("dispatch_config", {})}
        
        state: TaskDispatchState = {
            # 输入
            "event_id": event_id,
            "scenario_id": scenario_id,
            "scheme_id": scheme_id,
            "scheme_data": kwargs.get("scheme_data", {}),
            "available_resources": kwargs.get("available_resources", []),
            "dispatch_config": dispatch_config,
            
            # 任务拆解结果
            "decomposed_tasks": [],
            "task_dependencies": [],
            
            # 调度结果
            "scheduled_tasks": [],
            "critical_path_tasks": [],
            "makespan_min": 0,
            
            # 路径规划结果
            "planned_routes": [],
            "total_travel_distance_km": 0.0,
            "total_travel_time_min": 0,
            
            # 执行者分配结果
            "executor_assignments": [],
            
            # 输出
            "dispatch_orders": [],
            "gantt_data": [],
            
            # 追踪
            "trace": {"algorithms_used": ["TaskScheduler", "VehicleRoutingPlanner"], "nodes_executed": []},
            "errors": [],
            
            # 时间戳
            "started_at": None,
            "completed_at": None,
        }
        
        return state
    
    def process_output(self, state: TaskDispatchState) -> Dict[str, Any]:
        """
        处理输出结果
        
        Args:
            state: 最终状态
            
        Returns:
            格式化的API响应
        """
        dispatch_orders = state.get("dispatch_orders", [])
        gantt_data = state.get("gantt_data", [])
        errors = state.get("errors", [])
        
        return {
            "success": len(errors) == 0 or len(dispatch_orders) > 0,
            "event_id": state.get("event_id", ""),
            "scenario_id": state.get("scenario_id", ""),
            "scheme_id": state.get("scheme_id", ""),
            
            # 调度结果摘要
            "summary": {
                "task_count": len(state.get("decomposed_tasks", [])),
                "scheduled_count": len(state.get("scheduled_tasks", [])),
                "order_count": len(dispatch_orders),
                "route_count": len(state.get("planned_routes", [])),
                "makespan_min": state.get("makespan_min", 0),
                "total_distance_km": state.get("total_travel_distance_km", 0),
                "total_travel_time_min": state.get("total_travel_time_min", 0),
                "critical_path_tasks": state.get("critical_path_tasks", []),
            },
            
            # 详细结果
            "dispatch_orders": dispatch_orders,
            "scheduled_tasks": state.get("scheduled_tasks", []),
            "planned_routes": state.get("planned_routes", []),
            "executor_assignments": state.get("executor_assignments", []),
            "gantt_data": gantt_data,
            
            # 追踪
            "trace": state.get("trace", {}),
            "errors": errors,
            
            # 时间戳
            "started_at": state.get("started_at").isoformat() + "Z" if state.get("started_at") else None,
            "completed_at": state.get("completed_at").isoformat() + "Z" if state.get("completed_at") else None,
        }
    
    async def run_with_db(
        self,
        db: AsyncSession,
        event_id: str,
        scenario_id: str,
        scheme_id: str,
        scheme_data: Dict[str, Any],
        dispatch_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        带数据库集成的运行方法
        
        可从数据库查询可用资源
        
        Args:
            db: 数据库session
            event_id: 事件ID
            scenario_id: 场景ID
            scheme_id: 方案ID
            scheme_data: 方案数据
            dispatch_config: 调度配置
            
        Returns:
            调度结果
        """
        logger.info(f"开始任务调度（数据库模式）: scheme_id={scheme_id}")
        
        # 查询可用资源
        available_resources = await self._fetch_available_resources(db, scheme_data)
        logger.info(f"查询到 {len(available_resources)} 个可用资源")
        
        # 执行LangGraph
        result = self.run(
            event_id=event_id,
            scenario_id=scenario_id,
            scheme_id=scheme_id,
            scheme_data=scheme_data,
            available_resources=available_resources,
            dispatch_config=dispatch_config or {},
        )
        
        return result
    
    async def _fetch_available_resources(
        self,
        db: AsyncSession,
        scheme_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """从数据库查询可用资源"""
        # 从方案数据中提取已分配的资源
        allocations = scheme_data.get("resource_allocations", [])
        
        resources = []
        for alloc in allocations:
            resources.append({
                "id": alloc.get("resource_id", ""),
                "name": alloc.get("resource_name", ""),
                "type": alloc.get("resource_type", "rescue_team"),
                "capabilities": alloc.get("capabilities", []),
                "location": alloc.get("location"),
            })
        
        return resources


# 模块级单例
_task_dispatch_agent: TaskDispatchAgent | None = None


def get_task_dispatch_agent() -> TaskDispatchAgent:
    """获取TaskDispatchAgent单例"""
    global _task_dispatch_agent
    if _task_dispatch_agent is None:
        _task_dispatch_agent = TaskDispatchAgent()
    return _task_dispatch_agent
