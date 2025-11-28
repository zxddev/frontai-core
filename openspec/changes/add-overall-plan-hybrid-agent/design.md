# Design: 总体救灾方案生成混合Agent

## Context

根据架构选型文档的核心结论：**单一框架无法完美覆盖该业务链条的所有环节**。

- **CrewAI** 适合处理非结构化、高熵值的**灾情态势汇报**阶段
- **MetaGPT** 适合需要严谨逻辑、数学计算的**资源申请方案**与**正式文件生成**阶段
- **LangGraph** 作为状态管理的中枢神经系统，实现**人机回环（HITL）**审核功能

## Goals

1. 实现CrewAI + MetaGPT + LangGraph混合架构
2. CrewAI处理态势感知（模块0、5）
3. MetaGPT处理资源计算（模块1-4、6-8）和公文生成
4. LangGraph编排全流程，支持HITL审核
5. 使用SPHERE国际人道主义标准进行资源估算
6. 支持状态持久化，服务器重启后可恢复

## Non-Goals

- 不替换现有EmergencyAIAgent（本Agent消费其输出）
- 不实现实时动态调整（本期只做初始方案生成）
- 不实现多轮对话式修改（指挥官审核是单次修改）

## Decisions

### 1. 混合架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│ LangGraph (指挥台 - 状态管理与HITL编排)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                                               │
│  │ load_context│ ← events_v2 + EmergencyAI + resources         │
│  └──────┬──────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │ CrewAI Node (侦察兵 - 态势感知)          │                   │
│  │ ┌─────────────┐  ┌─────────────┐        │                   │
│  │ │情报指挥官   │──│灾情分析员   │        │                   │
│  │ │IntelChief  │  │DisasterAnalyst        │                   │
│  │ └─────────────┘  └─────────────┘        │                   │
│  │ → 模块0: 灾情基本情况                    │                   │
│  │ → 模块5: 次生灾害与安全防范              │                   │
│  └─────────────────────────────────────────┘                   │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │ MetaGPT Node (参谋长 - 资源计算)         │                   │
│  │ ┌─────────────┐                         │                   │
│  │ │ResourcePlanner │ ← Data Interpreter   │                   │
│  │ │(Python计算) │                         │                   │
│  │ └─────────────┘                         │                   │
│  │ → 模块1: 应急救援力量 (队伍数计算)       │                   │
│  │ → 模块2: 医疗救护部署 (医护资源计算)     │                   │
│  │ → 模块3: 基础设施抢修 (工程力量计算)     │                   │
│  │ → 模块4: 临时安置 (SPHERE标准计算)       │                   │
│  │ → 模块6: 通信保障 (设备需求计算)         │                   │
│  │ → 模块7: 物资调拨 (汇总计算)             │                   │
│  │ → 模块8: 自身保障 (后勤计算)             │                   │
│  └─────────────────────────────────────────┘                   │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │ ★ CHECKPOINT: 指挥官审核 (interrupt)    │                   │
│  │ - 状态持久化到PostgreSQL                 │                   │
│  │ - 前端获取9个模块内容                    │                   │
│  │ - 指挥官审核/修改                        │                   │
│  │ - 点击"批准"后resume                    │                   │
│  └─────────────────────────────────────────┘                   │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │ MetaGPT Node (文书专员 - 公文生成)       │                   │
│  │ ┌─────────────┐                         │                   │
│  │ │OfficialScribe│ → 正式方案文档         │                   │
│  │ └─────────────┘                         │                   │
│  └─────────────────────────────────────────┘                   │
│         │                                                       │
│         ▼                                                       │
│    [输出最终方案]                                               │
└─────────────────────────────────────────────────────────────────┘
```

### 2. State定义

```python
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class OverallPlanState(TypedDict):
    """总体救灾方案生成状态"""
    # 输入
    event_id: str
    scenario_id: str
    
    # 数据聚合（load_context节点输出）
    event_data: Dict[str, Any]           # events_v2数据
    ai_analysis: Dict[str, Any]          # EmergencyAI分析结果
    available_resources: List[Dict]      # 可用资源列表
    
    # CrewAI态势感知输出（模块0、5）
    module_0_basic_disaster: Dict[str, Any]  # 结构化灾情基本情况
    module_5_secondary_disaster: str          # 次生灾害与安全防范文本
    
    # MetaGPT资源计算输出（模块1-4、6-8）
    module_1_rescue_force: str           # 应急救援力量部署
    module_2_medical: str                # 医疗救护部署
    module_3_infrastructure: str         # 基础设施抢修
    module_4_shelter: str                # 临时安置与生活保障
    module_6_communication: str          # 通信与信息保障
    module_7_logistics: str              # 物资调拨与运输保障
    module_8_self_support: str           # 救援力量自身保障
    
    # 计算详情（供审核参考）
    calculation_details: Dict[str, Any]  # 各项资源需求的计算过程
    
    # 指挥官审核
    commander_feedback: Optional[str]    # 指挥官反馈意见
    approved: bool                       # 是否已审核通过
    
    # 最终输出
    final_document: Optional[str]        # 正式方案文档
    
    # 追踪
    current_phase: str                   # 当前阶段
    errors: List[str]                    # 错误信息
    
    # 消息历史（用于LLM对话）
    messages: Annotated[List[BaseMessage], add_messages]
