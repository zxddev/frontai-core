## MODIFIED Requirements

### Requirement: 现有算法清单
系统 SHALL 包含以下核心算法（共7大类）：

**5. arbitration/ - 冲突仲裁**
| 算法 | 文件 | 用途 |
|-----|------|------|
| ConflictResolver | conflict_resolver.py (11610行) | 资源冲突解决 + **GRA优先级仲裁(L0-L3)** + **切换成本计算** |
| SceneArbitrator | scene_arbitrator.py (12781行) | 多场景仲裁 |

#### Scenario: 算法选择
- **WHEN** 需要解决资源冲突
- **THEN** 使用 ConflictResolver
- **WHEN** 需要进行GRA优先级仲裁
- **THEN** 使用 ConflictResolver 的 GRA_PRIORITY_MAP 和切换成本计算

## ADDED Requirements

### Requirement: GRA优先级金字塔
ConflictResolver SHALL 支持四级优先级金字塔进行资源仲裁：

| 级别 | 优先级值 | 任务类型 | 说明 |
|------|----------|----------|------|
| L0 | 0 | life_rescue_confirmed, secondary_disaster_prevention | 最高，可抢占任何资源 |
| L1 | 1 | medical_transport, hazard_zone_recon | 高，可抢占L2/L3 |
| L2 | 2 | suspect_point_recon, panoramic_recon, supply_delivery | 中 |
| L3 | 3 | infrastructure_inspection | 最低 |

```python
GRA_PRIORITY_MAP: Dict[str, int] = {
    # L0 - 最高优先级
    "life_rescue_confirmed": 0,
    "secondary_disaster_prevention": 0,
    # L1
    "medical_transport": 1,
    "hazard_zone_recon": 1,
    # L2
    "suspect_point_recon": 2,
    "panoramic_recon": 2,
    "supply_delivery": 2,
    # L3
    "infrastructure_inspection": 3,
}
```

#### Scenario: L0任务抢占L2资源
- **WHEN** L0任务（life_rescue_confirmed）请求正在执行L2任务的资源
- **AND** 切换成本 < 0.2（剩余容量的20%）
- **THEN** 执行抢占，返回 ResolutionStrategy.PREEMPT
- **AND** 记录冲突日志

#### Scenario: 同级任务尝试合并
- **WHEN** 同级任务（如两个L2任务）请求同一资源
- **AND** 任务可顺路执行
- **THEN** 尝试合并任务，返回 Result.merged()

#### Scenario: 高成本拒绝抢占
- **WHEN** 高优先级任务请求抢占
- **AND** 切换成本 >= 0.2
- **THEN** 拒绝抢占
- **AND** 返回替代资源建议和预计可用时间

### Requirement: 切换成本计算
ConflictResolver MUST 实现真实的切换成本计算，禁止返回常量值：

```python
def _calc_switching_cost(
    self,
    resource: Resource,
    new_task: Task,
) -> float:
    """
    计算资源切换到新任务的成本
    
    Args:
        resource: 当前资源（包含位置、剩余容量）
        new_task: 新任务（包含起始位置）
    
    Returns:
        切换成本比例（0-1），表示切换消耗占剩余容量的比例
    """
    # 当前位置到返航点的距离
    return_distance = haversine(
        resource.current_position,
        resource.home_position
    )
    # 返航点到新任务起点的距离
    deploy_distance = haversine(
        resource.home_position,
        new_task.start_position
    )
    # 总切换消耗
    total_switch_distance = return_distance + deploy_distance
    # 剩余可用航程
    remaining_range = resource.remaining_capacity * resource.max_range
    
    if remaining_range <= 0:
        return 1.0  # 无剩余容量，成本为最大
    
    return min(1.0, total_switch_distance / remaining_range)
```

#### Scenario: 计算无人机切换成本
- **WHEN** 无人机在任务中途被请求切换
- **THEN** 计算返航距离 + 新任务部署距离
- **AND** 除以剩余电量对应的最大航程
- **AND** 返回0-1之间的比例值

#### Scenario: 剩余容量为零
- **WHEN** 资源剩余容量为0
- **THEN** 返回切换成本1.0（最大）
- **AND** 抢占请求被拒绝

### Requirement: 抢占阈值配置
切换成本阈值 SHALL 从配置读取，禁止硬编码：

```python
# 从 config.algorithm_parameters 获取
SWITCHING_COST_THRESHOLD = 0.2  # 默认20%
```

#### Scenario: 配置阈值
- **WHEN** 判断是否允许抢占
- **THEN** 从 algorithm_parameters 表读取 GRA_SWITCHING_THRESHOLD
- **AND** 若配置缺失则使用默认值 0.2

### Requirement: 被抢占任务处理
当任务被抢占时，ConflictResolver SHALL 根据任务类型采取不同处理：

| 被抢占任务类型 | 处理方式 |
|----------------|----------|
| 侦察任务 | 记录已侦察区域，返航后从断点继续 |
| 投送任务 | 如已接近目标（<500m），尝试完成投送再返航 |
| 正在执行救援 | **禁止抢占**，等待完成 |

#### Scenario: 侦察任务被抢占
- **WHEN** 侦察任务被L0任务抢占
- **THEN** 记录当前已完成的侦察区域
- **AND** 任务状态设为 SUSPENDED
- **AND** 原任务重新入队，从断点继续

#### Scenario: 正在执行救援禁止抢占
- **WHEN** 资源正在执行救援任务
- **AND** 收到抢占请求
- **THEN** 拒绝抢占，无论优先级
- **AND** 返回 Result.reject(reason="正在执行救援，禁止中断")
