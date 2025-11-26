# Rescue Workflow Specification

## ADDED Requirements

### Requirement: 事件通报接收
系统 SHALL 接收外部事件通报并创建事件记录。

#### Scenario: 成功接收事件通报
- **WHEN** 调用 POST `/rescue-workflow/incidents/receive` 传入有效通报数据
- **THEN** 创建事件记录到 events_v2 表
- **AND** 广播事件通知到 WebSocket
- **AND** 返回创建的事件ID和状态

---

### Requirement: 准备任务创建
系统 SHALL 支持批量创建出发前准备任务。

#### Scenario: 成功创建准备任务
- **WHEN** 调用 POST `/rescue-workflow/incidents/{event_id}/preparation-tasks` 传入任务列表
- **THEN** 为每个任务创建 tasks_v2 记录
- **AND** 关联到指定事件
- **AND** 返回创建的任务列表

---

### Requirement: 准备任务完成
系统 SHALL 支持提交准备任务完成状态。

#### Scenario: 成功提交准备完成
- **WHEN** 调用 POST `/rescue-workflow/incidents/preparation-tasks/{id}/complete` 传入完成详情
- **THEN** 更新任务状态为 completed
- **AND** 记录完成详情（装备、人员、燃油等）
- **AND** 返回任务状态和批次进度

#### Scenario: 任务不存在
- **WHEN** 调用完成接口但任务ID不存在
- **THEN** 返回 404 NotFound 错误

---

### Requirement: 出发指令下发
系统 SHALL 支持下发出发指令并更新资源状态。

#### Scenario: 成功下发出发指令
- **WHEN** 调用 POST `/rescue-workflow/incidents/depart-command` 传入出发指令
- **THEN** 更新指定队伍状态为 deployed
- **AND** 更新指定车辆状态为 deployed
- **AND** 广播出发指令到 WebSocket
- **AND** 返回指令ID和通知数量

---

### Requirement: 路径切换
系统 SHALL 支持途中切换到备选路径。

#### Scenario: 成功切换路径
- **WHEN** 调用 POST `/rescue-workflow/navigation/route/{route_id}/switch` 指定备选路径索引
- **THEN** 更新当前活动路径
- **AND** 返回切换后的路径信息

---

### Requirement: 安全点查询
系统 SHALL 支持查询沿途安全点。

#### Scenario: 成功获取安全点
- **WHEN** 调用 GET `/rescue-workflow/navigation/{event_id}/safe-points` 传入路径ID
- **THEN** 返回路径沿途的安全点列表
- **AND** 包含设施信息和距离

---

### Requirement: 安全点确认
系统 SHALL 支持确认到达安全点。

#### Scenario: 成功确认安全点
- **WHEN** 调用 POST `/rescue-workflow/navigation/safe-points/confirm` 传入确认信息
- **THEN** 记录车辆到达时间
- **AND** 返回确认状态

---

### Requirement: 指挥所确认
系统 SHALL 支持确认并创建现场指挥所。

#### Scenario: 成功确认指挥所
- **WHEN** 调用 POST `/rescue-workflow/command/post/confirm` 传入指挥所信息
- **THEN** 创建指挥所地图实体
- **AND** 广播指挥所建立通知
- **AND** 返回指挥所ID和位置

---

### Requirement: 无人机集群控制
系统 SHALL 支持无人机集群控制指令。

#### Scenario: 成功发送集群控制指令
- **WHEN** 调用 POST `/rescue-workflow/command/uav-cluster` 传入控制指令
- **THEN** 更新目标设备状态
- **AND** 返回指令执行状态

---

### Requirement: 救援点检测确认
系统 SHALL 支持确认AI检测的救援点。

#### Scenario: 确认救援点
- **WHEN** 调用 POST `/rescue-workflow/command/rescue-detections/confirm` 传入确认信息
- **THEN** 如果确认，创建救援点记录
- **AND** 返回确认结果

#### Scenario: 否定救援点
- **WHEN** 调用确认接口但 is_confirmed=false
- **THEN** 不创建救援点记录
- **AND** 返回否定结果

---

### Requirement: 救援点创建
系统 SHALL 支持手动创建救援点。

#### Scenario: 成功创建救援点
- **WHEN** 调用 POST `/rescue-workflow/rescue/points` 传入救援点信息
- **THEN** 创建 rescue_points_v2 记录
- **AND** 返回创建的救援点详情

---

### Requirement: 救援点更新
系统 SHALL 支持更新救援点状态和救援进度。

#### Scenario: 成功更新救援点
- **WHEN** 调用 PUT `/rescue-workflow/rescue/points/{point_id}` 传入更新信息
- **THEN** 更新救援点状态/救援人数
- **AND** 记录进度变更到 rescue_point_progress_v2
- **AND** 返回更新后的救援点

#### Scenario: 救援点不存在
- **WHEN** 调用更新接口但救援点ID不存在
- **THEN** 返回 404 NotFound 错误

---

### Requirement: 协同总览
系统 SHALL 支持获取救援协同总览图数据。

#### Scenario: 成功获取协同总览
- **WHEN** 调用 GET `/rescue-workflow/rescue/{event_id}/overview`
- **THEN** 返回事件关联的所有救援点
- **AND** 返回队伍当前位置
- **AND** 返回车辆当前位置
- **AND** 计算并返回总体救援进度

---

### Requirement: 协同状态更新
系统 SHALL 支持更新协同状态并广播。

#### Scenario: 成功更新协同状态
- **WHEN** 调用 POST `/rescue-workflow/rescue/coordination` 传入更新信息
- **THEN** 根据实体类型更新对应状态
- **AND** 广播协同更新到 WebSocket
- **AND** 返回更新ID

---

### Requirement: 评估报告查询
系统 SHALL 支持查询已生成的评估报告。

#### Scenario: 成功获取评估报告
- **WHEN** 调用 GET `/rescue-workflow/evaluation/{event_id}/report`
- **AND** 报告已生成
- **THEN** 返回完整评估报告

#### Scenario: 报告不存在
- **WHEN** 调用获取报告接口但报告未生成
- **THEN** 返回 404 NotFound 错误