```

### 3. 模块分工映射

| 模块 | 数据来源 | 处理框架 | 估算方法 |
|------|---------|---------|---------|
| 0-灾情基本情况 | events_v2 + EmergencyAI | CrewAI | 信息综合 |
| 1-应急救援力量 | 被困人数 | MetaGPT | 被困人数 ÷ 50 = 队伍数 |
| 2-医疗救护部署 | 伤亡数据 | MetaGPT | 伤亡 × 医护比例 |
| 3-基础设施抢修 | 道路/建筑损毁 | MetaGPT | 损毁点 → 工程队 |
| 4-临时安置 | 受灾人口 | MetaGPT | SPHERE标准公式 |
| 5-次生灾害 | EmergencyAI.has_* | CrewAI | 风险识别 |
| 6-通信保障 | 通信损毁情况 | MetaGPT | 基础配置 + 规模调整 |
| 7-物资调拨 | 各模块汇总 | MetaGPT | 汇总计算 |
| 8-自身保障 | 救援力量规模 | MetaGPT | 人员数 → 保障需求 |

### 4. SPHERE国际人道主义标准

```python
SPHERE_STANDARDS = {
    # 饮用水标准
    "water_liters_per_person_per_day": 20,       # 升/人/天
    
    # 临时住所标准
    "tent_capacity_persons": 5,                   # 人/顶帐篷
    "shelter_area_sqm_per_person": 3.5,          # 平方米/人
    
    # 生活物资标准
    "blankets_per_person": 2,                     # 条/人
    "food_kg_per_person_per_day": 0.5,           # 公斤/人/天
    
    # 救援力量配比
    "rescue_team_per_trapped_50": 1,              # 每50名被困者1支救援队
    "search_dogs_per_team": 2,                    # 每队2只搜救犬
    
    # 医疗资源配比
    "medical_staff_per_injured_20": 1,            # 每20名伤员1名医护
    "stretcher_per_serious_injury": 1,            # 每重伤1副担架
    "ambulance_per_injured_50": 1,                # 每50名伤员1辆救护车
}

def estimate_shelter_needs(affected_population: int, days: int = 3) -> Dict[str, int]:
    """估算临时安置物资需求"""
    from math import ceil
    return {
        "tents": ceil(affected_population / SPHERE_STANDARDS["tent_capacity_persons"]),
        "blankets": affected_population * SPHERE_STANDARDS["blankets_per_person"],
        "water_liters": affected_population * SPHERE_STANDARDS["water_liters_per_person_per_day"] * days,
        "food_kg": affected_population * SPHERE_STANDARDS["food_kg_per_person_per_day"] * days,
    }

def estimate_rescue_force(trapped_count: int) -> Dict[str, int]:
    """估算救援力量需求"""
    from math import ceil
    teams = ceil(trapped_count / 50)
    return {
        "rescue_teams": teams,
        "search_dogs": teams * SPHERE_STANDARDS["search_dogs_per_team"],
        "personnel": teams * 30,  # 假设每队30人
    }

def estimate_medical_resources(injured_count: int, serious_count: int) -> Dict[str, int]:
    """估算医疗资源需求"""
    from math import ceil
    return {
        "medical_staff": ceil(injured_count / 20),
        "stretchers": serious_count,
        "ambulances": ceil(injured_count / 50),
    }
```

### 5. CrewAI态势感知设计

```python
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI

def create_situational_awareness_crew(llm: ChatOpenAI) -> Crew:
    """创建态势感知Crew"""
    
    # 情报指挥官
    intel_chief = Agent(
        role="情报指挥官",
        goal="从多源信息中综合出准确的灾情态势",
        backstory="资深应急情报分析专家，擅长从混乱的信息中提取关键要素",
        llm=llm,
        verbose=True,
    )
    
    # 灾情分析员
    disaster_analyst = Agent(
        role="灾情分析员",
        goal="识别次生灾害风险并提出安全防范建议",
        backstory="地质与气象专家，熟悉各类次生灾害的触发条件和防范措施",
        llm=llm,
        verbose=True,
    )
    
    # 任务：生成模块0
    task_basic_disaster = Task(
        description="""
        基于以下灾情数据，生成"灾情基本情况"模块内容：
        {event_data}
        {ai_analysis}
        
        输出要求：
        1. 灾害名称、类型、发生时间
        2. 震级/强度、震源深度（如适用）
        3. 受灾范围、影响区域
        4. 人员伤亡情况（死亡、受伤、失踪、被困）
        5. 建筑受损情况
        6. 基础设施受损情况
        """,
        expected_output="结构化的灾情基本情况JSON",
        agent=intel_chief,
    )
    
    # 任务：生成模块5
    task_secondary_disaster = Task(
        description="""
        基于灾情分析结果，识别次生灾害风险：
        {ai_analysis}
        
        输出要求：
        1. 识别可能的次生灾害类型（余震、滑坡、堰塞湖、火灾、危化品泄漏等）
        2. 评估各类风险的等级
        3. 提出具体的安全防范措施
        4. 建议的监测预警措施
        """,
        expected_output="次生灾害与安全防范方案文本",
        agent=disaster_analyst,
    )
    
    return Crew(
        agents=[intel_chief, disaster_analyst],
        tasks=[task_basic_disaster, task_secondary_disaster],
        verbose=True,
    )
