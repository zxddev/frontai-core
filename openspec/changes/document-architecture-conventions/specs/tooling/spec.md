## ADDED Requirements

### Requirement: 工具目录结构
Agent工具 MUST 放置在对应Agent的tools/目录下：

```
src/agents/{agent_name}/tools/
├── __init__.py          # 导出所有工具
├── llm_tools.py         # LLM调用工具
├── kg_tools.py          # 知识图谱工具
├── rag_tools.py         # 向量检索工具
└── routing_tools.py     # 路径规划工具（如需要）
```

#### Scenario: 工具复用
- **WHEN** 多个Agent需要相同工具
- **THEN** 工具保留在原Agent的tools/目录
- **AND** 其他Agent通过导入使用
- **AND** 未来可提取到src/agents/shared/tools/

### Requirement: LLM工具封装规范
LLM工具 MUST 使用LangChain封装：

```python
# src/agents/emergency_ai/tools/llm_tools.py
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# 1. 定义输出结构
class DisasterParseResult(BaseModel):
    disaster_type: str = Field(description="灾害类型")
    severity: str = Field(description="严重程度")
    estimated_trapped: int = Field(description="预估被困人数")

# 2. 获取LLM客户端
def _get_llm(max_tokens: int = 4096) -> ChatOpenAI:
    from src.infra.settings import load_settings
    settings = load_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
        timeout=settings.request_timeout,
        max_tokens=max_tokens,
        max_retries=0,  # 禁止内部重试
    )

# 3. 定义同步工具
@tool
def parse_disaster_description(description: str) -> Dict[str, Any]:
    """解析灾情描述"""
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=DisasterParseResult)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是应急救灾AI助手..."),
        ("human", "{description}"),
    ])
    
    chain = prompt | llm | parser
    return chain.invoke({"description": description})

# 4. 定义异步版本（推荐）
async def parse_disaster_description_async(
    description: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """异步解析灾情描述"""
    llm = _get_llm()
    parser = JsonOutputParser(pydantic_object=DisasterParseResult)
    
    prompt = ChatPromptTemplate.from_messages([...])
    chain = prompt | llm | parser
    
    return await chain.ainvoke({"description": description})
```

#### Scenario: LLM调用失败
- **WHEN** LLM调用超时或返回错误
- **THEN** 抛出RuntimeError
- **AND** 不返回默认值或空结果

### Requirement: TRR规则引擎（双轨系统）
系统 SHALL 使用双轨规则系统：本地YAML规则引擎 + Neo4j知识图谱

**轨道1: 本地YAML规则引擎（src/agents/rules/）**
```python
# src/agents/rules/engine.py - TRR规则引擎（11797行）
from src.agents.rules.engine import TRRRuleEngine
from src.agents.rules.loader import RuleLoader
from src.agents.rules.models import TRRRule, RuleCondition

# 加载本地YAML规则
loader = RuleLoader()
rules = loader.load_rules_for_disaster_type("earthquake")

# 执行规则匹配
engine = TRRRuleEngine()
matched_rules = engine.match_rules(
    rules=rules,
    context={
        "disaster_type": "earthquake",
        "magnitude": 6.5,
        "trapped_count": 50,
    }
)
```

**轨道2: Neo4j知识图谱（复杂关系推理）**
```python
# src/agents/emergency_ai/tools/kg_tools.py
from neo4j import GraphDatabase, Driver

_neo4j_driver: Optional[Driver] = None

def _get_neo4j_driver() -> Driver:
    """获取Neo4j驱动（单例）"""
    global _neo4j_driver
    if _neo4j_driver is None:
        from src.infra.settings import load_settings
        settings = load_settings()
        _neo4j_driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _neo4j_driver

@tool
def query_trr_rules_neo4j(disaster_type: str) -> List[Dict[str, Any]]:
    """查询Neo4j中的TRR规则（用于复杂关系推理）"""
    driver = _get_neo4j_driver()
    
    cypher = '''
    MATCH (r:TRRRule {disaster_type: $disaster_type, is_active: true})
    OPTIONAL MATCH (r)-[:TRIGGERS]->(t:TaskType)
    RETURN r.rule_id, r.name, collect(t.code) AS tasks
    '''
    
    try:
        with driver.session() as session:
            result = session.run(cypher, {"disaster_type": disaster_type})
            return [dict(record) for record in result]
    except Exception as e:
        raise RuntimeError(f"Neo4j查询失败: {e}") from e
```

#### Scenario: 规则来源选择
- **WHEN** 需要简单条件匹配规则
- **THEN** 使用本地YAML规则引擎（src/agents/rules/engine.py）
- **WHEN** 需要复杂关系推理（如任务依赖链）
- **THEN** 使用Neo4j知识图谱查询

#### Scenario: Neo4j连接管理
- **WHEN** 应用启动
- **THEN** Neo4j驱动延迟初始化
- **WHEN** 应用关闭
- **THEN** 调用close_neo4j_driver()释放连接

### Requirement: RAG工具封装规范
向量检索工具 MUST 使用Qdrant：

