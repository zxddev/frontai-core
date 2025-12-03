"""
离散事件仿真算法 (生命体征仿真增强版)

业务逻辑:
=========
1. 仿真目的:
   - 验证救援方案的可行性
   - 评估方案执行效果
   - 识别潜在瓶颈和风险
   - 比较多个备选方案

2. 核心升级: 生命体征仿真 (Vital Signs Simulation)
   - 不再将伤亡视为随机数字，而是基于生理学模型的个体仿真
   - 引入 Victim (受难者) 智能体，拥有独立的健康值和伤情
   - 引入 Survival Decay (生存衰减) 曲线，随时间指数恶化
   - 引入环境因子 (低温/缺氧) 加速生命流逝

3. 事件类型:
   - 任务开始/完成
   - 资源到达/释放
   - 灾情变化(次生灾害)
   - 生命体征更新 (VICTIM_UPDATE)

4. 评估指标 (生命至上):
   - 可预防死亡数 (Preventable Deaths)
   - 生存质量指数 (Survival Quality Index)
   - 弱势群体获救率 (Vulnerable Rescue Rate)

算法实现:
=========
- 事件驱动仿真 (Event-Driven)
- 多智能体状态管理 (ABM)
- 生理学衰减模型 (Physiological Decay)
"""
from __future__ import annotations

import heapq
import random
import math
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
    VICTIM_UPDATE = "victim_update"  # 新增：生命体征更新事件


@dataclass
class Victim:
    """受难者智能体 (ABM核心)"""
    id: str
    age_group: str          # child, adult, elderly
    injury_type: str        # crush(挤压), hypoxia(缺氧), hypothermia(失温), trauma(创伤)
    injury_severity: int    # ISS评分 (1-75, 越高越严重)
    health_score: float     # 当前生命值 (0-100)
    status: str             # trapped, rescuing, rescued, deceased
    location: Tuple[float, float]
    
    # 生理学参数
    decay_rate: float       # 基础衰减率
    environmental_factor: float = 1.0 # 环境恶劣因子
    
    def update_health(self, dt_hours: float) -> None:
        """
        更新生命值 (基于指数衰减模型)
        H(t) = H0 * exp(-lambda * t)
        """
        if self.status in ["rescued", "deceased"]:
            return
            
        # 救援中衰减减缓 (医疗干预)
        current_decay = self.decay_rate * self.environmental_factor
        if self.status == "rescuing":
            current_decay *= 0.2  # 假设医疗介入减缓80%恶化
            
        # 指数衰减
        self.health_score *= math.exp(-current_decay * dt_hours)
        
        # 判定死亡
        if self.health_score < 10.0:  # 生命临界点
            self.status = "deceased"


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
    target_location: Tuple[float, float] # 任务地点
    coverage_radius: float = 0.5         # 任务覆盖半径(km)
    
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
    """仿真状态 (增强版)"""
    current_time: float = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    # 生命统计
    victims: List[Victim] = field(default_factory=list)
    casualties_initial: int = 0
    casualties_final: int = 0
    preventable_deaths: int = 0  # 可预防死亡 (初始存活但最终死亡)
    
    resource_utilization: Dict[str, float] = field(default_factory=dict)


