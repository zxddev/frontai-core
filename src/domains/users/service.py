"""
用户管理业务逻辑层
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password, verify_password, check_password_strength
from src.core.exceptions import NotFoundError, ValidationError, ConflictError

from .models import User, Organization, OperationLog
from .repository import UserRepository, OrganizationRepository, OperationLogRepository
from .schemas import UserCreate, UserUpdate, UserResponse, UserListResponse, CurrentUserResponse
from src.domains.auth.repository import RoleRepository, UserRoleRepository, PermissionRepository
from src.domains.auth.schemas import RoleInfo

logger = logging.getLogger(__name__)


class UserService:
    """用户服务"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.org_repo = OrganizationRepository(session)
        self.role_repo = RoleRepository(session)
        self.user_role_repo = UserRoleRepository(session)
        self.perm_repo = PermissionRepository(session)
        self.log_repo = OperationLogRepository(session)
    
    async def create_user(
        self,
        data: UserCreate,
        created_by: Optional[UUID] = None,
    ) -> UserResponse:
        """
        创建用户
        
        Raises:
            ConflictError: AU4004 用户名已存在
            ValidationError: AU4005 密码强度不足
        """
        # 检查用户名唯一性
        if await self.user_repo.exists_username(data.username):
            raise ConflictError(code="AU4004", message="用户名已存在")
        
        # 检查密码强度
        if not check_password_strength(data.password):
            raise ValidationError(code="AU4005", message="密码强度不足：需要8位以上，包含字母和数字")
        
        # 创建用户
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            real_name=data.real_name,
            employee_id=data.employee_id,
            user_type=data.user_type.value,
            org_id=data.org_id,
            department=data.department,
            position=data.position,
            rank=data.rank,
            phone=data.phone,
            email=data.email,
            certifications=data.certifications,
            specialties=data.specialties,
            can_operate_uav=data.can_operate_uav,
            can_operate_ugv=data.can_operate_ugv,
            can_operate_usv=data.can_operate_usv,
        )
        user = await self.user_repo.create(user)
        
        # 分配初始角色
        for role_id in data.role_ids:
            await self.user_role_repo.assign_role(
                user_id=user.id,
                role_id=role_id,
                granted_by=created_by,
            )
        
        await self.session.commit()
        
        # 记录操作日志
        await self._log_operation(
            user_id=created_by,
            module='users',
            action='create',
            resource_type='user',
            resource_id=user.id,
            description=f"创建用户: {user.username}",
        )
        
        return await self._build_user_response(user)
    
    async def get_user(self, user_id: UUID) -> UserResponse:
        """获取用户详情"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        return await self._build_user_response(user)
    
    async def get_current_user(self, user_id: UUID) -> CurrentUserResponse:
        """获取当前登录用户信息"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        org = None
        if user.org_id:
            org = await self.org_repo.get_by_id(user.org_id)
        
        roles = await self.role_repo.get_user_roles(user.id)
        permissions = await self.perm_repo.get_user_permissions(user.id)
        
        from .schemas import OrganizationInfo, RoleInfo
        
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            user_type=user.user_type,
            organization=OrganizationInfo(
                id=org.id, code=org.code, name=org.name, short_name=org.short_name
            ) if org else None,
            department=user.department,
            position=user.position,
            phone=user.phone,
            email=user.email,
            roles=[RoleInfo(id=r.id, code=r.code, name=r.name) for r in roles],
            permissions=permissions,
            last_login_at=user.last_login_at,
        )
    
    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        org_id: Optional[UUID] = None,
        user_type: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> UserListResponse:
        """获取用户列表"""
        users, total = await self.user_repo.list_users(
            page=page,
            page_size=page_size,
            org_id=org_id,
            user_type=user_type,
            status=status,
            keyword=keyword,
        )
        
        items = []
        for user in users:
            items.append(await self._build_user_response(user))
        
        return UserListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def update_user(
        self,
        user_id: UUID,
        data: UserUpdate,
        updated_by: Optional[UUID] = None,
    ) -> UserResponse:
        """更新用户"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        # 更新非空字段
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(user, field, value)
        
        user = await self.user_repo.update(user)
        await self.session.commit()
        
        await self._log_operation(
            user_id=updated_by,
            module='users',
            action='update',
            resource_type='user',
            resource_id=user.id,
            description=f"更新用户: {user.username}",
        )
        
        return await self._build_user_response(user)
    
    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改密码
        
        Raises:
            ValidationError: 旧密码错误或新密码强度不足
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        if not user.password_hash or not verify_password(old_password, user.password_hash):
            raise ValidationError(message="旧密码错误")
        
        if not check_password_strength(new_password):
            raise ValidationError(code="AU4005", message="密码强度不足：需要8位以上，包含字母和数字")
        
        user.password_hash = hash_password(new_password)
        await self.user_repo.update(user)
        await self.session.commit()
        
        await self._log_operation(
            user_id=user_id,
            module='users',
            action='change_password',
            resource_type='user',
            resource_id=user.id,
            description=f"修改密码: {user.username}",
        )
    
    async def disable_user(
        self,
        user_id: UUID,
        disabled_by: Optional[UUID] = None,
    ) -> UserResponse:
        """禁用用户"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        user.status = 'inactive'
        user = await self.user_repo.update(user)
        await self.session.commit()
        
        await self._log_operation(
            user_id=disabled_by,
            module='users',
            action='disable',
            resource_type='user',
            resource_id=user.id,
            description=f"禁用用户: {user.username}",
        )
        
        return await self._build_user_response(user)
    
    async def enable_user(
        self,
        user_id: UUID,
        enabled_by: Optional[UUID] = None,
    ) -> UserResponse:
        """启用用户"""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(message="用户不存在")
        
        user.status = 'active'
        user = await self.user_repo.update(user)
        await self.session.commit()
        
        await self._log_operation(
            user_id=enabled_by,
            module='users',
            action='enable',
            resource_type='user',
            resource_id=user.id,
            description=f"启用用户: {user.username}",
        )
        
        return await self._build_user_response(user)
    
    async def _build_user_response(self, user: User) -> UserResponse:
        """构建用户响应"""
        org = None
        if user.org_id:
            org = await self.org_repo.get_by_id(user.org_id)
        
        roles = await self.role_repo.get_user_roles(user.id)
        permissions = await self.perm_repo.get_user_permissions(user.id)
        
        from .schemas import OrganizationInfo, RoleInfo
        
        return UserResponse(
            id=user.id,
            username=user.username,
            real_name=user.real_name,
            employee_id=user.employee_id,
            user_type=user.user_type,
            org_id=user.org_id,
            organization=OrganizationInfo(
                id=org.id, code=org.code, name=org.name, short_name=org.short_name
            ) if org else None,
            department=user.department,
            position=user.position,
            rank=user.rank,
            phone=user.phone,
            email=user.email,
            certifications=user.certifications or [],
            specialties=user.specialties or [],
            can_operate_uav=user.can_operate_uav,
            can_operate_ugv=user.can_operate_ugv,
            can_operate_usv=user.can_operate_usv,
            status=user.status,
            last_login_at=user.last_login_at,
            roles=[RoleInfo(id=r.id, code=r.code, name=r.name) for r in roles],
            permissions=permissions,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
    
    async def _log_operation(
        self,
        user_id: Optional[UUID],
        module: str,
        action: str,
        resource_type: str,
        resource_id: UUID,
        description: str,
    ) -> None:
        """记录操作日志"""
        user = await self.user_repo.get_by_id(user_id) if user_id else None
        log = OperationLog(
            user_id=user_id,
            username=user.username if user else None,
            module=module,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
        )
        await self.log_repo.create(log)
        await self.session.commit()
