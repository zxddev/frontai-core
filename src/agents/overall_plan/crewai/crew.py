"""CrewAI Crew assembly for overall rescue plan generation.

业务场景：向省级指挥大厅汇报态势并申请资源

使用async_execution=True实现9个任务并行执行，大幅加速生成。
"""

import json
import logging
from typing import Any

from crewai import Crew, LLM, Process

from src.agents.overall_plan.crewai.agents import (
    create_intel_officer,
    create_rescue_coordinator,
    create_medical_coordinator,
    create_engineering_coordinator,
    create_shelter_coordinator,
    create_disaster_analyst,
    create_communication_coordinator,
    create_logistics_coordinator,
    create_support_coordinator,
)
from src.agents.overall_plan.crewai.tasks import (
    create_disaster_briefing_task,
    create_rescue_force_task,
    create_medical_task,
    create_infrastructure_task,
    create_shelter_task,
    create_secondary_disaster_task,
    create_communication_task,
    create_logistics_task,
    create_self_support_task,
    create_summary_task,
)

logger = logging.getLogger(__name__)


class OverallPlanCrewError(Exception):
    """Crew执行失败"""
    pass


# 兼容旧代码
SituationalAwarenessError = OverallPlanCrewError


def create_overall_plan_crew(llm: LLM) -> Crew:
    """创建完整的总体方案生成Crew
    
    使用async_execution=True让9个任务并行执行。
    最后一个summary任务通过context等待所有任务完成。
    
    Args:
        llm: LLM实例
        
    Returns:
        配置好的Crew
    """
    # 创建所有Agent
    intel_officer = create_intel_officer(llm)
    rescue_coordinator = create_rescue_coordinator(llm)
    medical_coordinator = create_medical_coordinator(llm)
    engineering_coordinator = create_engineering_coordinator(llm)
    shelter_coordinator = create_shelter_coordinator(llm)
    disaster_analyst = create_disaster_analyst(llm)
    communication_coordinator = create_communication_coordinator(llm)
    logistics_coordinator = create_logistics_coordinator(llm)
    support_coordinator = create_support_coordinator(llm)
    
    # 创建并行任务 (async_execution=True)
    task_0 = create_disaster_briefing_task(intel_officer, async_exec=True)
    task_1 = create_rescue_force_task(rescue_coordinator, async_exec=True)
    task_2 = create_medical_task(medical_coordinator, async_exec=True)
    task_3 = create_infrastructure_task(engineering_coordinator, async_exec=True)
    task_4 = create_shelter_task(shelter_coordinator, async_exec=True)
    task_5 = create_secondary_disaster_task(disaster_analyst, async_exec=True)
    task_6 = create_communication_task(communication_coordinator, async_exec=True)
    task_7 = create_logistics_task(logistics_coordinator, async_exec=True)
    task_8 = create_self_support_task(support_coordinator, async_exec=True)
    
    # 汇总任务 - 等待所有并行任务完成
    parallel_tasks = [task_0, task_1, task_2, task_3, task_4, task_5, task_6, task_7, task_8]
    summary_task = create_summary_task(intel_officer, context_tasks=parallel_tasks)
    
    return Crew(
        agents=[
            intel_officer,
            rescue_coordinator,
            medical_coordinator,
            engineering_coordinator,
            shelter_coordinator,
            disaster_analyst,
            communication_coordinator,
            logistics_coordinator,
            support_coordinator,
        ],
        tasks=[
            task_0, task_1, task_2, task_3, task_4,
            task_5, task_6, task_7, task_8,
            summary_task,  # 最后执行，等待所有并行任务
        ],
        process=Process.sequential,
        verbose=True,
    )


