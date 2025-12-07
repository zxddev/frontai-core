"""
缺口分析节点 - 分析资源和能力缺口

对比需求和可用资源，生成缺口报告和协调建议。
复用emergency_ai的能力缺口分析逻辑。
"""
from __future__ import annotations

import logging
from typing import Any

from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


# 能力缺口协调建议（与emergency_ai保持一致）
CAPABILITY_COORDINATION_ADVICE: dict[str, dict[str, str]] = {
    "search_rescue": {
        "name": "搜救力量",
        "agency": "消防救援支队、USAR城市搜救队",
        "hotline": "119",
    },
    "medical": {
        "name": "医疗救护",
        "agency": "卫健委、市级医院急救中心",
        "hotline": "120",
    },
    "engineering": {
        "name": "工程抢险",
        "agency": "住建部门、建工集团",
        "hotline": "市应急局调度热线",
    },
    "hazmat": {
        "name": "危化品处置",
        "agency": "消防特勤站、环保部门",
        "hotline": "119/12369",
    },
    "communication": {
        "name": "通信保障",
        "agency": "通信管理局、移动/联通/电信",
        "hotline": "市应急通信保障热线",
    },
    "logistics": {
        "name": "物资保障",
        "agency": "应急物资储备中心、红十字会",
        "hotline": "市应急局物资调度",
    },
    "shelter": {
        "name": "群众安置",
        "agency": "民政局、红十字会",
        "hotline": "12345",
    },
    "transport": {
        "name": "交通运输",
        "agency": "交通运输部门",
        "hotline": "市交通运输局",
    },
}


class GapAnalysisError(Exception):
    """缺口分析失败"""
    pass


async def gap_analysis_node(state: OverallPlanState) -> dict[str, Any]:
    """
    缺口分析节点
    
    对比资源需求和可用资源，生成缺口报告。
    数据来源：
    - force_requirements: 力量需求（来自resource_demand节点）
    - supply_requirements: 物资需求（来自resource_demand节点）
    - available_teams: 可用队伍（来自load_context）
    - available_supplies: 可用物资（来自load_context）
    
    Args:
        state: 当前工作流状态
        
    Returns:
        包含缺口分析结果的状态更新
    """
    scenario_id = state.get("scenario_id", "unknown")
    logger.info(f"[缺口分析] 开始执行，scenario_id={scenario_id}")
    
    errors: list[str] = list(state.get("errors", []))
    
    try:
        # 获取需求和可用资源
        force_requirements = state.get("force_requirements", [])
        supply_requirements = state.get("supply_requirements", [])
        available_teams = state.get("available_teams", [])
        available_supplies = state.get("available_supplies", [])
        
        # 分析力量缺口
        force_gap_report = _analyze_force_gap(
            requirements=force_requirements,
            available_teams=available_teams,
        )
        
        # 分析物资缺口
        supply_gap_report = _analyze_supply_gap(
            requirements=supply_requirements,
            available_supplies=available_supplies,
        )
        
        # 生成协调建议文本
        coordination_advice = _generate_coordination_advice(
            force_gaps=force_gap_report.get("gaps", []),
            supply_gaps=supply_gap_report.get("gaps", []),
        )
        
        # 生成通信保障模块文本
        communication_text = _generate_communication_text(
            available_teams=available_teams,
        )
        
        # 生成自身保障模块文本
        self_support_text = _generate_self_support_text(
            force_requirements=force_requirements,
        )
        
        logger.info(
            f"[缺口分析] 完成: 力量缺口{len(force_gap_report.get('gaps', []))}项, "
            f"物资缺口{len(supply_gap_report.get('gaps', []))}项"
        )
        
        return {
            "force_gap_report": force_gap_report,
            "supply_gap_report": supply_gap_report,
            "coordination_advice": coordination_advice,
            "module_5_communication": communication_text,
            "module_7_self_support": self_support_text,
            # 兼容旧字段
            "module_6_communication": communication_text,
            "module_8_self_support": self_support_text,
            "current_phase": "gap_analysis_completed",
            "errors": errors,
        }
        
    except Exception as e:
        logger.exception(f"[缺口分析] 失败: {e}")
        raise GapAnalysisError(f"缺口分析失败: {e}") from e


