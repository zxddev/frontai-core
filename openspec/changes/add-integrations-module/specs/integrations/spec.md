# Capability: Third-Party Integrations

第三方系统数据接入能力，接收外部系统推送的灾情、告警、遥测、天气数据。

## ADDED Requirements

### Requirement: API密钥认证

系统 SHALL 使用API密钥认证第三方系统接入。系统 MUST 通过 `X-Api-Key` Header验证请求来源，并记录 `X-Source-System` 来源标识。

#### Scenario: 有效API密钥访问

- **WHEN** 请求携带有效的 `X-Api-Key` Header
- **AND** 密钥状态为启用且未过期
- **THEN** 请求通过认证
- **AND** 记录请求来源系统

#### Scenario: 无效API密钥拒绝

- **WHEN** 请求携带无效或过期的 `X-Api-Key`
- **THEN** 返回401 Unauthorized
- **AND** 返回错误码 `UNAUTHORIZED`

#### Scenario: 缺少API密钥

- **WHEN** 请求未携带 `X-Api-Key` Header
- **THEN** 返回401 Unauthorized
- **AND** 返回错误码 `MISSING_API_KEY`

---

### Requirement: 灾情上报

系统 SHALL 接收第三方系统推送的灾情信息。系统 MUST 自动创建事件并触发处理流程。

#### Scenario: 新灾情上报成功

- **WHEN** 第三方系统POST灾情数据到 `/integrations/disaster-report`
- **AND** 数据格式正确且通过认证
- **AND** 不存在重复灾情
- **THEN** 创建新事件（状态为pending）
- **AND** 创建对应地图实体
- **AND** 返回201 Created
- **AND** 返回事件ID和事件编码
- **AND** 通过WebSocket推送事件创建通知

#### Scenario: 灾情来源去重

- **WHEN** 第三方系统上报灾情
- **AND** 相同 `source_system + source_event_id` 已存在
- **THEN** 返回200 OK
- **AND** 返回 `status: duplicate`
- **AND** 返回已存在事件的ID
- **AND** 将新信息追加到现有事件的更新记录

#### Scenario: 灾情时空去重

- **WHEN** 第三方系统上报灾情
- **AND** 100米范围内1小时内存在相同类型灾情
- **THEN** 返回200 OK
- **AND** 返回 `status: duplicate`
- **AND** 合并到邻近事件

#### Scenario: 灾情数据校验失败

- **WHEN** 灾情数据缺少必填字段或格式错误
- **THEN** 返回400 Bad Request
- **AND** 返回具体的校验错误信息

---

### Requirement: 传感器告警

系统 SHALL 接收IoT传感器的告警数据。系统 MUST 自动将warning/critical级别告警转换为事件。

#### Scenario: 传感器告警创建事件

- **WHEN** 传感器POST告警数据到 `/integrations/sensor-alert`
- **AND** 告警级别为warning或critical
- **THEN** 创建新事件
- **AND** 事件来源类型为 `sensor_alert`
- **AND** 事件优先级根据告警级别映射

#### Scenario: 信息级告警不创建事件

- **WHEN** 传感器告警级别为 `info`
- **THEN** 仅记录日志
- **AND** 不创建事件
- **AND** 返回200 OK 和 `action_taken: logged`

---

### Requirement: 设备遥测数据

系统 SHALL 接收无人设备的实时遥测数据。系统 MUST 更新设备位置并记录轨迹历史。

#### Scenario: 单条遥测数据处理

- **WHEN** POST单条遥测数据到 `/integrations/telemetry`
- **AND** `device_id` 存在于系统中
- **THEN** 更新设备对应实体的位置
- **AND** 写入轨迹记录
- **AND** 通过WebSocket telemetry频道推送

#### Scenario: 批量遥测数据处理

- **WHEN** POST包含多条遥测数据的batch请求
- **THEN** 批量更新所有设备位置
- **AND** 返回处理成功和失败的数量
- **AND** 失败项包含具体原因

#### Scenario: 未知设备遥测

- **WHEN** 遥测数据的 `device_id` 不存在
- **THEN** 记录警告日志
- **AND** 在响应中标记为未处理

---

### Requirement: 天气数据

系统 SHALL 接收气象部门推送的天气数据和预警信息。系统 MUST 评估无人机飞行条件并存储天气记录。

#### Scenario: 天气数据入库

- **WHEN** POST天气数据到 `/integrations/weather`
- **AND** 数据格式正确
- **THEN** 更新或插入天气记录
- **AND** 返回无人机可飞行评估结果

#### Scenario: 天气预警触发告警

- **WHEN** 天气数据包含橙色或红色预警
- **THEN** 创建系统告警
- **AND** 通过WebSocket alerts频道推送

---

### Requirement: 车辆位置更新

系统 SHALL 提供车辆位置更新接口。系统 MUST 同步更新对应地图实体位置并记录轨迹。

#### Scenario: 车辆位置更新成功

- **WHEN** PATCH请求到 `/vehicles/{id}/location`
- **AND** 车辆存在且位置数据有效
- **THEN** 更新车辆位置
- **AND** 同步更新对应地图实体位置
- **AND** 记录轨迹点

---

### Requirement: 队伍位置更新

系统 SHALL 提供队伍位置更新接口。系统 MUST 同步更新对应地图实体位置并记录轨迹。

#### Scenario: 队伍位置更新成功

- **WHEN** PATCH请求到 `/teams/{id}/location`
- **AND** 队伍存在且位置数据有效
- **THEN** 更新队伍位置
- **AND** 同步更新对应地图实体位置
- **AND** 记录轨迹点

---

### Requirement: 设备单独遥测接口

系统 SHALL 提供单设备遥测上报接口 `/devices/{id}/telemetry`。系统 MUST 更新设备位置、电量、状态等信息。

#### Scenario: 单设备遥测上报

- **WHEN** POST请求到 `/devices/{id}/telemetry`
- **AND** 设备存在且数据格式正确
- **THEN** 更新设备位置、电量、状态等信息
- **AND** 记录遥测历史
- **AND** 通过WebSocket推送更新
