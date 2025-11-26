# Change: 修复应急AI救援容量匹配致命缺陷

## Why

当前应急AI系统存在**致命设计缺陷**，会导致大规模灾害救援严重资源不足：

### 问题描述

**测试场景**：四川茂县6.8级地震，3000人被困，15万人受灾

**系统输出**：
- 派出队伍：4支
- 能力覆盖率：100%
- 成功率：84.9%

**实际问题**：
- 4支队伍总救援容量约240人/72小时
- 3000人被困，实际覆盖率仅8%
- 2760人（92%）无法在黄金72小时内获救
- **系统显示的84.9%成功率是假的！**

### 根本原因

1. **贪心算法终止条件错误**（matching.py 第873-874行）：
   ```python
   if covered_caps.issuperset(required_caps):
       break  # 只要能力覆盖100%就停止，完全不考虑被困人数！
   ```

2. **数据库有救援容量字段但代码未使用**：
   - `team_capabilities_v2.max_capacity` 字段存在
   - SQL查询完全没有获取这个字段
   - 贪心算法不知道每支队伍能救多少人

3. **NSGA-II目标函数错误**：
   - 当前目标3："最小化队伍数量"
   - 在救灾场景应该是"最大化救援容量"

4. **评估指标缺失**：
   - 缺少"救援容量覆盖率"维度
   - 缺少资源不足警告机制

### 后果

如果系统用于真实救灾：
- 指挥员看到"覆盖率100%、成功率85%"会误以为资源充足
- 实际上92%的被困人员会因资源不足而无法及时获救
- **这是人命关天的bug！**

## What Changes

### MODIFIED

**状态定义扩展** - `state.py`
- `ResourceCandidate` 新增 `rescue_capacity: int` 字段
- `AllocationSolution` 新增：
  - `total_rescue_capacity: int` - 总救援容量
  - `capacity_coverage_rate: float` - 容量覆盖率
  - `capacity_warning: Optional[str]` - 容量不足警告

**SQL查询修改** - `matching.py _query_teams_from_db()`
- 新增：`COALESCE(SUM(tc.max_capacity), 0) AS total_rescue_capacity`
- 返回字典新增 `rescue_capacity` 字段
- 当 max_capacity 为空时使用估算值：`available_personnel × 类型系数`

**贪心算法核心修改** - `matching.py _generate_greedy_solution()`
- 新增参数：`estimated_trapped: int`
- 新增累计变量：`total_capacity`
- **修改终止条件**：
  ```python
  # 旧条件：能力覆盖就停止
  if covered_caps.issuperset(required_caps):
      break
  
  # 新条件：能力覆盖 AND 容量足够才停止
  if covered_caps.issuperset(required_caps):
      if estimated_trapped == 0 or total_capacity >= min_capacity_required:
          break
      # 容量不足，继续添加队伍！
  ```

**NSGA-II目标函数修改** - `matching.py _run_nsga2_optimization()`
- 目标3从"最小化队伍数量"改为"最大化救援容量覆盖率"
- 新增约束：救援容量覆盖率必须>=50%

**硬规则新增** - `optimization.py filter_hard_rules()`
- 新增硬规则：`min_capacity_coverage: 0.5`
- 救援容量<被困人数50%的方案直接否决

**输出格式修改** - `output.py` 和 API响应
- 方案输出新增 `total_rescue_capacity`、`capacity_coverage_rate`
- 容量覆盖率<80%时添加明显警告：
  ```
  ⚠️ 警告：救援容量严重不足！
  被困人员：3000人
  派出队伍总容量：240人
  覆盖率：8%
  建议：紧急请求省级/国家级增援！
  ```

## Impact

- **Affected specs**: `emergency-ai`
- **Affected code**:
  - `src/agents/emergency_ai/state.py` - 类型定义扩展（~10行）
  - `src/agents/emergency_ai/nodes/matching.py` - 核心逻辑修改（~100行）
  - `src/agents/emergency_ai/nodes/optimization.py` - 硬规则新增（~20行）
  - `src/agents/emergency_ai/nodes/output.py` - 输出格式修改（~30行）
- **Breaking changes**: 无，API响应仅新增字段
- **Database changes**: 需要补充 `team_capabilities_v2.max_capacity` 数据（提供SQL）
- **Dependencies**: 无新增依赖

## Architecture: 正确的救援容量计算逻辑

**计算公式**：
```
救援容量覆盖率 = 派出队伍总救援容量 / 被困人数

总救援容量 = Σ(每支队伍的救援容量)

队伍救援容量 = 
  - 若 max_capacity 有值：使用 max_capacity
  - 否则按类型估算：
    - 消防救援：available_personnel × 2
    - 医疗队：available_personnel × 5
    - 搜救队：available_personnel × 1.5
    - 工程队：0（不直接救人）
    - 其他：available_personnel × 1
```

**新的贪心终止条件**：
```
终止 = (能力覆盖率 >= 100%) AND (救援容量覆盖率 >= 80%)

如果资源耗尽但容量覆盖率 < 80%：
  - 不停止，继续尝试所有可用资源
  - 最终方案附带严重警告
```

**修复后预期输出**（3000人被困场景）：
```json
{
  "teams_count": 9,  // 使用所有9支可用队伍
  "total_rescue_capacity": 720,  // 远大于之前的4支队伍
  "capacity_coverage_rate": 0.24,  // 720/3000 = 24%
  "capacity_warning": "⚠️ 救援容量严重不足！仅覆盖24%被困人员，建议紧急请求省级/国家级增援！"
}
```

指挥员会**立刻知道**需要请求增援，而不是被假的"85%成功率"误导！

## References

- 现有数据库定义：`sql/v2_rescue_resource_model.sql`（已有 max_capacity 字段）
- 贪心算法代码：`matching.py` 第816-898行
- NSGA-II代码：`matching.py` 第329-540行
- 测试场景：四川茂县6.8级地震，3000人被困
