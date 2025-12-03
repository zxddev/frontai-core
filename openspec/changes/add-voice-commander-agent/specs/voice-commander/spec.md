## ADDED Requirements

### Requirement: Semantic Intent Routing
系统 SHALL 在LLM调用前进行语义路由分类，将用户意图分发到对应Agent。

#### Scenario: 空间查询路由
- **WHEN** 用户说"Alpha队在哪里"
- **THEN** 系统在100ms内识别为spatial_query意图
- **AND** 请求被路由到SpatialAgent处理

#### Scenario: 控制指令路由
- **WHEN** 用户说"派无人机去B区"
- **THEN** 系统识别为robot_command意图（阈值≥0.85）
- **AND** 请求被路由到CommanderAgent处理

#### Scenario: 任务状态查询路由
- **WHEN** 用户说"当前救援进度怎么样"
- **THEN** 系统识别为mission_status意图
- **AND** 请求被路由到EmergencyAgent处理

#### Scenario: 降级处理
- **WHEN** 意图置信度低于所有路由阈值
- **THEN** 系统降级使用基础LLM处理

---

### Requirement: Spatial Query Capability
系统 SHALL 支持通过自然语言查询实体位置、距离和区域状态。

#### Scenario: 查询实体位置
- **WHEN** 用户问"一号无人机在哪里"
- **THEN** 系统查询PostGIS获取坐标
- **AND** 返回人类可读的位置描述（如"物资仓库东侧50米"）

#### Scenario: 查询最近单位
- **WHEN** 用户问"离着火点最近的救援队是谁"
- **THEN** 系统执行KNN空间查询
- **AND** 返回最近单位的名称、距离和状态

#### Scenario: 查询区域状态
- **WHEN** 用户问"B区搜救进度如何"
- **THEN** 系统查询区域内单位数量、搜索覆盖率、风险等级

#### Scenario: 实体名称模糊匹配
- **WHEN** 用户说"找一下旺财"（机器狗别名）
- **THEN** 系统通过模糊匹配找到对应实体
- **AND** 返回正确的位置信息

---

### Requirement: Robot Control with Human Confirmation
系统 SHALL 支持通过语音控制机器人，但所有写操作 MUST 经过人工确认。

#### Scenario: 派遣指令生成
- **WHEN** 用户说"派一号无人机去化工厂"
- **THEN** 系统生成待确认指令
- **AND** 执行安全检查（禁飞区、电量、冲突）
- **AND** 通过TTS播报确认请求

#### Scenario: 用户确认执行
- **WHEN** 系统播报"已准备指令...请确认执行"
- **AND** 用户回复"确认"或"执行"
- **THEN** 系统通过STOMP发送控制指令
- **AND** 回复"指令已发送"

#### Scenario: 用户取消执行
- **WHEN** 系统播报确认请求
- **AND** 用户回复"取消"或"不要"
- **THEN** 系统丢弃待确认指令
- **AND** 回复"指令已取消"

#### Scenario: 安全检查拦截-禁飞区
- **WHEN** 用户请求派遣无人机
- **AND** 目标位置在禁飞区内
- **THEN** 系统拒绝生成指令
- **AND** 回复"目标位置在禁飞区，无法执行"

#### Scenario: 安全检查拦截-电量不足
- **WHEN** 用户请求派遣无人机
- **AND** 无人机电量不足以完成往返
- **THEN** 系统拒绝生成指令
- **AND** 回复"无人机电量不足，无法执行该任务"

#### Scenario: 确认超时
- **WHEN** 系统播报确认请求
- **AND** 用户在30秒内未响应
- **THEN** 系统自动取消待确认指令
- **AND** 回复"确认超时，指令已取消"

---

### Requirement: Graceful Degradation
系统 SHALL 支持各能力的独立降级。

#### Scenario: 空间查询服务降级
- **WHEN** PostGIS服务不可用
- **THEN** 系统回复"空间查询服务暂时不可用"
- **AND** 基础对话功能正常

#### Scenario: 控制功能禁用
- **WHEN** 配置 robot_command_enabled=false
- **THEN** 控制类意图被路由到基础LLM
- **AND** LLM回复"机器人控制功能未启用"

#### Scenario: 语义路由降级
- **WHEN** embedding服务不可用
- **THEN** 系统降级使用全量LLM进行意图分类
- **AND** 记录降级日志

---

### Requirement: Command Traceability
系统 SHALL 记录所有控制指令的完整追溯信息。

#### Scenario: 指令追溯记录
- **WHEN** 用户确认执行控制指令
- **THEN** 系统记录以下信息：
  - 原始语音文本
  - 解析的意图和参数
  - 安全检查结果
  - 确认时间和方式
  - STOMP消息ID
  - 执行结果

#### Scenario: 取消指令记录
- **WHEN** 用户取消控制指令
- **THEN** 系统记录取消原因和时间
