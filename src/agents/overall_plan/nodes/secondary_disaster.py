"""
次生灾害分析节点 - 使用LLM推理次生灾害风险

保留CrewAI的合理使用场景：次生灾害种类多、组合复杂，
需要LLM推理能力，无法用规则穷举。

输入：结构化的灾害数据（来自数据库）
输出：次生灾害风险分析文本（LLM推理生成）
"""
from __future__ import annotations

import asyncio
import logging
import os
from functools import partial
from typing import Any

from crewai import Agent, Crew, LLM, Process, Task

from src.agents.overall_plan.state import OverallPlanState, SecondaryDisasterValue

logger = logging.getLogger(__name__)


class SecondaryDisasterError(Exception):
    """次生灾害分析失败"""
    pass


# 数据准确性约束规则
NO_DATA_MODIFICATION_RULE = """
## 数据准确性约束
- 你收到的灾害基本数据（类型、震级、地点）来自数据库，禁止修改
- 你的职责是基于这些事实数据推理可能的次生灾害风险
- 不要编造具体的伤亡数字、地名、机构名称
- 风险等级评估要有依据，不要随意定级
"""


async def secondary_disaster_node(state: OverallPlanState) -> dict[str, Any]:
    """
    次生灾害分析节点
    
    使用LLM推理次生灾害风险。这是CrewAI的合理使用场景，
    因为次生灾害种类多、组合复杂，无法用规则穷举。
    
    输入数据（来自数据库，非LLM生成）：
    - disaster_type: 灾害类型
    - magnitude: 震级（地震场景）
    - affected_area: 受灾区域
    - disaster_situations: 灾情态势列表
    
    Args:
        state: 当前工作流状态
        
    Returns:
        包含次生灾害分析的状态更新
    """
    scenario_id = state.get("scenario_id", "unknown")
    logger.info(f"[次生灾害] 开始执行，scenario_id={scenario_id}")
    
    errors: list[str] = list(state.get("errors", []))
    
    try:
        # 获取结构化灾害数据（来自数据库）
        scenario_data = state.get("scenario_data", {})
        disaster_assessment = state.get("module_1_disaster_assessment", {})
        disaster_situations = state.get("disaster_situations", [])
        
        disaster_type = scenario_data.get("scenario_type", "earthquake")
        magnitude = scenario_data.get("magnitude")
        affected_area = disaster_assessment.get("affected_area", "")
        
        # 准备LLM输入（结构化数据）
        llm_input = {
            "disaster_type": disaster_type,
            "disaster_type_cn": _translate_disaster_type(disaster_type),
            "magnitude": magnitude,
            "affected_area": affected_area,
            "has_building_collapse": disaster_assessment.get("buildings_collapsed", 0) > 0,
            "has_infrastructure_damage": bool(disaster_assessment.get("infrastructure_damage")),
            "disaster_situations_count": len(disaster_situations),
        }
        
        logger.info(f"[次生灾害] LLM输入: {llm_input}")
        
        # 使用LLM分析次生灾害
        analysis_result = await _analyze_with_llm(llm_input)
        
        # 解析结果
        secondary_disaster_value: SecondaryDisasterValue = {
            "risks": analysis_result.get("risks", []),
            "narrative": analysis_result.get("narrative", ""),
        }
        
        # 生成模块文本
        module_text = _format_secondary_disaster_text(secondary_disaster_value)
        
        logger.info(f"[次生灾害] 完成: 识别{len(secondary_disaster_value.get('risks', []))}类风险")
        
        return {
            "module_4_secondary_disaster": secondary_disaster_value,
            # 兼容旧字段
            "module_5_secondary_disaster": secondary_disaster_value,
            "module_4_text": module_text,
            "current_phase": "secondary_disaster_completed",
            "errors": errors,
        }
        
    except Exception as e:
        logger.exception(f"[次生灾害] 失败: {e}")
        # 降级到规则推理
        fallback_result = _rule_based_analysis(state)
        return {
            "module_4_secondary_disaster": fallback_result,
            "module_5_secondary_disaster": fallback_result,
            "current_phase": "secondary_disaster_completed",
            "errors": errors + [f"LLM分析失败，使用规则推理: {e}"],
        }


