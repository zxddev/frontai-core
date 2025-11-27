# Design: 灾害-想定-事件关联机制

## Context

### 背景
应急救援系统使用三层概念模型：
- **想定(Scenario)** - 应急响应的顶层容器，对应ICS的Area Command
- **事件(Event)** - 具体救援任务触发点，街道级/点位级
- **灾害(Disaster)** - 危险区域态势信息，用于预警和态势感知

当前问题：灾害记录与想定/事件体系割裂，无法实现完整的应急响应流程。

### 参考标准
- NIMS (National Incident Management System) - 美国国家应急管理体系
- ICS (Incident Command System) - 事故指挥系统

## Goals / Non-Goals

### Goals
1. 灾害记录能够关联到想定，纳入统一指挥框架
2. 需要救援响应的灾害能自动创建事件
3. 灾害边界能在地图上实时渲染
4. 前端能实时收到灾害通知

### Non-Goals
- 不改变现有events_v2表结构
- 不改变现有scenarios表结构
- 不实现灾害自动升级机制（后续迭代）

## Data Model

### 层级关系
```
想定(Scenario) ─ 应急响应顶层容器
    │
    ├── 灾害态势(Disaster) ─ 危险区域信息
    │   ├── 触发型：severity>=3, needs_response=true → 创建事件
    │   └── 预警型：仅通知，不创建事件
    │
    ├── 事件(Event) ─ 具体救援任务
    │   └── 可关联灾害（disaster_id）
    │
    └── 预警(Warning) ─ 通知机制
        └── 关联灾害（disaster_id）
```

### 修改字段
```sql
ALTER TABLE operational_v2.disaster_situations ADD COLUMN
    scenario_id UUID REFERENCES operational_v2.scenarios_v2(id),
    needs_response BOOLEAN DEFAULT true,
    linked_event_id UUID REFERENCES operational_v2.events_v2(id),
    map_entity_id UUID REFERENCES operational_v2.entities_v2(id);
```

## API Flow

### /disasters/update 完整流程
```
POST /api/v2/ai/early-warning/disasters/update
    │
    ├─① 创建 disaster_situations 记录
    │
    ├─② 关联想定
    │   ├── 有 scenario_id → 直接关联
    │   ├── 无 scenario_id → 按位置查找进行中的想定
    │   └── 无匹配且 severity>=4 → 创建新想定（可选）
    │
    ├─③ 判断是否创建事件
    │   ├── needs_response=true && severity>=3 → 创建事件
    │   └── 否则 → 跳过
    │
    ├─④ 创建 map_entity (danger_zone)
    │   └── WebSocket推送 /topic/map.entity.create
    │
    ├─⑤ 查询范围内队伍，创建 warning_records
    │
    ├─⑥ WebSocket推送灾害通知
    │   └── /topic/scenario.disaster.triggered
    │
    └─⑦ 返回响应
```

## Decisions

### Decision 1: 灾害分类
- **触发型灾害**：needs_response=true，会创建事件启动救援流程
- **预警型灾害**：needs_response=false，仅用于预警通知（如天气预警）

理由：天气预警等情况只需通知相关人员注意，不需要启动救援流程。

### Decision 2: 想定关联策略
优先级：
1. 请求中指定 scenario_id
2. 按灾害位置查找进行中的想定
3. severity>=4 时提示是否创建新想定

理由：大多数灾害应归属于已有想定；只有重大灾害需要启动新的应急响应。

### Decision 3: 地图实体类型
使用 `danger_zone` 类型（多边形），对应 EntityType.danger_zone。

理由：现有map_entities系统已定义此类型，前端已有渲染支持。

## Risks / Trade-offs

### Risk 1: 想定自动创建
如果按位置找不到想定且severity>=4，是否自动创建？
- 当前决策：不自动创建，返回提示让用户手动创建
- 风险：可能延迟响应
- 缓解：后续可配置自动创建规则

### Risk 2: 事件重复创建
同一灾害多次更新可能创建多个事件
- 缓解：检查linked_event_id，已关联则不重复创建

## Open Questions
1. 是否需要支持灾害升级（severity增加时重新评估）？
2. 是否需要支持灾害合并（相邻灾害合并为一个）？
3. 是否需要支持灾害过期（超时自动关闭）？
