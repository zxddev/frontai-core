"""SPHERE标准资源估算器

本模块实现基于SPHERE国际人道主义标准的资源估算。
所有计算都是确定性的，相同输入将产生相同结果。

参考来源：
- SPHERE Handbook 2018 Edition: https://spherestandards.org/handbook-2018/
- UNHCR Emergency Handbook: https://emergency.unhcr.org/

重要说明：
- 标有 [SPHERE] 的常量来自官方SPHERE 2018手册
- 标有 [OPERATIONAL] 的常量是操作性规划估算值，非国际标准
- 水标准20L/人/天是SPHERE目标值（含洗浴），非最低标准(7.5L)
"""

from math import ceil
from typing import Any


class EstimatorValidationError(Exception):
    """输入验证失败时抛出"""

    pass


# =============================================================================
# 标准常量定义
# =============================================================================
# [SPHERE] = 来自SPHERE Handbook 2018官方标准
# [OPERATIONAL] = 操作性规划估算值（非国际标准）
# =============================================================================

SPHERE_STANDARDS: dict[str, float | int] = {
    # ------------------------------------------
    # [SPHERE] 水标准 - WASH Standard 2.1
    # ------------------------------------------
    # 注：7.5L是短期最低标准，15L是目标，20L是完整目标（含洗浴、清洁）
    # 这里使用20L作为规划目标值
    "water_liters_per_person_per_day": 20,  # [SPHERE] 完整目标值

    # ------------------------------------------
    # [SPHERE] 庇护所标准 - Shelter Standard 3
    # ------------------------------------------
    "tent_capacity_persons": 5,  # [SPHERE] UNHCR标准家庭帐篷容量
    "shelter_area_sqm_per_person": 3.5,  # [SPHERE] 温暖气候人均有盖面积

    # ------------------------------------------
    # [SPHERE] 生活物资标准 - Shelter Standard 4
    # ------------------------------------------
    "blankets_per_person": 2,  # [SPHERE] 目标值（温带），最低为1
    "food_kg_per_person_per_day": 0.5,  # [SPHERE] 约等于2100kcal
    "sleeping_mats_per_person": 1,  # [SPHERE] 每人1个睡垫

    # ------------------------------------------
    # [OPERATIONAL] 救援力量比率 - 操作性估算
    # ------------------------------------------
    # 注：以下比率非SPHERE标准，是基于中国应急管理实践的经验估算
    "rescue_team_per_trapped_50": 1,  # [OPERATIONAL] 1队/50被困
    "search_dogs_per_team": 2,  # [OPERATIONAL] 2只/队
    "personnel_per_rescue_team": 30,  # [OPERATIONAL] 30人/队

    # ------------------------------------------
    # [OPERATIONAL] 医疗资源比率 - 操作性估算
    # ------------------------------------------
    "medical_staff_per_injured_20": 1,  # [OPERATIONAL] 1医护/20伤员
    "stretcher_per_serious_injury": 1,  # [OPERATIONAL] 1担架/重伤员
    "ambulance_per_injured_50": 1,  # [OPERATIONAL] 1救护车/50伤员

    # ------------------------------------------
    # [OPERATIONAL] 基础设施比率 - 操作性估算
    # ------------------------------------------
    "engineering_team_per_collapsed_building_5": 1,  # [OPERATIONAL]
    "personnel_per_engineering_team": 20,  # [OPERATIONAL]
    "excavator_per_engineering_team": 2,  # [OPERATIONAL]

    # ------------------------------------------
    # [OPERATIONAL] 通信保障比率 - 操作性估算
    # ------------------------------------------
    "satellite_phone_per_rescue_team": 1,  # [OPERATIONAL]
    "mobile_base_station_per_10000_affected": 1,  # [OPERATIONAL]

    # ------------------------------------------
    # [OPERATIONAL] 物流保障比率 - 操作性估算
    # ------------------------------------------
    "truck_per_1000_affected": 1,  # [OPERATIONAL]
    "forklift_per_distribution_point": 1,  # [OPERATIONAL]

    # ------------------------------------------
    # [OPERATIONAL] 救援人员自身保障 - 操作性估算
    # ------------------------------------------
    "food_kg_per_rescuer_per_day": 0.6,  # [OPERATIONAL] 高于受灾群众
    "water_liters_per_rescuer_per_day": 25,  # [OPERATIONAL] 高于受灾群众
    "tent_capacity_rescuers": 4,  # [OPERATIONAL]
}


