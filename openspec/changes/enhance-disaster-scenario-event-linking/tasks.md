# Tasks: 增强灾害-想定-事件关联机制

## 1. 数据模型修改
- [x] 1.1 修改 disaster_situations 表：添加 needs_response, linked_event_id, map_entity_id 字段
- [x] 1.2 更新 DisasterSituation ORM模型（models.py）
- [x] 1.3 更新 DisasterUpdateRequest schema，添加 needs_response 字段
- [x] 1.4 更新 DisasterUpdateResponse schema，添加 scenario_id, linked_event_id, map_entity_id, scenario_warning

## 2. 想定关联逻辑
- [x] 2.1 实现自动查找活动想定（使用 ScenarioRepository.get_active()）
- [x] 2.2 修改 update_disaster 接口：支持 scenario_id 参数（优先使用指定值）
- [x] 2.3 修改 update_disaster 接口：无指定时自动查找活动想定

## 3. 事件创建逻辑（待依赖表可用）
- [x] 3.1 设计事件创建条件：needs_response=true && severity>=3 && scenario_id存在
- [x] 3.2 定义灾害类型到事件类型的映射（DISASTER_TO_EVENT_TYPE）
- [ ] 3.3 实现事件创建（待events_v2表可用后启用）
- [ ] 3.4 记录 linked_event_id 到灾害记录（待启用）

## 4. 地图实体创建（待依赖表可用）
- [x] 4.1 设计danger_zone实体创建逻辑
- [ ] 4.2 实现地图实体创建（待layers_v2表可用后启用）
- [ ] 4.3 记录 map_entity_id 到灾害记录（待启用）
- [x] 4.4 WebSocket broadcast_entity_create 已存在

## 5. WebSocket推送
- [x] 5.1 修改 update_disaster 接口：调用 ws_manager.broadcast_disaster()
- [x] 5.2 确认 frontend_api/websocket 的 broadcast_disaster() 可用

## 6. 测试验证
- [x] 6.1 端到端测试：想定自动关联验证通过
- [x] 6.2 端到端测试：触发型灾害（needs_response=true）
- [x] 6.3 端到端测试：预警型灾害（needs_response=false）
- [ ] 6.4 验证前端WebSocket接收（需前端配合）

## 已知限制
- events_v2 和 layers_v2 表当前不存在，事件创建和地图实体创建功能已实现代码但暂时注释
- 当这些表可用后，取消注释router.py中相应代码即可启用
