"""
认证路由

/api/v2/auth/*
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.core.dependencies import get_current_user

from .schemas import LoginRequest, TokenResponse, RefreshRequest, RefreshResponse
from .service import AuthService


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="用户登录",
    description="验证用户名密码，返回JWT Token",
)
async def login(
    data: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """用户登录"""
    service = AuthService(session)
    return await service.login(data.username, data.password)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="用户登出",
    description="登出当前用户（客户端清除Token）",
)
async def logout(
    current_user: dict = Depends(get_current_user),
) -> None:
    """用户登出（无状态，客户端清除Token即可）"""
    pass


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="刷新Token",
    description="使用Refresh Token获取新的Access Token",
)
async def refresh_token(
    data: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> RefreshResponse:
    """刷新Token"""
    service = AuthService(session)
    result = await service.refresh_token(data.refresh_token)
    return RefreshResponse(**result)
