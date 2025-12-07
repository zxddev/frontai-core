# Change: Recon Agent V2.1 Spec (streaming, safety-first)

## Why
- Align侦察Agent到实时、流式、可自愈的生命救援场景，消除V1线性/批处理和2D假设带来的安全缺陷。
- 固化强制中继、分级验证、动态能耗、坐标标准、业务/控制数据契约和断点恢复，供后续实现遵循。

## What Changes
- 新增 recon-agent 能力规范：流式情报输出、L1/L2分级校验、重试+熔断+降级、自带中继防盲飞、UTM核心坐标、动态能耗模型、Checkpoints、性能护栏。
- 规定业务/控制数据分离与 PostGIS/DDLP 事件契约，以及恢复/重规划要求。

## Impact
- 影响模块：侦察 LangGraph 编排、Validation/Simulator、Stream Emitter、Checkpoint/Resume、Device/Energy 模型、坐标/Geo 工具。
- 影响数据契约：情报事件（confidence/source/SRID）、航线输出（DJI-like），world-model/PostGIS 更新流程。
