# 战略层扩展需求规格

## ADDED Requirements

### Requirement: 任务域分类

系统 SHALL 根据匹配的规则自动分类任务域。

#### Scenario: 地震场景激活生命救护域
- **WHEN** 匹配到 TRR-EM-001 (地震人员搜救规则)
- **THEN** 系统 SHALL 激活 `life_rescue` 任务域
- **AND** 记录日志 `【任务域分类】激活域: life_rescue`

#### Scenario: 复合灾害激活多个任务域
- **WHEN** 匹配到地震+火灾+滑坡相关规则
- **THEN** 系统 SHALL 激活多个任务域 [life_rescue, engineering, hazard_control]
- **AND** 按优先级排序

### Requirement: 阶段优先级

系统 SHALL 根据灾害发生时间确定当前阶段，并应用相应的任务域优先级。

#### Scenario: 黄金救援期优先级
- **WHEN** 灾害发生后 2-24 小时
- **THEN** 系统 SHALL 设置 current_phase = "golden"
- **AND** 任务域优先级为: life_rescue(1) > evacuation(2) > engineering(3) > logistics(4)

#### Scenario: 恢复重建期优先级
- **WHEN** 灾害发生后 72+ 小时
- **THEN** 系统 SHALL 设置 current_phase = "recovery"
- **AND** 任务域优先级为: logistics(1) > engineering(2) > hazard_control(3) > life_rescue(4)

### Requirement: 预编组模块装配

系统 SHALL 根据所需能力推荐预编组模块。

#### Scenario: 推荐废墟搜救模块
- **WHEN** 需要能力包含 LIFE_DETECTION 和 HEAVY_LIFTING
- **THEN** 系统 SHALL 推荐 `ruins_search` 模块
- **AND** 返回模块配置 {personnel: 15, dogs: 4, equipment: [...]}

#### Scenario: 多模块组合
- **WHEN** 需要能力覆盖搜救+医疗
- **THEN** 系统 SHALL 推荐多个模块 [ruins_search, medical_forward]
- **AND** 按能力覆盖度排序

### Requirement: 运力瓶颈检查

系统 SHALL 检查投送能力是否满足需求。

#### Scenario: 直升机运力不足警告
- **WHEN** 需要投送 100 人到灾区
- **AND** 可用直升机运力 = 60 人
- **THEN** 系统 SHALL 返回警告 "直升机运力缺口 40 人"
- **AND** 建议替代方案

#### Scenario: 道路中断警告
- **WHEN** 目标区域道路中断
- **THEN** 系统 SHALL 返回警告 "道路中断，需空中投送"

### Requirement: JSON条件安全规则

系统 SHALL 支持复杂 JSON 条件的安全规则检查。

#### Scenario: 硬规则阻止
- **WHEN** 方案包含 {disaster_type: "fire", has_gas_leak: true}
- **AND** 安全规则条件匹配
- **THEN** 系统 SHALL 阻止该方案
- **AND** 返回违规信息

#### Scenario: 软规则警告
- **WHEN** 方案触发软规则
- **THEN** 系统 SHALL 返回警告但不阻止
- **AND** 记录到 safety_violations

### Requirement: 报告自动生成

系统 SHALL 根据模板自动生成灾情报告。

#### Scenario: 生成初报
- **WHEN** 分析完成
- **THEN** 系统 SHALL 生成初报
- **AND** 填充模板变量 {disaster_type, affected_area, estimated_casualties, ...}

#### Scenario: 报告包含任务域信息
- **WHEN** 生成报告
- **THEN** 报告 SHALL 包含激活的任务域和优先级
- **AND** 包含推荐的模块列表