def _validate_non_negative(value: int | float, name: str) -> None:
    """Validate that a value is non-negative."""
    if value < 0:
        raise EstimatorValidationError(f"{name} must be non-negative, got {value}")


def _validate_positive(value: int | float, name: str) -> None:
    """Validate that a value is positive."""
    if value <= 0:
        raise EstimatorValidationError(f"{name} must be positive, got {value}")


def estimate_shelter_needs(
    affected_population: int,
    days: int = 3,
) -> dict[str, Any]:
    """Estimate temporary shelter and living supplies needs.

    Based on SPHERE standards for emergency shelter and non-food items.

    Args:
        affected_population: Number of people requiring shelter
        days: Expected duration of emergency in days

    Returns:
        Dictionary with calculated needs and basis

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(affected_population, "affected_population")
    _validate_positive(days, "days")

    if affected_population == 0:
        return {
            "tents": 0,
            "blankets": 0,
            "sleeping_mats": 0,
            "water_liters": 0,
            "food_kg": 0,
            "calculation_basis": "SPHERE Standards - zero affected population",
        }

    tents = ceil(affected_population / SPHERE_STANDARDS["tent_capacity_persons"])
    blankets = affected_population * int(SPHERE_STANDARDS["blankets_per_person"])
    sleeping_mats = affected_population * int(SPHERE_STANDARDS["sleeping_mats_per_person"])
    water_liters = (
        affected_population * int(SPHERE_STANDARDS["water_liters_per_person_per_day"]) * days
    )
    food_kg = affected_population * SPHERE_STANDARDS["food_kg_per_person_per_day"] * days

    return {
        "tents": tents,
        "blankets": blankets,
        "sleeping_mats": sleeping_mats,
        "water_liters": water_liters,
        "food_kg": food_kg,
        "calculation_basis": "SPHERE Standards",
        "parameters": {
            "affected_population": affected_population,
            "days": days,
            "tent_capacity": SPHERE_STANDARDS["tent_capacity_persons"],
            "blankets_per_person": SPHERE_STANDARDS["blankets_per_person"],
            "water_per_person_per_day": SPHERE_STANDARDS["water_liters_per_person_per_day"],
            "food_per_person_per_day": SPHERE_STANDARDS["food_kg_per_person_per_day"],
        },
    }


def estimate_rescue_force(trapped_count: int) -> dict[str, Any]:
    """Estimate rescue force requirements.

    Based on SPHERE standards and professional rescue team ratios.

    Args:
        trapped_count: Number of trapped persons requiring rescue

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(trapped_count, "trapped_count")

    if trapped_count == 0:
        return {
            "rescue_teams": 0,
            "search_dogs": 0,
            "rescue_personnel": 0,
            "calculation_basis": "SPHERE Standards - zero trapped persons",
        }

    teams = ceil(trapped_count / 50)
    search_dogs = teams * int(SPHERE_STANDARDS["search_dogs_per_team"])
    personnel = teams * int(SPHERE_STANDARDS["personnel_per_rescue_team"])

    return {
        "rescue_teams": teams,
        "search_dogs": search_dogs,
        "rescue_personnel": personnel,
        "calculation_basis": "SPHERE Standards",
        "parameters": {
            "trapped_count": trapped_count,
            "trapped_per_team": 50,
            "dogs_per_team": SPHERE_STANDARDS["search_dogs_per_team"],
            "personnel_per_team": SPHERE_STANDARDS["personnel_per_rescue_team"],
        },
    }


