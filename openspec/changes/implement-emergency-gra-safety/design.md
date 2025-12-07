## Context

前突指挥救援系统需要在灾区环境下运行，面临以下约束：
- 多Agent（ReconScheduler/EmergencyAI）可能同时请求同一资源
- 指挥员在高压环境下需要快速决策
- 某些操作存在安全风险但可能是必要的（Break Glass场景）
- 所有关键决策需要事后可追溯

## Goals / Non-Goals

**Goals:**
- 复用现有 ConflictResolver 实现 GRA 功能
- 复用现有 TRRRuleEngine 实现三级安全规则
- 提供完整的审计日志能力

**Non-Goals:**
- 本阶段不实现前端组件（SafetyInterlockButton等）
- 本阶段不实现完整离线模式
- 本阶段不实现告警系统

## Decisions

### D1: GRA 基于 ConflictResolver 扩展

**决策**: 扩展现有 ConflictResolver 而非新建 GlobalResourceArbiter 类

**理由**:
- ConflictResolver 已实现独占/容量/时间冲突检测（11610行）
- 已有优先级策略基础设施
- 避免重复造轮子

**实现方式**:
```python
# 在 ConflictResolver 中添加
GRA_PRIORITY_MAP = {
    "life_rescue_confirmed": 0,      # L0
    "secondary_disaster_prevention": 0,
    "medical_transport": 1,          # L1
    "hazard_zone_recon": 1,
    "suspect_point_recon": 2,        # L2
    "panoramic_recon": 2,
    "supply_delivery": 2,
    "infrastructure_inspection": 3,  # L3
}

def _calc_switching_cost(self, resource: Resource, new_task: Task) -> float:
    """计算切换成本（0-1）"""
    return_dist = haversine(resource.current_pos, resource.home_pos)
    deploy_dist = haversine(resource.home_pos, new_task.start_pos)
    return (return_dist + deploy_dist) / resource.remaining_range
```

### D2: Break Glass 基于 HardRuleAction 扩展

**决策**: 在现有 HardRuleAction 枚举中添加 BREAK_GLASS 类型

**理由**:
- TRRRuleEngine.check_hard_rules() 已有完整的规则检查流程
- 只需扩展枚举和返回结构

**实现方式**:
```python
# src/agents/rules/models.py
class HardRuleAction(Enum):
    REJECT = "reject"      # 硬性阻断
    WARN = "warn"          # 软性提示
    BREAK_GLASS = "break_glass"  # 新增：需长按确认
```

### D3: 审计日志独立域

**决策**: 新建 src/domains/audit/ 域而非放在现有域中

**理由**:
- 审计是跨领域关注点
- 便于后续扩展（不只是Break Glass，还有其他操作审计）
- 符合 DDD 单一职责原则

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 切换成本计算需要实时位置 | 从设备状态表获取最新位置 |
| Break Glass规则库可能不完整 | 初始提供核心规则，支持YAML热加载 |
| 审计日志写入可能影响性能 | 使用异步写入，非关键路径 |

## Migration Plan

1. 先扩展 models.py 添加 BREAK_GLASS 枚举
2. 创建 safety_rules.yaml 规则文件
3. 扩展 TRRRuleEngine 支持新规则类型
4. 创建 audit 域
5. 扩展 ConflictResolver 添加 GRA 功能
6. 集成到 EmergencyAI
