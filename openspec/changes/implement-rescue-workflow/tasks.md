# Tasks: 救援流程模块实现

## 1. 基础设施

- [ ] 1.1 创建 `src/domains/rescue_workflow/models.py`
  - RescuePoint ORM 模型（对应 rescue_points_v2 表）
  - RescuePointProgress ORM 模型（对应 rescue_point_progress_v2 表）
  - RescuePointTeamAssignment ORM 模型

- [ ] 1.2 创建 `src/domains/rescue_workflow/repository.py`
  - RescuePointRepository 类
  - CRUD 操作
  - 聚合查询方法

## 2. 阶段一：应急响应与准备

- [ ] 2.1 实现 `receive_incident` - 接收事件通报
  - 调用 EventService.create() 创建事件
  - 广播事件通知
  - 返回创建的事件信息

- [ ] 2.2 实现 `create_preparation_tasks` - 创建准备任务
  - 调用 TaskService.create() 批量创建任务
  - 关联到事件

- [ ] 2.3 新增 `complete_preparation_task` 路由和实现
  - 路由: POST `/incidents/preparation-tasks/{id}/complete`
  - 更新任务状态为完成
  - 记录完成详情（装备、人员、燃油等）
  - 返回批次进度

- [ ] 2.4 实现 `issue_depart_command` - 出发指令
  - 调用 TeamService 更新队伍状态为 deployed
  - 调用 VehicleService 更新车辆状态为 deployed
  - 广播出发指令

## 3. 阶段二：机动前出

- [ ] 3.1 实现 `switch_route` - 切换路径
  - 查询当前路径
  - 切换到备选路径
  - 返回新路径信息

- [ ] 3.2 实现 `get_safe_points` - 获取安全点
  - 查询 map_entities 中 entity_type="safe_point" 的实体
  - 按路径筛选

- [ ] 3.3 实现 `confirm_safe_point` - 确认安全点
  - 记录车辆到达安全点
  - 更新状态报告

## 4. 阶段三：现场指挥

- [ ] 4.1 实现 `confirm_command_post` - 确认指挥所
  - 调用 EntityService.create() 创建指挥所实体
  - entity_type="command_post"
  - 广播指挥所建立通知

- [ ] 4.2 实现 `control_uav_cluster` - 无人机集群控制
  - 调用 DeviceService 批量更新设备状态
  - 返回任务执行状态

- [ ] 4.3 实现 `confirm_rescue_point_detection` - 确认救援点检测
  - 根据确认结果创建 RescuePoint 记录
  - 关联到事件

## 5. 阶段四：救援作业

- [ ] 5.1 实现 `create_rescue_point` - 创建救援点
  - 调用 RescuePointRepository.create()
  - 返回创建的救援点

- [ ] 5.2 实现 `update_rescue_point` - 更新救援点
  - 调用 RescuePointRepository.update()
  - 触发进度记录
  - 返回更新后的救援点

- [ ] 5.3 实现 `get_coordination_overview` - 协同总览
  - 聚合查询救援点列表
  - 查询队伍当前位置
  - 查询车辆当前位置
  - 计算总体救援进度

- [ ] 5.4 实现 `update_coordination` - 更新协同状态
  - 根据 update_type 更新对应实体
  - 广播协同更新

## 6. 阶段五：评估总结

- [ ] 6.1 实现 `get_evaluation_report` - 获取评估报告
  - 查询已生成的评估报告
  - 如不存在返回 404

## 7. 更新路由

- [ ] 7.1 修改 `router.py` 添加准备完成路由
  - POST `/incidents/preparation-tasks/{id}/complete`

## 8. 验证

- [ ] 8.1 验证所有接口可正常调用
- [ ] 8.2 验证数据库操作正确
- [ ] 8.3 验证模块间调用正常

## 依赖关系

```
1.1, 1.2 (基础设施)
    ↓
2.x, 3.x, 4.x, 5.x, 6.x (业务逻辑，可并行)
    ↓
7.x (路由更新)
    ↓
8.x (验证)
```

## 并行建议

- 1.1 和 1.2 可并行
- 2.x, 3.x, 4.x, 5.x, 6.x 在基础设施完成后可并行
- 8.x 需等待所有实现完成
