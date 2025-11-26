"""
任务调度Agent状态定义

使用TypedDict定义LangGraph状态，所有字段强类型注解
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class LocationState(TypedDict):
    """位置坐标"""
    latitude: float
    longitude: float


class TaskDependencyState(TypedDict):
    """任务依赖关系"""
    task_id: str
    depends_on: List[str]
    dependency_type: str  # finish_to_start / start_to_start


class DecomposedTaskState(TypedDict):
    """拆解后的任务"""
    task_id: str
    task_name: str
    task_type: str  # search_rescue / fire_fighting / medical / logistics / evacuation
    priority: int  # 1最高
    duration_min: int
    location: LocationState
    predecessors: List[str]
    required_resources: Dict[str, int]  # {"rescue_team": 2, "detector": 1}
    required_skills: List[str]
    deadline_min: Optional[int]
    source_allocation_id: Optional[str]  # 来源资源分配ID


class ScheduledTaskState(TypedDict):
    """已调度的任务"""
    task_id: str
    task_name: str
    start_time_min: int  # 相对开始时间(分钟)
    end_time_min: int
    assigned_resource_ids: List[str]
    priority: int
    is_critical_path: bool


class RouteStopState(TypedDict):
    """路线停靠点"""
    stop_id: str
    stop_name: str
    location: LocationState
    arrival_time_min: int
    departure_time_min: int
    service_duration_min: int
    task_id: Optional[str]


class PlannedRouteState(TypedDict):
    """规划的路线"""
    vehicle_id: str
    vehicle_name: str
    depot_location: LocationState
    stops: List[RouteStopState]
    total_distance_km: float
    total_time_min: int
    route_geometry: Optional[List[LocationState]]  # 路线轨迹点


class ExecutorAssignmentState(TypedDict):
    """执行者分配"""
    task_id: str
    task_name: str
    executor_id: str
    executor_name: str
    executor_type: str  # team / vehicle / individual
    role: str  # leader / member / support
    route_id: Optional[str]
    eta_min: int
    contact_info: Optional[Dict[str, str]]


class DispatchOrderState(TypedDict):
    """调度单"""
    order_id: str
    task_id: str
    task_name: str
    executor_id: str
    executor_name: str
    priority: int
    scheduled_start_time: str  # ISO格式时间
    scheduled_end_time: str
    location: LocationState
    instructions: List[str]
    required_equipment: List[str]
    route_summary: Optional[str]
    status: str  # pending / dispatched / acknowledged


class GanttItemState(TypedDict):
    """甘特图项"""
    task_id: str
    task_name: str
    resource_id: str
    resource_name: str
    start_min: int
    end_min: int
    color: str


class TaskDispatchState(TypedDict):
    """
    任务调度Agent完整状态
    
    包含输入、中间结果、输出和追踪信息
    """
    # ========== 输入 ==========
    event_id: str
    scenario_id: str
    scheme_id: str
    
    # 方案数据（来自SchemeGenerationAgent）
    scheme_data: Dict[str, Any]
    
    # 可用资源（队伍、车辆）
    available_resources: List[Dict[str, Any]]
    
    # 调度配置
    dispatch_config: Dict[str, Any]
    
    # ========== 任务拆解结果 ==========
    decomposed_tasks: List[DecomposedTaskState]
    task_dependencies: List[TaskDependencyState]
    
    # ========== 调度结果 ==========
    scheduled_tasks: List[ScheduledTaskState]
    critical_path_tasks: List[str]  # 关键路径上的任务ID
    makespan_min: int  # 总工期(分钟)
    
    # ========== 路径规划结果 ==========
    planned_routes: List[PlannedRouteState]
    total_travel_distance_km: float
    total_travel_time_min: int
    
    # ========== 执行者分配结果 ==========
    executor_assignments: List[ExecutorAssignmentState]
    
    # ========== 输出 ==========
    dispatch_orders: List[DispatchOrderState]
    gantt_data: List[GanttItemState]
    
    # ========== 追踪 ==========
    trace: Dict[str, Any]
    errors: List[str]
    
    # ========== 时间戳 ==========
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
