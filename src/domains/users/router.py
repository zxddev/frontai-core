"""
用户管理路由

/api/v2/users/*
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_user, require_permission

from .schemas import (
    UserCreate, UserUpdate, UserResponse, UserListResponse,
    CurrentUserResponse, PasswordChange
)
from .service import UserService


router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="获取当前用户",
    description="获取当前登录用户的详细信息",
)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentUserResponse:
    """获取当前用户信息"""
    service = UserService(session)
    return await service.get_current_user(UUID(current_user["sub"]))


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="修改密码",
    description="修改当前用户的密码",
)
async def change_password(
    data: PasswordChange,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    """修改密码"""
    service = UserService(session)
    await service.change_password(
        user_id=UUID(current_user["sub"]),
        old_password=data.old_password,
        new_password=data.new_password,
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
    description="创建新用户（需要user:create权限）",
    dependencies=[Depends(require_permission("user:create"))],
)
async def create_user(
    data: UserCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """创建用户"""
    service = UserService(session)
    return await service.create_user(
        data=data,
        created_by=UUID(current_user["sub"]),
    )


@router.get(
    "",
    response_model=UserListResponse,
    summary="用户列表",
    description="分页获取用户列表（需要user:view权限）",
    dependencies=[Depends(require_permission("user:view"))],
)
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    org_id: Optional[UUID] = Query(None, description="组织ID"),
    user_type: Optional[str] = Query(None, description="用户类型"),
    status: Optional[str] = Query(None, description="状态"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserListResponse:
    """获取用户列表"""
    service = UserService(session)
    return await service.list_users(
        page=page,
        page_size=page_size,
        org_id=org_id,
        user_type=user_type,
        status=status,
        keyword=keyword,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="用户详情",
    description="获取指定用户的详细信息",
    dependencies=[Depends(require_permission("user:view"))],
)
async def get_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """获取用户详情"""
    service = UserService(session)
    return await service.get_user(user_id)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="更新用户",
    description="更新用户信息（需要user:edit权限）",
    dependencies=[Depends(require_permission("user:edit"))],
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """更新用户"""
    service = UserService(session)
    return await service.update_user(
        user_id=user_id,
        data=data,
        updated_by=UUID(current_user["sub"]),
    )


@router.post(
    "/{user_id}/disable",
    response_model=UserResponse,
    summary="禁用用户",
    description="禁用指定用户（需要user:edit权限）",
    dependencies=[Depends(require_permission("user:edit"))],
)
async def disable_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """禁用用户"""
    service = UserService(session)
    return await service.disable_user(
        user_id=user_id,
        disabled_by=UUID(current_user["sub"]),
    )


@router.post(
    "/{user_id}/enable",
    response_model=UserResponse,
    summary="启用用户",
    description="启用指定用户（需要user:edit权限）",
    dependencies=[Depends(require_permission("user:edit"))],
)
async def enable_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    """启用用户"""
    service = UserService(session)
    return await service.enable_user(
        user_id=user_id,
        enabled_by=UUID(current_user["sub"]),
    )
