# Staging Area Planning Specification

## ADDED Requirements

### Requirement: Rescue Staging Site Recommendation
系统 SHALL 提供救援队驻扎点推荐功能，根据地震参数、救援目标和约束条件，返回评分排序的候选驻扎点列表。

#### Scenario: 成功推荐驻扎点
- **GIVEN** 已配置候选驻扎点数据
- **WHEN** 调用推荐API，提供震中位置、震级、救援目标和队伍信息
- **THEN** 返回按总分排序的候选驻扎点列表
- **AND** 每个候选点包含5维评分（响应时间、安全性、后勤、设施、通信）
- **AND** 每个候选点包含到救援目标的路径信息

#### Scenario: 无可用候选点
- **GIVEN** 所有候选点都在危险区域内或不可达
- **WHEN** 调用推荐API
- **THEN** 返回 success=false 和错误信息

### Requirement: Risk Zone Calculation
系统 SHALL 计算综合风险区域，合并烈度影响区、次生灾害区和已标记危险区。

#### Scenario: 计算地震风险区域
- **GIVEN** 震中位置和震级
- **WHEN** 执行风险区域计算
- **THEN** 基于烈度衰减模型计算影响半径
- **AND** 红区（烈度>=8）标记为禁止驻扎
- **AND** 橙区（烈度6-8）标记为高风险

#### Scenario: 合并已有危险区
- **GIVEN** disaster_affected_areas_v2 中存在危险区域
- **WHEN** 执行风险区域计算
- **THEN** 将已有危险区域与计算区域合并

### Requirement: Candidate Site Filtering
系统 SHALL 使用PostGIS空间查询筛选候选驻扎点，排除不满足硬约束的点位。

#### Scenario: 排除风险区内的候选点
- **WHEN** 搜索候选点
- **THEN** 排除位于风险区域内的点位
- **AND** 排除距风险区边界小于缓冲距离的点位

#### Scenario: 检查通信覆盖
- **WHEN** 搜索候选点
- **THEN** 仅返回有通信网络覆盖的点位

#### Scenario: 检查坡度约束
- **WHEN** 搜索候选点且设置了max_slope_deg
- **THEN** 排除坡度超过限制的点位

### Requirement: Route Feasibility Validation
系统 SHALL 验证候选点的路径可行性，使用DatabaseRouteEngine计算实际路径。

#### Scenario: 验证驻地到候选点路径
- **GIVEN** 队伍驻地位置和候选点
- **WHEN** 验证路径可行性
- **THEN** 使用A*算法规划路径
- **AND** 考虑灾害区域避障
- **AND** 返回路径距离和行驶时间

#### Scenario: 验证候选点到救援目标路径
- **GIVEN** 候选点和多个救援目标
- **WHEN** 验证路径可行性
- **THEN** 批量规划到各目标的路径
- **AND** 过滤无法到达任何目标的候选点

### Requirement: Multi-Objective Evaluation
系统 SHALL 对候选点进行多目标加权评估，计算综合评分。

#### Scenario: 计算响应时间得分
- **GIVEN** 候选点到各救援目标的路径时间和目标优先级
- **WHEN** 计算响应时间得分
- **THEN** 按优先级加权计算平均响应时间
- **AND** 归一化为0-1得分（时间越短分数越高）

#### Scenario: 计算安全性得分
- **GIVEN** 候选点距各风险区域的距离
- **WHEN** 计算安全性得分
- **THEN** 基于最小距离和安全阈值计算得分
- **AND** 距离越远分数越高

#### Scenario: 计算综合评分
- **GIVEN** 5维评分和权重配置
- **WHEN** 计算综合评分
- **THEN** total = 0.35*response + 0.25*safety + 0.20*logistics + 0.10*facility + 0.10*communication

### Requirement: Staging Site Data Model
系统 SHALL 提供 rescue_staging_sites_v2 表存储候选驻扎点数据。

#### Scenario: 存储驻扎点基本信息
- **WHEN** 创建驻扎点记录
- **THEN** 包含：编号、名称、类型、位置、面积

#### Scenario: 存储地形条件
- **WHEN** 创建驻扎点记录
- **THEN** 包含：坡度、地形类型、地质稳定性

#### Scenario: 存储设施条件
- **WHEN** 创建驻扎点记录
- **THEN** 包含：水电供应、通信类型、直升机起降条件

### Requirement: Staging Area Recommendation API
系统 SHALL 提供 POST /api/v1/staging-area/recommend API端点。

#### Scenario: 成功调用API
- **WHEN** POST /api/v1/staging-area/recommend with valid request body
- **THEN** HTTP 200
- **AND** 返回 StagingRecommendationResponse

#### Scenario: 请求参数无效
- **WHEN** POST /api/v1/staging-area/recommend with invalid request body
- **THEN** HTTP 422 Validation Error
