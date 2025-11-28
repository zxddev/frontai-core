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
- [ ] 1.4 创建目录结构
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

- [ ] 2.1 创建 `state.py` - OverallPlanState定义
  - [ ] 2.1.1 定义TypedDict状态类型
  - [ ] 2.1.2 定义所有9个模块的状态字段
  - [ ] 2.1.3 定义HITL审核相关字段
- [ ] 2.2 创建 `schemas.py` - API请求/响应模型
  - [ ] 2.2.1 定义 `PlanModulesRequest` 请求模型
  - [ ] 2.2.2 定义 `PlanModulesResponse` 响应模型
  - [ ] 2.2.3 定义 `PlanStatusResponse` 状态响应模型
  - [ ] 2.2.4 定义 `ApproveRequest` 审批请求模型
- [ ] 2.3 定义CrewAI→MetaGPT的中间格式
  - [ ] 2.3.1 定义 `SituationalAwarenessOutput` 模型
  - [ ] 2.3.2 定义 `ResourceCalculationInput` 模型

## 3. SPHERE标准估算器

- [ ] 3.1 创建 `metagpt/estimators.py`
  - [ ] 3.1.1 定义 `SPHERE_STANDARDS` 常量字典
  - [ ] 3.1.2 实现 `estimate_shelter_needs()` - 安置物资估算
  - [ ] 3.1.3 实现 `estimate_rescue_force()` - 救援力量估算
  - [ ] 3.1.4 实现 `estimate_medical_resources()` - 医疗资源估算
  - [ ] 3.1.5 实现 `estimate_infrastructure_force()` - 工程力量估算
  - [ ] 3.1.6 实现 `estimate_communication_needs()` - 通信设备估算
  - [ ] 3.1.7 实现 `estimate_logistics_needs()` - 物资运输估算
  - [ ] 3.1.8 实现 `estimate_self_support()` - 自身保障估算
- [ ] 3.2 编写估算器单元测试
  - [ ] 3.2.1 测试各估算函数的计算正确性
  - [ ] 3.2.2 测试边界条件（0人、大规模灾害）

## 4. CrewAI态势感知子图

- [ ] 4.1 创建 `crewai/__init__.py`
- [ ] 4.2 创建 `crewai/agents.py` - 定义Agent
  - [ ] 4.2.1 定义 `IntelChief` 情报指挥官Agent
  - [ ] 4.2.2 定义 `DisasterAnalyst` 灾情分析员Agent
  - [ ] 4.2.3 配置Agent的LLM和工具
- [ ] 4.3 创建 `crewai/tasks.py` - 定义Task
  - [ ] 4.3.1 定义 `analyze_basic_disaster` Task（模块0）
  - [ ] 4.3.2 定义 `analyze_secondary_disaster` Task（模块5）
  - [ ] 4.3.3 定义Task的输入输出格式
- [ ] 4.4 创建 `crewai/crew.py` - 组装Crew
  - [ ] 4.4.1 实现 `create_situational_awareness_crew()` 函数
  - [ ] 4.4.2 配置Crew的执行模式（sequential）
- [ ] 4.5 实现模块0输出解析
  - [ ] 4.5.1 定义结构化输出Schema
  - [ ] 4.5.2 实现输出解析逻辑
- [ ] 4.6 实现模块5输出解析
  - [ ] 4.6.1 定义文本输出格式
  - [ ] 4.6.2 实现输出解析逻辑
- [ ] 4.7 测试CrewAI独立运行
  - [ ] 4.7.1 编写mock数据测试用例
  - [ ] 4.7.2 验证输出格式正确

## 5. MetaGPT资源计算子图

- [ ] 5.1 创建 `metagpt/__init__.py`
- [ ] 5.2 创建 `metagpt/actions.py` - 定义Action
  - [ ] 5.2.1 实现 `CalculateRescueForce` Action（模块1）
  - [ ] 5.2.2 实现 `CalculateMedicalResources` Action（模块2）
  - [ ] 5.2.3 实现 `CalculateInfrastructure` Action（模块3）
  - [ ] 5.2.4 实现 `CalculateShelter` Action（模块4）
  - [ ] 5.2.5 实现 `CalculateCommunication` Action（模块6）
  - [ ] 5.2.6 实现 `CalculateLogistics` Action（模块7）
  - [ ] 5.2.7 实现 `CalculateSelfSupport` Action（模块8）
- [ ] 5.3 创建 `metagpt/roles.py` - 定义Role
  - [ ] 5.3.1 实现 `ResourcePlanner` Role
  - [ ] 5.3.2 配置Role的Action列表
  - [ ] 5.3.3 配置Role的LLM
- [ ] 5.4 实现模块1-4, 6-8输出生成
  - [ ] 5.4.1 调用估算器计算数值
  - [ ] 5.4.2 使用LLM生成专业文本
- [ ] 5.5 测试MetaGPT独立运行
  - [ ] 5.5.1 编写mock数据测试用例
  - [ ] 5.5.2 验证计算结果正确
  - [ ] 5.5.3 验证输出文本质量

## 6. MetaGPT公文生成

