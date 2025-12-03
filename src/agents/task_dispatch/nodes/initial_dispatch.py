"""
Mode 1: 初始分配节点

处理方案到执行者的批量分配流程：
1. 提取能力需求
2. 查询可用执行者
3. 能力匹配
4. 时间调度
5. 生成调度指令
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.planning.algorithms.matching import CapabilityMatcher
from src.planning.algorithms.scheduling import TaskScheduler
from src.agents.emergency_ai.utils.mt_library import get_meta_task

from ..state import (
    TaskDispatchState,
    TaskAssignment,
    ExecutorInfo,
    SchemeTaskInfo,
    AssignmentStatus,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Node 1: 提取能力需求
# ============================================================================

async def extract_capability_needs(state: TaskDispatchState) -> Dict[str, Any]:
    """
    从方案任务中提取能力需求
    
    遍历scheme_tasks，查询mt_library获取每个任务的required_capabilities。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[初始分配-1] 提取能力需求: event_id={state['event_id']}")
    start_time = time.time()
    
    scheme_tasks = state.get("scheme_tasks", [])
    if not scheme_tasks:
        logger.warning("[初始分配-1] 无方案任务")
        return {
            "errors": state.get("errors", []) + ["无方案任务"],
            "current_phase": "extract_needs",
        }
    
    # 遍历任务，补充能力需求信息
    enriched_tasks: List[SchemeTaskInfo] = []
    capability_summary: Dict[str, List[str]] = {}  # {capability: [task_ids]}
    
    for task in scheme_tasks:
        task_id = task.get("task_id", "")
        
        # 从Neo4j获取元任务详情
        meta_task = get_meta_task(task_id)
        required_caps: List[str] = meta_task.get("required_capabilities", [])
        duration_min: int = meta_task.get("duration_max", 60)
        
        enriched_task: SchemeTaskInfo = {
            "task_id": task_id,
            "task_name": task.get("task_name") or meta_task.get("name", ""),
            "phase": task.get("phase") or meta_task.get("phase", ""),
            "priority": task.get("priority", "medium"),
            "sequence": task.get("sequence", 0),
            "depends_on": task.get("depends_on", []),
            "required_capabilities": required_caps,
            "duration_min": duration_min,
            "golden_hour": task.get("golden_hour"),
        }
        enriched_tasks.append(enriched_task)
        
        # 统计能力需求
        for cap in required_caps:
            if cap not in capability_summary:
                capability_summary[cap] = []
            capability_summary[cap].append(task_id)
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["extract_capability_needs"]
    trace["capability_summary"] = {cap: len(tasks) for cap, tasks in capability_summary.items()}
    trace["total_capabilities_needed"] = len(capability_summary)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[初始分配-1] 完成: {len(enriched_tasks)}个任务, "
        f"{len(capability_summary)}种能力需求, 耗时{elapsed_ms}ms"
    )
    
    return {
        "scheme_tasks": enriched_tasks,
        "trace": trace,
        "current_phase": "extract_needs",
    }


# ============================================================================
# Node 2: 查询可用执行者
# ============================================================================

