"""
第三方接入数据模型

ORM模型定义
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    ARRAY, Index
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped

from src.core.database import Base


class ApiKey(Base):
    """API密钥模型"""
    
    __tablename__ = "api_keys_v2"
    
    id: Mapped[UUID] = Column(PG_UUID(as_uuid=True), primary_key=True)
    
    # 密钥信息
    key_hash: Mapped[str] = Column(String(255), nullable=False, comment="API密钥SHA256哈希")
    key_prefix: Mapped[str] = Column(String(8), nullable=False, unique=True, comment="密钥前缀")
    name: Mapped[str] = Column(String(200), nullable=False, comment="密钥名称")
    
    # 来源系统标识
    source_system: Mapped[str] = Column(String(100), nullable=False, unique=True, comment="来源系统标识")
    
    # 权限范围
    scopes: Mapped[list[str]] = Column(
        ARRAY(String(50)), 
        default=['disaster-report', 'sensor-alert', 'telemetry', 'weather'],
        comment="允许的接口范围"
    )
    
    # 状态
    status: Mapped[str] = Column(String(20), nullable=False, default='active', comment="状态")
    
    # 有效期
    expires_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), comment="过期时间")
    
    # 限制
    rate_limit_per_minute: Mapped[int] = Column(Integer, default=100, comment="每分钟请求限制")
    allowed_ips: Mapped[Optional[list[str]]] = Column(ARRAY(Text), comment="IP白名单")
    
    # 扩展信息
    extra_data: Mapped[dict] = Column(JSONB, default={}, comment="扩展信息")
    
    # 审计信息
    created_by: Mapped[Optional[UUID]] = Column(PG_UUID(as_uuid=True), comment="创建人")
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, comment="创建时间")
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, comment="更新时间")
    last_used_at: Mapped[Optional[datetime]] = Column(DateTime(timezone=True), comment="最后使用时间")
    
    __table_args__ = (
        Index('idx_api_keys_v2_key_prefix', 'key_prefix'),
        Index('idx_api_keys_v2_source_system', 'source_system'),
        Index('idx_api_keys_v2_status', 'status'),
    )
    
    def is_valid(self) -> bool:
        """检查密钥是否有效"""
        if self.status != 'active':
            return False
        if self.expires_at and self.expires_at < datetime.now(self.expires_at.tzinfo):
            return False
        return True
    
    def has_scope(self, scope: str) -> bool:
        """检查是否有指定权限范围"""
        return scope in (self.scopes or [])
