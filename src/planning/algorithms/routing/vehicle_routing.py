"""
多车辆路径规划算法 (VRP)

业务逻辑:
=========
1. 问题定义:
   - 多辆救援车辆从各自出发点出发
   - 访问多个任务点(救援点、物资投放点)
   - 满足时间窗、容量等约束
   - 最小化总行驶距离/时间

2. VRP变体支持:
   - CVRP: 带容量约束
   - VRPTW: 带时间窗约束
   - VRPPD: 带取送货约束
   - MDVRP: 多depot

3. 约束条件:
   - 车辆容量(重量/体积)
   - 时间窗(任务点的服务时间要求)
   - 最大行驶时间/距离
   - 道路通行性

算法实现:
=========
- 使用OR-Tools Routing求解器
- 支持多种启发式策略
- 支持局部搜索优化
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass

from ..base import (
    AlgorithmBase, AlgorithmResult, AlgorithmStatus,
    Location, haversine_distance, TimeWindow
)

logger = logging.getLogger(__name__)


@dataclass
class Depot:
    """车辆出发/返回点"""
    id: str
    location: Location
    name: str = ""


@dataclass
class TaskNode:
    """任务节点"""
    id: str
    location: Location
    demand: int  # 需求量(用于容量约束)
    service_time_min: int  # 服务时间
    time_window: Optional[TimeWindow] = None
    priority: int = 1
    node_type: str = "task"  # task/pickup/delivery


@dataclass
class VRPVehicle:
    """VRP车辆"""
    id: str
    name: str
    depot_id: str
    capacity: int
    max_distance_km: float
    max_time_min: int
    speed_kmh: float = 40


@dataclass
class VRPRoute:
    """路线结果"""
    vehicle_id: str
    vehicle_name: str
    stops: List[Dict]
    total_distance_km: float
    total_time_min: int
    total_load: int
    depot_id: str


class VehicleRoutingPlanner(AlgorithmBase):
    """
    多车辆路径规划器
    
    使用示例:
    ```python
    planner = VehicleRoutingPlanner()
    result = planner.run({
        "depots": [
            {"id": "D1", "location": {"lat": 31.20, "lng": 121.45}, "name": "消防站"}
        ],
        "tasks": [
            {"id": "T1", "location": {"lat": 31.23, "lng": 121.47}, "demand": 1, 
             "service_time_min": 30, "time_window": {"start": 0, "end": 120}}
        ],
        "vehicles": [
            {"id": "V1", "name": "救援车1", "depot_id": "D1", "capacity": 5,
             "max_distance_km": 100, "max_time_min": 480, "speed_kmh": 40}
        ],
        "constraints": {
            "use_time_windows": True,
            "time_limit_sec": 30
        }
    })
    ```
    """
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "first_solution_strategy": "PATH_CHEAPEST_ARC",
            "local_search_metaheuristic": "GUIDED_LOCAL_SEARCH",
            "time_limit_sec": 30,
            "distance_scale": 100,  # 距离放大系数(OR-Tools用整数)
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "depots" not in problem or not problem["depots"]:
            return False, "缺少 depots"
        if "tasks" not in problem or not problem["tasks"]:
            return False, "缺少 tasks"
        if "vehicles" not in problem or not problem["vehicles"]:
            return False, "缺少 vehicles"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """求解VRP"""
        # 解析输入
        depots = self._parse_depots(problem["depots"])
        tasks = self._parse_tasks(problem["tasks"])
        vehicles = self._parse_vehicles(problem["vehicles"])
        constraints = problem.get("constraints", {})
        
        # 尝试OR-Tools求解
        try:
            routes = self._solve_with_ortools(depots, tasks, vehicles, constraints)
        except ImportError:
            logger.warning("OR-Tools未安装，使用贪心算法")
            routes = self._solve_greedy(depots, tasks, vehicles, constraints)
        
        # 统计
        total_distance = sum(r.total_distance_km for r in routes)
        served_tasks = sum(len(r.stops) for r in routes)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS if served_tasks == len(tasks) else AlgorithmStatus.PARTIAL,
            solution=[{
                "vehicle_id": r.vehicle_id,
                "vehicle_name": r.vehicle_name,
                "depot_id": r.depot_id,
                "stops": r.stops,
                "total_distance_km": r.total_distance_km,
                "total_time_min": r.total_time_min,
                "total_load": r.total_load,
            } for r in routes],
            metrics={
                "total_distance_km": round(total_distance, 2),
                "served_tasks": served_tasks,
                "total_tasks": len(tasks),
                "vehicles_used": len([r for r in routes if r.stops]),
            },
            trace={
                "depots": len(depots),
                "tasks": len(tasks),
                "vehicles": len(vehicles),
            },
            time_ms=0
        )
    
    def _parse_depots(self, data: List[Dict]) -> List[Depot]:
        return [Depot(
            id=d["id"],
            location=Location.from_dict(d["location"]),
            name=d.get("name", "")
        ) for d in data]
    
    def _parse_tasks(self, data: List[Dict]) -> List[TaskNode]:
        tasks = []
        for d in data:
            tw = d.get("time_window")
            tasks.append(TaskNode(
                id=d["id"],
                location=Location.from_dict(d["location"]),
                demand=d.get("demand", 1),
                service_time_min=d.get("service_time_min", 15),
                time_window=TimeWindow(tw["start"], tw["end"]) if tw else None,
                priority=d.get("priority", 1),
                node_type=d.get("node_type", "task")
            ))
        return tasks
    
    def _parse_vehicles(self, data: List[Dict]) -> List[VRPVehicle]:
        return [VRPVehicle(
            id=v["id"],
            name=v.get("name", ""),
            depot_id=v["depot_id"],
            capacity=v.get("capacity", 10),
            max_distance_km=v.get("max_distance_km", 200),
            max_time_min=v.get("max_time_min", 480),
            speed_kmh=v.get("speed_kmh", 40)
        ) for v in data]
    
    def _solve_with_ortools(self, depots: List[Depot], tasks: List[TaskNode],
                            vehicles: List[VRPVehicle], constraints: Dict) -> List[VRPRoute]:
        """使用OR-Tools求解"""
        from ortools.constraint_solver import routing_enums_pb2
        from ortools.constraint_solver import pywrapcp
        
        # 构建所有节点: depots + tasks
        depot_map = {d.id: (i, d) for i, d in enumerate(depots)}
        all_locations = [d.location for d in depots] + [t.location for t in tasks]
        n_locations = len(all_locations)
        n_depots = len(depots)
        
        # 构建距离矩阵
        distance_matrix = self._build_distance_matrix(all_locations)
        
        # 确定每辆车的起点depot索引
        starts = []
        ends = []
        for v in vehicles:
            depot_idx = depot_map.get(v.depot_id, (0, None))[0]
            starts.append(depot_idx)
            ends.append(depot_idx)
        
        # 创建路由模型
        manager = pywrapcp.RoutingIndexManager(n_locations, len(vehicles), starts, ends)
        routing = pywrapcp.RoutingModel(manager)
        
        # 距离回调
        scale = self.params["distance_scale"]
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node] * scale)
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        
        # 容量约束
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            if from_node < n_depots:
                return 0
            return tasks[from_node - n_depots].demand
        
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            [v.capacity for v in vehicles],
            True,
            'Capacity'
        )
        
        # 时间窗约束
        if constraints.get("use_time_windows", False):
            def time_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                # 行驶时间 + 服务时间
                dist = distance_matrix[from_node][to_node]
                travel_time = int(dist / 40 * 60)  # 假设40km/h
                service_time = 0
                if from_node >= n_depots:
                    service_time = tasks[from_node - n_depots].service_time_min
                return travel_time + service_time
            
            time_callback_index = routing.RegisterTransitCallback(time_callback)
            routing.AddDimension(
                time_callback_index,
                60,  # 允许等待
                max(v.max_time_min for v in vehicles),
                False,
                'Time'
            )
            
            time_dimension = routing.GetDimensionOrDie('Time')
            for i, task in enumerate(tasks):
                if task.time_window:
                    index = manager.NodeToIndex(n_depots + i)
                    time_dimension.CumulVar(index).SetRange(
                        task.time_window.start,
                        task.time_window.end
                    )
        
        # 求解参数
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = getattr(
            routing_enums_pb2.FirstSolutionStrategy,
            self.params["first_solution_strategy"]
        )
        search_parameters.local_search_metaheuristic = getattr(
            routing_enums_pb2.LocalSearchMetaheuristic,
            self.params["local_search_metaheuristic"]
        )
        search_parameters.time_limit.FromSeconds(
            constraints.get("time_limit_sec", self.params["time_limit_sec"])
        )
        
        # 求解
        solution = routing.SolveWithParameters(search_parameters)
        
        # 提取路线
        routes = []
        if solution:
            for vehicle_idx, vehicle in enumerate(vehicles):
                route = VRPRoute(
                    vehicle_id=vehicle.id,
                    vehicle_name=vehicle.name,
                    depot_id=vehicle.depot_id,
                    stops=[],
                    total_distance_km=0,
                    total_time_min=0,
                    total_load=0
                )
                
                index = routing.Start(vehicle_idx)
                route_distance = 0
                
                while not routing.IsEnd(index):
                    node = manager.IndexToNode(index)
                    
                    if node >= n_depots:
                        task = tasks[node - n_depots]
                        arrival_time = None
                        if constraints.get("use_time_windows"):
                            time_var = routing.GetDimensionOrDie('Time').CumulVar(index)
                            arrival_time = solution.Value(time_var)
                        
                        route.stops.append({
                            "task_id": task.id,
                            "location": task.location.to_tuple(),
                            "arrival_time_min": arrival_time,
                            "demand": task.demand
                        })
                        route.total_load += task.demand
                    
                    prev_index = index
                    index = solution.Value(routing.NextVar(index))
                    route_distance += routing.GetArcCostForVehicle(prev_index, index, vehicle_idx)
                
                route.total_distance_km = round(route_distance / scale, 2)
                route.total_time_min = int(route.total_distance_km / vehicle.speed_kmh * 60)
                routes.append(route)
        
        return routes
    
    def _solve_greedy(self, depots: List[Depot], tasks: List[TaskNode],
                      vehicles: List[VRPVehicle], constraints: Dict) -> List[VRPRoute]:
        """贪心算法(备用)"""
        depot_map = {d.id: d for d in depots}
        unassigned = list(tasks)
        routes = []
        
        for vehicle in vehicles:
            depot = depot_map.get(vehicle.depot_id)
            if not depot:
                continue
            
            route = VRPRoute(
                vehicle_id=vehicle.id,
                vehicle_name=vehicle.name,
                depot_id=vehicle.depot_id,
                stops=[],
                total_distance_km=0,
                total_time_min=0,
                total_load=0
            )
            
            current_location = depot.location
            current_load = 0
            current_distance = 0
            
            while unassigned:
                # 找最近可行任务
                best_task = None
                best_distance = float('inf')
                
                for task in unassigned:
                    if current_load + task.demand > vehicle.capacity:
                        continue
                    
                    dist = haversine_distance(current_location, task.location)
                    
                    if current_distance + dist > vehicle.max_distance_km:
                        continue
                    
                    if dist < best_distance:
                        best_distance = dist
                        best_task = task
                
                if best_task is None:
                    break
                
                # 分配任务
                route.stops.append({
                    "task_id": best_task.id,
                    "location": best_task.location.to_tuple(),
                    "demand": best_task.demand
                })
                current_load += best_task.demand
                current_distance += best_distance
                current_location = best_task.location
                unassigned.remove(best_task)
            
            route.total_load = current_load
            route.total_distance_km = round(current_distance, 2)
            route.total_time_min = int(current_distance / vehicle.speed_kmh * 60)
            routes.append(route)
        
        return routes
    
    def _build_distance_matrix(self, locations: List[Location]) -> List[List[float]]:
        """构建距离矩阵"""
        n = len(locations)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = haversine_distance(locations[i], locations[j])
        
        return matrix
