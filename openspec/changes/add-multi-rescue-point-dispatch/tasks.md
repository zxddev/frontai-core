## 1. Schema & Type Definitions
- [ ] 1.1 在 `schemas.py` 新增 `LocationInput` 类型定义（longitude/latitude）
- [ ] 1.2 在 `schemas.py` 新增 `RescuePointInput` 类型定义（name/address/location/estimated_victims/priority）
- [ ] 1.3 修改 `EmergencyAnalyzeRequest` 增加 `rescue_points: Optional[List[RescuePointInput]]` 字段
- [ ] 1.4 在 `state.py` 新增 `PointAllocation` 和 `MultiPointAllocationPlan` TypedDict
- [ ] 1.5 在 `state.py` 新增 `resolved_rescue_points` 字段到 `EmergencyAIState`

## 2. Geocoding Integration
- [ ] 2.1 在 `matching.py` 新增 `GeocodingError` 异常类
- [ ] 2.2 实现 `resolve_rescue_point_location()` 异步函数：
  - 优先使用location坐标
  - 如有address则调用 `amap_geocode_async()`
  - 失败时抛出 `GeocodingError`（不降级）
  - 添加详细日志
- [ ] 2.3 为 `resolve_rescue_point_location()` 编写单元测试（成功/失败/缺失场景）

## 3. Rescue Points Loading
- [ ] 3.1 实现 `_get_rescue_points_from_input()` 函数：从请求输入解析救援点
- [ ] 3.2 实现 `_get_rescue_points_from_db()` 函数：从 `rescue_points_v2` 表查询
- [ ] 3.3 实现 `_get_rescue_points()` 函数：优先输入，否则数据库
- [ ] 3.4 为救援点加载逻辑编写测试（输入优先/数据库读取/空数据场景）

## 4. Multi-Point Resource Matching
- [ ] 4.1 重构 `_extract_event_location()` 为 `_resolve_all_rescue_point_locations()`：
  - 接收救援点列表
  - 为每个点调用地名解析
  - 返回 Dict[point_id, (lat, lng)]
- [ ] 4.2 实现 `_query_candidates_for_point()` 函数：为单个救援点查询候选队伍
- [ ] 4.3 实现 `match_resources_multi_point()` 函数：
  - 获取所有救援点
  - 为每个点查询候选队伍
  - 返回 `point_candidates: Dict[str, List[ResourceCandidate]]`
- [ ] 4.4 修改 `match_resources()` 调用新的多点匹配逻辑
- [ ] 4.5 编写多点匹配的集成测试

## 5. Multi-Point Optimization
- [ ] 5.1 在 `optimization.py` 实现 `_build_multi_point_csp_model()` 函数：
  - 构建多点位-多队伍CSP约束模型
  - 约束：每个队伍最多分配到一个点
  - 约束：优先级高的点优先分配
  - 目标：最小化总响应时间
- [ ] 5.2 实现 `optimize_multi_point_allocation()` 函数：
  - 调用现有 `CapabilityMatcher` 或构建新CSP
  - 处理无解情况（返回部分解+警告）
  - 设置求解超时（30秒）
- [ ] 5.3 修改 `optimize_allocation()` 调用多点优化逻辑
- [ ] 5.4 编写多点优化的单元测试（正常/资源不足/超时场景）

## 6. Output Generation
- [ ] 6.1 修改 `generate_output()` 输出按救援点分组的分配结果
- [ ] 6.2 输出包含每个救援点的：队伍列表、ETA、task_description
- [ ] 6.3 输出包含 `unassigned_points` 和 `resource_warnings`
- [ ] 6.4 编写输出格式测试

## 7. Confirm Interface Refactor
- [ ] 7.1 修改 `confirm_emergency_scheme()` 创建 `schemes_v2` 记录：
  - status=approved
  - 记录完整分配方案
- [ ] 7.2 为每个救援点创建独立的 `tasks_v2` 记录：
  - 任务标题包含救援点名称和被困人数
  - 关联 `rescue_point_id`
- [ ] 7.3 创建 `task_assignments_v2` 时使用AI生成的 `task_description`
- [ ] 7.4 写入 `rescue_point_team_assignments_v2` 表
- [ ] 7.5 每个任务独立生成路径规划
- [ ] 7.6 编写confirm接口的集成测试

## 8. Database Verification
- [ ] 8.1 验证 `tasks_v2` 表是否有 `rescue_point_id` 列，若无则提供ALTER SQL
- [ ] 8.2 验证 `rescue_point_team_assignments_v2` 表结构符合需求
- [ ] 8.3 验证 `schemes_v2` 表字段满足方案存储需求

## 9. Error Handling & Logging
- [ ] 9.1 地名解析失败时返回明确错误信息（包含失败的地名）
- [ ] 9.2 CSP无解时返回部分解和资源缺口报告
- [ ] 9.3 为所有关键步骤添加INFO级别日志
- [ ] 9.4 为外部调用（高德API、数据库）添加详细日志

## 10. Integration Testing
- [ ] 10.1 编写端到端测试：多救援点输入 → 分析 → 确认 → 验证任务创建
- [ ] 10.2 编写边界测试：0个救援点、50个救援点、地名全部失败
- [ ] 10.3 编写资源不足测试：队伍数量少于救援点数量
- [ ] 10.4 运行现有测试确保向后兼容
