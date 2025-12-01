"""
模块1-4, 6-8的资源计算动作

每个动作为一个模块生成内容，使用：
1. SPHERE标准估算器（确定性计算）
2. Instructor生成结构化LLM输出（专业建议）
3. Jinja2模板保证报告格式一致

注：目录名'metagpt'是历史遗留，已不再使用MetaGPT框架。
"""

import logging
from typing import Any

import instructor

from src.agents.overall_plan.metagpt.estimators import (
    estimate_communication_needs,
    estimate_infrastructure_force,
    estimate_logistics_needs,
    estimate_medical_resources,
    estimate_rescue_force,
    estimate_self_support,
    estimate_shelter_needs,
)
from src.agents.overall_plan.schemas import ResourceCalculationInput
from src.agents.overall_plan.instructor.client import (
    generate_structured_output,
    get_default_model,
)
from src.agents.overall_plan.instructor.models import (
    RescueForceModuleOutput,
    MedicalModuleOutput,
    InfrastructureModuleOutput,
    ShelterModuleOutput,
    CommunicationModuleOutput,
    LogisticsModuleOutput,
    SelfSupportModuleOutput,
)
from src.agents.overall_plan.templates.modules import render_module_template

logger = logging.getLogger(__name__)


class ResourceCalculationError(Exception):
    """资源计算失败时抛出"""

    pass


# Instructor专用提示词模板
RESCUE_FORCE_PROMPT = """你是一名专业的应急救援规划专家。请根据以下灾情数据生成救援力量部署建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 被困人员：{trapped_count}人

## 计算数据
- 需要救援队伍：{rescue_teams}支
- 搜救犬：{search_dogs}只
- 救援人员：{rescue_personnel}人

## 可用救援队伍（来自数据库）
{available_teams_list}

请基于上述可用队伍，提供专业的部署建议。
重要：只能从"可用救援队伍"列表中选择队伍，不要编造不存在的队伍名称。
如果可用队伍为空，请建议"待指挥部确定"。"""

MEDICAL_PROMPT = """你是一名专业的医疗应急规划专家。请根据以下灾情数据生成医疗救护部署建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 伤员人数：{injured_count}人
- 重伤人数：{serious_injury_count}人

## 计算数据
- 医护人员：{medical_staff}人
- 担架：{stretchers}副
- 救护车：{ambulances}辆
- 野战医院：{field_hospitals}所

## 可用医疗队伍（来自数据库）
{available_medical_teams}

请基于上述可用医疗资源，提供专业的部署建议。
重要：只能从可用队伍中选择，不要编造不存在的队伍或医院名称。
如果可用资源为空，请建议"待卫健委协调"。"""

INFRASTRUCTURE_PROMPT = """你是一名专业的基础设施抢修规划专家。请根据以下灾情数据生成基础设施抢修建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}

## 损毁情况
- 倒塌建筑：{buildings_collapsed}栋
- 受损建筑：{buildings_damaged}栋
- 损毁道路：{roads_damaged_km}公里
- 损毁桥梁：{bridges_damaged}座
- 停电户数：{power_outage_households}户

## 计算数据
- 结构工程队：{structural_engineering_teams}支
- 道路抢修队：{road_repair_teams}支
- 桥梁抢修队：{bridge_repair_teams}支
- 电力抢修队：{power_restoration_teams}支
- 挖掘机：{excavators}台

## 可用工程队伍（来自数据库）
{available_engineering_teams}

请基于上述可用队伍，提供专业的抢修建议。
重要：只能从可用队伍中选择，不要编造不存在的队伍名称。"""

SHELTER_PROMPT = """你是一名专业的应急安置规划专家。请根据以下灾情数据生成临时安置与生活保障建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 受灾人口：{affected_population}人
- 安置期限：{days}天

## 计算数据（基于SPHERE国际人道主义标准）
- 帐篷：{tents}顶
- 棉被：{blankets}床
- 饮用水：{water_liters}升
- 应急食品：{food_kg}公斤

## 可用物资库存（来自数据库）
{available_supplies_list}

请基于上述可用物资，提供专业的安置建议。
重要：物资调拨建议应参考可用库存，如库存不足请明确说明缺口。"""

