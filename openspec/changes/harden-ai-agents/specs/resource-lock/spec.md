# Spec: 资源分配锁

## ADDED Requirements

### Requirement: 并发资源锁定

方案生成时必须锁定被分配的队伍，防止同一队伍被多个事件同时分配。

#### Scenario: 单事件正常分配

- **Given**: 系统空闲，无并发请求
- **When**: 事件A请求生成方案，选中team-001和team-002
- **Then**: 
  - Redis中创建锁键 `ai:team_lock:team-001` 和 `ai:team_lock:team-002`
  - 方案保存成功
  - 队伍状态更新为 `deployed`
  - Redis锁释放

#### Scenario: 并发请求锁定同一队伍

- **Given**: 事件A正在处理，已锁定team-001
- **When**: 事件B请求生成方案，也选中team-001
- **Then**: 
  - 事件B获取锁失败
  - 返回HTTP 409，错误码AI4003
  - 事件A的锁不受影响

#### Scenario: 批量锁定原子性

- **Given**: 事件A需要锁定team-001, team-002, team-003
- **When**: team-002已被事件B锁定
- **Then**:
  - 批量锁定失败
  - team-001和team-003不会被部分锁定
  - 返回AI4003错误

#### Scenario: 锁自动过期

- **Given**: 事件A获取了team-001的锁，TTL=300秒
- **When**: 事件A处理异常崩溃，未能主动释放锁
- **Then**:
  - 300秒后锁自动过期
  - team-001可被其他事件分配

---

### Requirement: Redis降级策略

Redis不可用时，系统必须能够降级到数据库锁。

#### Scenario: Redis连接失败降级

- **Given**: Redis服务不可用
- **When**: 事件A请求生成方案
- **Then**:
  - 记录警告日志
  - 使用数据库行级锁（SELECT FOR UPDATE）
  - 方案正常生成
  - 健康检查返回degraded状态

---

### Requirement: 队伍状态同步

方案保存时必须同步更新队伍状态。

#### Scenario: 方案保存更新队伍状态

- **Given**: 方案包含team-001和team-002的分配
- **When**: 方案保存到数据库
- **Then**:
  - `rescue_teams_v2.status` 更新为 'deployed'
  - `rescue_teams_v2.current_task_id` 设置为事件ID
  - `rescue_teams_v2.updated_at` 更新

#### Scenario: 查询排除已部署队伍

- **Given**: team-001状态为deployed
- **When**: 新事件查询可用队伍
- **Then**: team-001不在查询结果中

---

## Cross-References

- 依赖: `src/core/redis.py` Redis客户端
- 依赖: `src/agents/exceptions.py` 异常定义
- 被依赖: `src/agents/scheme_generation/agent.py` 方案生成流程
- 相关表: `operational_v2.rescue_teams_v2`
