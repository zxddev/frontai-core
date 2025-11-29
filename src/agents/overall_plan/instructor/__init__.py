"""
Instructor集成模块

提供结构化LLM输出的Pydantic模型定义和Instructor客户端工具。
支持vLLM的OpenAI兼容API。
"""

from src.agents.overall_plan.instructor.client import (
    create_instructor_client,
    generate_structured_output,
    get_default_model,
    InstructorClientError,
)
from src.agents.overall_plan.instructor.models import (
    RescueForceModuleOutput,
    MedicalModuleOutput,
    InfrastructureModuleOutput,
    ShelterModuleOutput,
    CommunicationModuleOutput,
    LogisticsModuleOutput,
    SelfSupportModuleOutput,
)

__all__ = [
    "create_instructor_client",
    "generate_structured_output",
    "get_default_model",
    "InstructorClientError",
    "RescueForceModuleOutput",
    "MedicalModuleOutput",
    "InfrastructureModuleOutput",
    "ShelterModuleOutput",
    "CommunicationModuleOutput",
    "LogisticsModuleOutput",
    "SelfSupportModuleOutput",
]
