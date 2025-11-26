"""
用户管理ORM模型

对应SQL表:
- operational_v2.users_v2
- operational_v2.organizations_v2
- operational_v2.operation_logs_v2

参考: sql/v2_user_permission_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ENUM

from src.core.database import Base


# 用户类型枚举
UserTypeEnum = ENUM(
    'internal', 'external_team', 'external_expert', 'external_volunteer', 'system',
    name='user_type_v2',
    schema='operational_v2',
    create_type=False,
)


class Organization(Base):
    """
    组织机构表 ORM 模型
    
    支持多级组织架构
    """
    __tablename__ = "organizations_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    code: str = Column(String(50), unique=True, nullable=False, comment="机构编码")
    name: str = Column(String(200), nullable=False, comment="机构名称")
    short_name: Optional[str] = Column(String(50), comment="简称")
    
    # 层级关系
    parent_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.organizations_v2.id"),
        comment="上级机构ID"
    )
    org_level: int = Column(Integer, default=1, comment="层级：1省/2市/3区县/4乡镇/5村")
    org_path: Optional[str] = Column(String(500), comment="路径：/省/市/区县/")
    
    # 机构类型
    org_type: str = Column(String(50), nullable=False, comment="类型: government/military/fire/medical/volunteer/enterprise")
    
    # 联系信息
    contact_person: Optional[str] = Column(String(100), comment="联系人")
    contact_phone: Optional[str] = Column(String(20), comment="联系电话")
    address: Optional[str] = Column(String(300), comment="地址")
    
    status: str = Column(String(20), default='active', comment="状态: active/inactive")
    properties: dict[str, Any] = Column(JSONB, default={})
    
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    """
    用户表 ORM 模型
    """
    __tablename__ = "users_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # 账户信息
    username: str = Column(String(100), unique=True, nullable=False, comment="登录账号")
    password_hash: Optional[str] = Column(String(255), comment="密码哈希")
    
    # 基本信息
    real_name: str = Column(String(100), nullable=False, comment="真实姓名")
    employee_id: Optional[str] = Column(String(50), comment="工号/编号")
    user_type: str = Column(UserTypeEnum, default='internal', comment="用户类型")
    
    # 所属组织
    org_id: Optional[UUID] = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.organizations_v2.id"),
        comment="所属组织ID"
    )
    department: Optional[str] = Column(String(100), comment="部门")
    position: Optional[str] = Column(String(100), comment="职务")
    rank: Optional[str] = Column(String(50), comment="职级/军衔")
    
    # 联系方式
    phone: Optional[str] = Column(String(20), comment="手机号")
    email: Optional[str] = Column(String(100), comment="邮箱")
    
    # 专业资质
    certifications: list[str] = Column(ARRAY(Text), default=[], comment="资质证书列表")
    specialties: list[str] = Column(ARRAY(Text), default=[], comment="专长领域")
    
    # 设备操作资质
    can_operate_uav: bool = Column(Boolean, default=False, comment="无人机操作资质")
    can_operate_ugv: bool = Column(Boolean, default=False, comment="机器狗操作资质")
    can_operate_usv: bool = Column(Boolean, default=False, comment="无人艇操作资质")
    
    # 状态
    status: str = Column(String(20), default='active', comment="状态: active/inactive/suspended")
    last_login_at: Optional[datetime] = Column(DateTime(timezone=True), comment="最后登录时间")
    
    properties: dict[str, Any] = Column(JSONB, default={})
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class OperationLog(Base):
    """
    操作日志表 ORM 模型
    """
    __tablename__ = "operation_logs_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # 操作人
    user_id: Optional[UUID] = Column(PG_UUID(as_uuid=True), comment="操作人ID")
    username: Optional[str] = Column(String(100), comment="操作人用户名")
    user_ip: Optional[str] = Column(String(50), comment="操作人IP")
    
    # 操作信息
    module: str = Column(String(50), nullable=False, comment="模块")
    action: str = Column(String(50), nullable=False, comment="操作")
    resource_type: Optional[str] = Column(String(50), comment="资源类型")
    resource_id: Optional[UUID] = Column(PG_UUID(as_uuid=True), comment="资源ID")
    
    # 操作详情
    description: Optional[str] = Column(Text, comment="操作描述")
    request_data: Optional[dict[str, Any]] = Column(JSONB, comment="请求数据")
    response_data: Optional[dict[str, Any]] = Column(JSONB, comment="响应数据")
    
    # 结果
    status: str = Column(String(20), default='success', comment="状态: success/failed")
    error_message: Optional[str] = Column(Text, comment="错误信息")
    
    # 关联想定
    scenario_id: Optional[UUID] = Column(PG_UUID(as_uuid=True), comment="想定ID")
    
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
