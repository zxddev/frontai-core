# Design: 救援流程模块技术设计

## Context

rescue-workflow模块覆盖五阶段救援流程（接警通报→应急准备→机动前出→灾情侦察→救援指挥→总结评估），需要与多个已有模块协作：

- **events**: 事件管理（events_v2表）
- **tasks**: 任务管理（tasks_v2表）
- **teams**: 队伍管理
- **vehicles**: 车辆管理
- **map_entities**: 地图实体（指挥所等）
- **devices**: 设备管理（无人机）

## Goals / Non-Goals

**Goals:**
- 实现14个普通业务接口的完整数据库操作
- 创建RescuePoint ORM模型复用rescue_points_v2表
- 复用已有模块避免代码重复
- 保持AI接口占位，返回Mock数据

**Non-Goals:**
- 不实现AI功能（装备推荐、路径规划、风险预测等）
- 不修改数据库表结构（使用现有表）
- 不添加新的外部依赖

## Decisions

### D1: 模块复用策略

**决策**: 在RescueWorkflowService中注入并调用其他Service

```python
class RescueWorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._event_service = EventService(db)
        self._task_service = TaskService(db)
        # ...
```

**原因**: 避免代码重复，保持单一职责

### D2: RescuePoint模型设计

**决策**: 创建独立的ORM模型对应rescue_points_v2表

```python
class RescuePoint(Base):
    __tablename__ = "rescue_points_v2"
    # 字段与SQL定义一致
```

**原因**: 数据库表已存在，只需创建ORM映射

### D3: 准备完成接口设计

**决策**: 新增路由 `POST /incidents/preparation-tasks/{id}/complete`

- 接收完成状态（装备检查结果、人员到位、燃油等）
- 更新对应Task状态
- 返回批次进度

### D4: 指挥所创建

**决策**: 复用map_entities模块创建指挥所实体

```python
async def confirm_command_post(self, scenario_id, data):
    entity_data = EntityCreate(
        scenario_id=scenario_id,
        entity_type="command_post",
        location=data.location,
        name=data.name,
        # ...
    )
    return await self._entity_service.create(entity_data)
```

### D5: 协同总览数据聚合

**决策**: 在Repository层实现聚合查询

- 查询event关联的所有rescue_points
- 查询当前任务分配的teams位置
- 查询派遣的vehicles位置
- 计算总体进度

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| 模块间循环依赖 | 通过构造函数注入，避免在模块级别import |
| 事务一致性 | 使用同一db session，由调用方控制commit |
| 性能问题（聚合查询） | 添加必要索引，使用视图优化 |

## Migration Plan

1. 创建models.py（RescuePoint ORM）
2. 创建repository.py（数据访问层）
3. 修改service.py（实现业务逻辑）
4. 修改router.py（添加缺失的路由）
5. 验证所有接口

## Open Questions

1. 安全点数据来源？是否需要新建表还是复用map_entities？
   - **暂定**: 复用map_entities，entity_type="safe_point"
   
2. 评估报告是否需要持久化？
   - **暂定**: AI生成后持久化到新表或JSONB字段
