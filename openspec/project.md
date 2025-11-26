# Project Context

## Purpose
本系统是“多场景协同决策中枢 v1.0”，旨在为城市应急、军事指挥等场景提供基于大模型的智能辅助决策。
核心能力：自然语言意图 -> 多场景拆解 -> 任务链规划 -> 资源匹配 -> 方案评估 -> 推荐方案。

## Tech Stack
- **Language**: Python 3.10+
- **Frameworks**:
  - **FastAPI**: Web API 服务
  - **LangChain**: >1.0.0 (Agent & Tooling)
  - **LangGraph**: >1.0.0 (Stateful Orchestration)
  - **Pydantic**: v2 (Data Validation)
- **Infrastructure**:
  - **PostgreSQL**: 关系型数据 & 规则存储
  - **Neo4j**: 知识图谱
  - **Qdrant**: 向量数据库 (RAG)
  - **vLLM**: 本地大模型推理 (OpenAI Compatible API)

## Project Conventions

### Code Style
- **Type Hints**: 必须全覆盖，使用 `typing` 和 `pydantic`。
- **Async/Sync**:
  - API 端点默认使用 `def` (Sync) 以避免阻塞主循环（针对 CPU 密集型任务）。
  - I/O 密集型操作应尽量使用异步库，或者在 Sync 函数中通过线程池执行。
- **Error Handling**: 禁止静默失败，必须抛出 HTTP 异常或记录 Error 级别日志。
- **Structure**:
  - `src/api`: FastAPI 路由与模型
  - `src/planning`: LangGraph 图定义与 Agent 逻辑
  - `src/infra`: 数据库与外部服务客户端
  - `openspec`: 规格说明书

### Architecture Patterns
- **Separation of Concerns**:
  - **ReAct Agent**: 仅负责意图澄清、工具路由（上层）。
  - **LangGraph**: 负责确定性的业务流程编排（下层）。
- **State Management**: 使用 `TypedDict` 定义 Graph State，使用 `Annotated[List, add_messages]` 处理消息历史。

## Domain Context
- **S1-S4**: 预定义的四大场景（火灾、内涝、危化品、安保）。
- **HTN**: 层次化任务网络，用于任务分解。
- **CSP**: 约束满足问题，用于资源匹配。

## Important Constraints
- **Performance**: 规划过程耗时较长，API 设计需考虑超时或异步轮询机制（当前 v1 暂为同步等待）。
- **Reliability**: 关键节点（如规则检查）失败必须报错，严禁降级为“幻觉”输出。

## External Dependencies
- OpenAI API 兼容接口 (vLLM)
- PostgreSQL (Port 5432)
- Neo4j (Bolt Port 7687)
- Qdrant (GRPC Port 6334)
