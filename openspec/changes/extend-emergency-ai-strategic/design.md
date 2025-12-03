# 设计文档

## 1. 数据库 Schema

### 1.1 Neo4j 节点

```cypher
-- TaskDomain: 任务域定义
(:TaskDomain {
    domain_id: String,      -- 'life_rescue', 'evacuation', 'engineering', 'logistics', 'hazard_control'
    name: String,           -- '生命救护', '群众转移', '工程抢险', '后勤保障', '次生灾害防控'
    description: String,
    priority_base: Int      -- 基础优先级
})

-- DisasterPhase: 灾害响应阶段
(:DisasterPhase {
    phase_id: String,       -- 'initial', 'golden', 'intensive', 'recovery'
    name: String,           -- '初期响应', '黄金救援期', '攻坚作战期', '恢复重建期'
    hours_start: Int,       -- 开始小时
    hours_end: Int          -- 结束小时 (-1表示无限)
})

-- RescueModule: 预编组救援模块
(:RescueModule {
    module_id: String,      -- 'ruins_search', 'heavy_rescue', 'medical_forward'
    name: String,           -- '废墟搜救模块', '重型破拆模块', '医疗前突模块'
    personnel: Int,         -- 人员数量
    dogs: Int,              -- 搜救犬数量
    description: String
})
```

### 1.2 Neo4j 关系

```cypher
-- TRRRule 属于 TaskDomain
(TRRRule)-[:BELONGS_TO]->(TaskDomain)

-- DisasterPhase 定义 TaskDomain 的优先级顺序
(DisasterPhase)-[:PRIORITY_ORDER {rank: Int}]->(TaskDomain)

-- RescueModule 提供 Capability
(RescueModule)-[:PROVIDES {level: String}]->(Capability)
```

### 1.3 TRRRule 扩展属性

```cypher
TRRRule {
    ... 现有属性 ...,
    domain: String,         -- 所属任务域 (新增)
    subtask_code: String    -- 军事框架编号，如 '1.1', '2.3' (新增，可选)
}
```

### 1.4 PostgreSQL 表

```sql
-- 安全规则表（支持JSON条件）
CREATE TABLE config.safety_rules (
    rule_id VARCHAR(50) PRIMARY KEY,
    rule_type VARCHAR(10) NOT NULL CHECK (rule_type IN ('hard', 'soft')),
    condition JSONB NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('block', 'warn')),
    message TEXT NOT NULL,
    priority INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 运力参数表
CREATE TABLE config.transport_capacity (
    transport_type VARCHAR(50) PRIMARY KEY,
    capacity_per_unit INT NOT NULL,
    speed_kmh INT NOT NULL,
    max_distance_km INT,
    constraints JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 报告模板表
CREATE TABLE config.report_templates (
    template_id VARCHAR(50) PRIMARY KEY,
    report_type VARCHAR(20) NOT NULL,
    template TEXT NOT NULL,
    variables JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 模块装备表
CREATE TABLE config.rescue_module_equipment (
    module_id VARCHAR(50) NOT NULL,
    equipment_type VARCHAR(100) NOT NULL,
    quantity INT NOT NULL,
    unit VARCHAR(20),
    PRIMARY KEY (module_id, equipment_type)
);
```

---

## 2. 代码架构

### 2.1 State 扩展

```python
# state.py 新增字段
class EmergencyAIState(TypedDict):
    # ... 现有字段 ...
    
    # 任务域相关
    active_domains: List[str]              # 激活的任务域
    domain_priorities: Dict[str, int]      # 任务域优先级 {"life_rescue": 1, ...}
    current_phase: str                     # 当前阶段 "golden"
    
    # 模块相关
    recommended_modules: List[Dict[str, Any]]  # 推荐的预编组模块
    
    # 运力相关
    transport_plan: Dict[str, Any]         # 运力规划
    transport_warnings: List[str]          # 运力警告
    
    # 安全相关
    safety_violations: List[Dict[str, Any]]  # 安全规则违反
    
    # 报告相关
    generated_reports: Dict[str, str]      # 生成的报告 {"initial": "...", "daily": "..."}
```

### 2.2 新节点

| 节点 | 文件 | 输入 | 输出 | 数据库操作 |
|------|------|------|------|-----------|
| classify_domains | domain_classifier.py | matched_rules | active_domains | Neo4j: 查询 TRRRule.domain |
| apply_phase_priority | phase_manager.py | active_domains, event_time | domain_priorities, current_phase | Neo4j: 查询 PRIORITY_ORDER |
| assemble_modules | module_assembler.py | required_capabilities | recommended_modules | Neo4j: 查询 PROVIDES |
| check_transport | transport_checker.py | recommended_modules, location | transport_plan, transport_warnings | PostgreSQL: 查询 transport_capacity |
| check_safety_rules | safety_checker.py | scheme | safety_violations | PostgreSQL: 查询 safety_rules |
| generate_reports | report_generator.py | all state | generated_reports | PostgreSQL: 查询 report_templates |

### 2.3 Graph 流程

```
1. understand_disaster
2. enhance_with_cases
3. query_rules
4. apply_rules
5. htn_decompose
6. 【classify_domains】      ← 新增
7. 【apply_phase_priority】  ← 新增
8. 【assemble_modules】      ← 新增
9. match_resources
10. optimize_allocation
11. 【check_transport】      ← 新增
12. filter_hard_rules
13. 【check_safety_rules】   ← 新增
14. score_soft_rules
15. explain_scheme
16. 【generate_reports】     ← 新增
17. generate_output
```

---

## 3. 日志规范

```python
import logging
import time

logger = logging.getLogger(__name__)

async def classify_domains(state: EmergencyAIState) -> Dict[str, Any]:
    """任务域分类节点"""
    event_id = state["event_id"]
    
    logger.info(
        "【任务域分类】开始执行",
        extra={"event_id": event_id, "matched_rules_count": len(state.get("matched_rules", []))}
    )
    start_time = time.time()
    
    # 查询 Neo4j
    query = """
        MATCH (r:TRRRule)
        WHERE r.rule_id IN $rule_ids
        RETURN DISTINCT r.domain as domain
    """
    params = {"rule_ids": [r["rule_id"] for r in state.get("matched_rules", [])]}
    
    logger.info("【Neo4j】查询任务域", extra={"cypher": query, "params": params})
    
    result = await neo4j_query(query, params)
    
    logger.info("【Neo4j】查询结果", extra={"count": len(result), "domains": result})
    
    if not result:
        raise ValueError(f"【任务域分类】未找到任务域配置，event_id={event_id}")
    
    active_domains = [r["domain"] for r in result if r["domain"]]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info(
        "【任务域分类】执行完成",
        extra={"event_id": event_id, "active_domains": active_domains, "elapsed_ms": elapsed_ms}
    )
    
    return {"active_domains": active_domains}
```

---

## 4. 错误处理规范

```python
# 禁止降级
result = await query_neo4j(...)  # 失败直接抛错

# 禁止空值静默处理
if not result:
    raise ValueError(f"【节点名】数据不存在: {context}")

# 禁止 Mock
# 所有数据必须来自数据库，不允许硬编码默认值
```
