## Context

当前EmergencyAI系统基于"一个事件=一个位置"的假设设计，但真实救援场景中：
- 一个地震事件可能有多个被困点（A楼、B楼、C楼）
- 现场报告通常使用地名而非经纬度
- 人命关天的决策需要指挥员审核后再执行

数据库层面已有完整支持（`rescue_points_v2`、`schemes_v2`、`rescue_point_team_assignments_v2`），但代码实现跳过了这些表。

## Goals / Non-Goals

**Goals:**
- 支持一个事件的多个救援点输入（最多50个）
- 支持地名输入，集成高德地理编码服务
- 为每个救援点生成独立的队伍分配方案
- 完善方案-任务分离流程（AI生成方案 → 审核 → 创建任务）
- 队伍知道具体救援位置和职责

**Non-Goals:**
- 不修改HTN任务分解逻辑（复用现有）
- 不新建独立agent（扩展现有emergency_ai）
- 不修改前端UI（仅后端API变更）
- 不实现方案版本管理（超出当前范围）

## Decisions

### Decision 1: 扩展现有API而非新建endpoint

**选择**: 在现有 `EmergencyAnalyzeRequest` 中增加 `rescue_points` 可选字段

**理由**: 
- 向后兼容，不破坏现有调用方
- 不传 `rescue_points` 时从数据库读取
- 减少API数量，降低维护成本

**备选方案被拒绝**:
- 新建 `/api/v2/ai/emergency-analyze-v2` - 增加维护负担

### Decision 2: 地名解析失败时抛出异常而非降级

**选择**: `resolve_rescue_point_location()` 失败时抛出 `GeocodingError`

**理由**:
- 这是救人的项目，位置错误会导致队伍去错地方
- 降级（如使用默认坐标）会隐藏问题
- 让调用方明确知道地名无法解析，需要提供经纬度

**备选方案被拒绝**:
- 返回None并使用事件中心坐标 - 会导致所有队伍去同一个地方

### Decision 3: 使用CSP求解器处理多对多分配

**选择**: 复用现有 `CapabilityMatcher`（基于OR-Tools CP-SAT）

**理由**:
- 多点位-多队伍分配是典型的约束满足问题
- 需要处理队伍互斥（一个队伍只能去一个点）
- 现有CSP求解器已有完整实现

**备选方案被拒绝**:
- 简单贪心算法 - 无法保证全局最优
- 为每个点独立分配 - 可能导致资源冲突

### Decision 4: 方案状态直接设为approved

**选择**: confirm接口创建的方案状态直接设为 `approved`

**理由**:
- 当前需求是"指挥员点击确认后执行"
- 完整的 draft → pending_review → approved 流程需要前端配合
- 先实现核心功能，后续迭代加入审核流程

**备选方案被拒绝**:
- 实现完整审核流程 - 需要前端同步改动，超出当前范围

## Architecture

### 数据流设计

```
输入请求
├── rescue_points: [
│   {name: "A楼", address: "茂县凤仪镇小学", victims: 30},
│   {name: "B楼", location: {lng: 103.85, lat: 31.67}, victims: 15}
│   ]
│
├── 1. 地名解析
│   ├── A楼: "茂县凤仪镇小学" → 高德API → (103.82, 31.62)
│   └── B楼: 直接使用坐标 (103.85, 31.67)
│
├── 2. 多点资源匹配
│   ├── A楼候选队伍: [搜救1(5km), 搜救2(8km), 医疗1(6km)]
│   └── B楼候选队伍: [搜救2(3km), 搜救3(4km), 医疗2(7km)]
│
├── 3. 全局优化分配
│   ├── A楼 ← 搜救1 + 医疗1 (最近+能力匹配)
│   └── B楼 ← 搜救2 + 搜救3 (搜救2不能同时去两处)
│
├── 4. 生成方案
│   └── schemes_v2: {status: draft, allocations: {...}}
│
├── 5. 指挥员确认
│   └── schemes_v2.status → approved
│
└── 6. 创建任务
    ├── tasks_v2: TSK-001 A楼救援任务 (rescue_point_id=A)
    ├── tasks_v2: TSK-002 B楼救援任务 (rescue_point_id=B)
    ├── task_assignments_v2: 搜救1→TSK-001, 医疗1→TSK-001
    ├── task_assignments_v2: 搜救2→TSK-002, 搜救3→TSK-002
    └── rescue_point_team_assignments_v2: 对应写入
```

### 类型定义

```python
class RescuePointInput(BaseModel):
    """救援点输入"""
    name: str                                    # 点位名称
    address: Optional[str] = None               # 地名（用于地理编码）
    location: Optional[LocationInput] = None    # 坐标
    estimated_victims: int = 0                  # 被困人数
    priority: str = "medium"                    # 优先级

class LocationInput(BaseModel):
    """坐标输入"""
    longitude: float
    latitude: float

class PointAllocation(TypedDict):
    """单个救援点的分配结果"""
    rescue_point_id: str
    rescue_point_name: str
    location: Tuple[float, float]
    estimated_victims: int
    assigned_teams: List[TeamAllocation]
    total_eta_minutes: float

class MultiPointAllocationPlan(TypedDict):
    """多点位分配方案"""
    event_id: str
    rescue_points: List[PointAllocation]
    unassigned_points: List[str]              # 无法分配的点位
    resource_warnings: List[str]              # 资源不足警告
```

## Risks / Trade-offs

### Risk 1: 高德API不可用
- **影响**: 地名无法解析，请求失败
- **缓解**: 
  - 记录详细日志
  - 返回明确错误信息
  - 建议调用方提供经纬度

### Risk 2: 救援点过多导致性能问题
- **影响**: CSP求解时间过长
- **缓解**:
  - 限制最大救援点数量（50个）
  - 设置求解超时（30秒）
  - 超时时返回部分解

### Risk 3: 资源完全不足
- **影响**: 无法为所有救援点分配队伍
- **缓解**:
  - 返回 `unassigned_points` 列表
  - 生成 `resource_warnings` 警告
  - 指挥员知道需要请求增援

## Migration Plan

1. **阶段一（本次实施）**:
   - 实现多救援点输入支持
   - 集成地名解析
   - 修改confirm创建多任务
   - 单元测试覆盖

2. **阶段二（后续迭代）**:
   - 前端支持多点位展示
   - 方案审核流程完善
   - 方案修改功能

3. **回滚方案**:
   - 不传 `rescue_points` 时行为与旧版一致
   - 可通过feature flag禁用多点功能

## Open Questions

1. 救援点数量上限是否需要可配置？
2. 地名解析是否需要缓存以减少API调用？
3. 是否需要支持批量地名解析以提高效率？
