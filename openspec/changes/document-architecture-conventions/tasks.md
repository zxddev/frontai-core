## 1. 架构规范文档编写

- [x] 1.1 创建change目录结构
- [x] 1.2 编写proposal.md
- [x] 1.3 编写architecture/spec.md（整体架构）
- [x] 1.4 编写agents/spec.md（Agent层规范）
- [x] 1.5 编写algorithms/spec.md（算法层规范）
- [x] 1.6 编写domains/spec.md（业务域层规范）
- [x] 1.7 编写tooling/spec.md（工具调用规范）

## 2. 验证与归档

- [x] 2.1 运行openspec validate验证文档格式
- [ ] 2.2 团队评审架构规范
- [ ] 2.3 归档到openspec/specs/

## 3. ReconScheduler V2.1规范更新

- [x] 3.1 更新agents/spec.md（验证机制规范）
  - 添加ReconScheduler验证机制要求
  - 添加区域可行性预检查规范
  - 添加设备能力参数来源规范
  - 添加成功判断逻辑规范
- [x] 3.2 更新architecture/spec.md（关键日志规范）
  - 添加救援系统关键日志要求
  - 添加日志格式示例
  - 添加日志级别选择规范
- [x] 3.3 新建testing/spec.md（测试验证规范）
  - 五级验证架构
  - 数学验证公式
  - 边界条件测试
  - 测试文件结构
  - 异步测试规范
- [ ] 3.4 团队评审V2.1规范更新

## 4. OverallPlan Agent修复经验文档化

- [x] 4.1 更新domains/spec.md（AlgorithmConfigService规范）
  - 添加独立列与JSONB字段合并说明
  - 添加name_cn字段获取示例
  - 添加配置缺失处理规范
- [x] 4.2 更新agents/spec.md（overall_plan架构）
  - 更新Agent清单中OverallPlanAgent描述
  - 添加数据驱动架构规范
  - 添加无降级原则实现示例
  - 添加SPHERE计算失败处理规范
  - 添加完整数据来源清单（7个数据表）
  - 添加字段映射详情（events_v2/scenarios_v2/command_group_templates_v2）
- [x] 4.3 更新architecture/spec.md（数据库查询过滤）
  - 添加scenario_id过滤规范
  - 添加数据隔离验证要求
  - 列出必须过滤的表清单
- [x] 4.4 更新algorithms/spec.md（SPHERE计算规范）
  - 添加SphereDemandCalculator使用示例
  - 添加SPHERE标准公式说明
  - 添加受灾人口校验要求
  - 添加物资名称显示规范

## 5. ReconSchedulerAgent继承BaseAgent重构

- [x] 5.1 重构agent.py继承BaseAgent
  - 实现build_graph()：返回get_recon_scheduler_graph()
  - 实现prepare_input()：60+字段初始状态构建
  - 实现process_output()：结果处理+成功判断
  - 覆盖arun()：设置recursion_limit=100
  - 保留schedule()便捷方法：内部调用arun
- [x] 5.2 更新agents/spec.md
  - 移除ReconSchedulerAgent例外说明
  - 添加ReconSchedulerAgent特殊处理场景
- [x] 5.3 测试验证
  - 小区域成功路径：status=completed ✓
  - 大区域拒绝路径：status=failed ✓
