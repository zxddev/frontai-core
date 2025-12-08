# Change: 支持多救援点调度与地名解析

## Why

当前EmergencyAI系统存在**致命架构缺陷**，无法处理真实救援场景：

1. **不支持多救援点**：系统只接受单一事件坐标，无法处理"A楼3人被困、B楼5人被困、C楼2人被困"这种多点位场景
2. **不支持地名输入**：现场报告通常使用地名（如"茂县凤仪镇小学"），但系统只接受经纬度
3. **跳过方案审核流程**：AI推荐直接变成任务，指挥员无法修改方案后再部署
4. **任务粒度太粗**：一个事件只创建一个任务，所有队伍混在一起，不知道具体去哪里救谁
5. **丢失细粒度分配信息**：AI生成的task_description未被使用，assignment_reason都是"AI智能推荐"

**这是救人的项目，当前系统会导致队伍不知道具体救援位置和职责！**

**注意：多事件并行处理由 `add-frontline-rescue-dispatch` 变更专门处理，本变更专注于单事件的多救援点调度。**

## What Changes

### ADDED

**多救援点输入支持**
- `EmergencyAnalyzeRequestV2` 新增 `rescue_points` 数组字段
- `RescuePointInput` 类型定义（支持地名或坐标）
- `_get_rescue_points()` 函数：优先从输入获取，否则从数据库 `rescue_points_v2` 读取

**地名转坐标功能**
- `resolve_rescue_point_location()` 异步函数：集成高德地理编码API
- `GeocodingError` 异常类：地理编码失败时抛出（不降级）
- 地名解析日志：记录每次地理编码调用

**多点位资源匹配**
- `match_resources_multi_point()` 函数：为每个救援点分别计算候选队伍
- `optimize_multi_point_allocation()` 函数：全局多对多最优分配
- 考虑队伍只能分配到一个点、优先级、距离、能力匹配度

**方案审核流程**
- confirm接口写入 `schemes_v2` 表（status=approved）
- 支持 draft → pending_review → approved 状态流转
- 方案修改接口（指挥员可调整队伍分配）

**任务细粒度创建**
- 为每个救援点创建独立任务
- 任务关联 `rescue_point_id`
- 写入 `rescue_point_team_assignments_v2`
- 使用AI生成的 `task_description` 作为分配原因

### MODIFIED

**EmergencyAnalyzeRequest** - `schemas.py`
- 新增 `rescue_points: Optional[List[RescuePointInput]]` 字段
- 向后兼容：不传时从数据库读取

**match_resources** - `matching.py`
- 从单点匹配改为多点匹配
- 调用 `resolve_rescue_point_location()` 处理地名
- 返回 `point_candidates: Dict[str, List[ResourceCandidate]]`

**confirm_emergency_scheme** - `router.py`
- 先创建 `schemes_v2` 记录
- 为每个救援点创建任务
- 使用AI生成的 `task_description`
- 写入 `rescue_point_team_assignments_v2`

## Impact

- **Affected specs**: `emergency-ai`
- **Affected code**:
  - `src/agents/schemas.py` - 请求模型扩展（~50行）
  - `src/agents/emergency_ai/nodes/matching.py` - 多点匹配逻辑（~200行）
  - `src/agents/emergency_ai/nodes/optimization.py` - 多点优化（~100行）
  - `src/agents/router.py` - confirm接口重构（~150行）
- **Affected tables**:
  - `rescue_points_v2` - 读取
  - `schemes_v2` - 写入
  - `task_assignments_v2` - 写入
  - `rescue_point_team_assignments_v2` - 写入
- **Breaking changes**: 无，API向后兼容
- **Dependencies**: 无新增（高德API客户端已存在）

## References

- 高德地理编码服务：`src/infra/clients/amap/geocode.py`（已实现）
- 数据库表定义：`sql/完整sql/operational_v2.sql`
- 现有匹配逻辑：`src/agents/emergency_ai/nodes/matching.py`
