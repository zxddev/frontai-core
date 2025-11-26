# WebSocket接口设计

> 版本: 1.0  
> 创建时间: 2025-11-25  
> 优先级: P0

---

## 一、模块概述

WebSocket提供实时双向通信能力，用于事件推送、任务状态同步、实体位置更新等实时场景。

**核心功能：**
- 频道订阅与取消
- 实时事件推送
- 心跳保活
- 断线重连与消息补发

---

## 二、连接协议

### 2.1 连接地址

```
wss://api.example.com/ws/v2?token={access_token}&scenario_id={scenario_id}
```

### 2.2 认证

连接时通过query参数传递JWT token，服务端验证后建立连接。

### 2.3 消息格式

所有消息使用JSON格式：

**客户端发送消息：**
```json
{
    "type": "subscribe|unsubscribe|ping|ack",
    "channel": "string",
    "data": {},
    "msg_id": "uuid"
}
```

**服务端推送消息：**
```json
{
    "type": "event|ack|pong|error",
    "channel": "string",
    "action": "string",
    "data": {},
    "msg_id": "uuid",
    "timestamp": "2025-11-25T14:30:00Z"
}
```

---

## 三、频道列表

| 频道 | 说明 | 订阅参数 |
|------|------|---------|
| scenarios | 想定状态变更 | scenario_id |
| events | 事件变更 | scenario_id |
| schemes | 方案变更 | scenario_id |
| tasks | 任务变更 | scenario_id, assignee_id(可选) |
| entities | 实体位置更新 | scenario_id, entity_types(可选) |
| messages | 指挥消息 | scenario_id, user_id |
| system | 系统通知 | 无 |

---

## 四、接口详细设计

### 4.1 订阅频道

**客户端发送：**
```json
{
    "type": "subscribe",
    "channel": "events",
    "data": {
        "scenario_id": "scenario-uuid",
        "filters": {
            "priority": ["critical", "high"]
        }
    },
    "msg_id": "msg-001"
}
```

**服务端响应：**
```json
{
    "type": "ack",
    "channel": "events",
    "data": {
        "success": true,
        "subscription_id": "sub-001"
    },
    "msg_id": "msg-001"
}
```

---

### 4.2 取消订阅

**客户端发送：**
```json
{
    "type": "unsubscribe",
    "channel": "events",
    "data": {
        "subscription_id": "sub-001"
    },
    "msg_id": "msg-002"
}
```

---

### 4.3 心跳保活

**客户端发送：** (每30秒)
```json
{
    "type": "ping",
    "msg_id": "ping-001"
}
```

**服务端响应：**
```json
{
    "type": "pong",
    "timestamp": "2025-11-25T14:30:00Z",
    "msg_id": "ping-001"
}
```

---

### 4.4 消息确认

**客户端发送：** (收到重要消息后)
```json
{
    "type": "ack",
    "data": {
        "msg_ids": ["msg-100", "msg-101"]
    }
}
```

---

## 五、推送事件

### 5.1 events频道

**事件创建：**
```json
{
    "type": "event",
    "channel": "events",
    "action": "created",
    "data": {
        "id": "event-uuid",
        "event_code": "EVT-001",
        "title": "建筑倒塌",
        "status": "pending",
        "priority": "critical"
    }
}
```

**事件状态变更：**
```json
{
    "type": "event",
    "channel": "events",
    "action": "status_changed",
    "data": {
        "id": "event-uuid",
        "previous_status": "pending",
        "current_status": "confirmed"
    }
}
```

**预确认倒计时提醒：** (剩余10分钟/5分钟时)
```json
{
    "type": "event",
    "channel": "events",
    "action": "pre_confirm_reminder",
    "data": {
        "id": "event-uuid",
        "expires_at": "2025-11-25T15:00:00Z",
        "minutes_remaining": 10
    }
}
```

---

### 5.2 tasks频道

**任务分配：**
```json
{
    "type": "event",
    "channel": "tasks",
    "action": "assigned",
    "data": {
        "task_id": "task-uuid",
        "task_name": "废墟搜救",
        "assignee_id": "team-001",
        "priority": "critical",
        "deadline_at": "2025-11-25T18:30:00+08:00"
    }
}
```

**任务进度更新：**
```json
{
    "type": "event",
    "channel": "tasks",
    "action": "progress_updated",
    "data": {
        "task_id": "task-uuid",
        "progress_percentage": 50,
        "status_description": "已搜索3层"
    }
}
```

---

### 5.3 entities频道

**位置更新：** (批量，每5秒聚合)
```json
{
    "type": "event",
    "channel": "entities",
    "action": "positions_updated",
    "data": {
        "entities": [
            {
                "entity_id": "entity-001",
                "entity_type": "rescue_team",
                "location": {"lng": 103.851, "lat": 31.682},
                "speed_kmh": 25,
                "heading": 45
            }
        ]
    }
}
```

