## ADDED Requirements

### Requirement: Multi-Rescue-Point Input Support
系统 SHALL 支持在应急分析请求中提供多个救援点，每个救援点包含名称、位置（坐标或地名）、预估被困人数和优先级。

#### Scenario: 多救援点输入分析
- **GIVEN** 用户提交包含3个救援点的分析请求（A楼30人、B楼15人、C楼10人）
- **WHEN** 系统执行应急分析
- **THEN** 系统为每个救援点分别生成队伍分配方案
- **AND** 输出包含每个救援点的分配结果、ETA、task_description

#### Scenario: 无救援点输入时从数据库读取
- **GIVEN** 用户提交的分析请求未包含 `rescue_points` 字段
- **AND** 数据库 `rescue_points_v2` 表中存在该事件的救援点记录
- **WHEN** 系统执行应急分析
- **THEN** 系统自动从数据库读取救援点列表
- **AND** 为读取到的救援点生成分配方案

#### Scenario: 救援点数量超过上限
- **GIVEN** 用户提交包含60个救援点的分析请求
- **WHEN** 系统校验输入
- **THEN** 系统返回 HTTP 400 错误
- **AND** 错误信息为"救援点数量超过上限50个"

#### Scenario: 无任何救援点（向后兼容）
- **GIVEN** 用户提交的分析请求未包含 `rescue_points` 字段
- **AND** 数据库 `rescue_points_v2` 表中无该事件的救援点记录
- **WHEN** 系统执行应急分析
- **THEN** 系统使用事件位置作为单一救援点
- **AND** 行为与旧版本完全一致

### Requirement: Address Geocoding Support
系统 SHALL 支持通过地名输入救援点位置，并自动转换为经纬度坐标。

#### Scenario: 地名成功解析
- **GIVEN** 用户提交的救援点包含 `address: "茂县凤仪镇小学"`
- **WHEN** 系统调用高德地理编码API
- **THEN** 返回对应的经纬度坐标
- **AND** 使用解析后的坐标进行资源匹配

#### Scenario: 地名解析失败
- **GIVEN** 用户提交的救援点包含无法解析的地名 `address: "不存在的地方abc123"`
- **AND** 该救援点未提供 `location` 坐标
- **WHEN** 系统尝试调用高德地理编码API
- **THEN** 系统抛出 `GeocodingError` 异常
- **AND** 返回错误信息明确指出哪个地名无法解析
- **AND** 不使用任何降级策略

#### Scenario: 坐标优先于地名
- **GIVEN** 用户提交的救援点同时包含 `location` 坐标和 `address` 地名
- **WHEN** 系统解析救援点位置
- **THEN** 系统直接使用 `location` 坐标
- **AND** 不调用地理编码API

#### Scenario: 地理编码API超时
- **GIVEN** 用户提交的救援点包含地名 `address: "某地址"`
- **AND** 高德地理编码API响应超过10秒
- **WHEN** 系统等待API响应
- **THEN** 系统抛出 `GeocodingError` 异常
- **AND** 错误信息为"地理编码服务超时：某地址"
- **AND** 不使用任何降级策略

### Requirement: Multi-Point Resource Matching
系统 SHALL 为每个救援点独立计算候选队伍列表，并执行全局最优分配。

#### Scenario: 多点位独立候选计算
- **GIVEN** 事件有2个救援点：A点(103.82, 31.62)和B点(103.85, 31.67)
- **AND** 存在5支可用队伍
- **WHEN** 系统执行资源匹配
- **THEN** 为A点计算候选队伍列表（按距离和能力排序）
- **AND** 为B点计算候选队伍列表（按距离和能力排序）

#### Scenario: 队伍互斥分配
- **GIVEN** 搜救队1距离A点5km，距离B点3km
- **AND** A点和B点都需要搜救能力
- **WHEN** 系统执行全局优化分配
- **THEN** 搜救队1只被分配到一个救援点
- **AND** 分配结果考虑全局最优（如总响应时间最小）

#### Scenario: 资源不足处理
- **GIVEN** 事件有5个救援点需要搜救能力
- **AND** 只有3支搜救队可用
- **WHEN** 系统执行资源分配
- **THEN** 系统为3个救援点分配搜救队
- **AND** 返回 `unassigned_points` 列表（包含2个未分配的点）
- **AND** 返回 `resource_warnings` 警告信息

### Requirement: Per-Point Task Creation
系统 SHALL 在确认部署时为每个救援点创建独立的任务记录。

#### Scenario: 多任务创建
- **GIVEN** 分析结果包含3个救援点的分配方案
- **WHEN** 指挥员确认部署方案
- **THEN** 系统创建3条 `tasks_v2` 记录
- **AND** 每个任务的 `rescue_point_id` 关联对应的救援点
- **AND** 每个任务标题包含救援点名称和被困人数

#### Scenario: 任务分配使用AI描述
- **GIVEN** AI为A点分配了搜救队1，task_description为"负责建筑倒塌搜救(EM03)"
- **WHEN** 系统创建任务分配记录
- **THEN** `task_assignments_v2.assignment_reason` 设置为"负责建筑倒塌搜救(EM03)"
- **AND** 不使用默认的"AI智能推荐"

#### Scenario: 救援点队伍关联
- **GIVEN** A点被分配了搜救队1和医疗队1
- **WHEN** 系统创建任务分配
- **THEN** `rescue_point_team_assignments_v2` 表写入2条记录
- **AND** 关联A点ID和对应队伍ID

### Requirement: Scheme Record Creation
系统 SHALL 在确认部署时创建方案记录，支持后续审核和追溯。

#### Scenario: 方案记录创建
- **GIVEN** 指挥员确认部署分析结果
- **WHEN** 系统执行确认操作
- **THEN** 系统在 `schemes_v2` 表创建记录
- **AND** 记录包含完整的分配方案JSON
- **AND** `status` 设置为 `approved`
- **AND** `source` 设置为 `ai_generated`

## MODIFIED Requirements

### Requirement: Emergency Analyze Request Schema
系统 SHALL 接受应急分析请求，支持可选的救援点列表输入。

#### Scenario: 带救援点的分析请求
- **GIVEN** 用户提交分析请求
- **WHEN** 请求包含 `rescue_points` 数组
- **THEN** 系统使用输入的救援点列表进行分析

#### Scenario: 不带救援点的分析请求（向后兼容）
- **GIVEN** 用户提交分析请求
- **WHEN** 请求未包含 `rescue_points` 字段
- **THEN** 系统从数据库读取救援点
- **AND** 若数据库也无救援点，则使用事件位置作为单一救援点
