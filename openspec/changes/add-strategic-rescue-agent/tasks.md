## 1. 数据库 Schema

- [ ] 1.1 编写 Neo4j 战略层节点/关系 Schema (`sql/v30_strategic_rescue_kg.cypher`)
  - 节点: DisasterType, SubTask, TaskDomain, RescueModule, DisasterPhase
  - 关系: ACTIVATES_SUBTASK, REQUIRES_CAP, PROVIDES, RECOMMENDS, BELONGS_TO, PRIORITY_ORDER
- [ ] 1.2 编写 PostgreSQL 表 Schema (`sql/v31_strategic_rescue_tables.sql`)
  - 表: capability_kpi, safety_rules, transport_capacity, report_templates, rescue_module_equipment
- [ ] 1.3 执行迁移

## 2. 初始数据

- [ ] 2.1 五大任务域 + 子任务数据（含洪涝/危化品/台风）
- [ ] 2.2 灾种→子任务触发关系（ACTIVATES_SUBTASK）
- [ ] 2.3 **SubTask→MetaTask 映射关系**（IMPLEMENTED_BY）- 战略层→战术层连接
- [ ] 2.4 能力需求关系（REQUIRES_CAP，使用大写 Capability 编码）
- [ ] 2.5 预编组模块数据 + PROVIDES 关系
- [ ] 2.6 阶段优先级数据（PRIORITY_ORDER）
- [ ] 2.7 能力 KPI 数据（config.capability_kpi）
- [ ] 2.8 安全规则数据（config.safety_rules，硬规则 + 软规则）
- [ ] 2.9 运力参数数据（config.transport_capacity）
- [ ] 2.10 报告模板数据（config.report_templates）
- [ ] 2.11 编写 seed 脚本 (`sql/v32_strategic_rescue_seed.sql`, `sql/v33_subtask_metatask_mapping.cypher`)
- [ ] 2.12 执行导入

## 3. 配置服务

- [ ] 3.1 `config_service.py` - Neo4j 查询（灾种→任务→能力→模块）
- [ ] 3.2 `config_service.py` - PostgreSQL 查询（KPI/规则/运力/模板）

## 4. 核心框架

- [ ] 4.1 `state.py` - 状态定义
- [ ] 4.2 `graph.py` - LangGraph 流程
- [ ] 4.3 `agent.py` - 主入口

## 5. 任务域

- [ ] 5.1 `domain_resolver.py` - 从 KG 查询激活任务域
- [ ] 5.2 `phase_manager.py` - 阶段管理（从 KG 查询优先级）

## 6. 资源规划

- [ ] 6.1 `module_assembler.py` - 从 KG 选择模块
- [ ] 6.2 `transport_resolver.py` - 从 PG 读取参数计算运力

## 7. 安全护栏

- [ ] 7.1 `guard.py` - 主类
- [ ] 7.2 `rule_engine.py` - JSON 条件解析器
- [ ] 7.3 `medical_validator.py` - 医疗验证

## 8. 指挥/汇报

- [ ] 8.1 `command_structure.py` - 指挥关系链
- [ ] 8.2 `report_generator.py` - 报告生成

## 9. LangGraph 节点

- [ ] 9.1 `understand_situation.py`
- [ ] 9.2 `decompose_tasks.py`
- [ ] 9.3 `plan_resources.py`
- [ ] 9.4 `safety_check.py`
- [ ] 9.5 `generate_orders.py`
- [ ] 9.6 `generate_reports.py`

## 10. API

- [ ] 10.1 Schema 定义
- [ ] 10.2 `/api/v2/ai/strategic-rescue` 端点

## 11. 测试

- [ ] 11.1 配置服务测试
- [ ] 11.2 规则引擎测试
- [ ] 11.3 完整流程测试