COMMUNICATION_PROMPT = """你是一名专业的应急通信保障专家。请根据以下灾情数据生成通信与信息保障建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 受灾人口：{affected_population}人
- 救援队伍：{rescue_teams}支

## 计算数据
- 卫星电话：{satellite_phones}部
- 移动基站车：{mobile_base_stations}辆
- 便携式电台：{portable_radios}部
- 通信保障发电机：{generators_for_communication}台

请提供专业的建议，包括网络恢复方案、指挥通信保障措施、信息发布与舆情监控、通信冗余方案和频率协调。"""

LOGISTICS_PROMPT = """你是一名专业的应急物流保障专家。请根据以下灾情数据生成物资调拨与运输保障建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 受灾人口：{affected_population}人
- 安置期限：{days}天

## 计算数据
- 运输车辆：{transport_trucks}辆
- 物资分发点：{distribution_points}个
- 叉车：{forklifts}辆
- 水车：{water_tankers}辆

请提供专业的建议，包括物资来源、运输通道规划、物资分发方案、追踪系统和道路中断替代方案。"""

SELF_SUPPORT_PROMPT = """你是一名专业的后勤保障专家。请根据以下数据生成救援力量自身保障建议。

## 灾情背景
- 灾害类型：{disaster_type}
- 受灾区域：{affected_area}
- 保障期限：{days}天

## 救援力量规模
- 救援人员：{total_rescue_personnel}人
- 医护人员：{total_medical_staff}人
- 工程人员：{total_engineering_personnel}人
- 总计：{total_responders}人

## 计算数据
- 救援人员帐篷：{responder_tents}顶
- 餐食：{responder_food_kg}公斤
- 饮用水：{responder_water_liters}升
- 野战厨房：{field_kitchens}个

请提供专业的建议，包括驻扎安排、轮换制度、健康监测、安全防护装备和心理支持。"""


async def calculate_rescue_force_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
) -> tuple[str, dict[str, Any]]:
    """Generate Module 1 - Emergency Rescue Force Deployment.

    Args:
        client: Instructor client instance
        input_data: Validated input data

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_rescue_force(input_data.trapped_count)

    prompt = RESCUE_FORCE_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        trapped_count=input_data.trapped_count,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=RescueForceModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_1", {
        **calculation,
        **suggestions.model_dump(),
        "trapped_count": input_data.trapped_count,
    })

    return text, calculation


async def calculate_medical_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
) -> tuple[str, dict[str, Any]]:
    """Generate Module 2 - Medical Response Deployment.

    Args:
        client: Instructor client instance
        input_data: Validated input data

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_medical_resources(
        input_data.injured_count,
        input_data.serious_injury_count,
    )

    prompt = MEDICAL_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        injured_count=input_data.injured_count,
        serious_injury_count=input_data.serious_injury_count,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=MedicalModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_2", {
        **calculation,
        "injured_count": input_data.injured_count,
        "serious_injury_count": input_data.serious_injury_count,
        **suggestions.model_dump(),
    })

    return text, calculation


async def calculate_infrastructure_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
) -> tuple[str, dict[str, Any]]:
    """Generate Module 3 - Infrastructure Repair.

    Args:
        client: Instructor client instance
        input_data: Validated input data

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_infrastructure_force(
        input_data.buildings_collapsed,
        input_data.buildings_damaged,
        input_data.roads_damaged_km,
        input_data.bridges_damaged,
        input_data.power_outage_households,
    )

    prompt = INFRASTRUCTURE_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        buildings_collapsed=input_data.buildings_collapsed,
        buildings_damaged=input_data.buildings_damaged,
        roads_damaged_km=input_data.roads_damaged_km,
        bridges_damaged=input_data.bridges_damaged,
        power_outage_households=input_data.power_outage_households,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=InfrastructureModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_3", {
        **calculation,
        "buildings_collapsed": input_data.buildings_collapsed,
        "buildings_damaged": input_data.buildings_damaged,
        "roads_damaged_km": input_data.roads_damaged_km,
        "bridges_damaged": input_data.bridges_damaged,
        "power_outage_households": input_data.power_outage_households,
        **suggestions.model_dump(),
    })

    return text, calculation


async def calculate_shelter_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
) -> tuple[str, dict[str, Any]]:
    """Generate Module 4 - Temporary Shelter and Living Support.

    Args:
        client: Instructor client instance
        input_data: Validated input data

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_shelter_needs(
        input_data.affected_population,
        input_data.emergency_duration_days,
    )

    prompt = SHELTER_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        affected_population=input_data.affected_population,
        days=input_data.emergency_duration_days,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=ShelterModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_4", {
        **calculation,
        "affected_population": input_data.affected_population,
        "days": input_data.emergency_duration_days,
        **suggestions.model_dump(),
    })

    return text, calculation


