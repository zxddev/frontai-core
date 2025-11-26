# Tasks: 完善救援流程模块

## 1. 数据库准备

- [ ] 1.1 执行`sql/v2_rescue_points.sql`创建救援点相关表
  - rescue_points_v2
  - rescue_point_team_assignments_v2
  - rescue_point_progress_v2
  - 相关索引和触发器

- [ ] 1.2 创建`sql/v2_evaluation_reports.sql`
  - evaluation_reports_v2表
  - event_id唯一索引
  - 时间戳索引

## 2. 服务层扩展

- [ ] 2.1 TeamService添加位置查询方法
  - `list_deployed_with_location(task_ids: list[UUID]) -> list[TeamLocationResponse]`
  - 查询deployed状态且关联指定任务的队伍
  - 返回队伍ID、名称、当前位置

- [ ] 2.2 VehicleService添加位置查询方法
  - `list_deployed_with_location(task_ids: list[UUID]) -> list[VehicleLocationResponse]`
  - 查询deployed状态且关联指定任务的车辆
  - 返回车辆ID、名称、当前位置

- [ ] 2.3 TaskService添加事件任务查询
  - `list_task_ids_by_event(event_id: UUID) -> list[UUID]`
  - 返回事件关联的所有任务ID

- [ ] 2.4 SchemeService添加准备方案管理
  - `get_or_create_preparation_scheme(scenario_id, event_id) -> SchemeResponse`
  - 查找或创建"应急准备"类型的scheme

- [ ] 2.5 创建EvaluationReportRepository
  - `create(event_id, report_data, generated_by) -> EvaluationReport`
  - `get_by_event_id(event_id) -> Optional[EvaluationReport]`
  - `update(event_id, report_data) -> EvaluationReport`

## 3. Schema扩展

- [ ] 3.1 扩展RescuePointConfirm添加可选字段
  - event_id: Optional[UUID]
  - name: Optional[str]
  - location: Optional[Location]
  - point_type: Optional[str]
  - estimated_victims: Optional[int]

- [ ] 3.2 创建TeamLocationResponse和VehicleLocationResponse
  - id: UUID
  - name: str
  - location: Location
  - status: str
  - current_task_id: Optional[UUID]

- [ ] 3.3 创建EvaluationReport ORM模型
  - 对应evaluation_reports_v2表

## 4. 业务逻辑完善

- [ ] 4.1 实现`get_safe_points`
  - 调用EntityService.list查询resettle_point/safety_area
  - 转换为SafePoint响应格式

- [ ] 4.2 实现`get_coordination_overview`位置查询
  - 调用TaskService获取事件任务ID
  - 调用TeamService获取队伍位置
  - 调用VehicleService获取车辆位置
  - 组装完整的CoordinationTracking响应

- [ ] 4.3 实现`update_coordination`分发逻辑
  - 根据entity_type调用对应Service
  - team -> TeamService.update_location
  - vehicle -> VehicleService.update_location
  - rescue_point -> RescueWorkflowService.update_rescue_point

- [ ] 4.4 实现`control_uav_cluster`设备控制
  - 导入DeviceService
  - 根据command_type映射设备状态
  - 批量更新设备状态
  - 返回执行结果

- [ ] 4.5 实现`confirm_rescue_point_detection`自动创建
  - 检查is_confirmed和必要字段
  - 调用create_rescue_point创建记录
  - 关联detection_id

- [ ] 4.6 实现`get_evaluation_report`查询
  - 调用EvaluationReportRepository.get_by_event_id
  - 返回报告或抛出NotFoundError

- [ ] 4.7 重构`create_preparation_tasks`使用正确scheme_id
  - 调用SchemeService.get_or_create_preparation_scheme
  - 使用返回的scheme_id创建任务

## 5. 验证

- [ ] 5.1 验证数据库表创建成功
  - 检查表结构
  - 检查索引
  - 检查触发器

- [ ] 5.2 验证安全点查询返回数据
  - 准备测试数据
  - 调用API验证响应

- [ ] 5.3 验证协同总览返回完整数据
  - 创建测试场景
  - 部署队伍和车辆
  - 验证位置数据

- [ ] 5.4 验证评估报告持久化
  - 生成报告（AI功能Mock）
  - 查询报告
  - 验证数据一致性

- [ ] 5.5 验证救援点检测确认流程
  - 模拟检测结果
  - 确认并创建救援点
  - 验证关联关系

## 依赖关系

```
1.x (数据库准备)
    ↓
2.x, 3.x (服务层和Schema扩展，可并行)
    ↓
4.x (业务逻辑完善)
    ↓
5.x (验证)
```

## 并行建议

- 1.1和1.2可并行
- 2.1-2.5可并行（不同Service）
- 3.1-3.3可并行（不同文件）
- 4.x需按依赖顺序执行
- 5.x需等待所有实现完成
