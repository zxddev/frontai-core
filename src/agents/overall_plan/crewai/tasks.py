"""CrewAI Task definitions for situational awareness.

Defines tasks for generating Module 0 (Basic Disaster Situation)
and Module 5 (Secondary Disaster Prevention).
"""

from typing import Literal

from crewai import Agent, Task
from pydantic import BaseModel, Field


class BasicDisasterOutput(BaseModel):
    """Structured output for Module 0."""

    disaster_name: str = Field(default="未知灾害", description="灾害名称，如：四川泸定6.8级地震")
    disaster_type: str = Field(default="未知", description="灾害类型，如：地震、洪涝、台风")
    occurrence_time: str | None = Field(default=None, description="发生时间，ISO格式")
    magnitude: float | None = Field(default=None, description="震级或强度（如适用）")
    epicenter_depth_km: float | None = Field(default=None, description="震源深度（如适用）")
    affected_area: str = Field(default="未知区域", description="受灾区域描述")
    affected_scope_km2: float | None = Field(default=None, description="受灾面积（平方公里）")
    deaths: int = Field(default=0, description="死亡人数")
    injuries: int = Field(default=0, description="受伤人数")
    missing: int = Field(default=0, description="失踪人数")
    trapped: int = Field(default=0, description="被困人数")
    buildings_collapsed: int = Field(default=0, description="倒塌建筑数量")
    buildings_damaged: int = Field(default=0, description="受损建筑数量")
    infrastructure_damage: str = Field(default="", description="基础设施受损情况描述")


class SecondaryDisasterRiskItem(BaseModel):
    """Single risk item in Module 5."""

    risk_type: str = Field(description="风险类型，如：余震、滑坡、火灾")
    risk_level: Literal["high", "medium", "low"] = Field(description="风险等级")
    prevention_measures: list[str] = Field(description="防范措施列表")
    monitoring_recommendations: list[str] = Field(description="监测建议列表")


class SecondaryDisasterOutput(BaseModel):
    """Structured output for Module 5."""

    risks: list[SecondaryDisasterRiskItem] = Field(description="识别的风险列表")
    narrative: str = Field(description="综合性的次生灾害防范方案文本描述")


MODULE_0_OUTPUT_SCHEMA = """
{
    "disaster_name": "灾害名称，如：四川泸定6.8级地震",
    "disaster_type": "灾害类型，如：地震、洪涝、台风",
    "occurrence_time": "发生时间，ISO格式",
    "magnitude": "震级或强度（如适用）",
    "epicenter_depth_km": "震源深度（如适用）",
    "affected_area": "受灾区域描述",
    "affected_scope_km2": "受灾面积（平方公里）",
    "deaths": "死亡人数",
    "injuries": "受伤人数",
    "missing": "失踪人数",
    "trapped": "被困人数",
    "buildings_collapsed": "倒塌建筑数量",
    "buildings_damaged": "受损建筑数量",
    "infrastructure_damage": "基础设施受损情况描述"
}
"""

MODULE_5_OUTPUT_SCHEMA = """
{
    "risks": [
        {
            "risk_type": "风险类型，如：余震、滑坡、火灾、危化品泄漏",
            "risk_level": "high | medium | low",
            "prevention_measures": ["防范措施1", "防范措施2"],
            "monitoring_recommendations": ["监测建议1", "监测建议2"]
        }
    ],
    "narrative": "综合性的次生灾害防范方案文本描述"
}
"""


def create_basic_disaster_task(agent: Agent) -> Task:
    """Create task for generating Module 0 - Basic Disaster Situation.

    Args:
        agent: The Intel Chief agent

    Returns:
        Configured Task
    """
    return Task(
        description="""基于以下灾情数据，生成"灾情基本情况"模块内容。

## 输入数据
事件数据：
{event_data}

AI分析结果：
{ai_analysis}

## 输出要求
请严格按照以下JSON Schema输出，确保所有字段都有值（未知的用null）：
"""
        + MODULE_0_OUTPUT_SCHEMA
        + """

## 注意事项
1. 数值字段必须是数字类型，不要加单位
2. 时间必须是ISO格式字符串
3. 如果某项数据未知，使用null而不是0
4. infrastructure_damage字段应该是综合描述文本
5. 输出必须是合法的JSON，不要有多余内容""",
        expected_output="符合Schema的JSON对象，包含完整的灾情基本情况",
        agent=agent,
        output_pydantic=BasicDisasterOutput,
    )


def create_secondary_disaster_task(agent: Agent, context_task: Task | None = None) -> Task:
    """Create task for generating Module 5 - Secondary Disaster Prevention.

    Args:
        agent: The Disaster Analyst agent
        context_task: Optional context task (basic disaster task) for sequential execution

    Returns:
        Configured Task
    """
    return Task(
        description="""基于灾情分析结果，识别次生灾害风险并提出防范措施。

## 输入数据
AI分析结果：
{ai_analysis}

灾情基本情况：将从上一个任务的输出中获取

## 输出要求
请严格按照以下JSON Schema输出：
"""
        + MODULE_5_OUTPUT_SCHEMA
        + """

## 风险识别指南
根据灾害类型和具体情况，考虑以下风险类型：

### 地震场景
- 余震：主震6级以上通常有余震风险
- 滑坡/泥石流：山区地形需重点关注
- 堰塞湖：河流地区需关注堵塞风险
- 火灾：燃气泄漏、电气故障
- 危化品泄漏：工业区需排查

### 洪涝场景
- 滑坡/泥石流
- 水源污染
- 疫病传播

### 通用风险
- 建筑次生坍塌
- 交通事故（救援车辆密集）

## 注意事项
1. 每种风险必须评估等级（high/medium/low）
2. 防范措施要具体可执行
3. 监测建议要包含监测对象和方法
4. narrative字段应该是一段完整的方案描述文本
5. 输出必须是合法的JSON""",
        expected_output="符合Schema的JSON对象，包含风险列表和综合描述",
        agent=agent,
        output_pydantic=SecondaryDisasterOutput,
        context=[context_task] if context_task else None,
    )
