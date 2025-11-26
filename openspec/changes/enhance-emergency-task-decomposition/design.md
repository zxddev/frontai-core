# Design: HTN任务分解、NSGA-II优化与大规模支持

## Context

当前 `emergency-ai` 模块存在多项问题：

**问题1：mt_library.json未被使用**

项目已有完整的元任务库配置（`config/emergency/mt_library.json`）：
```json
{
  "mt_library": [/* 32个元任务 EM01-EM32 */],
  "task_dependencies": {
    "earthquake_main_chain": {
      "tasks": ["EM02", "EM01", "EM03", "EM04", ...],
      "dependencies": {"EM01": ["EM02"], ...},
      "parallel_groups": [["EM06", "EM12", "EM13"], ...]
    }
  }
}
```
**但emergency_ai完全没有使用这些资产！**

**问题2：任务依赖未使用**
```
apply_rules → match_resources  // 跳过了依赖验证！
```

**问题3：优化算法与注释不一致**
```python
# agent.py 注释声称"NSGA-II优化"
# 实际 matching.py 实现：
pareto_solutions = _deduplicate_solutions(solutions)[:3]  # 这是贪心！
```

**问题4：规模限制**
```sql
LIMIT 50  -- 硬编码，大型救援需要100-500+队伍
```

## Goals / Non-Goals

**Goals**:
- **实现HTN任务分解**（使用mt_library.json，扁平化2层架构）
- **支持多场景组合**（复合灾害 → 多任务链合并）
- **支持并行任务调度**（parallel_groups）
- 实现真正的NSGA-II多目标优化（复用PymooOptimizer）
- 支持大规模救援场景（动态LIMIT配置）
- 实现5维评估体系（权重修正：成功率0.30）

**Non-Goals**:
- 不实现3层HTN递归分解（应急场景2层足够，任务→元任务）
- 不实现K-Means场景聚类（LLM理解更强大）
- 不修改API接口格式（保持向后兼容）

## Decisions

### Decision 1: HTN任务分解节点 - 使用mt_library.json

**位置**：在 `apply_rules` 之后，`match_resources` 之前

**设计**：
```python
# src/agents/emergency_ai/nodes/htn_decompose.py

async def htn_decompose(state: EmergencyAIState) -> Dict[str, Any]:
    """
    HTN任务分解节点
    
    1. 根据灾害类型识别场景（S1-S5）
    2. 加载mt_library.json对应的任务链
    3. 支持多场景组合（复合灾害）
    4. 拓扑排序生成执行序列
    5. 识别并行任务组
    """
    parsed_disaster = state["parsed_disaster"]
    
    # 场景识别（根据灾害类型）
    scene_codes = _identify_scenes(parsed_disaster)  # ["S1", "S2"]
    
    # 加载任务链配置
    mt_library = _load_mt_library()
    chains = [_get_chain_for_scene(mt_library, s) for s in scene_codes]
    
    # 合并多条任务链（复合灾害）
    merged_tasks, merged_deps = _merge_chains(chains)
    
    # 拓扑排序
    task_sequence = topological_sort(merged_tasks, merged_deps)
    
    # 识别并行任务
    parallel_tasks = _identify_parallel_tasks(chains)
    
    return {
        "task_sequence": task_sequence,
        "parallel_tasks": parallel_tasks,
        "scene_codes": scene_codes,
    }
```

**场景到任务链映射**：
```python
SCENE_TO_CHAIN: Dict[str, str] = {
    "S1": "earthquake_main_chain",      # 地震主灾
    "S2": "secondary_fire_chain",       # 次生火灾
    "S3": "hazmat_chain",               # 危化品泄漏
    "S4": "flood_debris_chain",         # 山洪泥石流
    "S5": "waterlogging_chain",         # 暴雨内涝
}
```

### Decision 2: 多场景组合（超越军事版）

**军事版限制**：单场景 → 单任务链

**应急版优势**：复合灾害 → 多任务链合并

```python
def _merge_chains(chains: List[TaskChainConfig]) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    合并多条任务链
    
    例：地震+火灾 → earthquake_main_chain + secondary_fire_chain
    """
    all_tasks: Set[str] = set()
    merged_deps: Dict[str, List[str]] = {}
    
    for chain in chains:
        all_tasks.update(chain["tasks"])
        for task, deps in chain["dependencies"].items():
            if task in merged_deps:
                merged_deps[task] = list(set(merged_deps[task] + deps))
            else:
                merged_deps[task] = deps
    
    return list(all_tasks), merged_deps
```

