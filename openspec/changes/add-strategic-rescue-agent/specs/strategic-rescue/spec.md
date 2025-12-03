# Strategic Rescue Agent Specification

## ADDED Requirements

### Requirement: Four Strategic Task Domains
系统 SHALL 支持四大（扩展为五大）战略任务域：

1. **生命救护 (life_rescue)** - 最高优先级
   - 1.1 建筑物废墟下被困人员搜救
   - 1.2 滑坡埋压人员搜救
   - 1.3 火灾现场被困人员救出
   - 1.4 重伤员现场急救与后送
   - 1.5 洪水围困人员水上救援

2. **群众转移安置 (evacuation)**
   - 2.1 震区危险区域人员紧急避险转移
   - 2.2 滑坡威胁区整村转移
   - 2.3 火灾威胁区疏散
   - 2.4 台风前群众预防性转移

3. **工程抢险 (engineering)**
   - 3.1 开辟生命通道（道路抢通）
   - 3.2 山体滑坡二次滑坡防控
   - 3.3 堰塞湖应急处置
   - 3.4 台风后道路抢通与电力恢复
   - 3.5 危房拆除与排险

4. **后勤保障 (logistics)**
   - 4.1 物资精准投送
   - 4.2 通信、电力、供水快速恢复
   - 4.3 疫情与心理危机干预
   - 4.4 野战医院展开

5. **次生灾害防控 (hazard_control)**
   - 5.1 危化品泄漏源头堵漏
   - 5.2 危化品扩散区域群众疏散
   - 5.3 化工火灾处置

#### Scenario: Activate life rescue domain on earthquake
- **WHEN** 态势数据包含 has_building_collapse=true 和 has_trapped_persons=true
- **THEN** 系统 SHALL 激活生命救护域的子任务 "1.1 建筑物废墟下被困人员搜救"
- **AND** 返回该子任务的能力需求列表

#### Scenario: Activate multiple domains for composite disaster
- **WHEN** 态势数据包含地震+次生火灾+滑坡的复合特征
- **THEN** 系统 SHALL 同时激活生命救护域、工程抢险域
- **AND** 按当前阶段的优先级顺序排列任务

---

### Requirement: Graph-Based Task Resolution
系统 SHALL 从 Neo4j 查询任务配置，支持灾种→子任务→能力→模块的链式查询。

**关系名（避免与现有系统冲突）**：
- `ACTIVATES_SUBTASK` - 灾种激活子任务
- `REQUIRES_CAP` - 子任务需要能力
- `IMPLEMENTED_BY` - 子任务映射到战术层 MetaTask

#### Scenario: Query subtasks by disaster type
- **WHEN** 输入灾种 ["earthquake", "fire"]
- **THEN** 系统 SHALL 执行 Cypher 查询 `ACTIVATES_SUBTASK` 关系
- **AND** 返回按优先级排序的子任务列表

#### Scenario: Query phase priority from graph
- **WHEN** 当前阶段为 "golden"（黄金救援期）
- **THEN** 系统 SHALL 查询 `PRIORITY_ORDER` 关系
- **AND** 返回任务域优先级顺序 [life_rescue, evacuation, engineering, logistics]

#### Scenario: Query capabilities for subtask
- **WHEN** 查询子任务 "1.1" 的能力需求
- **THEN** 系统 SHALL 查询 `REQUIRES_CAP` 关系返回能力列表
- **AND** 包含 requirement_type 和 min_level 属性
- **AND** 能力编码使用大写格式（如 LIFE_DETECTION）

#### Scenario: Query modules for capabilities
- **WHEN** 查询能力 ["LIFE_DETECTION", "HEAVY_LIFTING"] 对应的模块
- **THEN** 系统 SHALL 查询 `PROVIDES` 关系返回模块列表
- **AND** 按覆盖能力数量排序

#### Scenario: Map subtask to metatask
- **WHEN** 查询子任务 "1.1" 对应的战术层任务
- **THEN** 系统 SHALL 查询 `IMPLEMENTED_BY` 关系
- **AND** 返回映射的 MetaTask 列表 [EM06, EM10, EM11]

---

### Requirement: Database-Driven Capability KPI
系统 SHALL 从 PostgreSQL config.capability_kpi 表查询能力的量化 KPI 指标。

KPI 指标包含：
- target_value: 目标值（如 90）
- target_unit: 单位（如 %、分钟）
- time_window: 时间窗口（如 "6小时内"）
- max_response_time_min: 最大响应时间

#### Scenario: Check capability coverage against KPI
- **WHEN** 能力 "life_detection" 实际覆盖率 85%
- **AND** KPI 目标为 target_value=90, target_unit='%'
- **THEN** 系统 SHALL 返回缺口警告
- **AND** 返回缺口详情 {"capability": "life_detection", "actual": 85, "target": 90, "gap": 5}

