# 扩展 EmergencyAI 实现战略层功能

## 概述

在现有 EmergencyAI 基础上增加 6 个节点，实现战略层功能：
- 任务域分类（生命救护/转移/工程/后勤/次生灾害）
- 阶段优先级（初期/黄金/攻坚/恢复）
- 预编组模块装配
- 运力瓶颈检查
- JSON条件安全规则
- 报告自动生成

## 动机

现有 EmergencyAI 是"战术层"，解决具体资源匹配问题。
缺少"战略层"功能：任务域分类、阶段动态优先级、模块化资源配置。

## 方案

直接扩展 EmergencyAI，新增 6 个节点：
1. `classify_domains` - 任务域分类
2. `apply_phase_priority` - 阶段优先级
3. `assemble_modules` - 模块装配
4. `check_transport` - 运力检查
5. `check_safety_rules` - 安全规则
6. `generate_reports` - 报告生成

## 影响范围

### Neo4j
- 新增节点：TaskDomain(5), DisasterPhase(4), RescueModule(~10)
- 新增关系：BELONGS_TO, PRIORITY_ORDER, PROVIDES
- 扩展属性：TRRRule.domain, TRRRule.subtask_code

### PostgreSQL
- 新增表：config.safety_rules, config.transport_capacity, config.report_templates, config.rescue_module_equipment

### 代码
- 扩展 state.py
- 新增 6 个节点文件
- 修改 graph.py

## 开发规范

1. **日志规范**：所有数据库操作前后加日志
2. **严格报错**：不降级、不Mock，发现问题直接抛错
