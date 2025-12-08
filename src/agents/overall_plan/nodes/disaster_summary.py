"""
灾情数据汇总节点 - 从数据库数据汇总灾情态势

数据驱动，不依赖LLM生成数值数据。
汇总 events_data 和 disaster_situations 中的伤亡被困数据，
输出结构化的灾情评估数据供后续节点使用。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.agents.overall_plan.state import OverallPlanState, BasicDisasterValue

logger = logging.getLogger(__name__)


class DisasterSummaryError(Exception):
    """灾情汇总失败"""
    pass


async def disaster_summary_node(state: OverallPlanState) -> dict[str, Any]:
    """
    灾情数据汇总节点
    
    从 load_context 加载的数据中汇总灾情态势，输出结构化数据。
    数据来源：
    - scenario_data: 想定基本信息（灾害类型、震级、受灾人口）
    - main_event: 主事件（is_main_event=true）
    - related_events: 相关事件列表（次生灾害等）
    - aggregated_disaster_data: 已汇总的灾情数据（load_context预处理）
    - disaster_situations: 灾情态势（灾害扩散、严重程度）
    
    Args:
        state: 当前工作流状态
        
    Returns:
        包含结构化灾情数据的状态更新
    """
    scenario_id = state.get("scenario_id", "unknown")
    logger.info(f"[灾情汇总] 开始执行，scenario_id={scenario_id}")
    
    errors: list[str] = list(state.get("errors", []))
    
    try:
        # 从state获取已加载的数据
        scenario_data = state.get("scenario_data", {})
        main_event = state.get("main_event")
        related_events = state.get("related_events", [])
        aggregated_data = state.get("aggregated_disaster_data", {})
        disaster_situations = state.get("disaster_situations", [])
        
        # 输入数据追踪日志
        logger.info(
            f"[灾情汇总] 输入数据: scenario={scenario_data.get('name', 'N/A')}, "
            f"主事件={'有' if main_event else '无'}, 相关事件={len(related_events)}个, "
            f"situations数={len(disaster_situations)}"
        )
        
        if not scenario_data:
            raise DisasterSummaryError("scenario_data为空，无法汇总灾情")
        
        # 优先使用已汇总的数据，否则重新汇总
        if aggregated_data:
            disaster_assessment = _build_assessment_from_aggregated(
                aggregated_data=aggregated_data,
                scenario_data=scenario_data,
                disaster_situations=disaster_situations,
            )
        else:
            # 兼容旧逻辑：从events_data汇总
            events_data = state.get("events_data", [])
            disaster_assessment = _summarize_disaster_data(
                scenario_data=scenario_data,
                events_data=events_data,
                disaster_situations=disaster_situations,
            )
        
        # 生成总体描述文本
        overview_text = _generate_overview_text(disaster_assessment)
        
        logger.info(
            f"[灾情汇总] 完成: 死亡={disaster_assessment.get('deaths', 0)}, "
            f"受伤={disaster_assessment.get('injuries', 0)}, "
            f"被困={disaster_assessment.get('trapped', 0)}, "
            f"倒塌={disaster_assessment.get('buildings_collapsed', 0)}, "
            f"受损={disaster_assessment.get('buildings_damaged', 0)}"
        )
        
        return {
            "module_1_disaster_assessment": disaster_assessment,
            "module_0_overview": overview_text,
            # 兼容旧字段
            "module_0_basic_disaster": disaster_assessment,
            "current_phase": "disaster_summary_completed",
            "errors": errors,
        }
        
    except DisasterSummaryError:
        raise
    except Exception as e:
        logger.exception(f"[灾情汇总] 失败: {e}")
        raise DisasterSummaryError(f"灾情汇总失败: {e}") from e


def _build_assessment_from_aggregated(
    aggregated_data: dict[str, Any],
    scenario_data: dict[str, Any],
    disaster_situations: list[dict[str, Any]],
) -> BasicDisasterValue:
    """
    从已汇总的数据构建灾情评估结构
    
    Args:
        aggregated_data: load_context预处理的汇总数据
        scenario_data: 想定基本信息
        disaster_situations: 灾情态势
        
    Returns:
        结构化的灾情评估数据
    """
    # 格式化发生时间
    started_at = scenario_data.get("started_at")
    occurrence_time = "未知"
    if started_at:
        if isinstance(started_at, str):
            occurrence_time = started_at
        elif isinstance(started_at, datetime):
            occurrence_time = started_at.strftime("%Y年%m月%d日 %H:%M")
    
    # 获取受灾区域描述
    affected_area = _get_affected_area_desc(scenario_data, disaster_situations)
    
    # 构建基础设施损毁描述
    event_descriptions = aggregated_data.get("event_descriptions", [])
    infrastructure_damage = ""
    if event_descriptions:
        infrastructure_damage = "；".join(event_descriptions[:5])
        if len(event_descriptions) > 5:
            infrastructure_damage += f"等{len(event_descriptions)}处"
    
    result: BasicDisasterValue = {
        "disaster_name": aggregated_data.get("disaster_name", scenario_data.get("name", "未知灾害")),
        "disaster_type": _translate_disaster_type(aggregated_data.get("disaster_type", "earthquake")),
        "occurrence_time": occurrence_time,
        "magnitude": aggregated_data.get("magnitude"),
        "epicenter_depth_km": scenario_data.get("depth_km"),
        "affected_area": affected_area,
        "affected_scope_km2": aggregated_data.get("affected_area_km2"),
        "deaths": aggregated_data.get("deaths", 0),
        "injuries": aggregated_data.get("injuries", 0),
        "missing": aggregated_data.get("missing", 0),
        "trapped": aggregated_data.get("trapped", 0),
        "buildings_collapsed": aggregated_data.get("buildings_collapsed", 0),
        "buildings_damaged": aggregated_data.get("buildings_damaged", 0),
        "infrastructure_damage": infrastructure_damage,
    }
    
    return result


def _get_affected_area_desc(
    scenario_data: dict[str, Any],
    disaster_situations: list[dict[str, Any]],
) -> str:
    """获取受灾区域描述"""
    # 从disaster_situations获取更详细的区域描述
    for situation in disaster_situations:
        if situation.get("disaster_name"):
            return situation["disaster_name"]
    
    # 从scenario_data获取位置信息
    affected_area_desc = scenario_data.get("location", {})
    if isinstance(affected_area_desc, dict):
        lon = affected_area_desc.get("longitude", "")
        lat = affected_area_desc.get("latitude", "")
        if lon and lat:
            return f"经度{lon}°, 纬度{lat}°"
    elif affected_area_desc:
        return str(affected_area_desc)
    
    return "未知地区"


def _summarize_disaster_data(
    scenario_data: dict[str, Any],
    events_data: list[dict[str, Any]],
    disaster_situations: list[dict[str, Any]],
) -> BasicDisasterValue:
    """
    从数据库数据汇总灾情态势
    
    Args:
        scenario_data: 想定基本信息
        events_data: 事件列表
        disaster_situations: 灾情态势
        
    Returns:
        结构化的灾情评估数据
    """
    # 从scenario_data提取基本信息
    disaster_name = scenario_data.get("name", "未知灾害")
    disaster_type = scenario_data.get("scenario_type", "earthquake")
    magnitude = scenario_data.get("magnitude")
    depth_km = scenario_data.get("depth_km")
    affected_population = scenario_data.get("affected_population", 0)
    affected_area_km2 = scenario_data.get("affected_area_km2")
    started_at = scenario_data.get("started_at")
    
    # 格式化发生时间
    occurrence_time = "未知"
    if started_at:
        if isinstance(started_at, str):
            occurrence_time = started_at
        elif isinstance(started_at, datetime):
            occurrence_time = started_at.strftime("%Y年%m月%d日 %H:%M")
    
    # 从events_data汇总伤亡数据
    total_deaths = 0
    total_injuries = 0
    total_missing = 0
    total_trapped = 0
    total_buildings_collapsed = 0
    total_buildings_damaged = 0
    infrastructure_damages: list[str] = []
    
    for event in events_data:
        total_deaths += event.get("casualties", 0)
        total_injuries += event.get("injuries", 0)
        total_missing += event.get("missing", 0)
        total_trapped += event.get("trapped", 0)
        total_buildings_collapsed += event.get("buildings_collapsed", 0)
        total_buildings_damaged += event.get("buildings_damaged", 0)
        
        # 收集基础设施损毁描述
        if event.get("description"):
            infrastructure_damages.append(event["description"])
    
    # 从disaster_situations补充灾情态势
    affected_area_desc = scenario_data.get("location", {})
    if isinstance(affected_area_desc, dict):
        lon = affected_area_desc.get("longitude", "")
        lat = affected_area_desc.get("latitude", "")
        affected_area = f"经度{lon}°, 纬度{lat}°" if lon and lat else "未知地区"
    else:
        affected_area = str(affected_area_desc) if affected_area_desc else "未知地区"
    
    # 如果有灾情态势数据，提取更详细的区域描述
    for situation in disaster_situations:
        if situation.get("disaster_name"):
            affected_area = situation["disaster_name"]
            break
    
    # 汇总基础设施损毁
    infrastructure_damage = ""
    if infrastructure_damages:
        infrastructure_damage = "；".join(infrastructure_damages[:5])
        if len(infrastructure_damages) > 5:
            infrastructure_damage += f"等{len(infrastructure_damages)}处"
    
    # 构建结构化输出
    result: BasicDisasterValue = {
        "disaster_name": disaster_name,
        "disaster_type": _translate_disaster_type(disaster_type),
        "occurrence_time": occurrence_time,
        "magnitude": magnitude,
        "epicenter_depth_km": depth_km,
        "affected_area": affected_area,
        "affected_scope_km2": affected_area_km2,
        "deaths": total_deaths,
        "injuries": total_injuries,
        "missing": total_missing,
        "trapped": total_trapped,
        "buildings_collapsed": total_buildings_collapsed,
        "buildings_damaged": total_buildings_damaged,
        "infrastructure_damage": infrastructure_damage,
    }
    
    return result


def _translate_disaster_type(disaster_type: str) -> str:
    """
    灾害类型英文转中文
    """
    mapping = {
        "earthquake": "地震",
        "flood": "洪涝",
        "fire": "火灾",
        "landslide": "滑坡泥石流",
        "typhoon": "台风",
        "explosion": "爆炸",
        "hazmat": "危化品泄漏",
        "building_collapse": "建筑坍塌",
    }
    return mapping.get(disaster_type, disaster_type)


def _generate_overview_text(assessment: BasicDisasterValue) -> str:
    """
    生成总体描述文本
    
    基于结构化数据生成概述，不依赖LLM。
    """
    lines = []
    
    # 标题行
    lines.append(f"## {assessment.get('disaster_name', '灾害事件')}总体态势")
    lines.append("")
    
    # 基本情况
    lines.append("### 一、灾害基本情况")
    lines.append(f"- **灾害类型**：{assessment.get('disaster_type', '未知')}")
    lines.append(f"- **发生时间**：{assessment.get('occurrence_time', '未知')}")
    lines.append(f"- **受灾区域**：{assessment.get('affected_area', '未知')}")
    
    if assessment.get("magnitude"):
        lines.append(f"- **震级**：{assessment['magnitude']}级")
    if assessment.get("epicenter_depth_km"):
        lines.append(f"- **震源深度**：{assessment['epicenter_depth_km']}公里")
    if assessment.get("affected_scope_km2"):
        lines.append(f"- **受灾面积**：{assessment['affected_scope_km2']}平方公里")
    
    lines.append("")
    
    # 人员伤亡
    lines.append("### 二、人员伤亡情况")
    deaths = assessment.get("deaths", 0)
    injuries = assessment.get("injuries", 0)
    missing = assessment.get("missing", 0)
    trapped = assessment.get("trapped", 0)
    
    if deaths > 0:
        lines.append(f"- **死亡**：{deaths}人（已确认）")
    else:
        lines.append("- **死亡**：待核实")
    
    if injuries > 0:
        lines.append(f"- **受伤**：{injuries}人（已确认）")
    else:
        lines.append("- **受伤**：待核实")
    
    if missing > 0:
        lines.append(f"- **失联**：{missing}人")
    
    if trapped > 0:
        lines.append(f"- **被困**：{trapped}人（紧急救援中）")
    else:
        lines.append("- **被困**：待核实")
    
    lines.append("")
    
    # 建筑损毁
    lines.append("### 三、建筑房屋损毁")
    collapsed = assessment.get("buildings_collapsed", 0)
    damaged = assessment.get("buildings_damaged", 0)
    
    if collapsed > 0:
        lines.append(f"- **倒塌**：{collapsed}栋")
    else:
        lines.append("- **倒塌**：待核实")
    
    if damaged > 0:
        lines.append(f"- **受损**：{damaged}栋")
    else:
        lines.append("- **受损**：待核实")
    
    # 基础设施
    if assessment.get("infrastructure_damage"):
        lines.append("")
        lines.append("### 四、基础设施损毁")
        lines.append(assessment["infrastructure_damage"])
    
    return "\n".join(lines)
