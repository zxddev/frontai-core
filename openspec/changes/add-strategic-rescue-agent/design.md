## Context

战略级救灾智能体，对标军队"使命课题式指挥链条"框架，配置全部存数据库。

**开发阶段原则**：
- 先验证逻辑正确性
- 不做缓存/性能优化
- 不做兜底机制
- 后期统一优化

## Goals / Non-Goals

**Goals:**
- 配置 100% 数据库驱动
- 图谱支持灾种→任务→能力→模块链式查询
- 规则引擎支持 JSON 条件表达式
- 支持多灾种复合场景
- 四大任务域完整覆盖

**Non-Goals:**
- 分布式事务
- 实时传感器接入
- 配置管理 UI
- 缓存/性能优化（后期做）

## Decisions

### Decision 1: 配置存储分层

| 配置类型 | 存储位置 | 原因 |
|---------|---------|------|
| 灾种/任务/能力/模块关系 | Neo4j | 需要图遍历和关系推理 |
| KPI 指标 | PostgreSQL | 结构化数据，需事务 |
| 安全规则 | PostgreSQL | 需审计，支持复杂条件 |
| 运力参数 | PostgreSQL | 结构化，支持场景区分 |
| 报告模板 | PostgreSQL | 结构化，支持版本管理 |

### Decision 2: JSON 条件表达式

安全规则条件使用 JSON 格式：
```json
{
  "operator": "AND",
  "conditions": [
    {"field": "situation.has_active_fire", "op": "==", "value": true},
    {"field": "order.operation", "op": "==", "value": "OPEN_VALVE"},
    {"field": "order.valve_type", "op": "contains", "value": "gas"}
  ]
}
```

支持运算符: `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `in`, `AND`, `OR`, `NOT`

### Decision 3: 直接查询（无缓存）

开发阶段每次直接查数据库，不做缓存。后期优化时再加 Redis 缓存。

### Decision 4: 与现有系统关系（战略层/战术层分离）

**架构设计**：新建独立的 StrategicRescueAgent，与现有 EmergencyAI 并行运行，通过映射关系连接。

```
┌─────────────────────────────────────────────────────────────┐
│              StrategicRescueAgent（战略层）                  │
│  - 任务域分解（查 Neo4j: TaskDomain/SubTask）                │
│  - 阶段管理（查 Neo4j: DisasterPhase）                       │
│  - 模块装配（查 Neo4j: RescueModule）                        │
│  - 安全检查（查 PG: safety_rules）                           │
│  - 运力计算（查 PG: transport_capacity）                     │
│  - 报告生成（查 PG: report_templates）                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ IMPLEMENTED_BY 映射
                           ▼ 可选调用（细化资源匹配时）
┌─────────────────────────────────────────────────────────────┐
│                EmergencyAI（战术层）- 现有                    │
│  - HTN分解（Scene→TaskChain→MetaTask）                       │
│  - TRR规则匹配（TRRRule→TaskType→Capability）                │
│  - 资源匹配+优化                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ResourceSchedulingCore（执行层）
```

**职责分工**：
| 层级 | 决策内容 | 数据来源 |
|------|---------|---------|
| 战略层 | 激活哪些任务域、当前什么阶段、需要哪些模块、运力够不够 | 新建的 Neo4j 战略节点 + PG 配置表 |
| 战术层 | 具体派哪些队伍、走哪条路、带什么装备 | 现有的 TRRRule/MetaTask/Capability |

### Decision 5: Neo4j 关系名避免冲突

由于现有系统已使用 `TRIGGERS` 关系（TRRRule→TaskType），战略层使用不同关系名：

| 战略层关系（新建） | 战术层关系（现有） |
|------------------|------------------|
| `ACTIVATES_SUBTASK` | `TRIGGERS` |
| `REQUIRES_CAP` | `REQUIRES_CAPABILITY` |
| `IMPLEMENTED_BY` | 无（新建映射） |

### Decision 6: Capability 编码风格统一

与现有系统保持一致，统一使用**大写编码**：
```
现有: LIFE_DETECTION, MEDICAL_TRIAGE, FIRE_SUPPRESSION
战略层也用大写: LIFE_DETECTION（而非 life_detection）
```

## Data Flow

```
态势输入
    ↓
