# Tasks: fix-rescue-capacity-matching

## P0 - 致命问题修复（必须立即完成）

### 1. 状态定义扩展
- [ ] `state.py` ResourceCandidate 新增 `rescue_capacity: int`
- [ ] `state.py` AllocationSolution 新增：
  - `total_rescue_capacity: int`
  - `capacity_coverage_rate: float`
  - `capacity_warning: Optional[str]`
- 验证：类型检查通过，mypy无错误

### 2. SQL查询修改
- [ ] `matching.py` `_query_teams_from_db()` SQL新增：
  ```sql
  COALESCE(SUM(tc.max_capacity), 0) AS total_rescue_capacity
  ```
- [ ] 返回字典新增 `rescue_capacity` 字段
- [ ] 添加日志：记录每支队伍的救援容量
- 验证：查询结果包含 rescue_capacity 字段

### 3. 匹配分数计算传递
- [ ] `matching.py` `_calculate_match_scores()` 将 rescue_capacity 传递到 ResourceCandidate
- [ ] 当 max_capacity 为空时使用估算逻辑
- [ ] 添加日志：记录估算使用情况
- 验证：所有候选资源都有 rescue_capacity 值

### 4. 贪心算法核心修改【最关键】
- [ ] `matching.py` `_generate_greedy_solution()` 新增参数 `estimated_trapped: int`
- [ ] 新增累计变量 `total_capacity: int`
- [ ] 修改终止条件：能力覆盖 AND 容量足够
- [ ] 添加详细日志：
  - 每次选择队伍时记录累计容量
  - 记录容量需求和实际容量对比
- 验证：3000人被困场景使用9支队伍而不是4支

### 5. 调用链修改
- [ ] `optimize_allocation()` 获取 estimated_trapped 并传递给贪心算法
- [ ] 所有调用 `_generate_greedy_solution()` 的地方传递 estimated_trapped
- 验证：参数正确传递

### 6. 硬规则新增
- [ ] `optimization.py` `filter_hard_rules()` 新增容量覆盖率检查
- [ ] 容量覆盖率<50%的方案添加 violation
- [ ] 添加日志：记录容量硬规则检查结果
- 验证：容量不足方案被标记为 violations

### 7. 方案输出修改
- [ ] `matching.py` 方案构建时计算并添加：
  - `total_rescue_capacity`
  - `capacity_coverage_rate`
- [ ] 容量覆盖率<80%时生成 `capacity_warning`
- 验证：API返回包含新字段和警告

### 8. 输出格式修改
- [ ] `output.py` 方案说明包含容量信息
- [ ] 容量不足时在方案说明开头添加醒目警告
- 验证：方案说明包含资源不足警告

## P1 - 优化项

### 9. NSGA-II目标函数修改
- [ ] `matching.py` `_run_nsga2_optimization()` 修改目标3：
  - 从"最小化队伍数量"改为"最大化救援容量覆盖率"
- [ ] 新增约束：容量覆盖率>=50%
- [ ] 传递 estimated_trapped 到优化函数
- 验证：NSGA-II生成的方案容量更大

### 10. 数据库补充SQL
- [ ] 提供SQL补充 `team_capabilities_v2.max_capacity` 数据
- [ ] 覆盖所有现有队伍
- 验证：用户执行SQL后数据完整

## P2 - 测试和文档

### 11. 端到端测试
- [ ] 测试场景1：200人被困 → 验证选择合适数量队伍
- [ ] 测试场景2：3000人被困 → 验证使用所有可用资源+警告
- [ ] 测试场景3：0人被困 → 验证降级为纯能力覆盖逻辑
- 验证：所有场景通过

### 12. 日志完整性验证
- [ ] 确认所有关键决策点都有日志
- [ ] 确认日志包含足够信息用于问题排查
- 验证：日志可追踪完整决策过程

## 依赖关系

```
1 → 2 → 3 → 4 → 5 → 7 → 8
         ↓
         6
         
9 独立可并行
10 独立可并行
11 依赖 1-8 完成
```

## 验收标准

1. 3000人被困场景：
   - 系统使用所有9支可用队伍（不是4支）
   - 输出包含 `capacity_coverage_rate` 字段
   - 输出包含明确的资源不足警告

2. 200人被困场景：
   - 系统选择足够队伍覆盖容量需求
   - 不会只选4支就停止

3. 日志可追踪：
   - 每支队伍的救援容量
   - 累计容量和需求对比
   - 终止条件判断过程
