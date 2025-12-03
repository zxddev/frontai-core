## Phase 1: 数据库 Schema

- [ ] 1.1 编写 Neo4j Schema (`sql/v30_strategic_kg.cypher`)
  - TaskDomain 节点 (5个)
  - DisasterPhase 节点 (4个)
  - RescueModule 节点 (~10个)
  - BELONGS_TO 关系
  - PRIORITY_ORDER 关系 (20条)
  - PROVIDES 关系
  - TRRRule 属性扩展 (domain, subtask_code)

- [ ] 1.2 编写 PostgreSQL Schema (`sql/v31_strategic_tables.sql`)
  - config.safety_rules 表
  - config.transport_capacity 表
  - config.report_templates 表
  - config.rescue_module_equipment 表

## Phase 2: 初始数据

- [ ] 2.1 TaskDomain 数据 (5条)
- [ ] 2.2 DisasterPhase 数据 (4条)
- [ ] 2.3 PRIORITY_ORDER 关系 (20条: 4阶段 × 5域)
- [ ] 2.4 RescueModule 数据 (~10条)
- [ ] 2.5 PROVIDES 关系 (模块→能力)
- [ ] 2.6 更新 TRRRule.domain 属性 (56条)
- [ ] 2.7 safety_rules 数据 (~20条)
- [ ] 2.8 transport_capacity 数据 (5条)
- [ ] 2.9 report_templates 数据 (3条)
- [ ] 2.10 rescue_module_equipment 数据

## Phase 3: State 扩展

- [ ] 3.1 修改 `state.py` 添加新字段
- [ ] 3.2 修改 `create_initial_state()` 初始化新字段

## Phase 4: 新节点实现

- [ ] 4.1 `nodes/domain_classifier.py` - classify_domains()
- [ ] 4.2 `nodes/phase_manager.py` - apply_phase_priority()
- [ ] 4.3 `nodes/module_assembler.py` - assemble_modules()
- [ ] 4.4 `nodes/transport_checker.py` - check_transport()
- [ ] 4.5 `nodes/safety_checker.py` - check_safety_rules()
- [ ] 4.6 `nodes/report_generator.py` - generate_reports()

## Phase 5: Graph 修改

- [ ] 5.1 修改 `graph.py` 添加 6 个新节点
- [ ] 5.2 修改边连接顺序
- [ ] 5.3 修改 `nodes/__init__.py` 导出新函数

## Phase 6: 测试

- [ ] 6.1 单元测试 - 各节点独立测试
- [ ] 6.2 完整流程测试 - /emergency-analyze 端点
- [ ] 6.3 日志验证 - 检查日志输出完整性
