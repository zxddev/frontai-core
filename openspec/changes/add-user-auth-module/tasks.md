# Tasks: 用户权限认证模块

## 1. 基础设施

- [x] 1.1 创建 `src/domains/auth/` 目录结构
- [x] 1.2 创建 `src/domains/users/` 目录结构
- [x] 1.3 添加JWT配置到 `src/core/config.py`
- [x] 1.4 创建密码工具类 `src/core/security.py`

## 2. ORM模型 (匹配SQL表)

- [x] 2.1 创建 `users/models.py` - User, Organization, OperationLog 模型
- [x] 2.2 创建 `auth/models.py` - Role, Permission, UserRole, RolePermission 模型

## 3. Schemas (Pydantic)

- [x] 3.1 创建 `auth/schemas.py` - LoginRequest, TokenResponse, UserInfo
- [x] 3.2 创建 `users/schemas.py` - UserCreate, UserUpdate, UserResponse
- [x] 3.3 创建 `auth/schemas.py` - RoleResponse, PermissionResponse

## 4. Repository层

- [x] 4.1 创建 `users/repository.py` - UserRepository, OrganizationRepository
- [x] 4.2 创建 `auth/repository.py` - RoleRepository, PermissionRepository

## 5. Service层

- [x] 5.1 创建 `auth/service.py` - AuthService (login/logout/refresh)
- [x] 5.2 创建 `users/service.py` - UserService (CRUD)
- [x] 5.3 创建权限检查服务 `auth/permission_service.py` (集成到 auth/service.py)

## 6. Router层

- [x] 6.1 创建 `auth/router.py` - /auth/login, /auth/logout, /auth/refresh
- [x] 6.2 创建 `users/router.py` - /users CRUD, /users/me
- [x] 6.3 注册路由到 `main.py`

## 7. 权限中间件

- [x] 7.1 创建 `src/core/dependencies.py` - JWT验证依赖 (get_current_user)
- [x] 7.2 创建权限检查装饰器 (require_permission, require_role)

## 8. 验证测试

- [x] 8.1 语法检查 (py_compile) - ✅ 通过
- [ ] 8.2 手动测试登录流程 (需要运行时测试)
- [ ] 8.3 验证权限检查中间件 (需要运行时测试)
