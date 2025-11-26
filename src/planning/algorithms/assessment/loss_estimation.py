"""
灾害损失预测算法

业务逻辑:
=========
1. 人员伤亡估算:
   - 基于灾害类型、强度、人口暴露
   - 考虑时间因素(白天/夜间)、建筑类型
   - 输出: 死亡、受伤、失踪人数及置信区间

2. 建筑损毁估算:
   - 基于脆弱性曲线 (Fragility Curves)
   - 输入: 灾害强度、建筑库存清单
   - 输出: 各损毁等级建筑数量

3. 基础设施损失估算:
   - 道路、桥梁、电力、通信、供水
   - 基于网络拓扑和节点脆弱性
   - 输出: 损毁比例、恢复时间估计

4. 经济损失估算:
   - 直接损失: 建筑、设施、库存
   - 间接损失: 停工停产、交通中断

算法实现:
=========
- 伤亡: Casualties = Population * Exposure * Vulnerability * Fatality_Rate
- 建筑损毁: P(DS>=ds|IM) = Φ((ln(IM) - μ_ds) / σ_ds)  [累积正态分布]
- 基础设施: 基于蒙特卡洛模拟和网络可靠性分析
"""
from __future__ import annotations

import math
import logging
from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from ..base import AlgorithmBase, AlgorithmResult, AlgorithmStatus

logger = logging.getLogger(__name__)


class DamageState(Enum):
    """建筑损毁状态"""
    NONE = 0        # 无损坏
    SLIGHT = 1      # 轻微
    MODERATE = 2    # 中等
    EXTENSIVE = 3   # 严重
    COMPLETE = 4    # 完全损毁


class BuildingType(Enum):
    """建筑类型"""
    WOOD = "wood"
    MASONRY = "masonry"
    RC_FRAME = "rc_frame"       # 钢筋混凝土框架
    RC_SHEAR = "rc_shear"       # 剪力墙
    STEEL = "steel"
    PREFAB = "prefab"           # 预制板


@dataclass
class CasualtyEstimate:
    """伤亡估算结果"""
    deaths: int
    deaths_range: Tuple[int, int]  # 置信区间
    injuries_severe: int
    injuries_moderate: int
    injuries_minor: int
    missing: int
    displaced: int  # 需要安置人数
    confidence: float


@dataclass
class BuildingDamageEstimate:
    """建筑损毁估算结果"""
    total_buildings: int
    damage_distribution: Dict[str, int]  # {损毁等级: 数量}
    collapse_count: int
    heavily_damaged_count: int
    economic_loss_million: float
    confidence: float


@dataclass
class InfrastructureDamageEstimate:
    """基础设施损毁估算"""
    road_damage_km: float
    road_damage_ratio: float
    bridge_damage_count: int
    power_outage_ratio: float
    power_restore_hours: int
    water_outage_ratio: float
    water_restore_hours: int
    comm_outage_ratio: float
    comm_restore_hours: int