def estimate_medical_resources(
    injured_count: int,
    serious_injury_count: int,
) -> dict[str, Any]:
    """Estimate medical resource requirements.

    Args:
        injured_count: Total number of injured persons
        serious_injury_count: Number of seriously injured persons

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid or inconsistent
    """
    _validate_non_negative(injured_count, "injured_count")
    _validate_non_negative(serious_injury_count, "serious_injury_count")

    if serious_injury_count > injured_count:
        raise EstimatorValidationError(
            f"serious_injury_count ({serious_injury_count}) cannot exceed "
            f"injured_count ({injured_count})"
        )

    if injured_count == 0:
        return {
            "medical_staff": 0,
            "stretchers": 0,
            "ambulances": 0,
            "field_hospitals": 0,
            "calculation_basis": "SPHERE Standards - zero injured",
        }

    medical_staff = ceil(injured_count / 20)
    stretchers = serious_injury_count
    ambulances = ceil(injured_count / 50)
    field_hospitals = ceil(injured_count / 500) if injured_count >= 100 else 0

    return {
        "medical_staff": medical_staff,
        "stretchers": stretchers,
        "ambulances": ambulances,
        "field_hospitals": field_hospitals,
        "calculation_basis": "SPHERE Standards",
        "parameters": {
            "injured_count": injured_count,
            "serious_injury_count": serious_injury_count,
            "injured_per_staff": 20,
            "injured_per_ambulance": 50,
            "injured_per_field_hospital": 500,
        },
    }


def estimate_infrastructure_force(
    buildings_collapsed: int,
    buildings_damaged: int,
    roads_damaged_km: float = 0.0,
    bridges_damaged: int = 0,
    power_outage_households: int = 0,
) -> dict[str, Any]:
    """Estimate infrastructure repair force requirements.

    Args:
        buildings_collapsed: Number of collapsed buildings
        buildings_damaged: Number of damaged buildings
        roads_damaged_km: Kilometers of damaged roads
        bridges_damaged: Number of damaged bridges
        power_outage_households: Number of households without power

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(buildings_collapsed, "buildings_collapsed")
    _validate_non_negative(buildings_damaged, "buildings_damaged")
    _validate_non_negative(roads_damaged_km, "roads_damaged_km")
    _validate_non_negative(bridges_damaged, "bridges_damaged")
    _validate_non_negative(power_outage_households, "power_outage_households")

    # Structural engineering teams for buildings
    structural_teams = ceil(buildings_collapsed / 5) + ceil(buildings_damaged / 20)

    # Road repair teams
    road_teams = ceil(roads_damaged_km / 10) if roads_damaged_km > 0 else 0

    # Bridge repair teams
    bridge_teams = bridges_damaged  # One team per bridge

    # Power restoration teams
    power_teams = ceil(power_outage_households / 5000) if power_outage_households > 0 else 0

    total_engineering_teams = structural_teams + road_teams + bridge_teams + power_teams
    total_personnel = total_engineering_teams * int(
        SPHERE_STANDARDS["personnel_per_engineering_team"]
    )
    excavators = total_engineering_teams * int(SPHERE_STANDARDS["excavator_per_engineering_team"])

    return {
        "structural_engineering_teams": structural_teams,
        "road_repair_teams": road_teams,
        "bridge_repair_teams": bridge_teams,
        "power_restoration_teams": power_teams,
        "total_engineering_teams": total_engineering_teams,
        "total_personnel": total_personnel,
        "excavators": excavators,
        "calculation_basis": "Infrastructure assessment standards",
        "parameters": {
            "buildings_collapsed": buildings_collapsed,
            "buildings_damaged": buildings_damaged,
            "roads_damaged_km": roads_damaged_km,
            "bridges_damaged": bridges_damaged,
            "power_outage_households": power_outage_households,
        },
    }


def estimate_communication_needs(
    affected_population: int,
    rescue_teams: int,
    communication_towers_damaged: int = 0,
) -> dict[str, Any]:
    """Estimate communication equipment needs.

    Args:
        affected_population: Number of affected people
        rescue_teams: Number of rescue teams deployed
        communication_towers_damaged: Number of damaged communication towers

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(affected_population, "affected_population")
    _validate_non_negative(rescue_teams, "rescue_teams")
    _validate_non_negative(communication_towers_damaged, "communication_towers_damaged")

    satellite_phones = rescue_teams * int(SPHERE_STANDARDS["satellite_phone_per_rescue_team"])
    mobile_base_stations = ceil(affected_population / 10000) + communication_towers_damaged
    portable_radios = rescue_teams * 5  # 5 radios per team
    generators_for_comm = mobile_base_stations  # One generator per base station

    return {
        "satellite_phones": satellite_phones,
        "mobile_base_stations": mobile_base_stations,
        "portable_radios": portable_radios,
        "generators_for_communication": generators_for_comm,
        "calculation_basis": "Emergency communication standards",
        "parameters": {
            "affected_population": affected_population,
            "rescue_teams": rescue_teams,
            "communication_towers_damaged": communication_towers_damaged,
        },
    }


