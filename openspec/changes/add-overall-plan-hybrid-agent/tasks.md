# Tasks: 总体救灾方案生成混合Agent

## 1. 环境准备

- [ ] 1.1 安装CrewAI依赖
  ```bash
  pip install crewai>=0.30.0 crewai-tools>=0.4.0
  ```
- [ ] 1.2 安装MetaGPT依赖
  ```bash
  pip install metagpt>=0.8.0
  ```
- [ ] 1.3 验证asyncio兼容性（测试event loop不冲突）
- [x] 1.4 创建目录结构
  ```
  src/agents/overall_plan/
  ├── __init__.py
  ├── agent.py
  ├── graph.py
  ├── state.py
  ├── schemas.py
  ├── crewai/
  │   ├── __init__.py
  │   ├── agents.py
  │   ├── tasks.py
  │   └── crew.py
  ├── metagpt/
  │   ├── __init__.py
  │   ├── roles.py
  │   ├── actions.py
  │   ├── estimators.py
  │   └── scribe.py
  └── nodes/
      ├── __init__.py
      ├── load_context.py
      ├── situational_awareness.py
      ├── resource_calculation.py
      ├── human_review.py
      └── document_generation.py
  ```

## 2. 状态与数据契约

- [x] 2.1 创建 `state.py` - OverallPlanState定义
  - [x] 2.1.1 定义TypedDict状态类型
  - [x] 2.1.2 定义所有9个模块的状态字段
  - [x] 2.1.3 定义HITL审核相关字段
- [x] 2.2 创建 `schemas.py` - API请求/响应模型
  - [x] 2.2.1 定义 `TriggerPlanResponse` 请求模型
  - [x] 2.2.2 定义 `PlanModuleItem` 响应模型
  - [x] 2.2.3 定义 `PlanStatusResponse` 状态响应模型
  - [x] 2.2.4 定义 `ApproveRequest` 审批请求模型
- [x] 2.3 定义CrewAI→MetaGPT的中间格式
  - [x] 2.3.1 定义 `SituationalAwarenessOutput` 模型
  - [x] 2.3.2 定义 `ResourceCalculationInput` 模型

## 3. SPHERE标准估算器

- [x] 3.1 创建 `metagpt/estimators.py`
  - [x] 3.1.1 定义 `SPHERE_STANDARDS` 常量字典
  - [x] 3.1.2 实现 `estimate_shelter_needs()` - 安置物资估算
  - [x] 3.1.3 实现 `estimate_rescue_force()` - 救援力量估算
  - [x] 3.1.4 实现 `estimate_medical_resources()` - 医疗资源估算
  - [x] 3.1.5 实现 `estimate_infrastructure_force()` - 工程力量估算
  - [x] 3.1.6 实现 `estimate_communication_needs()` - 通信设备估算
  - [x] 3.1.7 实现 `estimate_logistics_needs()` - 物资运输估算
  - [x] 3.1.8 实现 `estimate_self_support()` - 自身保障估算
- [x] 3.2 编写估算器单元测试（通过Python脚本验证）
  - [x] 3.2.1 测试各估算函数的计算正确性
  - [x] 3.2.2 测试边界条件（0人、大规模灾害）
  - [x] 3.2.3 测试异常输入（负数、严重伤员数大于总伤员数等），确保估算器显式抛出校验错误并由上层fail-fast处理

## 4. CrewAI态势感知子图

- [x] 4.1 创建 `crewai/__init__.py`
- [x] 4.2 创建 `crewai/agents.py` - 定义Agent
  - [x] 4.2.1 定义 `IntelChief` 情报指挥官Agent
  - [x] 4.2.2 定义 `DisasterAnalyst` 灾情分析员Agent
  - [x] 4.2.3 配置Agent的LLM和工具
- [x] 4.3 创建 `crewai/tasks.py` - 定义Task
  - [x] 4.3.1 定义 `analyze_basic_disaster` Task（模块0）
  - [x] 4.3.2 定义 `analyze_secondary_disaster` Task（模块5）
  - [x] 4.3.3 定义Task的输入输出格式
- [x] 4.4 创建 `crewai/crew.py` - 组装Crew
  - [x] 4.4.1 实现 `create_situational_awareness_crew()` 函数
  - [x] 4.4.2 配置Crew的执行模式（sequential）