### Decision 3: 拓扑排序算法 - Kahn算法

**选择原因**：
- 时间复杂度 O(V+E)
- 天然检测循环依赖
- 实现简单，易于调试

```python
def topological_sort(tasks: List[str], dependencies: Dict[str, List[str]]) -> List[str]:
    in_degree: Dict[str, int] = {task: 0 for task in tasks}
    for task in tasks:
        for dep in dependencies.get(task, []):
            if dep in in_degree:
                in_degree[task] += 1
    
    queue: List[str] = [t for t in tasks if in_degree[t] == 0]
    result: List[str] = []
    
    while queue:
        task = queue.pop(0)
        result.append(task)
        for other in tasks:
            if task in dependencies.get(other, []):
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)
    
    if len(result) != len(tasks):
        raise ValueError("检测到循环依赖")
    return result
```

### Decision 4: NSGA-II优化迁移

**复用已有组件**：`src/planning/algorithms/optimization/PymooOptimizer`

**关键设计**：
- **不使用降级逻辑**：失败直接抛出 `RuntimeError`
- **不使用熔断器**：暴露问题，不静默

**优化目标函数**：
```python
objectives = {
    "response_time": minimize,   # 最小化响应时间
    "coverage_rate": maximize,   # 最大化覆盖率（取负）
    "cost": minimize,            # 最小化成本
    "risk": minimize,            # 最小化风险
}
```

**与 scheme_generation 的差异**：
| 方面 | scheme_generation | emergency_ai (改造后) |
|------|-------------------|----------------------|
| 熔断器 | 有 | 无 |
| 降级 | 有 | 无（直接报错） |
| 超时 | 30秒 | 60秒（大规模需要更多时间） |

### Decision 5: 动态LIMIT配置

**修改前**：
```sql
LIMIT 50  -- 硬编码
```

**修改后**：
```python
DEFAULT_MAX_TEAMS: int = 200

max_teams = constraints.get("max_teams", DEFAULT_MAX_TEAMS)
# SQL: LIMIT :max_teams
```

**配置建议**：
| 场景规模 | max_teams 建议值 |
|---------|-----------------|
| 小型（单点事故） | 50 |
| 中型（城区灾害） | 100-200 |
| 大型（地震级别） | 300-500 |

### Decision 6: 5维评估权重（修正）

**军事版权重**：
| 维度 | 权重 |
|------|------|
| 任务成功率 | 0.35 |
| 闭合时间 | 0.30 |
| 作战成本 | 0.15 |
| 作战风险 | 0.10 |
| 冗余性 | 0.10 |

**应急版权重（修正后）**：
| 维度 | 权重 | 修正原因 |
|------|------|----------|
| 成功率 | **0.30** | 人命关天，必须高权重 |
| 响应时间 | **0.30** | 黄金救援期72小时 |
| 覆盖率 | 0.20 | 所有灾区必须覆盖 |
| 风险 | **0.10** | 生命优先于风险规避 |
| 冗余性 | 0.10 | 备用资源保障 |

**计算公式**：
```python
DEFAULT_WEIGHTS: Dict[str, float] = {
    "success_rate": 0.30,
    "response_time": 0.30,
    "coverage_rate": 0.20,
    "risk": 0.10,
    "redundancy": 0.10,
}
```

## Risks / Trade-offs

| 风险 | 严重性 | 缓解措施 |
|------|--------|----------|
| NSGA-II耗时增加 | 中 | 大规模场景超时设为60秒 |
| NSGA-II失败无降级 | 高 | 添加详细错误日志，便于排查 |
| Neo4j查询延迟 | 低 | 任务依赖数量少，<50ms |
| 拓扑排序循环依赖 | 低 | 知识图谱设计已避免 |

## Migration Plan

**无迁移需求**：
- 纯增量修改，不修改现有API格式
- `task_sequence` 作为新增输出字段
- 旧客户端可忽略新字段
- NSGA-II替代贪心，输出格式不变

## Open Questions

1. ~~是否需要实现NSGA-II？~~ → **已决定：需要**

2. NSGA-II超时时间设置？
   - 建议：60秒（大规模场景需要更多时间）

3. 是否需要在API响应中暴露 `dependency_violations`？
   - 建议：暴露，让前端可以展示警告
