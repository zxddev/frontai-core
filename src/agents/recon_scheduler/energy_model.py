"""
动态能耗模型

基于 spec.md Requirement: Dynamic Energy Model 实现。
考虑风速、温度、载荷、电池老化、爬升、悬停等因素。

公式:
E_total = E_base * k_wind * k_temp * k_payload * k_age + E_climb + E_hover

单位:
- Energy: 电量百分比 (0-100%)
- Distance: 米 (m)
- Speed: 米/秒 (m/s)
- Temperature: 摄氏度 (°C)
- Payload: 千克 (kg)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .mock_data.providers.base_provider import DeviceProfile, EnergyParams


@dataclass
class EnergyFactors:
    """能耗因子配置"""
    wind_coefficient: float = 0.5       # 风速影响系数
    cold_temp_threshold: float = 0.0    # 低温阈值 (°C)
    cold_temp_factor: float = 1.3       # 低温系数
    hot_temp_threshold: float = 35.0    # 高温阈值 (°C)
    hot_temp_factor: float = 1.1        # 高温系数
    payload_coefficient: float = 0.3    # 载荷影响系数
    age_base_cycles: int = 500          # 电池老化基准循环数
    age_coefficient: float = 0.2        # 电池老化系数
    rth_safety_factor: float = 1.3      # RTH安全系数
    rth_margin_percent: float = 10.0    # RTH触发余量


# 默认因子配置
DEFAULT_FACTORS = EnergyFactors()


def calculate_headwind(
    wind_speed_ms: float,
    wind_direction_deg: float,
    heading_deg: float
) -> float:
    """
    计算逆风分量
    
    Args:
        wind_speed_ms: 风速 (m/s)
        wind_direction_deg: 风向 (度, 0=北, 表示风从北方吹来)
        heading_deg: 航向 (度, 0=北, 表示飞机向北飞)
    
    Returns:
        逆风分量 (m/s), 正值为逆风, 负值为顺风(按0处理)
    
    Note:
        风向表示风吹来的方向，需要转换为风吹去的方向(+180度)
        风吹去方向与航向相反时为逆风
        v_headwind = wind_speed * cos(wind_to_direction - heading)
        其中 wind_to_direction = wind_direction + 180
        
        示例:
        - 风从北吹来(0度), 风向南吹去(180度)
        - 飞机向北飞(0度), 逆风: cos(180-0) = -1, headwind = wind * (-1)
        - 需要取反: headwind = -wind * cos(wind_dir - heading)
    """
    # 风向是风吹来的方向，飞机逆风飞行时：
    # 风从正前方吹来意味着 wind_direction == heading
    # cos(0) = 1, 所以逆风分量 = wind_speed * cos(wind_dir - heading)
    angle_diff = math.radians(wind_direction_deg - heading_deg)
    # 风从正前方吹来(angle_diff=0)时cos=1，是逆风
    headwind = wind_speed_ms * math.cos(angle_diff)
    return max(0.0, headwind)  # 顺风按0处理


def calculate_wind_factor(
    headwind_ms: float,
    cruise_speed_ms: float,
    coefficient: float = DEFAULT_FACTORS.wind_coefficient
) -> float:
    """
    计算风速影响因子
    
    k_wind = 1 + coefficient * headwind / cruise_speed
    """
    if cruise_speed_ms <= 0:
        return 1.0
    return 1.0 + coefficient * headwind_ms / cruise_speed_ms


def calculate_temp_factor(
    temp_c: float,
    factors: EnergyFactors = DEFAULT_FACTORS
) -> float:
    """
    计算温度影响因子
    
    k_temp = 1.3 if temp < 0 else (1.1 if temp > 35 else 1.0)
    """
    if temp_c < factors.cold_temp_threshold:
        return factors.cold_temp_factor
    elif temp_c > factors.hot_temp_threshold:
        return factors.hot_temp_factor
    return 1.0


def calculate_payload_factor(
    payload_kg: float,
    max_payload_kg: float,
    coefficient: float = DEFAULT_FACTORS.payload_coefficient
) -> float:
    """
    计算载荷影响因子
    
    k_payload = 1 + payload_kg / max_payload_kg * coefficient
    """
    if max_payload_kg <= 0 or payload_kg <= 0:
        return 1.0
    return 1.0 + (payload_kg / max_payload_kg) * coefficient


def calculate_age_factor(
    cycle_count: int,
    base_cycles: int = DEFAULT_FACTORS.age_base_cycles,
    coefficient: float = DEFAULT_FACTORS.age_coefficient
) -> float:
    """
    计算电池老化因子
    
    k_age = 1 + cycle_count / base_cycles * coefficient
    """
    if cycle_count <= 0:
        return 1.0
    return 1.0 + (cycle_count / base_cycles) * coefficient


def calculate_energy(
    distance_m: float,
    altitude_gain_m: float,
    hover_time_s: float,
    wind_speed_ms: float,
    wind_direction_deg: float,
    heading_deg: float,
    temp_c: float,
    payload_kg: float,
    device_profile: DeviceProfile,
    cycle_count: Optional[int] = None,
    factors: EnergyFactors = DEFAULT_FACTORS
) -> float:
    """
    计算总能耗
    
    Args:
        distance_m: 飞行距离 (m)
        altitude_gain_m: 爬升高度 (m)
        hover_time_s: 悬停时间 (s)
        wind_speed_ms: 风速 (m/s)
        wind_direction_deg: 风向 (度)
        heading_deg: 航向 (度)
        temp_c: 温度 (°C)
        payload_kg: 载荷 (kg)
        device_profile: 设备配置
        cycle_count: 电池循环次数 (可选, 默认从profile获取)
        factors: 能耗因子配置
    
    Returns:
        总能耗 (电量百分比 0-100)
    
    Formula:
        E_total = E_base * k_wind * k_temp * k_payload * k_age + E_climb + E_hover
    """
    params = device_profile.energy_params
    
    # 基础能耗: distance / 1000 * base_consumption_per_km
    e_base = (distance_m / 1000.0) * params.base_consumption_per_km
    
    # 计算各影响因子
    headwind = calculate_headwind(wind_speed_ms, wind_direction_deg, heading_deg)
    k_wind = calculate_wind_factor(headwind, params.cruise_speed_ms, factors.wind_coefficient)
    k_temp = calculate_temp_factor(temp_c, factors)
    k_payload = calculate_payload_factor(payload_kg, params.max_payload_kg, factors.payload_coefficient)
    
    # 电池老化因子
    if cycle_count is None:
        # 从battery_health_factor反推 (如果有)
        k_age = params.battery_health_factor
    else:
        k_age = calculate_age_factor(cycle_count, factors.age_base_cycles, factors.age_coefficient)
    
    # 爬升能耗: altitude_gain / 100 * climb_consumption_per_100m
    e_climb = (altitude_gain_m / 100.0) * params.climb_consumption_per_100m if altitude_gain_m > 0 else 0.0
    
    # 悬停能耗: hover_time / 60 * hover_consumption_per_min
    e_hover = (hover_time_s / 60.0) * params.hover_consumption_per_min if hover_time_s > 0 else 0.0
    
    # 总能耗
    e_total = e_base * k_wind * k_temp * k_payload * k_age + e_climb + e_hover
    
    return e_total


def calculate_energy_simple(
    distance_m: float,
    energy_params: EnergyParams
) -> float:
    """
    简化能耗计算 (仅基于距离, 用于L1粗略估算)
    
    Args:
        distance_m: 飞行距离 (m)
        energy_params: 能耗参数
    
    Returns:
        能耗 (电量百分比)
    """
    return (distance_m / 1000.0) * energy_params.base_consumption_per_km


def calculate_rth_required(
    distance_to_home_m: float,
    cruise_speed_ms: float,
    power_rate_per_s: float,
    safety_factor: float = DEFAULT_FACTORS.rth_safety_factor
) -> float:
    """
    计算RTH所需电量
    
    Args:
        distance_to_home_m: 到起飞点距离 (m)
        cruise_speed_ms: 巡航速度 (m/s)
        power_rate_per_s: 每秒能耗 (%/s)
        safety_factor: 安全系数 (默认1.3)
    
    Returns:
        RTH所需电量 (百分比)
    
    Formula:
        RTH_required = (distance / speed) * power_rate * safety_factor
    """
    if cruise_speed_ms <= 0:
        return 100.0  # 无法计算, 返回最大值
    
    flight_time_s = distance_to_home_m / cruise_speed_ms
    return flight_time_s * power_rate_per_s * safety_factor


def calculate_rth_required_from_profile(
    distance_to_home_m: float,
    device_profile: DeviceProfile,
    safety_factor: float = DEFAULT_FACTORS.rth_safety_factor
) -> float:
    """
    基于设备配置计算RTH所需电量
    
    Args:
        distance_to_home_m: 到起飞点距离 (m)
        device_profile: 设备配置
        safety_factor: 安全系数
    
    Returns:
        RTH所需电量 (百分比)
    """
    params = device_profile.energy_params
    # 每秒能耗 = base_consumption_per_km / 1000 * cruise_speed
    power_rate_per_s = (params.base_consumption_per_km / 1000.0) * params.cruise_speed_ms / params.cruise_speed_ms
    # 简化: power_rate = base_consumption_per_km / 1000 (每米能耗)
    power_rate_per_m = params.base_consumption_per_km / 1000.0
    
    return distance_to_home_m * power_rate_per_m * safety_factor


def should_trigger_rth(
    battery_percent: float,
    rth_required_percent: float,
    margin_percent: float = DEFAULT_FACTORS.rth_margin_percent
) -> bool:
    """
    判断是否应触发RTH
    
    Args:
        battery_percent: 当前电量 (%)
        rth_required_percent: RTH所需电量 (%)
        margin_percent: 触发余量 (默认10%)
    
    Returns:
        True if should trigger RTH
    
    Formula:
        Trigger RTH when: battery < rth_required + margin
    """
    return battery_percent < (rth_required_percent + margin_percent)


def estimate_flight_time(
    distance_m: float,
    cruise_speed_ms: float
) -> float:
    """
    估算飞行时间
    
    Args:
        distance_m: 飞行距离 (m)
        cruise_speed_ms: 巡航速度 (m/s)
    
    Returns:
        飞行时间 (秒)
    """
    if cruise_speed_ms <= 0:
        return float('inf')
    return distance_m / cruise_speed_ms


def check_flight_time_constraint(
    distance_m: float,
    cruise_speed_ms: float,
    max_flight_time_min: float
) -> bool:
    """
    检查是否满足最大飞行时间约束
    
    Args:
        distance_m: 飞行距离 (m)
        cruise_speed_ms: 巡航速度 (m/s)
        max_flight_time_min: 最大飞行时间 (分钟)
    
    Returns:
        True if within constraint
    """
    flight_time_s = estimate_flight_time(distance_m, cruise_speed_ms)
    return flight_time_s <= max_flight_time_min * 60


class EnergyCalculator:
    """能耗计算器 (封装类)"""
    
    def __init__(
        self,
        device_profile: DeviceProfile,
        factors: EnergyFactors = DEFAULT_FACTORS
    ):
        self.profile = device_profile
        self.factors = factors
    
    def calculate(
        self,
        distance_m: float,
        altitude_gain_m: float = 0.0,
        hover_time_s: float = 0.0,
        wind_speed_ms: float = 0.0,
        wind_direction_deg: float = 0.0,
        heading_deg: float = 0.0,
        temp_c: float = 25.0,
        payload_kg: float = 0.0,
        cycle_count: Optional[int] = None
    ) -> float:
        """计算总能耗"""
        return calculate_energy(
            distance_m=distance_m,
            altitude_gain_m=altitude_gain_m,
            hover_time_s=hover_time_s,
            wind_speed_ms=wind_speed_ms,
            wind_direction_deg=wind_direction_deg,
            heading_deg=heading_deg,
            temp_c=temp_c,
            payload_kg=payload_kg,
            device_profile=self.profile,
            cycle_count=cycle_count,
            factors=self.factors
        )
    
    def calculate_rth(self, distance_to_home_m: float) -> float:
        """计算RTH所需电量"""
        return calculate_rth_required_from_profile(
            distance_to_home_m=distance_to_home_m,
            device_profile=self.profile,
            safety_factor=self.factors.rth_safety_factor
        )
    
    def should_rth(self, battery_percent: float, distance_to_home_m: float) -> bool:
        """判断是否应触发RTH"""
        rth_required = self.calculate_rth(distance_to_home_m)
        return should_trigger_rth(
            battery_percent=battery_percent,
            rth_required_percent=rth_required,
            margin_percent=self.factors.rth_margin_percent
        )
