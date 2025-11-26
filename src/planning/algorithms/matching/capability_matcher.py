"""
能力-资源CSP匹配算法

业务逻辑:
=========
1. 能力需求提取:
   - 从任务列表提取所需能力
   - 每个能力有优先级和数量要求

2. 资源能力映射:
   - 每个资源具备多种能力
   - 能力有熟练度(proficiency)

3. 约束定义:
   - 距离约束: 资源到任务点的距离限制
   - 时间约束: 响应时限要求
   - 容量约束: 单资源最大服务数
   - 互斥约束: 某些资源不能同时分配
   - 依赖约束: 某些任务需要特定资源组合

4. CSP求解:
   - 使用OR-Tools CP-SAT求解器
   - 目标: 最小化总距离 / 最大化匹配质量

算法实现:
=========
- 建模: 二元变量 assignment[i][j] = 1 表示资源j分配给需求i
- 约束: 能力覆盖、容量限制、距离限制
- 目标: 最小化总距离或最大化总匹配分数
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass

from ..base import (
    AlgorithmBase, AlgorithmResult, AlgorithmStatus,
    Location, haversine_distance
)

logger = logging.getLogger(__name__)


@dataclass
class CapabilityNeed:
    """能力需求"""
    id: str
    task_id: str
    capability_id: str
    min_level: float  # 最低能力等级 0-1
    importance: str   # required/preferred/optional
    location: Optional[Location] = None


@dataclass
class ResourceCapability:
    """资源能力"""
    resource_id: str
    resource_name: str
    capabilities: Dict[str, float]  # {能力ID: 熟练度}
    location: Location
    status: str
    max_assignments: int = 1


@dataclass
class Assignment:
    """分配结果"""
    need_id: str
    task_id: str
    resource_id: str
    resource_name: str
    capability_id: str
    proficiency: float
    distance_km: float


class CapabilityMatcher(AlgorithmBase):
    """
    能力-资源CSP匹配器
    
    使用OR-Tools CP-SAT求解约束满足问题
    
    使用示例:
    ```python
    matcher = CapabilityMatcher()
    result = matcher.run({
        "capability_needs": [
            {
                "id": "NEED-001",
                "task_id": "EM06",
                "capability_id": "life_detection",
                "min_level": 0.7,
                "importance": "required",
                "location": {"lat": 31.23, "lng": 121.47}
            }
        ],
        "resources": [
            {
                "id": "RESCUE-001",
                "name": "重型救援队",
                "capabilities": {"life_detection": 0.9, "rescue_operation": 0.95},
                "location": {"lat": 31.25, "lng": 121.48},
                "status": "available",
                "max_assignments": 2
            }
        ],
        "constraints": {
            "max_distance_km": 50,
            "time_limit_sec": 30
        }
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "max_distance_km": 100,
            "time_limit_sec": 60,
            "optimization_mode": "min_distance",  # min_distance / max_quality
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "capability_needs" not in problem:
            return False, "缺少 capability_needs"
        if "resources" not in problem:
            return False, "缺少 resources"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行CSP匹配"""
        # 解析输入
        needs = self._parse_needs(problem["capability_needs"])
        resources = self._parse_resources(problem["resources"])
        constraints = problem.get("constraints", {})
        
        # 过滤可用资源
        resources = [r for r in resources if r.status == "available"]
        
        if not resources:
            return AlgorithmResult(
                status=AlgorithmStatus.INFEASIBLE,
                solution=[],
                metrics={},
                trace={"error": "无可用资源"},
                time_ms=0,
                message="无可用资源"
            )
        
        # 尝试使用OR-Tools求解
        try:
            assignments = self._solve_with_ortools(needs, resources, constraints)
        except ImportError:
            logger.warning("OR-Tools未安装，使用贪心算法")
            assignments = self._solve_greedy(needs, resources, constraints)
        
        # 计算统计
        required_needs = [n for n in needs if n.importance == "required"]
        required_covered = sum(1 for a in assignments 
                              if any(n.id == a.need_id and n.importance == "required" for n in needs))
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS if required_covered == len(required_needs) else AlgorithmStatus.PARTIAL,
            solution=[{
                "need_id": a.need_id,
                "task_id": a.task_id,
                "resource_id": a.resource_id,
                "resource_name": a.resource_name,
                "capability_id": a.capability_id,
                "proficiency": a.proficiency,
                "distance_km": a.distance_km,
            } for a in assignments],
            metrics={
                "total_assignments": len(assignments),
                "required_coverage": required_covered / len(required_needs) if required_needs else 1.0,
                "total_distance": sum(a.distance_km for a in assignments),
                "avg_proficiency": sum(a.proficiency for a in assignments) / len(assignments) if assignments else 0,
            },
            trace={
                "total_needs": len(needs),
                "total_resources": len(resources),
            },
            time_ms=0
        )
    
    def _parse_needs(self, needs_data: List[Dict]) -> List[CapabilityNeed]:
        """解析能力需求"""
        needs = []
        for d in needs_data:
            loc = d.get("location")
            needs.append(CapabilityNeed(
                id=d.get("id", ""),
                task_id=d.get("task_id", ""),
                capability_id=d.get("capability_id", ""),
                min_level=d.get("min_level", 0.5),
                importance=d.get("importance", "required"),
                location=Location.from_dict(loc) if loc else None
            ))
        return needs
    
    def _parse_resources(self, resources_data: List[Dict]) -> List[ResourceCapability]:
        """解析资源"""
        resources = []
        for d in resources_data:
            loc = d.get("location", {})
            resources.append(ResourceCapability(
                resource_id=d.get("id", ""),
                resource_name=d.get("name", ""),
                capabilities=d.get("capabilities", {}),
                location=Location(lat=loc.get("lat", 0), lng=loc.get("lng", 0)),
                status=d.get("status", "available"),
                max_assignments=d.get("max_assignments", 1)
            ))
        return resources
    
    def _solve_with_ortools(self, needs: List[CapabilityNeed], 
                            resources: List[ResourceCapability],
                            constraints: Dict) -> List[Assignment]:
        """使用OR-Tools CP-SAT求解"""
        from ortools.sat.python import cp_model
        
        model = cp_model.CpModel()
        
        n_needs = len(needs)
        n_resources = len(resources)
        max_distance = constraints.get("max_distance_km", self.params["max_distance_km"])
        
        # 预计算距离和能力匹配
        distances = {}  # (need_idx, res_idx) -> distance
        can_satisfy = {}  # (need_idx, res_idx) -> bool
        proficiencies = {}  # (need_idx, res_idx) -> proficiency
        
        for i, need in enumerate(needs):
            for j, res in enumerate(resources):
                # 距离
                if need.location:
                    dist = haversine_distance(need.location, res.location)
                else:
                    dist = 0
                distances[(i, j)] = dist
                
                # 能力匹配
                cap_id = need.capability_id
                if cap_id in res.capabilities and res.capabilities[cap_id] >= need.min_level:
                    can_satisfy[(i, j)] = True
                    proficiencies[(i, j)] = res.capabilities[cap_id]
                else:
                    can_satisfy[(i, j)] = False
                    proficiencies[(i, j)] = 0
        
        # 决策变量: assignment[i][j] = 1 表示资源j分配给需求i
        assignment = {}
        for i in range(n_needs):
            for j in range(n_resources):
                assignment[(i, j)] = model.NewBoolVar(f"assign_{i}_{j}")
        
        # 约束1: 每个必须需求至少有一个资源
        for i, need in enumerate(needs):
            if need.importance == "required":
                valid_resources = [j for j in range(n_resources) 
                                   if can_satisfy.get((i, j), False) and distances[(i, j)] <= max_distance]
                if valid_resources:
                    model.Add(sum(assignment[(i, j)] for j in valid_resources) >= 1)
        
        # 约束2: 能力必须满足
        for i in range(n_needs):
            for j in range(n_resources):
                if not can_satisfy.get((i, j), False):
                    model.Add(assignment[(i, j)] == 0)
        
        # 约束3: 距离限制
        for i in range(n_needs):
            for j in range(n_resources):
                if distances[(i, j)] > max_distance:
                    model.Add(assignment[(i, j)] == 0)
        
        # 约束4: 资源容量限制
        for j, res in enumerate(resources):
            model.Add(sum(assignment[(i, j)] for i in range(n_needs)) <= res.max_assignments)
        
        # 目标函数
        if self.params["optimization_mode"] == "min_distance":
            # 最小化总距离
            total_distance = []
            for i in range(n_needs):
                for j in range(n_resources):
                    dist_scaled = int(distances[(i, j)] * 100)
                    total_distance.append(assignment[(i, j)] * dist_scaled)
            model.Minimize(sum(total_distance))
        else:
            # 最大化匹配质量 (熟练度)
            total_quality = []
            for i in range(n_needs):
                for j in range(n_resources):
                    prof_scaled = int(proficiencies.get((i, j), 0) * 100)
                    total_quality.append(assignment[(i, j)] * prof_scaled)
            model.Maximize(sum(total_quality))
        
        # 求解
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = constraints.get(
            "time_limit_sec", self.params["time_limit_sec"]
        )
        status = solver.Solve(model)
        
        # 提取结果
        assignments = []
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            for i, need in enumerate(needs):
                for j, res in enumerate(resources):
                    if solver.Value(assignment[(i, j)]) == 1:
                        assignments.append(Assignment(
                            need_id=need.id,
                            task_id=need.task_id,
                            resource_id=res.resource_id,
                            resource_name=res.resource_name,
                            capability_id=need.capability_id,
                            proficiency=proficiencies.get((i, j), 0),
                            distance_km=round(distances[(i, j)], 2)
                        ))
        
        return assignments
    
    def _solve_greedy(self, needs: List[CapabilityNeed],
                      resources: List[ResourceCapability],
                      constraints: Dict) -> List[Assignment]:
        """贪心算法 (备用)"""
        max_distance = constraints.get("max_distance_km", self.params["max_distance_km"])
        assignments = []
        resource_usage = {r.resource_id: 0 for r in resources}
        
        # 按重要性排序需求
        importance_order = {"required": 0, "preferred": 1, "optional": 2}
        sorted_needs = sorted(needs, key=lambda n: importance_order.get(n.importance, 2))
        
        for need in sorted_needs:
            best_resource = None
            best_score = -1
            
            for res in resources:
                # 检查容量
                if resource_usage[res.resource_id] >= res.max_assignments:
                    continue
                
                # 检查能力
                if need.capability_id not in res.capabilities:
                    continue
                
                proficiency = res.capabilities[need.capability_id]
                if proficiency < need.min_level:
                    continue
                
                # 检查距离
                if need.location:
                    dist = haversine_distance(need.location, res.location)
                    if dist > max_distance:
                        continue
                else:
                    dist = 0
                
                # 计算分数: 熟练度高、距离近更好
                score = proficiency * 100 - dist
                
                if score > best_score:
                    best_score = score
                    best_resource = (res, dist, proficiency)
            
            if best_resource:
                res, dist, prof = best_resource
                assignments.append(Assignment(
                    need_id=need.id,
                    task_id=need.task_id,
                    resource_id=res.resource_id,
                    resource_name=res.resource_name,
                    capability_id=need.capability_id,
                    proficiency=prof,
                    distance_km=round(dist, 2)
                ))
                resource_usage[res.resource_id] += 1
        
        return assignments
