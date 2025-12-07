## Context
- 侦察Agent需满足救援实时性：流式情报、可中断/恢复、安全优先；避免线性批处理与2D假设带来的安全风险。
- 环境约束：3D 地形/障碍、通信盲区、恶劣天气、动态能耗；需坐标一致性（WGS84 I/O, UTM core）。
- 数据契约：控制流(航线) vs 业务流(情报事件, confidence/source/SRID)，写入 PostGIS/world-model 与消息总线。
- 当前系统为模拟演示系统，需为后期真实数据接入预留接口。

## Goals
- 定义 Recon Agent V2.1 规范：流式事件、分级验证、重试+熔断+人工授权降级、强制中继、动态能耗、Checkpoint/Resume、性能护栏、紧急RTH。
- 固化坐标/高程标准与数据契约，确保实现可验证、可观测。
- 建立模拟数据与真实数据的切换机制，便于后期接入。

## Non-Goals
- 不定义具体前端UI/可视化。
- 不绑定具体硬件SDK（DJI等仍以"DJI-like"抽象）。
- 不实现代码（本变更仅为规范）。
- 不实现自动降级（所有降级需人工授权）。

## Key Decisions

### 1) 分级验证 (L1/L2)
- L1 快速验证(2.5D/禁飞/粗能耗)，500ms内完成
- L2 精算验证(3D/DEM/体素+动态能耗)，5s内完成
- L2仅作用于最终候选方案
- 超时视为验证失败

### 2) 安全优先：Fail-Safe + Human-Authorized Degradation
- **核心原则**：不自动降级，所有降级需人工授权
- State 持 `retry_count/max_retries/approval_status`
- 超预算进入安全模式（悬停/RTH），等待人工决策
- 人工可授权降级策略（降高度/换机型/减覆盖），授权后执行
- 授权超时（默认300s）自动RTH
- 复用现有 `circuit_breaker.py` 控制重试

### 3) 紧急RTH机制
- 电量低于RTH阈值+10%时强制RTH
- 信号丢失30s且无中继点时RTH
- 硬件故障时RTH
- RTH路径使用路由栈逆向避障
- 逆向路径受阻时爬升后直飞

### 4) 强制中继 (No Blind Flight)
- 预测盲区时插入 Relay，沿原路回"最近可视点"
- 上传数据等待ACK，60s超时后重试3次
- 重试失败后尝试爬升改善信号
- 仍失败则触发紧急RTH
- 禁用盲飞延迟回传

### 5) 坐标标准 (CTS-2025)
- I/O WGS84，核心 UTM；State 记录 utm_zone
- 统一高程基准（EGM96大地水准面）
- 跨zone任务使用中心点所在zone
- 转换工具集中在 `core/coord_transform.py`
- 复用已安装的 pyproj>=3.6.0

### 6) 动态能耗模型
- 公式：E_total = E_base * k_wind * k_temp * k_payload * k_age + E_climb + E_hover
- 风速系数：k_wind = 1 + 0.5 * headwind / cruise_speed
- 温度系数：k_temp = 1.3(<0°C) / 1.1(>35°C) / 1.0(其他)
- 老化系数：k_age = 1 + cycle_count/500 * 0.2
- 同一模型在 DeviceSelector/Validation/Simulator 共用
- RTH冗余：1.3安全系数 + 10%余量

### 7) 数据契约
- 控制流=DJI-like waypoints/KML
- 业务流=DDLP JSON（id/type/geom/confidence/source/timestamp/SRID）
- priority=base_priority * confidence
- 写 STOMP Broker + PostGIS
- 事件幂等性：event_id唯一，重复忽略

### 8) Checkpoint/Resume
- 包含进度、断点、覆盖掩膜(UTM)、环境快照、缓存情报
- 存储：Redis(TTL 24h) + PostgreSQL备份
- Resume需获取分布式锁，防止并发
- Resume先Re-Plan再继续

### 9) 性能护栏
- L2仅最终候选
- 并发限制：L2最多3个，设备规划最多5个
- 限流：单设备2次/分钟，L2总计10次/分钟
- 超时：L1=500ms, L2=5s, 单设备=30s, 全任务=120s

### 10) 流式事件发射
- 事件类型：PERCEPTION/HEALTH/PLAN/CHECKPOINT
- 实时写 STOMP（复用 stomp_broker.broadcast_event）
- 持久化写 PostGIS（复用 EventService）
- 网络断开时本地缓冲（最多1000条）

### 11) 模拟数据策略
- 模拟数据单独存放：`recon_scheduler/mock_data/`
- Provider接口抽象：支持Mock/Real切换
- 数据文件：
  - `comm_coverage.json` - 通信覆盖
  - `device_profiles.json` - 设备参数
  - `weather_conditions.json` - 天气条件
- 后期接入真实数据只需实现新Provider

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|---------|
| 3D校验性能开销 | L1/L2漏斗、限流、仅最终候选执行L2 |
| 盲区回传失败 | Relay回溯→爬升→RTH三级fallback |
| 人工授权延迟 | 300s超时自动RTH，保证安全 |
| 坐标/高程不一致 | CTS-2025强制、集中转换、State记录zone |
| 动态能耗模型误差 | 统一函数+冗余校验+保守估计(1.3安全系数) |
| 递归/回溯死锁 | 路由栈回溯+超时+重试上限+最终RTH兜底 |
| 模拟数据与真实差距 | Provider接口隔离，便于切换 |

## Reusable Components

| 组件 | 路径 | 复用方式 |
|------|------|---------|
| 灾情分析子图 | `shared/disaster_analysis.py` | 直接复用 |
| 优先级打分 | `shared/priority_scoring.py` | 复用于目标排序 |
| GIS服务 | `services/gis_service.py` | 复用模拟数据模式 |
| 熔断器 | `utils/circuit_breaker.py` | 复用于重试控制 |
| STOMP Broker | `core/stomp/broker.py` | 复用于事件广播 |
| Event Service | `domains/events/service.py` | 复用于PostGIS持久化 |
| DEM处理 | `planning/algorithms/routing/offroad_engine.py` | 复用rasterio读取 |
| 仿真框架 | `domains/simulation/` | 复用离散事件仿真 |
| recon_scheduler | `agents/recon_scheduler/` | 扩展而非新建 |

## Migration Plan
- 扩展现有 `recon_scheduler` agent，不新建独立agent
- 新增 `mock_data/` 目录存放模拟数据
- 新增 Provider 接口支持数据源切换
- 按 Sprint 逐步实现，每个Sprint可独立验证

## Open Questions
- 通信盲区栅格分辨率与来源：当前使用模拟数据，后期接入真实服务时需确定精度
- 电池健康数据接口：当前模拟，后期需对接设备管理系统
- DEM数据高程基准确认：需确认 `data/四川省.tif` 的具体基准