查询 Neo4j: 灾种 → 子任务 → 能力 → 模块
    ↓
查询 PG: KPI 指标
    ↓
查询 PG: 运力参数 → 计算瓶颈
    ↓
生成执行计划
    ↓
查询 PG: 安全规则 → 检查
    ↓
生成指令 + 报告
```

## Neo4j Schema 详细设计

### 节点类型

```cypher
// 灾种节点（战略层新建）
CREATE (d:DisasterType {
  code: "earthquake",
  name: "地震",
  severity_levels: ["low", "medium", "high", "extreme"]
})

// 子任务节点（战略层新建）
CREATE (st:SubTask {
  task_id: "1.1",
  name: "建筑物废墟下被困人员搜救",
  domain: "life_rescue",
  priority: 1,
  trigger_conditions: ["has_building_collapse", "has_trapped_persons"]
})

// 能力节点（复用现有，编码大写）
// 注意：复用现有 Capability 节点，不新建，编码统一大写
// 现有节点示例：(:Capability {code: 'LIFE_DETECTION', name: '生命探测'})

// 预编组模块节点（战略层新建）
CREATE (m:RescueModule {
  module_id: "ruins_search_module",
  name: "废墟搜救模块",
  personnel_count: 15,
  dog_count: 4,
  deployment_time_min: 30,
  sustained_hours: 72
})

// 阶段节点（战略层新建）
CREATE (p:DisasterPhase {
  phase_id: "golden",
  name: "黄金救援期",
  time_range_hours: [2, 24],
  focus: "全力搜救、大规模转移"
})

// 任务域节点（战略层新建）
CREATE (td:TaskDomain {
  domain_id: "life_rescue",
  name: "生命救护",
  description: "最高优先级，包含搜救、急救、后送"
})
```

### 关系类型（使用不同关系名避免与现有系统冲突）

```cypher
// 灾种激活子任务（用 ACTIVATES_SUBTASK 而非 TRIGGERS，避免与现有 TRRRule-TRIGGERS-TaskType 冲突）
CREATE (d)-[:ACTIVATES_SUBTASK {priority: 1}]->(st)

// 子任务需要能力（用 REQUIRES_CAP 而非 REQUIRES_CAPABILITY）
CREATE (st)-[:REQUIRES_CAP {
  requirement_type: "required",
  min_level: 0.7
}]->(c)

// 能力由模块提供
CREATE (c)<-[:PROVIDES]-(m)

// 子任务推荐模块
CREATE (st)-[:RECOMMENDS]->(m)

// 子任务属于任务域
CREATE (st)-[:BELONGS_TO]->(td)

// 阶段定义任务域优先级
CREATE (p)-[:PRIORITY_ORDER {rank: 1}]->(td)

