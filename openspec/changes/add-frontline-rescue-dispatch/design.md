## Context
- 现有 EmergencyAIAgent / OverallPlan 提供总体灾情评估与综合方案生成，但在多事件、一线队伍互斥调度场景下缺乏专用 FrontlineRescueAgent。
- 项目已具备完备的算法与服务层（SceneArbitrator、CapabilityMatcher、DatabaseRouteEngine、ResourceSchedulingCore、PriorityScoringEngine 等），需要通过统一的 DB 配置（config.algorithm_parameters）驱动规则与阈值。

## Goals / Non-Goals
- Goals:
  - 提供多事件 Frontline 救援调度能力（事件优先级、队伍互斥分配、路径与时间估算）。
  - 所有关键权重、阈值、硬规则完全来自数据库配置，禁止在业务代码中写死数值。
  - 引入 HITL 人审环节，禁止无人审核的自动下达任务。
  - 提供全链路审计日志，支撑事后复盘和监管要求。
- Non-Goals:
  - 不实现车辆级实时轨迹控制与动态调度闭环。
  - 不替代现有 overall plan 文档生成，仅补充战术级调度能力。

## Decisions
- Decision: 使用 `config.algorithm_parameters + AlgorithmConfigService + PriorityScoringEngine` 作为 Frontline 事件优先级、资源约束及硬规则的唯一配置来源。
  - Alternatives: 在 YAML 中维护规则或在代码中写死权重——被拒绝，原因是无法满足救灾场景对可审计性与地区/部门差异化的要求。
- Decision: FrontlineRescueAgent 采用 LangGraph StateGraph，节点与状态设计对齐 `src/agents/overall_plan`，便于复用已有基础设施与前端交互模式。
  - Alternatives: 引入额外的编排框架（MetaGPT/CrewAI）——被拒绝，原因是会显著增加复杂度且现有架构已满足需求。

## Risks / Trade-offs
- Risk: DB 或 Redis 故障时，FrontlineRescueAgent 无法加载必要规则，调度流程会 fail-fast 中止。
  - Mitigation: 明确错误返回与监控告警，在指挥系统 UI 中清晰提示“配置缺失/服务不可用”，并提供人工应急预案。
- Risk: Neo4j 中现有 TRR 规则与 Postgres 中新增 Frontline 硬规则可能产生语义重叠。
  - Mitigation: 在实现中明确职责边界：TRR 继续承担通用灾情规则，Frontline 硬规则聚焦多事件队伍调度安全阈值，并在后续规划统一迁移路径。

## Migration Plan
1. 引入本变更的 SQL 种子脚本（Frontline scoring/constraints/hard_rules），并在测试环境执行。
2. 通过 OpenSpec 变更驱动实现 FrontlineRescueAgent 及相关 API，确保所有 tasks.md 条目完成。
3. 在测试与演练环境中使用真实/模拟数据进行多轮仿真，记录行为与日志。
4. 在获得业务与安全评审通过后，再推广到更高环境，并保留回滚能力（禁用相关 DB 配置即可停用功能）。

## Open Questions
- Frontline 硬规则是否需要在长期内完全从 Neo4j 迁移到 Postgres？若需要，应采用何种统一 schema？
- 不同省市/部门是否需要独立的 Frontline 规则版本（region_code / department_code 粒度），以及如何管理版本升级？
