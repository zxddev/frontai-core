"""
车辆-物资智能匹配算法

业务逻辑:
=========
1. 兼容性检查:
   - 物资类型与车辆类型的兼容性矩阵
   - 特殊要求匹配(冷链、防爆、防泄漏等)

2. 容量检查:
   - 重量容量、体积容量
   - 多物资装载优化

3. 距离与时效:
   - 计算车辆到起点、起点到终点的距离
   - 根据紧急程度匹配车辆速度能力

4. 综合评分:
   - 兼容性、容量利用率、距离、紧急响应能力
   - 加权求和得出匹配分数

算法实现:
=========
- 兼容性: 查表 + 特殊要求检查
- 容量: 背包问题变体(多物资单车)
- 匹配: 二分图最优匹配 / 贪心 + 局部搜索
- 路径: 调用路径规划接口
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from ..base import (
    AlgorithmBase, AlgorithmResult, AlgorithmStatus,
    Location, haversine_distance, estimate_travel_time
)

logger = logging.getLogger(__name__)


class CargoType(Enum):
    """物资类型"""
    MEDICAL_SUPPLY = "medical_supply"      # 医疗物资
    FOOD_WATER = "food_water"              # 食品饮水
    TENT_SHELTER = "tent_shelter"          # 帐篷安置
    RESCUE_EQUIPMENT = "rescue_equipment"  # 救援器材
    HEAVY_EQUIPMENT = "heavy_equipment"    # 重型设备
    HAZMAT_MATERIAL = "hazmat_material"    # 危化品相关
    FUEL = "fuel"                          # 燃料
    BLOOD = "blood"                        # 血液制品
    GENERATOR = "generator"                # 发电设备
    COMMUNICATION = "communication"        # 通信设备


class VehicleType(Enum):
    """车辆类型"""
    CARGO_TRUCK = "cargo_truck"            # 普通货车
    REFRIGERATED_TRUCK = "refrigerated"    # 冷藏车
    TANKER = "tanker"                      # 罐车
    FLATBED = "flatbed"                    # 平板车
    AMBULANCE = "ambulance"                # 救护车
    HAZMAT_VEHICLE = "hazmat_vehicle"      # 危化品车
    HELICOPTER = "helicopter"              # 直升机
    WATER_TRUCK = "water_truck"            # 供水车
    SHELTER_TRUCK = "shelter_truck"        # 帐篷车


class Urgency(Enum):
    """紧急程度"""
    CRITICAL = "critical"   # 生命攸关
    HIGH = "high"           # 高优先
    MEDIUM = "medium"       # 中等
    LOW = "low"             # 低优先


@dataclass
class CargoRequest:
    """物资运输请求"""
    id: str
    cargo_type: str
    quantity_kg: float
    volume_m3: float
    urgency: str
    origin: Location
    destination: Location
    special_requirements: List[str]  # cold_chain, explosion_proof, leak_proof
    time_window_min: Optional[int] = None  # 最晚送达时间(分钟)
    
    @classmethod
    def from_dict(cls, d: Dict) -> "CargoRequest":
        return cls(
            id=d.get("id", ""),
            cargo_type=d.get("cargo_type", ""),
            quantity_kg=d.get("quantity_kg", 0),
            volume_m3=d.get("volume_m3", 0),
            urgency=d.get("urgency", "medium"),
            origin=Location.from_dict(d.get("origin", {})),
            destination=Location.from_dict(d.get("destination", {})),
            special_requirements=d.get("special_requirements", []),
            time_window_min=d.get("time_window_min"),
        )


@dataclass
class Vehicle:
    """车辆"""
    id: str
    name: str
    type: str
    location: Location
    capacity_kg: float
    capacity_m3: float
    avg_speed_kmh: float
    status: str
    features: List[str]  # refrigeration, hazmat_certified, etc.
    
    @classmethod
    def from_dict(cls, d: Dict) -> "Vehicle":
        loc = d.get("location", {})
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            type=d.get("type", ""),
            location=Location(lat=loc.get("lat", 0), lng=loc.get("lng", 0)),
            capacity_kg=d.get("capacity_kg", 1000),
            capacity_m3=d.get("capacity_m3", 10),
            avg_speed_kmh=d.get("avg_speed_kmh", 40),
            status=d.get("status", "available"),
            features=d.get("features", []),
        )


@dataclass
class MatchResult:
    """匹配结果"""
    request_id: str
    vehicle_id: str
    vehicle_name: str
    score: float
    eta_minutes: int
    distance_km: float
    capacity_utilization: float
    match_details: Dict[str, Any]


class VehicleCargoMatcher(AlgorithmBase):
    """
    车辆-物资智能匹配器
    
    使用示例:
    ```python
    matcher = VehicleCargoMatcher()
    result = matcher.run({
        "cargo_requests": [
            {
                "id": "REQ-001",
                "cargo_type": "medical_supply",
                "quantity_kg": 500,
                "volume_m3": 2.0,
                "urgency": "critical",
                "origin": {"lat": 31.23, "lng": 121.47},
                "destination": {"lat": 31.25, "lng": 121.50},
                "special_requirements": ["cold_chain"]
            }
        ],
        "available_vehicles": [...],
    })
    ```
    """
    
    # 物资-车辆兼容性矩阵
    COMPATIBILITY_MATRIX = {
        CargoType.MEDICAL_SUPPLY.value: [
            VehicleType.CARGO_TRUCK.value, 
            VehicleType.REFRIGERATED_TRUCK.value,
            VehicleType.AMBULANCE.value,
            VehicleType.HELICOPTER.value
        ],
        CargoType.FOOD_WATER.value: [
            VehicleType.CARGO_TRUCK.value,
            VehicleType.REFRIGERATED_TRUCK.value,
            VehicleType.WATER_TRUCK.value
        ],
        CargoType.TENT_SHELTER.value: [
            VehicleType.CARGO_TRUCK.value,
            VehicleType.FLATBED.value,
            VehicleType.SHELTER_TRUCK.value
        ],
        CargoType.RESCUE_EQUIPMENT.value: [
            VehicleType.CARGO_TRUCK.value,
            VehicleType.FLATBED.value
        ],
        CargoType.HEAVY_EQUIPMENT.value: [
            VehicleType.FLATBED.value
        ],
        CargoType.HAZMAT_MATERIAL.value: [
            VehicleType.HAZMAT_VEHICLE.value
        ],
        CargoType.FUEL.value: [
            VehicleType.TANKER.value
        ],
        CargoType.BLOOD.value: [
            VehicleType.REFRIGERATED_TRUCK.value,
            VehicleType.AMBULANCE.value,
            VehicleType.HELICOPTER.value
        ],
        CargoType.GENERATOR.value: [
            VehicleType.CARGO_TRUCK.value,
            VehicleType.FLATBED.value
        ],
        CargoType.COMMUNICATION.value: [
            VehicleType.CARGO_TRUCK.value
        ],
    }
    
    # 紧急程度对应的最低速度要求
    URGENCY_SPEED_REQUIREMENTS = {
        Urgency.CRITICAL.value: 60,   # km/h
        Urgency.HIGH.value: 45,
        Urgency.MEDIUM.value: 30,
        Urgency.LOW.value: 20,
    }
    
    # 特殊要求映射
    SPECIAL_REQUIREMENT_FEATURES = {
        "cold_chain": "refrigeration",
        "explosion_proof": "explosion_proof",
        "leak_proof": "leak_proof",
        "hazmat_certified": "hazmat_certified",
        "sterile": "sterile_environment",
    }
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "weight_compatibility": 0.3,
            "weight_capacity": 0.2,
            "weight_distance": 0.25,
            "weight_urgency": 0.25,
            "allow_partial_match": True,  # 允许部分满足
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "cargo_requests" not in problem:
            return False, "缺少 cargo_requests"
        if "available_vehicles" not in problem:
            return False, "缺少 available_vehicles"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行物资-车辆匹配"""
        requests = [CargoRequest.from_dict(r) for r in problem["cargo_requests"]]
        vehicles = [Vehicle.from_dict(v) for v in problem["available_vehicles"]]
        
        # 过滤可用车辆
        vehicles = [v for v in vehicles if v.status == "available"]
        
        if not vehicles:
            return AlgorithmResult(
                status=AlgorithmStatus.INFEASIBLE,
                solution=[],
                metrics={},
                trace={"error": "无可用车辆"},
                time_ms=0,
                message="无可用车辆"
            )
        
        matches = []
        unmatched = []
        used_vehicles = set()
        
        # 按紧急程度排序请求
        urgency_order = {Urgency.CRITICAL.value: 0, Urgency.HIGH.value: 1, 
                         Urgency.MEDIUM.value: 2, Urgency.LOW.value: 3}
        sorted_requests = sorted(requests, key=lambda r: urgency_order.get(r.urgency, 2))
        
        for request in sorted_requests:
            best_match = self._find_best_vehicle(request, vehicles, used_vehicles)
            
            if best_match:
                matches.append(best_match)
                used_vehicles.add(best_match.vehicle_id)
            else:
                unmatched.append(request.id)
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS if not unmatched else AlgorithmStatus.PARTIAL,
            solution=[{
                "request_id": m.request_id,
                "vehicle_id": m.vehicle_id,
                "vehicle_name": m.vehicle_name,
                "score": m.score,
                "eta_minutes": m.eta_minutes,
                "distance_km": m.distance_km,
                "capacity_utilization": m.capacity_utilization,
            } for m in matches],
            metrics={
                "matched_count": len(matches),
                "unmatched_count": len(unmatched),
                "match_rate": len(matches) / len(requests) if requests else 0,
                "avg_score": sum(m.score for m in matches) / len(matches) if matches else 0,
                "avg_eta": sum(m.eta_minutes for m in matches) / len(matches) if matches else 0,
            },
            trace={
                "unmatched_requests": unmatched,
                "total_requests": len(requests),
            },
            time_ms=0
        )
    
    def _find_best_vehicle(self, request: CargoRequest, vehicles: List[Vehicle],
                           used_vehicles: set) -> Optional[MatchResult]:
        """为物资请求找到最佳车辆"""
        candidates = []
        
        for vehicle in vehicles:
            if vehicle.id in used_vehicles:
                continue
            
            # 1. 兼容性检查
            if not self._check_compatibility(request, vehicle):
                continue
            
            # 2. 容量检查
            if not self._check_capacity(request, vehicle):
                continue
            
            # 3. 特殊要求检查
            if not self._check_special_requirements(request, vehicle):
                continue
            
            # 4. 计算分数
            score, details = self._compute_match_score(request, vehicle)
            
            if score > 0:
                candidates.append((vehicle, score, details))
        
        if not candidates:
            return None
        
        # 选择最高分
        candidates.sort(key=lambda x: -x[1])
        best_vehicle, best_score, details = candidates[0]
        
        # 计算ETA
        dist_to_origin = haversine_distance(best_vehicle.location, request.origin)
        dist_to_dest = haversine_distance(request.origin, request.destination)
        total_distance = dist_to_origin + dist_to_dest
        eta = estimate_travel_time(total_distance, best_vehicle.avg_speed_kmh)
        
        # 容量利用率
        utilization = max(
            request.quantity_kg / best_vehicle.capacity_kg,
            request.volume_m3 / best_vehicle.capacity_m3
        )
        
        return MatchResult(
            request_id=request.id,
            vehicle_id=best_vehicle.id,
            vehicle_name=best_vehicle.name,
            score=best_score,
            eta_minutes=eta,
            distance_km=round(total_distance, 2),
            capacity_utilization=round(utilization, 2),
            match_details=details
        )
    
    def _check_compatibility(self, request: CargoRequest, vehicle: Vehicle) -> bool:
        """检查物资-车辆兼容性"""
        compatible_types = self.COMPATIBILITY_MATRIX.get(request.cargo_type, [])
        
        # 如果物资类型未定义，假设通用货车可用
        if not compatible_types:
            return vehicle.type in [VehicleType.CARGO_TRUCK.value, VehicleType.FLATBED.value]
        
        return vehicle.type in compatible_types
    
    def _check_capacity(self, request: CargoRequest, vehicle: Vehicle) -> bool:
        """检查容量"""
        weight_ok = request.quantity_kg <= vehicle.capacity_kg
        volume_ok = request.volume_m3 <= vehicle.capacity_m3
        return weight_ok and volume_ok
    
    def _check_special_requirements(self, request: CargoRequest, vehicle: Vehicle) -> bool:
        """检查特殊要求"""
        for req in request.special_requirements:
            required_feature = self.SPECIAL_REQUIREMENT_FEATURES.get(req)
            if required_feature and required_feature not in vehicle.features:
                return False
        return True
    
    def _compute_match_score(self, request: CargoRequest, vehicle: Vehicle) -> Tuple[float, Dict]:
        """
        计算匹配分数
        
        分数 = w1*兼容性分 + w2*容量利用分 + w3*距离分 + w4*紧急响应分
        """
        details = {}
        
        # 1. 兼容性得分 (0-100)
        compatible_types = self.COMPATIBILITY_MATRIX.get(request.cargo_type, [])
        if vehicle.type in compatible_types:
            # 首选车型得更高分
            type_rank = compatible_types.index(vehicle.type)
            compatibility_score = 100 - type_rank * 10
        else:
            compatibility_score = 50  # 通用类型
        details["compatibility"] = compatibility_score
        
        # 2. 容量利用分 (最优利用率在60%-90%)
        weight_util = request.quantity_kg / vehicle.capacity_kg
        volume_util = request.volume_m3 / vehicle.capacity_m3
        utilization = max(weight_util, volume_util)
        
        if 0.6 <= utilization <= 0.9:
            capacity_score = 100
        elif utilization < 0.3:
            capacity_score = 50  # 浪费运力
        elif utilization > 0.95:
            capacity_score = 70  # 接近超载
        else:
            capacity_score = 80
        details["capacity"] = capacity_score
        
        # 3. 距离得分 (越近越好)
        distance = haversine_distance(vehicle.location, request.origin)
        if distance <= 5:
            distance_score = 100
        elif distance <= 10:
            distance_score = 90
        elif distance <= 20:
            distance_score = 70
        elif distance <= 50:
            distance_score = 50
        else:
            distance_score = 30
        details["distance"] = distance_score
        
        # 4. 紧急响应得分
        required_speed = self.URGENCY_SPEED_REQUIREMENTS.get(request.urgency, 30)
        if vehicle.avg_speed_kmh >= required_speed:
            urgency_score = 100
        else:
            urgency_score = max(30, 100 - (required_speed - vehicle.avg_speed_kmh) * 2)
        details["urgency"] = urgency_score
        
        # 5. 特殊功能加分
        bonus = 0
        for req in request.special_requirements:
            required_feature = self.SPECIAL_REQUIREMENT_FEATURES.get(req)
            if required_feature and required_feature in vehicle.features:
                bonus += 10
        details["special_bonus"] = bonus
        
        # 加权求和
        weights = self.params
        total_score = (
            weights["weight_compatibility"] * compatibility_score +
            weights["weight_capacity"] * capacity_score +
            weights["weight_distance"] * distance_score +
            weights["weight_urgency"] * urgency_score +
            bonus
        )
        
        return round(total_score, 2), details
