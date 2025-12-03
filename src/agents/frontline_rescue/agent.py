"""FrontlineRescueAgent - entry point for multi-event frontline dispatch.

This agent currently provides:
- plan(): load pending events for a scenario and prioritize them
  using DB-backed scoring rules.

后续可以在相同框架下扩展资源调度、硬规则检查与 HITL 审核。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from src.agents.frontline_rescue.graph import build_frontline_rescue_graph
from src.agents.frontline_rescue.state import FrontlineRescueState


logger = logging.getLogger(__name__)


class FrontlineRescueAgent:
    """High-level agent for frontline multi-event rescue dispatch.

    当前实现是一次性执行型：
    - plan(): 在一个调用中完成上下文加载与事件优先级计算。
    - 返回的结果可直接用于前端的多事件救援方案展示。
    """

    def __init__(self, checkpointer: BaseCheckpointSaver | None = None) -> None:
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = build_frontline_rescue_graph(self.checkpointer)
        logger.info("FrontlineRescueAgent initialized")

    async def plan(self, scenario_id: str | None = None) -> dict[str, Any]:
        """Run the frontline workflow once for a given scenario.

        Args:
            scenario_id: 想定 ID (Optional)

        Returns:
            包含 prioritized_events 等字段的状态字典。
        """

        task_id = str(uuid.uuid4())
        logger.info("[Frontline] Starting frontline plan: scenario=%s, task=%s", scenario_id, task_id)

        initial_state: FrontlineRescueState = {
            "scenario_id": scenario_id,
            "pending_events": [],
            "prioritized_events": [],
            "status": "pending",
            "current_phase": "initiated",
            "errors": [],
        }

        config = {"configurable": {"thread_id": task_id}}

        result = await self.graph.ainvoke(initial_state, config)

        # 标准化状态字段
        if "status" not in result:
            result["status"] = "completed"
        if "current_phase" not in result:
            result["current_phase"] = "completed"

        return result


__all__ = ["FrontlineRescueAgent"]
