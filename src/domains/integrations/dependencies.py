"""
第三方接入认证依赖

提供API密钥验证功能
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from .models import ApiKey

logger = logging.getLogger(__name__)


class ApiKeyAuth:
    """API密钥认证上下文"""
    
    def __init__(
        self,
        api_key: ApiKey,
        source_system: str,
        request_id: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.source_system = source_system
        self.request_id = request_id
    
    def has_scope(self, scope: str) -> bool:
        """检查是否有指定权限"""
        return self.api_key.has_scope(scope)


def hash_api_key(key: str) -> str:
    """计算API密钥的SHA256哈希"""
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    """获取密钥前缀（前8位）"""
    return key[:8] if len(key) >= 8 else key


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-Api-Key"),
    x_source_system: Optional[str] = Header(None, alias="X-Source-System"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id"),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyAuth:
    """
    验证API密钥
    
    从X-Api-Key Header获取密钥并验证。
    验证通过后更新最后使用时间。
    
    Raises:
        HTTPException 401: 密钥无效或缺失
    """
    # 检查密钥是否存在
    if not x_api_key:
        logger.warning("API请求缺少X-Api-Key Header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "MISSING_API_KEY",
                "message": "缺少API密钥",
            },
        )
    
    # 计算密钥哈希和前缀
    key_hash = hash_api_key(x_api_key)
    key_prefix = get_key_prefix(x_api_key)
    
    logger.debug(f"验证API密钥: prefix={key_prefix}, source_system={x_source_system}")
    
    # 查询密钥（通过前缀快速定位）
    stmt = select(ApiKey).where(ApiKey.key_prefix == key_prefix)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    # 密钥不存在
    if not api_key:
        logger.warning(f"API密钥不存在: prefix={key_prefix}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "API密钥无效",
            },
        )
    
    # 验证完整哈希
    if api_key.key_hash != key_hash:
        logger.warning(f"API密钥哈希不匹配: prefix={key_prefix}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "API密钥无效",
            },
        )
    
    # 检查密钥状态
    if not api_key.is_valid():
        logger.warning(f"API密钥已失效: prefix={key_prefix}, status={api_key.status}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "API密钥已失效或过期",
            },
        )
    
    # 验证来源系统（如果提供了X-Source-System）
    source_system = x_source_system or api_key.source_system
    if x_source_system and x_source_system != api_key.source_system:
        logger.warning(
            f"来源系统不匹配: expected={api_key.source_system}, got={x_source_system}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "error_code": "UNAUTHORIZED",
                "message": "来源系统与密钥不匹配",
            },
        )
    
    # 更新最后使用时间
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.utcnow())
    )
    await db.commit()
    
    logger.info(
        f"API密钥验证通过: source_system={source_system}, request_id={x_request_id}"
    )
    
    return ApiKeyAuth(
        api_key=api_key,
        source_system=source_system,
        request_id=x_request_id,
    )


def require_scope(scope: str):
    """
    权限范围检查依赖工厂
    
    用于检查API密钥是否具有特定接口权限。
    
    Usage:
        @router.post("/disaster-report", dependencies=[Depends(require_scope("disaster-report"))])
        async def disaster_report(...): ...
    """
    async def check_scope(
        auth: ApiKeyAuth = Depends(verify_api_key),
    ) -> ApiKeyAuth:
        if not auth.has_scope(scope):
            logger.warning(
                f"API密钥权限不足: source_system={auth.source_system}, "
                f"required_scope={scope}, available_scopes={auth.api_key.scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "error_code": "FORBIDDEN",
                    "message": f"API密钥无权访问此接口: 需要 {scope} 权限",
                },
            )
        return auth
    
    return check_scope
