# Tasks: RealTimeRiskAgent实现任务

## 0. 数据源工具准备

- [ ] 0.1 创建 `src/infra/clients/openmeteo/__init__.py`
- [ ] 0.2 创建 `src/infra/clients/openmeteo/weather.py` - OpenMeteo气象客户端
  - `get_current_weather(lon, lat)` - 当前天气
  - `get_weather_forecast(lon, lat, hours)` - 预报
  - 返回: temperature, wind_speed, wind_direction, precipitation, weather_code
- [ ] 0.3 从 `OffroadEngine` 提取 `get_slope_at()` 为独立工具
  - 创建 `src/infra/clients/gis/terrain.py`
  - 复用现有DEM读取逻辑
- [ ] 0.4 单元测试气象和地形工具

## 1. 数据模型准备

- [ ] 1.1 创建SQL迁移脚本 `sql/v10_risk_predictions.sql`
- [ ] 1.2 扩展 `state.py` 添加预测相关TypedDict
- [ ] 1.3 扩展 `schemas.py` 添加预测请求/响应Pydantic模型
- [ ] 1.4 扩展 `models.py` 添加RiskPrediction SQLAlchemy模型
- [ ] 1.5 扩展 `repository.py` 添加预测数据访问方法

## 2. 预测节点实现

- [ ] 2.1 创建 `nodes/predict_path_risk.py` - 路径风险预测
  - 输入：队伍当前位置、目标位置、路径、气象数据
  - 输出：路径风险评估（风险区域、等级、置信度）
  - 使用LLM分析+规则校验

- [ ] 2.2 创建 `nodes/predict_operation_risk.py` - 作业风险评估
  - 输入：作业位置、作业类型、环境数据
  - 输出：作业风险评估（风险因素、等级、安全建议）
  - 使用LLM分析+规则校验

- [ ] 2.3 创建 `nodes/predict_disaster_spread.py` - 灾害扩散预测
  - 输入：灾害态势、气象数据、地形数据
  - 输出：扩散预测（1h/6h/24h影响范围、概率）
  - 使用LLM分析+物理模型

- [ ] 2.4 创建 `nodes/generate_recommendation.py` - 建议生成
  - 输入：风险评估结果
  - 输出：规避建议、撤离建议、安全建议
  - 调用RoutePlanningAgent生成规避路线

- [ ] 2.5 创建 `nodes/human_review.py` - 人工审核门控
  - 红色风险：设置requires_human_review=True
  - 支持interrupt机制

## 3. 图扩展

- [ ] 3.1 扩展 `graph.py` 添加新节点
- [ ] 3.2 添加条件路由函数（判断是否需要预测）
- [ ] 3.3 配置interrupt_before（human_review节点）
- [ ] 3.4 添加预测分支（parallel处理多种预测）

## 4. API扩展

- [ ] 4.1 添加路径风险预测接口 `POST /ai/realtime-risk/predict/path`
- [ ] 4.2 添加作业风险预测接口 `POST /ai/realtime-risk/predict/operation`
- [ ] 4.3 添加灾害扩散预测接口 `POST /ai/realtime-risk/predict/spread`
- [ ] 4.4 添加预测记录查询接口 `GET /ai/realtime-risk/predictions`
- [ ] 4.5 添加人工审核接口 `POST /ai/realtime-risk/predictions/{id}/review`
- [ ] 4.6 更新现有预警接口保持兼容

## 5. 测试验证

- [ ] 5.1 单元测试：各预测节点
- [ ] 5.2 单元测试：图流程
- [ ] 5.3 集成测试：API端点
- [ ] 5.4 端到端测试：完整预测流程
- [ ] 5.5 HITL测试：红色风险人工审核流程

## 6. 文档更新

- [ ] 6.1 更新业务逻辑文档
- [ ] 6.2 更新API文档注释
