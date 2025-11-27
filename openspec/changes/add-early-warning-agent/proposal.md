# Change: 新增预警监测智能体

## Why
当灾害范围变化时，系统需要主动监测并预警受影响的车辆和救援队伍，确保人员安全。当前系统缺乏实时的灾害影响检测和预警通知能力。

## What Changes
- 新增预警监测智能体（EarlyWarningAgent）
- 实现灾害范围变化检测
- 实现车辆/队伍位置影响分析（3km预警距离）
- 实现路径穿越危险区域检测
- 实现预计接触时间计算
- 通过WebSocket推送交互式预警消息到前端
- 支持人工选择绕行后调用路径规划

## Impact
- Affected specs: early-warning (新增)
- Affected code:
  - `src/agents/early_warning/` (新增)
  - `src/core/websocket.py` (复用现有alerts频道)
  - `src/agents/route_planning/` (被调用，无修改)

## Design Decisions
- **Human in the Loop**: 不自动重规划路径，人工确认后才执行绕行
- **通知对象**: 对内车辆→指挥员，救援队伍→队伍负责人
- **通知渠道**: 仅WebSocket推送到前端（复用现有alerts频道）
- **预警距离**: 默认3km，可按灾害类型配置