def _analyze_force_gap(
    requirements: list[dict[str, Any]],
    available_teams: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    分析救援力量缺口
    
    Args:
        requirements: 力量需求列表
        available_teams: 可用队伍列表
        
    Returns:
        力量缺口分析报告
    """
    gaps: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    
    # 统计可用力量
    available_by_type: dict[str, int] = {}
    for team in available_teams:
        team_type = team.get("team_type", "other")
        personnel = team.get("available_personnel", 0)
        available_by_type[team_type] = available_by_type.get(team_type, 0) + personnel
    
    # 对比需求
    for req in requirements:
        req_type = req.get("type", "")
        req_quantity = req.get("quantity", 0)
        req_personnel = req.get("personnel", req_quantity)
        
        # 查找对应类型的可用力量
        available = available_by_type.get(req_type, 0)
        
        if available < req_personnel:
            gap_amount = req_personnel - available
            gaps.append({
                "type": req_type,
                "name": req.get("name", req_type),
                "required": req_personnel,
                "available": available,
                "gap": gap_amount,
                "unit": req.get("unit", "人"),
                "severity": "critical" if gap_amount > req_personnel * 0.5 else "warning",
            })
        else:
            covered.append({
                "type": req_type,
                "name": req.get("name", req_type),
                "required": req_personnel,
                "available": available,
            })
    
    return {
        "has_gap": len(gaps) > 0,
        "gaps": gaps,
        "covered": covered,
        "summary": f"共{len(requirements)}项需求，{len(gaps)}项存在缺口",
    }


def _analyze_supply_gap(
    requirements: list[dict[str, Any]],
    available_supplies: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    分析物资缺口
    
    Args:
        requirements: 物资需求列表
        available_supplies: 可用物资列表
        
    Returns:
        物资缺口分析报告
    """
    gaps: list[dict[str, Any]] = []
    covered: list[dict[str, Any]] = []
    
    # 构建可用物资索引
    available_by_code: dict[str, float] = {}
    for supply in available_supplies:
        code = supply.get("code", supply.get("supply_code", ""))
        quantity = supply.get("available_quantity", 0)
        available_by_code[code] = available_by_code.get(code, 0) + quantity
    
    # 对比需求
    for req in requirements:
        req_code = req.get("supply_code", "")
        req_quantity = req.get("quantity", 0)
        
        # 查找对应物资
        available = available_by_code.get(req_code, 0)
        
        if available < req_quantity:
            gap_amount = req_quantity - available
            gaps.append({
                "supply_code": req_code,
                "supply_name": req.get("supply_name", req_code),
                "required": req_quantity,
                "available": available,
                "gap": gap_amount,
                "unit": req.get("unit", ""),
                "priority": req.get("priority", "medium"),
            })
        else:
            covered.append({
                "supply_code": req_code,
                "supply_name": req.get("supply_name", req_code),
                "required": req_quantity,
                "available": available,
            })
    
    return {
        "has_gap": len(gaps) > 0,
        "gaps": gaps,
        "covered": covered,
        "summary": f"共{len(requirements)}种物资，{len(gaps)}种存在缺口",
    }


def _generate_coordination_advice(
    force_gaps: list[dict[str, Any]],
    supply_gaps: list[dict[str, Any]],
) -> str:
    """
    生成协调建议文本
    """
    lines = []
    lines.append("## 资源协调建议")
    lines.append("")
    
    if not force_gaps and not supply_gaps:
        lines.append("当前资源基本满足需求，暂无紧急协调事项。")
        return "\n".join(lines)
    
    # 力量缺口协调建议
    if force_gaps:
        lines.append("### 一、救援力量协调")
        lines.append("")
        for gap in force_gaps:
            gap_type = gap.get("type", "")
            advice = CAPABILITY_COORDINATION_ADVICE.get(gap_type, {})
            
            lines.append(f"**{gap.get('name', gap_type)}缺口**：{gap.get('gap', 0)}{gap.get('unit', '')}")
            if advice:
                lines.append(f"- 建议联络：{advice.get('agency', '上级指挥部')}")
                lines.append(f"- 参考热线：{advice.get('hotline', 'N/A')}")
            else:
                lines.append("- 建议联络上级指挥部协调")
            lines.append("")
    
    # 物资缺口协调建议
    if supply_gaps:
        lines.append("### 二、物资调拨协调")
        lines.append("")
        
        # 按优先级分组
        critical_gaps = [g for g in supply_gaps if g.get("priority") == "critical"]
        high_gaps = [g for g in supply_gaps if g.get("priority") == "high"]
        other_gaps = [g for g in supply_gaps if g.get("priority") not in ["critical", "high"]]
        
        if critical_gaps:
            lines.append("**紧急调拨**：")
            for gap in critical_gaps[:5]:
                lines.append(f"- {gap['supply_name']}：缺口{gap['gap']:,.0f}{gap['unit']}")
            lines.append("")
        
        if high_gaps:
            lines.append("**优先调拨**：")
            for gap in high_gaps[:5]:
                lines.append(f"- {gap['supply_name']}：缺口{gap['gap']:,.0f}{gap['unit']}")
            lines.append("")
        
        lines.append("建议联络应急物资储备中心、红十字会等单位协调调拨。")
    
    return "\n".join(lines)


def _generate_communication_text(
    available_teams: list[dict[str, Any]],
) -> str:
    """
    生成通信保障模块文本
    """
    lines = []
    lines.append("## 通信与信息保障")
    lines.append("")
    
    # 统计救援队伍数量
    teams_count = len(available_teams)
    
    lines.append("### 一、通信设备需求")
    lines.append("")
    lines.append(f"- **卫星电话**：{max(1, teams_count)}部（每支队伍1部）")
    lines.append(f"- **便携式电台**：{max(2, teams_count * 2)}部（每支队伍2部）")
    lines.append(f"- **移动基站车**：待评估")
    lines.append("")
    
    lines.append("### 二、指挥通信保障")
    lines.append("")
    lines.append("1. 建立指挥部-各工作组-救援队伍三级通信网络")
    lines.append("2. 明确各级通信联络方式和值班制度")
    lines.append("3. 确保关键节点通信畅通")
    lines.append("")
    
    lines.append("### 三、请求事项")
    lines.append("")
    lines.append("1. 请求通信管理局协调卫星电话")
    lines.append("2. 请求调派移动基站车")
    lines.append("3. 请求协调应急通信频率")
    
    return "\n".join(lines)


def _generate_self_support_text(
    force_requirements: list[dict[str, Any]],
) -> str:
    """
    生成救援力量自身保障模块文本
    """
    lines = []
    lines.append("## 救援力量自身保障")
    lines.append("")
    
    # 统计救援人员规模
    total_personnel = sum(
        req.get("personnel", req.get("quantity", 0))
        for req in force_requirements
    )
    
    lines.append("### 一、救援人员规模")
    lines.append("")
    if total_personnel > 0:
        lines.append(f"- **预计救援人员总数**：{total_personnel}人")
    else:
        lines.append("- **预计救援人员总数**：待确认")
    lines.append("- **保障期限**：3天")
    lines.append("")
    
    # 后勤保障需求（基于SPHERE标准）
    if total_personnel > 0:
        water = total_personnel * 25 * 3
        food = total_personnel * 0.6 * 3
        
        lines.append("### 二、后勤保障需求（基于SPHERE标准）")
        lines.append("")
        lines.append(f"- **饮用水**：{water:,.0f}升（每人每天25升×3天）")
        lines.append(f"- **餐食**：{food:,.0f}公斤（每人每天0.6公斤×3天）")
        lines.append(f"- **帐篷**：{max(1, total_personnel // 10)}顶（每10人1顶）")
        lines.append("")
    
    lines.append("### 三、请求事项")
    lines.append("")
    lines.append("1. 请求保障救援人员食宿")
    lines.append("2. 请求调拨救援人员帐篷")
    lines.append("3. 请求协调野战厨房")
    lines.append("4. 请求配置安全防护装备")
    
    return "\n".join(lines)
