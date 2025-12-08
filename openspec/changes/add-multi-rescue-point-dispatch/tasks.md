## 0. 数据库准备（P0-前置条件，用户执行）
- [ ] 0.1 提供SQL迁移脚本 `sql/migrations/v20251207_add_rescue_point_id_to_tasks.sql`
- [ ] 0.2 用户执行SQL迁移脚本
- [ ] 0.3 验证 `tasks_v2.rescue_point_id` 列已创建

**SQL迁移内容：**
```sql
-- 为tasks_v2表添加rescue_point_id列，关联救援点
ALTER TABLE operational_v2.tasks_v2 
ADD COLUMN IF NOT EXISTS rescue_point_id uuid 
REFERENCES operational_v2.rescue_points_v2(id);

COMMENT ON COLUMN operational_v2.tasks_v2.rescue_point_id 
IS '关联的救援点ID，用于多点位救援任务';

CREATE INDEX IF NOT EXISTS idx_tasks_v2_rescue_point_id 
ON operational_v2.tasks_v2(rescue_point_id);
```

## 1. Schema & Type Definitions
- [ ] 1.1 在 `schemas.py` 新增 `LocationInput` 类型定义：
  ```python
  class LocationInput(BaseModel):
      longitude: float = Field(..., ge=-180, le=180)
      latitude: float = Field(..., ge=-90, le=90)
  ```
- [ ] 1.2 在 `schemas.py` 新增 `RescuePointInput` 类型定义：
  ```python
  class RescuePointInput(BaseModel):
      name: str = Field(..., min_length=1, max_length=200)
      address: Optional[str] = Field(None, max_length=500)
      location: Optional[LocationInput] = None
      estimated_victims: int = Field(0, ge=0)
      priority: str = Field("medium", pattern="^(critical|high|medium|low)$")
  ```
- [ ] 1.3 修改 `EmergencyAnalyzeRequest` 增加字段：
  ```python
  rescue_points: Optional[List[RescuePointInput]] = Field(
      default=None,
      max_length=50,  # 最多50个救援点
      description="救援点列表，为空时从数据库读取"
  )
  ```
- [ ] 1.4 在 `state.py` 新增 `ResolvedRescuePoint` TypedDict：
  ```python
  class ResolvedRescuePoint(TypedDict):
      point_id: str
      name: str
      latitude: float
      longitude: float
      estimated_victims: int
      priority: str
      source: str  # 'input' | 'database'
  ```
- [ ] 1.5 在 `state.py` 新增 `PointAllocation` TypedDict
- [ ] 1.6 在 `state.py` 新增 `MultiPointAllocationPlan` TypedDict
- [ ] 1.7 在 `EmergencyAIState` 新增字段：
  ```python
  rescue_points: List[Dict[str, Any]]                    # 输入的救援点
  resolved_rescue_points: List[ResolvedRescuePoint]      # 解析后的救援点
  point_candidates: Dict[str, List[ResourceCandidate]]   # 每个点的候选队伍
  point_allocations: Dict[str, PointAllocation]          # 每个点的分配结果
  ```
- [ ] 1.8 更新 `create_initial_state()` 函数初始化新字段

## 2. Geocoding Integration
- [ ] 2.1 在 `matching.py` 新增 `GeocodingError` 异常类（继承Exception）
- [ ] 2.2 实现 `resolve_rescue_point_location()` 异步函数：
  - 参数：`point: RescuePointInput`
  - 返回：`Tuple[float, float]` (lat, lng)
  - 逻辑：坐标优先，否则调用 `amap_geocode_async()`
  - 失败时抛出 `GeocodingError`（不降级）
  - 添加INFO日志记录每次解析
- [ ] 2.3 实现 `_resolve_all_rescue_point_locations()` 函数：
  - 参数：`points: List[RescuePointInput]`
  - 返回：`List[ResolvedRescuePoint]`
  - 批量解析所有点位
- [ ] 2.4 为地名解析编写单元测试（成功/失败/超时场景）

## 3. Rescue Points Loading
- [ ] 3.1 实现 `_get_rescue_points_from_input()` 函数：
  - 从 `state["structured_input"]["rescue_points"]` 解析
  - 校验数量上限50个
- [ ] 3.2 实现 `_get_rescue_points_from_db()` 异步函数：
  - 从 `rescue_points_v2` 表查询 `WHERE event_id = :event_id`
  - 返回空列表时不报错（向后兼容）
