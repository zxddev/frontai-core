"""Pydantic schemas for Overall Plan API requests and responses.

These schemas define the API contract for the overall-plan endpoints.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PlanModuleItem(BaseModel):
    """A single module in the plan."""

    index: int = Field(..., ge=0, le=7, description="Module index (0-7)")
    title: str = Field(..., description="Module title in Chinese")
    value: str = Field(..., description="Module content")


class TriggerPlanResponse(BaseModel):
    """Response when triggering plan generation."""

    task_id: str = Field(..., description="Unique task ID for this generation run")
    status: Literal["pending", "running"] = Field(..., description="Initial status")
    event_id: str = Field(..., description="Event ID")


class PlanStatusResponse(BaseModel):
    """Response for plan generation status query."""

    task_id: str = Field(..., description="Task ID")
    event_id: str = Field(..., description="Event ID")
    status: Literal["pending", "running", "awaiting_approval", "completed", "failed"] = Field(
        ..., description="Current workflow status"
    )
    current_phase: str | None = Field(None, description="Current phase within workflow")
    modules: list[PlanModuleItem] | None = Field(
        None, description="Generated modules (available after running phase)"
    )
    calculation_details: dict[str, Any] | None = Field(
        None, description="Calculation details for commander review"
    )
    errors: list[str] | None = Field(None, description="Error messages if status is failed")


class ApproveRequest(BaseModel):
    """Request for commander approval."""

    task_id: str = Field(..., description="Task ID to approve")
    decision: Literal["approve", "reject"] = Field(..., description="Commander decision")
    feedback: str | None = Field(None, description="Optional commander feedback")
    modifications: dict[str, str] | None = Field(
        None,
        description="Optional modifications to modules, keyed by module field name (e.g., module_4_shelter)",
    )


class ApproveResponse(BaseModel):
    """Response after commander approval."""

    task_id: str = Field(..., description="Task ID")
    status: Literal["running", "completed", "failed"] = Field(
        ..., description="Status after approval"
    )
    message: str = Field(..., description="Result message")


class DocumentResponse(BaseModel):
    """Response containing the final generated document."""

    task_id: str = Field(..., description="Task ID")
    event_id: str = Field(..., description="Event ID")
    document: str = Field(..., description="Full document content in markdown")
    generated_at: str = Field(..., description="ISO timestamp of generation")


class SituationalAwarenessOutput(BaseModel):
    """Output from CrewAI situational awareness processing.

    Used as intermediate format between CrewAI and MetaGPT.
    """

    module_0_basic_disaster: dict[str, Any] = Field(
        ..., description="Structured basic disaster situation"
    )
    module_5_secondary_disaster: dict[str, Any] = Field(
        ..., description="Structured secondary disaster risks"
    )


class ResourceCalculationInput(BaseModel):
    """Input for MetaGPT resource calculation.

    Derived from event data and situational awareness output.
    """

    affected_population: int = Field(..., ge=0, description="Total affected population")
    trapped_count: int = Field(..., ge=0, description="Number of trapped persons")
    injured_count: int = Field(..., ge=0, description="Total number of injured")
    serious_injury_count: int = Field(..., ge=0, description="Number of serious injuries")
    emergency_duration_days: int = Field(
        default=3, ge=1, description="Expected emergency duration in days"
    )
    buildings_collapsed: int = Field(default=0, ge=0, description="Number of collapsed buildings")
    buildings_damaged: int = Field(default=0, ge=0, description="Number of damaged buildings")
    roads_damaged_km: float = Field(default=0.0, ge=0, description="Kilometers of damaged roads")
    bridges_damaged: int = Field(default=0, ge=0, description="Number of damaged bridges")
    power_outage_households: int = Field(
        default=0, ge=0, description="Households without power"
    )
    communication_towers_damaged: int = Field(
        default=0, ge=0, description="Damaged communication towers"
    )
    disaster_type: str = Field(..., description="Type of disaster (earthquake, flood, etc.)")
    affected_area: str = Field(..., description="Description of affected area")


# 模块标题映射 - 按Word模板7章结构（共8个模块，index 0-7）
MODULE_TITLES: dict[int, str] = {
    0: "总体描述",  # 概述部分
    1: "当前灾情初步评估",  # 一、当前灾情初步评估
    2: "组织指挥",  # 二、组织指挥
    3: "救援力量部署与任务分工",  # 三、救援力量部署与任务分工
    4: "次生灾害预防与安全措施",  # 四、次生灾害预防与安全措施
    5: "通信与信息保障",  # 五、通信与信息保障
    6: "物资调配与运输保障",  # 六、物资调配与运输保障
    7: "救援力量自身保障",  # 七、救援力量自身保障
}

# 第三章子节标题（救援力量部署与任务分工）
CHAPTER_3_SECTIONS: dict[str, str] = {
    "force_deployment": "应急力量配置",
    "medical_deployment": "医疗救护部署",
    "engineering_deployment": "工程抢险安排",
    "resettlement": "受灾群众安置与生活保障",
}
