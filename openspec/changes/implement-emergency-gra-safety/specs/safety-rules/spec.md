## ADDED Requirements

### Requirement: 三级安全规则体系
系统 SHALL 实现三级安全规则体系保护人命安全：

| 级别 | 类型 | 动作 | 确认方式 | 审计 |
|------|------|------|----------|------|
| 第一级 | 硬性阻断 | REJECT | 按钮置灰，不可Override | 无需 |
| 第二级 | Break Glass | BREAK_GLASS | 长按5秒确认 | 必须记录 |
| 第三级 | 软性提示 | WARN | 点击确认即可 | 可选 |

#### Scenario: 硬性阻断无法绕过
- **WHEN** 触发硬性阻断规则（如电量不足）
- **THEN** 操作按钮置灰，无法点击
- **AND** 显示阻断原因和解决建议
- **AND** 提供"传感器校准"入口（需主指挥员密码）

#### Scenario: Break Glass需要特别确认
- **WHEN** 触发Break Glass规则（如无防护进危险区）
- **THEN** 显示风险说明和AI替代方案
- **AND** 要求长按5秒确认
- **AND** 确认后记录到审计日志

### Requirement: 硬性阻断规则库
系统 SHALL 包含以下硬性阻断规则：

| 规则ID | 规则名称 | 触发条件 | 提示文案 |
|--------|----------|----------|----------|
| HB_001 | 电量不足返航 | battery < min_return + 10% | "电量不足以安全返航" |
| HB_002 | 超载 | weight > max_takeoff_weight | "载重超过物理极限" |
| HB_003 | 桥梁限重 | vehicle_weight > bridge_limit | "超过桥梁承载能力" |
| HB_004 | 禁飞区 | target in no_fly_zone | "目标位于禁飞区" |
| HB_005 | 设备损坏 | device_status == "damaged" | "设备已损坏无法使用" |

#### Scenario: 电量不足阻断
- **WHEN** 设备电量 < 返航所需 + 10%安全余量
- **THEN** 触发 HB_001 规则
- **AND** 按钮置灰，显示"电量不足以安全返航"

### Requirement: Break Glass规则库
系统 SHALL 包含以下Break Glass规则：

| 规则ID | 规则名称 | 触发条件 | 风险说明 |
|--------|----------|----------|----------|
| BG_001 | 风速超限 | wind_speed > device_wind_rating | "可能导致设备失控坠毁" |
| BG_002 | 能见度不足 | visibility < 500m | "可能导致碰撞事故" |
| BG_003 | 无防化装备进毒区 | zone=chemical_leak AND !has_chemical_suit | "可能导致人员中毒" |
| BG_004 | 无救生装备进深水 | zone=deep_water AND !has_life_jacket | "可能导致人员溺水" |
| BG_005 | 无防火装备进火场 | zone=fire AND !has_fire_suit | "可能导致人员烧伤" |
| BG_006 | 过度疲劳 | continuous_work_hours > 12 | "可能导致判断失误" |
| BG_007 | 电量勉强够用 | min_return < battery < task_required + 20% | "可能无法完成任务" |
| BG_008 | 夜间无夜视 | is_night AND !has_night_vision | "可能无法有效侦察" |
| BG_009 | 通信弱区 | signal_strength < -90dBm | "可能失去联系" |
| BG_010 | 建筑坍塌风险 | building_assessment == "dangerous" | "可能发生二次坍塌" |

#### Scenario: 无防化装备触发Break Glass
- **WHEN** 目标区域为化学泄漏区
- **AND** 队伍没有防化装备
- **THEN** 触发 BG_003 规则
- **AND** 显示"可能导致人员中毒"
- **AND** 提供替代方案：特勤中队（有防化装备）

### Requirement: 软性提示规则库
系统 SHALL 包含以下软性提示规则：

