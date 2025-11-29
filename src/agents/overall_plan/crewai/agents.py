"""CrewAI Agent definitions for situational awareness.

Defines the IntelChief and DisasterAnalyst agents that collaborate
to generate modules 0 and 5 through flexible information synthesis.
"""

from typing import Any

from crewai import Agent


def create_intel_chief(llm: Any) -> Agent:
    """Create the Intelligence Chief agent.

    The Intel Chief synthesizes multi-source information to produce
    a comprehensive basic disaster situation report (Module 0).

    Args:
        llm: Language model instance

    Returns:
        Configured CrewAI Agent
    """
    return Agent(
        role="情报指挥官",
        goal="从多源信息中综合出准确、完整的灾情态势报告",
        backstory="""你是一名资深应急情报分析专家，拥有20年灾害应急管理经验。
你擅长从混乱、碎片化的信息中快速提取关键要素，能够在信息不完整的情况下
做出合理推断。你的报告将直接呈报给省级应急指挥中心，必须准确、专业、简洁。

你熟悉ICS（事故指挥系统）标准，知道如何组织灾情报告的结构。
你会关注以下关键信息：
1. 灾害基本参数（类型、强度、时间、位置）
2. 人员伤亡情况（死亡、受伤、失踪、被困）
3. 建筑物受损情况
4. 基础设施受损情况
5. 受灾范围和影响区域""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )


def create_disaster_analyst(llm: Any) -> Agent:
    """Create the Disaster Analyst agent.

    The Disaster Analyst identifies secondary disaster risks and
    provides prevention measures (Module 5).

    Args:
        llm: Language model instance

    Returns:
        Configured CrewAI Agent
    """
    return Agent(
        role="灾情分析员",
        goal="识别次生灾害风险并提出专业的安全防范建议",
        backstory="""你是一名地质与气象专家，专门研究灾害链式反应和次生灾害。
你熟悉各类次生灾害的触发条件、演化规律和防范措施。

对于地震场景，你关注：
- 余震风险：根据主震震级评估后续余震可能性
- 滑坡泥石流：地形、降雨、地质条件
- 堰塞湖：河流阻塞风险
- 火灾：燃气泄漏、电气故障引发的火灾
- 危化品泄漏：工业区的化学品风险

对于每种识别出的风险，你会提供：
1. 风险类型和等级（高/中/低）
2. 具体的防范措施
3. 监测预警建议

你的分析必须基于科学依据，不能凭空臆测。""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
