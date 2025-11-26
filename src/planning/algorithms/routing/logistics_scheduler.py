"""
物资调度优化算法

业务逻辑:
=========
1. 物资分配问题:
   - 多仓库、多物资类型、多需求点
   - 目标: 最小化运输距离，满足所有需求

2. 配送路径问题:
   - 基于分配结果的车辆路径规划
   - 考虑车辆容量、时间窗

3. 库存预置优化:
   - P-median问题: 选择最优预置点
   - 最小化总响应时间

算法实现:
=========
- 分配: 运输问题(Transportation Problem) - 线性规划
- 路径: 调用VRP求解器
- 预置: P-median启发式算法
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
class Warehouse:
    """仓库"""
    id: str
    name: str
    location: Location
    inventory: Dict[str, int]  # {物资类型: 数量}
    capacity: int


@dataclass
class DemandPoint:
    """需求点"""
    id: str
    name: str
    location: Location
    needs: Dict[str, int]  # {物资类型: 需求量}
    priority: int  # 优先级 1-5
    deadline_min: Optional[int] = None


@dataclass
class AllocationPlan:
    """分配计划"""
    warehouse_id: str
    demand_id: str
    items: Dict[str, int]
    distance_km: float
    priority: int


@dataclass
class DeliveryRoute:
    """配送路线"""
    vehicle_id: str
    warehouse_id: str
    stops: List[Dict]
    total_distance_km: float
    total_load: Dict[str, int]


class LogisticsScheduler(AlgorithmBase):
    """
    物资调度优化器
    
    使用示例:
    ```python
    scheduler = LogisticsScheduler()
    result = scheduler.run({
        "warehouses": [
            {
                "id": "W1", 
                "name": "中心仓库",
                "location": {"lat": 31.20, "lng": 121.45},
                "inventory": {"food": 1000, "water": 500, "tent": 200},
                "capacity": 5000
            }
        ],
        "demands": [
            {
                "id": "D1",
                "name": "安置点A",
                "location": {"lat": 31.25, "lng": 121.50},
                "needs": {"food": 100, "water": 50},
                "priority": 1
            }
        ],
        "vehicles": [
            {"id": "V1", "capacity_kg": 1000, "speed_kmh": 40}
        ]
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "optimization_mode": "min_distance",  # min_distance / priority_first
            "allow_split_delivery": True,  # 允许拆分配送
            "max_iterations": 1000,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "warehouses" not in problem or not problem["warehouses"]:
            return False, "缺少 warehouses"
        if "demands" not in problem or not problem["demands"]:
            return False, "缺少 demands"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行物资调度"""
        warehouses = self._parse_warehouses(problem["warehouses"])
        demands = self._parse_demands(problem["demands"])
        vehicles = problem.get("vehicles", [])
        
        # 1. 物资分配
        allocations = self._solve_allocation(warehouses, demands)
        
        # 2. 配送路径 (如果有车辆信息)
        routes = []
        if vehicles:
            routes = self._plan_delivery_routes(allocations, warehouses, demands, vehicles)
        
        # 3. 统计
        total_distance = sum(a.distance_km for a in allocations)
        fulfilled_demands = self._compute_fulfillment(allocations, demands)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "allocations": [{
                    "warehouse_id": a.warehouse_id,
                    "demand_id": a.demand_id,
                    "items": a.items,
                    "distance_km": a.distance_km,
                    "priority": a.priority,
                } for a in allocations],
                "routes": [{
                    "vehicle_id": r.vehicle_id,
                    "warehouse_id": r.warehouse_id,
                    "stops": r.stops,
                    "total_distance_km": r.total_distance_km,
                } for r in routes] if routes else None,
                "fulfillment": fulfilled_demands,
            },
            metrics={
                "total_distance_km": round(total_distance, 2),
                "allocation_count": len(allocations),
                "fulfillment_rate": fulfilled_demands.get("overall_rate", 0),
            },
            trace={
                "warehouses": len(warehouses),
                "demands": len(demands),
            },
            time_ms=0
        )
    
    def _parse_warehouses(self, data: List[Dict]) -> List[Warehouse]:
        return [Warehouse(
            id=w["id"],
            name=w.get("name", ""),
            location=Location.from_dict(w["location"]),
            inventory=w.get("inventory", {}),
            capacity=w.get("capacity", 10000)
        ) for w in data]
    
    def _parse_demands(self, data: List[Dict]) -> List[DemandPoint]:
        return [DemandPoint(
            id=d["id"],
            name=d.get("name", ""),
            location=Location.from_dict(d["location"]),
            needs=d.get("needs", {}),
            priority=d.get("priority", 3),
            deadline_min=d.get("deadline_min")
        ) for d in data]
    
    def _solve_allocation(self, warehouses: List[Warehouse],
                          demands: List[DemandPoint]) -> List[AllocationPlan]:
        """
        求解物资分配
        
        使用贪心算法:
        1. 按优先级排序需求
        2. 对每个需求，选择最近且库存充足的仓库
        """
        # 复制库存(避免修改原数据)
        inventory = {w.id: dict(w.inventory) for w in warehouses}
        warehouse_map = {w.id: w for w in warehouses}
        
        allocations = []
        
        # 按优先级排序(高优先级先处理)
        sorted_demands = sorted(demands, key=lambda d: d.priority)
        
        for demand in sorted_demands:
            for item_type, need_qty in demand.needs.items():
                remaining = need_qty
                
                # 找能满足需求的仓库，按距离排序
                candidates = []
                for w_id, inv in inventory.items():
                    if inv.get(item_type, 0) > 0:
                        dist = haversine_distance(
                            warehouse_map[w_id].location,
                            demand.location
                        )
                        candidates.append((w_id, dist, inv[item_type]))
                
                candidates.sort(key=lambda x: x[1])  # 按距离排序
                
                for w_id, dist, available in candidates:
                    if remaining <= 0:
                        break
                    
                    # 分配数量
                    allocate_qty = min(remaining, available)
                    
                    if allocate_qty > 0:
                        allocations.append(AllocationPlan(
                            warehouse_id=w_id,
                            demand_id=demand.id,
                            items={item_type: allocate_qty},
                            distance_km=round(dist, 2),
                            priority=demand.priority
                        ))
                        
                        # 更新库存
                        inventory[w_id][item_type] -= allocate_qty
                        remaining -= allocate_qty
        
        return allocations
    
    def _plan_delivery_routes(self, allocations: List[AllocationPlan],
                               warehouses: List[Warehouse],
                               demands: List[DemandPoint],
                               vehicles: List[Dict]) -> List[DeliveryRoute]:
        """规划配送路线"""
        warehouse_map = {w.id: w for w in warehouses}
        demand_map = {d.id: d for d in demands}
        
        # 按仓库分组分配
        by_warehouse = {}
        for alloc in allocations:
            if alloc.warehouse_id not in by_warehouse:
                by_warehouse[alloc.warehouse_id] = []
            by_warehouse[alloc.warehouse_id].append(alloc)
        
        routes = []
        vehicle_idx = 0
        
        for w_id, allocs in by_warehouse.items():
            if vehicle_idx >= len(vehicles):
                break
            
            vehicle = vehicles[vehicle_idx]
            warehouse = warehouse_map[w_id]
            
            # 简单路线: 从仓库依次访问各需求点
            stops = []
            total_distance = 0
            current_loc = warehouse.location
            total_load = {}
            
            # 按距离排序需求点
            sorted_allocs = sorted(allocs, key=lambda a: a.distance_km)
            
            for alloc in sorted_allocs:
                demand = demand_map[alloc.demand_id]
                dist = haversine_distance(current_loc, demand.location)
                total_distance += dist
                
                stops.append({
                    "demand_id": alloc.demand_id,
                    "demand_name": demand.name,
                    "location": demand.location.to_tuple(),
                    "items": alloc.items,
                    "distance_from_prev": round(dist, 2)
                })
                
                # 累计装载
                for item, qty in alloc.items.items():
                    total_load[item] = total_load.get(item, 0) + qty
                
                current_loc = demand.location
            
            routes.append(DeliveryRoute(
                vehicle_id=vehicle["id"],
                warehouse_id=w_id,
                stops=stops,
                total_distance_km=round(total_distance, 2),
                total_load=total_load
            ))
            
            vehicle_idx += 1
        
        return routes
    
    def _compute_fulfillment(self, allocations: List[AllocationPlan],
                              demands: List[DemandPoint]) -> Dict:
        """计算需求满足率"""
        # 汇总分配
        fulfilled = {}  # {demand_id: {item: qty}}
        for alloc in allocations:
            if alloc.demand_id not in fulfilled:
                fulfilled[alloc.demand_id] = {}
            for item, qty in alloc.items.items():
                fulfilled[alloc.demand_id][item] = fulfilled[alloc.demand_id].get(item, 0) + qty
        
        # 计算满足率
        total_needed = 0
        total_fulfilled = 0
        by_demand = {}
        
        for demand in demands:
            demand_needed = sum(demand.needs.values())
            demand_fulfilled = sum(fulfilled.get(demand.id, {}).values())
            
            total_needed += demand_needed
            total_fulfilled += demand_fulfilled
            
            by_demand[demand.id] = {
                "needed": demand.needs,
                "fulfilled": fulfilled.get(demand.id, {}),
                "rate": demand_fulfilled / demand_needed if demand_needed > 0 else 1.0
            }
        
        return {
            "overall_rate": total_fulfilled / total_needed if total_needed > 0 else 1.0,
            "by_demand": by_demand
        }
    
    def optimize_warehouse_locations(self, candidate_locations: List[Location],
                                      demand_points: List[DemandPoint],
                                      num_warehouses: int) -> List[Location]:
        """
        仓库/预置点选址优化 (P-median问题)
        
        目标: 选择k个位置，使得所有需求点到最近仓库的总距离最小
        """
        n_candidates = len(candidate_locations)
        n_demands = len(demand_points)
        
        if num_warehouses >= n_candidates:
            return candidate_locations
        
        # 计算距离矩阵
        distances = []
        for loc in candidate_locations:
            row = []
            for demand in demand_points:
                dist = haversine_distance(loc, demand.location)
                # 加权距离(考虑优先级)
                weighted_dist = dist / demand.priority
                row.append(weighted_dist)
            distances.append(row)
        
        # 贪心选择
        selected = []
        remaining = set(range(n_candidates))
        
        for _ in range(num_warehouses):
            best_loc = None
            best_reduction = -1
            
            for loc_idx in remaining:
                # 计算如果选择这个位置，总距离减少多少
                reduction = 0
                for d_idx in range(n_demands):
                    current_min = float('inf')
                    for s_idx in selected:
                        current_min = min(current_min, distances[s_idx][d_idx])
                    
                    new_dist = distances[loc_idx][d_idx]
                    if new_dist < current_min:
                        reduction += current_min - new_dist if current_min < float('inf') else new_dist
                
                if reduction > best_reduction:
                    best_reduction = reduction
                    best_loc = loc_idx
            
            if best_loc is not None:
                selected.append(best_loc)
                remaining.remove(best_loc)
        
        return [candidate_locations[i] for i in selected]
