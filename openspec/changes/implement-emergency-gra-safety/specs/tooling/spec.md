## MODIFIED Requirements

### Requirement: TRR规则引擎（双轨系统）
系统 SHALL 使用双轨规则系统：本地YAML规则引擎 + Neo4j知识图谱

**轨道1: 本地YAML规则引擎（src/agents/rules/）**

TRRRuleEngine SHALL 支持三种规则动作类型：

| 动作类型 | 枚举值 | 说明 | 前端表现 |
|----------|--------|------|----------|
| 硬性阻断 | REJECT | 物理不可能，绝对禁止 | 按钮置灰 |
| Break Glass | BREAK_GLASS | 高危但可行，需特别确认 | 黑红条纹，长按5秒 |
| 软性提示 | WARN | 一般风险提示 | 正常按钮，点击确认 |

```python
# src/agents/rules/models.py
class HardRuleAction(Enum):
    REJECT = "reject"           # 硬性阻断
    WARN = "warn"               # 软性提示
    BREAK_GLASS = "break_glass" # Break Glass（新增）
```

#### Scenario: 规则动作分类
- **WHEN** 调用 TRRRuleEngine.check_hard_rules()
- **THEN** 返回结果包含 action 字段
- **AND** action 可能是 REJECT/BREAK_GLASS/WARN 三种之一

#### Scenario: Break Glass规则触发
- **WHEN** 规则 action 为 BREAK_GLASS
- **THEN** 返回结果包含 risk_description（风险说明）
- **AND** 返回结果包含 alternatives（替代方案建议）

### Requirement: 安全规则数据库加载
RuleLoader SHALL 从数据库加载安全规则：

```python
# src/agents/rules/loader.py
class RuleLoader:
    @staticmethod
    async def load_safety_rules_from_db(
        db: AsyncSession
    ) -> Dict[str, List[HardRule]]:
        """
        从数据库加载安全规则
        
        Args:
            db: 数据库会话
        
        Returns:
            {
                "hard_blocks": [...],   # 硬性阻断规则
                "break_glass": [...],   # Break Glass规则
                "soft_warns": [...]     # 软性提示规则
            }
        """
        stmt = (
            select(SafetyRule)
            .where(SafetyRule.is_active == True)
            .order_by(SafetyRule.sort_order)
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()
        
        return {
            "hard_blocks": [_to_hard_rule(r) for r in rules if r.rule_type == "hard_block"],
            "break_glass": [_to_hard_rule(r) for r in rules if r.rule_type == "break_glass"],
            "soft_warns": [_to_hard_rule(r) for r in rules if r.rule_type == "soft_warn"],
        }
```

#### Scenario: 从数据库加载安全规则
- **WHEN** 调用 load_safety_rules_from_db()
- **THEN** 查询 config.safety_rules 表中 is_active=true 的规则
- **AND** 按 rule_type 分类返回
- **AND** 按 sort_order 排序

#### Scenario: 规则缓存
- **WHEN** 高频调用规则检查
- **THEN** 可使用 lru_cache 或 Redis 缓存规则
- **AND** 提供 cache_clear() 方法用于规则更新后刷新

### Requirement: HardRuleResult扩展
HardRuleResult SHALL 包含 Break Glass 相关字段：

```python
@dataclass
class HardRuleResult:
    rule_id: str
    rule_name: str
    passed: bool
    action: HardRuleAction
    message: str
    severity: str
    checked_value: Any = None
    threshold_value: Any = None
    # 新增字段
    risk_description: Optional[str] = None  # 风险详细说明
    alternatives: Optional[List[Dict]] = None  # 替代方案列表
    requires_audit: bool = False  # 是否需要审计记录
```

#### Scenario: Break Glass结果包含替代方案
- **WHEN** 规则动作为 BREAK_GLASS
- **THEN** alternatives 字段包含AI建议的替代方案
- **AND** requires_audit 为 True
