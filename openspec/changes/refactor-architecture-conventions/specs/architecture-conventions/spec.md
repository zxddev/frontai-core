# Capability: architecture-conventions

## Overview
定义项目架构规范，包括数据模型标准、调用规范和层次边界。

## ADDED Requirements

### Requirement: ARCH-001 坡度单位统一
All slope-related fields SHALL use percentage (%) as the unit, consistent with the database field `max_gradient_percent`.

#### Scenario: 算法层坡度参数
- Given: CapabilityMetrics 定义坡度能力
- When: 创建或修改坡度相关字段
- Then: 字段名 SHALL 为 `slope_percent`，单位为百分比

#### Scenario: 坡度换算
- Given: 需要从角度转换为百分比
- When: 调用 `slope_deg_to_percent(deg)` 函数
- Then: SHALL 返回 `tan(deg) * 100`

### Requirement: ARCH-002 调用规范
Agent Node and HTTP Router SHALL access business capabilities through the Service layer. Direct calls to Core implementation classes MUST be avoided.

#### Scenario: Agent 调用业务逻辑
- Given: Agent Node 需要调用资源调度
- When: 编写调用代码
- Then: SHALL 使用 `from src.domains.xxx.service import XxxService`
- And: MUST NOT 使用 `from src.domains.xxx.core import XxxCore`

### Requirement: ARCH-003 车辆能力模型
VehicleCapability SHALL be used as the complete vehicle capability model (database entity), and CapabilityMetrics SHALL be used as the lightweight version (algorithm interface).

#### Scenario: 数据库查询车辆能力
- Given: 从数据库加载车辆信息
- When: 构建车辆能力对象
- Then: SHALL 使用 VehicleCapability 类型

#### Scenario: 算法接口参数
- Given: 路径规划算法需要车辆能力参数
- When: 定义算法接口
- Then: SHALL 使用 CapabilityMetrics 轻量类型
