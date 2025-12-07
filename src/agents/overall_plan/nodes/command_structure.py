"""
组织指挥生成节点 - 从command_groups数据生成组织指挥结构

数据驱动，从 command_group_templates_v2 表读取工作组配置，
按灾害类型和响应级别筛选适用的工作组，生成组织指挥结构。
不依赖LLM生成，符合国家应急预案规范。
"""
from __future__ import annotations

import logging
from typing import Any

from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


class CommandStructureError(Exception):
    """组织指挥生成失败"""
    pass


async def command_structure_node(state: OverallPlanState) -> dict[str, Any]:
    """
    组织指挥生成节点
    
    从 load_context 加载的 command_groups 数据生成组织指挥结构。
    数据来源：command_group_templates_v2 表
    
    Args:
        state: 当前工作流状态
        
    Returns:
        包含组织指挥结构的状态更新
    """
    scenario_id = state.get("scenario_id", "unknown")
    logger.info(f"[组织指挥] 开始执行，scenario_id={scenario_id}")
    
    errors: list[str] = list(state.get("errors", []))
    
    try:
        # 从state获取已加载的数据
        command_groups = state.get("command_groups", [])
        scenario_data = state.get("scenario_data", {})
        
        # 获取响应级别
        response_level = scenario_data.get("response_level", "II")
        disaster_type = scenario_data.get("scenario_type", "earthquake")
        
        # 不允许fallback到默认结构，必须从数据库获取工作组配置
        if not command_groups:
            logger.error(
                f"[组织指挥] command_group_templates_v2表无匹配数据: "
                f"disaster_type={disaster_type}, response_level={response_level}"
            )
            raise CommandStructureError(
                f"工作组配置未找到，请在command_group_templates_v2表配置"
                f"disaster_type={disaster_type}, response_level={response_level}的数据"
            )
        
        # 基于数据库数据生成组织指挥结构
        command_text = _generate_command_structure(
            command_groups=command_groups,
            response_level=response_level,
            disaster_type=disaster_type,
        )
        
        logger.info(f"[组织指挥] 完成: 生成{len(command_groups)}个工作组配置")
        
        return {
            "module_2_command": command_text,
            "current_phase": "command_structure_completed",
            "errors": errors,
        }
        
    except Exception as e:
        logger.exception(f"[组织指挥] 失败: {e}")
        raise CommandStructureError(f"组织指挥生成失败: {e}") from e


def _generate_command_structure(
    command_groups: list[dict[str, Any]],
    response_level: str,
    disaster_type: str,
) -> str:
    """
    基于数据库数据生成组织指挥结构
    
    Args:
        command_groups: 工作组配置列表（来自command_group_templates_v2）
        response_level: 响应级别（I/II/III/IV）
        disaster_type: 灾害类型
        
    Returns:
        组织指挥结构Markdown文本
    """
    lines = []
    
    # 标题
    level_name = _get_response_level_name(response_level)
    disaster_name = _translate_disaster_type(disaster_type)
    lines.append(f"## 组织指挥体系（{level_name}响应）")
    lines.append("")
    
    # 指挥架构说明
    lines.append("### 一、指挥架构")
    lines.append("")
    lines.append(f"根据《国家{disaster_name}应急预案》，启动{level_name}响应，建立以下指挥体系：")
    lines.append("")
    
    # 按sort_order排序工作组
    sorted_groups = sorted(command_groups, key=lambda g: g.get("sort_order", 99))
    
    # 生成工作组列表
    lines.append("### 二、工作组设置")
    lines.append("")
    
    for idx, group in enumerate(sorted_groups, 1):
        group_name = group.get("group_name", f"工作组{idx}")
        group_code = group.get("group_code", "")
        lead_department = group.get("lead_department", "待定")
        participating_units = group.get("participating_units", [])
        responsibilities = group.get("responsibilities", "")
        
        lines.append(f"#### {idx}. {group_name}")
        lines.append("")
        lines.append(f"- **牵头单位**：{lead_department}")
        
        if participating_units:
            if isinstance(participating_units, list):
                units_str = "、".join(participating_units[:5])
                if len(participating_units) > 5:
                    units_str += f"等{len(participating_units)}个单位"
            else:
                units_str = str(participating_units)
            lines.append(f"- **参与单位**：{units_str}")
        
        if responsibilities:
            lines.append(f"- **主要职责**：{responsibilities}")
        
        lines.append("")
    
    # 指挥关系说明
    lines.append("### 三、指挥关系")
    lines.append("")
    lines.append("1. 各工作组在前线指挥部统一领导下开展工作")
    lines.append("2. 各工作组组长由牵头单位负责同志担任")
    lines.append("3. 重大事项须向指挥部请示报告")
    lines.append("")
    
    # 通信联络
    lines.append("### 四、通信联络")
    lines.append("")
    lines.append("- 指挥部值班电话：详见指挥部通讯录")
    lines.append("- 各工作组联络方式：详见工作组通讯录")
    lines.append("- 应急通信频率：待指挥部统一分配")
    
    return "\n".join(lines)


