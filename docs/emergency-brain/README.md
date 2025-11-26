# 应急救灾AI大脑 - 技术文档

> **frontai-core** - 应急救灾AI指挥系统后端核心  
> 版本: 2.0 | 更新时间: 2025-11-25

---

## 📚 文档目录

| 文档 | 说明 |
|-----|------|
| [01_project_structure.md](./01_project_structure.md) | 项目结构设计 |
| [02_business_workflow.md](./02_business_workflow.md) | 业务流程设计 |
| [03_third_party_api.md](./03_third_party_api.md) | 第三方接口设计 |
| [04_algorithm_rules_design.md](./04_algorithm_rules_design.md) | 算法与规则设计 |
| [接口设计/](./接口设计/) | 接口与集成业务流程 |

---

## 🎯 系统概述

本系统是应急救灾AI指挥系统的后端核心，主要功能：

- **灾情接入** - 接收第三方系统、传感器、AI识别的灾情数据
- **智能分析** - AI自动分析事件严重程度、影响范围
- **方案生成** - AI生成救援方案，智能匹配资源，生成推荐理由
- **任务调度** - 方案转化为具体任务，分配执行者，路径规划
- **实时追踪** - 设备遥测、任务进度、状态变更实时推送
- **仿真演练** - 独立仿真模块，支持多场景演练

---

## 🏗️ 技术栈

| 类别 | 技术 | 版本 |
|-----|------|------|
| 运行时 | Python | ≥3.11 |
| Web框架 | FastAPI | ≥0.115.0 |
| AI框架 | LangChain | ≥1.0.0 |
| Agent编排 | LangGraph | ≥0.3.27 |
| 数据库 | PostgreSQL + PostGIS | 15+ |
| 缓存 | Redis | 7+ |
| 向量库 | Qdrant | 1.12+ |

---

## 📊 核心业务流程

```
想定(Scenario)
    ↓
事件(Event) ← 第三方上报/AI识别/传感器告警
    ↓
┌─────────────────┐
│ 事件分析Agent   │ → 分类、评估、摘要
└────────┬────────┘
         ↓
方案(Scheme)
    ↓
┌─────────────────┐
│ 方案生成Agent   │ → 需求分析、资源匹配、方案优化
└────────┬────────┘
         ↓
┌─────────────────┐
│ 资源匹配Agent   │ → 评分、排序、生成推荐理由
└────────┬────────┘
         ↓
方案审批 → 人工确认/修改
    ↓
任务(Task)
    ↓
┌─────────────────┐
│ 任务调度Agent   │ → 任务拆解、执行分配、路径规划
└────────┬────────┘
         ↓
执行追踪 → WebSocket实时推送
```

---

## 📁 数据库设计

SQL脚本位于 `/sql/` 目录：

| 文件 | 说明 |
|-----|------|
| v2_rescue_resource_model.sql | 救援资源模型（想定、队伍、装备） |
| v2_road_network_model.sql | 道路网络模型（路径规划） |
| v2_vehicle_device_model.sql | 车辆设备模型（4层装载） |
| v2_task_dispatch_model.sql | 任务调度模型 |
| v2_user_permission_model.sql | 用户权限模型 |
| v2_layer_entity_model.sql | 图层实体模型（前端兼容） |
| v2_event_scheme_model.sql | 事件方案模型（核心） |
| v2_environment_model.sql | 环境数据模型（天气、通信、安置点） |
| v2_conversation_message_model.sql | 对话消息模型 |

---

## 🔌 第三方接入

| 接口 | 路径 | 说明 |
|-----|------|------|
| 灾情上报 | POST /api/v2/integrations/disaster-report | 接收灾情数据 |
| 传感器告警 | POST /api/v2/integrations/sensor-alert | IoT告警 |
| 设备遥测 | POST /api/v2/integrations/telemetry | 实时位置 |
| 天气数据 | POST /api/v2/integrations/weather | 气象数据 |

详见 [03_third_party_api.md](./03_third_party_api.md)

---

## 🤖 AI Agent设计

| Agent | 职责 |
|-------|-----|
| EventAnalysisAgent | 事件分类、严重度评估、影响范围估算 |
| SchemeGenerationAgent | 需求分析、资源匹配、方案生成 |
| ResourceMatchingAgent | 能力/距离/可用性评分、生成推荐理由 |
| TaskDispatchAgent | 任务拆解、执行者分配、路径规划 |
| Orchestrator | 多Agent协调编排 |

---

## 🎮 仿真模块

独立模块，支持：
- 多场景（地震、洪水、火灾）
- 时间倍速控制
- 事件注入
- 设备轨迹模拟

---

## 📞 联系

如有问题，请联系项目负责人。