def estimate_logistics_needs(
    affected_population: int,
    shelter_needs: dict[str, Any],
    medical_needs: dict[str, Any],
    days: int = 3,
) -> dict[str, Any]:
    """Estimate logistics and transportation needs.

    Args:
        affected_population: Number of affected people
        shelter_needs: Output from estimate_shelter_needs
        medical_needs: Output from estimate_medical_resources
        days: Expected duration of emergency

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(affected_population, "affected_population")
    _validate_positive(days, "days")

    # Transport trucks for supplies
    trucks = ceil(affected_population / 1000) * days

    # Distribution points
    distribution_points = ceil(affected_population / 5000) if affected_population > 0 else 0
    forklifts = distribution_points

    # Water tankers
    total_water = shelter_needs.get("water_liters", 0)
    water_tankers = ceil(total_water / 10000) if total_water > 0 else 0

    # Medical transport (in addition to ambulances)
    medical_transport_vehicles = ceil(medical_needs.get("medical_staff", 0) / 10)

    return {
        "transport_trucks": trucks,
        "distribution_points": distribution_points,
        "forklifts": forklifts,
        "water_tankers": water_tankers,
        "medical_transport_vehicles": medical_transport_vehicles,
        "calculation_basis": "Logistics and distribution standards",
        "parameters": {
            "affected_population": affected_population,
            "days": days,
            "total_water_liters": total_water,
        },
    }


def estimate_self_support(
    total_rescue_personnel: int,
    total_medical_staff: int,
    total_engineering_personnel: int,
    days: int = 3,
) -> dict[str, Any]:
    """Estimate self-support needs for rescue forces.

    Args:
        total_rescue_personnel: Total rescue team personnel
        total_medical_staff: Total medical staff
        total_engineering_personnel: Total engineering personnel
        days: Expected duration of operations

    Returns:
        Dictionary with calculated needs

    Raises:
        EstimatorValidationError: If inputs are invalid
    """
    _validate_non_negative(total_rescue_personnel, "total_rescue_personnel")
    _validate_non_negative(total_medical_staff, "total_medical_staff")
    _validate_non_negative(total_engineering_personnel, "total_engineering_personnel")
    _validate_positive(days, "days")

    total_responders = total_rescue_personnel + total_medical_staff + total_engineering_personnel

    if total_responders == 0:
        return {
            "responder_tents": 0,
            "responder_food_kg": 0,
            "responder_water_liters": 0,
            "field_kitchens": 0,
            "rest_areas": 0,
            "calculation_basis": "Self-support standards - zero responders",
        }

    responder_tents = ceil(total_responders / int(SPHERE_STANDARDS["tent_capacity_rescuers"]))
    responder_food = total_responders * SPHERE_STANDARDS["food_kg_per_rescuer_per_day"] * days
    responder_water = (
        total_responders * int(SPHERE_STANDARDS["water_liters_per_rescuer_per_day"]) * days
    )
    field_kitchens = ceil(total_responders / 200) if total_responders > 0 else 0
    rest_areas = ceil(total_responders / 100) if total_responders > 0 else 0

    return {
        "total_responders": total_responders,
        "responder_tents": responder_tents,
        "responder_food_kg": responder_food,
        "responder_water_liters": responder_water,
        "field_kitchens": field_kitchens,
        "rest_areas": rest_areas,
        "calculation_basis": "Self-support standards",
        "parameters": {
            "total_rescue_personnel": total_rescue_personnel,
            "total_medical_staff": total_medical_staff,
            "total_engineering_personnel": total_engineering_personnel,
            "days": days,
            "tent_capacity": SPHERE_STANDARDS["tent_capacity_rescuers"],
            "food_per_rescuer_per_day": SPHERE_STANDARDS["food_kg_per_rescuer_per_day"],
            "water_per_rescuer_per_day": SPHERE_STANDARDS["water_liters_per_rescuer_per_day"],
        },
    }
