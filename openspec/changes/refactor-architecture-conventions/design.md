## Context
frontai-core 是应急救灾协同决策系统，包含多个路径规划引擎和业务服务。
当前架构评分 70 分，主要问题是数据模型不统一和调用规范缺失。

## Goals / Non-Goals

**Goals:**
- 统一坡度单位为百分比
- 统一车辆能力参数模型
- 建立明确的调用规范文档
- 为后续渐进式重构奠定基础

**Non-Goals:**
- 不做大规模目录重构
- 不改变现有工作代码的调用方式
- 不实现 OffroadEngine 的完整改造

## Decisions

### 1. 坡度单位选择
**决策**: 全部使用百分比（%）

| 选项 | 优点 | 缺点 |
|------|------|------|
| 百分比（%） | 与数据库一致，改动小 | 越野场景不直观 |
| 角度（°） | 物理含义直观 | 需要改数据库字段 |

**理由**: 数据库 road_edges_v2 表已使用 `max_gradient_percent`，改百分比成本最低

**换算公式**:
```
百分比 = tan(角度) × 100
角度 = atan(百分比 / 100)

示例:
10% ≈ 5.7°
30% ≈ 16.7°
100% = 45°
```

### 2. 车辆参数模型统一
**决策**: VehicleCapability 为主模型，CapabilityMetrics 作为轻量版

```python
# 主模型（完整参数，用于数据库实体）
@dataclass
class VehicleCapability:
    max_gradient_percent: Optional[int]  # 百分比
    is_all_terrain: bool
    terrain_capabilities: List[str]
    terrain_speed_factors: Dict[str, float]
    max_wading_depth_m: Optional[float]
    width_m: Optional[float]
    height_m: Optional[float]
    self_weight_kg: Optional[float]
    max_weight_kg: Optional[float]

# 轻量模型（算法接口用）
class CapabilityMetrics:
    slope_percent: Optional[float]  # 统一为百分比（原 slope_deg）
    width_m: Optional[float]
    height_m: Optional[float]
    weight_kg: Optional[float]
    turn_radius_m: Optional[float]
    wading_depth_m: Optional[float]
```

### 3. 调用规范
**决策**: 统一使用 UseCase 模式

```
✅ 正确调用链:
HTTP Router → Service/UseCase → Algorithm + Repository
Agent Node → Service/UseCase → Algorithm + Repository

❌ 禁止的调用:
Agent Node → Core（直接调用实现类，跳过Service）
```

**当前违规代码示例**（需要后续修复）:
```python
# src/agents/emergency_ai/nodes/matching.py
from src.domains.resource_scheduling.core import ResourceSchedulingCore  # ❌ 直接调用Core
```

**应该改为**:
```python
from src.domains.resource_scheduling.service import ResourceSchedulingService  # ✅ 调用Service
```

### 4. OffroadEngine 处理
**决策**: 保留但标记待改造

- 修改 `slope_deg` → `slope_percent`
- 添加 `# TODO: [refactor-architecture-conventions] 待改造` 注释
- 不删除，留待后续整合 DEM 数据时使用

**待改造项**:
1. 异步化（当前是同步）
2. 与 DatabaseRouteEngine 的 fallback 集成
3. 初始化代码（加载 DEM 和水域数据）

## Architecture Target (Long-term)

```
┌─────────────────────────────────────────────────────────┐
│                    入口层（Adapters）                    │
│   frontend_api/   │   agents/router   │   domains/router │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              应用服务层（Service / UseCase）              │
│   domains/*/service.py                                  │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌───────────────────────┐      ┌────────────────────────────┐
│    核心算法层          │      │    外部依赖                 │
│  planning/algorithms  │      │  domains/*/repository.py   │
│  （纯函数，无IO）       │      │  infra/clients/            │
└───────────────────────┘      └────────────────────────────┘
```
