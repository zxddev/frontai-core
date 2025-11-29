# Tasks: 使用Instructor优化资源计算模块

## Phase 1: 环境准备

- [x] 1.1 安装instructor依赖 (已通过CrewAI依赖安装)
- [ ] 1.2 验证instructor与vLLM兼容性
- [x] 1.3 创建目录结构

## Phase 2: Pydantic输出模型

- [x] 2.1 创建 `instructor/models.py`
  - [x] 2.1.1 `RescueForceModuleOutput` - 模块1输出
  - [x] 2.1.2 `MedicalModuleOutput` - 模块2输出
  - [x] 2.1.3 `InfrastructureModuleOutput` - 模块3输出
  - [x] 2.1.4 `ShelterModuleOutput` - 模块4输出
  - [x] 2.1.5 `CommunicationModuleOutput` - 模块6输出
  - [x] 2.1.6 `LogisticsModuleOutput` - 模块7输出
  - [x] 2.1.7 `SelfSupportModuleOutput` - 模块8输出
- [x] 2.2 创建 `instructor/__init__.py` 导出模型

## Phase 3: Instructor客户端

- [x] 3.1 创建 `instructor/client.py`
  - [x] 3.1.1 `create_instructor_client()` - 创建客户端
  - [x] 3.1.2 支持vLLM (OpenAI兼容模式)
  - [x] 3.1.3 配置重试机制
- [ ] 3.2 测试客户端连接vLLM

## Phase 4: Jinja2模板系统

- [x] 4.1 创建 `templates/modules.py`
  - [x] 4.1.1 `MODULE_1_TEMPLATE` - 应急救援力量部署
  - [x] 4.1.2 `MODULE_2_TEMPLATE` - 医疗救护部署
  - [x] 4.1.3 `MODULE_3_TEMPLATE` - 基础设施抢修
  - [x] 4.1.4 `MODULE_4_TEMPLATE` - 临时安置与生活保障
  - [x] 4.1.5 `MODULE_6_TEMPLATE` - 通信与信息保障
  - [x] 4.1.6 `MODULE_7_TEMPLATE` - 物资调拨与运输保障
  - [x] 4.1.7 `MODULE_8_TEMPLATE` - 救援力量自身保障
- [x] 4.2 实现 `render_module_template()` 函数
- [x] 4.3 添加自定义Jinja2过滤器（数字格式化等）
- [x] 4.4 创建 `templates/__init__.py` 导出函数

## Phase 5: 重构actions.py

- [x] 5.1 添加Instructor导入
- [x] 5.2 重构 `calculate_rescue_force_module()`
- [x] 5.3 重构 `calculate_medical_module()`
- [x] 5.4 重构 `calculate_infrastructure_module()`
- [x] 5.5 重构 `calculate_shelter_module()`
- [x] 5.6 重构 `calculate_communication_module()`
- [x] 5.7 重构 `calculate_logistics_module()`
- [x] 5.8 重构 `calculate_self_support_module()`
- [x] 5.9 移除旧的 `generate_module_text()` 函数（被Instructor+Template替代）

## Phase 6: 更新依赖角色

- [x] 6.1 更新 `roles.py` 中的 `ResourcePlanner`
  - [x] 6.1.1 初始化时支持Instructor客户端
  - [x] 6.1.2 传递客户端给各计算函数
- [x] 6.2 更新 `resource_calculation_node.py`
  - [x] 6.2.1 适配新的客户端创建方式
  - [x] 6.2.2 移除旧的 `_create_default_llm()` 函数

## Phase 7: 测试验证

- [x] 7.1 单元测试
  - [x] 7.1.1 Pydantic模型导入测试
  - [x] 7.1.2 模板渲染测试（通过，输出符合ICS格式）
- [ ] 7.2 集成测试
  - [ ] 7.2.1 单模块端到端测试（需vLLM）
  - [ ] 7.2.2 完整ResourcePlanner测试（需vLLM）
- [ ] 7.3 API测试
  - [ ] 7.3.1 `/api/v1/overall-plan/{event_id}/modules` 测试

## Phase 8: 文档和清理

- [ ] 8.1 更新 `metagpt/__init__.py` 导出
- [x] 8.2 语法检查通过
- [ ] 8.3 运行pyright类型检查（ruff未安装）
