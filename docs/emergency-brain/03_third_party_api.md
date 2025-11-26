# 应急救灾AI大脑 - 第三方接口设计

> 版本: 2.0  
> 更新时间: 2025-11-25

---

## 1. 接口总览

| 接口名称 | 路径 | 方法 | 说明 |
|---------|------|------|------|
| 灾情上报 | `/api/v2/integrations/disaster-report` | POST | 接收第三方系统灾情 |
| 传感器告警 | `/api/v2/integrations/sensor-alert` | POST | 接收IoT传感器数据 |
| 设备遥测 | `/api/v2/integrations/telemetry` | POST | 接收设备实时数据 |
| 天气数据 | `/api/v2/integrations/weather` | POST | 接收气象数据 |
| 回调通知 | `/api/v2/integrations/callback` | POST | 接收外部系统回调 |

---

## 2. 灾情上报接口

### 2.1 接口说明

接收第三方系统（如110报警系统、社区上报系统、AI识别系统）推送的灾情信息。

### 2.2 请求

**URL:** `POST /api/v2/integrations/disaster-report`

**Headers:**
```http
Content-Type: application/json
X-Source-System: 110-alarm-system    # 来源系统标识
X-Api-Key: your-api-key              # API密钥
X-Request-Id: uuid                   # 请求ID（用于追踪）
X-Timestamp: 1732536000              # 请求时间戳
X-Signature: hmac-sha256-signature   # 签名（可选）
```

**请求体:**
```json
{
    // ========== 必填字段 ==========
    "disaster_type": "trapped_person",       // 灾情类型
    "location": {
        "longitude": 104.0657,               // 经度
        "latitude": 30.5728,                 // 纬度
        "address": "四川省成都市武侯区xxx路xx号", // 地址描述
        "accuracy_meters": 10                // 定位精度(米)
    },
    "description": "建筑倒塌，有人员被困，急需救援", // 灾情描述
    
    // ========== 来源标识（用于去重） ==========
    "source_system": "110-alarm-system",     // 来源系统
    "source_event_id": "ALARM-2025112500001", // 来源系统事件ID
    
    // ========== 可选字段 ==========
    "priority": "high",                      // 优先级: critical/high/medium/low
    "estimated_victims": 3,                  // 预估受困人数
    "affected_radius_meters": 50,            // 影响半径(米)
    "occurred_at": "2025-11-25T10:30:00Z",   // 事件发生时间
    
    // ========== 媒体附件 ==========
    "media_urls": [
        "https://example.com/image1.jpg",
        "https://example.com/video1.mp4"
    ],
    
    // ========== 上报人信息 ==========
    "reporter": {
        "name": "张三",
        "phone": "13800138000",
        "type": "witness"                    // witness/victim/official
    },
    
    // ========== 扩展元数据 ==========
    "metadata": {
        "building_type": "residential",
        "floor_count": 6,
        "collapse_area_sqm": 200
    }
}
```

**灾情类型枚举 (disaster_type):**
```
trapped_person      - 被困人员
fire                - 火灾
flood               - 洪水
landslide           - 滑坡
building_collapse   - 建筑倒塌
road_damage         - 道路损毁
power_outage        - 电力中断
communication_lost  - 通信中断
hazmat_leak         - 危化品泄漏
epidemic            - 疫情
earthquake_secondary - 地震次生灾害
other               - 其他
```

### 2.3 响应

**成功响应 (HTTP 201):**
```json
{
    "success": true,
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_code": "EVT-20251125-0001",
    "status": "pending",                    // pending/confirmed/duplicate
    "message": "灾情已接收，等待确认",
    "entity_id": "660e8400-e29b-41d4-a716-446655440001",  // 地图实体ID
    "created_at": "2025-11-25T10:31:00Z",
    "duplicate_of": null                    // 如果是重复上报，返回原事件ID
}
```

**重复上报响应 (HTTP 200):**
```json
{
    "success": true,
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_code": "EVT-20251125-0001",
    "status": "duplicate",
    "message": "该灾情已存在，已合并到现有事件",
    "duplicate_of": "440e8400-e29b-41d4-a716-446655440000"
}
```

