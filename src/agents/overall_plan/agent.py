"""Overall Plan Agent - Main entry point for plan generation.

This module provides the high-level OverallPlanAgent class that
wraps the LangGraph workflow and provides a simple API for:
- Triggering plan generation
- Querying status
- Resuming after human review
- Retrieving final documents
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from src.agents.overall_plan.graph import build_overall_plan_graph
from src.agents.overall_plan.schemas import (
    MODULE_TITLES,
    ApproveResponse,
    DocumentResponse,
    PlanModuleItem,
    PlanStatusResponse,
    TriggerPlanResponse,
)
from src.agents.overall_plan.state import OverallPlanState

logger = logging.getLogger(__name__)


class OverallPlanAgent:
    """High-level agent for Overall Disaster Plan generation.

    This agent wraps the LangGraph workflow and provides methods for:
    - trigger(): Start a new plan generation
    - get_status(): Query current status
    - approve(): Resume after human approval
    - get_document(): Retrieve final document

    Each plan generation run is identified by a unique task_id that
    maps to a LangGraph thread_id for state isolation.
    """

    def __init__(self, checkpointer: BaseCheckpointSaver | None = None):
        """Initialize the agent.

        Args:
            checkpointer: Optional checkpoint saver for persistence.
                         Uses MemorySaver if not provided.
        """
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = build_overall_plan_graph(self.checkpointer)
        logger.info("OverallPlanAgent initialized")

    async def trigger(self, scenario_id: str, event_id: str = "") -> TriggerPlanResponse:
        """Trigger a new plan generation.

        Args:
            scenario_id: ID of the disaster scenario (想定)
            event_id: Optional event ID (deprecated, for backward compatibility)

        Returns:
            TriggerPlanResponse with task_id and initial status
        """
        task_id = str(uuid.uuid4())
        logger.info(f"Triggering plan generation: scenario={scenario_id}, task={task_id}")

        # Prepare initial state
        initial_state: OverallPlanState = {
            "scenario_id": scenario_id,
            "event_id": event_id or "",  # 保留兼容性
            "task_id": task_id,
            "status": "pending",
            "current_phase": "initiated",
            "errors": [],
            "approved": False,
            "messages": [],
        }

        # Start the graph execution
        config = {"configurable": {"thread_id": task_id}}

        try:
            # Run until we hit the interrupt (human_review) or complete
            result = await self.graph.ainvoke(initial_state, config)
            logger.info(f"Graph execution paused/completed for task {task_id}")

            # Determine status from result
            status = result.get("status", "running")
            if status == "failed":
                return TriggerPlanResponse(
                    task_id=task_id,
                    status="running",  # We still return running, actual status from get_status
                    event_id=scenario_id,  # 返回scenario_id以便前端使用
                )

            return TriggerPlanResponse(
                task_id=task_id,
                status="running",
                event_id=scenario_id,  # 返回scenario_id以便前端使用
            )

        except Exception as e:
            logger.exception(f"Failed to trigger plan generation for scenario {scenario_id}")
            raise

    async def get_status(self, event_id: str, task_id: str) -> PlanStatusResponse:
        """Get the current status of a plan generation.

        Args:
            event_id: ID of the disaster event
            task_id: ID of the generation task

        Returns:
            PlanStatusResponse with current status and modules
        """
        logger.debug(f"Getting status for task {task_id}")

        config = {"configurable": {"thread_id": task_id}}

        try:
            # Get current state from checkpoint
            state = await self.graph.aget_state(config)

            if state is None or state.values is None:
                return PlanStatusResponse(
                    task_id=task_id,
                    event_id=event_id,
                    status="pending",
                    current_phase="not_started",
                    modules=None,
                    calculation_details=None,
                    errors=None,
                )

            values = state.values
            status = values.get("status", "running")

            # Check if we're at an interrupt (awaiting approval)
            if state.next and "human_review" in state.next:
                status = "awaiting_approval"

            # Build modules list if available
            modules = self._extract_modules(values) if status != "pending" else None

            return PlanStatusResponse(
                task_id=task_id,
                event_id=event_id,
                status=status,
                current_phase=values.get("current_phase"),
                modules=modules,
                calculation_details=values.get("calculation_details"),
                errors=values.get("errors") if values.get("errors") else None,
            )

        except Exception as e:
            logger.exception(f"Failed to get status for task {task_id}")
            return PlanStatusResponse(
                task_id=task_id,
                event_id=event_id,
                status="failed",
                current_phase="status_query_failed",
                modules=None,
                calculation_details=None,
                errors=[str(e)],
            )

    async def approve(
        self,
        event_id: str,
        task_id: str,
        decision: str,
        feedback: str | None = None,
        modifications: dict[str, str] | None = None,
    ) -> ApproveResponse:
        """Process commander approval or rejection.

        Args:
            event_id: ID of the disaster event
            task_id: ID of the generation task
            decision: "approve" or "reject"
            feedback: Optional commander feedback
            modifications: Optional module modifications

        Returns:
            ApproveResponse with resulting status
        """
        logger.info(f"Processing approval for task {task_id}: {decision}")

        config = {"configurable": {"thread_id": task_id}}

        try:
            # Resume the graph with human input
            resume_value = {
                "decision": decision,
                "feedback": feedback or "",
                "modifications": modifications or {},
            }

            # Use Command to resume from interrupt
            from langgraph.types import Command

            result = await self.graph.ainvoke(
                Command(resume=resume_value),
                config,
            )

            status = result.get("status", "running")

            if decision == "approve":
                message = "方案已批准，正在生成正式文档" if status == "running" else "方案已生成完成"
            else:
                message = "方案已退回，请根据反馈意见修正后重新提交"

            return ApproveResponse(
                task_id=task_id,
                status=status,
                message=message,
            )

        except Exception as e:
            logger.exception(f"Failed to process approval for task {task_id}")
            return ApproveResponse(
                task_id=task_id,
                status="failed",
                message=f"审批处理失败: {str(e)}",
            )

    async def get_document(self, event_id: str, task_id: str) -> DocumentResponse | None:
        """Get the final generated document.

        Args:
            event_id: ID of the disaster event
            task_id: ID of the generation task

        Returns:
            DocumentResponse with document content, or None if not ready
        """
        logger.debug(f"Getting document for task {task_id}")

        config = {"configurable": {"thread_id": task_id}}

        try:
            state = await self.graph.aget_state(config)

            if state is None or state.values is None:
                return None

            values = state.values
            document = values.get("final_document")

            if not document:
                return None

            return DocumentResponse(
                task_id=task_id,
                event_id=event_id,
                document=document,
                generated_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.exception(f"Failed to get document for task {task_id}")
            return None

    def _extract_modules(self, values: dict[str, Any]) -> list[PlanModuleItem]:
        """提取模块数据，按Word模板8章结构。
        
        注意：CrewAI返回的是字符串文本，不是dict。
        """
        modules = []

        # 第0章：总体描述 - 直接使用module_0_basic_disaster文本
        basic_disaster = values.get("module_0_basic_disaster", "")
        modules.append(PlanModuleItem(
            index=0,
            title=MODULE_TITLES[0],
            value=self._ensure_string(basic_disaster),
        ))

        # 第一章：当前灾情初步评估 - 同样使用module_0文本
        modules.append(PlanModuleItem(
            index=1,
            title=MODULE_TITLES[1],
            value=self._ensure_string(basic_disaster),
        ))

        # 第二章：组织指挥 - 目前未生成
        modules.append(PlanModuleItem(
            index=2,
            title=MODULE_TITLES[2],
            value="（待完善：组织指挥结构）",
        ))

        # 第三章：救援力量部署与任务分工 - 合并module_1到module_4
        chapter_3_value = self._merge_chapter_3(values)
        modules.append(PlanModuleItem(
            index=3,
            title=MODULE_TITLES[3],
            value=chapter_3_value,
        ))

        # 第四章：次生灾害预防与安全措施
        modules.append(PlanModuleItem(
            index=4,
            title=MODULE_TITLES[4],
            value=self._ensure_string(values.get("module_5_secondary_disaster", "")),
        ))

        # 第五章：通信与信息保障
        modules.append(PlanModuleItem(
            index=5,
            title=MODULE_TITLES[5],
            value=self._ensure_string(values.get("module_6_communication", "")),
        ))

        # 第六章：物资调配与运输保障
        modules.append(PlanModuleItem(
            index=6,
            title=MODULE_TITLES[6],
            value=self._ensure_string(values.get("module_7_logistics", "")),
        ))

        # 第七章：救援力量自身保障
        modules.append(PlanModuleItem(
            index=7,
            title=MODULE_TITLES[7],
            value=self._ensure_string(values.get("module_8_self_support", "")),
        ))

        return modules

    def _ensure_string(self, value: Any) -> str:
        """确保值是字符串，处理dict和其他类型"""
        if value is None:
            return "（待生成）"
        if isinstance(value, str):
            return value if value else "（待生成）"
        if isinstance(value, dict):
            # 如果是dict，尝试获取常见的文本字段或转为JSON
            if "narrative" in value:
                return value["narrative"]
            if "raw" in value:
                return str(value["raw"])
            import json
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    def _merge_chapter_3(self, values: dict[str, Any]) -> str:
        """从旧的9模块key合并生成第三章内容。"""
        sections = []
        
        # module_1_rescue_force -> 应急力量配置
        force = values.get("module_1_rescue_force", "")
        if force:
            sections.append(f"（一）应急力量配置\n{force}")
        
        # module_2_medical -> 医疗救护部署
        medical = values.get("module_2_medical", "")
        if medical:
            sections.append(f"（二）医疗救护部署\n{medical}")
        
        # module_3_infrastructure -> 工程抢险安排
        engineering = values.get("module_3_infrastructure", "")
        if engineering:
            sections.append(f"（三）工程抢险安排\n{engineering}")
        
        # module_4_shelter -> 受灾群众安置与生活保障
        resettlement = values.get("module_4_shelter", "")
        if resettlement:
            sections.append(f"（四）受灾群众安置与生活保障\n{resettlement}")
        
        return "\n\n".join(sections) if sections else "（待生成：救援力量部署）"
