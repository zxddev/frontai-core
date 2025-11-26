"""
灾情等级评估算法

业务逻辑:
=========
1. 地震评估:
   - 输入: 震级、震源深度、震中位置、人口密度、建筑脆弱性
   - 计算烈度衰减 (基于USGS ShakeMap模型简化版)
   - 估算影响范围和人口
   - 输出灾情等级 I/II/III/IV

2. 洪涝评估:
   - 输入: 降雨量、持续时间、地形坡度、排水能力
   - 计算积水深度和范围
   - 评估交通影响

3. 危化品评估:
   - 输入: 化学品类型、泄漏速率、风速风向
   - 高斯烟羽模型计算扩散范围
   - 划定危险区域等级

算法实现:
=========
- 地震烈度衰减: I = M - k*log10(R) - c*R + site_factor
- 建筑损毁率: P(damage|I) = Φ((ln(I) - μ) / σ)  [脆弱性曲线]
- 洪涝积水: depth = (rainfall - drainage) * duration / area
- 高斯烟羽: C(x,y,z) = Q/(2πσyσzu) * exp(-y²/2σy²) * exp(-(z-H)²/2σz²)
"""
from __future__ import annotations

import math
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus, Location

logger = logging.getLogger(__name__)


class DisasterLevel(Enum):
    """灾情等级"""
    I = "I"    # 特别重大
    II = "II"   # 重大
    III = "III" # 较大
    IV = "IV"   # 一般


@dataclass
class EarthquakeParams:
    """地震参数"""
    magnitude: float          # 震级 (里氏)
    depth_km: float          # 震源深度 (km)
    epicenter: Location      # 震中位置
    population_density: float # 人口密度 (人/km²)
    building_vulnerability: float  # 建筑脆弱性系数 0-1


@dataclass
class FloodParams:
    """洪涝参数"""
    rainfall_mm: float       # 累计降雨量 (mm)
    duration_hours: float    # 降雨持续时间 (h)
    terrain_slope: float     # 地形坡度 (度)
    drainage_capacity: float # 排水能力 (mm/h)
    affected_area_km2: float # 影响区域面积


@dataclass
class HazmatParams:
    """危化品泄漏参数"""
    chemical_type: str       # 化学品类型
    leak_rate_kg_s: float   # 泄漏速率 (kg/s)
    wind_speed_ms: float    # 风速 (m/s)
    wind_direction: float   # 风向 (度, 北为0)
    source_location: Location
    atmospheric_stability: str  # 大气稳定度 A-F


@dataclass
class AssessmentResult:
    """评估结果"""
    disaster_type: str
    level: DisasterLevel
    affected_area_km2: float
    affected_population: int
    estimated_casualties: Dict[str, int]  # {"deaths": x, "injuries": y}
    intensity_map: Optional[Dict] = None  # 烈度/浓度分布图
    risk_zones: Optional[List[Dict]] = None  # 风险区域列表
    confidence: float = 0.8


