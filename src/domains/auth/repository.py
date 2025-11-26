"""
认证授权数据访问层

提供Role、Permission、UserRole、RolePermission的CRUD操作
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Role, Permission, RolePermission, UserRole


class RoleRepository:
    """角色数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def create(self, role: Role) -> Role:
        """创建角色"""
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role
    
    async def get_by_id(self, role_id: UUID) -> Optional[Role]:
        """根据ID获取角色"""
        result = await self.session.execute(
            select(Role).where(Role.id == role_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Role]:
        """根据编码获取角色"""
        result = await self.session.execute(
            select(Role).where(Role.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list_roles(
        self,
        category: Optional[str] = None,
        status: str = "active",
    ) -> list[Role]:
        """获取角色列表"""
        query = select(Role).where(Role.status == status)
        
        if category:
            query = query.where(Role.role_category == category)
        
        result = await self.session.execute(query.order_by(Role.role_level, Role.name))
        return list(result.scalars().all())
    
    async def update(self, role: Role) -> Role:
        """更新角色"""
        role.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(role)
        return role
    
    async def delete(self, role_id: UUID) -> bool:
        """删除角色（非系统内置）"""
        role = await self.get_by_id(role_id)
        if role and not role.is_system:
            await self.session.delete(role)
            await self.session.flush()
            return True
        return False
    
    async def get_user_roles(self, user_id: UUID) -> list[Role]:
        """获取用户的所有角色"""
        result = await self.session.execute(
            select(Role).join(
                UserRole, Role.id == UserRole.role_id
            ).where(
                and_(
                    UserRole.user_id == user_id,
                    Role.status == 'active'
                )
            )
        )
        return list(result.scalars().all())


class PermissionRepository:
    """权限数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def create(self, permission: Permission) -> Permission:
        """创建权限"""
        self.session.add(permission)
        await self.session.flush()
        await self.session.refresh(permission)
        return permission
    
    async def get_by_id(self, perm_id: UUID) -> Optional[Permission]:
        """根据ID获取权限"""
        result = await self.session.execute(
            select(Permission).where(Permission.id == perm_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Permission]:
        """根据编码获取权限"""
        result = await self.session.execute(
            select(Permission).where(Permission.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list_permissions(
        self,
        module: Optional[str] = None,
    ) -> list[Permission]:
        """获取权限列表"""
        query = select(Permission)
        
        if module:
            query = query.where(Permission.module == module)
        
        result = await self.session.execute(query.order_by(Permission.module, Permission.code))
        return list(result.scalars().all())
    
    async def get_role_permissions(self, role_id: UUID) -> list[Permission]:
        """获取角色的所有权限"""
        result = await self.session.execute(
            select(Permission).join(
                RolePermission, Permission.id == RolePermission.permission_id
            ).where(RolePermission.role_id == role_id)
        )
        return list(result.scalars().all())
    
    async def get_user_permissions(self, user_id: UUID) -> list[str]:
        """获取用户的所有权限编码"""
        result = await self.session.execute(
            select(Permission.code).distinct().join(
                RolePermission, Permission.id == RolePermission.permission_id
            ).join(
                UserRole, RolePermission.role_id == UserRole.role_id
            ).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())


class UserRoleRepository:
    """用户角色关联数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def assign_role(
        self,
        user_id: UUID,
        role_id: UUID,
        scope_type: str = "global",
        scope_id: Optional[UUID] = None,
        valid_until: Optional[datetime] = None,
        granted_by: Optional[UUID] = None,
    ) -> UserRole:
        """为用户分配角色"""
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
            valid_until=valid_until,
            granted_by=granted_by,
        )
        self.session.add(user_role)
        await self.session.flush()
        await self.session.refresh(user_role)
        return user_role
    
    async def revoke_role(self, user_id: UUID, role_id: UUID) -> bool:
        """撤销用户角色"""
        result = await self.session.execute(
            delete(UserRole).where(
                and_(
                    UserRole.user_id == user_id,
                    UserRole.role_id == role_id
                )
            )
        )
        await self.session.flush()
        return result.rowcount > 0
    
    async def get_user_role_ids(self, user_id: UUID) -> list[UUID]:
        """获取用户的角色ID列表"""
        result = await self.session.execute(
            select(UserRole.role_id).where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())
    
    async def revoke_all_roles(self, user_id: UUID) -> int:
        """撤销用户所有角色"""
        result = await self.session.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        await self.session.flush()
        return result.rowcount


class RolePermissionRepository:
    """角色权限关联数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def assign_permission(
        self,
        role_id: UUID,
        permission_id: UUID,
        data_scope: str = "all",
    ) -> RolePermission:
        """为角色分配权限"""
        role_perm = RolePermission(
            role_id=role_id,
            permission_id=permission_id,
            data_scope=data_scope,
        )
        self.session.add(role_perm)
        await self.session.flush()
        await self.session.refresh(role_perm)
        return role_perm
    
    async def revoke_permission(self, role_id: UUID, permission_id: UUID) -> bool:
        """撤销角色权限"""
        result = await self.session.execute(
            delete(RolePermission).where(
                and_(
                    RolePermission.role_id == role_id,
                    RolePermission.permission_id == permission_id
                )
            )
        )
        await self.session.flush()
        return result.rowcount > 0
