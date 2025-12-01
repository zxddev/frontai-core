"""MetaGPT Official Scribe role for document generation.

Generates the final formal document by integrating all 9 modules
into a standard format suitable for official submission.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI

from src.agents.overall_plan.schemas import MODULE_TITLES
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


class DocumentGenerationError(Exception):
    """Raised when document generation fails."""

    pass


class OfficialScribe:
    """Official Scribe role for generating formal disaster plan documents.

    This role takes the approved 9 modules and integrates them into
    a formal document following official reporting standards.
    """

    def __init__(self, llm: ChatOpenAI):
        """Initialize the Official Scribe.

        Args:
            llm: Language model instance
        """
        self.llm = llm
        self.name = "公文秘书"
        self.profile = "应急公文撰写专家"
        self.goal = "将9个模块整合为正式的总体救灾方案文档"

    async def generate_document(self, state: OverallPlanState) -> str:
        """Generate the final formal document.

        Args:
            state: Complete workflow state with all 9 modules

        Returns:
            Final document in markdown format

        Raises:
            DocumentGenerationError: If document generation fails
        """
        logger.info(f"OfficialScribe generating document for event {state.get('event_id')}")

        try:
            # Extract module contents
            modules = self._extract_modules(state)

            # Generate document header
            header = self._generate_header(state)

            # Generate document body
            body = self._generate_body(modules)

            # Generate document footer
            footer = self._generate_footer(state)

            # Combine all parts
            document = f"{header}\n\n{body}\n\n{footer}"

            logger.info("Document generation completed")
            return document

        except Exception as e:
            logger.exception("Document generation failed")
            raise DocumentGenerationError(f"Document generation failed: {e}") from e

    def _extract_modules(self, state: OverallPlanState) -> dict[int, str]:
        """Extract module contents from state."""
        modules = {}

        # Module 0: Basic Disaster Situation
        module_0_data = state.get("module_0_basic_disaster", {})
        modules[0] = self._format_module_0(module_0_data)

        # Modules 1-4, 6-8: Text content directly
        modules[1] = state.get("module_1_rescue_force", "")
        modules[2] = state.get("module_2_medical", "")
        modules[3] = state.get("module_3_infrastructure", "")
        modules[4] = state.get("module_4_shelter", "")

        # Module 5: Secondary Disaster
        module_5_data = state.get("module_5_secondary_disaster", {})
        modules[5] = self._format_module_5(module_5_data)

        modules[6] = state.get("module_6_communication", "")
        modules[7] = state.get("module_7_logistics", "")
        modules[8] = state.get("module_8_self_support", "")

        return modules

    def _format_module_0(self, data: dict[str, Any]) -> str:
        """Format Module 0 data into text."""
        if not data:
            return "暂无数据"

        lines = []
        lines.append(f"**灾害名称**: {data.get('disaster_name', '未知')}")
        lines.append(f"**灾害类型**: {data.get('disaster_type', '未知')}")
        lines.append(f"**发生时间**: {data.get('occurrence_time', '未知')}")

        if data.get("magnitude"):
            lines.append(f"**震级**: {data.get('magnitude')}级")
        if data.get("epicenter_depth_km"):
            lines.append(f"**震源深度**: {data.get('epicenter_depth_km')}公里")

        lines.append(f"**受灾区域**: {data.get('affected_area', '未知')}")
        if data.get("affected_scope_km2"):
            lines.append(f"**受灾面积**: {data.get('affected_scope_km2')}平方公里")

        lines.append("")
        lines.append("**人员伤亡情况**:")
        lines.append(f"- 死亡: {data.get('deaths', 0)}人")
        lines.append(f"- 受伤: {data.get('injuries', 0)}人")
        lines.append(f"- 失踪: {data.get('missing', 0)}人")
        lines.append(f"- 被困: {data.get('trapped', 0)}人")

        lines.append("")
        lines.append("**建筑受损情况**:")
        lines.append(f"- 倒塌: {data.get('buildings_collapsed', 0)}栋")
        lines.append(f"- 受损: {data.get('buildings_damaged', 0)}栋")

        if data.get("infrastructure_damage"):
            lines.append("")
            lines.append("**基础设施受损情况**:")
            lines.append(data.get("infrastructure_damage"))

        return "\n".join(lines)

    def _format_module_5(self, data: dict[str, Any]) -> str:
        """Format Module 5 data into text."""
        if not data:
            return "暂无数据"

        lines = []

        risks = data.get("risks", [])
        if risks:
            lines.append("**识别的次生灾害风险**:\n")
            for i, risk in enumerate(risks, 1):
                risk_level_map = {"high": "高", "medium": "中", "low": "低"}
                level = risk_level_map.get(risk.get("risk_level", ""), risk.get("risk_level", ""))
                lines.append(f"**{i}. {risk.get('risk_type', '未知风险')}** (风险等级: {level})")

                measures = risk.get("prevention_measures", [])
                if measures:
                    lines.append("防范措施:")
                    for m in measures:
                        lines.append(f"  - {m}")

                monitoring = risk.get("monitoring_recommendations", [])
                if monitoring:
                    lines.append("监测建议:")
                    for m in monitoring:
                        lines.append(f"  - {m}")
                lines.append("")

        narrative = data.get("narrative", "")
        if narrative:
            lines.append("**综合防范方案**:")
            lines.append(narrative)

        return "\n".join(lines)

    def _generate_header(self, state: OverallPlanState) -> str:
        """Generate document header."""
        event_data = state.get("event_data", {})
        disaster_name = event_data.get("name", "灾害事件")

        now = datetime.now().strftime("%Y年%m月%d日")

        return f"""# {disaster_name}总体救灾方案

**编制单位**: 前线指挥组
**编制日期**: {now}
**文件编号**: ZTZJFA-{state.get('event_id', 'UNKNOWN')[:8].upper()}

---
"""

    def _generate_body(self, modules: dict[int, str]) -> str:
        """Generate document body with all 8 modules (index 0-7)."""
        sections = []

        for i in range(8):
            title = MODULE_TITLES.get(i, f"模块{i}")
            content = modules.get(i, "暂无内容")

            section = f"""## {i + 1}. {title}

{content}
"""
            sections.append(section)

        return "\n---\n\n".join(sections)

    def _generate_footer(self, state: OverallPlanState) -> str:
        """Generate document footer."""
        calc_details = state.get("calculation_details", {})
        basis = calc_details.get("calculation_basis", "专业标准")

        commander_feedback = state.get("commander_feedback", "")
        feedback_section = ""
        if commander_feedback:
            feedback_section = f"""
## 指挥官批示

{commander_feedback}
"""

        return f"""
---
{feedback_section}
## 附注

- 本方案基于**{basis}**进行资源需求估算
- 实际执行中应根据灾情发展动态调整
- 如有疑问请联系前线指挥组

---

*本文档由应急指挥决策支持系统自动生成*
"""
