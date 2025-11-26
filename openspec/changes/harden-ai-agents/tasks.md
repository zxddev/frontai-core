# Tasks: 加固AI Agent模块

## 实施顺序

### Phase 1: 错误码规范（无依赖）

- [x] **T1.1** 创建AI模块异常类 `src/agents/exceptions.py`
  - 定义错误码常量（AI4xxx客户端错误，AI5xxx服务端错误）
  - 创建AIAgentError基类
  - 创建各专用异常类
  - **验证**: `python -c "from src.agents.exceptions import *"`

- [x] **T1.2** 修改router.py使用新异常
  - 替换硬编码错误码为异常类
  - 添加异常处理器统一捕获
  - **验证**: curl测试返回正确错误码格式

### Phase 2: Redis基础设施

- [x] **T2.1** 检查redis依赖
  - 检查requirements.txt是否已有redis
  - 如无则添加`redis>=5.0.0`
  - **验证**: `python -c "import redis; print(redis.__version__)"`

- [x] **T2.2** 创建Redis客户端 `src/core/redis.py`
  - 基于settings.redis_url创建异步客户端
  - 支持连接池
  - 添加健康检查方法
  - **验证**: 连接测试

### Phase 3: 资源锁实现

- [x] **T3.1** 创建资源锁模块 `src/agents/utils/resource_lock.py`
  - ResourceLock类实现
  - acquire_team_locks() - 原子性批量锁定
  - release_team_locks() - 释放锁
  - 支持TTL和锁续期
  - **验证**: 单元测试

- [x] **T3.2** 修改agent.py集成资源锁
  - run_with_db()中添加锁定逻辑
  - 分配前锁定，保存后释放
  - 异常时自动释放
  - **验证**: 并发测试

### Phase 4: 队伍状态管理

- [x] **T4.1** 修改schemes.py更新队伍状态
  - save_scheme()增加队伍状态更新
  - 将被分配队伍的status设为'deployed'
  - 设置current_task_id
  - **验证**: 数据库查询验证

- [x] **T4.2** 健康检查增加Redis状态
  - /ai/health接口添加Redis连接检查
  - **验证**: curl测试健康检查

### Phase 5: 集成测试

- [x] **T5.1** 端到端测试
  - 单请求正常流程
  - 并发请求资源锁测试
  - 异常恢复测试
  - **验证**: 所有测试通过

## 依赖关系

```
T1.1 ─┬─► T1.2
      │
T2.1 ─► T2.2 ─┬─► T3.1 ─► T3.2 ─► T4.1 ─► T4.2 ─► T5.1
              │
              └─► (并行)
```

## 风险点

1. **Redis不可用**: 需要降级策略（使用数据库锁）
2. **锁死问题**: TTL必须合理，太短会误释放，太长会阻塞
3. **性能影响**: 锁操作增加延迟，需监控

## 验收标准

1. 所有AI接口返回规范错误码格式
2. 并发10请求不会重复分配同一队伍
3. Redis断开时不影响基本功能（降级）
4. 健康检查能显示Redis状态
