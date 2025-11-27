# Design: 救援队安全驻扎点选址服务

## Context

地震应急救援场景中，救援队伍需要在靠近救援目标但远离危险区域的位置建立前沿驻扎点。
这是一个典型的**设施选址问题（Facility Location Problem）**，属于空间优化范畴。

### 约束条件

**硬约束（必须满足）**：
| 约束 | 说明 | 数据来源 |
|-----|------|---------|
| C1 | 不在danger_zone/blocked/flooded区域内 | disaster_affected_areas_v2 |
| C2 | 距危险区边界 >= min_buffer_m | PostGIS ST_Distance |
| C3 | 有通信网络覆盖 | communication_networks_v2 |
| C4 | 从队伍驻地到驻扎点有可行路径 | DatabaseRouteEngine |
| C5 | 从驻扎点到至少一个救援目标有可行路径 | DatabaseRouteEngine |
| C6 | 地面坡度 <= max_slope_deg | rescue_staging_sites_v2 |

**软约束（优化目标）**：
| 目标 | 权重 | 说明 |
|-----|------|-----|
| response_time | 0.35 | 到救援目标的加权响应时间 |
| safety | 0.25 | 距危险区距离 |
| logistics | 0.20 | 到补给/医疗点距离 |
| facility | 0.10 | 水电/面积条件 |
| communication | 0.10 | 通信质量 |

## Goals / Non-Goals

**Goals**:
- 提供驻扎点推荐API，返回评分排序的候选点列表
- 考虑实际路径距离（非直线距离）
- 支持多救援目标的加权响应时间优化
- 复用现有路径规划和风险评估组件

**Non-Goals**:
- 不使用LangGraph编排（纯算法流程）
- 不做实时动态更新（每次请求重新计算）
- 不处理多队伍协同选址（单队伍场景）

## Decisions

### 1. 架构模式：领域服务（Domain Service）

**决策**：采用 `StagingAreaCore` 类，参考 `ResourceSchedulingCore` 模式

**理由**：
- 核心是空间优化算法，不需要LLM参与决策
- 与项目现有架构保持一致
- 易于单元测试

**否决方案**：LangGraph Agent
- 5个处理步骤中只有可选的解释生成需要LLM
- 用LangGraph编排纯算法是过度设计

### 2. 算法流程

```
recommend()
├── _calculate_risk_zones()      # 计算风险区域
├── _search_candidates()         # PostGIS空间查询
├── _validate_routes_batch()     # 批量路径规划（复用DatabaseRouteEngine）
└── _evaluate_and_rank()         # 多目标加权评分
```

### 3. 数据存储

**新增表**：`rescue_staging_sites_v2`
- 存储预定义的候选驻扎点
- 包含地形、设施、通信等属性
- 支持动态安全评估更新

**复用表**：
- `disaster_affected_areas_v2`: 危险区域
- `communication_networks_v2`: 通信覆盖
- `evacuation_shelters_v2`: staging_area类型作为候选源

### 4. 风险区域计算

**来源合并**：
1. 烈度衰减模型计算的影响区（DisasterAssessment）
2. 次生灾害预测区（SecondaryHazardPredictor）
3. 已标记的disaster_affected_areas_v2

**安全距离计算**：
```python
# 烈度衰减公式: I = M - k*log10(R) - c*R
# 反推安全距离（烈度<6的区域）
safe_radius = calculate_intensity_radius(magnitude, target_intensity=6)
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| 候选点数据不足 | 支持多源查询（staging_sites + shelters + entities） |
| 路径规划性能 | 批量规划 + 限制候选点数量 |
| 风险区域动态变化 | 每次请求重新计算风险区域 |

## Migration Plan

1. 执行SQL创建 `rescue_staging_sites_v2` 表
2. 导入候选驻扎点数据（可从shelters迁移或手动录入）
3. 部署服务，注册API路由

## Open Questions

- 是否需要支持多队伍协同选址？（当前设计为单队伍）
- 候选点初始数据如何获取？（建议从GIS系统导入或人工标注）
