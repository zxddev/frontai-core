# Design: RealTimeRiskAgent架构设计

## Context

### 背景
操作手册定义的5阶段救援流程中，阶段2（机动前出）需要「AI风险预测」能力。
当前EarlyWarningAgent仅覆盖灾害态势监测，缺少主动预测能力。

### 约束
- 必须保持与现有EarlyWarningAgent的兼容性
- 必须支持Human-in-the-loop（红色风险）
- 必须与RoutePlanningAgent协同工作
- 预测结果必须可解释、可追溯

### 利益相关者
- 前突分队指挥员：接收风险预警，做出决策
- 后方指挥中心：监控整体风险态势
- 系统运维：监控Agent运行状态

## Goals / Non-Goals

### Goals
1. 扩展EarlyWarningAgent为RealTimeRiskAgent
2. 实现路径风险预测（气象/地形/历史数据）
3. 实现作业风险评估（建筑结构/危化品/环境）
4. 实现灾害扩散预测（1h/6h/24h时间尺度）
5. 提供可解释的风险评估报告
6. 与RoutePlanningAgent协同生成规避建议

### Non-Goals
1. 不做完全自动化决策（始终需要人工确认关键决策）
2. 不替代专业的气象预报系统（仅做应急场景的风险研判）
3. 不实现实时视频分析（救援点识别是另一个独立功能）

## Architecture

### LangGraph流程设计

```
RealTimeRiskAgent Graph:

START
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. IngestData                                               │
│    接收多源数据：灾害态势、气象、地形、队伍位置、历史事件   │
└─────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. AnalyzeCurrentRisk (原EarlyWarning核心)                  │
│    ├── 空间风险分析：哪些区域危险                          │
│    ├── 影响实体识别：谁在危险区域                          │
│    └── 风险等级评估：红/橙/黄/蓝                           │
└─────────────────────────────────────────────────────────────┘
  │
  ├─────────────────────────────────────────────────────────┐
  ▼                                                         │
┌─────────────────────────────────────────────────────────┐ │
│ 3. PredictFutureRisk (新增核心能力)                     │ │
│    ├── predict_path_risk: 路径风险预测                   │ │
│    ├── predict_operation_risk: 作业风险评估              │ │
│    └── predict_disaster_spread: 灾害扩散预测             │ │
└─────────────────────────────────────────────────────────┘ │
  │                                                         │
  ▼ (parallel)                                              │
┌─────────────────────────────────────────────────────────┐ │
│ 4. GenerateRecommendation                               │ │
│    ├── 规避路线建议 → 调用RoutePlanningAgent            │ │
│    ├── 撤离建议                                         │ │
│    └── 作业安全建议                                     │ │
└─────────────────────────────────────────────────────────┘ │
  │                                                         │
  ▼                                                         │
┌─────────────────────────────────────────────────────────┐ │
│ 5. HumanReviewGate [HITL]                               │ │
│    ├── 红色风险 → interrupt_before，必须人工确认        │ │
│    └── 黄/蓝风险 → 自动推送                             │ │
└─────────────────────────────────────────────────────────┘ │
  │                                                         │
  ▼                                                         │
┌─────────────────────────────────────────────────────────┐ │
│ 6. ExecuteAlert                                         │◄┘
│    ├── WebSocket推送                                    │
│    ├── 持久化记录                                       │
│    └── 触发联动（RoutePlanningAgent）                   │
└─────────────────────────────────────────────────────────┘
  │
  ▼
END
```

### 模块划分

```
src/agents/realtime_risk/
├── __init__.py
├── agent.py                    # RealTimeRiskAgent主类
├── graph.py                    # LangGraph流程定义
├── state.py                    # 状态定义（扩展）
├── schemas.py                  # Pydantic模型（扩展）
├── models.py                   # SQLAlchemy模型（扩展）
├── repository.py               # 数据访问层（扩展）
├── router.py                   # API路由（扩展）
└── nodes/
    ├── __init__.py
    ├── ingest.py               # 数据接入（原有）
    ├── analyze.py              # 当前风险分析（原有）
    ├── decide.py               # 预警决策（原有）
    ├── generate.py             # 消息生成（原有）
    ├── notify.py               # 通知发送（原有）
    ├── predict_path_risk.py    # 路径风险预测（新增）
    ├── predict_operation_risk.py # 作业风险评估（新增）
    ├── predict_disaster_spread.py # 灾害扩散预测（新增）
    ├── generate_recommendation.py # 建议生成（新增）
    └── human_review.py         # 人工审核门控（新增）
```

### 数据模型扩展

```sql
-- 新增表：风险预测记录
CREATE TABLE operational_v2.risk_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID REFERENCES operational_v2.scenarios_v2(id),
    prediction_type VARCHAR(50) NOT NULL,  -- path_risk/operation_risk/disaster_spread
    target_type VARCHAR(50) NOT NULL,      -- team/vehicle/area
    target_id UUID,
    target_name VARCHAR(255),
    
    -- 预测输入
    input_data JSONB NOT NULL,
    
    -- 预测结果
    risk_level VARCHAR(20) NOT NULL,       -- red/orange/yellow/blue
    risk_score DECIMAL(5,2),               -- 0-100
    confidence_score DECIMAL(5,2),         -- 0-1
    
    -- 预测时间范围
    prediction_horizon_hours INT,          -- 1/6/24
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    
    -- 风险详情
    risk_factors JSONB,                    -- 风险因素列表
    recommendations JSONB,                 -- 建议列表
    explanation TEXT,                      -- LLM生成的解释
    
    -- 人工审核
    requires_human_review BOOLEAN DEFAULT FALSE,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_decision VARCHAR(20),           -- approved/rejected/modified
    review_notes TEXT,
    
    -- 追踪
    trace JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_risk_predictions_scenario ON operational_v2.risk_predictions(scenario_id);
CREATE INDEX idx_risk_predictions_target ON operational_v2.risk_predictions(target_type, target_id);
CREATE INDEX idx_risk_predictions_level ON operational_v2.risk_predictions(risk_level);
```