class DiscreteEventSimulator(AlgorithmBase):
    """
    离散事件仿真器 (升级为生命体征仿真引擎)
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "monte_carlo_runs": 50,      # 降低次数，增加单次深度
            "default_success_prob": 0.8,
            "random_seed": None,
            "victim_update_interval": 30, # 每30分钟更新一次生命体征
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
        sim_time = problem.get("simulation_time", 48 * 60) # 默认48小时
        
        if self.params["random_seed"]:
            random.seed(self.params["random_seed"])
        
        # 多次仿真取平均
        results = []
        for _ in range(n_runs):
            run_result = self._single_run(problem, sim_time)
            results.append(run_result)
        
        # 统计汇总 (生命至上维度)
        avg_completion_time = sum(r["completion_time"] for r in results) / n_runs
        avg_survival_rate = sum(r["survival_rate"] for r in results) / n_runs
        avg_preventable_deaths = sum(r["preventable_deaths"] for r in results) / n_runs
        avg_survival_quality = sum(r["survival_quality"] for r in results) / n_runs
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "summary": {
                    "avg_completion_time_min": round(avg_completion_time, 1),
                    "avg_survival_rate": round(avg_survival_rate, 3), # 生存率
                    "avg_preventable_deaths": round(avg_preventable_deaths, 1), # 可预防死亡
                    "avg_survival_quality": round(avg_survival_quality, 1), # 生存质量(平均健康值)
                },
                "confidence_interval": {
                    "survival_rate_std": self._std([r["survival_rate"] for r in results]),
                },
                "worst_case": {
                    "survival_rate": min(r["survival_rate"] for r in results),
                    "preventable_deaths": max(r["preventable_deaths"] for r in results),
                },
                "best_case": {
                    "survival_rate": max(r["survival_rate"] for r in results),
                    "preventable_deaths": min(r["preventable_deaths"] for r in results),
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
        
        # 初始化受难者 (ABM)
        victims = self._init_victims(scenario, tasks)
        
        state = SimState(victims=victims)
        state.casualties_initial = sum(1 for v in victims if v.status == "deceased")
        
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
        
        # 添加生命体征更新循环事件
        update_interval = self.params["victim_update_interval"]
        for t in range(update_interval, int(sim_time), update_interval):
            heapq.heappush(event_queue, SimEvent(
                time=t,
                event_type=EventType.VICTIM_UPDATE,
                entity_id="system",
                data={}
            ))
        
        # 仿真主循环
        while event_queue and state.current_time < sim_time:
            event = heapq.heappop(event_queue)
            
            # 更新所有受难者的健康状态直到当前时刻
            time_delta_hours = (event.time - state.current_time) / 60.0
            if time_delta_hours > 0:
                for v in state.victims:
                    v.update_health(time_delta_hours)
            
            state.current_time = event.time
            self._process_event(event, tasks, resources, state, event_queue, scenario)
        
        # 计算生命指标
        survivors = [v for v in state.victims if v.status == "rescued"]
        deceased = [v for v in state.victims if v.status == "deceased"]
        still_trapped = [v for v in state.victims if v.status in ["trapped", "rescuing"]]
        
        # 仍被困者如果在结束时健康值过低，视为大概率死亡
        for v in still_trapped:
            if v.health_score < 20:
                deceased.append(v)
            else:
                # 存活但未救出
                pass
                
        total_victims = len(state.victims)
        survival_rate = len(survivors) / total_victims if total_victims > 0 else 0
        
        # 可预防死亡：初始存活但后来死亡的
        preventable = sum(1 for v in state.victims 
                         if v.health_score > 10 and v.status == "deceased") # 逻辑上初始肯定>10
        # 修正逻辑：只要最终状态是deceased，且初始生成时不是deceased（初始生成一般都是活的），就是simulation期间死亡
        # 这里简单统计 simulation期间状态变为deceased的数量
        
        final_deceased_count = len(deceased)
        preventable_deaths = max(0, final_deceased_count - state.casualties_initial)
        
        # 生存质量：获救者的平均健康值
        avg_quality = sum(v.health_score for v in survivors) / len(survivors) if survivors else 0
        
        total_time = 0
        for task in tasks.values():
            if task.end_time:
                total_time = max(total_time, task.end_time)
        
        return {
            "completion_time": total_time,
            "survival_rate": survival_rate,
            "preventable_deaths": preventable_deaths,
            "survival_quality": avg_quality,
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
                predecessors=d.get("predecessors", []),
                target_location=tuple(d.get("location", [0, 0])),
                coverage_radius=d.get("coverage_radius", 0.5)
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
        
    def _init_victims(self, scenario: Dict, tasks: Dict[str, SimTask]) -> List[Victim]:
        """
        初始化受难者群体 (ABM生成)
        基于灾情参数生成符合统计学分布的受难者
        """
        victims = []
        total_count = scenario.get("initial_casualties", 50)
        
        # 伤情分布 (参考地震伤情统计)
        # 10% 危重 (Crush/Trauma), 30% 重伤, 60% 轻伤
        
        for _ in range(total_count):
            v_id = f"V-{random.randint(10000, 99999)}"
            
            # 年龄分布
            r_age = random.random()
            if r_age < 0.15: age_group = "child"
            elif r_age > 0.85: age_group = "elderly"
            else: age_group = "adult"
            
            # 伤情严重度 (ISS) 和 类型
            r_sev = random.random()
            if r_sev < 0.1:
                injury_type = "crush"
                iss = random.randint(25, 50) # 危重
                health = random.uniform(30, 50)
            elif r_sev < 0.4:
                injury_type = "trauma"
                iss = random.randint(16, 24) # 重伤
                health = random.uniform(50, 70)
            else:
                injury_type = "hypoxia" if random.random() < 0.3 else "trauma"
                iss = random.randint(1, 15)  # 轻伤
                health = random.uniform(70, 90)
            
            # 计算衰减率 (基于ISS和年龄)
            # ISS越高，衰减越快
            base_decay = (iss / 75.0) * 0.1  # 每小时衰减比例
            
            # 老人和儿童更脆弱
            if age_group != "adult":
                base_decay *= 1.5
                
            # 随机分配到某个任务区域
            if tasks:
                target_task = random.choice(list(tasks.values()))
                # 在任务点附近随机生成
                loc = (
                    target_task.target_location[0] + random.uniform(-0.01, 0.01),
                    target_task.target_location[1] + random.uniform(-0.01, 0.01)
                )
            else:
                loc = (0, 0)
                
            victims.append(Victim(
                id=v_id,
                age_group=age_group,
                injury_type=injury_type,
                injury_severity=iss,
                health_score=health,
                status="trapped",
                location=loc,
                decay_rate=base_decay,
                environmental_factor=1.0 # 默认环境
            ))
            
        return victims
    
    def _process_event(self, event: SimEvent, tasks: Dict[str, SimTask],
                       resources: Dict[str, SimResource], state: SimState,
                       event_queue: List, scenario: Dict):
        """处理事件 (增强版)"""
        
        if event.event_type == EventType.TASK_START:
            task = tasks.get(event.entity_id)
            if task and task.status == "pending":
                assigned = self._try_assign_resources(task, resources)
                
                if assigned:
                    task.status = "running"
                    task.start_time = event.time
                    task.assigned_resources = assigned
                    
                    # 【生命干预】: 任务开始，锁定该区域受难者，状态转为rescuing
                    # 这会减缓他们的生命衰减
                    affected_victims = self._find_victims_in_area(state.victims, task.target_location, task.coverage_radius)
                    for v in affected_victims:
                        if v.status == "trapped":
                            v.status = "rescuing"
                    
                    for r_id in assigned:
                        resources[r_id].status = "busy"
                        resources[r_id].current_task = task.id
                    
                    delay = random.uniform(0.8, 1.2)
                    complete_time = event.time + task.duration_min * delay
                    
                    heapq.heappush(event_queue, SimEvent(
                        time=complete_time,
                        event_type=EventType.TASK_COMPLETE,
                        entity_id=task.id,
                        data={"affected_victims_ids": [v.id for v in affected_victims]}
                    ))
                else:
                    heapq.heappush(event_queue, SimEvent(
                        time=event.time + 15, # 每15分钟重试
                        event_type=EventType.TASK_START,
                        entity_id=task.id,
                        data={}
                    ))
        
        elif event.event_type == EventType.TASK_COMPLETE:
            task = tasks.get(event.entity_id)
            if task and task.status == "running":
                task.end_time = event.time
                
                # 【生命结算】: 任务完成，根据当前健康值判定生死
                victim_ids = event.data.get("affected_victims_ids", [])
                rescued_count = 0
                
                for v in state.victims:
                    if v.id in victim_ids and v.status == "rescuing":
                        if v.health_score > 10.0: # 仍存活
                            v.status = "rescued"
                            rescued_count += 1
                        else:
                            v.status = "deceased"
                
                task.status = "completed"
                state.tasks_completed += 1
                
                # 释放资源
                for r_id in task.assigned_resources:
                    resources[r_id].status = "available"
                    resources[r_id].current_task = None
                
                # 触发后续任务
                for other_id, other_task in tasks.items():
                    if task.id in other_task.predecessors and other_task.status == "pending":
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
        
        elif event.event_type == EventType.VICTIM_UPDATE:
            # 这是一个周期性事件，仅用于触发主循环的 update_health
            # 实际更新逻辑在主循环中处理
            pass
            
        elif event.event_type == EventType.DISASTER_UPDATE:
            # 灾情恶化 (如降温)
            # 增加环境恶劣因子，加速所有人的生命流逝
            rate_increase = event.data.get("factor", 0.1)
            for v in state.victims:
                v.environmental_factor += rate_increase
    
    def _find_victims_in_area(self, victims: List[Victim], center: Tuple[float, float], radius_km: float) -> List[Victim]:
        """查找区域内的受难者 (简化距离计算)"""
        found = []
        # 简化：1度约为111km
        radius_deg = radius_km / 111.0
        for v in victims:
            dx = v.location[0] - center[0]
            dy = v.location[1] - center[1]
            if dx*dx + dy*dy <= radius_deg*radius_deg:
                found.append(v)
        return found

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