class LossEstimator(AlgorithmBase):
    """
    灾害损失预测器
    
    使用示例:
    ```python
    estimator = LossEstimator()
    result = estimator.run({
        "disaster_type": "earthquake",
        "intensity": 8,
        "affected_area_km2": 50,
        "population_data": {
            "total": 100000,
            "density": 2000,
            "time_of_day": "night"
        },
        "building_inventory": [
            {"type": "masonry", "count": 5000, "avg_floors": 3},
            {"type": "rc_frame", "count": 3000, "avg_floors": 8}
        ]
    })
    ```
    """
    
    # 建筑脆弱性参数 (对数正态分布的μ和σ)
    # 格式: {建筑类型: {损毁等级: (μ, σ)}}
    FRAGILITY_PARAMS = {
        BuildingType.MASONRY: {
            DamageState.SLIGHT: (5.5, 0.6),
            DamageState.MODERATE: (6.5, 0.6),
            DamageState.EXTENSIVE: (7.2, 0.6),
            DamageState.COMPLETE: (7.8, 0.6),
        },
        BuildingType.RC_FRAME: {
            DamageState.SLIGHT: (6.0, 0.5),
            DamageState.MODERATE: (7.0, 0.5),
            DamageState.EXTENSIVE: (7.8, 0.5),
            DamageState.COMPLETE: (8.5, 0.5),
        },
        BuildingType.WOOD: {
            DamageState.SLIGHT: (5.0, 0.7),
            DamageState.MODERATE: (6.0, 0.7),
            DamageState.EXTENSIVE: (7.0, 0.7),
            DamageState.COMPLETE: (7.5, 0.7),
        },
        BuildingType.STEEL: {
            DamageState.SLIGHT: (6.5, 0.5),
            DamageState.MODERATE: (7.5, 0.5),
            DamageState.EXTENSIVE: (8.2, 0.5),
            DamageState.COMPLETE: (9.0, 0.5),
        },
    }
    
    # 各损毁等级的死亡率
    FATALITY_RATES = {
        DamageState.NONE: 0,
        DamageState.SLIGHT: 0.0001,
        DamageState.MODERATE: 0.001,
        DamageState.EXTENSIVE: 0.01,
        DamageState.COMPLETE: 0.1,
    }
    
    def get_default_params(self) -> Dict[str, Any]:
        return {
            "casualty_model": "simple",  # simple/hazus/pager
            "economic_model": "basic",
            "confidence_level": 0.9,
        }
    
    def validate_input(self, problem: Dict[str, Any]) -> Tuple[bool, str]:
        if "disaster_type" not in problem:
            return False, "缺少 disaster_type"
        if "intensity" not in problem:
            return False, "缺少 intensity"
        return True, ""
    
    def solve(self, problem: Dict[str, Any]) -> AlgorithmResult:
        """执行损失预测"""
        disaster_type = problem["disaster_type"]
        intensity = problem["intensity"]
        
        # 人员伤亡估算
        casualty = self._estimate_casualties(
            disaster_type=disaster_type,
            intensity=intensity,
            population_data=problem.get("population_data", {}),
            building_inventory=problem.get("building_inventory", [])
        )
        
        # 建筑损毁估算
        building_damage = self._estimate_building_damage(
            disaster_type=disaster_type,
            intensity=intensity,
            building_inventory=problem.get("building_inventory", [])
        )
        
        # 基础设施损毁估算
        infra_damage = self._estimate_infrastructure_damage(
            disaster_type=disaster_type,
            intensity=intensity,
            affected_area_km2=problem.get("affected_area_km2", 10)
        )
        
        return AlgorithmResult(
            status=AlgorithmStatus.SUCCESS,
            solution={
                "casualties": casualty,
                "building_damage": building_damage,
                "infrastructure_damage": infra_damage,
            },
            metrics={
                "estimated_deaths": casualty.deaths,
                "collapsed_buildings": building_damage.collapse_count,
                "economic_loss_million": building_damage.economic_loss_million,
            },
            trace={"disaster_type": disaster_type, "intensity": intensity},
            time_ms=0
        )
    
    def _estimate_casualties(self, disaster_type: str, intensity: float,
                             population_data: Dict, building_inventory: List[Dict]) -> CasualtyEstimate:
        """
        估算人员伤亡
        
        方法:
        1. 基于建筑损毁分布计算各损毁等级下的暴露人口
        2. 应用各等级死亡率
        3. 考虑时间因素调整(夜间室内人口更多)
        """
        total_pop = population_data.get("total", 50000)
        time_of_day = population_data.get("time_of_day", "day")
        
        # 室内人口比例 (夜间更高)
        indoor_ratio = 0.8 if time_of_day == "night" else 0.5
        indoor_pop = total_pop * indoor_ratio
        
        # 计算建筑损毁分布
        building_damage = self._estimate_building_damage(
            disaster_type, intensity, building_inventory
        )
        
        # 基于损毁分布计算伤亡
        total_buildings = building_damage.total_buildings or 1
        damage_dist = building_damage.damage_distribution
        
        deaths = 0
        severe_injuries = 0
        
        for ds_name, count in damage_dist.items():
            ds = DamageState[ds_name.upper()]
            fatality_rate = self.FATALITY_RATES.get(ds, 0)
            
            # 该损毁等级下的人口
            pop_in_ds = indoor_pop * (count / total_buildings)
            
            deaths += int(pop_in_ds * fatality_rate)
            # 重伤约为死亡的3倍
            severe_injuries += int(pop_in_ds * fatality_rate * 3)
        
        # 不确定性范围 (±30%)
        deaths_low = int(deaths * 0.7)
        deaths_high = int(deaths * 1.3)
        
        # 中等伤和轻伤
        moderate_injuries = severe_injuries * 2
        minor_injuries = severe_injuries * 5
        
        # 失踪 (约为死亡的20%)
        missing = int(deaths * 0.2)
        
        # 需要安置人口 (房屋严重损坏以上)
        displaced_ratio = (damage_dist.get("extensive", 0) + damage_dist.get("complete", 0)) / total_buildings
        displaced = int(total_pop * displaced_ratio)
        
        return CasualtyEstimate(
            deaths=deaths,
            deaths_range=(deaths_low, deaths_high),
            injuries_severe=severe_injuries,
            injuries_moderate=moderate_injuries,
            injuries_minor=minor_injuries,
            missing=missing,
            displaced=displaced,
            confidence=0.7
        )
    
    def _estimate_building_damage(self, disaster_type: str, intensity: float,
                                   building_inventory: List[Dict]) -> BuildingDamageEstimate:
        """
        估算建筑损毁
        
        使用脆弱性曲线 (Fragility Curves):
        P(DS >= ds | IM) = Φ((ln(IM) - μ) / σ)
        
        其中 Φ 是标准正态分布的累积分布函数
        """
        if not building_inventory:
            # 默认建筑库存
            building_inventory = [
                {"type": "masonry", "count": 3000, "avg_floors": 3, "avg_value_million": 0.5},
                {"type": "rc_frame", "count": 2000, "avg_floors": 6, "avg_value_million": 2.0},
            ]
        
        total_buildings = sum(b.get("count", 0) for b in building_inventory)
        
        damage_distribution = {
            "none": 0,
            "slight": 0,
            "moderate": 0,
            "extensive": 0,
            "complete": 0,
        }
        
        total_economic_loss = 0
        
        for building in building_inventory:
            b_type_str = building.get("type", "masonry")
            count = building.get("count", 0)
            avg_value = building.get("avg_value_million", 1.0)
            
            # 映射建筑类型
            b_type = self._map_building_type(b_type_str)
            
            # 获取脆弱性参数
            fragility = self.FRAGILITY_PARAMS.get(b_type, self.FRAGILITY_PARAMS[BuildingType.MASONRY])
            
            # 计算各损毁等级的概率
            probs = self._compute_damage_probabilities(intensity, fragility)
            
            # 分配建筑数量
            for ds, prob in probs.items():
                ds_name = ds.name.lower()
                damage_distribution[ds_name] += int(count * prob)
            
            # 计算经济损失
            loss_ratios = {
                DamageState.NONE: 0,
                DamageState.SLIGHT: 0.02,
                DamageState.MODERATE: 0.1,
                DamageState.EXTENSIVE: 0.5,
                DamageState.COMPLETE: 1.0,
            }
            for ds, prob in probs.items():
                total_economic_loss += count * avg_value * loss_ratios[ds] * prob
        
        collapse_count = damage_distribution["complete"]
        heavily_damaged = damage_distribution["extensive"] + collapse_count
        
        return BuildingDamageEstimate(
            total_buildings=total_buildings,
            damage_distribution=damage_distribution,
            collapse_count=collapse_count,
            heavily_damaged_count=heavily_damaged,
            economic_loss_million=round(total_economic_loss, 2),
            confidence=0.75
        )
    
    def _compute_damage_probabilities(self, intensity: float,
                                       fragility: Dict[DamageState, Tuple[float, float]]) -> Dict[DamageState, float]:
        """
        计算各损毁等级的概率
        
        使用累积概率差值法
        """
        from scipy.stats import norm
        
        # 计算累积概率 P(DS >= ds)
        cum_probs = {}
        for ds in [DamageState.SLIGHT, DamageState.MODERATE, DamageState.EXTENSIVE, DamageState.COMPLETE]:
            mu, sigma = fragility.get(ds, (8, 0.6))
            z = (math.log(intensity) - math.log(mu)) / sigma if intensity > 0 else -10
            cum_probs[ds] = norm.cdf(z)
        
        # 计算各等级的独立概率
        probs = {
            DamageState.COMPLETE: cum_probs[DamageState.COMPLETE],
            DamageState.EXTENSIVE: cum_probs[DamageState.EXTENSIVE] - cum_probs[DamageState.COMPLETE],
            DamageState.MODERATE: cum_probs[DamageState.MODERATE] - cum_probs[DamageState.EXTENSIVE],
            DamageState.SLIGHT: cum_probs[DamageState.SLIGHT] - cum_probs[DamageState.MODERATE],
            DamageState.NONE: 1 - cum_probs[DamageState.SLIGHT],
        }
        
        # 确保非负
        return {k: max(0, v) for k, v in probs.items()}
    
    def _map_building_type(self, type_str: str) -> BuildingType:
        """映射建筑类型字符串到枚举"""
        mapping = {
            "wood": BuildingType.WOOD,
            "masonry": BuildingType.MASONRY,
            "brick": BuildingType.MASONRY,
            "rc_frame": BuildingType.RC_FRAME,
            "concrete": BuildingType.RC_FRAME,
            "rc_shear": BuildingType.RC_SHEAR,
            "steel": BuildingType.STEEL,
            "prefab": BuildingType.PREFAB,
        }
        return mapping.get(type_str.lower(), BuildingType.MASONRY)
    
    def _estimate_infrastructure_damage(self, disaster_type: str, intensity: float,
                                         affected_area_km2: float) -> InfrastructureDamageEstimate:
        """
        估算基础设施损毁
        
        基于经验公式和灾害强度
        """
        # 道路损毁 (与烈度和面积相关)
        road_density_km_per_km2 = 2  # 假设道路密度
        total_road_km = affected_area_km2 * road_density_km_per_km2
        
        # 损毁比例 (烈度>=7开始显著损坏)
        if disaster_type == "earthquake":
            damage_ratio = max(0, (intensity - 6) / 4) ** 2
        elif disaster_type == "flood":
            damage_ratio = min(0.5, intensity / 20)  # intensity = 水深(m)
        else:
            damage_ratio = 0.1
        
        damage_ratio = min(0.8, damage_ratio)
        road_damage_km = total_road_km * damage_ratio
        
        # 桥梁损毁 (假设每10km²有1座桥)
        bridge_count = int(affected_area_km2 / 10)
        bridge_damage_rate = damage_ratio * 0.5  # 桥梁更坚固
        bridge_damage_count = int(bridge_count * bridge_damage_rate)
        
        # 电力中断
        power_outage_ratio = damage_ratio * 0.8
        power_restore_hours = int(24 + 48 * damage_ratio)
        
        # 供水中断
        water_outage_ratio = damage_ratio * 0.6
        water_restore_hours = int(12 + 36 * damage_ratio)
        
        # 通信中断
        comm_outage_ratio = damage_ratio * 0.4
        comm_restore_hours = int(6 + 24 * damage_ratio)
        
        return InfrastructureDamageEstimate(
            road_damage_km=round(road_damage_km, 1),
            road_damage_ratio=round(damage_ratio, 2),
            bridge_damage_count=bridge_damage_count,
            power_outage_ratio=round(power_outage_ratio, 2),
            power_restore_hours=power_restore_hours,
            water_outage_ratio=round(water_outage_ratio, 2),
            water_restore_hours=water_restore_hours,
            comm_outage_ratio=round(comm_outage_ratio, 2),
            comm_restore_hours=comm_restore_hours,
        )