class DisasterAssessment(AlgorithmBase):
    """
    灾情快速评估算法
    
    使用示例:
    ```python
    assessor = DisasterAssessment()
    result = assessor.run({
        "disaster_type": "earthquake",
        "params": {
            "magnitude": 6.5,
            "depth_km": 10,
            "epicenter": {"lat": 31.23, "lng": 121.47},
            "population_density": 5000,
            "building_vulnerability": 0.6
        }
    })
    ```
    """
    
    # 地震烈度衰减模型参数 (简化版)
    INTENSITY_ATTENUATION = {
        "k": 1.5,   # 对数衰减系数
        "c": 0.003, # 线性衰减系数
    }
    
    # 灾情等级划分标准
    LEVEL_THRESHOLDS = {
        "earthquake": {
            "I": {"magnitude": 7.0, "casualties": 100},
            "II": {"magnitude": 6.0, "casualties": 50},
            "III": {"magnitude": 5.0, "casualties": 10},
            "IV": {"magnitude": 4.0, "casualties": 0},
        },
        "flood": {
            "I": {"affected_population": 100000, "depth_m": 2.0},
            "II": {"affected_population": 50000, "depth_m": 1.0},
            "III": {"affected_population": 10000, "depth_m": 0.5},
            "IV": {"affected_population": 1000, "depth_m": 0.3},
        },
        "hazmat": {
            "I": {"affected_population": 10000, "toxicity": "high"},
            "II": {"affected_population": 5000, "toxicity": "medium"},
            "III": {"affected_population": 1000, "toxicity": "low"},
            "IV": {"affected_population": 100, "toxicity": "low"},
        }
    }
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "intensity_radius_km": 50,  # 烈度计算最大半径
            "grid_resolution_km": 1,    # 网格分辨率
            "casualty_model": "simple", # 伤亡模型: simple/pager
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "disaster_type" not in problem:
            return False, "缺少 disaster_type 字段"
        if "params" not in problem:
            return False, "缺少 params 字段"
        
        dtype = problem["disaster_type"]
        if dtype not in ["earthquake", "flood", "hazmat"]:
            return False, f"不支持的灾害类型: {dtype}"
        
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行灾情评估"""
        dtype = problem["disaster_type"]
        params = problem["params"]
        
        if dtype == "earthquake":
            result = self._assess_earthquake(params)
        elif dtype == "flood":
            result = self._assess_flood(params)
        elif dtype == "hazmat":
            result = self._assess_hazmat(params)
        else:
            return AlgorithmResult(
                status=AlgorithmStatus.ERROR,
                solution=None,
                metrics={},
                trace={},
                time_ms=0,
                message=f"不支持的灾害类型: {dtype}"
            )
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution=result,
            metrics={
                "level": result.level.value,
                "affected_area_km2": result.affected_area_km2,
                "affected_population": result.affected_population,
                "confidence": result.confidence,
            },
            trace={
                "disaster_type": dtype,
                "input_params": params,
            },
            time_ms=0
        )
    
    def _assess_earthquake(self, params: Dict) -> AssessmentResult:
        """
        地震灾情评估
        
        算法步骤:
        1. 计算烈度分布 (衰减模型)
        2. 估算建筑损毁率 (脆弱性曲线)
        3. 估算人员伤亡
        4. 确定灾情等级
        """
        eq = EarthquakeParams(
            magnitude=params["magnitude"],
            depth_km=params["depth_km"],
            epicenter=Location.from_dict(params["epicenter"]),
            population_density=params.get("population_density", 1000),
            building_vulnerability=params.get("building_vulnerability", 0.5)
        )
        
        # 1. 计算烈度分布
        intensity_map = self._compute_intensity_map(eq)
        
        # 2. 估算影响范围 (烈度>=VI的区域)
        affected_area = self._compute_affected_area(intensity_map, threshold=6)
        
        # 3. 估算受影响人口
        affected_pop = int(affected_area * eq.population_density)
        
        # 4. 估算伤亡 (简化模型)
        casualties = self._estimate_earthquake_casualties(
            eq.magnitude, eq.depth_km, affected_pop, eq.building_vulnerability
        )
        
        # 5. 确定灾情等级
        level = self._classify_earthquake_level(eq.magnitude, casualties["deaths"])
        
        return AssessmentResult(
            disaster_type="earthquake",
            level=level,
            affected_area_km2=affected_area,
            affected_population=affected_pop,
            estimated_casualties=casualties,
            intensity_map=intensity_map,
            confidence=0.75
        )
    
    def _compute_intensity_map(self, eq: EarthquakeParams) -> Dict:
        """
        计算地震烈度分布
        
        烈度衰减公式 (简化版):
        I(R) = 1.5*M - 1.5*log10(R) - 0.003*R + 3.0
        
        其中:
        - M: 震级
        - R: 震中距 (km)
        """
        k = self.INTENSITY_ATTENUATION["k"]
        c = self.INTENSITY_ATTENUATION["c"]
        
        # 计算不同距离的烈度
        distances = [0, 5, 10, 20, 30, 50, 80, 100]
        intensity_profile = {}
        
        for r in distances:
            if r == 0:
                r = 0.1  # 避免log(0)
            
            # 烈度计算 (修正震源深度影响)
            hypo_dist = math.sqrt(r**2 + eq.depth_km**2)
            intensity = 1.5 * eq.magnitude - k * math.log10(hypo_dist) - c * hypo_dist + 3.0
            intensity = max(1, min(12, intensity))  # 限制在1-12度
            
            intensity_profile[r] = round(intensity, 1)
        
        return {
            "epicenter": eq.epicenter.to_tuple(),
            "magnitude": eq.magnitude,
            "depth_km": eq.depth_km,
            "profile": intensity_profile,
            "max_intensity": max(intensity_profile.values()),
        }
    
    def _compute_affected_area(self, intensity_map: Dict, threshold: float = 6) -> float:
        """计算受影响面积 (烈度>=阈值的区域)"""
        profile = intensity_map["profile"]
        
        # 找到烈度低于阈值的最近距离
        for dist, intensity in sorted(profile.items()):
            if intensity < threshold:
                # 近似为圆形区域
                return math.pi * (dist ** 2)
        
        # 如果所有距离都超过阈值
        return math.pi * (max(profile.keys()) ** 2)
    
    def _estimate_earthquake_casualties(self, magnitude: float, depth: float,
                                        affected_pop: int, vulnerability: float) -> Dict[str, int]:
        """
        估算地震伤亡
        
        简化模型:
        - 死亡率 = base_rate * magnitude_factor * depth_factor * vulnerability
        - 受伤 = 死亡 * 3 (经验比例)
        """
        # 基础死亡率 (每万人)
        base_rate = 0.001
        
        # 震级因子 (指数增长)
        magnitude_factor = 10 ** (magnitude - 5)
        
        # 深度因子 (浅源更危险)
        depth_factor = max(0.5, 2 - depth / 20)
        
        # 计算死亡人数
        death_rate = base_rate * magnitude_factor * depth_factor * vulnerability
        deaths = int(affected_pop * death_rate)
        
        # 受伤人数 (约为死亡的3倍)
        injuries = deaths * 3
        
        return {
            "deaths": deaths,
            "injuries": injuries,
            "missing": int(deaths * 0.2),  # 失踪约为死亡的20%
        }
    
    def _classify_earthquake_level(self, magnitude: float, deaths: int) -> DisasterLevel:
        """确定地震灾情等级"""
        thresholds = self.LEVEL_THRESHOLDS["earthquake"]
        
        if magnitude >= thresholds["I"]["magnitude"] or deaths >= thresholds["I"]["casualties"]:
            return DisasterLevel.I
        elif magnitude >= thresholds["II"]["magnitude"] or deaths >= thresholds["II"]["casualties"]:
            return DisasterLevel.II
        elif magnitude >= thresholds["III"]["magnitude"] or deaths >= thresholds["III"]["casualties"]:
            return DisasterLevel.III
        else:
            return DisasterLevel.IV
    
    def _assess_flood(self, params: Dict) -> AssessmentResult:
        """
        洪涝灾情评估
        
        算法步骤:
        1. 计算积水深度 = (降雨量 - 排水能力) * 时间 / 汇水面积
        2. 估算淹没范围 (基于DEM简化)
        3. 评估交通影响
        """
        flood = FloodParams(
            rainfall_mm=params["rainfall_mm"],
            duration_hours=params["duration_hours"],
            terrain_slope=params.get("terrain_slope", 1),
            drainage_capacity=params.get("drainage_capacity", 30),
            affected_area_km2=params.get("affected_area_km2", 10)
        )
        
        # 计算净积水量 (mm)
        net_rainfall = max(0, flood.rainfall_mm - flood.drainage_capacity * flood.duration_hours)
        
        # 估算积水深度 (m) - 考虑地形坡度
        slope_factor = max(0.1, 1 - flood.terrain_slope / 10)
        water_depth_m = (net_rainfall / 1000) * slope_factor * 5  # 简化系数
        
        # 估算受影响人口 (假设城区人口密度)
        pop_density = params.get("population_density", 3000)
        affected_pop = int(flood.affected_area_km2 * pop_density)
        
        # 估算伤亡 (洪涝伤亡相对较低)
        death_rate = 0.0001 if water_depth_m < 1 else 0.001
        casualties = {
            "deaths": int(affected_pop * death_rate),
            "injuries": int(affected_pop * death_rate * 5),
            "missing": int(affected_pop * death_rate * 0.5),
        }
        
        # 确定等级
        level = self._classify_flood_level(affected_pop, water_depth_m)
        
        return AssessmentResult(
            disaster_type="flood",
            level=level,
            affected_area_km2=flood.affected_area_km2,
            affected_population=affected_pop,
            estimated_casualties=casualties,
            risk_zones=[{
                "type": "waterlogging",
                "depth_m": water_depth_m,
                "area_km2": flood.affected_area_km2
            }],
            confidence=0.7
        )
    
    def _classify_flood_level(self, affected_pop: int, depth_m: float) -> DisasterLevel:
        """确定洪涝灾情等级"""
        thresholds = self.LEVEL_THRESHOLDS["flood"]
        
        if affected_pop >= thresholds["I"]["affected_population"] or depth_m >= thresholds["I"]["depth_m"]:
            return DisasterLevel.I
        elif affected_pop >= thresholds["II"]["affected_population"] or depth_m >= thresholds["II"]["depth_m"]:
            return DisasterLevel.II
        elif affected_pop >= thresholds["III"]["affected_population"] or depth_m >= thresholds["III"]["depth_m"]:
            return DisasterLevel.III
        else:
            return DisasterLevel.IV
    
    def _assess_hazmat(self, params: Dict) -> AssessmentResult:
        """
        危化品泄漏评估
        
        算法: 高斯烟羽模型 (Gaussian Plume Model)
        
        C(x,y,z) = Q / (2π * σy * σz * u) * exp(-y²/2σy²) * [exp(-(z-H)²/2σz²) + exp(-(z+H)²/2σz²)]
        
        其中:
        - Q: 泄漏速率 (kg/s)
        - u: 风速 (m/s)
        - σy, σz: 扩散参数 (取决于大气稳定度和距离)
        - H: 释放高度 (m)
        """
        hazmat = HazmatParams(
            chemical_type=params["chemical_type"],
            leak_rate_kg_s=params["leak_rate_kg_s"],
            wind_speed_ms=params["wind_speed_ms"],
            wind_direction=params["wind_direction"],
            source_location=Location.from_dict(params["source_location"]),
            atmospheric_stability=params.get("atmospheric_stability", "D")
        )
        
        # 获取化学品毒性阈值
        toxicity_threshold = self._get_toxicity_threshold(hazmat.chemical_type)
        
        # 计算危险区半径 (简化计算)
        danger_radius_m = self._compute_hazmat_radius(
            hazmat.leak_rate_kg_s,
            hazmat.wind_speed_ms,
            toxicity_threshold,
            hazmat.atmospheric_stability
        )
        
        # 转换为面积 (考虑风向的扇形区域)
        affected_area = math.pi * (danger_radius_m / 1000) ** 2 * 0.5  # 下风向半圆
        
        # 估算受影响人口
        pop_density = params.get("population_density", 2000)
        affected_pop = int(affected_area * pop_density)
        
        # 伤亡估算 (取决于毒性和疏散速度)
        toxicity_factor = {"high": 0.01, "medium": 0.001, "low": 0.0001}.get(
            self._classify_toxicity(hazmat.chemical_type), 0.001
        )
        casualties = {
            "deaths": int(affected_pop * toxicity_factor),
            "injuries": int(affected_pop * toxicity_factor * 10),
            "missing": 0,
        }
        
        # 确定等级
        level = self._classify_hazmat_level(affected_pop, hazmat.chemical_type)
        
        return AssessmentResult(
            disaster_type="hazmat",
            level=level,
            affected_area_km2=affected_area,
            affected_population=affected_pop,
            estimated_casualties=casualties,
            risk_zones=[
                {"type": "lethal", "radius_m": danger_radius_m * 0.3},
                {"type": "danger", "radius_m": danger_radius_m * 0.6},
                {"type": "warning", "radius_m": danger_radius_m},
            ],
            confidence=0.65
        )
    
    def _get_toxicity_threshold(self, chemical_type: str) -> float:
        """获取化学品毒性阈值 (mg/m³)"""
        thresholds = {
            "ammonia": 300,      # 氨气
            "chlorine": 10,      # 氯气
            "hydrogen_sulfide": 50,  # 硫化氢
            "carbon_monoxide": 400,  # 一氧化碳
            "benzene": 500,      # 苯
            "default": 100,
        }
        return thresholds.get(chemical_type, thresholds["default"])
    
    def _classify_toxicity(self, chemical_type: str) -> str:
        """分类化学品毒性等级"""
        high_toxicity = ["chlorine", "hydrogen_sulfide", "phosgene"]
        medium_toxicity = ["ammonia", "carbon_monoxide", "sulfur_dioxide"]
        
        if chemical_type in high_toxicity:
            return "high"
        elif chemical_type in medium_toxicity:
            return "medium"
        else:
            return "low"
    
    def _compute_hazmat_radius(self, leak_rate: float, wind_speed: float,
                               threshold: float, stability: str) -> float:
        """
        计算危险区半径 (简化高斯模型)
        
        稳定度参数 (Pasquill-Gifford)
        """
        # 扩散系数 (取决于稳定度)
        stability_factors = {
            "A": 0.22, "B": 0.16, "C": 0.11,
            "D": 0.08, "E": 0.06, "F": 0.04
        }
        sigma_factor = stability_factors.get(stability, 0.08)
        
        # 简化计算: 沿风向轴浓度 C = Q / (π * σy * σz * u)
        # 令 C = threshold, 求 x (距离)
        # σy ≈ σ_factor * x, σz ≈ σ_factor * x * 0.7
        
        # Q / (π * (σf*x)² * 0.7 * u) = threshold
        # x² = Q / (π * σf² * 0.7 * u * threshold)
        
        denominator = math.pi * (sigma_factor ** 2) * 0.7 * wind_speed * (threshold / 1000)
        if denominator <= 0:
            return 1000  # 默认1km
        
        x_squared = (leak_rate * 1000) / denominator  # 转换单位
        radius = math.sqrt(max(0, x_squared))
        
        return min(5000, max(100, radius))  # 限制在100m-5km
    
    def _classify_hazmat_level(self, affected_pop: int, chemical_type: str) -> DisasterLevel:
        """确定危化品泄漏灾情等级"""
        toxicity = self._classify_toxicity(chemical_type)
        thresholds = self.LEVEL_THRESHOLDS["hazmat"]
        
        # 高毒性降低阈值
        toxicity_multiplier = {"high": 0.5, "medium": 1.0, "low": 2.0}.get(toxicity, 1.0)
        
        if affected_pop >= thresholds["I"]["affected_population"] * toxicity_multiplier:
            return DisasterLevel.I
        elif affected_pop >= thresholds["II"]["affected_population"] * toxicity_multiplier:
            return DisasterLevel.II
        elif affected_pop >= thresholds["III"]["affected_population"] * toxicity_multiplier:
            return DisasterLevel.III
        else:
            return DisasterLevel.IV
