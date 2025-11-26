# Tasks: 第三方数据接入模块

## 1. 数据库准备

- [x] 1.1 创建 `api_keys_v2` 表 SQL（提供SQL给用户执行）
- [x] 1.2 确认 `weather_conditions_v2` 表已存在

## 2. API密钥认证

- [x] 2.1 创建 `src/domains/integrations/dependencies.py` - API密钥认证依赖
- [x] 2.2 创建 `ApiKey` ORM模型
- [x] 2.3 实现密钥验证逻辑（查表验证 + 缓存）

## 3. 核心模块结构

- [x] 3.1 创建 `src/domains/integrations/__init__.py`
- [x] 3.2 创建 `src/domains/integrations/schemas.py` - 请求响应模型
- [x] 3.3 创建 `src/domains/integrations/deduplication.py` - 去重策略
- [x] 3.4 创建 `src/domains/integrations/service.py` - 业务逻辑
- [x] 3.5 创建 `src/domains/integrations/router.py` - 路由定义

## 4. 灾情上报接口

- [x] 4.1 实现 `POST /integrations/disaster-report` schema
- [x] 4.2 实现灾情去重逻辑（来源去重 + 时空去重）
- [x] 4.3 集成 `EventService.create()` 创建事件
- [x] 4.4 WebSocket推送事件创建通知
- [x] 4.5 日志记录关键节点

## 5. 传感器告警接口

- [x] 5.1 实现 `POST /integrations/sensor-alert` schema
- [x] 5.2 传感器告警转事件逻辑
- [x] 5.3 告警级别映射事件优先级

## 6. 设备遥测接口

- [x] 6.1 实现 `POST /integrations/telemetry` schema（批量）
- [x] 6.2 批量更新 `entities_v2` 位置
- [x] 6.3 批量写入 `entity_tracks_v2` 轨迹（update_location自动记录）
- [x] 6.4 触发 WebSocket telemetry 频道推送（broadcast_telemetry_batch）
- [x] 6.5 实现 `POST /devices/{id}/telemetry` 单设备接口（已存在）

## 7. 天气数据接口

- [x] 7.1 实现 `POST /integrations/weather` schema
- [x] 7.2 创建 `WeatherCondition` ORM模型（weather_models.py）
- [x] 7.3 天气数据入库（weather_repository.py）
- [ ] 7.4 天气预警转系统告警（TODO，需事件服务集成）

## 8. 位置更新接口

- [x] 8.1 修改 `vehicles/router.py` 增加 `PATCH /{id}/location`（已存在）
- [x] 8.2 修改 `vehicles/service.py` 实现位置更新逻辑（已存在）
- [x] 8.3 修改 `teams/router.py` 增加 `PATCH /{id}/location`（已存在）
- [x] 8.4 修改 `teams/service.py` 实现位置更新逻辑（已存在）
- [ ] 8.5 位置更新同步到 `entities_v2` 表（需集成）

## 9. 路由注册

- [x] 9.1 更新 `src/main.py` 注册 integrations 路由
- [x] 9.2 路由前缀配置为 `/api/v2/integrations`

## 10. 测试验证

- [x] 10.1 语法检查：所有文件编译通过
- [ ] 10.2 集成测试：灾情上报端到端（需数据库）
- [ ] 10.3 集成测试：遥测数据批量处理（需数据库）
- [ ] 10.4 类型检查：mypy 验证强类型（需配置mypy）

## 依赖关系

```
1.数据库准备 → 2.API密钥认证 → 3.核心模块 → 4-8.各接口实现（可并行） → 9.路由注册 → 10.测试
```
