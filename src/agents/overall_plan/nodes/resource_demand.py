"""
资源需求计算节点 - 基于SPHERE国际人道主义标准计算物资需求

数据驱动，使用SphereDemandCalculator计算物资需求，
不依赖LLM估算。所有数值基于国际标准算法得出。
"""
from __future__ import annotations

import logging
from typing import Any

from src.agents.overall_plan.state import OverallPlanState, BasicDisasterValue, CalculationDetails
from src.core.database import AsyncSessionLocal
from src.domains.resource_scheduling.sphere_demand_calculator import (
    SphereDemandCalculator,
    SupplyRequirement,
    DemandCalculationResult,
)
from src.domains.disaster import ResponsePhase, ClimateType
from src.domains.disaster.casualty_estimator import CasualtyEstimate
from src.infra.config.algorithm_config_service import AlgorithmConfigService

logger = logging.getLogger(__name__)


class ResourceDemandError(Exception):
    """资源需求计算失败"""
    pass


async def resource_demand_node(state: OverallPlanState) -> dict[str, Any]:
    """
    资源需求计算节点
    
    基于SPHERE国际人道主义标准计算物资需求。
    数据来源：
    - module_1_disaster_assessment: 灾情汇总数据（伤亡、被困）
    - scenario_data: 想定信息（受灾人口）
    
    输出：
    - supply_requirements: 物资需求清单
    - force_requirements: 救援力量需求
    - calculation_details: 计算详情（供指挥员审核）
    
    Args:
        state: 当前工作流状态
        
    Returns:
        包含资源需求数据的状态更新
    """
    scenario_id = state.get("scenario_id", "unknown")
    logger.info(f"[资源需求] 开始执行，scenario_id={scenario_id}")
    
    errors: list[str] = list(state.get("errors", []))
    
    try:
        # 获取灾情数据
        disaster_assessment = state.get("module_1_disaster_assessment", {})
        scenario_data = state.get("scenario_data", {})
        available_teams = state.get("available_teams", [])
        
        # 提取关键数值
        trapped_count = disaster_assessment.get("trapped", 0)
        injuries_count = disaster_assessment.get("injuries", 0)
        deaths_count = disaster_assessment.get("deaths", 0)
        affected_population = scenario_data.get("affected_population", 0)
        
        # 受灾人口必须由数据库提供，不允许凭空估算
        if affected_population == 0:
            logger.error(
                f"[资源需求] 受灾人口(affected_population)未设置，无法计算救援资源需求。"
                f"必须在scenarios_v2表中设置affected_population字段。"
            )
            raise ResourceDemandError(
                "受灾人口(affected_population)未设置，请在想定中配置受灾人口数据"
            )
        
        # 构造伤亡估算对象
        casualty_estimate = CasualtyEstimate(
            fatalities=deaths_count,
            severe_injuries=int(injuries_count * 0.25),
            minor_injuries=int(injuries_count * 0.75),
            trapped=trapped_count,
            displaced=int(affected_population * 0.3),
            affected=affected_population,
            confidence=0.7,
            methodology="database_aggregation",
        )
        
        logger.info(
            f"[资源需求] 伤亡数据: 死亡={deaths_count}, 受伤={injuries_count}, "
            f"被困={trapped_count}, 受灾人口={affected_population}"
        )
        
        # 使用SPHERE标准计算物资需求
        supply_requirements: list[dict[str, Any]] = []
        force_requirements: list[dict[str, Any]] = []
        calculation_details: CalculationDetails = {}
        
        async with AsyncSessionLocal() as db:
            config_service = AlgorithmConfigService(db)
            
            try:
                sphere_calculator = SphereDemandCalculator(db, config_service)
                
                # 计算救援人员需求
                rescuer_count = _calculate_rescuer_count(
                    trapped_count=trapped_count,
                    available_teams=available_teams,
                )
                
                # 计算物资需求（立即响应阶段，3天）
                demand_result = await sphere_calculator.calculate(
                    phase=ResponsePhase.IMMEDIATE,
                    casualty_estimate=casualty_estimate,
                    duration_days=3,
                    climate=ClimateType.TEMPERATE,
                    rescuer_count=rescuer_count,
                )
                
                # 转换为字典列表
                for req in demand_result.requirements:
                    supply_requirements.append({
                        "supply_code": req.supply_code,
                        "supply_name": req.supply_name,
                        "category": req.category,
                        "quantity": req.quantity,
                        "unit": req.unit,
                        "priority": req.priority,
                        "calculation_basis": f"SPHERE标准-{req.scaling_basis}",
                    })
                
                logger.info(f"[资源需求] SPHERE计算完成: {len(supply_requirements)}种物资")
                
                # 输出前5项物资需求明细（用于验证计算正确性）
                for req in supply_requirements[:5]:
                    logger.info(
                        f"[资源需求]   - {req['supply_name']}: "
                        f"{req['quantity']:,.0f}{req['unit']} ({req['calculation_basis']})"
                    )
                
            except Exception as e:
                # 不允许降级，SPHERE计算失败必须暴露问题
                logger.exception(f"[资源需求] SPHERE计算失败: {e}")
                raise ResourceDemandError(
                    f"SPHERE物资需求计算失败，请检查Sphere标准配置: {e}"
                ) from e
        
        # 计算救援力量需求
        force_requirements = _calculate_force_requirements(
            trapped_count=trapped_count,
            injuries_count=injuries_count,
            affected_population=affected_population,
        )
        
        # 构建计算详情
        calculation_details = {
            "affected_population": affected_population,
            "trapped_count": trapped_count,
            "injured_count": injuries_count,
            "serious_injury_count": int(injuries_count * 0.25),
            "emergency_duration_days": 3,
            "calculation_basis": "SPHERE国际人道主义标准",
        }
        
        # 生成物资调配模块文本
        logistics_text = _generate_logistics_text(supply_requirements)
        
        # 生成救援力量部署模块文本
        force_text = _generate_force_deployment_text(force_requirements)
        
        # 生成群众安置模块文本
        resettlement_text = _generate_resettlement_text(
            affected_population=affected_population,
            supply_requirements=supply_requirements,
        )
        
        logger.info(
            f"[资源需求] 完成: {len(supply_requirements)}种物资, "
            f"{len(force_requirements)}类力量需求"
        )
        
        return {
            "supply_requirements": supply_requirements,
            "force_requirements": force_requirements,
            "calculation_details": calculation_details,
            "module_6_logistics": logistics_text,
            "module_3_force_deployment": force_text,
            "module_3_resettlement": resettlement_text,
            # 兼容旧字段
            "module_1_rescue_force": force_text,
            "module_4_shelter": resettlement_text,
            "module_7_logistics": logistics_text,
            "current_phase": "resource_demand_completed",
            "errors": errors,
        }
        
    except Exception as e:
        logger.exception(f"[资源需求] 失败: {e}")
        raise ResourceDemandError(f"资源需求计算失败: {e}") from e


