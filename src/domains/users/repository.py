"""
用户管理数据访问层

提供User、Organization、OperationLog的CRUD操作
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Organization, OperationLog


class UserRepository:
    """用户数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def create(self, user: User) -> User:
        """创建用户"""
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """根据ID获取用户"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def exists_username(self, username: str) -> bool:
        """检查用户名是否存在"""
        result = await self.session.execute(
            select(func.count()).select_from(User).where(User.username == username)
        )
        return result.scalar() > 0
    
    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        org_id: Optional[UUID] = None,
        user_type: Optional[str] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> tuple[list[User], int]:
        """
        分页获取用户列表
        
        Returns:
            (users, total)
        """
        query = select(User)
        count_query = select(func.count()).select_from(User)
        
        conditions = []
        if org_id:
            conditions.append(User.org_id == org_id)
        if user_type:
            conditions.append(User.user_type == user_type)
        if status:
            conditions.append(User.status == status)
        if keyword:
            conditions.append(
                or_(
                    User.username.ilike(f"%{keyword}%"),
                    User.real_name.ilike(f"%{keyword}%"),
                    User.phone.ilike(f"%{keyword}%"),
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # 分页
        offset = (page - 1) * page_size
        query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        
        result = await self.session.execute(query)
        users = list(result.scalars().all())
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        return users, total
    
    async def update(self, user: User) -> User:
        """更新用户"""
        user.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def update_last_login(self, user_id: UUID) -> None:
        """更新最后登录时间"""
        user = await self.get_by_id(user_id)
        if user:
            user.last_login_at = datetime.utcnow()
            await self.session.flush()
    
    async def delete(self, user_id: UUID) -> bool:
        """删除用户"""
        user = await self.get_by_id(user_id)
        if user:
            await self.session.delete(user)
            await self.session.flush()
            return True
        return False


class OrganizationRepository:
    """组织机构数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def create(self, org: Organization) -> Organization:
        """创建组织"""
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)
        return org
    
    async def get_by_id(self, org_id: UUID) -> Optional[Organization]:
        """根据ID获取组织"""
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_code(self, code: str) -> Optional[Organization]:
        """根据编码获取组织"""
        result = await self.session.execute(
            select(Organization).where(Organization.code == code)
        )
        return result.scalar_one_or_none()
    
    async def list_organizations(
        self,
        parent_id: Optional[UUID] = None,
        org_type: Optional[str] = None,
        status: str = "active",
    ) -> list[Organization]:
        """获取组织列表"""
        query = select(Organization).where(Organization.status == status)
        
        if parent_id is not None:
            query = query.where(Organization.parent_id == parent_id)
        if org_type:
            query = query.where(Organization.org_type == org_type)
        
        result = await self.session.execute(query.order_by(Organization.org_level, Organization.name))
        return list(result.scalars().all())
    
    async def get_children(self, parent_id: UUID) -> list[Organization]:
        """获取子组织"""
        return await self.list_organizations(parent_id=parent_id)
    
    async def update(self, org: Organization) -> Organization:
        """更新组织"""
        org.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(org)
        return org


class OperationLogRepository:
    """操作日志数据访问层"""
    
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    
    async def create(self, log: OperationLog) -> OperationLog:
        """创建操作日志"""
        self.session.add(log)
        await self.session.flush()
        await self.session.refresh(log)
        return log
    
    async def list_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[UUID] = None,
        module: Optional[str] = None,
        action: Optional[str] = None,
        scenario_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[list[OperationLog], int]:
        """分页获取操作日志"""
        query = select(OperationLog)
        count_query = select(func.count()).select_from(OperationLog)
        
        conditions = []
        if user_id:
            conditions.append(OperationLog.user_id == user_id)
        if module:
            conditions.append(OperationLog.module == module)
        if action:
            conditions.append(OperationLog.action == action)
        if scenario_id:
            conditions.append(OperationLog.scenario_id == scenario_id)
        if start_time:
            conditions.append(OperationLog.created_at >= start_time)
        if end_time:
            conditions.append(OperationLog.created_at <= end_time)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        offset = (page - 1) * page_size
        query = query.order_by(OperationLog.created_at.desc()).offset(offset).limit(page_size)
        
        result = await self.session.execute(query)
        logs = list(result.scalars().all())
        
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        return logs, total
