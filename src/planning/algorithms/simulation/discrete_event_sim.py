"""
离散事件仿真算法

业务逻辑:
=========
1. 仿真目的:
   - 验证救援方案的可行性
   - 评估方案执行效果
   - 识别潜在瓶颈和风险
   - 比较多个备选方案

2. 事件类型:
   - 任务开始/完成
   - 资源到达/释放
   - 灾情变化(次生灾害)
   - 外部干扰(道路中断)

3. 评估指标:
   - 任务完成时间
   - 资源利用率
   - 救援成功率
   - 伤亡人数变化

算法实现:
=========
- 事件驱动仿真
- 优先队列管理事件
- 状态机管理任务/资源状态
- 蒙特卡洛采样处理不确定性
"""
from __future__ import annotations

import heapq
import random
import logging
from typing import Any, Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    TASK_START = "task_start"
    TASK_COMPLETE = "task_complete"
    RESOURCE_ARRIVE = "resource_arrive"
    RESOURCE_RELEASE = "resource_release"
    DISASTER_UPDATE = "disaster_update"
    ROAD_BLOCKED = "road_blocked"
    CASUALTY_UPDATE = "casualty_update"


@dataclass(order=True)
class SimEvent:
    """仿真事件"""
    time: float
    event_type: EventType = field(compare=False)
    entity_id: str = field(compare=False)
    data: Dict = field(default_factory=dict, compare=False)


@dataclass
class SimTask:
    """仿真任务"""
    id: str
    name: str
    duration_min: int
    success_prob: float
    required_resources: Dict[str, int]
    predecessors: List[str]
    
    status: str = "pending"  # pending/running/completed/failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    assigned_resources: List[str] = field(default_factory=list)


@dataclass
class SimResource:
    """仿真资源"""
    id: str
    name: str
    resource_type: str
    travel_speed_kmh: float = 40
    
    status: str = "available"  # available/busy/traveling
    current_task: Optional[str] = None
    location: Tuple[float, float] = (0, 0)


@dataclass
class SimState:
    """仿真状态"""
    current_time: float = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    casualties_saved: int = 0
    casualties_lost: int = 0
    resource_utilization: Dict[str, float] = field(default_factory=dict)


