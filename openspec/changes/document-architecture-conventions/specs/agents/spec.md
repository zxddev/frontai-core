## ADDED Requirements

### Requirement: Agent基类继承
所有Agent MUST 继承BaseAgent抽象基类并实现三个核心方法：

```python
from src.agents.base import BaseAgent

class MyAgent(BaseAgent[MyState]):
    def __init__(self) -> None:
        super().__init__(name="my_agent")
    
    def build_graph(self) -> CompiledStateGraph:
        """构建LangGraph状态图"""
        workflow = StateGraph(MyState)
        # 添加节点和边
        return workflow.compile()
    
    def prepare_input(self, **kwargs: Any) -> MyState:
        """准备初始状态"""
        return MyState(...)
    
    def process_output(self, state: MyState) -> Dict[str, Any]:
        """处理最终输出"""
        return {"result": state["final_output"]}
```

#### Scenario: Agent执行流程
- **WHEN** 调用agent.arun(**kwargs)
- **THEN** 系统自动调用prepare_input→graph.ainvoke→process_output
- **AND** 自动记录执行时间和错误

#### Scenario: ReconSchedulerAgent特殊处理
- **WHEN** ReconSchedulerAgent需要更高的递归限制
- **THEN** 覆盖arun方法，设置`config={"recursion_limit": 100}`
- **AND** 保留`schedule()`便捷方法，内部调用arun

### Requirement: LangGraph状态定义
Agent状态 MUST 使用TypedDict定义，SHALL 支持消息历史管理：

```python
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class EmergencyAIState(TypedDict):
    # 输入
    event_id: str
    disaster_description: str
    
    # LLM对话历史（自动合并）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 阶段中间结果
    parsed_disaster: Optional[ParsedDisasterInfo]
    matched_rules: List[MatchedTRRRule]
    
    # 最终输出
    final_output: Dict[str, Any]
    
    # 追踪信息
    trace: Dict[str, Any]
    errors: List[str]
```

#### Scenario: 状态字段类型
- **WHEN** 定义状态字段
- **THEN** 必须使用明确的类型注解
- **AND** Optional字段必须显式标注
- **AND** 复杂类型应定义为独立的TypedDict

### Requirement: 节点函数签名
Agent节点函数 MUST 遵循统一签名：

```python
from typing import Dict, Any

async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    """
    灾情理解节点
    
    只返回需要更新的状态字段，LangGraph自动合并。
    """
    # 执行逻辑
    parsed = await parse_disaster_with_llm(state["disaster_description"])
    
    # 只返回变更的字段
    return {
        "parsed_disaster": parsed,
        "trace": {
            **state.get("trace", {}),
            "phases_executed": state.get("trace", {}).get("phases_executed", []) + ["understand"]
        }
    }
```

#### Scenario: 节点返回值
- **WHEN** 节点执行完成
- **THEN** 只返回需要更新的字段
- **AND** 不要返回整个状态副本
- **AND** trace字段应追加而非覆盖

### Requirement: 条件边函数
图的条件分支 MUST 使用Literal类型标注返回值：

```python
from typing import Literal

def should_continue_after_understanding(
    state: EmergencyAIState
) -> Literal["query_rules", "generate_output"]:
    """判断灾情理解后的下一步"""
    if state.get("parsed_disaster") is None:
        return "generate_output"
    return "query_rules"
```

#### Scenario: 条件边定义
- **WHEN** 使用add_conditional_edges
- **THEN** 条件函数返回值必须是Literal类型
- **AND** 所有可能的返回值必须在映射字典中定义

### Requirement: 人在回路(HITL)机制
关键决策点 MUST 实现HITL审批机制：

```python
from langgraph.types import interrupt

def human_review_scheme(state: EmergencyAIState) -> Dict[str, Any]:
    """方案审批节点"""
    approval_request = HumanApprovalRequest(
        approval_type="scheme",
        summary=f"推荐方案: {state['recommended_scheme']['solution_id']}",
        details={"scheme": state["recommended_scheme"]},
        options=["approve", "reject", "select_alternative"],
    )
    
    # 暂停流程等待人工审批
    response: HumanApprovalResponse = interrupt(approval_request)
    
    if response["decision"] == "rejected":
        raise RuntimeError(f"指挥官拒绝方案: {response.get('reason')}")
    
    return {"approval_history": state.get("approval_history", []) + [response]}
```

#### Scenario: 审批点位置
- **WHEN** 流程涉及关键决策
- **THEN** 必须在以下位置设置HITL审批点：
  1. 灾情理解后
  2. 战略优先级确定后
  3. 最终方案推荐后

### Requirement: 共享子图复用
可复用的Agent能力 SHALL 抽取为共享子图：