// ========== 战略层→战术层映射关系 ==========
// SubTask 映射到现有 MetaTask（建立战略层与战术层的连接）
CREATE (st)-[:IMPLEMENTED_BY {coverage: "full"}]->(mt:MetaTask)
```

### SubTask → MetaTask 映射表

| SubTask | 名称 | MetaTask | 覆盖度 |
|---------|------|----------|--------|
| 1.1 | 建筑物废墟下被困人员搜救 | EM06+EM10+EM11 | full |
| 1.2 | 滑坡埋压人员搜救 | EM10 | partial |
| 1.3 | 火灾现场被困人员救出 | EM10+EM19 | full |
| 1.4 | 重伤员现场急救与后送 | EM14+EM15 | full |
| 1.5 | 洪水围困人员水上救援 | EM10 | partial |
| 2.1 | 震区紧急避险转移 | EM09 | full |
| 2.2 | 滑坡威胁区整村转移 | EM09 | full |
| 2.3 | 火灾威胁区疏散 | EM09 | full |
| 2.4 | 台风前群众预防性转移 | EM09 | full |
| 3.1 | 开辟生命通道 | EM16 | full |
| 3.2 | 山体滑坡二次滑坡防控 | EM23+EM24 | partial |
| 3.3 | 堰塞湖应急处置 | EM23 | partial |
| 3.4 | 台风后道路抢通与电力恢复 | EM16+EM18 | full |
| 3.5 | 危房拆除与排险 | EM24 | full |
| 4.1 | 物资精准投送 | EM28 | full |
| 4.2 | 通信、电力、供水快速恢复 | EM18+EM29 | full |
| 4.3 | 疫情与心理危机干预 | EM25 | partial |
| 4.4 | 野战医院展开 | EM25 | partial |
| 5.1 | 危化品泄漏源头堵漏 | EM20+EM21 | full |
| 5.2 | 危化品扩散区域群众疏散 | EM09+EM22 | full |
| 5.3 | 化工火灾处置 | EM19+EM20 | full |

### 完整节点关系图

```
┌──────────────┐    ACTIVATES_SUBTASK    ┌──────────────┐
│ DisasterType │ ─────────────────────▶  │   SubTask    │
│ (earthquake) │                         │ (1.1, 1.2..) │
└──────────────┘                         └──────┬───────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
                    ▼ BELONGS_TO                ▼ REQUIRES_CAP              ▼ IMPLEMENTED_BY
            ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
            │  TaskDomain  │            │  Capability  │            │   MetaTask   │
            │(life_rescue) │            │(LIFE_DETECT) │            │  (EM01-32)   │
            └──────┬───────┘            └──────┬───────┘            └──────────────┘
                   │                           │                      (现有，不改)
                   │ PRIORITY_ORDER            │ PROVIDES
                   │                           ▼
            ┌──────┴───────┐            ┌──────────────┐
            │DisasterPhase │            │ RescueModule │
            │   (golden)   │            │(ruins_search)│
            └──────────────┘            └──────────────┘
```

### 四大任务域子任务数据

**1. 生命救护 (life_rescue)**
- 1.1 建筑物废墟下被困人员搜救
- 1.2 滑坡埋压人员搜救
- 1.3 火灾现场被困人员救出
- 1.4 重伤员现场急救与后送
- 1.5 洪水围困人员水上救援（新增）

**2. 群众转移安置 (evacuation)**
- 2.1 震区危险区域人员紧急避险转移
- 2.2 滑坡威胁区整村转移
- 2.3 火灾威胁区疏散
- 2.4 台风前群众预防性转移（新增）

**3. 工程抢险 (engineering)**
- 3.1 开辟生命通道（道路抢通）
- 3.2 山体滑坡二次滑坡防控
- 3.3 堰塞湖应急处置（新增）
- 3.4 台风后道路抢通与电力恢复（新增）
- 3.5 危房拆除与排险

**4. 后勤保障 (logistics)**
- 4.1 物资精准投送
- 4.2 通信、电力、供水快速恢复
- 4.3 疫情与心理危机干预
- 4.4 野战医院展开

**5. 次生灾害防控 (hazard_control)** - 新增任务域
- 5.1 危化品泄漏源头堵漏
- 5.2 危化品扩散区域群众疏散
- 5.3 化工火灾处置

### 预编组模块数据

```
废墟搜救模块 (ruins_search_module):
  人员: 15人
  搜救犬: 4只
  装备: 雷达生命探测仪、音频生命探测仪、液压破拆工具组、蛇眼探测器
  部署时间: 30分钟
  持续作战: 72小时

重型破拆救援模块 (heavy_rescue_module):
  人员: 20人
  装备: 小型挖掘机、混凝土破碎器、切割炬、25吨移动吊车
  部署时间: 60分钟
  持续作战: 48小时

滑坡救援模块 (landslide_rescue_module):
  人员: 30人
  搜救犬: 2只
  装备: 履带式挖掘机、边坡监测仪、测绘无人机、锚杆钻机
  部署时间: 90分钟
  持续作战: 72小时

医疗前突模块 (medical_forward_module):
  人员: 12人
  装备: 高级创伤包、AED、便携式呼吸机、折叠担架x6
  部署时间: 20分钟
  持续作战: 24小时

水上救援模块 (water_rescue_module):
  人员: 20人
  装备: 冲锋舟x6、救生衣x100、抛绳器、水泵
  部署时间: 45分钟
  持续作战: 48小时