#### Scenario: Check response time KPI
- **WHEN** 能力 "medical_emergency" 预计响应时间 45 分钟
- **AND** KPI max_response_time_min=30
- **THEN** 系统 SHALL 返回响应时间超标警告

---

### Requirement: Disaster Phase State Machine
系统 SHALL 实现四阶段灾害响应状态机：

| 阶段 | 时间范围 | 优先级顺序 |
|------|---------|-----------|
| 初期响应 (initial) | 0-2 小时 | 1→3→2→4 |
| 黄金救援期 (golden) | 2-24 小时 | 1→2→3→4 |
| 攻坚作战期 (intensive) | 24-72 小时 | 1→4→5→3 |
| 恢复重建期 (recovery) | 72 小时+ | 4→5→3→1 |

#### Scenario: Phase transition by time
- **WHEN** 灾害发生后超过 2 小时
- **THEN** 系统 SHALL 自动从 initial 转换到 golden 阶段
- **AND** 调整任务域优先级顺序为 [1,2,3,4]

#### Scenario: Phase transition by situation
- **WHEN** 在恢复期发现新的被困人员（>10人）
- **THEN** 系统 SHALL 强制回退到 intensive 阶段
- **AND** 记录转换原因 "发现新被困人员，重新进入攻坚阶段"

#### Scenario: Get phase info
- **WHEN** 查询当前阶段信息
- **THEN** 系统 SHALL 返回阶段名称、时间范围、优先级顺序、关键链条

---

### Requirement: Pre-assembled Rescue Modules
系统 SHALL 支持预编组救援模块的查询和装配。

模块定义包含：
- personnel_count: 人员数量
- dog_count: 搜救犬数量
- equipment_list: 装备清单（从 config.rescue_module_equipment 查询）
- deployment_time_min: 部署时间
- sustained_hours: 持续作战时间
- provides_capabilities: 提供的能力列表

#### Scenario: Select modules for subtask
- **WHEN** 激活 "1.1 建筑物废墟下被困人员搜救" 子任务
- **THEN** 系统 SHALL 查询 RECOMMENDS 关系返回推荐模块
- **AND** 返回模块详情：ruins_search_module（15人+4犬+装备）

#### Scenario: Calculate module coverage
- **WHEN** 选择 [ruins_search_module, medical_forward_module] 后
- **THEN** 系统 SHALL 计算能力覆盖率
- **AND** 返回已覆盖能力和未覆盖能力列表

#### Scenario: Get module equipment list
- **WHEN** 查询 ruins_search_module 的装备清单
- **THEN** 系统 SHALL 从 config.rescue_module_equipment 表查询
- **AND** 返回装备列表含名称、数量、是否必需

---

### Requirement: JSON-Based Safety Rules
系统 SHALL 从 PostgreSQL config.safety_rules 表加载安全规则，解析 JSON 条件表达式。

