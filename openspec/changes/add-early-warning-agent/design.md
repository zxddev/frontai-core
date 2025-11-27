## Context
应急救援场景下，灾害范围会动态变化（火灾蔓延、洪水上涨等）。系统需要实时监测这些变化，并在车辆/队伍可能受影响时主动预警。

关键约束：
- 预警系统必须是"辅助决策"而非"自动决策"
- 路径变更必须由人工确认
- 通知仅推送到前端

## Goals / Non-Goals

**Goals:**
- 实时检测灾害范围变化对车辆/队伍的影响
- 计算预计接触危险区域的时间
- 检测规划路径是否穿过危险区域
- 通过WebSocket推送交互式预警消息
- 支持人工申请绕行并调用路径规划

**Non-Goals:**
- 不自动执行路径重规划
- 不发送短信/车载终端通知（仅前端）
- 不做预警审批流程

## Decisions

### 1. 智能体运行模式
**决策**: 事件驱动 + API触发模式

- 第三方灾情接口调用时触发检测
- 提供API供前端轮询或定时检测

**理由**: 简化实现，避免后台daemon复杂性，与现有Agent模式保持一致

### 2. 预警触发条件
**决策**: 3km距离阈值 + 路径穿越检测

```
预警触发 = (当前位置距灾害边界 < 3km) OR (规划路径与灾害范围相交)
```

**理由**: 3km是默认值，留出足够反应时间，可配置

### 3. 通知对象确定
**决策**: 
- 对内车辆 → 通知指挥员（通过scenario_id关联）
- 救援队伍车辆 → 通知该队伍负责人（通过team.contact_person）

**理由**: 无需审批流程，接收者即决策者

### 4. 与路径规划集成
**决策**: 被动调用模式

```
用户点击[申请绕行] 
  → 前端调用 POST /api/warnings/{id}/request-detour
  → 后端调用 RoutePlanningAgent（传入avoid_areas）
  → 返回备选路线
  → 用户选择确认
  → 更新任务路径
```

**理由**: 符合Human in the Loop原则，用户自主决策

## Architecture

```
┌─────────────────┐
│ 第三方灾情接口   │
└────────┬────────┘
         │ POST /api/disasters/update
         ▼
┌─────────────────────────────────────────────┐
│           EarlyWarningAgent                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │ ingest  │→│ analyze │→│ decide  │      │
│  └─────────┘  └─────────┘  └─────────┘     │
│                                ↓            │
│            ┌─────────┐  ┌─────────┐        │
│            │ notify  │←│generate │         │
│            └────┬────┘  └─────────┘        │
└─────────────────┼───────────────────────────┘
                  │ broadcast_alert()
                  ▼
┌─────────────────────────────────────────────┐
│         WebSocket (alerts频道)              │
└─────────────────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
 指挥大屏      指挥员终端    队伍负责人终端
```

## Data Model

### 灾害态势表 (新增)
```sql
CREATE TABLE operational_v2.disaster_situations (
    id UUID PRIMARY KEY,
    scenario_id UUID REFERENCES scenarios(id),
    disaster_type VARCHAR(50),          -- fire/flood/chemical/...
    boundary GEOMETRY(POLYGON, 4326),   -- 灾害范围多边形
    buffer_distance_m INT DEFAULT 3000, -- 预警缓冲距离
    spread_direction VARCHAR(20),       -- 扩散方向
    spread_speed_mps DECIMAL,           -- 扩散速度 m/s
    severity_level INT,                 -- 严重程度 1-5
    source VARCHAR(100),                -- 数据来源
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 预警记录表 (新增)
```sql
CREATE TABLE operational_v2.warning_records (
    id UUID PRIMARY KEY,
    disaster_id UUID REFERENCES disaster_situations(id),
    affected_type VARCHAR(20),          -- vehicle/team
    affected_id UUID,                   -- 车辆/队伍ID
    notify_target_type VARCHAR(20),     -- commander/team_leader
    notify_target_id UUID,              -- 通知目标用户ID
    warning_level VARCHAR(10),          -- blue/yellow/orange/red
    distance_m DECIMAL,                 -- 距离危险区域距离
    estimated_contact_minutes INT,      -- 预计接触时间
    route_affected BOOLEAN,             -- 路径是否受影响
    status VARCHAR(20),                 -- pending/acknowledged/detour_requested/resolved
    response_action VARCHAR(20),        -- continue/detour/standby
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP
);
```

## API Design

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/disasters/update` | POST | 接收第三方灾情数据，触发预警检测 |
| `/api/warnings` | GET | 查询预警列表 |
| `/api/warnings/{id}` | GET | 查询预警详情 |
| `/api/warnings/{id}/acknowledge` | POST | 确认收到预警 |
| `/api/warnings/{id}/respond` | POST | 提交响应（continue/detour/standby） |
| `/api/warnings/{id}/detour-options` | GET | 获取绕行备选路线 |
| `/api/warnings/{id}/confirm-detour` | POST | 确认选择的绕行路线 |

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 位置数据不及时 | 依赖现有GPS上报机制，文档说明数据时效性 |
| 预警消息丢失 | WebSocket有消息历史回放机制（已实现） |
| 计算延迟 | 使用空间索引优化范围查询 |

## Open Questions
- [ ] 第三方灾情接口的具体数据格式？（需对接方提供）
- [ ] 是否需要支持灾害范围预测（T+N分钟）？（v2考虑）
