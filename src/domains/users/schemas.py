"""
用户管理数据模型（Pydantic Schemas）
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserType(str, Enum):
    """用户类型"""
    internal = "internal"
    external_team = "external_team"
    external_expert = "external_expert"
    external_volunteer = "external_volunteer"
    system = "system"


class UserStatus(str, Enum):
    """用户状态"""
    active = "active"
    inactive = "inactive"
    suspended = "suspended"


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=100, description="登录账号")
    password: str = Field(..., min_length=8, description="密码")
    real_name: str = Field(..., min_length=1, max_length=100, description="真实姓名")
    employee_id: Optional[str] = Field(None, max_length=50, description="工号")
    user_type: UserType = Field(UserType.internal, description="用户类型")
    org_id: Optional[UUID] = Field(None, description="所属组织ID")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    position: Optional[str] = Field(None, max_length=100, description="职务")
    rank: Optional[str] = Field(None, max_length=50, description="职级")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    certifications: list[str] = Field(default_factory=list, description="资质证书")
    specialties: list[str] = Field(default_factory=list, description="专长领域")
    can_operate_uav: bool = Field(False, description="无人机操作资质")
    can_operate_ugv: bool = Field(False, description="机器狗操作资质")
    can_operate_usv: bool = Field(False, description="无人艇操作资质")
    role_ids: list[UUID] = Field(default_factory=list, description="初始角色ID列表")


class UserUpdate(BaseModel):
    """更新用户请求"""
    real_name: Optional[str] = Field(None, min_length=1, max_length=100, description="真实姓名")
    employee_id: Optional[str] = Field(None, max_length=50, description="工号")
    org_id: Optional[UUID] = Field(None, description="所属组织ID")
    department: Optional[str] = Field(None, max_length=100, description="部门")
    position: Optional[str] = Field(None, max_length=100, description="职务")
    rank: Optional[str] = Field(None, max_length=50, description="职级")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    certifications: Optional[list[str]] = Field(None, description="资质证书")
    specialties: Optional[list[str]] = Field(None, description="专长领域")
    can_operate_uav: Optional[bool] = Field(None, description="无人机操作资质")
    can_operate_ugv: Optional[bool] = Field(None, description="机器狗操作资质")
    can_operate_usv: Optional[bool] = Field(None, description="无人艇操作资质")


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(..., min_length=8, description="新密码")


class OrganizationInfo(BaseModel):
    """组织信息（简化）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str
    short_name: Optional[str]


class RoleInfo(BaseModel):
    """角色信息（简化）"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    name: str


class UserResponse(BaseModel):
    """用户响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    username: str
    real_name: str
    employee_id: Optional[str]
    user_type: str
    org_id: Optional[UUID]
    organization: Optional[OrganizationInfo]
    department: Optional[str]
    position: Optional[str]
    rank: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    certifications: list[str]
    specialties: list[str]
    can_operate_uav: bool
    can_operate_ugv: bool
    can_operate_usv: bool
    status: str
    last_login_at: Optional[datetime]
    roles: list[RoleInfo]
    permissions: list[str]
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """用户列表响应"""
    items: list[UserResponse]
    total: int
    page: int
    page_size: int


class CurrentUserResponse(BaseModel):
    """当前用户响应"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    username: str
    real_name: str
    user_type: str
    organization: Optional[OrganizationInfo]
    department: Optional[str]
    position: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    roles: list[RoleInfo]
    permissions: list[str]
    last_login_at: Optional[datetime]
