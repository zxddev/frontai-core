"""
安全工具模块

提供密码哈希、JWT Token生成与验证功能
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

logger = logging.getLogger(__name__)

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码强度正则：至少8位，包含字母和数字
PASSWORD_PATTERN = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def check_password_strength(password: str) -> bool:
    """
    检查密码强度
    
    规则: 至少8位，包含字母和数字
    """
    return bool(PASSWORD_PATTERN.match(password))


def create_access_token(
    user_id: UUID,
    username: str,
    roles: list[str],
    permissions: list[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建Access Token
    
    Args:
        user_id: 用户ID
        username: 用户名
        roles: 角色编码列表
        permissions: 权限编码列表
        expires_delta: 过期时间增量
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_expire_minutes)
    
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "permissions": permissions,
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: UUID,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建Refresh Token
    
    Args:
        user_id: 用户ID
        expires_delta: 过期时间增量
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_expire_days)
    
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """
    解码Token
    
    Returns:
        解码后的payload，失败返回None
    """
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret, 
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token解码失败: {e}")
        return None


def verify_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    验证Access Token
    
    Returns:
        验证成功返回payload，失败返回None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    if payload.get("type") != "access":
        logger.warning("Token类型不是access")
        return None
    
    return payload


def verify_refresh_token(token: str) -> Optional[str]:
    """
    验证Refresh Token
    
    Returns:
        验证成功返回user_id，失败返回None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    if payload.get("type") != "refresh":
        logger.warning("Token类型不是refresh")
        return None
    
    return payload.get("sub")
