"""
规则数据模型

定义TRR触发规则和硬约束规则的数据结构
使用Pydantic v2 + 强类型注解
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ConditionOperator(str, Enum):
    """条件操作符"""
    EQ = "eq"           # 等于
    NE = "ne"           # 不等于
    GT = "gt"           # 大于
    GTE = "gte"         # 大于等于
    LT = "lt"           # 小于
    LTE = "lte"         # 小于等于
    IN = "in"           # 包含于列表
    NOT_IN = "not_in"   # 不包含于列表
    CONTAINS = "contains"  # 包含（字符串或列表）
    REGEX = "regex"     # 正则匹配


class ConditionLogic(str, Enum):
    """条件组合逻辑"""
    AND = "AND"
    OR = "OR"


class RulePriority(str, Enum):
    """规则优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HardRuleAction(str, Enum):
    """硬规则执行动作"""
    REJECT = "reject"   # 否决方案
    WARN = "warn"       # 警告但不否决


class HardRuleSeverity(str, Enum):
    """硬规则严重程度"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"


class Condition(BaseModel):
    """单个触发条件"""
    field: str = Field(..., description="上下文字段名")
    operator: ConditionOperator = Field(..., description="比较操作符")
    value: Any = Field(..., description="比较值")


class TriggerConfig(BaseModel):
    """触发配置"""
    conditions: List[Condition] = Field(..., description="条件列表")
    logic: ConditionLogic = Field(default=ConditionLogic.AND, description="条件组合逻辑")


class CapabilityRequirement(BaseModel):
    """能力需求"""
    code: str = Field(..., description="能力代码")
    priority: RulePriority = Field(..., description="优先级")
    min_quantity: int = Field(default=1, description="最小数量")


class ActionConfig(BaseModel):
    """规则触发后的动作配置"""
    task_types: List[str] = Field(default_factory=list, description="任务类型列表")
    required_capabilities: List[CapabilityRequirement] = Field(
        default_factory=list, description="能力需求列表"
    )
    resource_types: List[str] = Field(default_factory=list, description="资源类型列表")
    grouping_pattern: Optional[str] = Field(default=None, description="编组模式描述")
    tactical_notes: Optional[str] = Field(default=None, description="战术注意事项")


class TRRRule(BaseModel):
    """TRR触发规则"""
    id: str = Field(..., description="规则ID，如TRR-EM-001")
    name: str = Field(..., description="规则名称")
    description: Optional[str] = Field(default=None, description="规则描述")
    trigger: TriggerConfig = Field(..., description="触发配置")
    actions: ActionConfig = Field(..., description="动作配置")
    priority: RulePriority = Field(default=RulePriority.MEDIUM, description="规则优先级")
    weight: float = Field(default=0.5, ge=0.0, le=1.0, description="规则权重")


class MatchedRule(BaseModel):
    """匹配的规则结果"""
    rule_id: str = Field(..., description="规则ID")
    rule_name: str = Field(..., description="规则名称")
    actions: ActionConfig = Field(..., description="触发的动作")
    priority: RulePriority = Field(..., description="优先级")
    weight: float = Field(..., description="权重")
    matched_conditions: List[str] = Field(default_factory=list, description="匹配的条件描述")


class HardRuleCheck(BaseModel):
    """硬规则检查配置"""
    field: str = Field(..., description="检查字段")
    operator: ConditionOperator = Field(..., description="比较操作符")
    threshold: Optional[Union[float, int, bool]] = Field(default=None, description="阈值")
    threshold_field: Optional[str] = Field(default=None, description="动态阈值字段名")


class HardRuleCondition(BaseModel):
    """硬规则前置条件（仅特定场景生效）"""
    field: str = Field(..., description="条件字段")
    operator: ConditionOperator = Field(..., description="操作符")
    value: Any = Field(..., description="条件值")


class HardRule(BaseModel):
    """硬约束规则"""
    id: str = Field(..., description="规则ID，如HR-EM-001")
    name: str = Field(..., description="规则名称")
    description: Optional[str] = Field(default=None, description="规则描述")
    check: HardRuleCheck = Field(..., description="检查配置")
    condition: Optional[HardRuleCondition] = Field(default=None, description="前置条件")
    action: HardRuleAction = Field(..., description="执行动作")
    message: str = Field(..., description="触发时的消息模板")
    severity: HardRuleSeverity = Field(default=HardRuleSeverity.HIGH, description="严重程度")


class HardRuleResult(BaseModel):
    """硬规则检查结果"""
    rule_id: str = Field(..., description="规则ID")
    rule_name: str = Field(..., description="规则名称")
    passed: bool = Field(..., description="是否通过")
    action: HardRuleAction = Field(..., description="执行动作")
    message: str = Field(..., description="结果消息")
    severity: HardRuleSeverity = Field(..., description="严重程度")
    checked_value: Optional[Any] = Field(default=None, description="检查的实际值")
    threshold_value: Optional[Any] = Field(default=None, description="阈值")


class RuleLibrary(BaseModel):
    """规则库"""
    version: str = Field(default="1.0", description="版本号")
    description: Optional[str] = Field(default=None, description="描述")
    rules: Dict[str, TRRRule] = Field(default_factory=dict, description="规则字典")


class HardRuleLibrary(BaseModel):
    """硬规则库"""
    version: str = Field(default="1.0", description="版本号")
    description: Optional[str] = Field(default=None, description="描述")
    rules: Dict[str, HardRule] = Field(default_factory=dict, description="规则字典")
