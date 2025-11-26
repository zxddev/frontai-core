# Design: AI Agent核心模块

## Context

应急救灾系统需要AI智能层来：
1. 自动分析灾情事件（地震/洪涝/危化品）
2. 计算确认评分并决定状态流转（confirmed/pre_confirmed/pending）
3. 调用现有算法模块（DisasterAssessment等）
4. 记录决策过程，支持可追溯可解释

现有基础：
- 算法层已实现：DisasterAssessment, SecondaryHazardPredictor, LossEstimator
- LLM客户端已实现：infra/clients/llm_client.py
- 数据库表已创建：events_v2, ai_decision_logs_v2

## Goals

- 实现EventAnalysisAgent，完成事件自动分析和确认评分
- 使用LangGraph编排多步骤分析流程
- 提供异步API接口 `/api/v2/ai/analyze-event`
- 记录AI决策到ai_decision_logs_v2表
- 通过WebSocket推送分析结果

## Non-Goals

- SchemeGenerationAgent（下一迭代）
- ResourceMatchingAgent（下一迭代）
- TaskDispatchAgent（下一迭代）
- ChatAgent（下一迭代）

## Decisions

### 1. LangGraph State设计

```python
from typing import Optional, Annotated
from typing_extensions import TypedDict
from uuid import UUID
from datetime import datetime

class EventAnalysisState(TypedDict):
    """事件分析Agent状态"""
    # 输入
    event_id: UUID
    scenario_id: UUID
    disaster_type: str  # earthquake/flood/hazmat
    location: dict      # {"longitude": float, "latitude": float}
    initial_data: dict  # 灾害参数
    source_system: str
    source_trust_level: float
    
    # 中间结果
    assessment_result: Optional[dict]       # DisasterAssessment输出
    secondary_hazards: Optional[list]       # SecondaryHazardPredictor输出
    loss_estimation: Optional[dict]         # LossEstimator输出
    
    # 确认评分
    ai_confidence: float
    rule_match_score: float
    matched_rules: list[str]
    confirmation_score: float
    
    # 输出
    recommended_status: str  # confirmed/pre_confirmed/pending
    auto_confirmed: bool
    rationale: str
    
    # 追踪
    trace: dict
    errors: list[str]
```

### 2. LangGraph流程

```
START
  │
  ▼
assess_disaster (调用DisasterAssessment)
  │
  ▼
predict_hazards (调用SecondaryHazardPredictor)
  │
  ▼
estimate_loss (调用LossEstimator)
  │
  ▼
calculate_confirmation (调用ConfirmationScorer)
  │
  ▼
decide_status (决定状态流转)
  │
  ▼
END
```

### 3. 确认评分算法 (ConfirmationScorer)

```python
# 评分公式
confirmation_score = (
    ai_confidence * 0.6 +      # AI置信度权重60%
    rule_match_score * 0.3 +   # 规则匹配度权重30%
    source_trust_level * 0.1   # 来源可信度权重10%
)

# 自动确认规则 (AC Rules)
AC_001 = "同位置(500m内)30分钟内≥2个不同来源上报"
AC_002 = "来源=传感器告警 且 AI置信度≥0.8"
AC_003 = "来源∈{110,119,120} 且 is_urgent=true"
AC_004 = "estimated_victims>=1 且 AI置信度>=0.7"

# 状态决策
if 满足任一AC规则 or confirmation_score >= 0.85:
    status = "confirmed", auto_confirmed = True
elif 0.6 <= confirmation_score < 0.85 or priority in ("critical", "high"):
    status = "pre_confirmed"
else:
    status = "pending"
```

### 4. API设计

```
POST /api/v2/ai/analyze-event
→ 立即返回 {"task_id": "...", "status": "processing"}
→ 异步执行Agent
→ 完成后WebSocket推送结果
→ 可通过 GET /api/v2/ai/analyze-event/{task_id} 查询结果
```

### 5. 目录结构

```
src/agents/
├── __init__.py
├── base/
│   ├── __init__.py
│   ├── agent.py           # BaseAgent抽象类
│   ├── state.py           # 共享State
│   └── tools.py           # 工具函数
├── event_analysis/
│   ├── __init__.py
│   ├── agent.py           # EventAnalysisAgent
│   ├── graph.py           # LangGraph定义
│   ├── state.py           # EventAnalysisState
│   └── nodes/
│       ├── __init__.py
│       ├── assess.py      # assess_disaster节点
│       ├── predict.py     # predict_hazards节点
│       ├── loss.py        # estimate_loss节点
│       └── confirm.py     # calculate_confirmation + decide_status节点
├── router.py              # /api/v2/ai/* 路由
└── schemas.py             # Pydantic模型
```

### 6. 异步执行策略

- 使用FastAPI BackgroundTasks执行Agent
- task_id生成：`f"task-{event_id}"`
- 结果存储：Redis或内存缓存（当前使用内存）
- 超时控制：30秒
- 完成通知：WebSocket broadcast_event_update

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| Agent执行超时 | 设置30秒硬超时，超时返回部分结果 |
| 算法调用失败 | 不降级，直接抛出异常，由上层处理 |
| 并发执行冲突 | 使用event_id作为task_id，重复请求返回已有task |
| 内存缓存丢失 | 关键结果写入数据库（ai_decision_logs_v2） |

## Migration Plan

1. 创建agents/模块代码
2. 创建confirmation_scorer.py算法
3. 更新main.py添加AI路由
4. 测试API端点
5. 集成WebSocket推送

## Open Questions

- 是否需要支持取消正在执行的分析任务？（当前：不支持）
- 结果缓存TTL设置多长？（当前：1小时）
- 是否需要支持批量事件分析？（当前：不支持，逐个分析）