- [ ] 3.3 实现 `_get_rescue_points()` 函数：
  - 优先使用输入
  - 无输入时查数据库
  - 都无则使用事件位置作为单一救援点
- [ ] 3.4 为救援点加载逻辑编写测试

## 4. Multi-Point Resource Matching
- [ ] 4.1 实现 `_query_candidates_for_point()` 异步函数：
  - 为单个救援点查询候选队伍
  - 计算距离、ETA、能力匹配度
- [ ] 4.2 实现 `match_resources_multi_point()` 异步函数：
  - 获取所有救援点
  - 为每个点查询候选队伍
  - 更新 `state["point_candidates"]`
- [ ] 4.3 修改 `match_resources()` 调用多点匹配逻辑
- [ ] 4.4 保持单点场景向后兼容
- [ ] 4.5 编写多点匹配的集成测试

## 5. Multi-Point Optimization
- [ ] 5.1 实现 `_build_multi_point_assignment_problem()` 函数：
  - 构建多点位-多队伍分配问题
  - 约束：每个队伍最多分配到一个点
  - 目标：最小化总响应时间
- [ ] 5.2 实现 `optimize_multi_point_allocation()` 函数：
  - 调用现有 `CapabilityMatcher` 或 OR-Tools
  - 处理无解情况（返回部分解+警告）
  - 设置求解超时（30秒）
  - 更新 `state["point_allocations"]`
- [ ] 5.3 修改 `optimize_allocation()` 调用多点优化
- [ ] 5.4 编写优化测试（正常/资源不足/超时）

## 6. Output Generation
- [ ] 6.1 修改 `generate_output()` 按救援点分组输出
- [ ] 6.2 输出结构包含：
  ```python
  {
      "rescue_points": [
          {
              "point_id": "...",
              "name": "A楼",
              "location": {...},
              "estimated_victims": 30,
              "assigned_teams": [...],
              "total_eta_minutes": 15.5
          }
      ],
      "unassigned_points": [...],
      "resource_warnings": [...]
  }
  ```
- [ ] 6.3 编写输出格式测试

## 7. Confirm Interface Refactor
- [ ] 7.1 修改 `confirm_emergency_scheme()` 创建 `schemes_v2` 记录：
  - `scheme_code`: 格式 `SCH-{YYYYMMDD}-{seq:04d}`
  - `scheme_type`: `'rescue'`
  - `status`: `'approved'`
  - `source`: `'ai_generated'`
  - `ai_reasoning`: 存储AI分析摘要
- [ ] 7.2 为每个救援点创建 `tasks_v2` 记录：
  - `task_code`: 格式 `TSK-{seq:04d}`
  - `title`: `"{point_name}救援任务（{victims}人被困）"`
  - `rescue_point_id`: 关联救援点
  - `scheme_id`: 关联方案
- [ ] 7.3 创建 `task_assignments_v2` 使用AI的 `task_description`
- [ ] 7.4 写入 `rescue_point_team_assignments_v2` 表
- [ ] 7.5 每个任务独立生成路径规划（到对应救援点）
- [ ] 7.6 编写confirm接口集成测试

## 8. Error Handling & Logging
- [ ] 8.1 地名解析失败：返回明确错误信息（包含失败的地名）
- [ ] 8.2 救援点超过50个：返回 `400 Bad Request`
- [ ] 8.3 CSP无解：返回部分解 + `resource_warnings`
- [ ] 8.4 高德API超时（>10s）：抛出 `GeocodingError("地理编码服务超时")`
- [ ] 8.5 为所有关键步骤添加INFO日志
- [ ] 8.6 为外部调用（高德API、数据库）添加详细日志

## 9. Integration Testing
- [ ] 9.1 端到端测试：多救援点输入 → 分析 → 确认 → 验证任务创建
- [ ] 9.2 边界测试：0个救援点（使用事件位置）
- [ ] 9.3 边界测试：50个救援点
- [ ] 9.4 边界测试：51个救援点（应拒绝）
- [ ] 9.5 地名解析测试：全部成功/部分失败/全部失败
- [ ] 9.6 资源不足测试：队伍数量少于救援点
- [ ] 9.7 向后兼容测试：不传rescue_points时行为一致