---

### 5.4 messages频道

**新消息：**
```json
{
    "type": "event",
    "channel": "messages",
    "action": "new_message",
    "data": {
        "id": "message-uuid",
        "from_user": {"id": "user-001", "name": "指挥员A"},
        "message_type": "command",
        "content": "立即转移至北侧集结点",
        "priority": "urgent"
    }
}
```

---

## 六、断线重连

### 6.1 重连流程

1. 客户端检测连接断开
2. 使用指数退避重连（1s, 2s, 4s, 8s, max 30s）
3. 重连时携带 `last_msg_id` 参数
4. 服务端推送断线期间的消息

**重连请求：**
```
wss://api.example.com/ws/v2?token={token}&scenario_id={id}&last_msg_id={msg_id}
```

**消息补发：**
```json
{
    "type": "event",
    "channel": "system",
    "action": "missed_messages",
    "data": {
        "messages": [
            {"channel": "events", "action": "created", "data": {...}},
            {"channel": "tasks", "action": "assigned", "data": {...}}
        ],
        "count": 2,
        "from_msg_id": "last-msg-id"
    }
}
```

### 6.2 last_msg_id机制详解

**客户端职责：**
1. 每次收到服务端消息时，记录`msg_id`到本地存储（localStorage/内存）
2. 断线重连时，将最后收到的`msg_id`作为参数传递
3. 如无`last_msg_id`（首次连接或存储丢失），服务端不补发历史消息

**服务端职责：**
1. 每条推送消息生成唯一`msg_id`（UUID格式）
2. 消息存储在Redis有序集合中，以时间戳为score，保留1小时
3. 收到带`last_msg_id`的重连请求时，查询该ID之后的所有消息并补发
4. 补发消息数量上限100条，超过则只发送最近100条并标记`truncated: true`

**存储结构：**
```
Redis Key: ws:messages:{scenario_id}
Type: Sorted Set
Score: Unix timestamp (毫秒)
Member: JSON序列化的消息内容
TTL: 3600秒 (1小时)
```

**客户端实现示例：**
```javascript
class WSClient {
    constructor() {
        this.lastMsgId = localStorage.getItem('ws_last_msg_id');
    }
    
    onMessage(message) {
        // 记录最后收到的消息ID
        if (message.msg_id) {
            this.lastMsgId = message.msg_id;
            localStorage.setItem('ws_last_msg_id', message.msg_id);
        }
        // 处理消息...
    }
    
    reconnect() {
        const url = `wss://api.example.com/ws/v2?token=${token}&scenario_id=${scenarioId}`;
        const reconnectUrl = this.lastMsgId ? `${url}&last_msg_id=${this.lastMsgId}` : url;
        this.ws = new WebSocket(reconnectUrl);
    }
}
```

**边界情况处理：**
| 场景 | 处理方式 |
|------|---------|
| `last_msg_id`不存在于Redis | 返回`invalid_msg_id`错误，客户端清空本地存储后重连 |
| 断线超过1小时 | 消息已过期，返回`messages_expired`，客户端需主动拉取最新状态 |
| 补发消息过多 | 返回最近100条并标记`truncated: true`，客户端可调用REST API获取完整数据 |

---

## 七、错误处理

**错误消息：**
```json
{
    "type": "error",
    "data": {
        "code": "WS4001",
        "message": "频道不存在",
        "channel": "invalid_channel"
    }
}
```

**错误码：**
| 错误码 | 说明 |
|-------|------|
| WS4001 | 频道不存在 |
| WS4002 | 订阅参数错误 |
| WS4003 | 无权限订阅该频道 |
| WS4004 | 连接超时 |
| WS4005 | 消息格式错误 |

---

## 八、实现要点

### 8.1 频道订阅管理

```python
class ChannelManager:
    def __init__(self):
        self.subscriptions: Dict[str, Set[WebSocket]] = defaultdict(set)
    
    async def subscribe(self, ws: WebSocket, channel: str, filters: dict):
        channel_key = f"{channel}:{filters.get('scenario_id')}"
        self.subscriptions[channel_key].add(ws)
    
    async def broadcast(self, channel: str, scenario_id: str, message: dict):
        channel_key = f"{channel}:{scenario_id}"
        for ws in self.subscriptions[channel_key]:
            await ws.send_json(message)
```

### 8.2 消息持久化（用于补发）

```python
# 消息存储在Redis，保留1小时
async def store_message(scenario_id: str, message: dict):
    msg_id = str(uuid.uuid4())
    message["msg_id"] = msg_id
    await redis.zadd(
        f"ws:messages:{scenario_id}",
        {json.dumps(message): time.time()}
    )
    await redis.expire(f"ws:messages:{scenario_id}", 3600)
    return msg_id
```
