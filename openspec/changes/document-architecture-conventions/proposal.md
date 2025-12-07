# Change: 建立项目架构规范文档

## Why
项目缺乏系统化的架构规范文档，导致：
1. 新功能开发时不清楚应该放在哪个模块
2. Agent、Service、算法之间的调用关系不明确
3. 通用组件重复开发，没有统一的复用指南
4. 代码审查缺乏架构层面的参考标准

## What Changes
建立完整的架构规范文档体系，包括：
- **architecture/spec.md**: 项目整体架构、目录结构、分层规范
- **agents/spec.md**: Agent层开发规范、LangGraph使用指南、工具调用规范
- **algorithms/spec.md**: 算法层开发规范、基类使用、性能要求
- **domains/spec.md**: 业务域层开发规范、Service模式、Repository模式
- **tooling/spec.md**: 工具封装规范、LLM/KG/RAG工具开发指南

## Impact
- Affected specs: 新增5个capability specs
- Affected code: 无代码变更，纯文档
- 所有后续开发必须遵循此架构规范
