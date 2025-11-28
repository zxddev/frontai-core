"""
Sphere Humanitarian Standards Module

Based on:
- Sphere Handbook 2018 Edition
- WHO Technical Notes on WASH in Emergencies
- UNHCR Emergency Handbook

This module defines the minimum humanitarian standards for disaster response,
providing type-safe data structures and constants for supply demand calculation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, List, Mapping, Tuple


class ResponsePhase(str, Enum):
    """
    Disaster response phases based on international emergency management standards.
    
    Each phase has distinct characteristics and resource requirements:
    - IMMEDIATE: Life-saving operations, search and rescue, emergency triage
    - SHORT_TERM: Basic needs provision, temporary shelter, sanitation
    - RECOVERY: Rehabilitation, reconstruction, return to normalcy
    """
    IMMEDIATE = "immediate"    # 0-72 hours
    SHORT_TERM = "short_term"  # 3-14 days
    RECOVERY = "recovery"      # 14+ days

    @property
    def duration_hours(self) -> Tuple[int, int]:
        """Return (min_hours, max_hours) for this phase."""
        durations = {
            ResponsePhase.IMMEDIATE: (0, 72),
            ResponsePhase.SHORT_TERM: (72, 336),  # 14 days
            ResponsePhase.RECOVERY: (336, 8760),  # up to 1 year
        }
        return durations[self]

    @property
    def description_cn(self) -> str:
        """Chinese description for UI display."""
        descriptions = {
            ResponsePhase.IMMEDIATE: "立即响应 (0-72小时): 搜救、分检、紧急疏散",
            ResponsePhase.SHORT_TERM: "短期救济 (3-14天): 安置、基本生活保障",
            ResponsePhase.RECOVERY: "恢复重建 (14天+): 临时住房、恢复生产",
        }
        return descriptions[self]


class ClimateType(str, Enum):
    """
    Climate types affecting resource requirements.
    
    Based on WHO guidelines for adjusting water and shelter needs.
    """
    TROPICAL = "tropical"     # Hot and humid - water+20%, blankets-50%
    TEMPERATE = "temperate"   # Standard baseline
    COLD = "cold"             # Cold climate - water-20%, blankets+100%
    ARID = "arid"             # Hot and dry - water+50%

    @property
    def water_factor(self) -> float:
        """Water requirement adjustment factor."""
        factors = {
            ClimateType.TROPICAL: 1.2,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 0.8,
            ClimateType.ARID: 1.5,
        }
        return factors[self]

    @property
    def blanket_factor(self) -> float:
        """Blanket/thermal requirement adjustment factor."""
        factors = {
            ClimateType.TROPICAL: 0.5,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 2.0,
            ClimateType.ARID: 0.8,
        }
        return factors[self]


class ScalingBasis(str, Enum):
    """
    Basis for scaling supply quantities.
    
    Different supplies scale with different population metrics:
    - Water scales with total affected population
    - Medical supplies scale with casualties
    - Tents scale with displaced persons only
    - SAR equipment scales with search area
    """
    PER_PERSON = "per_person"           # Total affected population
    PER_DISPLACED = "per_displaced"     # Only displaced/evacuated persons
    PER_CASUALTY = "per_casualty"       # Injured + trapped persons
    PER_TRAPPED = "per_trapped"         # Only trapped persons (SAR)
    PER_AREA_KM2 = "per_area_km2"       # Affected area in km²
    PER_TEAM = "per_team"               # Per rescue team
    FIXED = "fixed"                      # Fixed quantity regardless of scale


class SphereCategory(str, Enum):
    """
    Sphere Handbook standard categories.
    """
    WASH = "WASH"       # Water, Sanitation and Hygiene
    FOOD = "FOOD"       # Food Security and Nutrition
    SHELTER = "SHELTER" # Shelter and Settlement
    HEALTH = "HEALTH"   # Health
    NFI = "NFI"         # Non-Food Items
    OTHER = "OTHER"     # Project-specific items


@dataclass(frozen=True)
class SphereStandard:
    """
    Immutable data class representing a Sphere humanitarian standard.
    
    Frozen=True ensures thread safety and hashability for caching.
    
    Attributes:
        code: Unique identifier (e.g., "SPHERE-WASH-001")
        name: Human-readable name
        name_cn: Chinese name for UI
        category: Sphere category (WASH/FOOD/SHELTER/HEALTH/NFI)
        min_quantity: Minimum acceptable quantity per scaling unit
        target_quantity: Target quantity per scaling unit
        unit: Unit of measurement (liter, kg, piece, etc.)
        scaling_basis: What this quantity scales with
        applicable_phases: Tuple of phases where this standard applies
        climate_factors: Dict of climate type to adjustment factor
        reference: Source document reference
        description: Detailed description
    """
    code: str
    name: str
    name_cn: str
    category: SphereCategory
    min_quantity: float
    target_quantity: float
    unit: str
    scaling_basis: ScalingBasis
    applicable_phases: FrozenSet[ResponsePhase]
    climate_factors: Mapping[ClimateType, float]
    reference: str = "Sphere Handbook 2018"
    description: str = ""

    def get_quantity(
        self,
        base_count: int,
        climate: ClimateType = ClimateType.TEMPERATE,
        use_target: bool = False,
    ) -> float:
        """
        Calculate required quantity for given population/area count.
        
        Args:
            base_count: The count based on scaling_basis (persons, casualties, km², etc.)
            climate: Climate type for adjustment
            use_target: Use target_quantity instead of min_quantity
            
        Returns:
            Calculated quantity in the standard's unit
        """
        base_qty = self.target_quantity if use_target else self.min_quantity
        climate_factor = self.climate_factors.get(climate, 1.0)
        return base_count * base_qty * climate_factor

    def applies_to_phase(self, phase: ResponsePhase) -> bool:
        """Check if this standard applies to the given response phase."""
        return phase in self.applicable_phases


# =============================================================================
# Sphere Standards Data - Based on Sphere Handbook 2018
# =============================================================================

_DEFAULT_CLIMATE_FACTORS: Dict[ClimateType, float] = {
    ClimateType.TROPICAL: 1.0,
    ClimateType.TEMPERATE: 1.0,
    ClimateType.COLD: 1.0,
    ClimateType.ARID: 1.0,
}

SPHERE_STANDARDS: Dict[str, SphereStandard] = {
    # =========================================================================
    # WASH - Water, Sanitation and Hygiene
    # =========================================================================
    "SPHERE-WASH-001": SphereStandard(
        code="SPHERE-WASH-001",
        name="Survival Water",
        name_cn="生存用水",
        category=SphereCategory.WASH,
        min_quantity=2.5,  # L/person/day
        target_quantity=3.0,
        unit="liter",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE}),
        climate_factors={
            ClimateType.TROPICAL: 1.2,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 0.8,
            ClimateType.ARID: 1.5,
        },
        reference="Sphere Handbook 2018, WASH Standard 1",
        description="Minimum water for drinking and food preparation in immediate response",
    ),
    "SPHERE-WASH-002": SphereStandard(
        code="SPHERE-WASH-002",
        name="Basic Water",
        name_cn="基本用水",
        category=SphereCategory.WASH,
        min_quantity=7.5,  # L/person/day
        target_quantity=15.0,
        unit="liter",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors={
            ClimateType.TROPICAL: 1.2,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 0.8,
            ClimateType.ARID: 1.3,
        },
        reference="Sphere Handbook 2018, WASH Standard 1",
        description="Water for drinking, cooking, and personal hygiene",
    ),
    "SPHERE-WASH-003": SphereStandard(
        code="SPHERE-WASH-003",
        name="Toilet Ratio",
        name_cn="厕所配比",
        category=SphereCategory.WASH,
        min_quantity=0.05,  # 1 toilet per 20 people
        target_quantity=0.05,
        unit="unit",
        scaling_basis=ScalingBasis.PER_DISPLACED,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Sphere Handbook 2018, WASH Standard 3",
        description="Maximum 20 persons per toilet in emergency camps",
    ),

    # =========================================================================
    # FOOD - Food Security and Nutrition
    # =========================================================================
    "SPHERE-FOOD-001": SphereStandard(
        code="SPHERE-FOOD-001",
        name="Daily Calorie Intake",
        name_cn="每日热量摄入",
        category=SphereCategory.FOOD,
        min_quantity=2100,  # kcal/person/day
        target_quantity=2100,
        unit="kcal",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE, ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors={
            ClimateType.TROPICAL: 0.95,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 1.15,  # +15% for cold
            ClimateType.ARID: 1.0,
        },
        reference="Sphere Handbook 2018, Food Security Standard 1",
        description="Minimum daily energy intake per person",
    ),
    "SPHERE-FOOD-002": SphereStandard(
        code="SPHERE-FOOD-002",
        name="Dry Rations",
        name_cn="干粮配给",
        category=SphereCategory.FOOD,
        min_quantity=0.5,  # kg/person/day
        target_quantity=0.6,
        unit="kg",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE, ResponsePhase.SHORT_TERM}),
        climate_factors={
            ClimateType.TROPICAL: 1.0,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 1.1,
            ClimateType.ARID: 1.0,
        },
        reference="Calculated from 2100 kcal standard",
        description="Dry food rations equivalent to 2100 kcal",
    ),

    # =========================================================================
    # SHELTER - Shelter and Settlement
    # =========================================================================
    "SPHERE-SHELTER-001": SphereStandard(
        code="SPHERE-SHELTER-001",
        name="Covered Living Space",
        name_cn="人均居住面积",
        category=SphereCategory.SHELTER,
        min_quantity=3.5,  # m²/person
        target_quantity=4.5,
        unit="m2",
        scaling_basis=ScalingBasis.PER_DISPLACED,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors={
            ClimateType.TROPICAL: 0.9,  # Less indoor time
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 1.2,  # More indoor time
            ClimateType.ARID: 1.0,
        },
        reference="Sphere Handbook 2018, Shelter Standard 3",
        description="Minimum covered floor area per person",
    ),
    "SPHERE-SHELTER-002": SphereStandard(
        code="SPHERE-SHELTER-002",
        name="Tent (4-person)",
        name_cn="帐篷(4人)",
        category=SphereCategory.SHELTER,
        min_quantity=0.25,  # 1 tent per 4 persons
        target_quantity=0.25,
        unit="unit",
        scaling_basis=ScalingBasis.PER_DISPLACED,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE, ResponsePhase.SHORT_TERM}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Standard 4-person emergency tent",
        description="4-person emergency tent allocation",
    ),
    "SPHERE-SHELTER-003": SphereStandard(
        code="SPHERE-SHELTER-003",
        name="Blanket/Thermal Sheet",
        name_cn="毛毯/保温毯",
        category=SphereCategory.SHELTER,
        min_quantity=1.0,  # per person
        target_quantity=2.0,
        unit="piece",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE, ResponsePhase.SHORT_TERM}),
        climate_factors={
            ClimateType.TROPICAL: 0.5,
            ClimateType.TEMPERATE: 1.0,
            ClimateType.COLD: 2.0,
            ClimateType.ARID: 0.8,
        },
        reference="Sphere Handbook 2018, Shelter Standard 4",
        description="Blankets for thermal comfort",
    ),
    "SPHERE-SHELTER-004": SphereStandard(
        code="SPHERE-SHELTER-004",
        name="Sleeping Mat",
        name_cn="睡垫/睡袋",
        category=SphereCategory.SHELTER,
        min_quantity=1.0,  # per person
        target_quantity=1.0,
        unit="piece",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE, ResponsePhase.SHORT_TERM}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Sphere Handbook 2018, Shelter Standard 4",
        description="Sleeping mat or sleeping bag per person",
    ),

    # =========================================================================
    # HEALTH - Health
    # =========================================================================
    "SPHERE-HEALTH-001": SphereStandard(
        code="SPHERE-HEALTH-001",
        name="First Aid Kit",
        name_cn="急救包",
        category=SphereCategory.HEALTH,
        min_quantity=0.1,  # 1 per 10 casualties
        target_quantity=0.1,
        unit="kit",
        scaling_basis=ScalingBasis.PER_CASUALTY,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Emergency medical response standard",
        description="First aid kit per 10 casualties",
    ),
    "SPHERE-HEALTH-002": SphereStandard(
        code="SPHERE-HEALTH-002",
        name="Stretcher",
        name_cn="担架",
        category=SphereCategory.HEALTH,
        min_quantity=0.02,  # 1 per 50 casualties
        target_quantity=0.05,  # 1 per 20 casualties
        unit="unit",
        scaling_basis=ScalingBasis.PER_CASUALTY,
        applicable_phases=frozenset({ResponsePhase.IMMEDIATE}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Emergency medical response standard",
        description="Stretcher for casualty evacuation",
    ),
    "SPHERE-HEALTH-003": SphereStandard(
        code="SPHERE-HEALTH-003",
        name="Basic Medical Kit",
        name_cn="基础药品包",
        category=SphereCategory.HEALTH,
        min_quantity=0.001,  # 1 per 1000 persons
        target_quantity=0.001,
        unit="kit",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="WHO Essential Medicines",
        description="Basic medical supplies kit per 1000 population",
    ),

    # =========================================================================
    # NFI - Non-Food Items
    # =========================================================================
    "SPHERE-NFI-001": SphereStandard(
        code="SPHERE-NFI-001",
        name="Cooking Set",
        name_cn="烹饪套装",
        category=SphereCategory.NFI,
        min_quantity=0.2,  # 1 per 5 persons
        target_quantity=0.2,
        unit="set",
        scaling_basis=ScalingBasis.PER_DISPLACED,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Sphere Handbook 2018, Food Security Standard",
        description="Cooking utensils set per 5 persons",
    ),
    "SPHERE-NFI-002": SphereStandard(
        code="SPHERE-NFI-002",
        name="Hygiene Kit",
        name_cn="卫生用品包",
        category=SphereCategory.NFI,
        min_quantity=1.0,  # per person per month
        target_quantity=1.0,
        unit="kit",
        scaling_basis=ScalingBasis.PER_PERSON,
        applicable_phases=frozenset({ResponsePhase.SHORT_TERM, ResponsePhase.RECOVERY}),
        climate_factors=_DEFAULT_CLIMATE_FACTORS,
        reference="Sphere Handbook 2018, WASH Standard",
        description="Personal hygiene items kit per person per month",
    ),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_standards_by_phase(phase: ResponsePhase) -> List[SphereStandard]:
    """
    Get all Sphere standards applicable to the given response phase.
    
    Args:
        phase: The response phase to filter by
        
    Returns:
        List of SphereStandard objects applicable to this phase
    """
    return [
        std for std in SPHERE_STANDARDS.values()
        if std.applies_to_phase(phase)
    ]


def get_standards_by_category(category: SphereCategory) -> List[SphereStandard]:
    """
    Get all Sphere standards in the given category.
    
    Args:
        category: The Sphere category to filter by
        
    Returns:
        List of SphereStandard objects in this category
    """
    return [
        std for std in SPHERE_STANDARDS.values()
        if std.category == category
    ]


def get_standard(code: str) -> SphereStandard:
    """
    Get a specific Sphere standard by code.
    
    Args:
        code: The standard code (e.g., "SPHERE-WASH-001")
        
    Returns:
        The SphereStandard object
        
    Raises:
        KeyError: If the code is not found
    """
    if code not in SPHERE_STANDARDS:
        raise KeyError(f"Unknown Sphere standard code: {code}")
    return SPHERE_STANDARDS[code]
