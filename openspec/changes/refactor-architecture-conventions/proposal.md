# Change: 架构规范与数据模型统一

## Why
当前代码存在以下架构问题：
1. **数据模型不统一** - 坡度单位混用（% vs °），车辆参数有两套模型
2. **调用规范缺失** - Agent 直接调用 Core，跳过 Service 层
3. **死代码残留** - 已删除部分（road_engine.py, logistics_scheduler.py），但仍有 OffroadEngine 待改造
4. **层次边界模糊** - Service 层被绕过，存在意义不明确

这些问题会导致：
- 坡度判断错误（30% vs 30° 差距巨大）
- 代码维护困难（两条路径到达同一目的地）
- 新人上手困难（没有明确规范）

## What Changes
1. **统一数据模型**
   - 坡度单位全部使用百分比（%），与数据库字段一致
   - 统一车辆能力参数模型（VehicleCapability 为主）
   
2. **建立调用规范**
   - 明确 Agent Node → UseCase → Algorithm 的调用链
   - 禁止 Agent 直接调用 Core 实现类
   
3. **清理 OffroadEngine**
   - 修改坡度单位为百分比
   - 添加 TODO 标记待改造项

4. **创建架构文档**
   - `docs/架构规范/数据模型规范.md` - 数据模型规范
   - `docs/架构规范/调用规范.md` - 调用规范

## Impact
- Affected specs: 无（本次仅建立规范）
- Affected code:
  - `src/planning/algorithms/routing/types.py` (修改)
  - `src/planning/algorithms/routing/offroad_engine.py` (修改)
  - `docs/架构规范/` (新增)

## Design Decisions
- **渐进式重构** - 不一次性大改，先建立规范，新代码遵循
- **坡度单位选择** - 使用百分比（%），因为数据库已用百分比
- **保留 OffroadEngine** - 不删除，标记待改造，后期整合时再处理