## Decisions

### Decision 1: 扩展而非新建Agent
**选择**：扩展EarlyWarningAgent为RealTimeRiskAgent
**理由**：
- 数据内聚：预警和预测需要相同的数据源
- 降低失败风险：减少Agent间通信
- H2O.ai工业实践验证

**备选方案**：
- 新建独立RiskPredictionAgent → 数据重复获取，Agent间通信复杂

### Decision 2: Human-in-the-loop设计
**选择**：红色风险使用interrupt_before门控
**理由**：
- 这是救人的系统，错误决策可能致命
- LangGraph原生支持interrupt机制
- SafeAgentBench研究证明HITL必要性

### Decision 3: 预测时间尺度
**选择**：1h/6h/24h三档
**理由**：
- 1h：战术级，行进/作业决策
- 6h：战役级，阶段性规划
- 24h：战略级，整体部署

### Decision 4: 与RoutePlanningAgent协同
**选择**：通过recommendation生成调用
**理由**：
- 规避路线需要RoutePlanningAgent计算
- 保持Agent职责单一
- 通过API调用而非直接耦合

## Risks / Trade-offs

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 预测不准确 | 可能导致错误决策 | 所有预测带置信度，低置信度需人工确认 |
| LLM幻觉 | 生成虚假风险 | 基于规则校验，RAG增强事实性 |
| 响应延迟 | 错过最佳决策时机 | 缓存常见场景，流式处理 |
| 数据源不可用 | 无法预测 | 多数据源冗余，降级到基于规则的预测 |

## Migration Plan

### Phase 1: 数据模型准备
1. 执行SQL创建risk_predictions表
2. 扩展现有state.py添加预测相关类型

### Phase 2: 节点实现
1. 实现predict_path_risk节点
2. 实现predict_operation_risk节点
3. 实现predict_disaster_spread节点
4. 实现generate_recommendation节点
5. 实现human_review门控节点

### Phase 3: 图扩展
1. 扩展graph.py添加新节点
2. 配置条件路由
3. 配置interrupt_before

### Phase 4: API扩展
1. 扩展router.py添加预测查询接口
2. 添加人工审核接口

### Phase 5: 集成测试
1. 单元测试各节点
2. 端到端测试完整流程
3. HITL流程测试

### Rollback Plan
- 保留原EarlyWarningAgent代码
- 通过feature flag控制新功能启用
- 数据库表独立，不影响原有表

## Data Sources (已确认)

### 1. 气象数据 - OpenMeteo API (免费)
```python
# src/infra/clients/openmeteo/weather.py (新增)
# 无需API Key，全球覆盖，支持16天预报

async def get_current_weather(lon: float, lat: float) -> WeatherData:
    """获取当前天气: temperature, wind_speed, wind_direction, precipitation"""

async def get_weather_forecast(lon: float, lat: float, hours: int = 24) -> List[WeatherData]:
    """获取未来N小时预报"""
```

### 2. DEM地形 - 复用 OffroadEngine
```python
# 已有: src/planning/algorithms/routing/offroad_engine.py
# 数据: /data/四川省.tif (2.4GB GeoTIFF)

def get_slope_at(lon: float, lat: float) -> float:
    """获取指定点的坡度(度)"""
```

### 3. 历史案例 - 复用 RAG
```python
# 已有: src/agents/emergency_ai/tools/rag_tools.py

async def search_similar_cases_async(query: str, disaster_type: str, top_k: int) -> List[dict]:
    """检索历史相似案例"""
```

### 4. 灾情数据 - 复用 DataService
```python
# 已有: /data/services.py

async def list_risk_sources(hazard, bbox, time_window) -> List[RiskSource]:
    """查询危险源"""

async def list_blockages(bbox, time_window) -> List[Blockage]:
    """查询阻断信息"""
```

### 5. 路径规划 - 复用高德API
```python
# 已有: src/infra/clients/amap/route_planning.py

async def amap_route_planning_with_avoidance_async(...) -> dict:
    """避障路径规划"""
```

## Risk Assessment Rules (确定性计算)

| 参数 | 红色 | 橙色 | 黄色 | 蓝色 |
|------|------|------|------|------|
| 风速 | >20m/s | 15-20 | 10-15 | <10 |
| 降水 | >50mm/h | 30-50 | 10-30 | <10 |
| 坡度+降水 | >30°+暴雨 | >25° | >20° | <20° |
| 灾害距离 | <1km | 1-3km | 3-5km | >5km |

## Confidence Score Calculation

```python
confidence = 0.6  # 基础（简化模型）
if weather_data_available: confidence += 0.1
if terrain_data_available: confidence += 0.1
if rag_cases_found: confidence += 0.1
if all_data_complete: confidence += 0.1
# 最高 1.0
```
