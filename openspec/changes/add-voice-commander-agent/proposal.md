# Change: 语音指挥Agent能力扩展

## Why

当前VoiceChatManager是被动的"问答引擎"，缺乏：
1. **空间智能**：无法回答"Alpha队在哪里"、"最近的无人机是哪个"
2. **机器人控制**：无法执行"派无人机去B区侦查"等指令
3. **安全屏障**：高风险指令缺乏确认机制

**参考依据：**
- 设计文档：`docs/agent架构选型/语音聊天Agent能力扩展设计.md`
- 项目已有基础：PostGIS空间数据、STOMP协议、LangGraph interrupt机制

## What Changes

- **ADDED** SemanticRouter：毫秒级意图分流（中文优化embedding）
- **ADDED** SpatialAgent：空间查询能力（位置、距离、区域状态）
- **ADDED** CommanderAgent：机器人控制（带中断-确认安全机制）
- **ADDED** 空间查询工具链：find_entity_location, find_nearest_unit, get_area_status
- **ADDED** 控制工具链：prepare_dispatch_command, execute_confirmed_command
- **MODIFIED** VoiceChatManager：集成语义路由和Agent分发

## Impact

- Affected specs: 新增 `specs/voice-commander/spec.md`
- Affected code:
  - `src/agents/voice_commander/` (新增)
  - `src/domains/voice/router.py` (修改)
  - `src/infra/settings.py` (新增配置)
  - `src/agents/db/spatial.py` (新增)

## Safety Principles

**机器人控制必须遵循：**
1. 所有写操作强制human-in-the-loop确认
2. 高阈值路由（0.85）防止误触发
3. 安全检查门控（禁飞区、电量、冲突任务）
4. 完整trace记录