class DiscreteEventSimulator(AlgorithmBase):
    """
    离散事件仿真器
    
    使用示例:
    ```python
    simulator = DiscreteEventSimulator()
    result = simulator.run({
        "tasks": [
            {
                "id": "T1",
                "name": "生命探测",
                "duration_min": 60,
                "success_prob": 0.9,
                "required_resources": {"detector": 1},
                "predecessors": [],
                "potential_casualties": 10
            },
            {
                "id": "T2",
                "name": "废墟搜救",
                "duration_min": 120,
                "success_prob": 0.7,
                "required_resources": {"rescue_team": 2},
                "predecessors": ["T1"],
                "potential_casualties": 10
            }
        ],
        "resources": [
            {"id": "R1", "name": "探测仪", "type": "detector", "location": [31.2, 121.4]},
            {"id": "R2", "name": "救援队A", "type": "rescue_team", "location": [31.2, 121.4]},
            {"id": "R3", "name": "救援队B", "type": "rescue_team", "location": [31.2, 121.4]}
        ],
        "scenario": {
            "initial_casualties": 50,
            "casualty_rate_per_hour": 2,
            "road_block_prob": 0.1
        },
        "simulation_time": 480,
        "monte_carlo_runs": 100
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "monte_carlo_runs": 100,
            "default_success_prob": 0.8,
            "random_seed": None,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "tasks" not in problem or not problem["tasks"]:
            return False, "缺少 tasks"
        if "resources" not in problem or not problem["resources"]:
            return False, "缺少 resources"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行仿真"""
        n_runs = problem.get("monte_carlo_runs", self.params["monte_carlo_runs"])
        sim_time = problem.get("simulation_time", 480)
        
        if self.params["random_seed"]:
            random.seed(self.params["random_seed"])
        
        # 多次仿真取平均
        results = []
        for _ in range(n_runs):
            run_result = self._single_run(problem, sim_time)
            results.append(run_result)
        
        # 统计汇总
        avg_completion_time = sum(r["completion_time"] for r in results) / n_runs
        avg_success_rate = sum(r["success_rate"] for r in results) / n_runs
        avg_casualties_saved = sum(r["casualties_saved"] for r in results) / n_runs
        avg_utilization = sum(r["resource_utilization"] for r in results) / n_runs
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "summary": {
                    "avg_completion_time_min": round(avg_completion_time, 1),
                    "avg_success_rate": round(avg_success_rate, 3),
                    "avg_casualties_saved": round(avg_casualties_saved, 1),
                    "avg_resource_utilization": round(avg_utilization, 3),
                },
                "confidence_interval": {
                    "completion_time_std": self._std([r["completion_time"] for r in results]),
                    "success_rate_std": self._std([r["success_rate"] for r in results]),
                },
                "worst_case": {
                    "completion_time": max(r["completion_time"] for r in results),
                    "success_rate": min(r["success_rate"] for r in results),
                },
                "best_case": {
                    "completion_time": min(r["completion_time"] for r in results),
                    "success_rate": max(r["success_rate"] for r in results),
                },
            },
            metrics={
                "monte_carlo_runs": n_runs,
                "simulation_time": sim_time,
            },
            trace={},
            time_ms=0
        )
    
    def _single_run(self, problem: Dict[str, Any], sim_time: float) -> Dict:
        """单次仿真运行"""
        # 初始化
        tasks = self._init_tasks(problem["tasks"])
        resources = self._init_resources(problem["resources"])
        scenario = problem.get("scenario", {})
        
        state = SimState()
        event_queue = []
        
        # 初始事件: 启动无前置的任务
        for task_id, task in tasks.items():
            if not task.predecessors:
                heapq.heappush(event_queue, SimEvent(
                    time=0,
                    event_type=EventType.TASK_START,
                    entity_id=task_id,
                    data={"task": task}
                ))
        
        # 添加灾情恶化事件
        casualty_rate = scenario.get("casualty_rate_per_hour", 0)
        if casualty_rate > 0:
            for t in range(60, int(sim_time), 60):
                heapq.heappush(event_queue, SimEvent(
                    time=t,
                    event_type=EventType.CASUALTY_UPDATE,
                    entity_id="scenario",
                    data={"rate": casualty_rate}
                ))
        
        # 仿真主循环
        while event_queue and state.current_time < sim_time:
            event = heapq.heappop(event_queue)
            state.current_time = event.time
            
            self._process_event(event, tasks, resources, state, event_queue, scenario)
        
        # 计算结果
        completed_tasks = sum(1 for t in tasks.values() if t.status == "completed")
        total_tasks = len(tasks)
        
        total_time = 0
        busy_time = {r_id: 0 for r_id in resources}
        
        for task in tasks.values():
            if task.start_time is not None and task.end_time is not None:
                duration = task.end_time - task.start_time
                total_time = max(total_time, task.end_time)
                for r_id in task.assigned_resources:
                    busy_time[r_id] = busy_time.get(r_id, 0) + duration
        
        utilization = sum(busy_time.values()) / (len(resources) * max(total_time, 1)) if resources else 0
        
        return {
            "completion_time": total_time,
            "success_rate": completed_tasks / total_tasks if total_tasks > 0 else 0,
            "casualties_saved": state.casualties_saved,
            "resource_utilization": utilization,
        }
    
    def _init_tasks(self, data: List[Dict]) -> Dict[str, SimTask]:
        """初始化任务"""
        return {
            d["id"]: SimTask(
                id=d["id"],
                name=d.get("name", ""),
                duration_min=d.get("duration_min", 0),
                success_prob=d.get("success_prob", self.params["default_success_prob"]),
                required_resources=d.get("required_resources", {}),
                predecessors=d.get("predecessors", [])
            )
            for d in data
        }
    
    def _init_resources(self, data: List[Dict]) -> Dict[str, SimResource]:
        """初始化资源"""
        return {
            d["id"]: SimResource(
                id=d["id"],
                name=d.get("name", ""),
                resource_type=d.get("type", ""),
                travel_speed_kmh=d.get("speed_kmh", 40),
                location=tuple(d.get("location", [0, 0]))
            )
            for d in data
        }
    
    def _process_event(self, event: SimEvent, tasks: Dict[str, SimTask],
                       resources: Dict[str, SimResource], state: SimState,
                       event_queue: List, scenario: Dict):
        """处理事件"""
        
        if event.event_type == EventType.TASK_START:
            task = tasks.get(event.entity_id)
            if task and task.status == "pending":
                # 尝试分配资源
                assigned = self._try_assign_resources(task, resources)
                
                if assigned:
                    task.status = "running"
                    task.start_time = event.time
                    task.assigned_resources = assigned
                    
                    for r_id in assigned:
                        resources[r_id].status = "busy"
                        resources[r_id].current_task = task.id
                    
                    # 添加完成事件 (考虑随机延迟)
                    delay = random.uniform(0.8, 1.2)
                    complete_time = event.time + task.duration_min * delay
                    
                    heapq.heappush(event_queue, SimEvent(
                        time=complete_time,
                        event_type=EventType.TASK_COMPLETE,
                        entity_id=task.id,
                        data={}
                    ))
                else:
                    # 资源不足，稍后重试
                    heapq.heappush(event_queue, SimEvent(
                        time=event.time + 5,
                        event_type=EventType.TASK_START,
                        entity_id=task.id,
                        data={}
                    ))
        
        elif event.event_type == EventType.TASK_COMPLETE:
            task = tasks.get(event.entity_id)
            if task and task.status == "running":
                task.end_time = event.time
                
                # 判断成功/失败
                if random.random() < task.success_prob:
                    task.status = "completed"
                    state.tasks_completed += 1
                    state.casualties_saved += random.randint(1, 5)
                else:
                    task.status = "failed"
                    state.tasks_failed += 1
                
                # 释放资源
                for r_id in task.assigned_resources:
                    resources[r_id].status = "available"
                    resources[r_id].current_task = None
                
                # 触发后续任务
                for other_id, other_task in tasks.items():
                    if task.id in other_task.predecessors and other_task.status == "pending":
                        # 检查所有前置是否完成
                        all_done = all(
                            tasks[p].status in ["completed", "failed"]
                            for p in other_task.predecessors
                        )
                        if all_done:
                            heapq.heappush(event_queue, SimEvent(
                                time=event.time,
                                event_type=EventType.TASK_START,
                                entity_id=other_id,
                                data={}
                            ))
        
        elif event.event_type == EventType.CASUALTY_UPDATE:
            # 灾情恶化
            state.casualties_lost += int(event.data.get("rate", 1))
    
    def _try_assign_resources(self, task: SimTask,
                              resources: Dict[str, SimResource]) -> Optional[List[str]]:
        """尝试为任务分配资源"""
        assigned = []
        
        for res_type, needed in task.required_resources.items():
            available = [
                r_id for r_id, r in resources.items()
                if r.resource_type == res_type and r.status == "available"
            ]
            
            if len(available) < needed:
                return None
            
            assigned.extend(available[:needed])
        
        return assigned
    
    def _std(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) <= 1:
            return 0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return round(variance ** 0.5, 3)
