# Change: Add Frontline Multi-Event Rescue Dispatch Agent

## Why
当前系统已有 overall plan 生成与 EmergencyAI 总体评估能力，但缺乏面向「多事件、一线队伍互斥调度」的战术级 FrontlineRescueAgent。
在真实救灾场景中，指挥员需要在多起并行灾情下，基于统一规则和硬约束，快速给出多事件优先级与队伍分配方案，并且所有关键阈值和规则必须从数据库配置、可审计、可解释。

## What Changes
- 新增 FrontlineRescueAgent（LangGraph）实现 9 阶段多事件调度工作流（加载上下文 → 事件优先级 → 场景分类 → 批量路网 → 全局分配 → 方案生成 → 硬规则检查 → HITL 人审 → 任务下发）。
- 引入基于 `config.algorithm_parameters` 的多事件优先级 scoring 规则（SCORING_FRONTLINE_EVENT_V1），替代任何 hard-coded 权重或 YAML。
- 引入 Frontline 专用资源分配约束配置（FRONTLINE_ALLOCATION_CONSTRAINTS_V1），统一控制覆盖率/响应时间/最大距离等安全阈值。
- 为 Frontline 场景新增一组 DB 驱动的硬规则（HARD_RULES_FRONTLINE_V1），确保人员安全红线、黄金时间等不可被 LLM 或手工绕过。
- 新增前端/后端接口：支持多事件救援行动方案查询、HITL 审核与任务批量创建。

## Impact
- Affected specs: 新增 `frontline-rescue-dispatch` capability；视需要引用 existing `overall-plan` / `emergency-ai` specs 作为上下文。
- Affected code:
  - `src/agents/frontline_rescue/`（新建）
  - `src/domains/frontend_api/...` 中与 multi-rescue-scheme / multi-rescue-task 相关的路由与 schema
  - `src/infra/config/algorithm_config_service.py` 的配置项使用（不改行为，但增加依赖的 codes）
  - `sql/`：添加 `vYYYYMMDD_frontline_scoring_rules.sql` 之类的规则种子脚本
- Risk: 高（涉及救援调度决策和安全阈值），需要充分测试、仿真与审计。
