"""
认证授权业务逻辑层
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.security import (
    verify_password, hash_password, check_password_strength,
    create_access_token, create_refresh_token, verify_refresh_token
)
from src.core.exceptions import (
    AuthenticationError, AuthorizationError, NotFoundError, ValidationError, ConflictError
)

from .repository import RoleRepository, PermissionRepository, UserRoleRepository
from .schemas import TokenResponse, RoleInfo, UserInfo
from src.domains.users.models import User
from src.domains.users.repository import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)
        self.perm_repo = PermissionRepository(session)
        self.user_role_repo = UserRoleRepository(session)
    
    async def login(self, username: str, password: str) -> TokenResponse:
        """
        用户登录
        
        Raises:
            AuthenticationError: AU4001 用户名或密码错误
            AuthorizationError: AU4002 用户已禁用
        """
        user = await self.user_repo.get_by_username(username)
        
        if not user:
            logger.warning(f"登录失败：用户不存在 {username}")
            raise AuthenticationError(code="AU4001", message="用户名或密码错误")
        
        if user.status != 'active':
            logger.warning(f"登录失败：用户已禁用 {username}")
            raise AuthorizationError(code="AU4002", message="用户已禁用")
        
        if not user.password_hash or not verify_password(password, user.password_hash):
            logger.warning(f"登录失败：密码错误 {username}")
            raise AuthenticationError(code="AU4001", message="用户名或密码错误")
        
        # 获取用户角色和权限
        roles = await self.role_repo.get_user_roles(user.id)
        role_codes = [r.code for r in roles]
        permissions = await self.perm_repo.get_user_permissions(user.id)
        
        # 生成Token
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=role_codes,
            permissions=permissions,
        )
        refresh_token = create_refresh_token(user_id=user.id)
        
        # 更新最后登录时间
        await self.user_repo.update_last_login(user.id)
        await self.session.commit()
        
        # 构造响应
        role_infos = [RoleInfo(id=r.id, code=r.code, name=r.name) for r in roles]
        user_info = UserInfo(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            roles=role_infos,
            permissions=permissions,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_expire_minutes * 60,
            user=user_info,
        )
    
    async def refresh_token(self, refresh_token: str) -> dict:
        """
        刷新Token
        
        Raises:
            AuthenticationError: Token无效或已过期
        """
        user_id_str = verify_refresh_token(refresh_token)
        if not user_id_str:
            raise AuthenticationError(code="AU4001", message="Token无效或已过期")
        
        user_id = UUID(user_id_str)
        user = await self.user_repo.get_by_id(user_id)
        
        if not user or user.status != 'active':
            raise AuthenticationError(code="AU4001", message="Token无效或用户已禁用")
        
        # 获取最新角色和权限
        roles = await self.role_repo.get_user_roles(user.id)
        role_codes = [r.code for r in roles]
        permissions = await self.perm_repo.get_user_permissions(user.id)
        
        # 生成新的Access Token
        access_token = create_access_token(
            user_id=user.id,
            username=user.username,
            roles=role_codes,
            permissions=permissions,
        )
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_expire_minutes * 60,
        }
    
    async def get_user_info(self, user_id: UUID) -> UserInfo:
        """获取用户信息"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        roles = await self.role_repo.get_user_roles(user.id)
        permissions = await self.perm_repo.get_user_permissions(user.id)
        
        role_infos = [RoleInfo(id=r.id, code=r.code, name=r.name) for r in roles]
        
        return UserInfo(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            roles=role_infos,
            permissions=permissions,
        )
    
    async def assign_role(
        self,
        user_id: UUID,
        role_id: UUID,
        scope_type: str = "global",
        scope_id: Optional[UUID] = None,
        granted_by: Optional[UUID] = None,
    ) -> None:
        """为用户分配角色"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundError(message="角色不存在")
        
        await self.user_role_repo.assign_role(
            user_id=user_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
            granted_by=granted_by,
        )
        await self.session.commit()
    
    async def revoke_role(self, user_id: UUID, role_id: UUID) -> None:
        """撤销用户角色"""
        success = await self.user_role_repo.revoke_role(user_id, role_id)
        if not success:
            raise NotFoundError(message="用户角色关联不存在")
        await self.session.commit()


class PermissionService:
    """权限检查服务"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.perm_repo = PermissionRepository(session)
    
    async def check_permission(
        self,
        user_id: UUID,
        required_permission: str,
    ) -> bool:
        """
        检查用户是否拥有指定权限
        
        Args:
            user_id: 用户ID
            required_permission: 权限编码
        
        Returns:
            True if has permission
        """
        permissions = await self.perm_repo.get_user_permissions(user_id)
        
        # 支持通配符匹配 task:* -> task:create, task:edit...
        for perm in permissions:
            if perm == required_permission:
                return True
            if perm.endswith(':*'):
                prefix = perm[:-1]  # "task:*" -> "task:"
                if required_permission.startswith(prefix):
                    return True
        
        return False
    
    async def check_permissions(
        self,
        user_id: UUID,
        required_permissions: list[str],
        require_all: bool = True,
    ) -> bool:
        """
        检查用户是否拥有多个权限
        
        Args:
            user_id: 用户ID
            required_permissions: 权限编码列表
            require_all: True=需要全部权限, False=只需任一权限
        """
        if not required_permissions:
            return True
        
        results = []
        for perm in required_permissions:
            results.append(await self.check_permission(user_id, perm))
        
        if require_all:
            return all(results)
        return any(results)
