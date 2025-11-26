"""
前端用户API路由

接口路径: /user/*
对接前端用户登录等操作
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.domains.auth.service import AuthService
from src.domains.frontend_api.common import ApiResponse
from .schemas import LoginRequest, LoginResponse, UserInfo


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["前端-用户"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """获取认证服务实例"""
    return AuthService(db)


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse[LoginResponse]:
    """
    用户登录
    
    验证用户名密码，返回token和用户信息
    前端存储token后，后续请求通过Authorization头携带
    """
    logger.info(f"用户登录请求, username={request.username}, mode={request.mode}")
    
    try:
        # 兼容password和passwordHash字段
        password = request.get_password()
        if not password:
            return ApiResponse.error(400, "密码不能为空")
        
        result = await service.login(request.username, password)
        
        primary_role = result.user.roles[0] if result.user.roles else None
        role_code = primary_role.code if primary_role else "user"
        role_name = primary_role.name if primary_role else "普通用户"
        
        user_info = UserInfo(
            userId=str(result.user.id),
            username=result.user.username,
            role=role_code,
            roleName=role_name,
            realName=result.user.real_name,
            permissions=result.user.permissions,
        )
        
        login_response = LoginResponse(
            token=result.access_token,
            userInfo=user_info,
        )
        
        logger.info(f"用户登录成功, userId={result.user.id}, role={role_code}")
        return ApiResponse.success(login_response)
        
    except Exception as e:
        error_msg = str(e)
        if "用户名或密码错误" in error_msg or "AU4001" in error_msg:
            logger.warning(f"登录失败: 用户名或密码错误, username={request.username}")
            return ApiResponse.error(401, "用户名或密码错误")
        elif "用户已禁用" in error_msg or "AU4002" in error_msg:
            logger.warning(f"登录失败: 用户已禁用, username={request.username}")
            return ApiResponse.error(403, "用户已禁用")
        else:
            logger.exception(f"登录失败: {e}")
            return ApiResponse.error(500, f"登录失败: {error_msg}")
