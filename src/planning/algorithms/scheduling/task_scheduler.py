"""
任务调度算法

业务逻辑:
=========
1. 调度目标:
   - 最小化总完成时间 (makespan)
   - 最大化资源利用率
   - 满足任务优先级和截止时间

2. 约束条件:
   - 任务依赖关系
   - 资源容量限制
   - 时间窗约束
   - 技能匹配约束

3. 调度策略:
   - 列表调度: 按优先级排序后贪心分配
   - 关键路径法: 识别关键路径优先调度
   - 遗传算法: 搜索近优解

算法实现:
=========
- 拓扑排序处理依赖
- 优先级队列管理就绪任务
- 资源池管理可用资源
- 甘特图生成调度方案
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import heapq

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class ScheduleTask:
    """调度任务"""
    id: str
    name: str
    duration_min: int
    priority: int  # 1最高
    predecessors: List[str] = field(default_factory=list)
    required_resources: Dict[str, int] = field(default_factory=dict)
    required_skills: List[str] = field(default_factory=list)
    deadline: Optional[int] = None
    
    status: TaskStatus = TaskStatus.PENDING
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    assigned_resources: List[str] = field(default_factory=list)


@dataclass
class ScheduleResource:
    """调度资源"""
    id: str
    name: str
    resource_type: str
    skills: List[str] = field(default_factory=list)
    capacity: int = 1
    
    current_load: int = 0
    available_at: int = 0
    assigned_tasks: List[str] = field(default_factory=list)


@dataclass
class ScheduleSlot:
    """调度时隙"""
    task_id: str
    task_name: str
    resource_ids: List[str]
    start_time: int
    end_time: int
    priority: int


class TaskScheduler(AlgorithmBase):
    """
    任务调度器
    
    使用示例:
    ```python
    scheduler = TaskScheduler()
    result = scheduler.run({
        "tasks": [
            {
                "id": "T1",
                "name": "生命探测",
                "duration_min": 60,
                "priority": 1,
                "predecessors": [],
                "required_resources": {"detector": 1},
                "required_skills": ["life_detection"]
            },
            {
                "id": "T2",
                "name": "废墟搜救",
                "duration_min": 120,
                "priority": 1,
                "predecessors": ["T1"],
                "required_resources": {"rescue_team": 2},
                "required_skills": ["rescue_operation"]
            }
        ],
        "resources": [
            {
                "id": "R1",
                "name": "生命探测仪A",
                "type": "detector",
                "skills": ["life_detection"],
                "capacity": 1
            },
            {
                "id": "R2",
                "name": "重型救援队",
                "type": "rescue_team",
                "skills": ["rescue_operation", "heavy_equipment"],
                "capacity": 2
            }
        ],
        "start_time": 0
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "scheduling_strategy": "priority_list",  # priority_list / critical_path
            "allow_preemption": False,
            "max_parallel_tasks": 10,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "tasks" not in problem or not problem["tasks"]:
            return False, "缺少 tasks"
        if "resources" not in problem or not problem["resources"]:
            return False, "缺少 resources"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行任务调度"""
        tasks = self._parse_tasks(problem["tasks"])
        resources = self._parse_resources(problem["resources"])
        start_time = problem.get("start_time", 0)
        
        # 检查依赖是否有环
        if self._has_cycle(tasks):
            return AlgorithmResult(
                status=AlgorithmStatus.INFEASIBLE,
                solution=None,
                metrics={},
                trace={"error": "任务依赖存在环"},
                time_ms=0,
                message="任务依赖关系存在循环"
            )
        
        # 执行调度
        strategy = self.params["scheduling_strategy"]
        if strategy == "critical_path":
            schedule = self._schedule_critical_path(tasks, resources, start_time)
        else:
            schedule = self._schedule_priority_list(tasks, resources, start_time)
        
        # 计算统计
        if schedule:
            makespan = max(s.end_time for s in schedule) - start_time
            scheduled_count = len(schedule)
        else:
            makespan = 0
            scheduled_count = 0
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS if scheduled_count == len(tasks) else AlgorithmStatus.PARTIAL,
            solution={
                "schedule": [{
                    "task_id": s.task_id,
                    "task_name": s.task_name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "resource_ids": s.resource_ids,
                    "priority": s.priority,
                } for s in schedule],
                "gantt_data": self._generate_gantt_data(schedule, resources),
            },
            metrics={
                "makespan_min": makespan,
                "scheduled_tasks": scheduled_count,
                "total_tasks": len(tasks),
                "resource_utilization": self._compute_utilization(schedule, resources, makespan),
            },
            trace={
                "strategy": strategy,
            },
            time_ms=0
        )
    
    def _parse_tasks(self, data: List[Dict]) -> Dict[str, ScheduleTask]:
        """解析任务"""
        tasks = {}
        for d in data:
            tasks[d["id"]] = ScheduleTask(
                id=d["id"],
                name=d.get("name", ""),
                duration_min=d.get("duration_min", 0),
                priority=d.get("priority", 3),
                predecessors=d.get("predecessors", []),
                required_resources=d.get("required_resources", {}),
                required_skills=d.get("required_skills", []),
                deadline=d.get("deadline")
            )
        return tasks
    
    def _parse_resources(self, data: List[Dict]) -> Dict[str, ScheduleResource]:
        """解析资源"""
        resources = {}
        for d in data:
            resources[d["id"]] = ScheduleResource(
                id=d["id"],
                name=d.get("name", ""),
                resource_type=d.get("type", ""),
                skills=d.get("skills", []),
                capacity=d.get("capacity", 1)
            )
        return resources
    
    def _has_cycle(self, tasks: Dict[str, ScheduleTask]) -> bool:
        """检测依赖是否有环"""
        visited = set()
        rec_stack = set()
        
        def dfs(task_id):
            visited.add(task_id)
            rec_stack.add(task_id)
            
            task = tasks.get(task_id)
            if task:
                for pred in task.predecessors:
                    if pred not in visited:
                        if dfs(pred):
                            return True
                    elif pred in rec_stack:
                        return True
            
            rec_stack.remove(task_id)
            return False
        
        for task_id in tasks:
            if task_id not in visited:
                if dfs(task_id):
                    return True
        
        return False
    
    def _schedule_priority_list(self, tasks: Dict[str, ScheduleTask],
                                 resources: Dict[str, ScheduleResource],
                                 start_time: int) -> List[ScheduleSlot]:
        """优先级列表调度"""
        schedule = []
        current_time = start_time
        completed = set()
        resource_available_at = {r_id: start_time for r_id in resources}
        
        # 优先级队列: (priority, task_id)
        ready_queue = []
        
        # 初始化就绪队列
        for task_id, task in tasks.items():
            if not task.predecessors:
                heapq.heappush(ready_queue, (task.priority, task_id))
        
        max_iterations = len(tasks) * 10
        iterations = 0
        
        while ready_queue and iterations < max_iterations:
            iterations += 1
            priority, task_id = heapq.heappop(ready_queue)
            task = tasks[task_id]
            
            # 找可用资源
            assigned, earliest_start = self._find_resources(
                task, resources, resource_available_at
            )
            
            if assigned is None:
                # 无法分配资源，跳过
                continue
            
            # 创建调度时隙
            task_start = max(earliest_start, current_time)
            task_end = task_start + task.duration_min
            
            slot = ScheduleSlot(
                task_id=task_id,
                task_name=task.name,
                resource_ids=assigned,
                start_time=task_start,
                end_time=task_end,
                priority=task.priority
            )
            schedule.append(slot)
            completed.add(task_id)
            
            # 更新资源可用时间
            for r_id in assigned:
                resource_available_at[r_id] = task_end
            
            # 检查新就绪的任务
            for other_id, other_task in tasks.items():
                if other_id in completed:
                    continue
                if other_id in [t for _, t in ready_queue]:
                    continue
                
                # 检查前置任务是否都完成
                if all(p in completed for p in other_task.predecessors):
                    heapq.heappush(ready_queue, (other_task.priority, other_id))
        
        return schedule
    
    def _schedule_critical_path(self, tasks: Dict[str, ScheduleTask],
                                 resources: Dict[str, ScheduleResource],
                                 start_time: int) -> List[ScheduleSlot]:
        """关键路径调度"""
        # 计算关键路径
        earliest_start = {}
        latest_finish = {}
        
        # 拓扑排序
        topo_order = self._topological_sort(tasks)
        
        # 正向传播: 计算最早开始时间
        for task_id in topo_order:
            task = tasks[task_id]
            es = start_time
            for pred in task.predecessors:
                pred_finish = earliest_start.get(pred, start_time) + tasks[pred].duration_min
                es = max(es, pred_finish)
            earliest_start[task_id] = es
        
        # 反向传播: 计算最晚完成时间
        makespan = max(earliest_start[t] + tasks[t].duration_min for t in tasks)
        
        for task_id in reversed(topo_order):
            task = tasks[task_id]
            successors = [t for t, tk in tasks.items() if task_id in tk.predecessors]
            
            if not successors:
                latest_finish[task_id] = makespan
            else:
                lf = min(latest_finish[s] - tasks[s].duration_min for s in successors)
                latest_finish[task_id] = lf
        
        # 计算松弛度
        slack = {}
        for task_id in tasks:
            task = tasks[task_id]
            slack[task_id] = latest_finish[task_id] - (earliest_start[task_id] + task.duration_min)
        
        # 按松弛度排序 (关键任务优先)
        sorted_tasks = sorted(tasks.keys(), key=lambda t: (slack[t], tasks[t].priority))
        
        # 调度
        schedule = []
        resource_available_at = {r_id: start_time for r_id in resources}
        
        for task_id in sorted_tasks:
            task = tasks[task_id]
            
            assigned, _ = self._find_resources(task, resources, resource_available_at)
            
            if assigned is None:
                continue
            
            task_start = earliest_start[task_id]
            task_end = task_start + task.duration_min
            
            slot = ScheduleSlot(
                task_id=task_id,
                task_name=task.name,
                resource_ids=assigned,
                start_time=task_start,
                end_time=task_end,
                priority=task.priority
            )
            schedule.append(slot)
            
            for r_id in assigned:
                resource_available_at[r_id] = max(resource_available_at[r_id], task_end)
        
        return schedule
    
    def _topological_sort(self, tasks: Dict[str, ScheduleTask]) -> List[str]:
        """拓扑排序"""
        in_degree = {t: len(tasks[t].predecessors) for t in tasks}
        queue = [t for t, d in in_degree.items() if d == 0]
        result = []
        
        while queue:
            task_id = queue.pop(0)
            result.append(task_id)
            
            for other_id, other_task in tasks.items():
                if task_id in other_task.predecessors:
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)
        
        return result
    
    def _find_resources(self, task: ScheduleTask,
                        resources: Dict[str, ScheduleResource],
                        resource_available_at: Dict[str, int]) -> Tuple[Optional[List[str]], int]:
        """为任务寻找可用资源"""
        assigned = []
        earliest_start = 0
        
        for res_type, needed in task.required_resources.items():
            # 找该类型的资源
            candidates = [
                r_id for r_id, r in resources.items()
                if r.resource_type == res_type
            ]
            
            # 检查技能
            if task.required_skills:
                candidates = [
                    r_id for r_id in candidates
                    if all(skill in resources[r_id].skills for skill in task.required_skills)
                ]
            
            # 按可用时间排序
            candidates.sort(key=lambda r: resource_available_at.get(r, 0))
            
            if len(candidates) < needed:
                return None, 0
            
            for r_id in candidates[:needed]:
                assigned.append(r_id)
                earliest_start = max(earliest_start, resource_available_at.get(r_id, 0))
        
        return assigned, earliest_start
    
    def _generate_gantt_data(self, schedule: List[ScheduleSlot],
                              resources: Dict[str, ScheduleResource]) -> List[Dict]:
        """生成甘特图数据"""
        gantt = []
        
        for slot in schedule:
            for r_id in slot.resource_ids:
                gantt.append({
                    "resource_id": r_id,
                    "resource_name": resources[r_id].name if r_id in resources else r_id,
                    "task_id": slot.task_id,
                    "task_name": slot.task_name,
                    "start": slot.start_time,
                    "end": slot.end_time,
                })
        
        return gantt
    
    def _compute_utilization(self, schedule: List[ScheduleSlot],
                              resources: Dict[str, ScheduleResource],
                              makespan: int) -> float:
        """计算资源利用率"""
        if makespan <= 0:
            return 0
        
        total_work = 0
        total_capacity = len(resources) * makespan
        
        for slot in schedule:
            duration = slot.end_time - slot.start_time
            total_work += duration * len(slot.resource_ids)
        
        return round(total_work / total_capacity, 4) if total_capacity > 0 else 0
