"""
Disaster Domain Module

Provides domain models and services for disaster response planning:
- Sphere humanitarian standards
- Casualty estimation models
- Response phase requirements
"""
from .sphere_standards import (
    ResponsePhase,
    ClimateType,
    ScalingBasis,
    SphereCategory,
    SphereStandard,
    SPHERE_STANDARDS,
    get_standards_by_phase,
    get_standards_by_category,
)
from .casualty_estimator import (
    CasualtyEstimate,
    BuildingVulnerability,
    CasualtyEstimator,
)
from .phase_requirements import (
    DisasterType,
    EquipmentSet,
    Capability,
    PhaseRequirements,
    get_phase_requirements,
    get_equipment_priorities,
    get_required_capabilities,
)
from .requirement_inferencer import (
    DisasterRequirementInferencer,
    get_inferencer,
    infer_capabilities,
    infer_device_types,
    infer_supply_categories,
)

__all__ = [
    # Enums
    "ResponsePhase",
    "ClimateType",
    "ScalingBasis",
    "SphereCategory",
    "BuildingVulnerability",
    "DisasterType",
    "EquipmentSet",
    "Capability",
    # Data classes
    "SphereStandard",
    "CasualtyEstimate",
    "PhaseRequirements",
    # Constants
    "SPHERE_STANDARDS",
    # Functions
    "get_standards_by_phase",
    "get_standards_by_category",
    "get_phase_requirements",
    "get_equipment_priorities",
    "get_required_capabilities",
    # Inferencer
    "DisasterRequirementInferencer",
    "get_inferencer",
    "infer_capabilities",
    "infer_device_types",
    "infer_supply_categories",
    # Classes
    "CasualtyEstimator",
]