def _generate_default_command_structure(
    response_level: str,
    disaster_type: str,
) -> str:
    """
    生成默认的组织指挥结构（当数据库无数据时使用）
    
    基于国家应急预案的通用工作组设置。
    """
    lines = []
    
    level_name = _get_response_level_name(response_level)
    disaster_name = _translate_disaster_type(disaster_type)
    
    lines.append(f"## 组织指挥体系（{level_name}响应）")
    lines.append("")
    lines.append(f"根据《国家{disaster_name}应急预案》，启动{level_name}响应。")
    lines.append("")
    lines.append("### 工作组设置")
    lines.append("")
    
    # 通用工作组（基于国家应急预案）
    default_groups = [
        {
            "name": "综合协调组",
            "lead": "应急管理部门",
            "duty": "负责指挥部日常运转、信息汇总、综合协调",
        },
        {
            "name": "抢险救援组",
            "lead": "消防救援部门",
            "duty": "负责人员搜救、抢险救灾、排险除危",
        },
        {
            "name": "医疗救治组",
            "lead": "卫生健康部门",
            "duty": "负责伤员救治、卫生防疫、心理援助",
        },
        {
            "name": "群众安置组",
            "lead": "民政部门",
            "duty": "负责受灾群众转移安置、生活保障",
        },
        {
            "name": "交通保障组",
            "lead": "交通运输部门",
            "duty": "负责道路抢通、交通管制、运力保障",
        },
        {
            "name": "通信保障组",
            "lead": "通信管理部门",
            "duty": "负责应急通信保障、信息网络恢复",
        },
        {
            "name": "物资保障组",
            "lead": "发展改革部门",
            "duty": "负责救灾物资调配、市场保供",
        },
        {
            "name": "新闻宣传组",
            "lead": "宣传部门",
            "duty": "负责信息发布、舆情引导、宣传报道",
        },
    ]
    
    for idx, group in enumerate(default_groups, 1):
        lines.append(f"#### {idx}. {group['name']}")
        lines.append(f"- **牵头单位**：{group['lead']}")
        lines.append(f"- **主要职责**：{group['duty']}")
        lines.append("")
    
    lines.append("*注：具体工作组设置及人员组成待指挥部确定*")
    
    return "\n".join(lines)


def _get_response_level_name(level: str) -> str:
    """
    响应级别代码转名称
    """
    mapping = {
        "I": "一级",
        "II": "二级",
        "III": "三级",
        "IV": "四级",
        "1": "一级",
        "2": "二级",
        "3": "三级",
        "4": "四级",
    }
    return mapping.get(level, level)


def _translate_disaster_type(disaster_type: str) -> str:
    """
    灾害类型英文转中文
    """
    mapping = {
        "earthquake": "地震",
        "flood": "洪涝灾害",
        "fire": "火灾",
        "landslide": "地质灾害",
        "typhoon": "台风",
        "explosion": "爆炸事故",
        "hazmat": "危险化学品事故",
        "building_collapse": "建筑坍塌事故",
    }
    return mapping.get(disaster_type, "突发事件")
