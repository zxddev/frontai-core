# Design: 救援流程模块功能完善

## Context

rescue-workflow模块的基础框架（ORM、Repository、Service、Router）已完成，但部分业务逻辑仍为占位实现。本设计文档说明如何完善这些功能。

## Goals / Non-Goals

**Goals:**
- 完善9个非AI功能的完整业务逻辑
- 确保数据持久化和查询正常工作
- 实现跨模块数据聚合（协同总览）

**Non-Goals:**
- 不实现AI功能
- 不修改API接口定义
- 不重构已完成的基础架构

## Decisions

### D1: 安全点查询策略

**决策**: 复用map_entities模块，查询`entity_type`为`resettle_point`或`safety_area`的实体

**实现**:
```python
async def get_safe_points(self, event_id: UUID, route_id: UUID) -> list[SafePoint]:
    # 获取事件关联的scenario_id
    event = await self._event_service.get_by_id(event_id)
    
    # 查询安全点实体
    entities = await self._entity_service.list(
        scenario_id=event.scenario_id,
        entity_types="resettle_point,safety_area",
    )
    
    # 转换为SafePoint响应
    return [self._entity_to_safe_point(e) for e in entities.items]
```

**原因**: 
- 安全点数据已存在于map_entities表
- 避免重复存储
- 复用现有空间查询能力

### D2: 队伍/车辆位置查询

**决策**: 扩展TeamService和VehicleService，添加位置查询方法

**实现方案**:
1. 队伍/车辆表已有`current_location`字段（Geometry类型）
2. 添加`list_with_location`方法，返回带位置的资源列表
3. 按task关联筛选（deployed状态且关联到当前事件的任务）

```python
# TeamService新增方法
async def list_deployed_with_location(
    self, 
    task_ids: list[UUID]
) -> list[TeamLocationResponse]:
    ...

# get_coordination_overview中调用
task_ids = await self._task_service.list_task_ids_by_event(event_id)
team_locations = await self._team_service.list_deployed_with_location(task_ids)
```

### D3: 评估报告持久化

**决策**: 新建`evaluation_reports_v2`表存储AI生成的报告

**表结构**:
```sql
CREATE TABLE evaluation_reports_v2 (
    id UUID PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,  -- 一个事件一份报告
    report_data JSONB NOT NULL,      -- 完整报告内容
    generated_at TIMESTAMPTZ NOT NULL,
    generated_by VARCHAR(50),        -- ai/manual
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**原因**:
- 报告内容复杂，使用JSONB存储灵活
- 一个事件只有一份最终报告
- 便于后续扩展（版本历史等）

### D4: 协同更新路由逻辑

**决策**: 根据`entity_type`分发到对应Service

**实现**:
```python
async def update_coordination(self, scenario_id: UUID, data: CoordinationUpdate):
    match data.entity_type:
        case "team":
            await self._team_service.update_location(data.entity_id, data.data["location"])
        case "vehicle":
            await self._vehicle_service.update_location(data.entity_id, data.data["location"])
        case "rescue_point":
            await self.update_rescue_point(data.entity_id, RescuePointUpdate(**data.data))
    
    # 广播更新
    await broadcast_event_update(scenario_id, "coordination_update", {...})
```

### D5: 准备任务完成重构

**决策**: 保持现有实现，但添加注释说明设计决策

**原因**:
- TaskService.complete()要求assignee信息，但准备任务可能无明确assignee
- 当前直接操作Repository是合理的临时方案
- 后续可考虑为TaskService添加`complete_without_assignee`方法

### D6: 救援点检测确认

**决策**: 确认时传入完整信息创建RescuePoint

**修改RescuePointConfirm schema**:
```python
class RescuePointConfirm(BaseModel):
    detection_id: UUID
    is_confirmed: bool
    # 新增字段（确认时必填）
    event_id: Optional[UUID] = None
    name: Optional[str] = None
    location: Optional[Location] = None
    point_type: Optional[str] = None
    estimated_victims: Optional[int] = None
```

**实现**:
```python
if data.is_confirmed and data.event_id and data.location:
    rescue_point = await self.create_rescue_point(
        scenario_id=scenario_id,
        data=RescuePointCreate(
            event_id=data.event_id,
            name=data.name or f"检测点-{data.detection_id}",
            location=data.location,
            point_type=data.point_type or "trapped_person",
            estimated_victims=data.estimated_victims or 0,
        )
    )
    result["rescue_point_id"] = rescue_point.id
```

### D7: 无人机集群控制

**决策**: 集成DeviceService批量更新设备状态

**实现**:
```python
async def control_uav_cluster(self, data: UAVClusterControl):
    from src.domains.resources.devices.service import DeviceService
    from src.domains.resources.devices.schemas import DeviceStatus
    
    device_service = DeviceService(self._db)
    
    status_map = {
        "deploy": DeviceStatus.deployed,
        "recall": DeviceStatus.available,
        "reposition": DeviceStatus.deployed,
    }
    
    target_status = status_map.get(data.command_type, DeviceStatus.deployed)
    
    for uav_id in data.uav_ids:
        try:
            await device_service.update_status(uav_id, target_status)
        except NotFoundError:
            logger.warning(f"设备不存在: {uav_id}")
    
    return {...}
```

### D8: scheme_id来源

**决策**: 从event关联的scheme获取，若无则创建临时scheme

**分析**:
- 准备任务属于事件响应阶段，可能尚未创建正式scheme
- 方案1: 创建"应急准备"类型的临时scheme
- 方案2: 允许task的scheme_id为NULL（需修改表结构）

**选择方案1**:
```python
async def create_preparation_tasks(self, scenario_id, event_id, tasks):
    # 查找或创建准备阶段scheme
    prep_scheme = await self._scheme_service.get_or_create_preparation_scheme(
        scenario_id=scenario_id,
        event_id=event_id,
    )
    
    for task in tasks:
        task_create = TaskCreate(
            scheme_id=prep_scheme.id,
            ...
        )
```

## Migration Plan

1. **Phase 1: 数据库准备**
   - 执行`sql/v2_rescue_points.sql`创建表
   - 创建`sql/v2_evaluation_reports.sql`

2. **Phase 2: 服务层扩展**
   - TeamService添加`list_deployed_with_location`
   - VehicleService添加`list_deployed_with_location`
   - SchemeService添加`get_or_create_preparation_scheme`

3. **Phase 3: 业务逻辑完善**
   - 实现`get_safe_points`
   - 实现`get_coordination_overview`位置查询
   - 实现`update_coordination`分发逻辑
   - 实现`control_uav_cluster`设备控制
   - 实现`confirm_rescue_point_detection`自动创建
   - 实现`get_evaluation_report`查询

4. **Phase 4: Schema扩展**
   - 修改RescuePointConfirm添加可选字段

## Open Questions

1. **安全点筛选**: 是否需要按路径/区域筛选安全点？
   - 当前实现返回scenario下所有安全点，后续可添加空间过滤

2. **评估报告版本**: 是否需要支持多版本报告？
   - 当前设计为一个事件一份报告，可后续扩展
