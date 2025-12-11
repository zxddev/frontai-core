"""
认证授权数据模型（Pydantic Schemas）
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=100, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class PhoneLoginRequest(BaseModel):
    """手机号验证码登录请求（外部救援队伍）"""
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$", description="手机号")
    code: str = Field(..., min_length=4, max_length=6, description="验证码")


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field("Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: "UserInfo" = Field(..., description="用户信息")


class RefreshRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str = Field(..., description="刷新令牌")


class RefreshResponse(BaseModel):
    """刷新Token响应"""
    access_token: str = Field(..., description="新的访问令牌")
    token_type: str = Field("Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class RoleInfo(BaseModel):
    """角色信息"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str


class UserInfo(BaseModel):
    """用户信息（Token中携带）"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    real_name: str
    phone: Optional[str] = None
    user_type: Optional[str] = None
    roles: list[RoleInfo]
    permissions: list[str]
    # 所属队伍信息（通过手机号匹配team_members_v2.contact_phone）
    team_id: Optional[UUID] = Field(None, description="所属队伍ID")
    team_name: Optional[str] = Field(None, description="所属队伍名称")
    team_position: Optional[str] = Field(None, description="在队伍中的职位（如队长/副队长/队员）")


class RoleCategory(str, Enum):
    """角色分类"""
    command = "command"
    operation = "operation"
    support = "support"
    external = "external"


class RoleResponse(BaseModel):
    """角色响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    description: Optional[str]
    role_category: str
    role_level: int
    is_system: bool
    status: str
    created_at: datetime


class RoleListResponse(BaseModel):
    """角色列表响应"""
    items: list[RoleResponse]
    total: int


class PermissionResponse(BaseModel):
    """权限响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    description: Optional[str]
    module: str
    action: str
    resource_type: Optional[str]


class PermissionListResponse(BaseModel):
    """权限列表响应"""
    items: list[PermissionResponse]
    total: int


class AssignRoleRequest(BaseModel):
    """分配角色请求"""
    user_id: UUID = Field(..., description="用户ID")
    role_id: UUID = Field(..., description="角色ID")
    scope_type: str = Field("global", description="范围类型: global/scenario")
    scope_id: Optional[UUID] = Field(None, description="范围ID")
    valid_until: Optional[datetime] = Field(None, description="过期时间")
