# Change: 增强灾害-想定-事件关联机制

## Why
当前预警监测智能体的灾害(Disaster)记录与想定(Scenario)、事件(Event)体系是割裂的：
1. 灾害记录没有关联到想定，无法纳入统一指挥框架
2. 第三方推送的灾害数据没有自动创建事件，无法触发救援流程
3. 灾害边界没有在地图上渲染，指挥员无法直观感知危险区域
4. 灾害创建时没有WebSocket推送，前端无法实时感知

## What Changes
- **MODIFIED** disaster_situations表：增加scenario_id、needs_response等字段
- **MODIFIED** /disasters/update接口：
  - 支持关联想定（自动查找或创建）
  - 支持按需创建事件（触发救援流程）
  - 创建map_entity（danger_zone类型）渲染地图
  - WebSocket推送灾害通知到前端
- **ADDED** 灾害分类机制：区分"需响应灾害"和"仅预警灾害"

## Impact
- Affected specs: early-warning
- Affected code:
  - `src/agents/early_warning/router.py` - 增强update_disaster逻辑
  - `src/agents/early_warning/models.py` - 增加字段
  - `src/agents/early_warning/schemas.py` - 增加请求/响应字段
  - `src/domains/map_entities/` - 调用创建danger_zone实体
  - `src/domains/events/` - 调用创建事件
  - `src/domains/frontend_api/websocket/` - 调用推送通知

## Design Decisions
- **灾害→想定关联**：优先使用请求中的scenario_id，其次按位置查找进行中的想定，最后根据严重程度决定是否创建新想定
- **灾害→事件触发**：severity_level>=3 且 needs_response=true 时自动创建事件
- **地图渲染**：创建danger_zone类型的map_entity，前端订阅实体变更自动渲染
- **通知机制**：WebSocket推送到/topic/scenario.disaster.triggered
