"""
FastAPI 依赖注入

提供认证和权限检查依赖
"""

from __future__ import annotations

from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .security import verify_access_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict[str, Any]:
    """
    获取当前用户（JWT验证依赖）
    
    从Authorization header中提取JWT Token并验证
    
    Returns:
        Token payload dict
    
    Raises:
        HTTPException 401: Token无效或缺失
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AU4001", "message": "未提供认证Token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AU4001", "message": "Token无效或已过期"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[dict[str, Any]]:
    """
    获取当前用户（可选）
    
    不强制要求登录，未登录时返回None
    """
    if not credentials:
        return None
    
    payload = verify_access_token(credentials.credentials)
    return payload


def require_permission(permission: str) -> Callable:
    """
    权限检查依赖工厂
    
    Usage:
        @router.get("/", dependencies=[Depends(require_permission("task:view"))])
        async def list_tasks(): ...
    
    Args:
        permission: 所需权限编码
    
    Returns:
        依赖函数
    
    Raises:
        HTTPException 403: 权限不足
    """
    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> None:
        user_permissions: list[str] = current_user.get("permissions", [])
        
        # 支持通配符匹配
        for perm in user_permissions:
            if perm == permission:
                return
            if perm.endswith(':*'):
                prefix = perm[:-1]
                if permission.startswith(prefix):
                    return
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AU4003", "message": f"权限不足: {permission}"},
        )
    
    return check_permission


def require_any_permission(*permissions: str) -> Callable:
    """
    任一权限检查依赖
    
    只要拥有其中任一权限即可访问
    """
    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> None:
        user_permissions: list[str] = current_user.get("permissions", [])
        
        for required in permissions:
            for perm in user_permissions:
                if perm == required:
                    return
                if perm.endswith(':*'):
                    prefix = perm[:-1]
                    if required.startswith(prefix):
                        return
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AU4003", "message": f"权限不足: 需要 {' 或 '.join(permissions)}"},
        )
    
    return check_permission


def require_all_permissions(*permissions: str) -> Callable:
    """
    全部权限检查依赖
    
    必须拥有全部指定权限才能访问
    """
    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> None:
        user_permissions: list[str] = current_user.get("permissions", [])
        
        missing = []
        for required in permissions:
            found = False
            for perm in user_permissions:
                if perm == required:
                    found = True
                    break
                if perm.endswith(':*'):
                    prefix = perm[:-1]
                    if required.startswith(prefix):
                        found = True
                        break
            if not found:
                missing.append(required)
        
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "AU4003", "message": f"权限不足: 缺少 {', '.join(missing)}"},
            )
    
    return check_permission


def require_role(role_code: str) -> Callable:
    """
    角色检查依赖
    
    检查用户是否具有指定角色
    """
    async def check_role(
        current_user: dict = Depends(get_current_user),
    ) -> None:
        user_roles: list[str] = current_user.get("roles", [])
        
        if role_code not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "AU4003", "message": f"需要角色: {role_code}"},
            )
    
    return check_role