**错误响应 (HTTP 4xx/5xx):**
```json
{
    "success": false,
    "error_code": "INVALID_LOCATION",
    "message": "经纬度坐标无效",
    "details": {
        "field": "location.longitude",
        "reason": "经度必须在-180到180之间"
    },
    "request_id": "req-uuid"
}
```

### 2.4 错误码

| 错误码 | HTTP状态 | 说明 |
|-------|---------|------|
| INVALID_REQUEST | 400 | 请求格式错误 |
| MISSING_REQUIRED_FIELD | 400 | 缺少必填字段 |
| INVALID_LOCATION | 400 | 位置信息无效 |
| INVALID_DISASTER_TYPE | 400 | 灾情类型无效 |
| UNAUTHORIZED | 401 | 认证失败 |
| INVALID_SIGNATURE | 401 | 签名验证失败 |
| RATE_LIMITED | 429 | 请求频率超限 |
| INTERNAL_ERROR | 500 | 服务内部错误 |

---

## 3. 传感器告警接口

### 3.1 接口说明

接收IoT传感器（地震仪、水位计、烟雾报警器等）的告警数据。

### 3.2 请求

**URL:** `POST /api/v2/integrations/sensor-alert`

**请求体:**
```json
{
    // ========== 必填字段 ==========
    "sensor_id": "SENSOR-EQ-001",           // 传感器ID
    "sensor_type": "seismometer",            // 传感器类型
    "alert_type": "earthquake",              // 告警类型
    "alert_level": "warning",                // 告警级别: info/warning/critical
    "location": {
        "longitude": 104.0657,
        "latitude": 30.5728
    },
    "readings": {                            // 传感器读数
        "magnitude": 4.5,                    // 震级
        "depth_km": 10,                      // 震源深度
        "intensity": "V"                     // 烈度
    },
    "triggered_at": "2025-11-25T10:30:00Z", // 触发时间
    
    // ========== 可选字段 ==========
    "source_system": "iot-platform",
    "raw_data": "base64-encoded-raw-data",   // 原始数据
    "metadata": {}
}
```

**传感器类型枚举 (sensor_type):**
```
seismometer         - 地震仪
water_level_gauge   - 水位计
smoke_detector      - 烟雾报警器
gas_detector        - 燃气探测器
temperature_sensor  - 温度传感器
rain_gauge          - 雨量计
displacement_sensor - 位移传感器
other               - 其他
```

### 3.3 响应

```json
{
    "success": true,
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_id": "660e8400-e29b-41d4-a716-446655440001",  // 关联的事件ID
    "action_taken": "event_created",         // event_created/merged/ignored
    "message": "告警已处理，已创建事件"
}
```

---

## 4. 设备遥测接口

### 4.1 接口说明

接收无人设备（无人机、机器狗、无人船）的实时遥测数据。

### 4.2 请求

**URL:** `POST /api/v2/integrations/telemetry`

**请求体 (单条):**
```json
{
    "device_id": "UAV-001",
    "device_type": "uav",                    // uav/ugv/usv/vehicle
    "telemetry_type": "location",            // location/battery/speed/status/sensor
    "payload": {
        "longitude": 104.0657,
        "latitude": 30.5728,
        "altitude": 120,                     // 高度(米)
        "heading": 45,                       // 航向(度)
        "ground_speed": 15.5,                // 地速(m/s)
        "accuracy": 2                        // 定位精度(米)
    },
    "device_timestamp": "2025-11-25T10:30:00.123Z",
    "sequence_no": 12345                     // 序列号
}
```

**批量请求:**
```json
{
    "batch": [
        { /* 遥测数据1 */ },
        { /* 遥测数据2 */ },
        { /* 遥测数据3 */ }
    ]
}
```

**遥测类型 (telemetry_type):**
```
location  - 位置信息
battery   - 电池状态 {level, voltage, temperature, charging}
speed     - 速度信息 {ground_speed, air_speed, vertical_speed}
altitude  - 高度信息 {absolute, relative, terrain}
status    - 设备状态 {state, mode, errors[]}
sensor    - 传感器数据 {sensor_type, readings[]}
```

### 4.3 响应

