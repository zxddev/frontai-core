"""
认证授权ORM模型

对应SQL表:
- operational_v2.roles_v2
- operational_v2.permissions_v2
- operational_v2.role_permissions_v2
- operational_v2.user_roles_v2

参考: sql/v2_user_permission_model.sql
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
import uuid as uuid_lib

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from src.core.database import Base


class Role(Base):
    """
    角色表 ORM 模型
    """
    __tablename__ = "roles_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    code: str = Column(String(50), unique=True, nullable=False, comment="角色编码")
    name: str = Column(String(100), nullable=False, comment="角色名称")
    description: Optional[str] = Column(Text, comment="角色描述")
    
    # 角色分类
    role_category: str = Column(String(50), nullable=False, comment="分类: command/operation/support/external")
    role_level: int = Column(Integer, default=5, comment="角色等级1-10，1最高")
    
    is_system: bool = Column(Boolean, default=False, comment="是否系统内置角色")
    status: str = Column(String(20), default='active', comment="状态")
    
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Permission(Base):
    """
    权限表 ORM 模型
    """
    __tablename__ = "permissions_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    code: str = Column(String(100), unique=True, nullable=False, comment="权限编码")
    name: str = Column(String(100), nullable=False, comment="权限名称")
    description: Optional[str] = Column(Text, comment="权限描述")
    
    # 权限分类
    module: str = Column(String(50), nullable=False, comment="所属模块")
    action: str = Column(String(50), nullable=False, comment="操作类型: view/create/edit/delete/execute/approve")
    resource_type: Optional[str] = Column(String(50), comment="资源类型")
    
    need_data_scope: bool = Column(Boolean, default=False, comment="是否需要数据权限控制")
    
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)


class RolePermission(Base):
    """
    角色-权限关联表 ORM 模型
    """
    __tablename__ = "role_permissions_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    role_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.roles_v2.id", ondelete="CASCADE"),
        nullable=False
    )
    permission_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.permissions_v2.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # 数据范围
    data_scope: str = Column(String(50), default='all', comment="数据范围: all/org/self")
    
    created_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)


class UserRole(Base):
    """
    用户-角色关联表 ORM 模型
    """
    __tablename__ = "user_roles_v2"
    __table_args__ = {"schema": "operational_v2"}
    
    id: UUID = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    user_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.users_v2.id", ondelete="CASCADE"),
        nullable=False
    )
    role_id: UUID = Column(
        PG_UUID(as_uuid=True), 
        ForeignKey("operational_v2.roles_v2.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # 角色生效范围
    scope_type: str = Column(String(50), default='global', comment="范围类型: global/scenario")
    scope_id: Optional[UUID] = Column(PG_UUID(as_uuid=True), comment="范围ID")
    
    # 有效期（临时授权）
    valid_from: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
    valid_until: Optional[datetime] = Column(DateTime(timezone=True), comment="过期时间")
    
    # 授权信息
    granted_by: Optional[UUID] = Column(PG_UUID(as_uuid=True), comment="授权人ID")
    granted_at: datetime = Column(DateTime(timezone=True), default=datetime.utcnow)
