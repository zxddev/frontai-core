"""CrewAI Task 定义：设备筛选和任务分配

两个任务：
1. 设备筛选任务：从全部设备中筛选出适合侦察的设备
2. 任务分配任务：为每个目标分配最合适的设备
"""
from typing import Literal

from crewai import Agent, Task
from pydantic import BaseModel, Field


class ReconDevice(BaseModel):
    """筛选后的侦察设备"""
    device_id: str = Field(description="设备ID")
    code: str = Field(description="设备编码")
    name: str = Field(description="设备名称")
    device_type: str = Field(description="设备类型：drone/dog/ship")
    env_type: str = Field(description="作业环境：air/land/sea")
    capabilities: list[str] = Field(default_factory=list, description="设备能力列表")
    applicable_disasters: list[str] = Field(default_factory=list, description="适用灾害类型")
    reason: str = Field(description="筛选理由")


class DeviceScreeningOutput(BaseModel):
    """设备筛选任务输出"""
    recon_devices: list[ReconDevice] = Field(description="适合侦察的设备列表")
    excluded_devices: list[dict] = Field(default_factory=list, description="被排除的设备及原因")
    summary: str = Field(description="筛选结果摘要")


class DeviceAssignmentItem(BaseModel):
    """单个设备分配结果"""
    device_id: str = Field(description="设备ID")
    device_name: str = Field(description="设备名称")
    device_type: str = Field(description="设备类型")
    target_id: str = Field(description="目标ID")
    target_name: str = Field(description="目标名称")
    priority: Literal["critical", "high", "medium", "low"] = Field(description="任务优先级")
    reason: str = Field(description="分配理由，说明为什么选择这台设备")


class DeviceAssignmentOutput(BaseModel):
    """设备分配任务输出"""
    assignments: list[DeviceAssignmentItem] = Field(description="设备分配列表")
    unassigned_targets: list[dict] = Field(default_factory=list, description="未分配设备的目标")
    explanation: str = Field(description="分配方案说明")


DEVICE_SCREENING_SCHEMA = """
{
    "recon_devices": [
        {
            "device_id": "设备UUID",
            "code": "设备编码，如 DV-DRONE-001",
            "name": "设备名称",
            "device_type": "drone | dog | ship",
            "env_type": "air | land | sea",
            "capabilities": ["aerial_recon", "3d_mapping"],
            "applicable_disasters": ["earthquake", "flood"],
            "reason": "筛选理由"
        }
    ],
    "excluded_devices": [
        {"device_id": "xxx", "name": "物资投送无人机", "reason": "具备cargo_delivery能力，非侦察用途"}
    ],
    "summary": "从N台设备中筛选出M台侦察设备"
}
"""

DEVICE_ASSIGNMENT_SCHEMA = """
{
    "assignments": [
        {
            "device_id": "设备UUID",
            "device_name": "设备名称",
            "device_type": "drone | dog | ship",
            "target_id": "目标UUID",
            "target_name": "目标名称",
            "priority": "critical | high | medium | low",
            "reason": "分配理由，说明为什么选择这台设备执行此任务"
        }
    ],
    "unassigned_targets": [
        {"target_id": "xxx", "target_name": "某目标", "reason": "无可用设备"}
    ],
    "explanation": "分配方案的整体说明"
}
"""


def create_device_screening_task(agent: Agent) -> Task:
    """创建设备筛选任务
    
    从全部无人设备中筛选出适合执行侦察任务的设备
    """
    return Task(
        description="""根据设备的基础能力（base_capabilities），筛选出适合执行侦察任务的无人设备。

## 输入数据
可用设备列表：
{devices_data}

## 筛选规则

### 侦察能力标签（具备以下任一能力的设备可用于侦察）
- aerial_recon: 空中侦察
- ground_recon: 地面侦察
- water_recon: 水面侦察
- 3d_mapping: 3D建模
- video_stream: 实时视频
- thermal_imaging: 热成像
- life_detection: 生命探测
- environment_analysis: 环境分析

### 非侦察能力标签（仅具备以下能力的设备不能用于侦察）
- cargo_delivery: 物资投送（送物资的，不是侦察的）
- cargo_transport: 货物运输
- medical_delivery: 医疗投送
- water_rescue: 水上救援（救人的，不是侦察的）
- search_rescue: 搜救
- communication_relay: 通讯组网

### 筛选逻辑
1. 如果设备有 base_capabilities：
   - 包含任一侦察能力标签 → 可用于侦察
   - 仅包含非侦察能力标签 → 排除
2. 如果设备没有 base_capabilities（为空或null）：
   - 根据设备名称判断：名称含"侦察/热成像/扫图/建模/分析"的可用
   - 名称含"投送/搜救/救援/组网/运输"的排除

## 输出要求
请严格按照以下JSON Schema输出：
""" + DEVICE_SCREENING_SCHEMA,
        expected_output="符合Schema的JSON对象，包含筛选后的侦察设备列表",
        agent=agent,
        output_pydantic=DeviceScreeningOutput,
    )


def create_device_assignment_task(agent: Agent, context_task: Task | None = None) -> Task:
    """创建设备分配任务
    
    为每个侦察目标匹配最合适的设备
    """
    return Task(
        description="""根据灾害类型和目标特征，为每个侦察目标分配最合适的无人设备。

## 输入数据
侦察目标列表（按优先级排序）：
{targets_data}

可用侦察设备：从上一个任务的筛选结果获取

当前灾害类型：{disaster_type}

## 分配规则

### 灾害类型与设备匹配
| 灾害/场景 | 首选设备类型 | 理由 |
|-----------|-------------|------|
| 滑坡(landslide) | drone, dog | 无人机航拍全貌，机器狗进入复杂地形 |
| 淹没(flooded) | drone, ship | 无人机空中观察，无人艇水面机动 |
| 地震高危区(seismic_red/orange) | drone, dog | 航拍危险建筑，机器狗废墟探测 |
| 化工厂/污染区(contaminated) | drone | 远程侦察避免人员暴露 |
| 阻断路段(blocked) | drone | 快速确认道路情况 |
| 建筑内部搜索 | dog | 可进入狭小空间 |
| 水库/河流 | drone, ship | 空中+水面侦察 |

### 设备能力与目标匹配
- thermal_imaging（热成像）：适合搜索被困人员
- 3d_mapping（3D建模）：适合评估建筑损坏
- life_detection（生命探测）：适合废墟搜救
- environment_analysis（环境分析）：适合污染区检测

### 分配优先级
1. critical 和 high 优先级目标优先分配设备
2. 每台设备只能分配给一个目标
3. 优先使用 applicable_disasters 匹配当前灾害类型的设备
4. 避免使用 forbidden_disasters 包含当前灾害类型的设备

## 输出要求
请严格按照以下JSON Schema输出：
""" + DEVICE_ASSIGNMENT_SCHEMA + """

## 注意事项
1. reason 字段要具体说明为什么这台设备适合这个目标
2. 如果可用设备不足，把未分配的目标放入 unassigned_targets
3. explanation 要给出整体分配方案的概述""",
        expected_output="符合Schema的JSON对象，包含设备分配方案",
        agent=agent,
        output_pydantic=DeviceAssignmentOutput,
        context=[context_task] if context_task else None,
    )
