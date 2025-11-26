# Change: 应急AI HTN任务分解、NSGA-II优化与大规模场景支持

## Why

当前 `emergency-ai` 模块存在**多项关键功能缺失**，无法支持大型救援场景：

1. **任务依赖未使用**：`query_task_dependencies` 工具已实现，但流程中**完全未调用**
   - 可能生成"先医疗急救，后搜救"的错误方案
   - 被困人员必须先救出才能治疗，这是**致命错误**

2. **mt_library.json未被使用**：项目已有完整的元任务库配置
   - 32个元任务（EM01-EM32）
   - 5条任务依赖链（earthquake_main_chain等）
   - parallel_groups定义可并行任务
   - **这些资产完全未被emergency_ai使用**

3. **优化算法不足**：当前使用贪心算法，代码注释声称"NSGA-II"但实际未实现
   - 贪心算法在大规模资源分配中只能找到局部最优
   - 大型灾害（地震级别）需要调度数百支队伍，贪心明显不够

4. **规模限制**：`LIMIT 50` 硬编码限制了队伍查询数量
   - 大型救援可能需要100-500+支队伍
   - 当前限制无法支持大规模场景

5. **评估维度不足**：当前仅4维评估，缺少**成功率**和**冗余性**

参考军事版文档（TO XIAOMA 20251124），本提案不仅对齐军事版，更要**超越军事版**。

## What Changes

### ADDED

**HTN任务分解节点**
- `src/agents/emergency_ai/nodes/htn_decompose.py` 新增 HTN分解模块
  - 根据灾害类型识别场景（S1-S5）
  - 加载 `config/emergency/mt_library.json` 任务链配置
  - 支持**多场景组合**（复合灾害 → 多任务链合并）
  - 使用Kahn算法拓扑排序生成执行序列
  - 识别并行任务组（parallel_groups）
  - 查询Neo4j补充golden_hour等动态属性

**元任务库加载器**
- `src/agents/emergency_ai/utils/mt_library.py` 新增
  - 加载并解析 mt_library.json
  - 提供场景到任务链的映射
  - 缓存配置避免重复IO

**NSGA-II多目标优化**
- `src/agents/emergency_ai/nodes/matching.py` 重构 `optimize_allocation()`
  - 复用 `src/planning/algorithms/optimization/PymooOptimizer`
  - 实现真正的帕累托前沿生成
  - **不使用降级逻辑**，优化失败直接抛出错误

**状态扩展**
- `src/agents/emergency_ai/state.py` 新增类型定义
  - `MetaTask` - 元任务定义（对应mt_library中的EM01-EM32）
  - `TaskSequenceItem` - 任务序列项
  - `task_sequence` 字段 - 排序后的任务执行序列
  - `parallel_tasks` 字段 - 可并行执行的任务组
  - `scene_codes` 字段 - 识别的场景列表

**5维评估体系**
- `src/agents/emergency_ai/nodes/optimization.py` 增强
  - 新增成功率评估（历史案例相似度 × 资源能力匹配度）
  - 新增冗余性评估（备用资源覆盖率）
  - **权重修正**：成功率 0.30（人命关天）

### MODIFIED

- `src/agents/emergency_ai/nodes/matching.py`
  - `LIMIT 50` → 动态限制，默认200，可通过 `constraints.max_teams` 配置
  - `optimize_allocation()` 使用 NSGA-II 替代贪心
- `src/agents/emergency_ai/graph.py` - 在 `apply_rules` 后添加 `htn_decompose` 节点
- `src/agents/emergency_ai/nodes/__init__.py` - 导出 `htn_decompose`
- `src/agents/emergency_ai/nodes/output.py` - 输出包含任务执行序列和并行任务组
- `src/agents/emergency_ai/agent.py` - 修正注释（移除虚假的"NSGA-II"声明，改为实际实现）

## Impact

- **Affected specs**: `emergency-ai`
- **Affected code**:
  - `src/agents/emergency_ai/state.py` - 新增3个TypedDict，4个字段
  - `src/agents/emergency_ai/nodes/htn_decompose.py` - **新增** HTN分解节点 (~200行)
  - `src/agents/emergency_ai/utils/mt_library.py` - **新增** 元任务库加载器 (~80行)
  - `src/agents/emergency_ai/nodes/matching.py` - 重构优化逻辑 (~150行)
  - `src/agents/emergency_ai/nodes/optimization.py` - 修改评估逻辑 (~50行)
  - `src/agents/emergency_ai/graph.py` - 新增节点和边 (~30行)
  - `src/agents/emergency_ai/nodes/output.py` - 修改输出格式 (~30行)
- **Breaking changes**: 无，仅增强现有功能
- **Database changes**: 无
- **Dependencies**: 复用已有的 `pymoo` 依赖
- **Config dependencies**: 使用 `config/emergency/mt_library.json`

## Architecture: 超越军事版

**军事版 vs 应急版对比**：

| 能力 | 军事版 | 应急版（本提案） | 优势方 |
|------|--------|-----------------|--------|
| NLP理解 | 传统5步流程 | LLM端到端 | **应急版** |
| 场景识别 | K-Means聚类 | LLM理解 | **应急版** |
| 任务链 | 单场景单链 | **多场景组合** | **应急版** |
| 并行调度 | 线性执行 | **parallel_groups** | **应急版** |
| 资源约束 | 静态编组规则 | **实时数据库查询** | **应急版** |
| NSGA-II | 有 | 有（复用PymooOptimizer） | 平 |
| 5维评估 | 有 | 有（权重修正） | 平 |

**应急版超越军事版的核心优势**：

1. **多场景组合**：地震+火灾+危化品 → 自动合并多条任务链
2. **并行任务调度**：mt_library.json 定义 parallel_groups，可并行执行探测任务
3. **实时资源感知**：查询数据库 `rescue_teams_v2.status='standby'`，非静态规则
4. **LLM动态决策**：根据灾情动态调整任务链，而非固定的战术偏好

**对齐军事版的核心能力**：

| 军事版概念 | 应急版实现 |
|-----------|-----------|
| 元任务库（MT库） | `config/emergency/mt_library.json` |
| 前提-效果逻辑链 | mt_library.json + Neo4j DEPENDS_ON |
| HTN分层任务网络 | htn_decompose.py（扁平化2层，适合应急场景） |
| NSGA-II多目标优化 | 复用 PymooOptimizer |
| 5维评估 | score_soft_rules（权重修正）|

## References

- 军事版文档：`docs/TO XIAOMA 20251124(2).docx`
- 现有change：`implement-emergency-ai-hybrid`
- **元任务库配置**：`config/emergency/mt_library.json`（32个元任务，5条任务链）
- Neo4j任务依赖：`scripts/init_emergency_kg.cypher` 中的 `DEPENDS_ON` 关系
- NSGA-II参考：`src/agents/scheme_generation/nodes/optimization.py`
- LangGraph subgraph文档：https://langchain-ai.github.io/langgraph/how-tos/subgraph/