```json
{
    "success": true,
    "received_count": 3,
    "processed_count": 3,
    "entity_updates": [                      // 已更新的地图实体
        {
            "device_id": "UAV-001",
            "entity_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    ]
}
```

---

## 5. 天气数据接口

### 5.1 接口说明

接收气象部门推送的天气数据和预警信息。

### 5.2 请求

**URL:** `POST /api/v2/integrations/weather`

**请求体:**
```json
{
    "area_id": "510107",                     // 区域编码
    "area_name": "四川省成都市武侯区",
    "coverage_area": {                       // GeoJSON Polygon
        "type": "Polygon",
        "coordinates": [[[104.0, 30.5], [104.1, 30.5], ...]]
    },
    "weather_type": "heavy_rain",            // 天气类型
    "temperature": 25.5,                     // 温度
    "wind_speed": 8.5,                       // 风速(m/s)
    "wind_direction": 180,                   // 风向(度)
    "visibility": 5000,                      // 能见度(米)
    "precipitation": 30.5,                   // 降水量(mm/h)
    "humidity": 85,                          // 湿度(%)
    "pressure": 1013.25,                     // 气压(hPa)
    
    // ========== 预警信息 ==========
    "alerts": [
        {
            "type": "rainstorm",
            "level": "orange",               // blue/yellow/orange/red
            "message": "暴雨橙色预警",
            "issued_at": "2025-11-25T10:00:00Z",
            "valid_until": "2025-11-25T22:00:00Z"
        }
    ],
    
    // ========== 预报数据 ==========
    "forecast": [
        {
            "hour": 1,
            "weather_type": "heavy_rain",
            "temperature": 24,
            "wind_speed": 10,
            "precipitation": 40
        }
    ],
    
    "recorded_at": "2025-11-25T10:30:00Z",
    "valid_until": "2025-11-25T11:00:00Z",
    "data_source": "meteorological_bureau"
}
```

### 5.3 响应

```json
{
    "success": true,
    "weather_id": "550e8400-e29b-41d4-a716-446655440000",
    "uav_flyable": false,                    // 是否适合无人机飞行
    "uav_restriction_reason": "风速超过8m/s，不建议飞行",
    "active_alerts_count": 1
}
```

---

## 6. 认证与安全

### 6.1 API密钥认证

```http
X-Api-Key: your-api-key-here
```

### 6.2 签名验证（可选）

对于安全性要求高的接入方，支持HMAC-SHA256签名验证：

**签名生成:**
```python
import hmac
import hashlib
import json

def generate_signature(secret_key: str, timestamp: str, body: dict) -> str:
    message = f"{timestamp}:{json.dumps(body, separators=(',', ':'), sort_keys=True)}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
```

**请求头:**
```http
X-Timestamp: 1732536000
X-Signature: generated-signature
```

### 6.3 IP白名单

生产环境可配置IP白名单，仅允许授权IP访问。

### 6.4 请求频率限制

| 接口 | 限制 |
|-----|------|
| 灾情上报 | 100次/分钟 |
| 传感器告警 | 500次/分钟 |
| 设备遥测 | 1000次/分钟 |
| 天气数据 | 60次/分钟 |

---

## 7. 去重策略

### 7.1 来源去重

基于 `source_system` + `source_event_id` 组合，相同组合视为重复。

### 7.2 位置时间去重

同一位置（100米范围内）+ 同一时间窗口（1小时内）+ 相同灾情类型，视为重复。

```python
def is_duplicate(new_event, existing_events):
    for event in existing_events:
        if (
            distance(new_event.location, event.location) < 100  # 100米内
            and abs(new_event.time - event.time) < timedelta(hours=1)  # 1小时内
            and new_event.disaster_type == event.disaster_type  # 相同类型
        ):
            return True, event.id
    return False, None
```

### 7.3 去重响应

重复事件不会创建新记录，而是：
1. 返回已存在事件的ID
2. 将新上报信息作为更新附加到已有事件
3. 在 `event_updates_v2` 中记录

---

## 8. WebSocket推送（给前端）

### 8.1 连接

```javascript
const ws = new WebSocket('wss://api.example.com/ws/v2/realtime');

ws.onopen = () => {
    // 订阅频道
    ws.send(JSON.stringify({
        action: 'subscribe',
        channels: ['events', 'entities', 'tasks'],
        scenario_id: 'scenario-uuid'
    }));
};
```