async def _analyze_with_llm(llm_input: dict[str, Any]) -> dict[str, Any]:
    """
    使用LLM分析次生灾害风险
    
    Args:
        llm_input: 结构化的灾害数据
        
    Returns:
        次生灾害分析结果
    """
    # 创建LLM
    llm = _create_llm()
    
    # 创建Agent
    agent = Agent(
        role="灾情分析员",
        goal="基于灾害数据推理可能的次生灾害风险",
        backstory="""你是省应急指挥中心灾情分析员，专门研究次生灾害风险。
        
职责：
1. 根据主灾情况识别可能的次生灾害
2. 评估各类风险的等级（高/中/低）
3. 提出具体的防范措施建议

重要原则：
- 只基于收到的灾害数据进行推理
- 不要编造数据或机构名称
- 风险等级要有明确依据
""" + NO_DATA_MODIFICATION_RULE,
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    
    # 构建任务描述
    task_desc = f"""基于以下灾害数据，分析可能的次生灾害风险：

## 灾害基本信息（来自数据库，不可修改）
- 灾害类型：{llm_input['disaster_type_cn']}
- 震级：{llm_input.get('magnitude', '未知')}
- 受灾区域：{llm_input.get('affected_area', '未知')}
- 是否有建筑倒塌：{'是' if llm_input.get('has_building_collapse') else '否'}
- 是否有基础设施损毁：{'是' if llm_input.get('has_infrastructure_damage') else '否'}

## 输出要求
请识别3-5类主要次生灾害风险，对每类风险：
1. 说明风险类型
2. 评估风险等级（高/中/低）并说明依据
3. 提出2-3条防范措施

输出格式：
### [风险类型]
- 风险等级：[高/中/低]
- 评估依据：[简要说明]
- 防范措施：
  1. [措施1]
  2. [措施2]
"""
    
    task = Task(
        description=task_desc,
        expected_output="次生灾害风险分析报告",
        agent=agent,
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )
    
    # 在线程池中运行
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(crew.kickoff, inputs={}),
    )
    
    # 解析结果
    raw_output = str(result.raw) if hasattr(result, "raw") else str(result)
    
    return {
        "risks": _parse_risks_from_text(raw_output, llm_input["disaster_type"]),
        "narrative": raw_output,
    }


def _parse_risks_from_text(text: str, disaster_type: str) -> list[dict[str, Any]]:
    """
    从LLM输出文本中解析风险列表
    
    简单解析，提取关键信息。
    """
    risks = []
    
    # 根据灾害类型定义常见次生灾害
    common_risks = {
        "earthquake": ["余震", "滑坡泥石流", "火灾", "危化品泄漏", "堰塞湖"],
        "flood": ["山洪", "泥石流", "疫病", "水污染", "电力中断"],
        "fire": ["复燃", "有毒气体", "建筑坍塌", "爆炸"],
        "landslide": ["后续滑坡", "堰塞湖", "道路阻断"],
    }
    
    risk_keywords = common_risks.get(disaster_type, ["次生灾害"])
    
    # 简单匹配
    for keyword in risk_keywords:
        if keyword in text:
            # 判断风险等级
            level = "medium"
            if "高" in text and keyword in text:
                level = "high"
            elif "低" in text and keyword in text:
                level = "low"
            
            risks.append({
                "risk_type": keyword,
                "risk_level": level,
                "prevention_measures": [f"加强{keyword}监测预警", f"制定{keyword}应急预案"],
                "monitoring_recommendations": [f"持续关注{keyword}风险动态"],
            })
    
    # 如果没有匹配到，添加通用风险
    if not risks:
        risks.append({
            "risk_type": "次生灾害",
            "risk_level": "medium",
            "prevention_measures": ["加强监测预警", "做好应急准备"],
            "monitoring_recommendations": ["持续关注灾情发展"],
        })
    
    return risks[:5]


