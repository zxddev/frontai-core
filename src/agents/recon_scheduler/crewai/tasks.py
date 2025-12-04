"""CrewAI Task定义 - 灾情分析和计划呈报

两个核心任务：
1. 灾情分析任务：从自然语言提取结构化灾情信息
2. 计划呈报任务：生成指挥员级别的侦察计划报告
"""
from typing import List, Literal, Optional

from crewai import Agent, Task
from pydantic import BaseModel, Field


# ============================================================================
# 灾情分析输出模型
# ============================================================================

class PriorityTargetItem(BaseModel):
    """优先侦察目标"""
    target_type: str = Field(description="目标类型：building_collapse/trapped_persons/fire_point/flood_area等")
    description: str = Field(description="目标描述")
    priority: Literal["critical", "high", "medium", "low"] = Field(description="优先级")
    estimated_location: Optional[str] = Field(default=None, description="估计位置描述")
    urgency_reason: str = Field(description="紧急原因")


class SecondaryRiskItem(BaseModel):
    """次生灾害风险"""
    risk_type: str = Field(description="风险类型：aftershock/fire/explosion/flood/landslide等")
    probability: Literal["high", "medium", "low"] = Field(description="发生概率")
    description: str = Field(description="风险描述")


class DisasterAnalysisOutput(BaseModel):
    """灾情分析任务输出"""
    disaster_type: Literal[
        "earthquake_collapse", "flood", "fire", "hazmat", "landslide", "other"
    ] = Field(description="灾害类型")
    disaster_subtype: Optional[str] = Field(default=None, description="灾害子类型，如地震的震级")
    severity: Literal["critical", "high", "medium", "low"] = Field(description="严重程度")
    
    location_description: str = Field(description="位置描述")
    affected_area_estimate: Optional[str] = Field(default=None, description="影响范围估计")
    
    priority_targets: List[PriorityTargetItem] = Field(
        default_factory=list, description="优先侦察目标列表"
    )
    secondary_risks: List[SecondaryRiskItem] = Field(
        default_factory=list, description="次生灾害风险列表"
    )
    
    golden_hour_status: str = Field(description="黄金救援时间状态评估")
    time_since_onset_estimate: Optional[str] = Field(default=None, description="灾害发生时间估计")
    
    key_constraints: List[str] = Field(
        default_factory=list, description="关键约束条件（天气、地形、禁飞区等）"
    )
    
    recommended_device_types: List[str] = Field(
        default_factory=list, description="推荐的设备类型"
    )
    
    analysis_summary: str = Field(description="分析摘要（100字内）")


# ============================================================================
# 计划呈报输出模型
# ============================================================================

class MilestoneItem(BaseModel):
    """任务里程碑"""
    time_offset: str = Field(description="时间偏移，如T+30min")
    event: str = Field(description="里程碑事件")
    significance: str = Field(description="重要性说明")


class RiskWarningItem(BaseModel):
    """风险警示"""
    risk: str = Field(description="风险描述")
    mitigation: str = Field(description="应对措施")
    attention_level: Literal["critical", "high", "medium"] = Field(description="关注级别")


class ForceDeploymentItem(BaseModel):
    """兵力部署"""
    wave: int = Field(description="波次")
    device_name: str = Field(description="设备名称")
    mission: str = Field(description="任务")
    altitude_or_area: str = Field(description="作业高度或区域")


class PlanPresentationOutput(BaseModel):
    """计划呈报任务输出"""
    executive_summary: str = Field(description="指挥员摘要（100字内，一句话概括任务）")
    
    mission_overview: str = Field(description="任务概述")
    
    force_deployment: List[ForceDeploymentItem] = Field(
        default_factory=list, description="兵力部署（按波次）"
    )
    
    key_milestones: List[MilestoneItem] = Field(
        default_factory=list, description="关键时间节点"
    )
    
    risk_warnings: List[RiskWarningItem] = Field(
        default_factory=list, description="风险警示"
    )
    
    coordination_notes: str = Field(description="协同说明")
    
    commander_decisions_needed: List[str] = Field(
        default_factory=list, description="需要指挥员决策的事项"
    )
    
    full_briefing: str = Field(description="完整简报文本（军事简报格式）")


# ============================================================================
# JSON Schema（用于Task描述）
# ============================================================================

DISASTER_ANALYSIS_SCHEMA = """
{
    "disaster_type": "earthquake_collapse | flood | fire | hazmat | landslide | other",
    "disaster_subtype": "可选，如震级6.5级",
    "severity": "critical | high | medium | low",
    "location_description": "位置描述",
    "affected_area_estimate": "影响范围估计",
    "priority_targets": [
        {
            "target_type": "building_collapse | trapped_persons | fire_point | flood_area",
            "description": "目标描述",
            "priority": "critical | high | medium | low",
            "estimated_location": "位置",
            "urgency_reason": "紧急原因"
        }
    ],
    "secondary_risks": [
        {
            "risk_type": "aftershock | fire | explosion | flood",
            "probability": "high | medium | low",
            "description": "风险描述"
        }
    ],
    "golden_hour_status": "黄金救援时间状态",
    "key_constraints": ["约束1", "约束2"],
    "recommended_device_types": ["drone", "dog"],
    "analysis_summary": "分析摘要（100字内）"
}
"""