支持的条件操作符：`==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `in`
支持的逻辑操作符：`AND`, `OR`, `NOT`

#### Scenario: Block on fire-gas rule violation
- **WHEN** 计划在火灾区域执行 OPEN_VALVE 操作且 valve_type 包含 "gas"
- **THEN** 系统 SHALL 匹配规则 HR001
- **AND** 阻止计划执行
- **AND** 返回 "【硬规则违反】火灾期间禁止开启燃气阀门"

#### Scenario: Block on electrical fire water rule
- **WHEN** 计划在带电区域使用水灭火
- **THEN** 系统 SHALL 匹配规则 HR002
- **AND** 返回 "【硬规则违反】带电区域禁止使用水灭火"
- **AND** 推荐 "先切断电源或使用干粉/CO2灭火剂"

#### Scenario: Block on hazmat protection rule
- **WHEN** 计划进入危化品区域但未配备防护装备
- **THEN** 系统 SHALL 匹配规则 HR003
- **AND** 返回 "【硬规则违反】进入危化品区域未配备防护装备"

#### Scenario: Warn on soft rule violation
- **WHEN** 计划的资源冗余率 < 20%
- **THEN** 系统 SHALL 匹配软规则 SR001
- **AND** 返回警告而非阻止
- **AND** 要求人工确认后才能执行

#### Scenario: Evaluate nested AND/OR condition
- **WHEN** 规则条件为 {"operator": "OR", "conditions": [...]}
- **THEN** 系统 SHALL 递归解析
- **AND** 任一子条件匹配即触发规则

---

### Requirement: Transport Capacity Calculation
系统 SHALL 从 PostgreSQL config.transport_capacity 表读取运力参数，计算投送瓶颈。

运力模式：air_drop, helicopter, highway, railway, waterway

#### Scenario: Calculate air transport capacity
- **WHEN** 查询空投运力
- **AND** 参数为 {aircraft_count: 2, payload_per_sortie_tons: 20, sortie_turnaround_hours: 4}
- **THEN** 系统 SHALL 计算每小时通过能力 = 2/4 * 20 = 10 吨/小时

#### Scenario: Calculate helicopter capacity with weather
- **WHEN** 查询直升机运力
- **AND** 当前风速 > 15 m/s 或有雷暴
- **THEN** 系统 SHALL 返回可用容量为 0
- **AND** 标记瓶颈因素 "天气条件不允许飞行"

#### Scenario: Calculate highway capacity with damage
- **WHEN** 查询公路运力
- **AND** 道路损毁率 50%
- **THEN** 系统 SHALL 将通过能力乘以 (1-0.5) 系数

#### Scenario: Detect transport bottleneck
- **WHEN** 所有可用通道的运力总和 < 需求
- **THEN** 系统 SHALL 返回运力瓶颈警告
- **AND** 提供替代方案建议

---

### Requirement: Multi-Disaster Support
系统 SHALL 支持以下复合灾种场景（通过 Neo4j 配置）：
- 地震 + 火灾 + 滑坡
- 洪涝 + 堰塞湖
- 危化品泄漏 + 爆炸
- 台风 + 内涝 + 基础设施损毁

#### Scenario: Handle earthquake composite disaster
- **WHEN** 输入灾种为 ["earthquake", "fire", "landslide"]
- **THEN** 系统 SHALL 查询这三个灾种触发的所有子任务
- **AND** 合并去重
- **AND** 按当前阶段优先级排序

#### Scenario: Handle flood with barrier lake
- **WHEN** 输入灾种为 ["flood", "barrier_lake"]
- **THEN** 系统 SHALL 激活工程抢险域的 "3.3 堰塞湖应急处置"
- **AND** 设置 KPI "24小时内开导流槽"

#### Scenario: Handle chemical hazmat
- **WHEN** 输入灾种为 ["hazmat_leak"]
- **THEN** 系统 SHALL 激活次生灾害防控域
- **AND** 激活子任务 5.1, 5.2

---

### Requirement: Command Structure
系统 SHALL 支持多级指挥关系链：
- 战略层（省级指挥部）
- 战役层（市级指挥部）
- 战术层（现场指挥所）
- 执行层（具体单位）

ExecutionOrder SHALL 包含：
- commander_id: 直接指挥官 ID
- commander_name: 指挥官姓名/职务
- subordinate_units: 下属单位列表
- command_chain: 完整指挥链

#### Scenario: Query command chain
- **WHEN** 查询执行单位 "rescue_team_001" 的指挥链
- **THEN** 系统 SHALL 返回 [tactical_cmd_001, operational_cmd_001, strategic_hq]

#### Scenario: Include commander in order
- **WHEN** 生成执行指令
- **THEN** 指令 SHALL 包含 commander_id 和 subordinate_units 字段
- **AND** 包含汇报对象和汇报频率

---

### Requirement: Report Generation
系统 SHALL 从 PostgreSQL config.report_templates 表加载模板，自动生成上报文档。

报告类型：
- initial: 初报（灾情发生后30分钟内）
- progress: 续报（每2小时）
- daily: 日报（每日18:00）
- completion: 结束报告

#### Scenario: Generate initial report
- **WHEN** 触发初报生成
- **THEN** 系统 SHALL 加载 TPL_INITIAL 模板
- **AND** 填充灾情概况、人员伤亡、财产损失、已采取措施
- **AND** 格式化输出

#### Scenario: Generate progress report
- **WHEN** 触发续报生成
- **THEN** 系统 SHALL 加载 TPL_PROGRESS 模板
- **AND** 包含最新态势、救援进展（搜救/转移/医疗）、力量部署、物资保障

#### Scenario: Generate daily report
- **WHEN** 触发日报生成
- **THEN** 系统 SHALL 加载 TPL_DAILY 模板
- **AND** 包含当日工作情况、累计数据、明日计划、存在问题、建议

---

### Requirement: Medical Advice Validation
系统 SHALL 验证 AI 生成的医疗建议是否符合急救指南。

验证项目：
- 药物剂量上限
- CPR 参数标准
- 禁忌症检查

#### Scenario: Validate epinephrine dosage
- **WHEN** AI 建议的肾上腺素剂量 >1mg
- **THEN** 系统 SHALL 标记医疗警告
- **AND** 返回 "剂量超标，参考 AHA 指南上限 1mg"

#### Scenario: Validate CPR compression rate
- **WHEN** CPR 按压频率 <100 或 >120 次/分
- **THEN** 系统 SHALL 标记参数异常
- **AND** 返回标准值范围 100-120 次/分

#### Scenario: Validate CPR compression depth
- **WHEN** CPR 按压深度 <5cm 或 >6cm
- **THEN** 系统 SHALL 标记参数异常

#### Scenario: Check contraindications
- **WHEN** 建议溶栓治疗
- **AND** 患者有近期手术史
- **THEN** 系统 SHALL 标记禁忌症警告