def prepare_crew_inputs(
    event_data: dict[str, Any],
    scenario_data: dict[str, Any],
    available_teams: list[dict[str, Any]],
    available_supplies: list[dict[str, Any]],
    aggregated_disaster_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """准备Crew输入数据
    
    Args:
        event_data: 单个事件数据（兼容旧逻辑）
        scenario_data: 想定基本信息
        available_teams: 可用救援队伍
        available_supplies: 可用物资
        aggregated_disaster_data: 汇总后的灾情数据（优先使用）
        
    Returns:
        Crew输入数据字典
    """
    # 格式化队伍列表
    teams_by_type = _group_teams_by_type(available_teams)
    
    all_teams_str = _format_teams_list(available_teams)
    rescue_teams_str = _format_teams_list(teams_by_type.get("search_rescue", []) + 
                                          teams_by_type.get("fire_rescue", []))
    medical_teams_str = _format_teams_list(teams_by_type.get("medical", []))
    engineering_teams_str = _format_teams_list(teams_by_type.get("engineering", []))
    
    # 格式化物资列表
    supplies_str = _format_supplies_list(available_supplies)
    
    # 优先使用汇总后的灾情数据，避免LLM编造数据
    if aggregated_disaster_data:
        trapped_count = aggregated_disaster_data.get("trapped", 0)
        injured_count = aggregated_disaster_data.get("injuries", 0)
        deaths_count = aggregated_disaster_data.get("deaths", 0)
        missing_count = aggregated_disaster_data.get("missing", 0)
        buildings_collapsed = aggregated_disaster_data.get("buildings_collapsed", 0)
        buildings_damaged = aggregated_disaster_data.get("buildings_damaged", 0)
        affected_population = aggregated_disaster_data.get("affected_population", 0) or scenario_data.get("affected_population", 0)
    else:
        # 兼容旧逻辑：从单个event_data获取
        trapped_count = event_data.get("trapped", 0)
        injured_count = event_data.get("injuries", 0)
        deaths_count = event_data.get("casualties", 0)
        missing_count = event_data.get("missing", 0)
        buildings_collapsed = event_data.get("buildings_collapsed", 0)
        buildings_damaged = event_data.get("buildings_damaged", 0)
        affected_population = scenario_data.get("affected_population", 0)
    
    serious_injury_count = int(injured_count * 0.25) if injured_count > 0 else 0
    
    # 计算救援人员规模
    rescue_teams_count = max(1, trapped_count // 50) if trapped_count > 0 else len(available_teams)
    rescue_personnel = rescue_teams_count * 30
    medical_staff = max(1, injured_count // 20) if injured_count > 0 else 0
    engineering_personnel = 0
    total_responders = rescue_personnel + medical_staff + engineering_personnel
    
    # 格式化数值显示（0显示为"待核实"）
    def format_count(value: int, unit: str = "") -> str:
        if value > 0:
            return f"{value}{unit}"
        return "待核实"
    
    return {
        # 原始数据
        "event_data": json.dumps(event_data, ensure_ascii=False, indent=2),
        "scenario_data": json.dumps(scenario_data, ensure_ascii=False, indent=2),
        
        # 关键数值（用于prompt模板）
        "trapped_count": trapped_count,
        "injured_count": injured_count,
        "deaths_count": deaths_count,
        "missing_count": missing_count,
        "serious_injury_count": serious_injury_count,
        "affected_population": affected_population,
        "buildings_collapsed": buildings_collapsed,
        "buildings_damaged": buildings_damaged,
        "roads_damaged_km": event_data.get("roads_damaged_km", 0),
        "bridges_damaged": event_data.get("bridges_damaged", 0),
        "power_outage_households": event_data.get("power_outage_households", 0),
        "days": 3,
        
        # 格式化显示值（0显示为"待核实"，防止LLM编造）
        "trapped_count_display": format_count(trapped_count, "人"),
        "injured_count_display": format_count(injured_count, "人"),
        "deaths_count_display": format_count(deaths_count, "人"),
        "missing_count_display": format_count(missing_count, "人"),
        "buildings_collapsed_display": format_count(buildings_collapsed, "栋"),
        "buildings_damaged_display": format_count(buildings_damaged, "栋"),
        "affected_population_display": format_count(affected_population, "人"),
        
        # 灾害信息
        "disaster_type": scenario_data.get("scenario_type", "earthquake"),
        "affected_area": event_data.get("address", ""),
        "magnitude": scenario_data.get("magnitude"),
        
        # 人员规模
        "rescue_teams_count": rescue_teams_count,
        "rescue_personnel": rescue_personnel,
        "medical_staff": medical_staff,
        "engineering_personnel": engineering_personnel,
        "total_responders": total_responders,
        
        # 格式化的队伍和物资列表
        "available_teams": all_teams_str,
        "available_medical_teams": medical_teams_str,
        "available_engineering_teams": engineering_teams_str,
        "available_supplies": supplies_str,
        
        # 数据来源标记
        "data_source": "database" if aggregated_disaster_data else "event_data",
    }


def parse_crew_output(crew_output: Any) -> dict[str, str]:
    """解析Crew输出为各模块内容"""
    try:
        tasks_output = crew_output.tasks_output if hasattr(crew_output, "tasks_output") else []
        
        modules = {}
        module_keys = [
            "module_0_basic_disaster",
            "module_1_rescue_force", 
            "module_2_medical",
            "module_3_infrastructure",
            "module_4_shelter",
            "module_5_secondary_disaster",
            "module_6_communication",
            "module_7_logistics",
            "module_8_self_support",
        ]
        
        for i, key in enumerate(module_keys):
            if i < len(tasks_output):
                task_out = tasks_output[i]
                if hasattr(task_out, "raw"):
                    modules[key] = str(task_out.raw)
                else:
                    modules[key] = str(task_out)
            else:
                modules[key] = "（待生成）"
        
        return modules
        
    except Exception as e:
        logger.exception("Failed to parse crew output")
        raise OverallPlanCrewError(f"Failed to parse crew output: {e}") from e


def _group_teams_by_type(teams: list[dict]) -> dict[str, list[dict]]:
    """按类型分组队伍"""
    result: dict[str, list[dict]] = {}
    for team in teams:
        team_type = team.get("team_type", "other")
        if team_type not in result:
            result[team_type] = []
        result[team_type].append(team)
    return result


def _format_teams_list(teams: list[dict]) -> str:
    """格式化队伍列表"""
    if not teams:
        return "（暂无可用队伍）"
    
    lines = []
    for team in teams[:20]:  # 限制数量避免prompt过长
        name = team.get("name", "未知")
        team_type = team.get("team_type", "")
        personnel = team.get("available_personnel", 0)
        lines.append(f"- {name}（{team_type}，{personnel}人）")
    
    if len(teams) > 20:
        lines.append(f"- ...及其他{len(teams) - 20}支队伍")
    
    return "\n".join(lines)


def _format_supplies_list(supplies: list[dict]) -> str:
    """格式化物资列表"""
    if not supplies:
        return "（暂无库存数据）"
    
    lines = []
    for supply in supplies[:15]:
        name = supply.get("name", "未知")
        quantity = supply.get("available_quantity", 0)
        unit = supply.get("unit", "")
        lines.append(f"- {name}：{quantity}{unit}")
    
    if len(supplies) > 15:
        lines.append(f"- ...及其他{len(supplies) - 15}种物资")
    
    return "\n".join(lines)


# 兼容旧代码
def create_situational_awareness_crew(llm: LLM) -> Crew:
    """兼容旧代码"""
    return create_overall_plan_crew(llm)