PLAN_PRESENTATION_SCHEMA = """
{
    "executive_summary": "指挥员摘要（100字内）",
    "mission_overview": "任务概述",
    "force_deployment": [
        {
            "wave": 1,
            "device_name": "经纬M300无人机",
            "mission": "高空正射建图",
            "altitude_or_area": "150m"
        }
    ],
    "key_milestones": [
        {
            "time_offset": "T+30min",
            "event": "完成首轮态势评估",
            "significance": "为救援决策提供依据"
        }
    ],
    "risk_warnings": [
        {
            "risk": "余震风险",
            "mitigation": "保持200m以上飞行高度",
            "attention_level": "high"
        }
    ],
    "coordination_notes": "协同说明",
    "commander_decisions_needed": ["需要决策的事项"],
    "full_briefing": "完整军事简报文本"
}
"""


# ============================================================================
# Task创建函数
# ============================================================================

def create_disaster_analysis_task(agent: Agent) -> Task:
    """创建灾情分析任务
    
    从自然语言描述中提取结构化灾情信息
    """
    return Task(
        description="""根据用户输入的灾情描述，提取关键信息用于侦察规划。

## 输入数据
用户描述：
{recon_request}

目标区域信息（如有）：
{target_area_info}

## 分析要求

### 1. 灾害类型识别
- earthquake_collapse: 地震建筑倒塌
- flood: 洪涝灾害
- fire: 火灾
- hazmat: 危化品泄漏
- landslide: 山体滑坡
- other: 其他

### 2. 严重程度评估
- critical: 大量人员被困，需立即救援
- high: 有人员伤亡风险，需紧急响应
- medium: 有财产损失，需要评估
- low: 预防性侦察

### 3. 优先目标识别
从描述中提取需要优先侦察的目标：
- 人员密集区（学校、医院、居民楼）
- 建筑倒塌点
- 被困人员报告位置
- 火势蔓延方向
- 洪水淹没区域

### 4. 次生灾害预判
根据主灾害类型预判：
- 地震 → 余震、火灾、山体滑坡
- 洪涝 → 山体滑坡、疫病
- 火灾 → 爆炸、有毒烟雾
- 危化品 → 爆炸、污染扩散

### 5. 设备推荐
根据灾害类型推荐：
- 地震: drone（航拍）+ dog（废墟探测）
- 洪涝: drone（航拍）+ ship（水面侦察）
- 火灾: drone（热成像，上风向接近）
- 危化品: drone（远程侦察，避免人员暴露）

## 输出要求
请严格按照以下JSON Schema输出：
""" + DISASTER_ANALYSIS_SCHEMA,
        expected_output="符合Schema的JSON对象，包含结构化的灾情分析结果",
        agent=agent,
        output_pydantic=DisasterAnalysisOutput,
    )


def create_plan_presentation_task(agent: Agent, context_task: Task | None = None) -> Task:
    """创建计划呈报任务
    
    将技术性侦察计划转化为指挥员级别的报告
    """
    return Task(
        description="""将侦察计划转化为指挥员可理解的行动方案简报。

## 输入数据
侦察计划数据：
{recon_plan_data}

灾情类型：{disaster_type}
总时长：{total_duration_min} 分钟
航线数量：{flight_count} 条
风险等级：{risk_level}

## 呈报要求

### 1. 指挥员摘要（100字内）
一句话概括：做什么、多少资源、多长时间、预期成果

### 2. 任务概述
简要说明任务背景和目标

### 3. 兵力部署（按波次）
说明各波次侦察的设备、任务、作业参数

### 4. 关键时间节点
列出重要里程碑和对应意义

### 5. 风险警示
列出需要指挥员关注的风险及应对措施

### 6. 协同说明
说明各侦察单元之间的配合关系

### 7. 需要决策的事项
列出需要指挥员批准或决策的事项

### 8. 完整简报
按军事简报格式输出：
```
【侦察任务简报】

一、任务概述
...

二、兵力部署
第一波次：...
第二波次：...

三、关键时间节点
- T+30min：...
- T+180min：...

四、风险提示
- ...

五、协同要求
...

六、建议
...
```

## 输出要求
请严格按照以下JSON Schema输出：
""" + PLAN_PRESENTATION_SCHEMA,
        expected_output="符合Schema的JSON对象，包含完整的指挥员简报",
        agent=agent,
        output_pydantic=PlanPresentationOutput,
        context=[context_task] if context_task else None,
    )
