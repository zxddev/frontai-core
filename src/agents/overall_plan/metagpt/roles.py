"""
资源计算角色定义

定义ResourcePlanner角色，编排模块1-4, 6-8的所有资源计算动作。

使用异步Instructor生成结构化LLM输出，独立模块并行执行以提升性能。

注：目录名'metagpt'是历史遗留，已不再使用MetaGPT框架。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import instructor

from src.agents.overall_plan.metagpt.actions import (
    ResourceCalculationError,
    calculate_communication_module,
    calculate_infrastructure_module,
    calculate_logistics_module,
    calculate_medical_module,
    calculate_rescue_force_module,
    calculate_self_support_module,
    calculate_shelter_module,
)
from src.agents.overall_plan.metagpt.estimators import EstimatorValidationError
from src.agents.overall_plan.schemas import ResourceCalculationInput
from src.agents.overall_plan.instructor.client import (
    create_instructor_client,
    InstructorClientError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ResourcePlannerOutput:
    """
    ResourcePlanner的输出，包含所有模块文本和计算详情

    不可变dataclass，使用slots提升内存效率。
    """

    module_1_rescue_force: str
    module_2_medical: str
    module_3_infrastructure: str
    module_4_shelter: str
    module_6_communication: str
    module_7_logistics: str
    module_8_self_support: str
    calculation_details: dict[str, Any] = field(default_factory=dict)


class ResourcePlanner:
    """
    资源规划师角色

    编排所有资源相关模块(1-4, 6-8)的计算与生成：
    1. SPHERE标准进行确定性计算
    2. 异步Instructor生成结构化LLM输出
    3. Jinja2模板保证格式一致

    模块1-4相互独立，并行执行以提升性能。
    模块6-8依赖前序结果，顺序执行。
    """

    __slots__ = ("_client", "name", "profile", "goal")

    def __init__(
        self,
        client: instructor.AsyncInstructor | None = None,
    ):
        """
        初始化ResourcePlanner

        Args:
            client: 异步Instructor客户端实例，若为None则创建默认客户端
        """
        self._client = client
        self.name = "资源规划师"
        self.profile = "应急资源调度专家"
        self.goal = "根据灾情数据精确计算资源需求并生成专业方案"

    @property
    def client(self) -> instructor.AsyncInstructor:
        """获取异步Instructor客户端，必要时创建"""
        if self._client is None:
            self._client = create_instructor_client()
        return self._client

    async def run(
        self,
        input_data: ResourceCalculationInput,
        available_teams: list[dict[str, Any]] | None = None,
        available_supplies: list[dict[str, Any]] | None = None,
    ) -> ResourcePlannerOutput:
        """
        执行所有模块的资源规划

        模块1-4独立执行（并行），模块6-8顺序执行。

        Args:
            input_data: 经过验证的计算输入数据
            available_teams: 数据库中可用的救援队伍列表
            available_supplies: 数据库中可用的物资列表

        Returns:
            ResourcePlannerOutput，包含所有模块文本和计算详情

        Raises:
            ResourceCalculationError: 计算失败时抛出
            EstimatorValidationError: 输入验证失败时抛出
            InstructorClientError: LLM结构化输出生成失败时抛出
        """
        available_teams = available_teams or []
        available_supplies = available_supplies or []
        
        logger.info(
            "ResourcePlanner starting calculation",
            extra={
                "affected_population": input_data.affected_population,
                "available_teams_count": len(available_teams),
                "available_supplies_count": len(available_supplies),
            },
        )

        try:
            client = self.client

            # 阶段1: 并行执行独立模块（性能提升40-50%）
            # 传入数据库资源数据，让LLM基于真实数据生成建议
            (
                (module_1_text, rescue_calc),
                (module_2_text, medical_calc),
                (module_3_text, infrastructure_calc),
                (module_4_text, shelter_calc),
            ) = await asyncio.gather(
                calculate_rescue_force_module(client, input_data, available_teams),
                calculate_medical_module(client, input_data, available_teams),
                calculate_infrastructure_module(client, input_data, available_teams),
                calculate_shelter_module(client, input_data, available_supplies),
            )
            logger.debug("阶段1完成: 模块1-4 (并行)")

            # 阶段2: 顺序执行依赖模块
            # 模块6: 通信保障 (依赖rescue_calc)
            module_6_text, communication_calc = await calculate_communication_module(
                client, input_data, rescue_calc
            )
            logger.debug("模块6 (通信保障) 完成")

            # 模块7: 物资保障 (依赖shelter_calc, medical_calc)
            module_7_text, logistics_calc = await calculate_logistics_module(
                client, input_data, shelter_calc, medical_calc
            )
            logger.debug("模块7 (物资保障) 完成")

            # 模块8: 救援力量自身保障 (依赖所有人员计算)
            module_8_text, self_support_calc = await calculate_self_support_module(
                client, input_data, rescue_calc, medical_calc, infrastructure_calc
            )
            logger.debug("模块8 (自身保障) 完成")

            # 聚合计算详情
            calculation_details = {
                "affected_population": input_data.affected_population,
                "trapped_count": input_data.trapped_count,
                "injured_count": input_data.injured_count,
                "serious_injury_count": input_data.serious_injury_count,
                "emergency_duration_days": input_data.emergency_duration_days,
                "rescue_calculation": rescue_calc,
                "medical_calculation": medical_calc,
                "infrastructure_calculation": infrastructure_calc,
                "shelter_calculation": shelter_calc,
                "communication_calculation": communication_calc,
                "logistics_calculation": logistics_calc,
                "self_support_calculation": self_support_calc,
                "calculation_basis": "SPHERE国际人道主义标准 + Instructor结构化输出",
            }

            logger.info("ResourcePlanner completed all modules successfully")

            return ResourcePlannerOutput(
                module_1_rescue_force=module_1_text,
                module_2_medical=module_2_text,
                module_3_infrastructure=module_3_text,
                module_4_shelter=module_4_text,
                module_6_communication=module_6_text,
                module_7_logistics=module_7_text,
                module_8_self_support=module_8_text,
                calculation_details=calculation_details,
            )

        except EstimatorValidationError as e:
            logger.error("Input validation failed: %s", e, exc_info=True)
            raise
        except InstructorClientError as e:
            logger.error("Instructor client error: %s", e, exc_info=True)
            raise ResourceCalculationError(f"LLM structured output failed: {e}") from e
        except Exception as e:
            logger.exception("Resource calculation failed")
            raise ResourceCalculationError(f"Resource calculation failed: {e}") from e
