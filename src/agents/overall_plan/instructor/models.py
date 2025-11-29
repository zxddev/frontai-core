"""
结构化LLM输出的Pydantic模型定义

每个模型定义了LLM生成建议时必须遵循的结构。
SPHERE估算器计算的数值不在此定义，在模板渲染时单独注入。

这些模型仅捕获LLM生成的"创意"部分（建议、方案等）。
"""

from pydantic import BaseModel, Field


class RescueForceModuleOutput(BaseModel):
    """模块1: 应急救援力量部署 - LLM生成内容"""

    team_sources: list[str] = Field(
        description="建议调派的救援队伍来源，如：省消防救援总队、武警机动部队、蓝天救援队等",
        min_length=2,
        max_length=6,
    )
    deployment_phases: list[str] = Field(
        description="72小时内的分阶段部署建议，每条描述一个阶段",
        min_length=2,
        max_length=4,
    )
    priority_areas: list[str] = Field(
        description="重点救援区域，基于灾情严重程度排序",
        min_length=1,
        max_length=5,
    )
    coordination_suggestions: str = Field(
        description="多支队伍协调配合建议，100字以内",
        max_length=200,
    )
    special_equipment: list[str] = Field(
        description="建议携带的特殊装备，如：生命探测仪、破拆工具等",
        min_length=2,
        max_length=6,
    )


class MedicalModuleOutput(BaseModel):
    """模块2: 医疗救护部署 - LLM生成内容"""

    triage_plan: str = Field(
        description="伤员分诊方案建议（红黄绿分区）",
        max_length=300,
    )
    hospital_coordination: list[str] = Field(
        description="周边医院协调建议",
        min_length=1,
        max_length=4,
    )
    medical_supply_priorities: list[str] = Field(
        description="医疗物资优先配置建议",
        min_length=3,
        max_length=6,
    )
    field_hospital_location_criteria: list[str] = Field(
        description="野战医院/临时医疗点选址标准",
        min_length=2,
        max_length=4,
    )
    evacuation_routes: str = Field(
        description="伤员转运通道规划建议",
        max_length=200,
    )


class InfrastructureModuleOutput(BaseModel):
    """模块3: 基础设施抢修 - LLM生成内容"""

    repair_priorities: list[str] = Field(
        description="抢修优先级排序（生命线工程优先）",
        min_length=3,
        max_length=6,
    )
    temporary_solutions: list[str] = Field(
        description="临时通道/便桥搭建建议",
        min_length=1,
        max_length=4,
    )
    safety_inspection_plan: str = Field(
        description="危险建筑排查与安全评估计划",
        max_length=200,
    )
    equipment_deployment: list[str] = Field(
        description="大型机械设备部署建议",
        min_length=2,
        max_length=5,
    )
    power_restoration_plan: str = Field(
        description="电力恢复方案建议",
        max_length=200,
    )


class ShelterModuleOutput(BaseModel):
    """模块4: 临时安置与生活保障 - LLM生成内容"""

    site_selection_criteria: list[str] = Field(
        description="安置点选址标准（远离次生灾害风险区）",
        min_length=3,
        max_length=6,
    )
    special_groups_care: str = Field(
        description="特殊群体（老人、儿童、孕妇、残疾人）照护建议",
        max_length=300,
    )
    sanitation_facilities: list[str] = Field(
        description="卫生设施配置建议",
        min_length=2,
        max_length=5,
    )
    water_supply_plan: str = Field(
        description="饮用水供应方案",
        max_length=200,
    )
    food_distribution_plan: str = Field(
        description="食品发放方案",
        max_length=200,
    )
    expansion_considerations: str = Field(
        description="后续扩展安置的预案考虑",
        max_length=200,
    )


class CommunicationModuleOutput(BaseModel):
    """模块6: 通信与信息保障 - LLM生成内容"""

    network_restoration_plan: str = Field(
        description="应急通信网络恢复方案",
        max_length=300,
    )
    command_communication: list[str] = Field(
        description="指挥链路通信保障措施",
        min_length=2,
        max_length=4,
    )
    public_information: str = Field(
        description="信息发布与舆情监控建议",
        max_length=200,
    )
    redundancy_plan: str = Field(
        description="通信冗余和备份方案",
        max_length=200,
    )
    frequency_coordination: str = Field(
        description="频率协调与干扰规避建议",
        max_length=150,
    )


class LogisticsModuleOutput(BaseModel):
    """模块7: 物资调拨与运输保障 - LLM生成内容"""

    supply_sources: list[str] = Field(
        description="物资调拨来源（省级储备库、周边市县、社会捐赠）",
        min_length=2,
        max_length=5,
    )
    transport_routes: list[str] = Field(
        description="运输通道规划（主通道、备用通道）",
        min_length=2,
        max_length=4,
    )
    distribution_plan: str = Field(
        description="物资分发点布局与流程",
        max_length=300,
    )
    tracking_system: str = Field(
        description="物资追踪与管理建议",
        max_length=150,
    )
    alternative_routes: str = Field(
        description="道路中断情况下的替代方案",
        max_length=200,
    )


class SelfSupportModuleOutput(BaseModel):
    """模块8: 救援力量自身保障 - LLM生成内容"""

    camp_arrangement: str = Field(
        description="救援人员驻扎安排建议",
        max_length=200,
    )
    shift_rotation: str = Field(
        description="休息轮换制度建议",
        max_length=200,
    )
    health_monitoring: str = Field(
        description="救援人员健康监测建议",
        max_length=200,
    )
    safety_equipment: list[str] = Field(
        description="安全防护装备配置建议",
        min_length=3,
        max_length=6,
    )
    mental_health_support: str = Field(
        description="心理疏导与支持建议",
        max_length=150,
    )