```python
# src/agents/shared/disaster_analysis.py
from langgraph.graph import StateGraph, START, END

class DisasterAnalysisState(TypedDict):
    disaster_description: str
    parsed_disaster: Optional[ParsedDisasterInfo]
    similar_cases: List[SimilarCase]

def build_disaster_analysis_subgraph() -> StateGraph:
    """构建灾情分析子图（可嵌入其他Agent）"""
    workflow = StateGraph(DisasterAnalysisState)
    workflow.add_node("understand", understand_disaster)
    workflow.add_node("search_cases", search_similar_cases)
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "search_cases")
    workflow.add_edge("search_cases", END)
    return workflow
```

#### Scenario: 子图嵌入
- **WHEN** 多个Agent需要相同功能
- **THEN** 抽取为src/agents/shared/下的子图
- **AND** 主Agent通过add_node嵌入子图

### Requirement: 现有Agent清单
系统 SHALL 包含以下Agent，各有明确职责：

| Agent | 路径 | 职责 | 架构类型 |
|-------|------|------|----------|
| EmergencyAIAgent | emergency_ai/ | 现场救援方案生成（核心） | LangGraph |
| EarlyWarningAgent | early_warning/ | 实时风险预警监测 | LangGraph+Monitor |
| ReconSchedulerAgent | recon_scheduler/ | 侦察调度Agent（最复杂） | LangGraph+CrewAI+自有algorithms |
| ReconAgent | recon_agent/ | 无人机侦察任务规划 | LangGraph |
| ReconnaissanceAgent | reconnaissance/ | 侦察执行Agent | CrewAI多智能体 |
| OverallPlanAgent | overall_plan/ | 全局救援计划编排（数据驱动+LLM润色） | LangGraph（数据驱动架构） |
| VoiceCommanderAgent | voice_commander/ | 语音指令解析与路由 | **多Agent架构**：semantic_router+spatial_graph+task_agent+resource_agent |
| FrontlineRescueAgent | frontline_rescue/ | 一线队伍任务分配 | LangGraph |
| StagingAreaAgent | staging_area/ | 集结区选址规划 | LangGraph |
| TaskDispatchAgent | task_dispatch/ | 任务智能分发 | LangGraph |
| EquipmentPreparationAgent | equipment_preparation/ | 装备准备Agent | LangGraph |
| SituationPlotAgent | situation_plot/ | 态势标绘Agent | 工具类 |
| SchemeParsingAgent | scheme_parsing/ | 方案解析Agent | LLM结构化输出 |
| route_planning | route_planning/ | 路径规划 | **函数invoke，非Agent类** |

**辅助模块（非Agent）**：
| 模块 | 路径 | 职责 |
|------|------|------|
| db | db/ | 数据库查询工具（schemes.py, spatial.py, teams.py） |
| rules | rules/ | TRR规则引擎（engine.py, loader.py, models.py） |
| shared | shared/ | 共享子图（disaster_analysis.py, priority_scoring.py） |
| services | services/ | Agent服务（config_service.py, gis_service.py） |
| utils | utils/ | 工具类（circuit_breaker.py, resource_lock.py） |

#### Scenario: Agent选择
- **WHEN** 需要生成现场救援方案
- **THEN** 调用EmergencyAIAgent
- **WHEN** 需要规划无人机侦察任务
- **THEN** 调用ReconSchedulerAgent（复杂调度）或ReconAgent（单次规划）
- **WHEN** 需要解析语音指令
- **THEN** 调用VoiceCommanderAgent（内部有4个子Agent协同）
- **WHEN** 需要准备出发装备
- **THEN** 调用EquipmentPreparationAgent
- **WHEN** 需要生成全局总体应急预案
- **THEN** 调用OverallPlanAgent（数据驱动，伤亡物资来自数据库）

### Requirement: overall_plan 数据驱动架构
OverallPlanAgent SHALL 采用数据驱动架构，LLM仅用于次生灾害分析和文本润色：

```
数据流（6个节点，5个数据驱动）:
1. load_context → 从DB加载scenario/events/situations（数据库）
2. disaster_summary → 汇总伤亡数据deaths/injuries/trapped（纯数据聚合）
3. command_structure → 加载组织指挥模板（数据库模板）
4. resource_demand → SPHERE标准计算物资需求（纯算法）
5. gap_analysis → 调用emergency_ai能力匹配（复用现有Agent）
6. secondary_disaster → LLM分析次生灾害（仅此节点用LLM）
```

```python
# 数据驱动节点示例（disaster_summary）
async def disaster_summary_node(state: OverallPlanState) -> dict[str, Any]:
    events_data = state.get("events_data", [])
    
    # 从数据库聚合，禁止LLM估算
    # 字段来源：
    #   casualties ← events_v2.casualty_count
    #   trapped    ← events_v2.estimated_victims
    #   injuries   ← events_v2.source_detail->>'injuries'
    #   missing    ← events_v2.source_detail->>'missing'
    deaths = sum(e.get("casualties", 0) for e in events_data)
    injuries = sum(e.get("injuries", 0) for e in events_data)
    trapped = sum(e.get("trapped", 0) for e in events_data)
    missing = sum(e.get("missing", 0) for e in events_data)
    
    return {
        "module_1_disaster_assessment": {
            "deaths": deaths,
            "injuries": injuries,
            "trapped": trapped,
            "missing": missing,
        }
    }
```

