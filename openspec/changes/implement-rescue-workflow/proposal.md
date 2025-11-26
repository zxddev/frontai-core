# Change: 实现救援流程模块完整业务逻辑

## Why

rescue-workflow模块当前只有路由定义和空壳service，所有接口返回Mock数据或空列表，无法支撑真实业务流程。需要实现完整的数据库操作和业务逻辑，使五阶段救援流程可用。

**当前问题：**
- 14个普通业务接口仅返回Mock数据，未持久化
- 缺少RescuePoint ORM模型和Repository
- 缺少"准备完成"接口（文档定义但未实现）
- 未复用已有的events、tasks、teams、vehicles模块

## What Changes

### 阶段一：应急响应与准备
- **receive_incident**: 复用EventService创建事件记录
- **create_preparation_tasks**: 复用TaskService创建任务
- **ADDED** 准备完成接口: `/incidents/preparation-tasks/{id}/complete`
- **issue_depart_command**: 更新teams/vehicles状态

### 阶段二：机动前出
- **switch_route**: 操作planned_routes_v2表
- **get_safe_points**: 查询安全点数据
- **confirm_safe_point**: 记录确认状态

### 阶段三：现场指挥
- **confirm_command_post**: 调用EntityService创建指挥所实体
- **control_uav_cluster**: 调用DeviceService批量操作
- **confirm_rescue_point_detection**: 创建RescuePoint记录

### 阶段四：救援作业
- **ADDED** RescuePoint ORM模型和Repository
- **create_rescue_point**: 持久化到rescue_points_v2
- **update_rescue_point**: 更新救援点状态
- **get_coordination_overview**: 聚合查询救援点、队伍、车辆

### 阶段五：评估总结
- **get_evaluation_report**: 查询评估报告（AI生成后持久化）

### 不在本次范围（AI功能）
以下8个接口需要AI能力，本次仅保留占位，由用户另行开发：
1. get_equipment_suggestion - AI装备推荐
2. plan_route - AI路径规划
3. get_risk_predictions - AI风险预测
4. get_command_post_recommendation - AI指挥所选址
5. get_rescue_point_detections - AI救援点识别
6. generate_evaluation_report - AI评估报告
7. get_manual_recommendations - AI手册推荐
8. search_manuals - AI手册搜索

## Impact

- **Affected specs**: rescue-workflow (新建)
- **Affected code**:
  - `src/domains/rescue_workflow/` - 主要修改
  - `src/domains/rescue_workflow/models.py` - 新建
  - `src/domains/rescue_workflow/repository.py` - 新建
- **Dependencies**:
  - 复用 `events` 模块
  - 复用 `tasks` 模块
  - 复用 `resources/teams` 模块
  - 复用 `resources/vehicles` 模块
  - 复用 `map_entities` 模块
- **Database**: 使用已存在的 `rescue_points_v2` 表
