"""
前端用户模块数据结构

对应前端期望的登录请求/响应格式
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: Optional[str] = Field(None, description="密码")
    passwordHash: Optional[str] = Field(None, description="密码（前端字段名）")
    mode: Optional[str] = Field(None, description="登录模式: practice(训练)/real(实战)")
    
    def get_password(self) -> str:
        """获取密码，兼容password和passwordHash字段"""
        return self.password or self.passwordHash or ""


class UserInfo(BaseModel):
    """用户信息（前端格式）"""
    userId: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    role: str = Field(..., description="角色编码: commander/scout/coordinator等")
    roleName: str = Field(..., description="角色名称")
    realName: Optional[str] = Field(None, description="真实姓名")
    permissions: list[str] = Field(default_factory=list, description="权限列表")


class LoginResponse(BaseModel):
    """登录响应（前端格式）"""
    token: str = Field(..., description="访问令牌")
    userInfo: UserInfo = Field(..., description="用户信息")
    path: str = Field("/home", description="登录成功后跳转路径")