async def query_available_executors(state: TaskDispatchState) -> Dict[str, Any]:
    """
    查询可用的执行者（队伍成员、车辆、装备）
    
    基于allocated_teams中的队伍ID，查询其下属的可用执行者。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[初始分配-2] 查询可用执行者: event_id={state['event_id']}")
    start_time = time.time()
    
    allocated_teams = state.get("allocated_teams", [])
    if not allocated_teams:
        logger.warning("[初始分配-2] 无已分配队伍")
        return {
            "errors": state.get("errors", []) + ["无已分配队伍"],
            "current_phase": "query_executors",
        }
    
    executors: List[ExecutorInfo] = []
    errors: List[str] = list(state.get("errors", []))
    
    # 提取队伍ID列表（在try外部，供错误消息使用）
    team_ids = [team.get("team_id") or team.get("resource_id") for team in allocated_teams]
    team_ids = [tid for tid in team_ids if tid]
    
    if not team_ids:
        raise ValueError("无有效队伍ID，allocated_teams必须包含team_id或resource_id")
    
    async with AsyncSessionLocal() as session:
        try:
            
            # 查询队伍作为执行者（当前简化：每个队伍作为一个执行单元）
            query = text("""
                SELECT 
                    id,
                    name,
                    team_type,
                    COALESCE(properties->'capabilities', '[]'::jsonb) as capabilities,
                    ST_Y(base_location::geometry) as lat,
                    ST_X(base_location::geometry) as lng,
                    status,
                    total_personnel
                FROM operational_v2.rescue_teams_v2
                WHERE id = ANY(:team_ids)
                AND status IN ('available', 'standby')
            """)
            
            result = await session.execute(query, {"team_ids": team_ids})
            rows = result.fetchall()
            
            for row in rows:
                # 解析能力列表
                caps = row.capabilities if isinstance(row.capabilities, list) else []
                
                executor: ExecutorInfo = {
                    "executor_id": str(row.id),
                    "executor_name": row.name,
                    "executor_type": "team",
                    "capabilities": caps,
                    "current_load": 0,  # 初始分配时负载为0
                    "max_load": max(1, row.total_personnel // 5),  # 按人数估算最大并行任务数
                    "status": row.status,
                    "location": {"lat": row.lat or 0, "lng": row.lng or 0},
                    "eta_minutes": None,  # 稍后计算
                }
                executors.append(executor)
                logger.debug(f"  - 执行者: {row.name}, 能力: {caps}")
            
            # 查询车辆作为执行者（通过team_vehicles_v2关联）
            vehicle_query = text("""
                SELECT 
                    v.id,
                    v.name,
                    v.vehicle_type as type,
                    COALESCE(v.properties->'capabilities', '[]'::jsonb) as capabilities,
                    v.status
                FROM operational_v2.vehicles_v2 v
                JOIN operational_v2.team_vehicles_v2 tv ON tv.vehicle_id = v.id
                WHERE tv.team_id = ANY(:team_ids)
                AND v.status = 'available'
                AND tv.status = 'assigned'
            """)
            
            vehicle_result = await session.execute(vehicle_query, {"team_ids": team_ids})
            vehicle_rows = vehicle_result.fetchall()
            
            for row in vehicle_rows:
                caps = row.capabilities if isinstance(row.capabilities, list) else []
                
                executor: ExecutorInfo = {
                    "executor_id": str(row.id),
                    "executor_name": row.name,
                    "executor_type": "vehicle",
                    "capabilities": caps,
                    "current_load": 0,
                    "max_load": 1,  # 车辆一次只能执行一个任务
                    "status": row.status,
                    "location": {"lat": 0, "lng": 0},  # 车辆位置需要从其他表获取
                    "eta_minutes": None,
                }
                executors.append(executor)
            
            logger.info(f"[初始分配-2] 查询到 {len(executors)} 个执行者")
            
        except Exception as e:
            # 数据库查询失败，禁止降级，直接报错
            logger.error(f"[初始分配-2] 数据库查询失败: {e}")
            raise
    
    # 数据库必须有结果
    if not executors:
        raise ValueError(f"数据库中未找到有效执行者，team_ids: {team_ids}")
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["query_available_executors"]
    trace["db_calls"] = trace.get("db_calls", 0) + 2
    trace["executors_found"] = len(executors)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[初始分配-2] 完成: {len(executors)}个执行者, 耗时{elapsed_ms}ms")
    
    return {
        "available_executors": executors,
        "errors": errors,
        "trace": trace,
        "current_phase": "query_executors",
    }


# ============================================================================
# Node 3: 能力匹配
# ============================================================================

async def match_executors(state: TaskDispatchState) -> Dict[str, Any]:
    """
    将任务与执行者进行能力匹配
    
    使用CapabilityMatcher（OR-Tools CSP）进行约束满足求解。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[初始分配-3] 能力匹配: event_id={state['event_id']}")
    start_time = time.time()
    
    scheme_tasks = state.get("scheme_tasks", [])
    executors = state.get("available_executors", [])
    
    if not scheme_tasks or not executors:
        logger.warning("[初始分配-3] 任务或执行者为空")
        return {
            "errors": state.get("errors", []) + ["任务或执行者为空，无法匹配"],
            "current_phase": "match_executors",
        }
    
    # 构建能力需求列表
    capability_needs: List[Dict[str, Any]] = []
    for task in scheme_tasks:
        for cap in task.get("required_capabilities", []):
            need = {
                "id": f"{task['task_id']}-{cap}",
                "task_id": task["task_id"],
                "capability_id": cap,
                "min_level": 0.5,
                "importance": "required" if task.get("priority") in ["critical", "high"] else "preferred",
            }
            capability_needs.append(need)
    
    # 构建资源列表
    resources: List[Dict[str, Any]] = []
    for executor in executors:
        # 将能力列表转换为能力-熟练度映射
        cap_map = {cap: 0.8 for cap in executor.get("capabilities", [])}
        
        resource = {
            "id": executor["executor_id"],
            "name": executor["executor_name"],
            "capabilities": cap_map,
            "location": executor.get("location", {"lat": 0, "lng": 0}),
            "status": executor.get("status", "available"),
            "max_assignments": executor.get("max_load", 3),
        }
        resources.append(resource)
    
    # 调用CapabilityMatcher
    matcher = CapabilityMatcher()
    match_result = matcher.run({
        "capability_needs": capability_needs,
        "resources": resources,
        "constraints": {
            "max_distance_km": 100,
            "time_limit_sec": 30,
        }
    })
    
    # 解析匹配结果，构建初步分配
    assignments: List[TaskAssignment] = []
    task_executor_map: Dict[str, str] = {}  # {task_id: executor_id}
    
    if match_result.solution:
        for assignment in match_result.solution:
            task_id = assignment.get("task_id", "")
            executor_id = assignment.get("resource_id", "")
            
            # 记录任务-执行者映射（去重）
            if task_id and task_id not in task_executor_map:
                task_executor_map[task_id] = executor_id
    
    # 为每个任务创建分配记录
    now = datetime.utcnow().isoformat()
    for task in scheme_tasks:
        task_id = task["task_id"]
        executor_id = task_executor_map.get(task_id)
        
        # 查找执行者信息
        executor_info = None
        if executor_id:
            for ex in executors:
                if ex["executor_id"] == executor_id:
                    executor_info = ex
                    break
        
        # 如果没有匹配到执行者，选择负载最低的可用执行者
        if not executor_info and executors:
            available = [e for e in executors if e.get("current_load", 0) < e.get("max_load", 3)]
            if available:
                executor_info = min(available, key=lambda x: x.get("current_load", 0))
                executor_id = executor_info["executor_id"]
        
        if executor_info:
            assignment: TaskAssignment = {
                "assignment_id": str(uuid.uuid4()),
                "task_id": task_id,
                "task_name": task.get("task_name", ""),
                "task_priority": task.get("priority", "medium"),
                "executor_id": executor_id,
                "executor_name": executor_info.get("executor_name", ""),
                "executor_type": executor_info.get("executor_type", "team"),
                "status": AssignmentStatus.PENDING.value,
                "scheduled_start": None,
                "scheduled_end": None,
                "actual_start": None,
                "instructions": "",
                "created_at": now,
                "updated_at": now,
            }
            assignments.append(assignment)
            
            # 更新执行者负载
            executor_info["current_load"] = executor_info.get("current_load", 0) + 1
        else:
            logger.warning(f"[初始分配-3] 任务 {task_id} 无法分配执行者")
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["match_executors"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["CapabilityMatcher_CSP"]
    trace["match_metrics"] = match_result.metrics if match_result else {}
    trace["assignments_created"] = len(assignments)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[初始分配-3] 完成: {len(assignments)}个分配, "
        f"覆盖率={match_result.metrics.get('required_coverage', 0):.2%}, "
        f"耗时{elapsed_ms}ms"
    )
    
    return {
        "current_assignments": assignments,
        "trace": trace,
        "current_phase": "match_executors",
    }


