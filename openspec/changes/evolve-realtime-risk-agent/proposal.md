# Change: 演进EarlyWarningAgent为RealTimeRiskAgent

## Why

当前EarlyWarningAgent仅支持「被动预警」：灾害发生后通知受影响队伍。
根据操作手册阶段2（机动前出）需求，系统需要「主动预测」能力：
- 路径风险预测（行进中的队伍）
- 作业风险评估（现场救援）
- 灾害扩散预测（1h/6h/24h）

**参考依据：**
- H2O.ai Flood Intelligence Blueprint：Risk Analyzer + Predictive Intelligence紧密耦合
- Multi-Agent Failure研究：减少Agent间不必要分离可降低失败风险
- HAZARD Challenge (MIT)：动态环境决策需要实时感知+预测结合

## What Changes

- **MODIFIED** EarlyWarningAgent → RealTimeRiskAgent（保持原有功能，扩展新能力）
- **ADDED** RiskPredictor模块：路径风险、作业风险、灾害扩散预测
- **ADDED** 新数据表：risk_predictions存储预测记录
- **ADDED** 新API端点：风险预测查询接口
- **ADDED** LangGraph新节点：predict_path_risk, predict_operation_risk, predict_disaster_spread
- **ADDED** Human-in-the-loop：红色风险必须人工确认

## Impact

- Affected specs: `specs/early-warning/spec.md`
- Affected code:
  - `src/agents/early_warning/` → 重命名为 `src/agents/realtime_risk/`
  - `src/agents/early_warning/graph.py` → 扩展流程
  - `src/agents/early_warning/state.py` → 扩展状态定义
  - `src/agents/early_warning/router.py` → 新增API端点
  - `sql/` → 新增risk_predictions表

## Safety Principles

**这是救人的系统，设计必须遵循：**
1. 红色风险预警必须human-in-the-loop确认
2. 所有预测必须带置信度（confidence_score）
3. 决策可追溯（完整trace记录）
4. 建议≠指令，人是最终决策者
