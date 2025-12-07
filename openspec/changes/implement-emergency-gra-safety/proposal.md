# Change: 实现前突指挥救援系统核心安全机制

## Why
前突指挥车是灾区移动指挥中心，需要：
1. 全局资源仲裁（GRA）防止资源冲突和任务震荡
2. 三级安全机制（硬性阻断/Break Glass/软性提示）保护人命
3. 完整审计日志（事后追责）

现有 `implement-emergency-rescue-v3-1` 存在致命缺陷：
- `_calc_switching_cost` 返回常量0/1会导致任务震荡
- 未复用现有 ConflictResolver（11610行）和 TRRRuleEngine（11797行）
- specs目录全空，无法实施

## What Changes
- **MODIFIED** `algorithms`: 扩展 ConflictResolver 添加GRA优先级金字塔（L0-L3）和切换成本计算
- **MODIFIED** `tooling`: 扩展 TRRRuleEngine 添加 BREAK_GLASS 规则类型
- **ADDED** `safety-rules`: 三级安全规则体系（硬性阻断/Break Glass/软性提示）
- **ADDED** `audit`: 审计日志域（Break Glass操作记录）

## Impact
- Affected specs: algorithms, tooling, safety-rules(新), audit(新)
- Affected code:
  - src/planning/algorithms/arbitration/conflict_resolver.py（扩展）
  - src/agents/rules/engine.py（扩展）
  - src/agents/rules/models.py（扩展）
  - src/domains/audit/（新增）
  - config/rules/safety_rules.yaml（新增）
- Database: audit.safety_overrides 表（新增）
