# Design: 用户权限认证模块

## Context

应急救援系统需要支持多用户协同工作，不同角色（指挥员、调度员、执行者等）有不同的操作权限。系统需要实现：
- 安全的用户认证（JWT）
- 基于角色的访问控制（RBAC）
- 操作审计日志

## Goals

- 实现JWT认证流程（登录/登出/刷新）
- 支持RBAC权限模型
- 匹配现有SQL表结构
- 提供可复用的权限检查中间件

## Non-Goals

- OAuth2/SSO集成（后续迭代）
- 细粒度数据权限（当前版本只做功能权限）
- 多租户隔离

## Decisions

### 1. JWT策略

- Access Token有效期: 1小时
- Refresh Token有效期: 7天
- Token存储: 客户端存储，服务端无状态
- 算法: HS256

```python
# JWT payload结构
{
    "sub": "user-uuid",           # 用户ID
    "username": "admin",          # 用户名
    "roles": ["COMMANDER"],       # 角色编码列表
    "permissions": ["task:*"],    # 权限编码列表
    "exp": 1234567890,            # 过期时间
    "type": "access"              # token类型
}
```

### 2. 权限检查流程

```
请求 → JWT验证中间件 → 权限检查装饰器 → 业务逻辑
         ↓                  ↓
      解析Token         检查permissions[]
         ↓                  ↓
      注入current_user   403/通过
```

### 3. 目录结构

```
src/domains/
├── auth/
│   ├── __init__.py
│   ├── models.py        # Role, Permission, UserRole, RolePermission
│   ├── schemas.py       # LoginRequest, TokenResponse
│   ├── repository.py    # RoleRepo, PermissionRepo
│   ├── service.py       # AuthService
│   └── router.py        # /auth/*
├── users/
│   ├── __init__.py
│   ├── models.py        # User, Organization, OperationLog
│   ├── schemas.py       # UserCreate, UserResponse
│   ├── repository.py    # UserRepo, OrgRepo
│   ├── service.py       # UserService
│   └── router.py        # /users/*
src/core/
├── security.py          # 密码哈希、JWT工具
└── dependencies.py      # get_current_user, require_permission
```

### 4. 密码安全

- 使用bcrypt哈希
- 密码强度要求: 8位以上，含字母和数字

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| Token泄露 | 短有效期 + HTTPS |
| 权限缓存过期 | Token中嵌入权限，修改后需重新登录 |
| 性能开销 | 权限列表在Token中，无需每次查库 |

## Migration Plan

1. 部署SQL表（已存在）
2. 部署新模块代码
3. 配置JWT密钥（环境变量）
4. 逐步为现有API添加权限检查

## Open Questions

- 是否需要支持多设备登录？（当前：支持）
- Token刷新是否需要记录？（当前：不记录）
