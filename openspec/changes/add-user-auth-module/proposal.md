# Change: 添加用户权限认证模块

## Why

当前系统缺少用户认证和权限控制功能，无法实现多用户协同、角色分工和操作审计。根据应急救援业务需求，系统需要支持RBAC权限模型、内外部用户管理、席位分配等功能。

## What Changes

- **ADDED**: 用户认证模块 (`src/domains/auth/`)
  - JWT登录/登出/刷新Token
  - 密码哈希与验证
  - 当前用户信息获取

- **ADDED**: 用户管理模块 (`src/domains/users/`)
  - 用户CRUD操作
  - 组织机构管理
  - 角色分配

- **ADDED**: 权限控制模块 (`src/domains/permissions/`)
  - 角色管理
  - 权限管理
  - 权限检查中间件

- **ADDED**: 操作日志模块
  - 关键操作审计记录

## Impact

- **Affected specs**: 新增 `user-auth` capability
- **Affected code**: 
  - 新增 `src/domains/auth/`, `src/domains/users/`, `src/domains/permissions/`
  - 更新 `src/main.py` 添加路由
  - 所有现有API可能需要添加权限检查装饰器

## SQL Tables (Already Exist)

基于 `sql/v2_user_permission_model.sql` 中已定义的表：
- `operational_v2.users_v2` - 用户表
- `operational_v2.roles_v2` - 角色表
- `operational_v2.permissions_v2` - 权限表
- `operational_v2.organizations_v2` - 组织机构表
- `operational_v2.user_roles_v2` - 用户角色关联
- `operational_v2.role_permissions_v2` - 角色权限关联
- `operational_v2.operation_logs_v2` - 操作日志

## Dependencies

- `python-jose[cryptography]` - JWT处理
- `passlib[bcrypt]` - 密码哈希
- 现有FastAPI/SQLAlchemy基础设施
