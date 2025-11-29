# Proposal: 使用Instructor优化资源计算模块

## Why

当前资源计算模块（模块1-4, 6-8）的实现存在以下问题：

1. **输出格式不稳定**：LLM生成的文本格式不一致，难以预测
2. **无结构化验证**：无法保证LLM输出包含所有必要字段
3. **模板与逻辑耦合**：报告模板硬编码在prompt中，难以维护
4. **缺乏重试机制**：LLM输出不符合要求时无自动修复

通过深度调研，发现：
- **Instructor** (Jason Liu) 是成熟的结构化LLM输出库
- 已被CrewAI等框架内部使用
- 支持Pydantic模型验证和自动重试

## What Changes

### 新增组件

1. **Instructor集成层** (`instructor/`)
   - Pydantic输出模型定义
   - vLLM兼容的客户端封装

2. **模板系统** (`templates/`)
   - 基于Jinja2的模块报告模板
   - 符合ICS标准的格式规范

### 修改组件

1. **actions.py** - 集成Instructor和模板系统
2. **requirements.txt** - 添加instructor依赖

### 保持不变

1. **estimators.py** - SPHERE标准计算逻辑
2. **roles.py** - ResourcePlanner角色编排
3. **整体架构** - CrewAI + LangGraph + SPHERE

## Impact

### 正面影响
- 输出格式100%符合预期
- 报告质量和一致性提升
- 模板可由领域专家维护
- 计算过程完全可审计

### 风险
- Instructor与vLLM的兼容性需验证
- 额外依赖增加

## Architecture Alignment

本变更符合项目架构原则：
- **分层设计**：计算层(estimators) → 生成层(instructor) → 渲染层(templates)
- **关注点分离**：SPHERE计算与文本生成解耦
- **可测试性**：每层可独立测试
