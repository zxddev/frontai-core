# Change: 新增战略级救灾智能体 (StrategicRescueAgent)

## Why

现有 EmergencyAI 存在以下不足：

1. **任务体系不完整**：EmergencyAI 的 HTN 分解是技术任务层（EM01-EM32），缺少战略任务域层（生命救护/群众转移/工程抢险/后勤保障）
2. **能力指标不精细**：当前只有能力列表，缺少量化 KPI（如"搜索覆盖率≥90%"、"30分钟内救治"）
3. **阶段切换缺失**：无灾害响应阶段状态机（初期/黄金期/攻坚期/恢复期），无法动态调整优先级
4. **预编组模块缺失**：按单个队伍匹配，无"废墟搜救模块=15人+4犬+装备"的模块化编组概念
5. **安全护栏不足**：缺少硬规则引擎（如"火灾时禁止开启燃气阀门"）和医疗建议验证
6. **灾种覆盖不全**：仅地震+火灾+滑坡，缺少洪涝/堰塞湖、危化品泄漏、台风场景
7. **运力瓶颈未建模**：资源规划未考虑投送能力（空投架次、直升机吊次、公路通过能力）
8. **指挥关系链缺失**：执行指令是扁平的，无多级指挥层级
9. **信息上报链缺失**：无自动生成灾情日报/救援进展报告的能力

**配置方案**：全部存 Neo4j + PostgreSQL，不用 YAML，实现动态调整、可审计、可视化管理

## What Changes

### ADDED

**Neo4j 知识图谱扩展（战略层节点，与现有战术层并行）**

新建节点类型：
- `DisasterType` - 灾种节点 (code, name, severity_levels)
- `SubTask` - 子任务节点 (task_id, name, domain, priority, trigger_conditions)
- `RescueModule` - 预编组模块节点 (module_id, name, personnel_count, dog_count, deployment_time_min, sustained_hours)
- `DisasterPhase` - 灾害阶段节点 (phase_id, name, time_range_hours, focus)
- `TaskDomain` - 任务域节点 (domain_id, name, description)

复用节点类型：
- `Capability` - 复用现有能力节点，编码统一大写 (LIFE_DETECTION, FIRE_SUPPRESSION等)
- `MetaTask` - 复用现有元任务节点，通过 IMPLEMENTED_BY 关系连接

关系类型（使用不同关系名避免与现有系统冲突）：
- `(DisasterType)-[:ACTIVATES_SUBTASK {priority}]->(SubTask)` - 灾种激活子任务
- `(SubTask)-[:REQUIRES_CAP {requirement_type, min_level}]->(Capability)` - 子任务需要能力
- `(RescueModule)-[:PROVIDES]->(Capability)` - 模块提供能力
- `(SubTask)-[:RECOMMENDS]->(RescueModule)` - 子任务推荐模块
- `(SubTask)-[:BELONGS_TO]->(TaskDomain)` - 子任务属于任务域
- `(DisasterPhase)-[:PRIORITY_ORDER {rank}]->(TaskDomain)` - 阶段定义任务域优先级
- `(SubTask)-[:IMPLEMENTED_BY {coverage}]->(MetaTask)` - **战略→战术层映射**

**PostgreSQL 配置表**
- `config.capability_kpi` - 能力指标配置（target_value, target_unit, time_window, max_response_time_min）
- `config.safety_rules` - 安全规则配置（rule_type, condition_expression JSONB, action, violation_message）
- `config.transport_capacity` - 运力参数配置（transport_mode, capacity_params JSONB, scenario_id）
- `config.report_templates` - 报告模板配置（report_type, template_structure JSONB）
- `config.rescue_module_equipment` - 模块装备清单（module_id, equipment_code, quantity）