| 规则ID | 规则名称 | 触发条件 | 提示文案 |
|--------|----------|----------|----------|
| SW_001 | 到达超时 | eta > golden_rescue_time | "预计到达时间较长，可能影响救援效果" |
| SW_002 | 轻度疲劳 | 6 < continuous_work_hours < 12 | "队伍有一定疲劳，注意监控状态" |
| SW_003 | 非关键装备缺失 | missing_optional_equipment | "部分装备缺失，可能影响效率" |
| SW_004 | 路线拥堵 | route_congestion_level > 0.5 | "推荐路线有拥堵，预计延时X分钟" |
| SW_005 | 非最优匹配 | better_match_exists | "有更专业的队伍可选，但距离较远" |
| SW_006 | 存在更近队伍 | closer_team_exists | "有更近的队伍，但专业能力略弱" |
| SW_007 | 天气变化趋势 | weather_forecast_worsening | "未来X小时天气可能恶化" |
| SW_008 | 电量中等 | 50% < battery < 70% | "设备电量中等，建议优先完成" |

#### Scenario: 软性提示确认
- **WHEN** 触发软性提示规则
- **THEN** 显示提示信息
- **AND** 用户点击确认即可继续
- **AND** 不强制记录审计日志

### Requirement: 安全规则数据库配置
安全规则 SHALL 存储在 config.safety_rules 表，便于动态维护：

```sql
CREATE TABLE config.safety_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 规则标识
    rule_id VARCHAR(32) NOT NULL UNIQUE,  -- HB_001, BG_003, SW_001
    rule_name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(16) NOT NULL,       -- reject, break_glass, warn（与HardRuleAction枚举一致）
    
    -- 触发条件（可选前置条件）
    condition_field VARCHAR(64),          -- target_zone_type
    condition_operator VARCHAR(16),       -- eq, ne, gt, gte, lt, lte, in, not_in, contains, regex
    condition_value JSONB,                -- "chemical_leak"
    
    -- 检查条件
    check_field VARCHAR(64) NOT NULL,     -- battery_level, has_chemical_suit
    check_operator VARCHAR(16) NOT NULL,  -- lt, gt, eq
    check_threshold JSONB,                -- 固定阈值
    check_threshold_field VARCHAR(64),    -- 动态阈值字段名
    
    -- 提示信息
    message_template TEXT NOT NULL,       -- "电量{value}%不足（需{threshold}%）"
    risk_description TEXT,                -- Break Glass专用
    severity VARCHAR(16) NOT NULL,        -- critical, high, medium, low
    
    -- 元数据
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_safety_rules_type ON config.safety_rules(rule_type);
CREATE INDEX idx_safety_rules_active ON config.safety_rules(is_active);
```

#### Scenario: 从数据库加载规则
- **WHEN** 系统启动或规则重载
- **THEN** 从 config.safety_rules 表加载所有 is_active=true 的规则
- **AND** 按 rule_type 分类（reject/break_glass/warn）
- **AND** 按 sort_order 排序

#### Scenario: 动态更新规则
- **WHEN** 管理员修改规则配置
- **THEN** 下次规则检查时生效
- **AND** 无需重启服务

#### Scenario: 规则字段校验
- **WHEN** 加载规则记录
- **THEN** 验证 rule_id, rule_name, rule_type, check_field, check_operator, message_template 必填
- **AND** rule_type 必须是 reject/break_glass/warn 之一

### Requirement: 传感器校准入口
硬性阻断规则 SHALL 提供传感器校准入口防止系统死锁：

```python
class SensorCalibration(BaseModel):
    """传感器校准请求"""
    sensor_type: str           # 传感器类型（battery, weight等）
    original_value: float      # 原始读数
    calibrated_value: float    # 校准后读数
    reason: str                # 校准原因
    operator_id: str           # 操作员ID
    requires_password: bool = True  # 需要主指挥员密码
```

#### Scenario: 传感器校准流程
- **WHEN** 指挥员确认传感器读数有误
- **THEN** 点击"传感器校准"入口
- **AND** 输入主指挥员密码
- **AND** 填写校准值和原因
- **AND** 记录完整审计日志
