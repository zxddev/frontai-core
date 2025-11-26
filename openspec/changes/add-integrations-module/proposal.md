# Change: 添加第三方数据接入模块 (integrations)

## Why

当前系统缺少第三方系统接入能力，无法接收外部系统（110报警系统、IoT传感器、无人设备、气象系统）推送的灾情数据、告警信息和遥测数据。根据 `docs/emergency-brain/03_third_party_api.md` 设计文档和开发计划，第三方接入是P0阶段核心功能。

## What Changes

- **ADDED**: 第三方数据接入模块 (`src/domains/integrations/`)
  - `POST /api/v2/integrations/disaster-report` - 灾情上报
  - `POST /api/v2/integrations/sensor-alert` - 传感器告警
  - `POST /api/v2/integrations/telemetry` - 设备遥测（批量）
  - `POST /api/v2/integrations/weather` - 天气数据

- **ADDED**: API密钥认证机制
  - `X-Api-Key` Header认证
  - `X-Source-System` 来源系统标识
  - 可选HMAC-SHA256签名验证

- **ADDED**: 数据去重策略
  - 来源去重（source_system + source_event_id）
  - 位置时间去重（100米内 + 1小时内 + 相同类型）

- **MODIFIED**: 设备模块增加遥测接口
  - `POST /api/v2/devices/{id}/telemetry` - 单设备遥测

- **MODIFIED**: 车辆/队伍模块增加位置更新接口
  - `PATCH /api/v2/vehicles/{id}/location` - 车辆位置更新
  - `PATCH /api/v2/teams/{id}/location` - 队伍位置更新

## Impact

- **Affected specs**: 新增 `integrations` capability
- **Affected code**:
  - 新增 `src/domains/integrations/` 模块
  - 修改 `src/domains/resources/vehicles/` 增加位置接口
  - 修改 `src/domains/resources/teams/` 增加位置接口
  - 修改 `src/domains/resources/devices/` 增加遥测接口
  - 更新 `src/main.py` 注册路由
  - 更新 `src/core/dependencies.py` 增加API密钥认证

## SQL Tables

基于现有SQL定义，无需新建表：
- `events_v2` - 灾情上报写入（source_type='external_system'）
- `event_updates_v2` - 记录上报合并
- `entities_v2` - 地图实体位置更新
- `entity_tracks_v2` - 轨迹记录（遥测数据写入）
- `weather_conditions_v2` - 天气数据（v2_environment_model.sql已定义）

需要新增：
- `api_keys_v2` - API密钥管理表

## Dependencies

- 复用现有 `EventService` 处理灾情上报
- 复用现有 `EntityService` 更新位置
- 依赖 `websocket` 模块推送实时数据