### 8.2 消息格式

```json
{
    "channel": "events",
    "action": "created",                     // created/updated/deleted
    "timestamp": "2025-11-25T10:31:00Z",
    "data": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "event_code": "EVT-20251125-0001",
        "disaster_type": "trapped_person",
        "status": "pending",
        "location": {
            "type": "Point",
            "coordinates": [104.0657, 30.5728]
        },
        "priority": "high"
    }
}
```

### 8.3 频道类型

| 频道 | 说明 |
|-----|------|
| events | 事件变更 |
| entities | 地图实体变更 |
| tasks | 任务状态变更 |
| schemes | 方案变更 |
| telemetry | 实时遥测数据 |
| messages | 指挥消息 |
| alerts | 系统告警 |

---

## 9. 接口调用示例

### 9.1 Python示例

```python
import httpx
import json
from datetime import datetime

async def report_disaster():
    url = "https://api.example.com/api/v2/integrations/disaster-report"
    
    headers = {
        "Content-Type": "application/json",
        "X-Source-System": "community-report",
        "X-Api-Key": "your-api-key",
        "X-Request-Id": "req-12345"
    }
    
    payload = {
        "disaster_type": "fire",
        "location": {
            "longitude": 104.0657,
            "latitude": 30.5728,
            "address": "成都市武侯区xxx路xx号"
        },
        "description": "3楼住户家中起火，有浓烟冒出",
        "source_system": "community-report",
        "source_event_id": "CR-2025112500001",
        "priority": "high",
        "reporter": {
            "name": "李四",
            "phone": "13900139000",
            "type": "witness"
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        result = response.json()
        
        if result["success"]:
            print(f"上报成功，事件ID: {result['event_id']}")
        else:
            print(f"上报失败: {result['message']}")

```

### 9.2 cURL示例

```bash
curl -X POST https://api.example.com/api/v2/integrations/disaster-report \
  -H "Content-Type: application/json" \
  -H "X-Source-System: 110-alarm" \
  -H "X-Api-Key: your-api-key" \
  -d '{
    "disaster_type": "trapped_person",
    "location": {
      "longitude": 104.0657,
      "latitude": 30.5728,
      "address": "成都市武侯区xxx路"
    },
    "description": "建筑倒塌，有人被困",
    "source_system": "110-alarm",
    "source_event_id": "ALARM-001",
    "priority": "critical",
    "estimated_victims": 3
  }'
```

---

## 10. 仿真数据推送

### 10.1 仿真控制API

**启动仿真:**
```http
POST /api/v2/simulation/start
{
    "scenario_id": "scenario-uuid",
    "scenario_type": "earthquake",           // earthquake/flood/fire
    "speed_multiplier": 2.0,                 // 时间倍速
    "auto_generate_events": true
}
```

**暂停仿真:**
```http
POST /api/v2/simulation/pause
{
    "scenario_id": "scenario-uuid"
}
```

**注入事件:**
```http
POST /api/v2/simulation/inject-event
{
    "scenario_id": "scenario-uuid",
    "event": {
        "disaster_type": "fire",
        "location": { ... },
        "description": "模拟火灾事件"
    }
}
```

### 10.2 仿真数据流

```
仿真引擎(SimulationEngine)
         │
         ├── EventGenerator ──→ 生成模拟事件 ──→ EventService ──→ DB + WebSocket
         │
         ├── TelemetryGenerator ──→ 生成设备遥测 ──→ TelemetryService ──→ DB + WebSocket
         │
         └── EntityGenerator ──→ 更新实体位置 ──→ EntityService ──→ DB + WebSocket
                                                        │
                                                        ↓
                                                   前端地图实时更新
```

### 10.3 预设场景

| 场景 | 说明 |
|-----|------|
| earthquake | 地震场景：震中、余震、建筑倒塌、人员被困 |
| flood | 洪水场景：水位上升、道路中断、人员转移 |
| fire | 火灾场景：火点蔓延、烟雾扩散、人员疏散 |
| multi_disaster | 复合灾害：地震引发火灾和滑坡 |