**战略救灾智能体模块**
- `src/agents/strategic_rescue/agent.py` - StrategicRescueAgent 主入口
- `src/agents/strategic_rescue/graph.py` - LangGraph 状态图定义
- `src/agents/strategic_rescue/state.py` - 强类型状态定义
- `src/agents/strategic_rescue/config_service.py` - 配置服务（Neo4j+PG 整合查询）
- `src/agents/strategic_rescue/domain_resolver.py` - 任务域解析器（从 KG 查询）
- `src/agents/strategic_rescue/phase_manager.py` - 阶段管理器（从 KG 查询优先级）
- `src/agents/strategic_rescue/module_assembler.py` - 模块装配器（从 KG 查询模块）
- `src/agents/strategic_rescue/transport_resolver.py` - 运力解算器（从 PG 读取参数）
- `src/agents/strategic_rescue/command_structure.py` - 指挥关系链
- `src/agents/strategic_rescue/report_generator.py` - 报告生成器（从 PG 读取模板）

**安全护栏模块**
- `src/agents/safety/guard.py` - 安全护栏主类
- `src/agents/safety/rule_engine.py` - 规则引擎（从 PG 加载规则，解析 JSON 条件）
- `src/agents/safety/medical_validator.py` - 医疗验证器

**LangGraph 节点**
- `src/agents/strategic_rescue/nodes/understand_situation.py` - 态势理解
- `src/agents/strategic_rescue/nodes/decompose_tasks.py` - 任务分解（查询 KG）
- `src/agents/strategic_rescue/nodes/plan_resources.py` - 资源规划
- `src/agents/strategic_rescue/nodes/safety_check.py` - 安全检查（查询 PG 规则）
- `src/agents/strategic_rescue/nodes/generate_orders.py` - 指令生成
- `src/agents/strategic_rescue/nodes/generate_reports.py` - 报告生成

**数据库迁移脚本**
- `sql/v30_strategic_rescue_kg.cypher` - Neo4j 节点和关系
- `sql/v31_strategic_rescue_tables.sql` - PostgreSQL 配置表
- `sql/v32_strategic_rescue_seed.sql` - 初始数据（子任务、能力、模块、规则）

**API 端点**
- `POST /api/v2/ai/strategic-rescue` - 战略救灾分析
- `POST /api/v2/ai/strategic-rescue/{task_id}/approve` - 人工审核
- `GET /api/v2/ai/reports/{task_id}` - 获取报告

### MODIFIED

- `src/agents/router.py` - 添加新端点
- `src/agents/schemas.py` - 添加数据模型
- `src/infra/clients/neo4j_client.py` - 增加战略救灾相关查询
- `src/agents/db/__init__.py` - 导出新 Repository

## Impact

- **Affected specs**: 新增 `strategic-rescue` capability
- **Affected code**: 新增 ~25 个文件
- **Affected database**:
  - Neo4j: 5 种新节点类型，7 种新关系类型（含映射关系）
  - PostgreSQL: 5 张新配置表
- **Risk**: 高（需数据库迁移，涉及安全决策）

## Architecture Alignment

### 战略层/战术层分离架构

```
┌─────────────────────────────────────────────────────────────┐
│              StrategicRescueAgent（战略层）- 新建            │
│  数据源: DisasterType/SubTask/TaskDomain/RescueModule       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ IMPLEMENTED_BY 映射
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                EmergencyAI（战术层）- 现有                    │
│  数据源: TRRRule/TaskType/Scene/TaskChain/MetaTask          │
└─────────────────────────────────────────────────────────────┘
```

### 与军队使命课题式框架对应

| 军队框架层级 | 系统实现 | 核心组件 |
|-------------|---------|---------|
| 使命/目标层 | 态势理解节点 | LLM + RAG + KG |
| 任务分解层 | 五大任务域 + HTN | DomainResolver + PhaseManager |
| 能力解构层 | 能力指标库 + 运力解算 | CapabilityKPI + TransportResolver |
| 装备映射层 | 预编组模块库 | RescueModule (Neo4j) |
| 执行层 | 指令生成 + 报告 | ExecutionOrder + ReportGenerator |
| 安全层 | 安全护栏（贯穿） | SafetyGuard + RuleEngine |
| **映射层** | **战略→战术连接** | **IMPLEMENTED_BY 关系** |