def _rule_based_analysis(state: OverallPlanState) -> SecondaryDisasterValue:
    """
    基于规则的次生灾害分析（LLM失败时的降级方案）
    """
    scenario_data = state.get("scenario_data", {})
    disaster_type = scenario_data.get("scenario_type", "earthquake")
    magnitude = scenario_data.get("magnitude")
    
    # 规则库
    risk_rules = {
        "earthquake": [
            {
                "risk_type": "余震",
                "risk_level": "high" if magnitude and magnitude >= 6.0 else "medium",
                "prevention_measures": ["建立余震监测网络", "受损建筑设置警戒", "做好人员避险准备"],
                "monitoring_recommendations": ["持续监测地震活动", "关注地震部门预报"],
            },
            {
                "risk_type": "滑坡泥石流",
                "risk_level": "high",
                "prevention_measures": ["山区设置警戒线", "转移危险区域群众", "加强巡查监测"],
                "monitoring_recommendations": ["关注气象预报", "监测山体变形"],
            },
            {
                "risk_type": "火灾",
                "risk_level": "medium",
                "prevention_measures": ["检查燃气管线", "消除火灾隐患", "部署消防力量"],
                "monitoring_recommendations": ["巡查重点区域", "关注烟雾报警"],
            },
        ],
        "flood": [
            {
                "risk_type": "山洪",
                "risk_level": "high",
                "prevention_measures": ["转移低洼地区群众", "加强水位监测", "疏通排水设施"],
                "monitoring_recommendations": ["监测上游水情", "关注气象预警"],
            },
            {
                "risk_type": "疫病",
                "risk_level": "medium",
                "prevention_measures": ["消毒饮用水源", "处理动物尸体", "加强卫生防疫"],
                "monitoring_recommendations": ["监测水质", "关注疫情动态"],
            },
        ],
    }
    
    risks = risk_rules.get(disaster_type, [
        {
            "risk_type": "次生灾害",
            "risk_level": "medium",
            "prevention_measures": ["加强监测预警", "做好应急准备"],
            "monitoring_recommendations": ["持续关注灾情发展"],
        }
    ])
    
    # 生成描述
    narrative = f"根据{_translate_disaster_type(disaster_type)}特点，识别以下次生灾害风险：\n"
    for risk in risks:
        narrative += f"\n**{risk['risk_type']}**（风险等级：{risk['risk_level']}）\n"
        narrative += "防范措施：" + "、".join(risk["prevention_measures"]) + "\n"
    
    return {
        "risks": risks,
        "narrative": narrative,
    }


def _format_secondary_disaster_text(value: SecondaryDisasterValue) -> str:
    """
    格式化次生灾害模块文本
    """
    lines = []
    lines.append("## 次生灾害预防与安全措施")
    lines.append("")
    
    risks = value.get("risks", [])
    if not risks:
        lines.append("*次生灾害风险评估进行中*")
        return "\n".join(lines)
    
    lines.append("### 一、次生灾害风险识别")
    lines.append("")
    
    level_map = {"high": "高", "medium": "中", "low": "低"}
    
    for idx, risk in enumerate(risks, 1):
        risk_type = risk.get("risk_type", "未知")
        level = level_map.get(risk.get("risk_level", "medium"), "中")
        
        lines.append(f"#### {idx}. {risk_type}（风险等级：{level}）")
        lines.append("")
        
        measures = risk.get("prevention_measures", [])
        if measures:
            lines.append("**防范措施**：")
            for m in measures:
                lines.append(f"- {m}")
            lines.append("")
        
        monitoring = risk.get("monitoring_recommendations", [])
        if monitoring:
            lines.append("**监测建议**：")
            for m in monitoring:
                lines.append(f"- {m}")
            lines.append("")
    
    lines.append("### 二、安全措施")
    lines.append("")
    lines.append("1. 建立次生灾害监测预警机制")
    lines.append("2. 划定危险区域并设置警戒")
    lines.append("3. 制定次生灾害应急处置预案")
    
    return "\n".join(lines)


def _translate_disaster_type(disaster_type: str) -> str:
    """灾害类型英文转中文"""
    mapping = {
        "earthquake": "地震",
        "flood": "洪涝灾害",
        "fire": "火灾",
        "landslide": "地质灾害",
        "typhoon": "台风",
        "explosion": "爆炸事故",
        "hazmat": "危险化学品事故",
    }
    return mapping.get(disaster_type, disaster_type)


def _create_llm() -> LLM:
    """创建LLM实例"""
    llm_model = os.environ.get("LLM_MODEL", "/models/openai/gpt-oss-120b")
    openai_base_url = os.environ.get("OPENAI_BASE_URL", "http://192.168.31.50:8000/v1")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "dummy_key")
    request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "180"))
    
    if llm_model.startswith("openai/"):
        model = llm_model
    else:
        model = f"openai/{llm_model}"
    
    return LLM(
        model=model,
        base_url=openai_base_url,
        api_key=openai_api_key,
        temperature=0.3,
        timeout=request_timeout,
    )