```

### 6. MetaGPT资源计算设计

```python
from metagpt.roles import Role
from metagpt.actions import Action
from metagpt.schema import Message

class CalculateResourceNeeds(Action):
    """计算资源需求Action - 使用Python代码精确计算"""
    
    name: str = "CalculateResourceNeeds"
    
    async def run(self, context: dict) -> dict:
        """执行资源需求计算"""
        # 提取关键数据
        affected_pop = context.get("affected_population", 0)
        trapped_count = context.get("trapped_count", 0)
        injured_count = context.get("injured_count", 0)
        serious_count = context.get("serious_injury_count", 0)
        
        # 使用SPHERE标准计算
        shelter_needs = estimate_shelter_needs(affected_pop)
        rescue_needs = estimate_rescue_force(trapped_count)
        medical_needs = estimate_medical_resources(injured_count, serious_count)
        
        return {
            "shelter": shelter_needs,
            "rescue": rescue_needs,
            "medical": medical_needs,
            "calculation_basis": "SPHERE国际人道主义标准",
        }

class ResourcePlanner(Role):
    """资源规划师角色"""
    
    name: str = "资源规划师"
    profile: str = "应急资源调度专家"
    goal: str = "根据灾情数据精确计算资源需求"
    
    def __init__(self):
        super().__init__()
        self.set_actions([CalculateResourceNeeds()])
```

### 7. HITL审核机制

```python
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph

def build_overall_plan_graph(checkpointer: PostgresSaver) -> StateGraph:
    """构建总体方案生成图"""
    
    graph = StateGraph(OverallPlanState)
    
    # 添加节点
    graph.add_node("load_context", load_context_node)
    graph.add_node("situational_awareness", crewai_situational_node)
    graph.add_node("resource_calculation", metagpt_resource_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("document_generation", metagpt_document_node)
    
    # 定义边
    graph.add_edge("load_context", "situational_awareness")
    graph.add_edge("situational_awareness", "resource_calculation")
    graph.add_edge("resource_calculation", "human_review")
    graph.add_edge("human_review", "document_generation")
    
    # 设置入口和出口
    graph.set_entry_point("load_context")
    graph.set_finish_point("document_generation")
    
    # 编译，启用interrupt_before实现HITL
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["document_generation"],  # 在文档生成前暂停
    )
```

### 8. API设计

```python
# GET /api/overall-plan/{event_id}/modules
# 触发方案生成，返回任务ID
async def get_modules(event_id: str) -> dict:
    """获取9个模块内容（触发Agent流程）"""
    # 1. 启动LangGraph流程
    # 2. 返回任务ID和初始状态
    pass

# GET /api/overall-plan/{event_id}/status
# 查询流程状态
async def get_status(event_id: str) -> dict:
    """查询流程状态"""
    # 返回: pending | running | awaiting_approval | completed | failed
    pass

# PUT /api/overall-plan/{event_id}/approve
# 指挥官审核通过
async def approve(event_id: str, feedback: Optional[str] = None) -> dict:
    """指挥官审核通过，继续执行"""
    # 1. 更新state.approved = True
    # 2. 恢复LangGraph执行
    pass

# GET /api/overall-plan/{event_id}/document
# 获取最终文档
async def get_document(event_id: str) -> dict:
    """获取最终生成的方案文档"""
    pass
```

### 9. 异步兼容性处理

```python
import asyncio
from functools import partial

async def run_crewai_in_thread(crew, inputs: dict) -> dict:
    """在线程中运行CrewAI（避免event loop冲突）"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        partial(crew.kickoff, inputs=inputs)
    )
    return result

async def run_metagpt_role(role, message: str) -> str:
    """运行MetaGPT角色（原生async）"""
    result = await role.run(message)
    return result
```

## Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| CrewAI输出过于发散 | MetaGPT无法解析 | 增加"结构化总结"Agent |
| 上下文超长 | 撑爆Context Window | 只传摘要，原始数据用RAG检索 |
| 指挥官修改违反逻辑 | 数据不一致 | 前端校验 + 校验Agent |
| asyncio event loop冲突 | 运行时错误 | run_in_executor隔离 |
| 状态丢失 | 审核中断需重新开始 | PostgreSQL Checkpointer持久化 |

## References

- [SPHERE Handbook](https://handbook.spherestandards.org/) - 国际人道主义标准
- [ICS-209](https://training.fema.gov/emiweb/is/icsresource/) - 事故指挥系统表格
- [LangGraph HITL](https://langchain-ai.github.io/langgraph/concepts/human_in_the_loop/) - 人机回环文档
- [CrewAI Docs](https://docs.crewai.com/) - CrewAI文档
- [MetaGPT Docs](https://docs.deepwisdom.ai/) - MetaGPT文档
