"""
资源冲突消解算法 + GRA全局资源仲裁器

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

4. GRA仲裁（新增）:
   - 优先级金字塔: L0(生命优先) > L1(次要救援) > L2(侦察) > L3(基础保障)
   - 切换成本计算: 防止任务震荡
   - 抢占规则: 优先级差>=2直接抢占，差=1需检查切换成本

算法实现:
=========
- 冲突检测: 构建资源-任务映射
- 冲突评分: 计算每个冲突的严重程度
- 消解排序: 按严重程度处理
- 方案生成: 对每个冲突生成消解方案
- GRA仲裁: 基于优先级和切换成本决定抢占
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


# ============================================================================
# GRA 全局资源仲裁器 - 优先级映射
# ============================================================================

GRA_PRIORITY_MAP: Dict[str, int] = {
    # L0 - 生命优先（最高优先级）
    "life_rescue_confirmed": 0,
    "secondary_disaster_prevention": 0,
    # L1 - 次要救援
    "medical_transport": 1,
    "hazard_zone_recon": 1,
    # L2 - 侦察任务
    "suspect_point_recon": 2,
    "panoramic_recon": 2,
    "supply_delivery": 2,
    # L3 - 基础保障（最低优先级）
    "infrastructure_inspection": 3,
}

# GRA 默认优先级（未知任务类型）
GRA_DEFAULT_PRIORITY = 3

# GRA 抢占阈值
GRA_COST_THRESHOLD_DEFAULT = 0.2  # 切换成本阈值（默认20%，可由配置覆盖）
GRA_AUTO_PREEMPT_DIFF_DEFAULT = 2  # 优先级差>=2时自动抢占
GRA_MIN_PREEMPT_DIFF_DEFAULT = 1   # 最小抢占优先级差


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
    # GRA 扩展字段
    task_type: str = ""  # 任务类型，用于GRA优先级映射
    gra_priority: int = GRA_DEFAULT_PRIORITY  # GRA优先级 (0-3)
    start_position: Optional[Tuple[float, float]] = None  # 新任务起始位置 (lon, lat)


@dataclass
class ResourceState:
    """资源状态（用于GRA切换成本计算）"""
    resource_id: str
    current_position: Tuple[float, float] = (0.0, 0.0)  # (lon, lat)
    home_position: Tuple[float, float] = (0.0, 0.0)     # 返航点
    remaining_capacity: float = 100.0  # 剩余容量百分比
    max_range: float = 50.0  # 最大航程(km)
    current_task_progress: float = 0.0  # 当前任务进度 (0-1)


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
            # GRA 配置（可由调用方传入覆盖，或由上层加载算法参数表后注入）
            "gra_cost_threshold": GRA_COST_THRESHOLD_DEFAULT,
            "gra_auto_preempt_diff": GRA_AUTO_PREEMPT_DIFF_DEFAULT,
            "gra_min_preempt_diff": GRA_MIN_PREEMPT_DIFF_DEFAULT,
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
            is_preemptible=d.get("is_preemptible", True),
            task_type=d.get("task_type", ""),
            gra_priority=d.get("gra_priority", GRA_PRIORITY_MAP.get(d.get("task_type", ""), GRA_DEFAULT_PRIORITY)),
            start_position=tuple(d["start_position"]) if d.get("start_position") else None,
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
    
    # ========================================================================
    # GRA 全局资源仲裁器方法
    # ========================================================================
    
    def get_gra_priority(self, task_type: str) -> int:
        """
        获取任务的GRA优先级
        
        Args:
            task_type: 任务类型字符串
            
        Returns:
            GRA优先级 (0=最高, 3=最低)
        """
        priority_map = self.params.get("gra_priority_map", GRA_PRIORITY_MAP)
        return priority_map.get(task_type, GRA_DEFAULT_PRIORITY)
    
    @staticmethod
    def _haversine_distance(
        pos1: Tuple[float, float], 
        pos2: Tuple[float, float]
    ) -> float:
        """
        计算两点间的Haversine距离（公里）
        
        Args:
            pos1: (lon, lat) 第一个点
            pos2: (lon, lat) 第二个点
            
        Returns:
            距离（公里）
        """
        lon1, lat1 = pos1
        lon2, lat2 = pos2
        
        # 地球半径（公里）
        R = 6371.0
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        # Haversine公式
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def calc_switching_cost(
        self,
        resource: ResourceState,
        new_task_position: Tuple[float, float],
    ) -> float:
        """
        计算资源切换成本（GRA核心算法）
        
        公式: switching_cost = return_distance / remaining_range
        
        Args:
            resource: 资源当前状态
            new_task_position: 新任务起点位置 (lon, lat)
            
        Returns:
            切换成本 (0.0-1.0)，1.0表示无法切换
        """
        # 计算返航距离
        return_distance = self._haversine_distance(
            resource.current_position,
            resource.home_position,
        )
        # 返航点到新任务起点的距离（部署距离）
        deploy_distance = self._haversine_distance(
            resource.home_position,
            new_task_position,
        )

        # 计算剩余航程
        remaining_range = (resource.remaining_capacity / 100.0) * resource.max_range

        # 边界条件处理
        if remaining_range <= 0:
            logger.warning(f"资源 {resource.resource_id} 剩余航程为0或负数")
            return 1.0

        # 基础切换成本 = (返航 + 部署) / 剩余航程
        base_cost = (return_distance + deploy_distance) / remaining_range

        # 添加任务进度惩罚（已完成越多，切换成本越高）
        progress_penalty = resource.current_task_progress * 0.15

        # 总成本，限制在 0-1 范围内
        total_cost = min(1.0, base_cost + progress_penalty)

        logger.debug(
            f"资源 {resource.resource_id} 切换成本: {total_cost:.3f} "
            f"(返航={return_distance:.1f}km, 部署={deploy_distance:.1f}km, 剩余={remaining_range:.1f}km, 进度={resource.current_task_progress:.1%})"
        )

        return total_cost

    def _get_gra_params(self) -> Dict[str, Any]:
        """获取GRA相关参数（允许通过实例参数覆盖，缺省使用默认值）。"""
        return {
            "cost_threshold": self.params.get("gra_cost_threshold", self.params.get("switching_cost_threshold", GRA_COST_THRESHOLD_DEFAULT)),
            "auto_preempt_diff": self.params.get("gra_auto_preempt_diff", GRA_AUTO_PREEMPT_DIFF_DEFAULT),
            "min_preempt_diff": self.params.get("gra_min_preempt_diff", GRA_MIN_PREEMPT_DIFF_DEFAULT),
        }
    
    def gra_can_preempt(
        self,
        new_task: ResourceClaim,
        current_task: ResourceClaim,
        resource: Optional[ResourceState] = None,
        new_task_position: Optional[Tuple[float, float]] = None,
    ) -> Tuple[bool, str, float]:
        """
        GRA仲裁：判断新任务是否可以抢占当前任务
        
        抢占规则:
        1. 优先级差>=2: 直接抢占，不检查切换成本
        2. 优先级差==1: 需切换成本<0.3才允许抢占
        3. 优先级差<=0: 不允许抢占
        
        Args:
            new_task: 新任务请求
            current_task: 当前执行的任务
            resource: 资源状态（用于计算切换成本）
            new_task_position: 新任务位置（用于计算切换成本）
            
        Returns:
            (can_preempt, reason, switching_cost)
        """
        # 获取GRA优先级（数字越小优先级越高）
        gra_params = self._get_gra_params()
        cost_threshold = gra_params["cost_threshold"]
        auto_preempt_diff = gra_params["auto_preempt_diff"]
        min_preempt_diff = gra_params["min_preempt_diff"]

        # 获取GRA优先级（数字越小优先级更高）
        new_priority = self.get_gra_priority(new_task.task_type) if new_task.task_type else new_task.gra_priority
        current_priority = self.get_gra_priority(current_task.task_type) if current_task.task_type else current_task.gra_priority

        priority_diff = current_priority - new_priority  # 正数表示新任务优先级更高
        # 规则1：当前任务不可抢占
        if not current_task.is_preemptible:
            return False, "当前任务标记为不可抢占", 0.0
        
        # 规则2：同优先级或新任务优先级更低，不抢占
        if priority_diff < min_preempt_diff:
            return False, f"优先级差不足: {priority_diff} < {min_preempt_diff}", 0.0
        
        # 规则3：优先级差>=2，直接抢占
        if priority_diff >= auto_preempt_diff:
            return True, f"高优先级直接抢占 (L{new_priority} vs L{current_priority})", 0.0
        
        # 规则4：优先级差==1，需检查切换成本
        switching_cost = 0.0
        if resource and new_task_position:
            switching_cost = self.calc_switching_cost(resource, new_task_position)

            if switching_cost >= cost_threshold:
                return False, f"切换成本过高: {switching_cost:.3f} >= {cost_threshold}", switching_cost
        else:
            # 无法计算成本时，不允许依据成本放行，返回提示
            return False, "缺少资源位置或新任务起点，无法计算切换成本", 1.0

        return True, f"允许抢占 (优先级差={priority_diff}, 切换成本={switching_cost:.3f})", switching_cost
    
    def gra_resolve_conflict(
        self,
        conflict: Conflict,
        resources: Dict[str, ResourceState],
    ) -> Optional[Resolution]:
        """
        使用GRA仲裁消解冲突
        
        Args:
            conflict: 冲突对象
            resources: 资源状态字典
            
        Returns:
            消解方案，如果无法消解返回None
        """
        claims = conflict.claims
        
        # 按GRA优先级排序（优先级数字越小越高）
        sorted_claims = sorted(
            claims, 
            key=lambda c: self.get_gra_priority(c.task_type) if c.task_type else c.gra_priority
        )
        
        winner = sorted_claims[0]
        losers = sorted_claims[1:]
        
        actions = []
        total_cost = 0.0
        
        resource = resources.get(conflict.resource_id)
        # 新任务起点位置，用于切换成本计算
        winner_position = winner.start_position if winner.start_position else None
        
        for loser in losers:
            can_preempt, reason, switching_cost = self.gra_can_preempt(
                new_task=winner,
                current_task=loser,
                resource=resource,
                new_task_position=winner_position,
            )
            
            if can_preempt:
                actions.append({
                    "type": "gra_preempt",
                    "task_id": loser.task_id,
                    "preempted_by": winner.task_id,
                    "reason": reason,
                    "switching_cost": switching_cost,
                    "reschedule_after": winner.end_time,
                })
                total_cost += switching_cost
                logger.info(f"GRA抢占: {winner.task_id} 抢占 {loser.task_id} - {reason}")
            else:
                # 不能抢占，使用延迟策略
                delay_amount = winner.end_time - loser.start_time
                actions.append({
                    "type": "delay",
                    "task_id": loser.task_id,
                    "delay_minutes": max(0, delay_amount),
                    "reason": reason,
                })
                total_cost += delay_amount * self.params.get("delay_penalty", 1.0)
                logger.info(f"GRA延迟: {loser.task_id} 延迟 {delay_amount}分钟 - {reason}")
        
        return Resolution(
            conflict_id=conflict.id,
            strategy=ResolutionStrategy.PREEMPT,
            winner_task=winner.task_id,
            affected_tasks=[l.task_id for l in losers],
            actions=actions,
            cost=total_cost,
        )
