## 1. Database Rules & Config
- [ ] 1.1 设计 Frontline 事件优先级 scoring 规则结构（SCORING_FRONTLINE_EVENT_V1）
- [ ] 1.2 设计 Frontline 资源分配约束配置结构（FRONTLINE_ALLOCATION_CONSTRAINTS_V1）
- [ ] 1.3 设计 Frontline 硬规则配置结构（HARD_RULES_FRONTLINE_V1）
- [ ] 1.4 在 `sql/` 中新增种子脚本 `vYYYYMMDD_frontline_scoring_rules.sql`，写入上述配置

## 2. Agent & Domain Implementation
- [ ] 2.1 新建 `FrontlineRescueState`，对齐现有 `OverallPlanState` 风格
- [ ] 2.2 实现 LangGraph `frontline_rescue` 工作流及 9 个节点（load_context / prioritize_events / classify_scenes / batch_route_planning / global_resource_allocation / generate_schemes / hard_rules_check / human_review / generate_tasks）
- [ ] 2.3 将 `PriorityScoringEngine` 集成到 Phase 2，使用 `SCORING_FRONTLINE_EVENT_V1` 规则从 DB 取权重和硬规则
- [ ] 2.4 将 `ResourceSchedulingCore` 集成到 Phase 4 & 5，使用 `FRONTLINE_ALLOCATION_CONSTRAINTS_V1` 参数
- [ ] 2.5 将 Frontline 硬规则（HARD_RULES_FRONTLINE_V1）接入 TRRRuleEngine 或等效检查逻辑

## 3. API & Frontend Integration
- [ ] 3.1 扩展/新增前端 API：multi-rescue-scheme（多事件方案）与 multi-rescue-task（批量任务），对接新 Agent
- [ ] 3.2 前端救援行动弹窗支持展示多事件优先级列表、推荐队伍、硬规则警告，并支持 HITL 人审（选择/取消队伍、调整优先级）

## 4. Testing, Simulation & Validation
- [ ] 4.1 为 FrontlineRescueAgent 编写单元测试和集成测试（含多事件、多队伍、资源不足、规则缺失等边界场景）
- [ ] 4.2 为 DB scoring/constraints/hard_rules 配置增加校验测试（AlgorithmConfigService.validate_required）
- [ ] 4.3 在开发环境用真实/模拟数据跑多轮仿真，验证优先级和调度结果是否符合预期
- [ ] 4.4 补充日志与审计：关键决策点（优先级、分配、硬规则、人审操作）必须可追踪