- [x] 4.5 实现模块0输出解析
  - [x] 4.5.1 定义结构化输出Schema
  - [x] 4.5.2 实现输出解析逻辑
- [x] 4.6 实现模块5输出解析
  - [x] 4.6.1 定义结构化输出Schema（风险类型、风险等级、防范措施等）及对应文本格式
  - [x] 4.6.2 实现输出解析与校验逻辑，确保CrewAI输出可被下游稳定消费
- [ ] 4.7 测试CrewAI独立运行（需要安装crewai依赖）
  - [ ] 4.7.1 编写mock数据测试用例
  - [ ] 4.7.2 验证输出格式正确

## 5. MetaGPT资源计算子图

- [x] 5.1 创建 `metagpt/__init__.py`
- [x] 5.2 创建 `metagpt/actions.py` - 定义Action
  - [x] 5.2.1 实现 `calculate_rescue_force_module` Action（模块1）
  - [x] 5.2.2 实现 `calculate_medical_module` Action（模块2）
  - [x] 5.2.3 实现 `calculate_infrastructure_module` Action（模块3）
  - [x] 5.2.4 实现 `calculate_shelter_module` Action（模块4）
  - [x] 5.2.5 实现 `calculate_communication_module` Action（模块6）
  - [x] 5.2.6 实现 `calculate_logistics_module` Action（模块7）
  - [x] 5.2.7 实现 `calculate_self_support_module` Action（模块8）
- [x] 5.3 创建 `metagpt/roles.py` - 定义Role
  - [x] 5.3.1 实现 `ResourcePlanner` Role
  - [x] 5.3.2 配置Role的Action列表
  - [x] 5.3.3 配置Role的LLM
- [x] 5.4 实现模块1-4, 6-8输出生成
  - [x] 5.4.1 调用估算器计算数值
  - [x] 5.4.2 使用LLM生成专业文本
- [ ] 5.5 测试MetaGPT独立运行（需要安装metagpt依赖）
  - [ ] 5.5.1 编写mock数据测试用例
  - [ ] 5.5.2 验证计算结果正确
  - [ ] 5.5.3 验证输出文本质量

## 6. MetaGPT公文生成

- [x] 6.1 创建 `metagpt/scribe.py` - 公文秘书Role
  - [x] 6.1.1 实现 `generate_document` 方法
  - [x] 6.1.2 实现 `OfficialScribe` Role
  - [x] 6.1.3 定义公文模板格式
- [x] 6.2 实现9模块整合逻辑
  - [x] 6.2.1 合并CrewAI和MetaGPT输出
  - [x] 6.2.2 生成标准格式文档
- [ ] 6.3 测试公文生成（需要LLM服务）
  - [ ] 6.3.1 验证文档结构完整
  - [ ] 6.3.2 验证格式符合规范

## 7. LangGraph节点实现

- [x] 7.1 创建 `nodes/__init__.py`
- [x] 7.2 创建 `nodes/load_context.py` - 数据聚合节点
  - [x] 7.2.1 查询events_v2表获取事件数据（mock实现）
  - [x] 7.2.2 查询ai_decision_logs_v2获取EmergencyAI分析结果（mock实现）
  - [x] 7.2.3 查询资源库获取可用资源（mock实现）
  - [x] 7.2.4 组装为State格式
- [x] 7.3 创建 `nodes/situational_awareness.py` - CrewAI封装节点
  - [x] 7.3.1 实现async节点函数
  - [x] 7.3.2 使用run_in_executor调用CrewAI（避免event loop冲突）
  - [x] 7.3.3 解析输出更新State
- [x] 7.4 创建 `nodes/resource_calculation.py` - MetaGPT封装节点
  - [x] 7.4.1 实现async节点函数
  - [x] 7.4.2 调用MetaGPT ResourcePlanner Role
  - [x] 7.4.3 解析输出更新State
- [x] 7.5 创建 `nodes/human_review.py` - HITL审核节点
  - [x] 7.5.1 实现审核状态检查
  - [x] 7.5.2 实现状态持久化
  - [x] 7.5.3 实现resume逻辑（指挥官批准后继续执行）
  - [x] 7.5.4 支持指挥官显式"退回"：将workflow状态标记为failed，不自动重跑Graph
