# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Emergency Brain API - 应急救援智能决策系统，基于 LangGraph + FastAPI 的多智能体架构。

## 常用命令

### 启动应用
```bash
# 开发模式（热重载）
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

# 健康检查
curl http://localhost:8000/health
```

### 运行测试
```bash
# 全部测试
pytest tests/ -v

# 单元测试
pytest tests/unit/ -v

# E2E测试（需要服务运行）
pytest tests/e2e/ -v

# 单个测试文件
pytest tests/e2e/api/test_01_health.py -v

# 显示print输出
pytest tests/ -s

# 覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 架构概览

```
src/
├── main.py              # FastAPI入口，路由挂载
├── core/                # 基础设施（数据库、配置、异常）
├── domains/             # 业务领域模块（28个）
├── agents/              # AI智能体（22个，基于LangGraph）
├── infra/               # 外部服务客户端（高德、天气等）
└── planning/            # 优化算法（OR-Tools、PyMOO）
```

### 关键模块

| 层级 | 模块 | 职责 |
|------|------|------|
| **Domains** | scenarios, events, tasks, schemes | 核心业务：场景、事件、任务、方案 |
| **Domains** | resources, map_entities, routing | 资源管理、地图实体、路由规划 |
| **Domains** | users, auth, websocket, voice | 用户系统、认证、实时通信、语音 |
| **Agents** | emergency_ai, overall_plan | 主力智能体：应急决策、总体方案 |
| **Agents** | route_planning, recon_scheduler | 路由规划、侦察调度 |
| **Agents** | staging_area, voice_commander | 集结地点、语音指挥 |

### API路由结构

- `/api/v2/*` - 新架构API（主要）
- `/api/v1/*` - 前端适配层（兼容原Java后端）
- `/ws/real-time` - 前端WebSocket
- `/ws/stomp` - STOMP协议WebSocket
- `/ws/voice/chat` - 语音对话WebSocket
- `/health` - 健康检查

## 配置管理

**配置优先级**（从高到低）：
1. `config/private.yaml` - 本地私密配置（已在.gitignore）
2. `.env` - 环境变量文件
3. 代码默认值

**两个配置类**：
- `src/core/config.py` - FastAPI应用配置（数据库、Redis、JWT）
- `src/infra/settings.py` - AI服务配置（LLM、向量库、图数据库）

**关键环境变量**：
```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0

# LLM
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=your-key
LLM_MODEL=gpt-4

# 向量数据库
QDRANT_URL=http://localhost:6333

# 图数据库
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# 高德地图
AMAP_API_KEY=your-key
```

## 技术栈

- **Web框架**: FastAPI + uvicorn（异步）
- **ORM**: SQLAlchemy 2.0（异步） + asyncpg
- **AI框架**: LangChain + LangGraph（智能体编排）
- **向量库**: Qdrant
- **图数据库**: Neo4j
- **缓存**: Redis
- **GIS**: GeoAlchemy2, Shapely, Geopandas
- **优化**: OR-Tools, PyMOO, NetworkX

## 代码规范

### Domain模块结构
每个domain遵循统一结构：
```
domains/xxx/
├── __init__.py      # 导出router
├── router.py        # FastAPI路由
├── service.py       # 业务逻辑
├── repository.py    # 数据访问
├── schemas.py       # Pydantic模型
└── models.py        # SQLAlchemy模型
```

### Agent模块结构
每个agent基于LangGraph：
```
agents/xxx/
├── __init__.py
├── agent.py         # StateGraph定义
├── nodes/           # 节点函数
├── schemas.py       # 状态和消息定义
└── tools.py         # 工具函数
```

## 数据库

- **PostgreSQL**: 主数据库，支持PostGIS地理扩展
- **Redis**: 缓存、消息队列、WebSocket pub/sub
- **Neo4j**: 知识图谱（应急能力、规则关系）
- **Qdrant**: 向量检索（RAG）

## 注意事项

1. **异步优先**: 所有数据库操作使用async/await
2. **两套配置**: `core/config.py`（应用）和 `infra/settings.py`（AI服务）分开管理
3. **前端兼容**: `/api/v1`路由是为了兼容原Java后端接口，修改时注意向后兼容
4. **WebSocket**: 支持STOMP协议和简化版两种模式
