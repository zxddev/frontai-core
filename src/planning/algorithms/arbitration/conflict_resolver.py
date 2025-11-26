"""
资源冲突消解算法

业务逻辑:
=========
1. 冲突类型:
   - 独占冲突: 多任务需要同一唯一资源
   - 容量冲突: 资源总需求超过可用容量
   - 时间冲突: 资源使用时间窗重叠

2. 消解策略:
   - 优先级策略: 高优先级任务优先
   - 紧急度策略: 紧急任务优先
   - 成本策略: 最小化重新分配成本
   - 公平策略: 均衡分配

3. 消解方法:
   - 资源抢占: 从低优先级任务回收资源
   - 任务延迟: 推迟低优先级任务
   - 资源替代: 寻找替代资源
   - 任务分割: 拆分任务使用不同资源

算法实现:
=========
- 冲突检测: 构建资源-任务映射
- 冲突评分: 计算每个冲突的严重程度
- 消解排序: 按严重程度处理
- 方案生成: 对每个冲突生成消解方案
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """冲突类型"""
    EXCLUSIVE = "exclusive"     # 独占冲突
    CAPACITY = "capacity"       # 容量冲突
    TEMPORAL = "temporal"       # 时间冲突


class ResolutionStrategy(Enum):
    """消解策略"""
    PREEMPT = "preempt"         # 抢占
    DELAY = "delay"             # 延迟
    SUBSTITUTE = "substitute"   # 替代
    SPLIT = "split"             # 分割


@dataclass
class ResourceClaim:
    """资源请求"""
    task_id: str
    task_name: str
    resource_id: str
    quantity: int
    start_time: int
    end_time: int
    priority: int  # 1-5, 1最高
    is_preemptible: bool = True


@dataclass
class Conflict:
    """冲突"""
    id: str
    conflict_type: ConflictType
    resource_id: str
    claims: List[ResourceClaim]
    severity: float  # 严重程度 0-1


@dataclass
class Resolution:
    """消解方案"""
    conflict_id: str
    strategy: ResolutionStrategy
    winner_task: str
    affected_tasks: List[str]
    actions: List[Dict]
    cost: float


class ConflictResolver(AlgorithmBase):
    """
    资源冲突消解器
    
    使用示例:
    ```python
    resolver = ConflictResolver()
    result = resolver.run({
        "claims": [
            {
                "task_id": "TASK-001",
                "task_name": "生命探测",
                "resource_id": "RES-DETECTOR-001",
                "quantity": 1,
                "start_time": 0,
                "end_time": 120,
                "priority": 1,
                "is_preemptible": False
            },
            {
                "task_id": "TASK-002",
                "task_name": "结构评估",
                "resource_id": "RES-DETECTOR-001",
                "quantity": 1,
                "start_time": 60,
                "end_time": 180,
                "priority": 2,
                "is_preemptible": True
            }
        ],
        "resources": {
            "RES-DETECTOR-001": {"capacity": 1, "is_exclusive": True}
        },
        "strategy": "priority"
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "default_strategy": "priority",
            "allow_preemption": True,
            "delay_penalty": 1.0,
            "preemption_penalty": 2.0,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "claims" not in problem or not problem["claims"]:
            return False, "缺少 claims"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行冲突消解"""
        claims = self._parse_claims(problem["claims"])
        resources = problem.get("resources", {})
        strategy = problem.get("strategy", self.params["default_strategy"])
        
        # 1. 检测冲突
        conflicts = self._detect_conflicts(claims, resources)
        
        if not conflicts:
            return AlgorithmResult(
                status=AlgorithmStatus.SUCCESS,
                solution={"conflicts": [], "resolutions": [], "message": "无冲突"},
                metrics={"conflict_count": 0},
                trace={},
                time_ms=0
            )
        
        # 2. 按严重程度排序
        conflicts.sort(key=lambda c: c.severity, reverse=True)
        
        # 3. 逐个消解
        resolutions = []
        for conflict in conflicts:
            resolution = self._resolve_conflict(conflict, strategy, resources)
            if resolution:
                resolutions.append(resolution)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "conflicts": [{
                    "id": c.id,
                    "type": c.conflict_type.value,
                    "resource_id": c.resource_id,
                    "task_ids": [cl.task_id for cl in c.claims],
                    "severity": c.severity,
                } for c in conflicts],
                "resolutions": [{
                    "conflict_id": r.conflict_id,
                    "strategy": r.strategy.value,
                    "winner": r.winner_task,
                    "affected": r.affected_tasks,
                    "actions": r.actions,
                    "cost": r.cost,
                } for r in resolutions],
            },
            metrics={
                "conflict_count": len(conflicts),
                "resolution_count": len(resolutions),
                "total_cost": sum(r.cost for r in resolutions),
            },
            trace={
                "strategy": strategy,
            },
            time_ms=0
        )
    
    def _parse_claims(self, data: List[Dict]) -> List[ResourceClaim]:
        """解析资源请求"""
        return [ResourceClaim(
            task_id=d["task_id"],
            task_name=d.get("task_name", ""),
            resource_id=d["resource_id"],
            quantity=d.get("quantity", 1),
            start_time=d.get("start_time", 0),
            end_time=d.get("end_time", 999999),
            priority=d.get("priority", 3),
            is_preemptible=d.get("is_preemptible", True)
        ) for d in data]
    
    def _detect_conflicts(self, claims: List[ResourceClaim],
                          resources: Dict) -> List[Conflict]:
        """检测冲突"""
        conflicts = []
        conflict_id = 0
        
        # 按资源分组
        by_resource = {}
        for claim in claims:
            if claim.resource_id not in by_resource:
                by_resource[claim.resource_id] = []
            by_resource[claim.resource_id].append(claim)
        
        for res_id, res_claims in by_resource.items():
            if len(res_claims) <= 1:
                continue
            
            res_info = resources.get(res_id, {})
            capacity = res_info.get("capacity", 1)
            is_exclusive = res_info.get("is_exclusive", False)
            
            # 检测时间重叠
            for i, c1 in enumerate(res_claims):
                for c2 in res_claims[i+1:]:
                    # 时间窗重叠检测
                    if c1.start_time < c2.end_time and c2.start_time < c1.end_time:
                        # 判断冲突类型
                        if is_exclusive:
                            conflict_type = ConflictType.EXCLUSIVE
                            severity = 1.0
                        elif c1.quantity + c2.quantity > capacity:
                            conflict_type = ConflictType.CAPACITY
                            severity = (c1.quantity + c2.quantity - capacity) / capacity
                        else:
                            continue  # 无冲突
                        
                        conflict_id += 1
                        conflicts.append(Conflict(
                            id=f"CONFLICT-{conflict_id:03d}",
                            conflict_type=conflict_type,
                            resource_id=res_id,
                            claims=[c1, c2],
                            severity=min(1.0, severity)
                        ))
        
        return conflicts
    
    def _resolve_conflict(self, conflict: Conflict, strategy: str,
                          resources: Dict) -> Optional[Resolution]:
        """消解单个冲突"""
        claims = conflict.claims
        
        # 按策略确定优胜者
        if strategy == "priority":
            winner = min(claims, key=lambda c: c.priority)
        elif strategy == "urgency":
            winner = min(claims, key=lambda c: c.start_time)
        elif strategy == "fairness":
            # 选择已获得资源最少的任务
            winner = claims[0]  # 简化: 选第一个
        else:
            winner = min(claims, key=lambda c: c.priority)
        
        losers = [c for c in claims if c.task_id != winner.task_id]
        
        # 确定消解方案
        actions = []
        total_cost = 0
        
        for loser in losers:
            if not loser.is_preemptible:
                # 不可抢占，尝试延迟
                delay_amount = winner.end_time - loser.start_time
                actions.append({
                    "type": "delay",
                    "task_id": loser.task_id,
                    "delay_minutes": delay_amount,
                    "new_start_time": winner.end_time,
                })
                total_cost += delay_amount * self.params["delay_penalty"]
                resolution_strategy = ResolutionStrategy.DELAY
            else:
                # 可抢占
                if self.params["allow_preemption"]:
                    actions.append({
                        "type": "preempt",
                        "task_id": loser.task_id,
                        "preempted_by": winner.task_id,
                        "reschedule_after": winner.end_time,
                    })
                    total_cost += self.params["preemption_penalty"]
                    resolution_strategy = ResolutionStrategy.PREEMPT
                else:
                    # 延迟
                    delay_amount = winner.end_time - loser.start_time
                    actions.append({
                        "type": "delay",
                        "task_id": loser.task_id,
                        "delay_minutes": delay_amount,
                    })
                    total_cost += delay_amount * self.params["delay_penalty"]
                    resolution_strategy = ResolutionStrategy.DELAY
        
        return Resolution(
            conflict_id=conflict.id,
            strategy=resolution_strategy,
            winner_task=winner.task_id,
            affected_tasks=[l.task_id for l in losers],
            actions=actions,
            cost=total_cost
        )
    
    def find_substitute_resources(self, original_resource: str,
                                   required_capabilities: List[str],
                                   available_resources: Dict) -> List[str]:
        """
        寻找替代资源
        
        当原资源冲突时，寻找具有相同能力的替代资源
        """
        substitutes = []
        
        for res_id, res_info in available_resources.items():
            if res_id == original_resource:
                continue
            
            res_capabilities = res_info.get("capabilities", [])
            if all(cap in res_capabilities for cap in required_capabilities):
                substitutes.append(res_id)
        
        return substitutes
