# Spec: 救援流程模块功能完善

## Overview

完善rescue-workflow模块的9个非AI功能，使其从占位实现变为完整的业务逻辑。

---

## ADDED Requirements

### Requirement: 安全点查询

系统 SHALL 提供安全点查询功能，返回场景内的所有安全点实体，包括resettle_point和safety_area类型。

#### Scenario: 查询事件关联的安全点
```gherkin
Given 场景ID "scenario-001" 下存在3个安全点实体
  And 安全点类型包括 "resettle_point" 和 "safety_area"
When 调用 GET /rescue-workflow/navigation/{event_id}/safe-points
Then 返回3个SafePoint对象
  And 每个对象包含 point_id, name, location, point_type
```

#### Scenario: 无安全点时返回空列表
```gherkin
Given 场景ID "scenario-002" 下没有安全点实体
When 调用 GET /rescue-workflow/navigation/{event_id}/safe-points
Then 返回空列表 []
```

---

### Requirement: 协同总览位置查询

协同总览接口 SHALL 包含队伍和车辆的实时位置信息，通过task关联查询deployed状态的资源。

#### Scenario: 获取包含位置的协同总览
```gherkin
Given 事件 "event-001" 关联2个任务
  And 任务分配了3个队伍和2辆车辆
  And 所有资源状态为 "deployed"
When 调用 GET /rescue-workflow/rescue/{event_id}/overview
Then 返回CoordinationTracking对象
  And team_locations 包含3个队伍位置
  And vehicle_locations 包含2个车辆位置
  And 每个位置包含 id, name, location, status
```

#### Scenario: 无部署资源时返回空位置列表
```gherkin
Given 事件 "event-002" 没有部署的队伍和车辆
When 调用 GET /rescue-workflow/rescue/{event_id}/overview
Then team_locations 为空列表
  And vehicle_locations 为空列表
```

---

### Requirement: 评估报告持久化

系统 SHALL 支持评估报告持久化存储到evaluation_reports_v2表并支持按事件ID查询。

#### Scenario: 查询已生成的评估报告
```gherkin
Given 事件 "event-001" 已生成评估报告
  And 报告存储在 evaluation_reports_v2 表
When 调用 GET /rescue-workflow/evaluation/{event_id}/report
Then 返回EvaluationReport对象
  And 包含 report_id, event_id, generated_at, summary, timeline
```

#### Scenario: 查询未生成报告时返回404
```gherkin
Given 事件 "event-003" 尚未生成评估报告
When 调用 GET /rescue-workflow/evaluation/{event_id}/report
Then 返回404 NotFoundError
  And 错误消息包含 "EvaluationReport"
```

---

### Requirement: 协同更新路由分发

协同更新接口 SHALL 根据entity_type分发到对应服务处理，MUST 支持team、vehicle、rescue_point三种类型。

#### Scenario: 更新队伍位置
```gherkin
Given 协同更新请求 entity_type="team", entity_id="team-001"
  And data 包含 location 信息
When 调用 POST /rescue-workflow/rescue/coordination
Then TeamService.update_location 被调用
  And WebSocket广播 "coordination_update" 消息
```

#### Scenario: 更新救援点状态
```gherkin
Given 协同更新请求 entity_type="rescue_point", entity_id="rp-001"
  And data 包含 status="completed", rescued_count=5
When 调用 POST /rescue-workflow/rescue/coordination
Then 救援点状态更新为 "completed"
  And rescued_count 更新为 5
```

---

### Requirement: 救援点检测确认自动创建

确认救援点检测时 SHALL 自动创建救援点记录（如果提供完整信息），MUST 关联detection_id。

#### Scenario: 确认检测并创建救援点
```gherkin
Given 救援点检测确认请求 is_confirmed=true
  And 请求包含 event_id, name, location, point_type
When 调用 POST /rescue-workflow/command/rescue-detections/confirm
Then 创建新的RescuePoint记录
  And detection_id 关联到该救援点
  And 返回包含 rescue_point_id 的响应
```

#### Scenario: 拒绝检测不创建救援点
```gherkin
Given 救援点检测确认请求 is_confirmed=false
When 调用 POST /rescue-workflow/command/rescue-detections/confirm
Then 不创建RescuePoint记录
  And 返回 confirmed=false
```

---

### Requirement: 无人机集群控制设备状态

无人机集群控制 SHALL 调用DeviceService批量更新设备状态，deploy MUST 映射到deployed，recall MUST 映射到available。

#### Scenario: 部署无人机集群
```gherkin
Given 无人机集群控制请求 command_type="deploy"
  And uav_ids 包含3个设备ID
When 调用 POST /rescue-workflow/command/uav-cluster
Then 3个设备状态更新为 "deployed"
  And 返回 status="executing", uav_count=3
```

#### Scenario: 召回无人机集群
```gherkin
Given 无人机集群控制请求 command_type="recall"
  And uav_ids 包含2个设备ID
When 调用 POST /rescue-workflow/command/uav-cluster
Then 2个设备状态更新为 "available"
```

#### Scenario: 部分设备不存在时继续执行
```gherkin
Given 无人机集群控制请求包含1个不存在的设备ID
When 调用 POST /rescue-workflow/command/uav-cluster
Then 存在的设备状态正常更新
  And 记录警告日志
  And 不抛出异常
```

---

### Requirement: 准备任务scheme关联

准备任务 SHALL 关联到正确的方案，若不存在 MUST 自动创建"应急准备"类型的scheme。

#### Scenario: 创建准备任务时关联方案
```gherkin
Given 事件 "event-001" 在场景 "scenario-001" 下
  And 该场景尚未创建准备方案
When 调用 POST /rescue-workflow/incidents/{event_id}/preparation-tasks
Then 自动创建"应急准备"类型的scheme
  And 所有任务关联到该scheme_id
```

#### Scenario: 复用已存在的准备方案
```gherkin
Given 场景 "scenario-001" 已存在准备方案 "prep-scheme-001"
When 再次创建准备任务
Then 复用已存在的scheme_id
  And 不创建新的scheme
```

---

## MODIFIED Requirements

### Requirement: 数据库表创建

系统 SHALL 执行SQL脚本创建所需数据库表，MUST 包括rescue_points_v2和evaluation_reports_v2，MUST 支持幂等执行。

#### Scenario: 创建救援点相关表
```gherkin
Given 数据库中不存在 rescue_points_v2 表
When 执行 sql/v2_rescue_points.sql
Then 创建 rescue_points_v2 表
  And 创建 rescue_point_team_assignments_v2 表
  And 创建 rescue_point_progress_v2 表
  And 创建相关索引和触发器
```

#### Scenario: 幂等执行不报错
```gherkin
Given 数据库中已存在 rescue_points_v2 表
When 再次执行 sql/v2_rescue_points.sql
Then 不抛出错误
  And 表结构保持不变
```

---

## Cross-References

- Related to: `implement-rescue-workflow` (基础实现)
- Depends on: `events`, `tasks`, `teams`, `vehicles`, `map_entities`, `devices` 模块
