# Tasks: 语音指挥Agent实现任务

## Phase 0: 基础设施准备 (1周)

- [x] 0.1 新增中文embedding配置
  - `src/infra/settings.py` 添加 `semantic_router_embedding_model`
  - `src/infra/settings.py` 添加 `semantic_router_embedding_base_url`
  - `src/infra/settings.py` 添加 `robot_command_enabled` 安全开关
- [ ] 0.2 部署 bge-small-zh-v1.5 到embedding服务
- [x] 0.3 创建目录结构 `src/agents/voice_commander/`
  - `__init__.py`
  - `state.py`
  - `schemas.py`
  - `semantic_router.py`
  - `spatial_graph.py`
  - `commander_graph.py`
  - `tools/__init__.py`
  - `tools/spatial_tools.py`
  - `tools/command_tools.py`
- [x] 0.4 创建 `src/agents/db/spatial.py` 空间查询仓库骨架

## Phase 1: 语义路由层 (1周)

- [x] 1.1 安装依赖 `semantic-router>=0.1.0`
- [x] 1.2 创建 `src/agents/voice_commander/semantic_router.py`
  - 使用 semantic-router 库的 OpenAIEncoder
  - 定义4个路由：spatial_query, robot_command, mission_status, chitchat
  - 配置路由阈值 (0.75-0.85)
- [x] 1.3 创建路由配置类
  - 从settings加载embedding配置
  - ROUTE_TARGETS映射表
- [x] 1.4 修改 `src/domains/voice/router.py` 集成语义路由
  - 在 `_generate_ai_response` 前添加路由判断
  - 实现 `_dispatch_to_agent` 方法
  - 支持降级到原有LLM逻辑
- [x] 1.5 单元测试：路由准确率测试 (scripts/test_voice_commander_unit.py)
  - 准备中文测试语料（72样本：spatial 22, robot 20, mission 15, chitchat 15）
  - Hybrid路由准确率 95.8% (69/72)
    - spatial_query: 95.5%, robot_command: 95.0%, mission_status: 93.3%, chitchat: 100%

## Phase 2: 空间智能Agent (2周)

### 2.1 状态与模型定义
- [x] 2.1.1 创建 `src/agents/voice_commander/state.py`（骨架已完成）
  - SpatialAgentState TypedDict
  - CommanderAgentState TypedDict
- [x] 2.1.2 创建 `src/agents/voice_commander/schemas.py`（骨架已完成）
  - EntityLocation Pydantic模型
  - NearestUnitResult Pydantic模型
  - AreaStatus Pydantic模型

### 2.2 空间查询仓库
- [x] 2.2.1 实现 `src/agents/db/spatial.py` SpatialRepository
  - `find_by_name_fuzzy(name)` - 模糊名称匹配
  - `find_nearest_knn(point, unit_type, limit)` - KNN查询
  - `get_units_in_area(area_id)` - 区域内单位查询
  - `resolve_location_name(name)` - 地名解析为坐标
  - `reverse_geocode(point)` - 逆地理编码
- [ ] 2.2.2 Neo4j团队关系查询（骨架，Phase 3依赖）
  - `get_team_members(team_name)` - 获取团队成员
  - `get_unit_team(unit_id)` - 获取单位所属团队
  - 备注：当前空间查询不需要Neo4j，留待Phase 3实现

### 2.3 空间查询工具
- [x] 2.3.1 创建 `tools/spatial_tools.py`
  - `@tool find_entity_location(entity_name, entity_type)`
  - `@tool find_nearest_unit(reference_point, target_type, count)`
  - `@tool get_area_status(area_id)`
- [x] 2.3.2 实现逆地理编码（坐标→人类可读描述）

### 2.4 SpatialAgent图
- [x] 2.4.1 创建 `src/agents/voice_commander/spatial_graph.py`
  - 节点: parse_query（LLM解析用户意图）
  - 节点: execute_tool（调用空间查询工具）
  - 节点: format_response（LLM格式化回复）
- [x] 2.4.2 实现图编排和条件边

### 2.5 集成
- [x] 2.5.1 修改 `VoiceChatManager._dispatch_to_agent` 支持SpatialAgent
- [x] 2.5.2 端到端测试：语音空间查询 (scripts/test_spatial_agent.py)
  - "消防救援大队在哪里" ✓
  - "103.85,31.68附近最近的救援队" ✓
  - Hybrid路由分类 100% (Semantic Router + LLM Fallback)
    - 80% 请求由 Semantic Router 处理（~50ms）
    - 20% 低置信度请求由 LLM 兜底（~1000ms）

## Phase 3: 战术控制Agent (2周)

### 3.1 指令模型
- [x] 3.1.1 扩展 `schemas.py`（骨架已完成）
  - TacticalCommand 模型
  - PendingCommand 模型
  - CommandConfirmation 模型
- [x] 3.1.2 定义指令类型枚举（骨架已完成）
  - NAVIGATE_TO, PATROL, RETURN_HOME, STOP, FOLLOW

### 3.2 控制工具
- [ ] 3.2.1 创建 `tools/command_tools.py`
  - `@tool prepare_dispatch_command(unit_id, target, action)`
  - `@tool execute_confirmed_command(pending_command_id)`
- [ ] 3.2.2 实现安全检查逻辑
  - 禁飞区检测（查询risk_areas表）
  - 电量检查（查询单位状态）
  - 任务冲突检测

### 3.3 CommanderAgent图
- [ ] 3.3.1 创建 `src/agents/voice_commander/commander_graph.py`
  - 节点: parse_command
  - 节点: safety_check
  - 节点: generate_confirmation
  - 节点: execute
- [ ] 3.3.2 配置 `interrupt_before=["execute"]`
- [ ] 3.3.3 实现图状态持久化（MemorySaver）

### 3.4 WebSocket确认流程
- [ ] 3.4.1 扩展WebSocket消息类型
  - `{"type": "require_confirmation", "text": "...", "command_id": "..."}`
  - `{"type": "command_sent", "command_id": "..."}`
  - `{"type": "command_cancelled", "command_id": "..."}`
- [ ] 3.4.2 实现 `_handle_confirmation` 方法
  - 识别确认/取消意图
  - 恢复图执行 `graph.ainvoke(Command(resume=...))`
- [ ] 3.4.3 实现确认超时处理（30秒）

### 3.5 STOMP集成
- [ ] 3.5.1 创建STOMP指令发送工具
  - 发布到 `/topic/robot_commands/{unit_id}`
  - 指令签名（HMAC）
- [ ] 3.5.2 订阅机器人状态反馈（可选）
  - 订阅 `/topic/robot_status/{unit_id}`
  - 状态更新推送到WebSocket

### 3.6 测试
- [ ] 3.6.1 单元测试：安全检查逻辑
- [ ] 3.6.2 集成测试：完整确认流程
- [ ] 3.6.3 安全测试：禁飞区拦截

## Phase 4: 性能优化 (1周)

- [ ] 4.1 流式TTS优化
  - 基于标点的微批处理
  - 首字延迟 < 500ms
- [ ] 4.2 Redis查询缓存
  - 救援进度等非实时敏感数据
  - TTL 5-10秒
- [ ] 4.3 延迟监控埋点
  - semantic_router_latency_ms
  - spatial_query_latency_ms
  - command_confirmation_rate
  - e2e_voice_response_latency_ms
- [ ] 4.4 性能测试
  - P95端到端延迟 < 2s
  - 路由延迟 < 100ms