- [x] 7.6 创建 `nodes/document_generation.py` - 公文生成节点
  - [x] 7.6.1 实现async节点函数
  - [x] 7.6.2 调用MetaGPT OfficialScribe Role
  - [x] 7.6.3 生成最终文档

## 8. LangGraph图编排

- [x] 8.1 创建 `graph.py` - 状态图定义
  - [x] 8.1.1 定义StateGraph
  - [x] 8.1.2 添加所有节点
  - [x] 8.1.3 定义边连接
  - [x] 8.1.4 设置入口和出口
- [x] 8.2 配置PostgreSQL Checkpointer（使用MemorySaver作为默认，PostgreSQL待集成）
  - [x] 8.2.1 复用现有数据库连接
  - [x] 8.2.2 配置checkpointer
- [x] 8.3 实现interrupt机制
  - [x] 8.3.1 在human_review节点中使用interrupt实现人机回环
  - [ ] 8.3.2 测试暂停功能与多事件并发审核场景（需要完整环境）
- [x] 8.4 实现resume机制
  - [x] 8.4.1 实现状态更新逻辑
  - [x] 8.4.2 实现继续执行逻辑
- [x] 8.5 创建 `agent.py` - OverallPlanAgent类
  - [x] 8.5.1 封装图的创建和执行
  - [x] 8.5.2 提供简洁的API接口

## 9. API端点实现

- [x] 9.1 创建 `src/domains/frontend_api/overall_plan/` 目录
- [x] 9.2 创建 `router.py`
  - [x] 9.2.1 实现 `GET /modules` - 触发流程，创建`task_id`并返回初始状态
  - [x] 9.2.2 实现 `GET /status` - 基于`event_id`+`task_id`查询指定run的状态与模块内容
  - [x] 9.2.3 实现 `PUT /approve` - 指挥官审批指定`task_id`，支持approve/reject并携带修改
  - [x] 9.2.4 实现 `GET /document` - 基于`event_id`+`task_id`获取最终文档
- [x] 9.3 使用agent schemas作为API模型
- [x] 9.4 注册路由到frontend_router
  - [x] 9.4.1 更新 `src/domains/frontend_api/router.py`
  - [x] 9.4.2 添加路由前缀 `/api/overall-plan`

## 10. 集成测试

- [ ] 10.1 端到端测试 - 地震场景（需要安装依赖）
  - [ ] 10.1.1 准备测试数据
  - [ ] 10.1.2 测试完整流程
  - [ ] 10.1.3 验证输出质量
- [ ] 10.2 验证CrewAI→MetaGPT数据流转（需要安装依赖）
  - [ ] 10.2.1 验证State正确传递
  - [ ] 10.2.2 验证数据格式兼容
- [ ] 10.3 验证HITL审核流程（需要完整环境）
  - [ ] 10.3.1 测试暂停功能
  - [ ] 10.3.2 测试状态查询
  - [ ] 10.3.3 测试审批恢复
  - [ ] 10.3.4 测试指挥官退回场景：workflow标记为failed且不会自动重跑
- [ ] 10.4 验证状态持久化与恢复（需要PostgreSQL）
  - [ ] 10.4.1 测试服务器重启后恢复
  - [ ] 10.4.2 测试checkpoint正确保存，包括多`task_id`并存时的隔离性
- [ ] 10.5 验证前端对接
  - [ ] 10.5.1 测试API响应格式
  - [ ] 10.5.2 验证与前端组件兼容

## 11. 风险控制

- [ ] 11.1 CrewAI输出增加"结构化总结"Agent
  - [ ] 11.1.1 添加SummaryAgent
  - [ ] 11.1.2 强制输出JSON格式
- [ ] 11.2 上下文超长处理
  - [ ] 11.2.1 实现摘要逻辑
  - [ ] 11.2.2 使用RAG检索详细数据
- [ ] 11.3 指挥官修改数据校验
  - [ ] 11.3.1 定义校验规则
  - [ ] 11.3.2 实现校验逻辑

## 12. 文档和清理

- [x] 12.1 更新 `src/agents/__init__.py` 导出OverallPlanAgent
- [x] 12.2 确认所有代码使用强类型注解
- [x] 12.3 确认所有关键位置有日志输出
- [ ] 12.4 运行类型检查（pyright）
- [ ] 12.5 运行代码格式化（ruff）