```python
# src/agents/emergency_ai/tools/rag_tools.py
from qdrant_client import QdrantClient
from langchain_core.tools import tool

def _get_qdrant_client() -> QdrantClient:
    """获取Qdrant客户端"""
    from src.infra.settings import load_settings
    settings = load_settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )

async def search_similar_cases_async(
    query: str,
    disaster_type: str,
    top_k: int = 5,
) -> List[SimilarCase]:
    """异步检索相似案例"""
    from langchain_openai import OpenAIEmbeddings
    from src.infra.settings import load_settings
    
    settings = load_settings()
    
    # 生成查询向量
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
    )
    query_vector = await embeddings.aembed_query(query)
    
    # 检索
    client = _get_qdrant_client()
    results = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=top_k,
        query_filter={"disaster_type": disaster_type},
    )
    
    return [_convert_to_case(r) for r in results]
```

#### Scenario: RAG检索失败
- **WHEN** Qdrant服务不可用
- **THEN** 抛出RuntimeError
- **AND** 调用方决定是否中断流程

### Requirement: 路径规划工具封装（现状）
路径规划工具当前行为：
- 通过环境变量 `ETA_USE_STRAIGHT_LINE`（默认 true）决定是否跳过真实路径规划；未使用 Settings 读取。
- 调用 `RoutePlanningService.plan_route` / `plan_route_with_avoidance` 时未传入 `scenario_id`，灾害避障未启用。
- 出现失败/超时时会回退到直线估算。

```python
# src/agents/emergency_ai/tools/routing_tools.py
from typing import List, Optional
from uuid import UUID

async def batch_calculate_team_etas(
    teams: List[Dict[str, Any]],
    event_lat: float,
    event_lng: float,
    scenario_id: Optional[UUID] = None,
    avoid_areas: Optional[List[AvoidArea]] = None,
    max_concurrent: int = 10,
) -> Dict[str, ETAResult]:
    """
    批量计算多个队伍的 ETA（并行），当前实现：
    - 默认直线估算（ETA_USE_STRAIGHT_LINE=true）
    - 未将 scenario_id 透传到路径规划服务
    - 失败时回退直线估算
    """
    ...
```

#### Scenario: 批量路径规划
- **WHEN** 需要计算多支队伍的ETA
- **THEN** 使用batch_calculate_team_etas
- **AND** 单个失败不影响其他队伍计算

### Requirement: 工具调用模式
Agent节点调用工具 MUST 遵循统一模式：

```python
# 模式1: 直接调用（简单场景）
async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    from ..tools.llm_tools import parse_disaster_description_async
    
    parsed = await parse_disaster_description_async(
        state["disaster_description"]
    )
    return {"parsed_disaster": parsed}

# 模式2: 并行调用（多工具）
async def understand_disaster(state: EmergencyAIState) -> Dict[str, Any]:
    import asyncio
    from ..tools.llm_tools import parse_disaster_description_async
    from ..tools.rag_tools import search_similar_cases_async
    
    # 并行执行
    llm_task = parse_disaster_description_async(state["disaster_description"])
    rag_task = search_similar_cases_async(state["disaster_description"], "earthquake")
    
    parsed, cases = await asyncio.gather(llm_task, rag_task)
    
    return {
        "parsed_disaster": parsed,
        "similar_cases": cases,
    }

# 模式3: 条件调用（有依赖）
async def apply_rules(state: EmergencyAIState) -> Dict[str, Any]:
    from ..tools.kg_tools import query_trr_rules_async
    
    parsed = state.get("parsed_disaster")
    if not parsed:
        return {"errors": state.get("errors", []) + ["灾情未解析"]}
    
    rules = await query_trr_rules_async(parsed["disaster_type"])
    return {"matched_rules": rules}
```

#### Scenario: 工具导入位置
- **WHEN** 节点需要调用工具
- **THEN** 在函数内部导入（延迟导入）
- **AND** 避免循环依赖

### Requirement: 外部客户端统一管理
所有外部服务客户端 MUST 放在src/infra/clients/：

| 客户端 | 路径 | 用途 |
|-------|------|------|
| LLM | llm_client.py | vLLM/OpenAI调用 |
| Neo4j | neo4j_client.py | 知识图谱 |
| Qdrant | qdrant_client.py | 向量数据库 |
| 高德地图 | amap/ | 地理编码、路径规划 |
| ASR | asr/ | 语音识别 |
| TTS | tts/ | 语音合成 |
| 天气 | openmeteo/ | 天气数据 |
| 设备适配器 | adapter_hub.py | 机器狗等设备控制 |

#### Scenario: 客户端配置
- **WHEN** 创建外部客户端
- **THEN** 从Settings获取配置
- **AND** 实现连接池/单例模式

### Requirement: 配置获取规范
工具获取配置 MUST 通过Settings：

```python
# 正确做法
from src.infra.settings import load_settings

def _get_llm() -> ChatOpenAI:
    settings = load_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key,
    )

# 错误做法（禁止）
def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ.get("LLM_MODEL", "gpt-4"),  # 禁止直接读环境变量
        base_url="http://192.168.31.50:8000/v1",     # 禁止硬编码
    )
```

#### Scenario: 配置缺失
- **WHEN** 必需配置项缺失
- **THEN** Settings抛出RuntimeError
- **AND** 明确指出缺失的配置项名称