化工危化品处置模块 (chemical_hazmat_module):
  人员: 25人
  装备: A级防化服x15、多气体检测仪x10、围堵设备、中和剂
  部署时间: 60分钟
  持续作战: 24小时

野战医院模块 (field_hospital_module):
  人员: 50人
  装备: 医疗方舱x4、手术台x2、便携X光机、移动血库
  部署时间: 180分钟
  持续作战: 168小时（7天）
```

## PostgreSQL Schema 详细设计

### config.capability_kpi

```sql
CREATE TABLE config.capability_kpi (
    id SERIAL PRIMARY KEY,
    capability_code VARCHAR(50) NOT NULL,
    kpi_name VARCHAR(100) NOT NULL,
    target_value DECIMAL(10,2),
    target_unit VARCHAR(20),           -- '%', '分钟', '小时', '人'
    time_window VARCHAR(100),          -- '6小时内', '黄金72小时'
    min_quantity INT DEFAULT 1,
    max_response_time_min INT,
    requirement_type VARCHAR(20) DEFAULT 'required',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(capability_code, kpi_name)
);

-- 示例数据（Capability 编码统一大写，与现有系统一致）
INSERT INTO config.capability_kpi VALUES
(1, 'LIFE_DETECTION', '搜索覆盖率', 90.00, '%', '6小时内完成第一轮全覆盖搜索', 1, NULL, 'required'),
(2, 'LIFE_DETECTION', '黄金期存活率', 70.00, '%', '黄金72小时搜救存活率', 1, NULL, 'required'),
(3, 'EMERGENCY_TREATMENT', '救治响应时间', 30.00, '分钟', '重伤员30分钟内得到专业救治', 1, 30, 'required'),
(4, 'HEAVY_LIFTING', '到场时间', 60.00, '分钟', '重型装备1小时内到场', 2, 60, 'required');
```

### config.safety_rules

```sql
CREATE TABLE config.safety_rules (
    id SERIAL PRIMARY KEY,
    rule_id VARCHAR(50) UNIQUE NOT NULL,
    rule_type VARCHAR(10) NOT NULL,    -- 'hard' or 'soft'
    rule_name VARCHAR(200) NOT NULL,
    category VARCHAR(50),              -- 'fire', 'hazmat', 'structural', 'medical'
    condition_expression JSONB NOT NULL,
    action VARCHAR(20) DEFAULT 'block',
    violation_message TEXT NOT NULL,
    recommendation TEXT,
    is_active BOOLEAN DEFAULT true,
    priority INT DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 示例硬规则
INSERT INTO config.safety_rules (rule_id, rule_type, rule_name, category, condition_expression, action, violation_message, recommendation) VALUES
('HR001', 'hard', '火灾期间禁止开启燃气阀门', 'fire', 
 '{"operator": "AND", "conditions": [{"field": "situation.has_active_fire", "op": "==", "value": true}, {"field": "order.operation", "op": "==", "value": "OPEN_VALVE"}, {"field": "order.valve_type", "op": "contains", "value": "gas"}]}',
 'block', '【硬规则违反】火灾期间禁止开启燃气阀门', '确保所有燃气阀门处于关闭状态'),

('HR002', 'hard', '带电区域禁止用水灭火', 'fire',
 '{"operator": "AND", "conditions": [{"field": "situation.zone_type", "op": "==", "value": "electrical"}, {"field": "order.extinguish_method", "op": "==", "value": "water"}]}',
 'block', '【硬规则违反】带电区域禁止使用水灭火', '先切断电源或使用干粉/CO2灭火剂'),

('HR003', 'hard', '危化品区域必须配备防护装备', 'hazmat',
 '{"operator": "AND", "conditions": [{"field": "situation.is_hazmat_zone", "op": "==", "value": true}, {"field": "order.has_hazmat_protection", "op": "==", "value": false}]}',
 'block', '【硬规则违反】进入危化品区域未配备防护装备', '必须配备A级或B级防化服和空气呼吸器'),

('HR004', 'hard', '爆破前必须完成人员疏散', 'structural',
 '{"operator": "AND", "conditions": [{"field": "order.task_type", "op": "in", "value": ["demolition", "blasting"]}, {"field": "situation.area_evacuated", "op": "==", "value": false}]}',
 'block', '【硬规则违反】拆除区域尚未完成人员疏散', '先完成区域疏散，确认无人后再进行拆除作业'),

('HR005', 'hard', '恶劣天气禁止直升机作业', 'weather',
 '{"operator": "OR", "conditions": [{"field": "situation.wind_speed_ms", "op": ">", "value": 15}, {"field": "situation.has_thunderstorm", "op": "==", "value": true}]}',
 'block', '【硬规则违反】当前天气条件禁止直升机作业', '改用地面运输方式或等待天气好转');

-- 示例软规则
INSERT INTO config.safety_rules (rule_id, rule_type, rule_name, category, condition_expression, action, violation_message, recommendation) VALUES
('SR001', 'soft', '资源冗余不足警告', 'resource',
 '{"operator": "AND", "conditions": [{"field": "plan.redundancy_rate", "op": "<", "value": 0.2}]}',
 'warn', '【警告】资源冗余率低于20%，存在保障风险', '建议增加备用资源'),

('SR002', 'soft', '人员连续作业时间过长', 'personnel',
 '{"operator": "AND", "conditions": [{"field": "unit.continuous_operation_hours", "op": ">", "value": 12}]}',
 'warn', '【警告】人员连续作业超过12小时，存在疲劳风险', '建议安排轮换休息');
```

### config.transport_capacity

```sql
CREATE TABLE config.transport_capacity (
    id SERIAL PRIMARY KEY,
    transport_mode VARCHAR(30) NOT NULL,
    scenario_id UUID,
    capacity_params JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(transport_mode, scenario_id)
);

-- 默认运力参数
INSERT INTO config.transport_capacity (transport_mode, scenario_id, capacity_params) VALUES
('air_drop', NULL, '{"aircraft_count": 2, "payload_per_sortie_tons": 20, "sortie_turnaround_hours": 4, "max_sorties_per_day": 12}'),
('helicopter', NULL, '{"helicopter_count": 6, "payload_per_sortie_tons": 3, "sortie_turnaround_hours": 1, "max_sorties_per_day": 36, "weather_sensitive": true}'),
('highway', NULL, '{"lanes_available": 2, "throughput_per_lane_per_hour_tons": 50, "road_condition_factor": 1.0}'),
('railway', NULL, '{"trains_per_day": 4, "payload_per_train_tons": 500}'),
('waterway', NULL, '{"boats_available": 10, "payload_per_boat_tons": 5}');
```

### config.report_templates

```sql
CREATE TABLE config.report_templates (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(50) UNIQUE NOT NULL,
    report_type VARCHAR(30) NOT NULL,
    template_name VARCHAR(200) NOT NULL,
    template_structure JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 初报模板
INSERT INTO config.report_templates (template_id, report_type, template_name, template_structure) VALUES
('TPL_INITIAL', 'initial', '灾情初报模板', '{
  "sections": [
    {"key": "disaster_overview", "title": "一、灾情概况", "fields": ["disaster_type", "disaster_time", "location", "affected_area", "severity"]},
    {"key": "casualties", "title": "二、人员伤亡情况", "fields": ["deaths", "missing", "injured", "trapped", "evacuated"]},
    {"key": "property_loss", "title": "三、财产损失初步估计", "fields": ["collapsed_buildings", "damaged_buildings", "economic_loss"]},
    {"key": "actions_taken", "title": "四、已采取措施", "fields": ["actions_list"]},
    {"key": "difficulties", "title": "五、存在困难和问题", "fields": ["difficulties_list"]},
    {"key": "next_steps", "title": "六、下一步工作计划", "fields": ["next_steps_list"]}
  ]
}'),

-- 续报模板
('TPL_PROGRESS', 'progress', '救援进展报告模板', '{
  "sections": [
    {"key": "latest_situation", "title": "一、最新态势", "fields": ["report_time", "situation_changes", "secondary_risks"]},
    {"key": "rescue_progress", "title": "二、救援进展", "subsections": [
      {"key": "search", "title": "搜救进展", "fields": ["search_coverage", "rescued_count", "ongoing_areas"]},
      {"key": "evacuation", "title": "转移安置", "fields": ["total_evacuated", "shelter_count", "shelter_status"]},
      {"key": "medical", "title": "医疗救治", "fields": ["treated_count", "severe_injuries", "hospital_transfers"]}
    ]},
    {"key": "force_deployment", "title": "三、力量部署", "fields": ["deployed_forces", "enroute_forces", "equipment_status"]},
    {"key": "supplies", "title": "四、物资保障", "fields": ["supplies_delivered", "supply_gaps"]},
    {"key": "requests", "title": "五、请示事项", "fields": ["requests_list"]}
  ]
}'),

-- 日报模板
('TPL_DAILY', 'daily', '救灾工作日报模板', '{
  "sections": [
    {"key": "daily_work", "title": "一、当日工作情况", "fields": ["search_summary", "evacuation_summary", "medical_summary", "engineering_summary", "logistics_summary"]},
    {"key": "cumulative", "title": "二、累计数据", "fields": ["total_rescued", "total_evacuated", "total_treated", "total_forces"]},
    {"key": "tomorrow_plan", "title": "三、明日工作计划", "fields": ["plan_list"]},
    {"key": "issues", "title": "四、存在问题", "fields": ["issues_list"]},
    {"key": "suggestions", "title": "五、建议", "fields": ["suggestions_list"]}
  ]
}');
```

### config.rescue_module_equipment

```sql
CREATE TABLE config.rescue_module_equipment (
    id SERIAL PRIMARY KEY,
    module_id VARCHAR(50) NOT NULL,
    equipment_code VARCHAR(50) NOT NULL,
    equipment_name VARCHAR(200) NOT NULL,
    quantity INT DEFAULT 1,
    is_required BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(module_id, equipment_code)
);

-- 废墟搜救模块装备
INSERT INTO config.rescue_module_equipment (module_id, equipment_code, equipment_name, quantity, is_required) VALUES
('ruins_search_module', 'life_detector_radar', '雷达生命探测仪', 2, true),
('ruins_search_module', 'life_detector_acoustic', '音频生命探测仪', 2, true),
('ruins_search_module', 'life_detector_infrared', '红外生命探测仪', 1, false),
('ruins_search_module', 'snake_eye_camera', '蛇眼探测器', 2, true),
('ruins_search_module', 'hydraulic_cutter', '液压剪切器', 4, true),
('ruins_search_module', 'hydraulic_spreader', '液压扩张器', 4, true),
('ruins_search_module', 'pneumatic_lifting_bag', '气动起重气垫', 6, true),
('ruins_search_module', 'concrete_chainsaw', '混凝土切割链锯', 2, true);
```

## 阶段优先级配置

| 阶段 | 时间范围 | 优先级顺序 | 主导力量 | 关键链条 |
|------|---------|-----------|---------|---------|
| 初期响应 (initial) | 0-2小时 | 1→3→2→4 | 当地消防+驻军先遣队 | 生命通道开辟+火灾先控 |
| 黄金救援期 (golden) | 2-24小时 | 1→2→3→4 | 国家救援队+消防特勤 | 废墟搜救+火灾围堵+滑坡监控 |
| 攻坚作战期 (intensive) | 24-72小时 | 1→4→5→3 | 专业救援队+工程部队 | 大规模搜救+群众转移+堰塞湖处置 |
| 恢复重建期 (recovery) | 72小时+ | 4→5→3→1 | 地方为主、军队辅助 | 安置+防疫+基础设施恢复 |

**优先级编号**：1-生命救护, 2-群众转移, 3-工程抢险, 4-后勤保障, 5-次生灾害防控

## Risks

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 配置错误导致安全问题 | 高 | 配置校验 + 审核流程 |
| 图谱查询性能 | 中 | 后期加缓存 |
| JSON 条件解析错误 | 中 | 单元测试覆盖 |
| 数据库迁移失败 | 高 | 备份 + 回滚脚本 |