def _calculate_rescuer_count(
    trapped_count: int,
    available_teams: list[dict[str, Any]],
) -> int:
    """
    计算救援人员总数
    
    基于SPHERE标准：每50名被困人员配1支救援队（约30人）
    """
    # 基于被困人数计算需求
    if trapped_count > 0:
        teams_needed = max(1, trapped_count // 50)
        personnel_needed = teams_needed * 30
    else:
        personnel_needed = 0
    
    # 统计可用人员
    available_personnel = sum(
        team.get("available_personnel", 0) 
        for team in available_teams
    )
    
    return max(personnel_needed, available_personnel)


def _calculate_force_requirements(
    trapped_count: int,
    injuries_count: int,
    affected_population: int,
) -> list[dict[str, Any]]:
    """
    计算救援力量需求（基于SPHERE标准）
    """
    requirements = []
    
    # 搜救力量（每50名被困人员1支队伍）
    if trapped_count > 0:
        rescue_teams = max(1, trapped_count // 50)
        requirements.append({
            "type": "search_rescue",
            "name": "搜救队伍",
            "quantity": rescue_teams,
            "unit": "支",
            "personnel": rescue_teams * 30,
            "calculation_basis": f"SPHERE标准: {trapped_count}被困÷50人/队",
        })
    
    # 医疗力量（每20名伤员1名医护）
    if injuries_count > 0:
        medical_staff = max(1, injuries_count // 20)
        requirements.append({
            "type": "medical",
            "name": "医护人员",
            "quantity": medical_staff,
            "unit": "人",
            "calculation_basis": f"SPHERE标准: {injuries_count}伤员÷20人/医护",
        })
        
        # 救护车（每10名伤员1辆）
        ambulances = max(1, injuries_count // 10)
        requirements.append({
            "type": "ambulance",
            "name": "救护车",
            "quantity": ambulances,
            "unit": "辆",
            "calculation_basis": f"SPHERE标准: {injuries_count}伤员÷10人/车",
        })
    
    # 安置力量（每1000人1个安置点管理团队）
    if affected_population > 0:
        shelter_teams = max(1, affected_population // 1000)
        requirements.append({
            "type": "shelter",
            "name": "安置点管理团队",
            "quantity": shelter_teams,
            "unit": "个",
            "calculation_basis": f"每1000受灾群众1个管理团队",
        })
    
    return requirements


def _calculate_basic_supplies(
    affected_population: int,
    trapped_count: int,
    injuries_count: int,
    duration_days: int,
) -> list[dict[str, Any]]:
    """
    简化的物资需求计算（SPHERE标准降级版）
    
    当SPHERE计算器不可用时使用。
    """
    supplies = []
    
    # 饮用水：每人每天20升
    if affected_population > 0:
        water = affected_population * 20 * duration_days
        supplies.append({
            "supply_code": "WATER-001",
            "supply_name": "饮用水",
            "category": "WASH",
            "quantity": water,
            "unit": "升",
            "priority": "critical",
            "calculation_basis": f"SPHERE标准: {affected_population}人×20升/天×{duration_days}天",
        })
    
    # 应急食品：每人每天0.5公斤
    if affected_population > 0:
        food = affected_population * 0.5 * duration_days
        supplies.append({
            "supply_code": "FOOD-001",
            "supply_name": "应急食品",
            "category": "FOOD",
            "quantity": food,
            "unit": "公斤",
            "priority": "critical",
            "calculation_basis": f"SPHERE标准: {affected_population}人×0.5kg/天×{duration_days}天",
        })
    
    # 帐篷：每5人1顶
    if affected_population > 0:
        tents = max(1, affected_population // 5)
        supplies.append({
            "supply_code": "SHELTER-001",
            "supply_name": "救灾帐篷",
            "category": "SHELTER",
            "quantity": tents,
            "unit": "顶",
            "priority": "high",
            "calculation_basis": f"SPHERE标准: {affected_population}人÷5人/顶",
        })
    
    # 棉被：每人2床
    if affected_population > 0:
        blankets = affected_population * 2
        supplies.append({
            "supply_code": "NFI-001",
            "supply_name": "棉被",
            "category": "NFI",
            "quantity": blankets,
            "unit": "床",
            "priority": "high",
            "calculation_basis": f"SPHERE标准: {affected_population}人×2床/人",
        })
    
    return supplies


def _generate_logistics_text(supply_requirements: list[dict[str, Any]]) -> str:
    """
    生成物资调配模块文本
    """
    lines = []
    lines.append("## 物资调配与运输保障")
    lines.append("")
    
    if not supply_requirements:
        lines.append("*物资需求待灾情确认后计算*")
        return "\n".join(lines)
    
    lines.append("### 一、物资需求清单（基于SPHERE标准）")
    lines.append("")
    lines.append("| 物资名称 | 需求数量 | 单位 | 优先级 | 计算依据 |")
    lines.append("|---------|---------|------|-------|---------|")
    
    for req in supply_requirements[:15]:
        priority_map = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}
        priority = priority_map.get(req.get("priority", ""), req.get("priority", ""))
        lines.append(
            f"| {req['supply_name']} | {req['quantity']:,.0f} | {req['unit']} | "
            f"{priority} | {req.get('calculation_basis', 'SPHERE标准')} |"
        )
    
    if len(supply_requirements) > 15:
        lines.append(f"| ... | | | | 共{len(supply_requirements)}项 |")
    
    lines.append("")
    lines.append("### 二、请求事项")
    lines.append("")
    lines.append("1. 请求应急物资储备中心紧急调拨上述物资")
    lines.append("2. 请求交通部门协调运输车辆")
    lines.append("3. 请求开辟救灾物资运输绿色通道")
    
    return "\n".join(lines)


def _generate_force_deployment_text(force_requirements: list[dict[str, Any]]) -> str:
    """
    生成救援力量部署模块文本
    """
    lines = []
    lines.append("## 救援力量部署与任务分工")
    lines.append("")
    
    if not force_requirements:
        lines.append("*救援力量需求待灾情确认后计算*")
        return "\n".join(lines)
    
    lines.append("### 一、力量需求测算（基于SPHERE标准）")
    lines.append("")
    lines.append("| 力量类型 | 需求数量 | 单位 | 计算依据 |")
    lines.append("|---------|---------|------|---------|")
    
    for req in force_requirements:
        lines.append(
            f"| {req['name']} | {req['quantity']} | {req['unit']} | "
            f"{req.get('calculation_basis', '')} |"
        )
    
    lines.append("")
    lines.append("### 二、请求事项")
    lines.append("")
    lines.append("1. 请求上级调派专业救援力量")
    lines.append("2. 请求明确救援力量指挥关系")
    lines.append("3. 请求协调救援力量后勤保障")
    
    return "\n".join(lines)


def _generate_resettlement_text(
    affected_population: int,
    supply_requirements: list[dict[str, Any]],
) -> str:
    """
    生成群众安置模块文本
    """
    lines = []
    lines.append("## 受灾群众安置与生活保障")
    lines.append("")
    
    lines.append("### 一、安置规模")
    lines.append("")
    if affected_population > 0:
        lines.append(f"- **预计需安置人口**：{affected_population:,}人")
    else:
        lines.append("- **预计需安置人口**：待核实")
    lines.append("- **安置期限**：3天（应急响应期）")
    lines.append("")
    
    # 提取安置相关物资
    shelter_supplies = [
        req for req in supply_requirements 
        if req.get("category") in ["SHELTER", "NFI", "WASH", "FOOD"]
    ]
    
    if shelter_supplies:
        lines.append("### 二、安置物资需求（基于SPHERE标准）")
        lines.append("")
        for req in shelter_supplies[:8]:
            lines.append(f"- **{req['supply_name']}**：{req['quantity']:,.0f}{req['unit']}")
        lines.append("")
    
    lines.append("### 三、请求事项")
    lines.append("")
    lines.append("1. 请求民政部门协调安置点选址")
    lines.append("2. 请求调拨安置物资")
    lines.append("3. 请求协调安置点卫生设施配置")
    
    return "\n".join(lines)
