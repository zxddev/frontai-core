"""
Phase 3: 资源盘点节点

盘点可用设备、评估设备能力、估计就绪时间。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..state import (
    ReconSchedulerState,
    ResourceInventory,
    DeviceStatus,
)
from ..config import get_weather_rules
from ..mock_data import get_device_provider

logger = logging.getLogger(__name__)


async def resource_inventory_node(state: ReconSchedulerState) -> Dict[str, Any]:
    """
    资源盘点节点
    
    输入:
        - environment_assessment: 环境评估结果
        - event_id: 事件ID（用于查询数据库）
        - scenario_id: 场景ID
    
    输出:
        - resource_inventory: 资源盘点结果
        - available_devices: 可用设备列表
    """
    logger.info("Phase 3: 资源盘点")
    
    environment = state.get("environment_assessment", {})
    flight_condition = state.get("flight_condition", "green")
    event_id = state.get("event_id", "")
    scenario_id = state.get("scenario_id", "")
    
    weather_rules = get_weather_rules()
    weather = environment.get("weather", {})
    
    # 查询数据库获取设备
    # 这里使用模拟数据，实际应该从数据库查询
    all_devices = await _query_devices_from_db(event_id, scenario_id)
    
    # 根据天气条件筛选可用设备
    available_devices = _filter_by_weather(all_devices, weather, weather_rules, flight_condition)
    
    # 按类型分组
    devices_by_type = _group_by_type(available_devices)
    devices_by_category = _group_by_category(available_devices)
    
    # 统计能力
    total_flight_time = sum(d.get("effective_endurance_min", 0) for d in available_devices 
                           if d.get("device_type") == "drone")
    
    thermal_devices = [d["device_id"] for d in available_devices 
                       if "thermal_camera" in d.get("capabilities", [])]
    mapping_devices = [d["device_id"] for d in available_devices 
                       if "mapping" in d.get("capabilities", [])]
    
    # 按就绪时间分组
    immediate_ready = [d["device_id"] for d in available_devices 
                       if d.get("ready_time_min", 0) == 0]
    ready_in_15min = [d["device_id"] for d in available_devices 
                      if 0 < d.get("ready_time_min", 0) <= 15]
    ready_in_30min = [d["device_id"] for d in available_devices 
                      if 15 < d.get("ready_time_min", 0) <= 30]
    
    # 构建资源盘点结果
    resource_inventory: ResourceInventory = {
        "available_devices": available_devices,
        "devices_by_type": devices_by_type,
        "devices_by_category": devices_by_category,
        "total_flight_time_available_min": total_flight_time,
        "thermal_imaging_devices": thermal_devices,
        "mapping_devices": mapping_devices,
        "immediate_ready": immediate_ready,
        "ready_in_15min": ready_in_15min,
        "ready_in_30min": ready_in_30min,
    }
    
    # 生成警告
    warnings = state.get("warnings", [])
    if not available_devices:
        warnings.append("没有可用的设备！")
    elif len(available_devices) < 3:
        warnings.append(f"可用设备数量较少（{len(available_devices)}个），可能影响任务执行")
    
    if not thermal_devices:
        warnings.append("没有热成像设备可用，可能影响人员搜索")
    
    logger.info(f"资源盘点完成: 可用设备={len(available_devices)}, "
                f"热成像={len(thermal_devices)}, 测绘={len(mapping_devices)}")
    
    return {
        "resource_inventory": resource_inventory,
        "available_devices": available_devices,
        "warnings": warnings,
        "current_phase": "resource_inventory",
        "phase_history": state.get("phase_history", []) + [{
            "phase": "resource_inventory",
            "timestamp": datetime.now().isoformat(),
            "available_count": len(available_devices),
            "thermal_count": len(thermal_devices),
        }],
    }


async def _query_devices_from_db(event_id: str, scenario_id: str) -> List[DeviceStatus]:
    """
    从统一数据源查询设备
    
    使用 MockDeviceDataProvider 获取设备数据，确保与 L1/L2 验证使用同一数据源。
    实际生产环境可替换为数据库查询。
    """
    provider = get_device_provider()
    device_ids = await provider.list_available_devices()
    
    devices = []
    for device_id in device_ids:
        profile = await provider.get_device_profile(device_id)
        if profile is None:
            continue
        
        # 从Provider的原始数据中获取完整信息
        provider._load_data()
        raw_data = provider._devices.get(device_id, {})
        
        # 根据category确定device_type (drone/dog)
        category = raw_data.get("category", "multirotor")
        if category in ["multirotor", "vtol_fixed_wing", "fixed_wing"]:
            device_type = "drone"
        elif category in ["ugv_quadruped"]:
            device_type = "dog"
        else:
            device_type = "unknown"
        
        device_status: DeviceStatus = {
            "device_id": device_id,
            "device_code": raw_data.get("device_code", device_id),
            "device_name": raw_data.get("device_name", profile.device_type),
            "device_type": device_type,
            "category": category,
            "status": raw_data.get("status", "available"),
            "battery_percent": raw_data.get("battery_percent", 100),
            "location": raw_data.get("location"),
            "capabilities": raw_data.get("capabilities", []),
            "max_endurance_min": raw_data.get("max_endurance_min", 30),
            "max_speed_ms": profile.max_speed_ms,
            "max_wind_resistance_ms": profile.max_wind_resistance_ms,
            "ip_rating": raw_data.get("ip_rating", "IP43"),
            "sensor_fov_deg": raw_data.get("sensor_fov_deg", 84),
            "requires_runway": raw_data.get("requires_runway", False),
            "is_autonomous": raw_data.get("is_autonomous", False),
            "effective_endurance_min": raw_data.get("effective_endurance_min", 30),
            "ready_time_min": raw_data.get("ready_time_min", 0),
            "vehicle_id": raw_data.get("vehicle_id"),
            "vehicle_name": raw_data.get("vehicle_name"),
        }
        devices.append(device_status)
    
    logger.info(f"从统一数据源加载了 {len(devices)} 个设备")
    return devices


def _filter_by_weather(
    devices: List[DeviceStatus],
    weather: Dict[str, Any],
    weather_rules: Dict[str, Any],
    flight_condition: str
) -> List[DeviceStatus]:
    """根据天气条件筛选设备"""
    if flight_condition == "black":
        # 禁飞条件下只保留地面设备
        return [d for d in devices if d.get("device_type") in ["dog", "ship"]]
    
    wind_speed = weather.get("wind_speed_ms", 0)
    rain_level = weather.get("rain_level", "none")
    
    flight_conditions = weather_rules.get("flight_conditions", {})
    ip_requirements = weather_rules.get("ip_rating_requirements", {})
    
    available = []
    for device in devices:
        category = device.get("category", "")
        device_type = device.get("device_type", "")
        
        # 地面设备不受天气限制
        if device_type in ["dog", "ship"]:
            available.append(device)
            continue
        
        # 检查风速
        wind_rules = flight_conditions.get("wind", {}).get(category, {})
        max_wind = wind_rules.get("no_fly_above_ms", 15)
        device_max_wind = device.get("max_wind_resistance_ms", 12)
        
        if wind_speed > min(max_wind, device_max_wind):
            continue
        
        # 检查防水等级
        required_ip = ip_requirements.get(rain_level, "IP00")
        device_ip = device.get("ip_rating", "IP00")
        
        if rain_level not in ["none", "light"] and not _check_ip_rating(device_ip, required_ip):
            continue
        
        available.append(device)
    
    return available


def _check_ip_rating(device_ip: Optional[str], required_ip: str) -> bool:
    """检查IP防护等级是否满足要求"""
    if not device_ip:
        return False
    
    try:
        # 解析IP等级，如"IP45"
        device_num = int(device_ip.replace("IP", ""))
        required_num = int(required_ip.replace("IP", ""))
        return device_num >= required_num
    except:
        return False


def _group_by_type(devices: List[DeviceStatus]) -> Dict[str, List[DeviceStatus]]:
    """按设备类型分组"""
    groups = {}
    for device in devices:
        dtype = device.get("device_type", "unknown")
        if dtype not in groups:
            groups[dtype] = []
        groups[dtype].append(device)
    return groups


def _group_by_category(devices: List[DeviceStatus]) -> Dict[str, List[DeviceStatus]]:
    """按设备类别分组"""
    groups = {}
    for device in devices:
        category = device.get("category", "unknown")
        if category not in groups:
            groups[category] = []
        groups[category].append(device)
    return groups
