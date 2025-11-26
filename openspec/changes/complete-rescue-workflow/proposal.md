# Proposal: 完善救援流程模块剩余功能

## Summary

完成rescue-workflow模块中尚未实现的9个非AI功能，使五阶段救援流程可投入实际使用。

## Motivation

当前rescue-workflow模块已实现基础框架，但以下功能仍返回空数据或占位逻辑：

1. **数据库表未创建** - ORM模型已定义，但SQL脚本未执行
2. **安全点查询** - `get_safe_points`返回空列表
3. **队伍/车辆位置查询** - `get_coordination_overview`中位置数据为空
4. **评估报告持久化** - `get_evaluation_report`返回None
5. **协同更新路由** - `update_coordination`仅广播未实际更新
6. **准备任务完成** - 绕过TaskService直接操作Repository
7. **救援点检测确认** - 确认后未自动创建RescuePoint
8. **无人机集群控制** - 未集成DeviceService
9. **scheme_id来源** - 使用临时UUID

## Scope

### In Scope
- 执行SQL迁移脚本创建数据库表
- 实现安全点查询（复用map_entities，entity_type=resettle_point/safety_area）
- 实现队伍/车辆实时位置查询
- 创建评估报告持久化表和查询逻辑
- 完善协同更新的实体状态同步
- 重构准备任务完成逻辑
- 实现救援点检测确认后自动创建记录
- 集成DeviceService实现无人机批量控制
- 确认scheme_id的正确来源

### Out of Scope
- 8个AI功能（装备推荐、路径规划、风险预测、指挥所推荐、救援点检测、评估报告生成、手册推荐、手册搜索）
- 新增API路由（路由层已完成）
- 修改现有数据库表结构

## Impact

| Area | Impact |
|------|--------|
| Database | 新增evaluation_reports_v2表；执行rescue_points_v2等表创建脚本 |
| Service Layer | 完善9个方法的业务逻辑 |
| Dependencies | 需集成DeviceService、增加TeamService/VehicleService位置查询 |

## Risks

| Risk | Mitigation |
|------|------------|
| 数据库迁移可能影响现有数据 | 使用IF NOT EXISTS，确保幂等性 |
| 跨模块调用增加耦合 | 保持Service注入模式，避免直接Repository调用 |
| 位置查询性能问题 | 使用空间索引，限制查询范围 |

## Success Criteria

- [ ] 所有9个功能返回真实数据而非空/Mock
- [ ] 数据库表已创建并可正常读写
- [ ] 协同总览显示完整的救援点、队伍、车辆位置
- [ ] 评估报告可持久化和查询
