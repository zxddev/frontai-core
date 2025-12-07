## 1. 后端 - GRA仲裁器扩展

- [ ] 1.1 扩展 ConflictResolver 添加 GRA_PRIORITY_MAP（L0-L3优先级映射）
- [ ] 1.2 实现 ConflictResolver._calc_switching_cost() 真实计算
- [ ] 1.3 扩展 ConflictResolver._resolve_conflict() 支持切换成本阈值检查
- [ ] 1.4 添加 GRA 配置到 config.algorithm_parameters 表
- [ ] 1.5 编写 tests/unit/test_gra_switching_cost.py

## 2. 后端 - 安全规则扩展

- [ ] 2.1 扩展 HardRuleAction 枚举添加 BREAK_GLASS
- [ ] 2.2 创建 config.safety_rules 数据库表
- [ ] 2.3 创建 SafetyRule SQLAlchemy ORM 模型（src/agents/rules/models/safety_rule.py）
- [ ] 2.4 插入初始规则数据（5条硬性+10条BG+8条软性）
- [ ] 2.5 实现 RuleLoader.load_safety_rules_from_db()
- [ ] 2.6 扩展 TRRRuleEngine.check_hard_rules() 返回规则分类
- [ ] 2.7 编写 tests/unit/test_safety_rules.py

## 3. 后端 - 审计日志域

- [ ] 3.1 创建 src/domains/audit/ 目录结构（service, repository, schemas, router）
- [ ] 3.2 实现 AuditService.record_break_glass()
- [ ] 3.3 实现 AuditService.query_break_glass_logs()
- [ ] 3.4 创建 /api/audit/break-glass 查询接口

## 4. 数据库

- [ ] 4.1 提供 sql/migrations/v20251207_add_safety_rules_table.sql（config.safety_rules表+初始数据）
- [ ] 4.2 提供 sql/migrations/v20251207_add_audit_schema.sql（audit.safety_overrides表）
- [ ] 4.3 提供 sql/migrations/v20251207_add_gra_config.sql（GRA配置插入）

## 5. 测试验证

- [ ] 5.1 L1数学验证：切换成本计算（haversine距离/剩余航程）
- [ ] 5.2 L2节点验证：GRA抢占逻辑（L0抢占L2场景）
- [ ] 5.3 L3流程验证：完整抢占流程（请求→成本计算→抢占/拒绝）

## 6. 集成

- [ ] 6.1 集成 GRA 到 EmergencyAI 资源匹配节点
- [ ] 6.2 集成安全规则检查到方案优化阶段
- [ ] 6.3 运行 openspec validate --strict 确保规格正确