# ============================================================================
# Node 4: 时间调度
# ============================================================================

async def schedule_tasks(state: TaskDispatchState) -> Dict[str, Any]:
    """
    为分配的任务生成时间调度
    
    使用TaskScheduler（优先级列表/关键路径调度）生成甘特图。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[初始分配-4] 时间调度: event_id={state['event_id']}")
    start_time = time.time()
    
    assignments = state.get("current_assignments", [])
    scheme_tasks = state.get("scheme_tasks", [])
    executors = state.get("available_executors", [])
    
    if not assignments:
        logger.warning("[初始分配-4] 无分配记录")
        return {
            "errors": state.get("errors", []) + ["无分配记录，无法调度"],
            "current_phase": "schedule_tasks",
        }
    
    # 构建任务信息映射
    task_info_map = {task["task_id"]: task for task in scheme_tasks}
    
    # 构建调度任务列表
    schedule_tasks_input: List[Dict[str, Any]] = []
    for assignment in assignments:
        task_id = assignment["task_id"]
        task_info = task_info_map.get(task_id, {})
        
        schedule_task = {
            "id": task_id,
            "name": assignment.get("task_name", ""),
            "duration_min": task_info.get("duration_min", 60),
            "priority": {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(
                assignment.get("task_priority", "medium"), 3
            ),
            "predecessors": task_info.get("depends_on", []),
            "required_resources": {assignment["executor_type"]: 1},
            "required_skills": task_info.get("required_capabilities", []),
        }
        schedule_tasks_input.append(schedule_task)
    
    # 构建资源列表
    schedule_resources: List[Dict[str, Any]] = []
    executor_type_count: Dict[str, int] = {}
    
    for executor in executors:
        etype = executor.get("executor_type", "team")
        executor_type_count[etype] = executor_type_count.get(etype, 0) + 1
        
        resource = {
            "id": executor["executor_id"],
            "name": executor["executor_name"],
            "type": etype,
            "skills": executor.get("capabilities", []),
            "capacity": executor.get("max_load", 1),
        }
        schedule_resources.append(resource)
    
    # 调用TaskScheduler
    scheduler = TaskScheduler()
    schedule_result = scheduler.run({
        "tasks": schedule_tasks_input,
        "resources": schedule_resources,
        "start_time": 0,
    })
    
    # 更新分配的调度时间
    if schedule_result.solution:
        schedule_map = {
            slot["task_id"]: slot 
            for slot in schedule_result.solution.get("schedule", [])
        }
        
        for assignment in assignments:
            slot = schedule_map.get(assignment["task_id"])
            if slot:
                assignment["scheduled_start"] = f"T+{slot['start_time']}min"
                assignment["scheduled_end"] = f"T+{slot['end_time']}min"
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["schedule_tasks"]
    trace["algorithms_used"] = trace.get("algorithms_used", []) + ["TaskScheduler_PriorityList"]
    trace["schedule_metrics"] = schedule_result.metrics if schedule_result else {}
    trace["gantt_data"] = schedule_result.solution.get("gantt_data", []) if schedule_result.solution else []
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"[初始分配-4] 完成: makespan={schedule_result.metrics.get('makespan_min', 0)}min, "
        f"耗时{elapsed_ms}ms"
    )
    
    return {
        "current_assignments": assignments,
        "trace": trace,
        "current_phase": "schedule_tasks",
    }


# ============================================================================
# Node 5: 生成调度指令
# ============================================================================

async def generate_dispatch_orders(state: TaskDispatchState) -> Dict[str, Any]:
    """
    生成最终的调度指令（dispatch_order）
    
    将分配记录转换为可执行的调度指令格式。
    
    Args:
        state: 当前状态
        
    Returns:
        状态更新字典
    """
    logger.info(f"[初始分配-5] 生成调度指令: event_id={state['event_id']}")
    start_time = time.time()
    
    assignments = state.get("current_assignments", [])
    scheme_tasks = state.get("scheme_tasks", [])
    
    if not assignments:
        logger.warning("[初始分配-5] 无分配记录")
        return {
            "errors": state.get("errors", []) + ["无分配记录"],
            "current_phase": "generate_orders",
        }
    
    # 构建任务信息映射
    task_info_map = {task["task_id"]: task for task in scheme_tasks}
    
    # 生成调度指令
    dispatch_orders: List[Dict[str, Any]] = []
    now = datetime.utcnow().isoformat()
    
    for assignment in assignments:
        task_id = assignment["task_id"]
        task_info = task_info_map.get(task_id, {})
        
        # 生成执行指令（简化版，可扩展为LLM生成）
        instructions = _generate_task_instructions(assignment, task_info)
        
        order = {
            "order_id": str(uuid.uuid4()),
            "assignment_id": assignment["assignment_id"],
            "task_id": task_id,
            "task_name": assignment.get("task_name", ""),
            "executor_id": assignment["executor_id"],
            "executor_name": assignment["executor_name"],
            "executor_type": assignment["executor_type"],
            "priority": assignment.get("task_priority", "medium"),
            "scheduled_start": assignment.get("scheduled_start"),
            "scheduled_end": assignment.get("scheduled_end"),
            "instructions": instructions,
            "status": "pending",
            "created_at": now,
            "event_id": state["event_id"],
            "scheme_id": state.get("scheme_id"),
        }
        dispatch_orders.append(order)
        
        # 更新分配状态
        assignment["status"] = AssignmentStatus.ASSIGNED.value
        assignment["instructions"] = instructions
        assignment["updated_at"] = now
    
    # 更新追踪信息
    trace = dict(state.get("trace", {}))
    trace["phases_executed"] = trace.get("phases_executed", []) + ["generate_dispatch_orders"]
    trace["orders_generated"] = len(dispatch_orders)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[初始分配-5] 完成: 生成{len(dispatch_orders)}个调度指令, 耗时{elapsed_ms}ms")
    
    return {
        "current_assignments": assignments,
        "dispatch_orders": dispatch_orders,
        "trace": trace,
        "current_phase": "generate_orders",
    }


def _generate_task_instructions(
    assignment: TaskAssignment, 
    task_info: Dict[str, Any]
) -> str:
    """
    生成任务执行指令
    
    Args:
        assignment: 分配记录
        task_info: 任务信息
        
    Returns:
        执行指令文本
    """
    task_name = assignment.get("task_name", "未知任务")
    executor_name = assignment.get("executor_name", "未知执行者")
    priority = assignment.get("task_priority", "medium")
    phase = task_info.get("phase", "execute")
    golden_hour = task_info.get("golden_hour")
    
    # 优先级描述
    priority_desc = {
        "critical": "紧急",
        "high": "高优先级",
        "medium": "正常",
        "low": "低优先级",
    }.get(priority, "正常")
    
    # 构建指令
    instructions = f"【{priority_desc}任务】{task_name}\n"
    instructions += f"执行单位: {executor_name}\n"
    instructions += f"任务阶段: {phase}\n"
    
    if golden_hour:
        instructions += f"黄金救援时间: {golden_hour}分钟内\n"
    
    if assignment.get("scheduled_start"):
        instructions += f"计划开始: {assignment['scheduled_start']}\n"
    
    # 根据任务类型添加具体指令
    task_id = assignment.get("task_id", "")
    if task_id.startswith("EM06"):  # 生命探测
        instructions += "执行要求: 使用生命探测仪对倒塌区域进行全面扫描，标记疑似生命体征位置。"
    elif task_id.startswith("EM10"):  # 被困人员救援
        instructions += "执行要求: 在确保安全的前提下，组织力量对被困人员实施救援，注意记录救出人员情况。"
    elif task_id.startswith("EM14"):  # 伤员急救
        instructions += "执行要求: 对伤员进行分诊和初步救治，按伤情轻重缓急分类转运。"
    else:
        instructions += "执行要求: 按照标准作业程序执行任务，及时上报进展和异常情况。"
    
    return instructions
