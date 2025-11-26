# Tasks: HTN任务分解、NSGA-II优化与大规模场景支持

## 1. 状态定义扩展 ✅

- [x] 1.1 在 `state.py` 新增 `MetaTask` TypedDict（对应mt_library中的EM01-EM32）
- [x] 1.2 在 `state.py` 新增 `TaskSequenceItem` TypedDict
- [x] 1.3 在 `state.py` 新增 `ParallelTaskGroup` TypedDict
- [x] 1.4 在 `EmergencyAIState` 新增 `task_sequence` 字段
- [x] 1.5 在 `EmergencyAIState` 新增 `parallel_tasks` 字段
- [x] 1.6 在 `EmergencyAIState` 新增 `scene_codes` 字段

## 2. 元任务库加载器 ✅

- [x] 2.1 创建 `utils/mt_library.py`
  - [x] 2.1.1 实现 `load_mt_library()` 加载 `config/emergency/mt_library.json`
  - [x] 2.1.2 实现 `get_chain_for_scene(scene_code)` 获取场景对应的任务链
  - [x] 2.1.3 实现配置缓存避免重复IO（使用lru_cache）
  - [x] 2.1.4 强类型：返回 `MTLibraryConfig` TypedDict

## 3. HTN任务分解节点实现 ✅

- [x] 3.1 创建 `nodes/htn_decompose.py`
  - [x] 3.1.1 实现 `_identify_scenes()` 根据灾害类型识别场景
  - [x] 3.1.2 实现 `_merge_chains()` 合并多条任务链（复合灾害）
  - [x] 3.1.3 实现 `topological_sort()` Kahn算法拓扑排序
  - [x] 3.1.4 实现 `_identify_parallel_tasks()` 识别并行任务组
  - [x] 3.1.5 主函数 `htn_decompose()` 整合上述逻辑
  - [x] 3.1.6 查询Neo4j补充golden_hour等动态属性
- [x] 3.2 在 `nodes/__init__.py` 导出 `htn_decompose`

## 4. NSGA-II优化迁移 ✅

- [x] 4.1 在 `nodes/matching.py` 修改 `LIMIT 50` 为动态配置
  - [x] 4.1.1 添加 `DEFAULT_MAX_TEAMS = 200` 常量
  - [x] 4.1.2 从 `constraints.max_teams` 读取配置，默认根据灾害等级动态调整
  - [x] 4.1.3 更新SQL查询使用动态LIMIT
- [x] 4.2 重构 `optimize_allocation()` 函数
  - [x] 4.2.1 导入 `pymoo` NSGA2 算法
  - [x] 4.2.2 定义优化目标函数（响应时间、覆盖率、队伍数量）
  - [x] 4.2.3 调用 NSGA-II 生成帕累托前沿
  - [x] 4.2.4 候选资源<=10时退化为贪心策略（效率优化）
- [x] 4.3 保留 `_generate_greedy_solution()` 作为小规模场景备用
- [x] 4.4 更新 `pareto_solutions` 生成逻辑

## 5. 流程图修改 ✅

- [x] 5.1 在 `graph.py` 添加 `htn_decompose` 节点
- [x] 5.2 修改边：`apply_rules` → `htn_decompose` → `match_resources`
- [x] 5.3 添加条件边：task_sequence为空时跳转到 `generate_output`
- [x] 5.4 新增 `should_continue_after_htn_decompose` 判断函数

## 6. 5维评估体系实现 ✅

- [x] 6.1 在 `optimization.py` 新增成功率计算函数 `_calculate_success_rate()`
  - [x] 6.1.1 基于RAG相似案例的成功率加权平均
  - [x] 6.1.2 乘以资源能力匹配度
- [x] 6.2 在 `optimization.py` 新增冗余性计算函数 `_calculate_redundancy_rate()`
  - [x] 6.2.1 计算每个能力是否有备用资源
  - [x] 6.2.2 返回备用覆盖比例
- [x] 6.3 修改 `DEFAULT_WEIGHTS` 为5维权重（**严格对齐军事版**）
  - `success_rate: 0.35, response_time: 0.30, coverage_rate: 0.20, risk: 0.05, redundancy: 0.10`
- [x] 6.4 修改 `score_soft_rules()` 使用5维评估
- [x] 6.5 更新 `SchemeScore` 的 `soft_rule_scores` 包含新维度

## 7. 输出格式修改 ✅

- [x] 7.1 在 `output.py` 的 `generate_output()` 增加 `task_sequence` 输出
- [x] 7.2 增加 `parallel_tasks` 输出（可并行执行的任务组）
- [x] 7.3 增加 `scene_codes` 输出（识别的场景列表）
- [x] 7.4 增加 `htn_decomposition` 输出块

## 8. 代码清理 ✅

- [x] 8.1 修正 `agent.py` 注释（更新为5阶段流程，包含HTN分解和5维评估说明）
- [x] 8.2 添加关键日志点：HTN分解、NSGA-II优化开始/结束/耗时
- [x] 8.3 确保所有新增代码使用强类型注解

## 9. 验证与测试 ✅

- [x] 9.1 验证导入：所有模块导入成功
- [x] 9.2 验证元任务库加载：32个元任务，5条任务链
- [x] 9.3 验证拓扑排序：Kahn算法正确排序依赖关系
- [x] 9.4 验证5维权重：success_rate=0.35, risk=0.05，总和=1.0
- [x] 9.5 验证成功率计算函数正常工作
- [x] 9.6 验证冗余性计算函数正常工作
- [ ] 9.7 端到端测试（需要数据库和Neo4j环境）