async def calculate_communication_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
    rescue_calculation: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Generate Module 6 - Communication and Information Support.

    Args:
        client: Instructor client instance
        input_data: Validated input data
        rescue_calculation: Output from rescue force calculation

    Returns:
        Tuple of (module text, calculation details)
    """
    rescue_teams = rescue_calculation.get("rescue_teams", 0)
    calculation = estimate_communication_needs(
        input_data.affected_population,
        rescue_teams,
        input_data.communication_towers_damaged,
    )

    prompt = COMMUNICATION_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        affected_population=input_data.affected_population,
        rescue_teams=rescue_teams,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=CommunicationModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_6", {
        **calculation,
        "rescue_teams": rescue_teams,
        "affected_population": input_data.affected_population,
        **suggestions.model_dump(),
    })

    return text, calculation


async def calculate_logistics_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
    shelter_calculation: dict[str, Any],
    medical_calculation: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Generate Module 7 - Logistics and Transportation Support.

    Args:
        client: Instructor client instance
        input_data: Validated input data
        shelter_calculation: Output from shelter calculation
        medical_calculation: Output from medical calculation

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_logistics_needs(
        input_data.affected_population,
        shelter_calculation,
        medical_calculation,
        input_data.emergency_duration_days,
    )

    prompt = LOGISTICS_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        affected_population=input_data.affected_population,
        days=input_data.emergency_duration_days,
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=LogisticsModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_7", {
        **calculation,
        "affected_population": input_data.affected_population,
        "days": input_data.emergency_duration_days,
        **suggestions.model_dump(),
    })

    return text, calculation


async def calculate_self_support_module(
    client: instructor.Instructor,
    input_data: ResourceCalculationInput,
    rescue_calculation: dict[str, Any],
    medical_calculation: dict[str, Any],
    infrastructure_calculation: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Generate Module 8 - Rescue Force Self-Support.

    Args:
        client: Instructor client instance
        input_data: Validated input data
        rescue_calculation: Output from rescue force calculation
        medical_calculation: Output from medical calculation
        infrastructure_calculation: Output from infrastructure calculation

    Returns:
        Tuple of (module text, calculation details)
    """
    calculation = estimate_self_support(
        rescue_calculation.get("rescue_personnel", 0),
        medical_calculation.get("medical_staff", 0),
        infrastructure_calculation.get("total_personnel", 0),
        input_data.emergency_duration_days,
    )

    prompt = SELF_SUPPORT_PROMPT.format(
        disaster_type=input_data.disaster_type,
        affected_area=input_data.affected_area,
        days=input_data.emergency_duration_days,
        total_rescue_personnel=rescue_calculation.get("rescue_personnel", 0),
        total_medical_staff=medical_calculation.get("medical_staff", 0),
        total_engineering_personnel=infrastructure_calculation.get("total_personnel", 0),
        **calculation,
    )

    suggestions = await generate_structured_output(
        client=client,
        model=get_default_model(),
        response_model=SelfSupportModuleOutput,
        prompt=prompt,
    )

    text = render_module_template("module_8", {
        **calculation,
        "total_rescue_personnel": rescue_calculation.get("rescue_personnel", 0),
        "total_medical_staff": medical_calculation.get("medical_staff", 0),
        "total_engineering_personnel": infrastructure_calculation.get("total_personnel", 0),
        "days": input_data.emergency_duration_days,
        **suggestions.model_dump(),
    })

    return text, calculation
