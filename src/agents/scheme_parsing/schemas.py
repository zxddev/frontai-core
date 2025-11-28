"""
方案解析数据模型

定义LLM输出的结构化Schema，使用Pydantic保证类型安全。
"""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ParsedTask(BaseModel):
    """解析出的单个任务"""
    
    task_name: str = Field(
        ..., 
        description="任务名称，如：生命探测、被困人员救援",
        examples=["生命探测", "被困人员救援", "伤员急救"],
    )
    task_type: str = Field(
        ..., 
        description="任务类型代码，如：EM06、EM10、EM14",
        examples=["EM06", "EM10", "EM14"],
    )
    priority: Literal["critical", "high", "medium", "low"] = Field(
        "medium",
        description="任务优先级：critical(紧急)/high(高)/medium(中)/low(低)",
    )
    assigned_team: str = Field(
        ..., 
        description="负责执行的队伍名称",
        examples=["XX重型救援队", "XX消防支队", "XX医疗队"],
    )
    duration_min: int = Field(
        60, 
        description="预计执行时长（分钟）",
        ge=5,
        le=720,
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="依赖的前置任务名称列表",
        examples=[["生命探测"], ["生命探测", "现场评估"]],
    )
    execution_notes: Optional[str] = Field(
        None,
        description="执行备注或特殊要求",
    )


class TeamAssignment(BaseModel):
    """队伍分配信息"""
    
    team_name: str = Field(
        ...,
        description="队伍名称",
        examples=["XX重型救援队", "XX消防支队"],
    )
    task_names: List[str] = Field(
        ...,
        description="该队伍负责的任务名称列表",
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="该队伍具备的能力（从方案文本中提取）",
        examples=[["生命探测", "重型破拆"], ["灭火", "人员搜救"]],
    )
    estimated_eta_min: Optional[int] = Field(
        None,
        description="预计到达时间（分钟），从方案文本中提取",
        ge=0,
    )
    distance_km: Optional[float] = Field(
        None,
        description="距离事发地距离（公里），从方案文本中提取",
        ge=0,
    )


class ParsedScheme(BaseModel):
    """解析后的方案结构"""
    
    tasks: List[ParsedTask] = Field(
        ...,
        description="解析出的任务列表，按执行顺序排列",
        min_length=1,
    )
    team_assignments: List[TeamAssignment] = Field(
        ...,
        description="队伍分配列表",
    )
    disaster_type: str = Field(
        "unknown",
        description="灾害类型：earthquake/fire/flood/hazmat/landslide/unknown",
    )
    disaster_severity: Literal["critical", "high", "medium", "low"] = Field(
        "medium",
        description="灾害严重程度",
    )
    estimated_trapped: int = Field(
        0,
        description="预估被困人数（从方案文本中提取）",
        ge=0,
    )
    parsing_confidence: float = Field(
        0.8,
        description="解析置信度（0-1），表示LLM对解析结果的确信程度",
        ge=0,
        le=1,
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="解析警告列表，如信息不完整、数据不一致等",
    )
    raw_summary: str = Field(
        "",
        description="原始方案的简要摘要（100字以内）",
        max_length=200,
    )