#### 数据来源清单

| 节点 | 数据表 | 关键字段 |
|------|--------|----------|
| load_context | `operational_v2.scenarios_v2` | name, scenario_type, response_level, affected_population |
| load_context | `operational_v2.events_v2` | casualty_count→deaths, estimated_victims→trapped, source_detail→injuries/missing |
| load_context | `operational_v2.disaster_situations` | disaster_type, disaster_name, severity_level |
| load_context | `operational_v2.rescue_teams_v2` | code, name, team_type, capability_level, available_personnel |
| load_context | `operational_v2.supplies_v2` + `supply_inventory_v2` | code, name, category, available_quantity |
| command_structure | `config_v2.command_group_templates_v2` | group_code, group_name, lead_department, responsibilities |
| resource_demand | `config.algorithm_parameters` (sphere) | code, name_cn, params(unit, min_quantity, scaling_basis) |

#### 字段映射详情

**events_v2 → events_data**
```
casualty_count      → casualties (死亡人数)
estimated_victims   → trapped (被困人数)
source_detail JSONB:
  →injuries         → injuries (受伤人数)
  →missing          → missing (失联人数)
  →buildings_collapsed → buildings_collapsed
  →buildings_damaged   → buildings_damaged
```

**scenarios_v2 → scenario_data**
```
affected_population → 受灾人口（SPHERE计算基础）
response_level      → 响应级别（匹配command_group模板）
scenario_type       → 灾害类型（匹配command_group模板）
```

**command_group_templates_v2 → command_groups**
```
WHERE disaster_type = :scenario_type
  AND response_level = :response_level
```

#### Scenario: 数据来源追溯
- **WHEN** 返回伤亡数据（deaths/injuries/trapped）
- **THEN** 必须来自 events_v2 表的聚合，禁止LLM估算
- **WHEN** 返回物资需求数量
- **THEN** 必须基于SPHERE标准公式计算，禁止LLM猜测

### Requirement: overall_plan 无降级原则
overall_plan 节点 MUST 严格禁止降级fallback，配置缺失必须报错：

```python
# 正确做法：配置缺失直接报错
if not command_groups:
    raise CommandStructureError(
        f"工作组配置未找到，请在command_group_templates_v2表配置"
    )

# 错误做法（禁止）：静默使用默认值
if not command_groups:
    return _generate_default_command_structure()  # 禁止！

# 正确做法：SPHERE计算失败报错
try:
    result = await sphere_calculator.calculate(...)
except Exception as e:
    raise ResourceDemandError(f"SPHERE计算失败: {e}") from e

# 错误做法（禁止）：降级到简化算法
except Exception:
    return _calculate_basic_supplies()  # 禁止！
```

#### Scenario: SPHERE计算失败
- **WHEN** SPHERE标准配置缺失或计算失败
- **THEN** 抛出 ResourceDemandError
- **AND** 不使用简化算法降级

#### Scenario: 受灾人口为零
- **WHEN** affected_population = 0 或 NULL
- **THEN** 抛出 ResourceDemandError
- **AND** 不允许使用估算公式（如 deaths*10）替代

### Requirement: emergency_ai流程规范
核心Agent EmergencyAI MUST 遵循5阶段流程：

```
Phase 1: 灾情理解
├── understand_disaster (LLM解析)
├── enhance_with_cases (RAG检索)
└── [HITL] human_review_understanding

Phase 2: 规则推理
├── query_rules (Neo4j TRR规则)
└── apply_rules (条件匹配)

Phase 2.5: 战略层
├── classify_domains (任务域分类)
├── apply_phase_priority (阶段优先级)
├── [HITL] human_review_strategy
├── htn_decompose (HTN任务分解)
└── assemble_modules (模块装配)

Phase 3: 资源匹配
├── match_resources (PostgreSQL队伍查询)
├── optimize_allocation (NSGA-III优化)
└── check_transport (运力检查)

Phase 4: 方案优化
├── filter_hard_rules (硬规则过滤)
├── check_safety_rules (安全规则)
├── score_soft_rules (软规则评分)
├── [HITL] human_review_scheme
├── explain_scheme (LLM方案解释)
└── generate_reports (报告生成)

Phase 5: 仿真验证
├── run_simulation (方案仿真)
└── generate_output (输出生成)
```

#### Scenario: 阶段跳过
- **WHEN** 灾情解析失败(parsed_disaster=None)
- **THEN** 直接跳转到generate_output
- **AND** 输出包含错误信息

