## 1. 数据模型
- [x] 1.1 创建 disaster_situations 表（灾害态势）
- [x] 1.2 创建 warning_records 表（预警记录）
- [x] 1.3 添加空间索引优化范围查询

## 2. 智能体核心
- [x] 2.1 创建 `src/agents/early_warning/` 目录结构
- [x] 2.2 定义 EarlyWarningState（状态类型）
- [x] 2.3 实现 ingest 节点（接收灾情数据）
- [x] 2.4 实现 analyze_impact 节点（影响分析：距离计算、路径检测）
- [x] 2.5 实现 decide_warning 节点（预警决策：级别判断）
- [x] 2.6 实现 generate_message 节点（生成预警消息）
- [x] 2.7 实现 notify 节点（WebSocket推送）
- [x] 2.8 组装 LangGraph 图

## 3. API接口
- [x] 3.1 POST /api/disasters/update（接收灾情数据）
- [x] 3.2 GET /api/warnings（查询预警列表）
- [x] 3.3 GET /api/warnings/{id}（查询预警详情）
- [x] 3.4 POST /api/warnings/{id}/acknowledge（确认收到）
- [x] 3.5 POST /api/warnings/{id}/respond（提交响应）
- [x] 3.6 GET /api/warnings/{id}/detour-options（获取绕行方案）
- [x] 3.7 POST /api/warnings/{id}/confirm-detour（确认绕行）

## 4. 绕行集成
- [x] 4.1 实现绕行请求处理（调用RoutePlanningAgent）
- [x] 4.2 传递avoid_areas参数给路径规划
- [x] 4.3 返回多条备选路线
- [x] 4.4 创建数据库Repository类
- [x] 4.5 实现confirm_detour完整逻辑

## 5. 测试验证
- [x] 5.1 编写单元测试（影响分析逻辑）
- [x] 5.2 端到端测试（完整预警流程）- 所有API接口测试通过
- [x] 5.3 数据库表创建并验证
