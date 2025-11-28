# 工作日报 - 2025年11月26日

## 一、前端代码改动

### 1.1 登录模块优化 (`src/view/login/index.jsx`)
- 适配新的登录接口响应结构：{ token, userInfo }
- 新增token本地存储
- 字段映射调整：fullName → roleName/realName，id → userId

### 1.2 AI对话功能优化 (`src/view/ai/ai-dialog.jsx`)
- TTS播放完成后自动调用 stopRealtimeChat 收尾
- 优化错误处理：重置loading状态和streamingText
- 加载动画显示逻辑优化：仅在无流式文本时显示loading

### 1.3 地图实体数据流重构
- handleEntity.js / useEntityStream.js / EntityWebSocketClient.js - 实体WebSocket数据处理逻辑调整
- MainMap.jsx - 添加 addAreaPoint 函数的调试日志和图层校验

### 1.4 代理配置调整 (`vite.config.js`)
- 新增 /web-api/ws WebSocket专用代理
- /ws/voice/chat 端口从8008改为8000

### 1.5 其他
- package-lock.json 依赖配置微调

---

## 二、后端Python代码改动

### 2.1 WebSocket/STOMP协议适配

#### 2.1.1 SockJS协议支持 (`src/core/stomp/`)

为适配前端SockJS库，对STOMP协议栈进行全面改造：

| 文件 | 改动 | 说明 |
|------|------|------|
| `router.py` | 新增SockJS端点 | `/stomp/{server_id}/{session_id}/websocket` |
| `connection.py` | 增加sockjs_mode标志 | 支持SockJS消息格式 `a["STOMP帧"]` |
| `frames.py` | 新增to_text()方法 | STOMP帧文本格式序列化 |
| `broker.py` | Redis连接降级 | 连接失败时降级到本地模式 |

**SockJS消息格式适配**：
```python
# SockJS 格式: a["STOMP帧文本"]
stomp_text = frame.to_text()
await websocket.send_text('a' + json.dumps([stomp_text]))
```

#### 2.1.2 前端WebSocket管理器优化 (`src/domains/frontend_api/websocket/router.py`)

- 连接时发送SockJS open帧 `"o"`
- 心跳响应改为SockJS格式 `a["\\n"]`
- STOMP帧发送改为SockJS包装格式
- 增加SockJS消息解包逻辑

### 2.2 事件系统增强

#### 2.2.1 Event模型ENUM强约束 (`src/domains/events/models.py`)

使用PostgreSQL原生ENUM类型替代String字段，强化数据有效性校验：

| ENUM类型 | 字段 | 值域 |
|----------|------|------|
| EventTypeEnum | event_type | earthquake, fire, flood, landslide等13种 |
| EventSourceTypeEnum | source_type | manual_report, ai_detection, sensor_alert等5种 |
| EventStatusEnum | status | pending, pre_confirmed, confirmed等8种 |
| EventPriorityEnum | priority | critical, high, medium, low |

#### 2.2.2 地震事件触发API (`src/domains/frontend_api/event/router.py`)

新增模拟仿真地震触发接口，用于系统测试：

```
POST /events/earthquake/trigger
```

功能：
1. 创建真实事件记录入库
2. 创建地震地图实体（热力图数据）
3. 推送地震动画到WebSocket（前端播放动画+弹窗）
4. 幂等检查：同一想定下相同参数地震只创建一次

**震级-优先级映射**：
- ≥7.0级 → critical（特大地震）
- ≥6.0级 → high
- ≥5.0级 → medium
- <5.0级 → low

### 2.3 实体服务重构 (`src/domains/map_entities/service.py`)

将实体变更通知从旧的websocket模块迁移到STOMP broker：

| 操作 | 旧方式 | 新方式 |
|------|--------|--------|
| 创建 | broadcast_entity_update | stomp_broker.broadcast_entity_create |
| 更新 | broadcast_entity_update | stomp_broker.broadcast_entity_update |
| 删除 | broadcast_entity_update | stomp_broker.broadcast_entity_delete_full |
| 位置 | broadcast_entity_update | stomp_broker.broadcast_location |

**圆形区域特殊处理**：
- 为danger_area、safety_area、command_post_candidate类型补充center和radius字段
- 前端handleEntity.js需要这些字段渲染圆形区域

### 2.4 智能体路由扩展 (`src/agents/router.py`)

新增多个智能体路由和态势标绘API：

| 路由 | 功能 |
|------|------|
| staging_area_agent_router | 驻扎点选址智能体 |
| task_dispatch_router | 任务分发智能体 |
| `/plotting/point` | 标绘点位 |
| `/plotting/circle` | 标绘圆形区域 |
| `/plotting/polygon` | 标绘多边形 |
| `/plotting/route` | 标绘规划路线 |
| `/plotting/event-range` | 标绘事件三层范围 |
| `/plotting/weather` | 标绘天气区域（雨区） |
| `/situation-plot` | 对话式态势标绘 |

### 2.5 预警智能体扩展 (`src/agents/early_warning/`)

#### 2.5.1 LangGraph流程扩展 (`graph.py`)

新增独立风险预测图，支持不走完整预警流程直接调用风险预测：

```
prediction_graph: predict_path_risk → predict_operation_risk → predict_disaster_spread → human_review → END
```

- 红色预警自动触发人工审核（interrupt_before=["human_review"]）
- 支持流程中断等待审核后继续

#### 2.5.2 新增预测节点

| 节点 | 文件 | 功能 |
|------|------|------|
| predict_path_risk | `predict_path_risk.py` | 路径风险预测 |
| predict_operation_risk | `predict_operation_risk.py` | 作业风险评估 |
| predict_disaster_spread | `predict_disaster_spread.py` | 灾害扩散预测 |
| human_review_gate | `human_review.py` | 人工审核节点 |

### 2.6 新模块集成 (`src/main.py`)

| 模块 | 路由 | 功能 |
|------|------|------|
| movement_simulation | movement_router | 移动仿真管理器 |
| simulation | simulation_router | 仿真推演系统 |
| equipment_recommendation | equipment_rec_router | 装备推荐 |

**启动/关闭生命周期**：
- startup: 启动STOMP broker + 移动仿真管理器
- shutdown: 停止移动仿真管理器 + STOMP broker

### 2.7 其他改动

| 文件 | 改动 |
|------|------|
| `src/infra/settings.py` | 高德API Key改为可选配置 |
| `src/core/stomp/broker.py` | 新增broadcast_entity_delete_full方法 |
| `src/domains/staging_area/service.py` | 重构为实例方法模式，遵循调用规范 |

---

## 三、今日产出

| 类别 | 文件数 | 主要改动 |
|------|--------|----------|
| STOMP协议适配 | 4 | SockJS格式支持、Redis降级 |
| 事件系统 | 4 | ENUM强约束、地震触发API |
| 实体服务 | 2 | WebSocket广播重构 |
| 智能体路由 | 3 | 标绘API、新智能体集成 |
| 新模块 | 3 | 仿真系统、装备推荐 |
| **合计** | **约40个文件** | **+2000行 / -970行** |

---

## 四、工作时长

- 上午工作：8:30 - 12:00（3.5小时）
- 下午工作：14:00 - 18:00（4小时）
- 晚间加班：18:00 - 次日01:00（7小时）
- **合计：14.5小时**

---

*报告人：马圣权*
*日期：2025年11月26日*
