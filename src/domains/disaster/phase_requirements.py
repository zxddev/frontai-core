"""
阶段感知的装备需求模块

根据灾害类型和响应阶段，定义所需的装备套件、能力和优先级。
这是连接 Sphere 标准与具体装备选择的桥梁。

Usage:
    from src.domains.disaster.phase_requirements import (
        get_phase_requirements,
        get_equipment_priorities,
    )
    
    reqs = get_phase_requirements(DisasterType.EARTHQUAKE, ResponsePhase.IMMEDIATE)
    print(reqs.equipment_sets)  # ['USAR_heavy', 'medical_triage', ...]
    print(reqs.capabilities)    # ['life_detection', 'heavy_rescue', ...]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional, Set

from .sphere_standards import ResponsePhase, SphereCategory


class DisasterType(str, Enum):
    """灾害类型"""
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"
    LANDSLIDE = "landslide"
    TYPHOON = "typhoon"
    FIRE = "fire"
    EXPLOSION = "explosion"
    CHEMICAL = "chemical"
    BIOLOGICAL = "biological"
    NUCLEAR = "nuclear"


class EquipmentSet(str, Enum):
    """标准装备套件"""
    # 搜救类
    USAR_HEAVY = "USAR_heavy"           # 重型城市搜救
    USAR_MEDIUM = "USAR_medium"         # 中型城市搜救
    USAR_LIGHT = "USAR_light"           # 轻型城市搜救
    WATER_RESCUE = "water_rescue"       # 水域救援
    HIGH_ANGLE = "high_angle"           # 高空救援
    CONFINED_SPACE = "confined_space"   # 狭窄空间救援
    
    # 医疗类
    MEDICAL_TRIAGE = "medical_triage"   # 分检医疗
    MEDICAL_FIELD = "medical_field"     # 野外医疗
    MEDICAL_TRANSPORT = "medical_transport"  # 医疗转运
    
    # 生活保障类
    SHELTER_DEPLOYMENT = "shelter_deployment"  # 帐篷部署
    WATER_PURIFICATION = "water_purification"  # 净水设备
    FIELD_KITCHEN = "field_kitchen"     # 野战炊事
    POWER_SUPPLY = "power_supply"       # 电力供应
    LIGHTING = "lighting"               # 照明设备
    
    # 防护类
    HAZMAT_LEVEL_A = "hazmat_level_A"   # A级化学防护
    HAZMAT_LEVEL_B = "hazmat_level_B"   # B级化学防护
    RADIATION = "radiation"              # 辐射防护
    FIREFIGHTING = "firefighting"        # 消防装备
    
    # 通信类
    COMMS_BASE = "comms_base"           # 基地通信
    COMMS_FIELD = "comms_field"         # 野外通信
    COMMS_SATELLITE = "comms_satellite"  # 卫星通信


class Capability(str, Enum):
    """救援能力"""
    # 搜救能力
    LIFE_DETECTION = "life_detection"       # 生命探测
    HEAVY_RESCUE = "heavy_rescue"           # 重型救援
    LIGHT_RESCUE = "light_rescue"           # 轻型救援
    SWIFT_WATER = "swift_water"             # 激流救援
    DIVE_RESCUE = "dive_rescue"             # 潜水救援
    ROPE_RESCUE = "rope_rescue"             # 绳索救援
    TRENCH_RESCUE = "trench_rescue"         # 沟槽救援
    
    # 医疗能力
    TRAUMA_CARE = "trauma_care"             # 创伤处理
    MASS_CASUALTY = "mass_casualty"         # 群体伤亡处理
    MEDICAL_EVAC = "medical_evac"           # 医疗后送
    
    # 生活保障能力
    SHELTER_MANAGEMENT = "shelter_management"  # 安置点管理
    WASH = "WASH"                           # 水卫设施
    FOOD_DISTRIBUTION = "food_distribution"  # 食品分发
    
    # 特殊能力
    HAZMAT_RESPONSE = "hazmat_response"     # 危化品处置
    DECON = "decon"                         # 洗消
    FIRE_SUPPRESSION = "fire_suppression"   # 灭火


@dataclass(frozen=True)
class PhaseRequirements:
    """
    阶段需求定义
    
    定义特定灾害类型在特定响应阶段所需的：
    - 装备套件 (equipment_sets)
    - 救援能力 (capabilities)
    - Sphere 品类优先级 (sphere_priorities)
    - 优先级描述 (priority_description)
    """
    disaster_type: DisasterType
    phase: ResponsePhase
    equipment_sets: FrozenSet[EquipmentSet]
    capabilities: FrozenSet[Capability]
    sphere_priorities: tuple  # 按优先级排序的 SphereCategory
    priority_description: str
    notes: str = ""

    def requires_capability(self, cap: Capability) -> bool:
        """检查是否需要某能力"""
        return cap in self.capabilities

    def get_top_sphere_category(self) -> SphereCategory:
        """获取最高优先级的Sphere品类"""
        return self.sphere_priorities[0] if self.sphere_priorities else SphereCategory.OTHER


# =============================================================================
# 地震响应需求
# =============================================================================

EARTHQUAKE_REQUIREMENTS: Dict[ResponsePhase, PhaseRequirements] = {
    ResponsePhase.IMMEDIATE: PhaseRequirements(
        disaster_type=DisasterType.EARTHQUAKE,
        phase=ResponsePhase.IMMEDIATE,
        equipment_sets=frozenset({
            EquipmentSet.USAR_HEAVY,
            EquipmentSet.USAR_MEDIUM,
            EquipmentSet.MEDICAL_TRIAGE,
            EquipmentSet.LIGHTING,
            EquipmentSet.COMMS_FIELD,
        }),
        capabilities=frozenset({
            Capability.LIFE_DETECTION,
            Capability.HEAVY_RESCUE,
            Capability.LIGHT_RESCUE,
            Capability.TRAUMA_CARE,
            Capability.MASS_CASUALTY,
            Capability.TRENCH_RESCUE,
        }),
        sphere_priorities=(
            SphereCategory.HEALTH,
            SphereCategory.WASH,
            SphereCategory.SHELTER,
            SphereCategory.FOOD,
        ),
        priority_description="救援为主，生活物资为辅",
        notes="0-72小时黄金救援期，优先生命探测和搜救",
    ),
    ResponsePhase.SHORT_TERM: PhaseRequirements(
        disaster_type=DisasterType.EARTHQUAKE,
        phase=ResponsePhase.SHORT_TERM,
        equipment_sets=frozenset({
            EquipmentSet.USAR_LIGHT,
            EquipmentSet.SHELTER_DEPLOYMENT,
            EquipmentSet.WATER_PURIFICATION,
            EquipmentSet.FIELD_KITCHEN,
            EquipmentSet.POWER_SUPPLY,
            EquipmentSet.MEDICAL_FIELD,
        }),
        capabilities=frozenset({
            Capability.LIGHT_RESCUE,
            Capability.SHELTER_MANAGEMENT,
            Capability.WASH,
            Capability.FOOD_DISTRIBUTION,
            Capability.MEDICAL_EVAC,
        }),
        sphere_priorities=(
            SphereCategory.SHELTER,
            SphereCategory.WASH,
            SphereCategory.FOOD,
            SphereCategory.HEALTH,
            SphereCategory.NFI,
        ),
        priority_description="安置为主，持续搜救",
        notes="3-14天，建立安置点，保障基本生活",
    ),
    ResponsePhase.RECOVERY: PhaseRequirements(
        disaster_type=DisasterType.EARTHQUAKE,
        phase=ResponsePhase.RECOVERY,
        equipment_sets=frozenset({
            EquipmentSet.SHELTER_DEPLOYMENT,
            EquipmentSet.POWER_SUPPLY,
            EquipmentSet.MEDICAL_FIELD,
        }),
        capabilities=frozenset({
            Capability.SHELTER_MANAGEMENT,
            Capability.WASH,
            Capability.FOOD_DISTRIBUTION,
        }),
        sphere_priorities=(
            SphereCategory.SHELTER,
            SphereCategory.NFI,
            SphereCategory.FOOD,
            SphereCategory.HEALTH,
        ),
        priority_description="恢复重建，长期安置",
        notes="14天以上，过渡安置和恢复重建",
    ),
}


# =============================================================================
# 洪水响应需求
# =============================================================================

FLOOD_REQUIREMENTS: Dict[ResponsePhase, PhaseRequirements] = {
    ResponsePhase.IMMEDIATE: PhaseRequirements(
        disaster_type=DisasterType.FLOOD,
        phase=ResponsePhase.IMMEDIATE,
        equipment_sets=frozenset({
            EquipmentSet.WATER_RESCUE,
            EquipmentSet.MEDICAL_TRIAGE,
            EquipmentSet.COMMS_FIELD,
            EquipmentSet.LIGHTING,
        }),
        capabilities=frozenset({
            Capability.SWIFT_WATER,
            Capability.DIVE_RESCUE,
            Capability.TRAUMA_CARE,
            Capability.MEDICAL_EVAC,
        }),
        sphere_priorities=(
            SphereCategory.HEALTH,
            SphereCategory.WASH,
            SphereCategory.SHELTER,
        ),
        priority_description="水域救援为主，医疗转运",
        notes="洪水救援重点是水域作业和快速转移",
    ),
    ResponsePhase.SHORT_TERM: PhaseRequirements(
        disaster_type=DisasterType.FLOOD,
        phase=ResponsePhase.SHORT_TERM,
        equipment_sets=frozenset({
            EquipmentSet.SHELTER_DEPLOYMENT,
            EquipmentSet.WATER_PURIFICATION,
            EquipmentSet.FIELD_KITCHEN,
            EquipmentSet.POWER_SUPPLY,
        }),
        capabilities=frozenset({
            Capability.SHELTER_MANAGEMENT,
            Capability.WASH,
            Capability.FOOD_DISTRIBUTION,
        }),
        sphere_priorities=(
            SphereCategory.WASH,  # 洪水后饮水安全优先
            SphereCategory.SHELTER,
            SphereCategory.FOOD,
            SphereCategory.HEALTH,
        ),
        priority_description="饮水安全和临时安置",
        notes="洪水后饮水污染风险高，净水优先",
    ),
    ResponsePhase.RECOVERY: PhaseRequirements(
        disaster_type=DisasterType.FLOOD,
        phase=ResponsePhase.RECOVERY,
        equipment_sets=frozenset({
            EquipmentSet.WATER_PURIFICATION,
            EquipmentSet.SHELTER_DEPLOYMENT,
        }),
        capabilities=frozenset({
            Capability.WASH,
            Capability.SHELTER_MANAGEMENT,
        }),
        sphere_priorities=(
            SphereCategory.WASH,
            SphereCategory.SHELTER,
            SphereCategory.NFI,
        ),
        priority_description="恢复供水和住房重建",
    ),
}


# =============================================================================
# 危化品事故响应需求
# =============================================================================

CHEMICAL_REQUIREMENTS: Dict[ResponsePhase, PhaseRequirements] = {
    ResponsePhase.IMMEDIATE: PhaseRequirements(
        disaster_type=DisasterType.CHEMICAL,
        phase=ResponsePhase.IMMEDIATE,
        equipment_sets=frozenset({
            EquipmentSet.HAZMAT_LEVEL_A,
            EquipmentSet.HAZMAT_LEVEL_B,
            EquipmentSet.MEDICAL_TRIAGE,
            EquipmentSet.COMMS_FIELD,
        }),
        capabilities=frozenset({
            Capability.HAZMAT_RESPONSE,
            Capability.DECON,
            Capability.TRAUMA_CARE,
            Capability.MASS_CASUALTY,
        }),
        sphere_priorities=(
            SphereCategory.HEALTH,
            SphereCategory.SHELTER,
        ),
        priority_description="危化品处置和洗消为主",
        notes="优先隔离污染源，建立洗消站",
    ),
    ResponsePhase.SHORT_TERM: PhaseRequirements(
        disaster_type=DisasterType.CHEMICAL,
        phase=ResponsePhase.SHORT_TERM,
        equipment_sets=frozenset({
            EquipmentSet.HAZMAT_LEVEL_B,
            EquipmentSet.MEDICAL_FIELD,
            EquipmentSet.SHELTER_DEPLOYMENT,
        }),
        capabilities=frozenset({
            Capability.DECON,
            Capability.MEDICAL_EVAC,
            Capability.SHELTER_MANAGEMENT,
        }),
        sphere_priorities=(
            SphereCategory.HEALTH,
            SphereCategory.SHELTER,
            SphereCategory.WASH,
        ),
        priority_description="持续监测和医疗观察",
    ),
    ResponsePhase.RECOVERY: PhaseRequirements(
        disaster_type=DisasterType.CHEMICAL,
        phase=ResponsePhase.RECOVERY,
        equipment_sets=frozenset({
            EquipmentSet.SHELTER_DEPLOYMENT,
        }),
        capabilities=frozenset({
            Capability.SHELTER_MANAGEMENT,
        }),
        sphere_priorities=(
            SphereCategory.HEALTH,
            SphereCategory.SHELTER,
        ),
        priority_description="环境修复和健康监测",
    ),
}


# =============================================================================
# 需求查询 API
# =============================================================================

_DISASTER_REQUIREMENTS: Dict[DisasterType, Dict[ResponsePhase, PhaseRequirements]] = {
    DisasterType.EARTHQUAKE: EARTHQUAKE_REQUIREMENTS,
    DisasterType.FLOOD: FLOOD_REQUIREMENTS,
    DisasterType.CHEMICAL: CHEMICAL_REQUIREMENTS,
}


def get_phase_requirements(
    disaster_type: DisasterType,
    phase: ResponsePhase,
) -> Optional[PhaseRequirements]:
    """
    获取指定灾害类型和响应阶段的需求定义
    
    Args:
        disaster_type: 灾害类型
        phase: 响应阶段
        
    Returns:
        PhaseRequirements 或 None（如果未定义）
    """
    disaster_reqs = _DISASTER_REQUIREMENTS.get(disaster_type)
    if not disaster_reqs:
        return None
    return disaster_reqs.get(phase)


def get_equipment_priorities(
    disaster_type: DisasterType,
    phase: ResponsePhase,
) -> List[EquipmentSet]:
    """
    获取装备套件优先级列表
    
    Args:
        disaster_type: 灾害类型
        phase: 响应阶段
        
    Returns:
        按优先级排序的装备套件列表
    """
    reqs = get_phase_requirements(disaster_type, phase)
    if not reqs:
        return []
    return list(reqs.equipment_sets)


def get_required_capabilities(
    disaster_type: DisasterType,
    phase: ResponsePhase,
) -> Set[Capability]:
    """
    获取所需能力集合
    
    Args:
        disaster_type: 灾害类型
        phase: 响应阶段
        
    Returns:
        能力集合
    """
    reqs = get_phase_requirements(disaster_type, phase)
    if not reqs:
        return set()
    return set(reqs.capabilities)


def get_all_disaster_types() -> List[DisasterType]:
    """获取所有已定义需求的灾害类型"""
    return list(_DISASTER_REQUIREMENTS.keys())


def get_all_phases_for_disaster(disaster_type: DisasterType) -> List[ResponsePhase]:
    """获取某灾害类型已定义的所有响应阶段"""
    disaster_reqs = _DISASTER_REQUIREMENTS.get(disaster_type)
    if not disaster_reqs:
        return []
    return list(disaster_reqs.keys())
