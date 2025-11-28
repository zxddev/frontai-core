"""
灾情需求推断服务

统一入口，替换所有硬编码的DISASTER_*_MAP。基于phase_requirements提供：
1. 能力需求推断 (capabilities)
2. 设备类型推断 (device_types)
3. 物资类别推断 (supply_categories)

Usage:
    from src.domains.disaster.requirement_inferencer import DisasterRequirementInferencer
    
    inferencer = DisasterRequirementInferencer()
    capabilities = inferencer.infer_capabilities("earthquake")
    device_types = inferencer.infer_device_types("earthquake")
    supply_categories = inferencer.infer_supply_categories("earthquake")
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from .phase_requirements import (
    DisasterType,
    EquipmentSet,
    Capability,
    PhaseRequirements,
    get_phase_requirements,
)
from .sphere_standards import ResponsePhase, SphereCategory


# Capability枚举到智能体使用的字符串映射
# phase_requirements.Capability -> agents使用的capability字符串
CAPABILITY_TO_STRING: Dict[Capability, str] = {
    Capability.LIFE_DETECTION: "life_detection",
    Capability.HEAVY_RESCUE: "structural_assessment",
    Capability.LIGHT_RESCUE: "debris_search",
    Capability.SWIFT_WATER: "water_rescue",
    Capability.DIVE_RESCUE: "water_surface_operation",
    Capability.ROPE_RESCUE: "rope_rescue",
    Capability.TRENCH_RESCUE: "trench_rescue",
    Capability.TRAUMA_CARE: "thermal_imaging",
    Capability.MASS_CASUALTY: "mass_casualty",
    Capability.MEDICAL_EVAC: "medical_evac",
    Capability.SHELTER_MANAGEMENT: "shelter_management",
    Capability.WASH: "water_purification",
    Capability.FOOD_DISTRIBUTION: "food_distribution",
    Capability.HAZMAT_RESPONSE: "chemical_detection",
    Capability.DECON: "decon",
    Capability.FIRE_SUPPRESSION: "fire_monitoring",
}

# EquipmentSet到设备类型字符串映射
EQUIPMENT_SET_TO_DEVICE: Dict[EquipmentSet, List[str]] = {
    EquipmentSet.USAR_HEAVY: ["drone", "dog"],
    EquipmentSet.USAR_MEDIUM: ["drone", "dog"],
    EquipmentSet.USAR_LIGHT: ["drone"],
    EquipmentSet.WATER_RESCUE: ["drone", "ship"],
    EquipmentSet.HIGH_ANGLE: ["drone"],
    EquipmentSet.CONFINED_SPACE: ["dog", "robot"],
    EquipmentSet.MEDICAL_TRIAGE: ["drone"],
    EquipmentSet.MEDICAL_FIELD: [],
    EquipmentSet.MEDICAL_TRANSPORT: [],
    EquipmentSet.SHELTER_DEPLOYMENT: [],
    EquipmentSet.WATER_PURIFICATION: [],
    EquipmentSet.FIELD_KITCHEN: [],
    EquipmentSet.POWER_SUPPLY: [],
    EquipmentSet.LIGHTING: ["drone"],
    EquipmentSet.HAZMAT_LEVEL_A: ["drone", "robot"],
    EquipmentSet.HAZMAT_LEVEL_B: ["drone", "robot"],
    EquipmentSet.RADIATION: ["drone", "robot"],
    EquipmentSet.FIREFIGHTING: ["drone"],
    EquipmentSet.COMMS_BASE: [],
    EquipmentSet.COMMS_FIELD: ["drone"],
    EquipmentSet.COMMS_SATELLITE: [],
}

# SphereCategory到物资类别字符串映射
SPHERE_TO_SUPPLY_CATEGORY: Dict[SphereCategory, str] = {
    SphereCategory.WASH: "life",
    SphereCategory.FOOD: "life",
    SphereCategory.SHELTER: "life",
    SphereCategory.HEALTH: "medical",
    SphereCategory.NFI: "tool",
    SphereCategory.OTHER: "rescue",
}


class DisasterRequirementInferencer:
    """
    灾情需求推断器
    
    替换所有DISASTER_*_MAP硬编码，统一从phase_requirements派生。
    """

    def __init__(self) -> None:
        self._cache: Dict[str, PhaseRequirements] = {}

    def _get_requirements(
        self,
        disaster_type: str,
        phase: ResponsePhase = ResponsePhase.IMMEDIATE,
    ) -> Optional[PhaseRequirements]:
        """获取阶段需求（带缓存）"""
        cache_key = f"{disaster_type}:{phase.value}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            dt = DisasterType(disaster_type)
        except ValueError:
            dt = DisasterType.EARTHQUAKE
        
        reqs = get_phase_requirements(dt, phase)
        if reqs:
            self._cache[cache_key] = reqs
        return reqs

    def infer_capabilities(
        self,
        disaster_type: str,
        phase: ResponsePhase = ResponsePhase.IMMEDIATE,
        has_building_collapse: bool = False,
        has_trapped_persons: bool = False,
        has_secondary_fire: bool = False,
        has_hazmat_leak: bool = False,
    ) -> List[str]:
        """
        推断所需能力列表
        
        Args:
            disaster_type: 灾害类型
            phase: 响应阶段
            has_building_collapse: 是否有建筑倒塌
            has_trapped_persons: 是否有被困人员
            has_secondary_fire: 是否有次生火灾
            has_hazmat_leak: 是否有危化品泄漏
            
        Returns:
            能力字符串列表（兼容旧代码格式）
        """
        reqs = self._get_requirements(disaster_type, phase)
        
        if not reqs:
            # fallback默认值
            return ["aerial_reconnaissance", "life_detection"]
        
        capabilities: Set[str] = set()
        
        # 从phase_requirements的capabilities转换
        for cap in reqs.capabilities:
            cap_str = CAPABILITY_TO_STRING.get(cap, cap.value)
            capabilities.add(cap_str)
        
        # 根据灾情特征添加额外能力（兼容旧逻辑）
        if has_building_collapse:
            capabilities.add("life_detection")
            capabilities.add("debris_search")
        
        if has_trapped_persons:
            capabilities.add("life_detection")
        
        if has_secondary_fire:
            capabilities.add("thermal_imaging")
        
        if has_hazmat_leak:
            capabilities.add("chemical_detection")
            capabilities.add("remote_operation")
        
        # 始终添加空中侦察（通用需求）
        capabilities.add("aerial_reconnaissance")
        
        return list(capabilities)

    def infer_device_types(
        self,
        disaster_type: str,
        phase: ResponsePhase = ResponsePhase.IMMEDIATE,
    ) -> List[str]:
        """
        推断所需设备类型
        
        Args:
            disaster_type: 灾害类型
            phase: 响应阶段
            
        Returns:
            设备类型列表 ["drone", "dog", "ship", "robot"]
        """
        reqs = self._get_requirements(disaster_type, phase)
        
        if not reqs:
            return ["drone"]
        
        device_types: Set[str] = set()
        
        for equip_set in reqs.equipment_sets:
            devices = EQUIPMENT_SET_TO_DEVICE.get(equip_set, [])
            device_types.update(devices)
        
        # 确保至少有无人机（通用侦察）
        if not device_types:
            device_types.add("drone")
        
        return list(device_types)

    def infer_supply_categories(
        self,
        disaster_type: str,
        phase: ResponsePhase = ResponsePhase.IMMEDIATE,
    ) -> List[str]:
        """
        推断所需物资类别
        
        Args:
            disaster_type: 灾害类型
            phase: 响应阶段
            
        Returns:
            物资类别列表 ["medical", "rescue", "protection", "life", "tool"]
        """
        reqs = self._get_requirements(disaster_type, phase)
        
        if not reqs:
            return ["medical", "rescue"]
        
        categories: Set[str] = set()
        
        # 从sphere_priorities派生
        for sphere_cat in reqs.sphere_priorities:
            cat_str = SPHERE_TO_SUPPLY_CATEGORY.get(sphere_cat, "rescue")
            categories.add(cat_str)
        
        # 根据装备套件添加类别
        for equip_set in reqs.equipment_sets:
            if "USAR" in equip_set.value.upper() or "RESCUE" in equip_set.value.upper():
                categories.add("rescue")
            if "MEDICAL" in equip_set.value.upper():
                categories.add("medical")
            if "HAZMAT" in equip_set.value.upper():
                categories.add("protection")
                categories.add("chemical")
            if "WATER" in equip_set.value.upper():
                categories.add("water_rescue")
            if "FIRE" in equip_set.value.upper():
                categories.add("fire_fighting")
        
        return list(categories)

    def infer_all(
        self,
        disaster_type: str,
        phase: ResponsePhase = ResponsePhase.IMMEDIATE,
        **disaster_features,
    ) -> Dict[str, List[str]]:
        """
        一次性推断所有需求
        
        Args:
            disaster_type: 灾害类型
            phase: 响应阶段
            **disaster_features: 灾情特征（has_building_collapse等）
            
        Returns:
            {
                "capabilities": [...],
                "device_types": [...],
                "supply_categories": [...],
            }
        """
        return {
            "capabilities": self.infer_capabilities(
                disaster_type, phase, **disaster_features
            ),
            "device_types": self.infer_device_types(disaster_type, phase),
            "supply_categories": self.infer_supply_categories(disaster_type, phase),
        }


# 全局单例（可选，用于无状态调用）
_inferencer: Optional[DisasterRequirementInferencer] = None


def get_inferencer() -> DisasterRequirementInferencer:
    """获取全局推断器实例"""
    global _inferencer
    if _inferencer is None:
        _inferencer = DisasterRequirementInferencer()
    return _inferencer


def infer_capabilities(disaster_type: str, **kwargs) -> List[str]:
    """便捷函数：推断能力需求"""
    return get_inferencer().infer_capabilities(disaster_type, **kwargs)


def infer_device_types(disaster_type: str, **kwargs) -> List[str]:
    """便捷函数：推断设备类型"""
    return get_inferencer().infer_device_types(disaster_type, **kwargs)


def infer_supply_categories(disaster_type: str, **kwargs) -> List[str]:
    """便捷函数：推断物资类别"""
    return get_inferencer().infer_supply_categories(disaster_type, **kwargs)
