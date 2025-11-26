# Tasks: HTN任务分解、NSGA-II优化与大规模场景支持

## 1. 状态定义扩展

- [ ] 1.1 在 `state.py` 新增 `MetaTask` TypedDict（对应mt_library中的EM01-EM32）
- [ ] 1.2 在 `state.py` 新增 `TaskSequenceItem` TypedDict
- [ ] 1.3 在 `state.py` 新增 `ParallelTaskGroup` TypedDict
- [ ] 1.4 在 `EmergencyAIState` 新增 `task_sequence` 字段
- [ ] 1.5 在 `EmergencyAIState` 新增 `parallel_tasks` 字段
- [ ] 1.6 在 `EmergencyAIState` 新增 `scene_codes` 字段

## 2. 元任务库加载器

- [ ] 2.1 创建 `utils/mt_library.py`
  - [ ] 2.1.1 实现 `load_mt_library()` 加载 `config/emergency/mt_library.json`
  - [ ] 2.1.2 实现 `get_chain_for_scene(scene_code)` 获取场景对应的任务链
  - [ ] 2.1.3 实现配置缓存避免重复IO
  - [ ] 2.1.4 强类型：返回 `MTLibraryConfig` TypedDict

## 3. HTN任务分解节点实现

- [ ] 3.1 创建 `nodes/htn_decompose.py`
  - [ ] 3.1.1 实现 `_identify_scenes()` 根据灾害类型识别场景
  - [ ] 3.1.2 实现 `_merge_chains()` 合并多条任务链（复合灾害）
  - [ ] 3.1.3 实现 `topological_sort()` Kahn算法拓扑排序
  - [ ] 3.1.4 实现 `_identify_parallel_tasks()` 识别并行任务组
  - [ ] 3.1.5 主函数 `htn_decompose()` 整合上述逻辑
  - [ ] 3.1.6 查询Neo4j补充golden_hour等动态属性
- [ ] 3.2 在 `nodes/__init__.py` 导出 `htn_decompose`

## 4. NSGA-II优化迁移

- [ ] 4.1 在 `nodes/matching.py` 修改 `LIMIT 50` 为动态配置
  - [ ] 4.1.1 添加 `DEFAULT_MAX_TEAMS = 200` 常量
  - [ ] 4.1.2 从 `constraints.max_teams` 读取配置，默认200
  - [ ] 4.1.3 更新SQL查询使用动态LIMIT
- [ ] 4.2 重构 `optimize_allocation()` 函数
  - [ ] 4.2.1 导入 `PymooOptimizer` 从 `src/planning/algorithms/optimization`
  - [ ] 4.2.2 定义优化目标函数（响应时间、覆盖率、成本、风险）
  - [ ] 4.2.3 调用 NSGA-II 生成帕累托前沿
  - [ ] 4.2.4 **不使用降级逻辑**，失败直接抛出 `RuntimeError`
- [ ] 4.3 删除 `_generate_greedy_solution()` 函数（已被NSGA-II替代）
- [ ] 4.4 更新 `pareto_solutions` 生成逻辑

## 5. 流程图修改

- [ ] 5.1 在 `graph.py` 添加 `htn_decompose` 节点
- [ ] 5.2 修改边：`apply_rules` → `htn_decompose` → `match_resources`
- [ ] 5.3 添加条件边：task_sequence为空时跳转到 `generate_output`
- [ ] 5.4 新增 `should_continue_after_htn_decompose` 判断函数

## 6. 5维评估体系实现

- [ ] 6.1 在 `optimization.py` 新增成功率计算函数 `_calculate_success_rate()`
  - [ ] 6.1.1 基于RAG相似案例的成功率加权平均
  - [ ] 6.1.2 乘以资源能力匹配度
- [ ] 6.2 在 `optimization.py` 新增冗余性计算函数 `_calculate_redundancy_rate()`
  - [ ] 6.2.1 计算每个能力是否有备用资源
  - [ ] 6.2.2 返回备用覆盖比例
- [ ] 6.3 修改 `DEFAULT_WEIGHTS` 为5维权重（**修正**）
  - `success_rate: 0.30, response_time: 0.30, coverage_rate: 0.20, risk: 0.10, redundancy: 0.10`
- [ ] 6.4 修改 `score_soft_rules()` 使用5维评估
- [ ] 6.5 更新 `SchemeScore` 的 `soft_rule_scores` 包含新维度

## 7. 输出格式修改

- [ ] 7.1 在 `output.py` 的 `generate_output()` 增加 `task_sequence` 输出
- [ ] 7.2 增加 `parallel_tasks` 输出（可并行执行的任务组）
- [ ] 7.3 增加 `scene_codes` 输出（识别的场景列表）
- [ ] 7.4 更新 `reasoning` 输出包含HTN分解结果

## 8. 代码清理

- [ ] 8.1 修正 `agent.py` 注释（删除虚假的"NSGA-II"声明，现已真实实现）
- [ ] 8.2 添加关键日志点：HTN分解、NSGA-II优化开始/结束/耗时
- [ ] 8.3 确保所有新增代码使用强类型注解

## 9. 验证与测试

- [ ] 9.1 验证场景识别：earthquake+fire → ["S1", "S2"]
- [ ] 9.2 验证多任务链合并：earthquake_main_chain + secondary_fire_chain
- [ ] 9.3 验证拓扑排序：EM14(医疗)必须在EM10(救援)之后
- [ ] 9.4 验证并行任务：[EM06, EM12, EM13]可同时执行
- [ ] 9.5 验证NSGA-II生成多个帕累托解
- [ ] 9.6 验证动态LIMIT生效（测试max_teams=100和max_teams=300）
- [ ] 9.7 验证5维评估权重生效（成功率0.30）
- [ ] 9.8 验证输出包含完整的任务序列和并行任务组
- [ ] 9.9 运行类型检查确保强类型覆盖
