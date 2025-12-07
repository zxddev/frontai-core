from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OperatorInfo(BaseModel):
    operator_id: str = Field(..., description="操作员ID")
    operator_name: str = Field(..., description="操作员名称")
    operator_role: str = Field(..., description="角色: commander/deputy/operator")
    auth_method: str = Field(..., description="确认方式: long_press_5s/password/dual_confirm")


class ActionInfo(BaseModel):
    action_type: str = Field(..., description="动作类型，如 deploy_team/start_mission")
    target_resource: Dict[str, Any] = Field(..., description="被操作资源")
    target_event: Optional[Dict[str, Any]] = Field(default=None, description="关联事件/任务")


class OutcomeInfo(BaseModel):
    result: str = Field(..., description="success/failure/partial")
    casualties: int = Field(default=0, description="伤亡人数")
    notes: str = Field(default="", description="备注")
    evidence: Optional[List[str]] = Field(default=None, description="证据附件URL")


class BreakGlassOverride(BaseModel):
    id: UUID
    timestamp: datetime
    operator_id: str
    operator_name: str
    operator_role: str
    auth_method: str
    rule_id: str
    rule_name: str
    risk_overridden: str
    action_type: str
    target_resource: Dict[str, Any]
    target_event: Optional[Dict[str, Any]] = None
    ai_recommendation: Optional[Dict[str, Any]] = None
    was_adopted: bool = False
    context: Dict[str, Any]
    outcome: Optional[Dict[str, Any]] = None
    outcome_recorded_at: Optional[datetime] = None
    created_at: datetime


class BreakGlassOverrideCreate(BaseModel):
    operator: OperatorInfo
    rule_id: str
    rule_name: str
    risk_overridden: str
    action: ActionInfo
    ai_recommendation: Optional[Dict[str, Any]] = None
    was_adopted: bool = False
    context: Dict[str, Any]


class BreakGlassOverrideResponse(BaseModel):
    id: UUID
    timestamp: datetime
    operator_id: str
    operator_name: str
    operator_role: str
    rule_id: str
    rule_name: str
    risk_overridden: str
    action_type: str
    target_resource: Dict[str, Any]
    target_event: Optional[Dict[str, Any]] = None
    ai_recommendation: Optional[Dict[str, Any]] = None
    was_adopted: bool = False
    context: Dict[str, Any]
    outcome: Optional[Dict[str, Any]] = None
    outcome_recorded_at: Optional[datetime] = None
    created_at: datetime
