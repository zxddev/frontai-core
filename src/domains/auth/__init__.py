"""
认证授权模块

提供JWT登录、Token刷新、权限检查功能
"""

from .models import Role, Permission, RolePermission, UserRole
from .schemas import LoginRequest, TokenResponse, RefreshRequest, RefreshResponse
from .service import AuthService, PermissionService
from .router import router as auth_router

__all__ = [
    "Role",
    "Permission", 
    "RolePermission",
    "UserRole",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "RefreshResponse",
    "AuthService",
    "PermissionService",
    "auth_router",
]
