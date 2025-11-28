## 1. 数据模型统一
- [x] 1.1 修改 `types.py` 中 CapabilityMetrics.slope_deg → slope_percent
- [x] 1.2 修改 `offroad_engine.py` 使用 slope_percent
- [x] 1.3 添加单位转换工具函数（角度↔百分比）到 types.py
- [x] 1.4 添加 TODO 标记 OffroadEngine 待改造项

## 2. 架构文档
- [x] 2.1 创建 `docs/架构规范/` 目录
- [x] 2.2 编写 `数据模型规范.md`
- [x] 2.3 编写 `调用规范.md`

## 3. 验证
- [x] 3.1 确认 Python 导入无报错
- [x] 3.2 运行 openspec validate 确认通过