### Requirement: 工具调用规范
Agent节点调用工具 MUST 遵循规范：

```python
# 正确：异步调用工具
async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    from ..tools.llm_tools import parse_disaster_description_async
    from ..tools.rag_tools import search_similar_cases_async
    
    # 并行调用提高性能
    llm_task = parse_disaster_description_async(state["disaster_description"])
    rag_task = search_similar_cases_async(state["disaster_description"])
    
    parsed, cases = await asyncio.gather(llm_task, rag_task)
    
    return {"parsed_disaster": parsed, "similar_cases": cases}

# 错误：同步阻塞调用
def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    parsed = parse_disaster_description(state["disaster_description"])  # 阻塞！
    cases = search_similar_cases(state["disaster_description"])  # 串行！
    return {...}
```

#### Scenario: 工具调用性能
- **WHEN** 节点需要调用多个工具
- **THEN** 应使用asyncio.gather并行调用
- **AND** 工具函数必须提供async版本

### Requirement: ReconScheduler验证机制（现状）
侦察调度 Agent 的验证机制存在以下行为：
- L1/L2 结果为 None 时，流程直接视为通过，继续后续节点（允许跳过实际验证）。
- 失败时仍会进入 plan_adjustment 或 handle_error；成功判断仍按航线>0 且 errors 为空。

```python
def should_continue_after_l1(state: ReconSchedulerState) -> Literal["timeline_scheduling", "plan_adjustment", "handle_error"]:
    """L1验证后的条件路由"""
    l1_result = state.get("l1_result")
    
    if l1_result.get("passed", True):
        return "timeline_scheduling"
    
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if retry_count >= max_retries:
        # 验证失败且无法修复，必须停止并报错
        return "handle_error"  # 绝对禁止返回"timeline_scheduling"跳过验证
    
    return "plan_adjustment"
```

#### Scenario: 验证失败处理
- **WHEN** L1/L2验证失败
- **THEN** 进入plan_adjustment重试；重试达到max_retries后进入handle_error
- **现状**：若 l1_result/l2_result 为 None，则直接视为通过，未强制执行验证

#### Scenario: 成功判断逻辑
- **WHEN** 任务执行完成
- **THEN** success = len(flight_plans) > 0 AND len(errors) == 0
- **AND** 有错误时status必须为failed
- **AND** 不允许有错误但success=True

```python
# agent.py 正确的成功判断
flight_plans = result.get("flight_plans", [])
errors = result.get("errors", [])
success = len(flight_plans) > 0 and len(errors) == 0
```

### Requirement: 区域可行性预检查
航线规划节点 MUST 在生成航线前执行预检查：

```python
def _check_area_feasibility(
    polygon: List[Tuple[float, float]],
    device_profile: DeviceProfile,
    scan_config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    检查区域是否在设备能力范围内
    
    Args:
        polygon: 区域多边形坐标 [(lat, lng), ...]
        device_profile: 设备配置
        scan_config: 扫描配置
    
    Returns:
        {"feasible": bool, "estimated_distance_km": float, "max_distance_km": float}
    """
    # 计算预估飞行距离
    scan_distance = num_lines * line_length
    turn_distance = (num_lines - 1) * line_spacing
    return_distance = diagonal * 2
    estimated_distance = scan_distance + turn_distance + return_distance
    
    # 计算设备最大可飞距离（90%安全系数）
    max_distance = max_endurance_min * cruise_speed_ms * 60 * 0.9
    
    return {
        "feasible": estimated_distance <= max_distance,
        "estimated_distance_km": estimated_distance / 1000,
        "max_distance_km": max_distance / 1000,
    }
```

#### Scenario: 预检查失败
- **WHEN** 预检查判定区域过大
- **THEN** 立即记录错误并跳过该任务
- **AND** 错误信息必须包含：预估距离、设备最大距离、设备名称

```python
if not area_check["feasible"]:
    error_msg = (f"任务 {task_id} 区域过大无法单次覆盖: "
                f"预估飞行{area_check['estimated_distance_km']:.1f}km, "
                f"设备{device_name}最大可飞{area_check['max_distance_km']:.1f}km")
    logger.error(error_msg)
    errors.append(error_msg)
    continue
```

### Requirement: 设备能力参数来源
设备续航时间等能力参数 MUST 从配置读取，禁止硬编码：

```python
# 正确：从设备配置读取
device_profile = await device_provider.get_device_profile(device_id)
max_flight_time = device_profile.max_endurance_min

# 错误：硬编码（禁止）
max_flight_time = 41  # 硬编码！
```

#### Scenario: 新增设备类型
- **WHEN** 系统需要支持新设备类型
- **THEN** 只需在设备配置中添加参数
- **AND** 不需要修改任何业务代码