- [ ] 6.1 创建 `metagpt/scribe.py` - 公文秘书Role
  - [ ] 6.1.1 实现 `GenerateOfficialDocument` Action
  - [ ] 6.1.2 实现 `OfficialScribe` Role
  - [ ] 6.1.3 定义公文模板格式
- [ ] 6.2 实现9模块整合逻辑
  - [ ] 6.2.1 合并CrewAI和MetaGPT输出
  - [ ] 6.2.2 生成标准格式文档
- [ ] 6.3 测试公文生成
  - [ ] 6.3.1 验证文档结构完整
  - [ ] 6.3.2 验证格式符合规范

## 7. LangGraph节点实现

- [ ] 7.1 创建 `nodes/__init__.py`
- [ ] 7.2 创建 `nodes/load_context.py` - 数据聚合节点
  - [ ] 7.2.1 查询events_v2表获取事件数据
  - [ ] 7.2.2 查询ai_decision_logs_v2获取EmergencyAI分析结果
  - [ ] 7.2.3 查询资源库获取可用资源
  - [ ] 7.2.4 组装为State格式
- [ ] 7.3 创建 `nodes/situational_awareness.py` - CrewAI封装节点
  - [ ] 7.3.1 实现async节点函数
  - [ ] 7.3.2 使用run_in_executor调用CrewAI（避免event loop冲突）
  - [ ] 7.3.3 解析输出更新State
- [ ] 7.4 创建 `nodes/resource_calculation.py` - MetaGPT封装节点
  - [ ] 7.4.1 实现async节点函数
  - [ ] 7.4.2 调用MetaGPT ResourcePlanner Role
  - [ ] 7.4.3 解析输出更新State
- [ ] 7.5 创建 `nodes/human_review.py` - HITL审核节点
  - [ ] 7.5.1 实现审核状态检查
  - [ ] 7.5.2 实现状态持久化
  - [ ] 7.5.3 实现resume逻辑
- [ ] 7.6 创建 `nodes/document_generation.py` - 公文生成节点
  - [ ] 7.6.1 实现async节点函数
  - [ ] 7.6.2 调用MetaGPT OfficialScribe Role
  - [ ] 7.6.3 生成最终文档

## 8. LangGraph图编排

- [ ] 8.1 创建 `graph.py` - 状态图定义
  - [ ] 8.1.1 定义StateGraph
  - [ ] 8.1.2 添加所有节点
  - [ ] 8.1.3 定义边连接
  - [ ] 8.1.4 设置入口和出口
- [ ] 8.2 配置PostgreSQL Checkpointer
  - [ ] 8.2.1 复用现有数据库连接
  - [ ] 8.2.2 配置checkpointer
- [ ] 8.3 实现interrupt_before
  - [ ] 8.3.1 在document_generation前设置断点
  - [ ] 8.3.2 测试暂停功能
- [ ] 8.4 实现resume机制
  - [ ] 8.4.1 实现状态更新逻辑
  - [ ] 8.4.2 实现继续执行逻辑
- [ ] 8.5 创建 `agent.py` - OverallPlanAgent类
  - [ ] 8.5.1 封装图的创建和执行
  - [ ] 8.5.2 提供简洁的API接口

## 9. API端点实现

- [ ] 9.1 创建 `src/domains/frontend_api/overall_plan/` 目录
- [ ] 9.2 创建 `router.py`
  - [ ] 9.2.1 实现 `GET /modules` - 触发流程
  - [ ] 9.2.2 实现 `GET /status` - 查询状态
  - [ ] 9.2.3 实现 `PUT /approve` - 指挥官审批
  - [ ] 9.2.4 实现 `GET /document` - 获取最终文档
- [ ] 9.3 创建 `schemas.py` - API模型（如果与agent schemas不同）
- [ ] 9.4 注册路由到frontend_router
  - [ ] 9.4.1 更新 `src/domains/frontend_api/router.py`
  - [ ] 9.4.2 添加路由前缀 `/api/overall-plan`

## 10. 集成测试

- [ ] 10.1 端到端测试 - 地震场景
  - [ ] 10.1.1 准备测试数据
  - [ ] 10.1.2 测试完整流程
  - [ ] 10.1.3 验证输出质量
- [ ] 10.2 验证CrewAI→MetaGPT数据流转
  - [ ] 10.2.1 验证State正确传递
  - [ ] 10.2.2 验证数据格式兼容
- [ ] 10.3 验证HITL审核流程
  - [ ] 10.3.1 测试暂停功能
  - [ ] 10.3.2 测试状态查询
  - [ ] 10.3.3 测试审批恢复
- [ ] 10.4 验证状态持久化与恢复
  - [ ] 10.4.1 测试服务器重启后恢复
  - [ ] 10.4.2 测试checkpoint正确保存
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

- [ ] 12.1 更新 `src/agents/__init__.py` 导出OverallPlanAgent
- [ ] 12.2 确认所有代码使用强类型注解
- [ ] 12.3 确认所有关键位置有日志输出
- [ ] 12.4 运行类型检查（pyright）
- [ ] 12.5 运行代码格式化（ruff）
