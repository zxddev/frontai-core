# User Authentication & Authorization

## ADDED Requirements

### Requirement: User Login
用户登录系统SHALL验证用户名密码并返回JWT Token。

#### Scenario: 登录成功
- **WHEN** 用户提供正确的用户名和密码
- **THEN** 系统返回access_token和refresh_token
- **AND** 返回用户基本信息和权限列表

#### Scenario: 密码错误
- **WHEN** 用户提供错误的密码
- **THEN** 系统返回401错误，错误码AU4001

#### Scenario: 用户已禁用
- **WHEN** 用户账号状态为inactive或suspended
- **THEN** 系统返回403错误，错误码AU4002

---

### Requirement: Token Refresh
系统SHALL支持使用refresh_token获取新的access_token。

#### Scenario: 刷新成功
- **WHEN** 客户端提供有效的refresh_token
- **THEN** 系统返回新的access_token
- **AND** 可选返回新的refresh_token

#### Scenario: Token已过期
- **WHEN** refresh_token已过期
- **THEN** 系统返回401错误，需要重新登录

---

### Requirement: User Logout
系统SHALL支持用户登出。

#### Scenario: 登出成功
- **WHEN** 用户调用登出接口
- **THEN** 系统返回成功状态
- **AND** 客户端应清除本地Token

---

### Requirement: Get Current User
系统SHALL提供获取当前登录用户信息的接口。

#### Scenario: 获取成功
- **WHEN** 用户已登录且Token有效
- **THEN** 返回用户详细信息
- **AND** 返回用户角色和权限列表

#### Scenario: Token无效
- **WHEN** Token已过期或无效
- **THEN** 系统返回401错误

---

### Requirement: User Management
系统SHALL支持用户的增删改查操作。

#### Scenario: 创建用户
- **WHEN** 管理员创建新用户
- **THEN** 系统验证用户名唯一性
- **AND** 系统验证密码强度
- **AND** 创建成功后返回用户信息

#### Scenario: 用户名已存在
- **WHEN** 创建用户时用户名已存在
- **THEN** 系统返回409错误，错误码AU4004

#### Scenario: 密码强度不足
- **WHEN** 密码不满足强度要求
- **THEN** 系统返回400错误，错误码AU4005

#### Scenario: 禁用用户
- **WHEN** 管理员禁用用户
- **THEN** 用户状态变为inactive
- **AND** 用户无法登录

---

### Requirement: Password Change
系统SHALL支持用户修改自己的密码。

#### Scenario: 修改成功
- **WHEN** 用户提供正确的旧密码和新密码
- **THEN** 系统更新密码哈希
- **AND** 返回成功状态

#### Scenario: 旧密码错误
- **WHEN** 用户提供的旧密码不正确
- **THEN** 系统返回400错误

---

### Requirement: Permission Check
系统SHALL提供权限检查机制，保护受限资源。

#### Scenario: 有权限访问
- **WHEN** 用户拥有所需权限
- **THEN** 允许访问资源

#### Scenario: 无权限访问
- **WHEN** 用户缺少所需权限
- **THEN** 系统返回403错误，错误码AU4003

---

### Requirement: Operation Logging
系统SHALL记录关键操作日志用于审计。

#### Scenario: 记录成功操作
- **WHEN** 用户执行关键操作（创建/修改/删除）
- **THEN** 系统记录操作者、操作类型、资源、时间

#### Scenario: 记录失败操作
- **WHEN** 操作失败
- **THEN** 系统记录失败原因

---

## API Endpoints

| 方法 | 路径 | 说明 |
|-----|------|-----|
| POST | /api/v2/auth/login | 用户登录 |
| POST | /api/v2/auth/logout | 用户登出 |
| POST | /api/v2/auth/refresh | 刷新Token |
| GET | /api/v2/users/me | 获取当前用户 |
| PUT | /api/v2/users/me/password | 修改密码 |
| POST | /api/v2/users | 创建用户 |
| GET | /api/v2/users | 用户列表 |
| GET | /api/v2/users/{id} | 用户详情 |
| PUT | /api/v2/users/{id} | 更新用户 |
| POST | /api/v2/users/{id}/disable | 禁用用户 |

## Error Codes

| 错误码 | HTTP状态 | 说明 |
|-------|---------|------|
| AU4001 | 401 | 用户名或密码错误 |
| AU4002 | 403 | 用户已禁用 |
| AU4003 | 403 | 权限不足 |
| AU4004 | 409 | 用户名已存在 |
| AU4005 | 400 | 密码强度不足 |
