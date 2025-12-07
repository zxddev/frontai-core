-- ============================================================================
-- 安全规则表迁移脚本
-- 版本: v20251207
-- 目的: 创建三级安全规则体系的数据库表（硬性阻断/Break Glass/软性提示）
-- 
-- 规则类型:
--   1. reject - 硬性阻断，按钮置灰不可Override
--   2. break_glass - Break Glass，长按5秒确认，必须审计
--   3. warn - 软性提示，点击确认即可
--
-- 执行前请备份数据！
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. 创建安全规则表
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.safety_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 规则标识
    rule_id VARCHAR(32) NOT NULL UNIQUE,      -- HB_001, BG_003, SW_001
    rule_name VARCHAR(128) NOT NULL,
    rule_type VARCHAR(16) NOT NULL,           -- reject, break_glass, warn
    
    -- 触发条件（可选前置条件）
    condition_field VARCHAR(64),              -- target_zone_type
    condition_operator VARCHAR(16),           -- eq, ne, gt, gte, lt, lte, in, not_in, contains, regex
    condition_value JSONB,                    -- "chemical_leak"
    
    -- 检查条件
    check_field VARCHAR(64) NOT NULL,         -- battery_level, has_chemical_suit
    check_operator VARCHAR(16) NOT NULL,      -- lt, gt, eq, gte, lte
    check_threshold JSONB,                    -- 固定阈值
    check_threshold_field VARCHAR(64),        -- 动态阈值字段名
    
    -- 提示信息
    message_template TEXT NOT NULL,           -- "电量{value}%不足（需{threshold}%）"
    risk_description TEXT,                    -- Break Glass专用
    severity VARCHAR(16) NOT NULL,            -- critical, high, medium, low
    
    -- 元数据
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 约束
    CONSTRAINT chk_rule_type CHECK (rule_type IN ('reject', 'break_glass', 'warn')),
    CONSTRAINT chk_severity CHECK (severity IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT chk_check_operator CHECK (check_operator IN ('eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'not_in', 'contains', 'regex'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_safety_rules_type ON config.safety_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_safety_rules_active ON config.safety_rules(is_active);

COMMENT ON TABLE config.safety_rules IS '三级安全规则配置表';
COMMENT ON COLUMN config.safety_rules.rule_type IS 'reject=硬性阻断, break_glass=需确认, warn=软性提示';

-- ============================================================================
-- 2. 插入硬性阻断规则（5条）
-- ============================================================================

INSERT INTO config.safety_rules (rule_id, rule_name, rule_type, check_field, check_operator, check_threshold, check_threshold_field, message_template, severity, sort_order)
VALUES
    ('HB_001', '电量不足返航', 'reject', 'battery_level', 'lt', NULL, 'min_return_battery', '电量{value}%不足以安全返航（需{threshold}%）', 'critical', 1),
    ('HB_002', '超载', 'reject', 'current_weight', 'gt', NULL, 'max_takeoff_weight', '载重{value}kg超过物理极限（限{threshold}kg）', 'critical', 2),
    ('HB_003', '桥梁限重', 'reject', 'vehicle_weight', 'gt', NULL, 'bridge_weight_limit', '车重{value}吨超过桥梁承载能力（限{threshold}吨）', 'critical', 3),
    ('HB_004', '禁飞区', 'reject', 'target_in_no_fly_zone', 'eq', 'true', NULL, '目标位于禁飞区，禁止飞行', 'critical', 4),
    ('HB_005', '设备损坏', 'reject', 'device_status', 'eq', '"damaged"', NULL, '设备已损坏无法使用', 'critical', 5)
ON CONFLICT (rule_id) DO NOTHING;

-- ============================================================================
-- 3. 插入 Break Glass 规则（10条）
-- ============================================================================

INSERT INTO config.safety_rules (rule_id, rule_name, rule_type, condition_field, condition_operator, condition_value, check_field, check_operator, check_threshold, message_template, risk_description, severity, sort_order)
VALUES
    ('BG_001', '风速超限', 'break_glass', NULL, NULL, NULL, 'wind_speed', 'gt', NULL, '当前风速{value}m/s超过设备限制（{threshold}m/s）', '可能导致设备失控坠毁', 'high', 10),
    ('BG_002', '能见度不足', 'break_glass', NULL, NULL, NULL, 'visibility', 'lt', '500', '当前能见度{value}m不足（需500m）', '可能导致碰撞事故', 'high', 11),
    ('BG_003', '无防化装备进毒区', 'break_glass', 'target_zone_type', 'eq', '"chemical_leak"', 'has_chemical_suit', 'eq', 'false', '队伍无防化装备，即将进入化学泄漏区', '可能导致人员中毒', 'critical', 12),
    ('BG_004', '无救生装备进深水', 'break_glass', 'target_zone_type', 'eq', '"deep_water"', 'has_life_jacket', 'eq', 'false', '队伍无救生装备，即将进入深水区', '可能导致人员溺水', 'critical', 13),
    ('BG_005', '无防火装备进火场', 'break_glass', 'target_zone_type', 'eq', '"fire"', 'has_fire_suit', 'eq', 'false', '队伍无防火装备，即将进入火场', '可能导致人员烧伤', 'critical', 14),
    ('BG_006', '过度疲劳', 'break_glass', NULL, NULL, NULL, 'continuous_work_hours', 'gt', '12', '队伍已连续工作{value}小时（超过12小时）', '可能导致判断失误', 'high', 15),
    ('BG_007', '电量勉强够用', 'break_glass', NULL, NULL, NULL, 'battery_margin', 'lt', '20', '电量余量仅{value}%（建议20%以上）', '可能无法完成任务', 'medium', 16),
    ('BG_008', '夜间无夜视', 'break_glass', 'is_night', 'eq', 'true', 'has_night_vision', 'eq', 'false', '夜间任务但队伍无夜视设备', '可能无法有效侦察', 'medium', 17),
    ('BG_009', '通信弱区', 'break_glass', NULL, NULL, NULL, 'signal_strength', 'lt', '-90', '信号强度{value}dBm过弱（需>-90dBm）', '可能失去联系', 'high', 18),
    ('BG_010', '建筑坍塌风险', 'break_glass', NULL, NULL, NULL, 'building_assessment', 'eq', '"dangerous"', '目标建筑评估为危险级别', '可能发生二次坍塌', 'critical', 19)
ON CONFLICT (rule_id) DO NOTHING;

-- 补充 BG_001 的动态阈值字段
UPDATE config.safety_rules SET check_threshold_field = 'device_wind_rating' WHERE rule_id = 'BG_001';

-- ============================================================================
-- 4. 插入软性提示规则（8条）
-- ============================================================================

INSERT INTO config.safety_rules (rule_id, rule_name, rule_type, check_field, check_operator, check_threshold, check_threshold_field, message_template, severity, sort_order)
VALUES
    ('SW_001', '到达超时', 'warn', 'eta_minutes', 'gt', NULL, 'golden_rescue_time', '预计到达{value}分钟，超过黄金救援时间（{threshold}分钟）', 'medium', 20),
    ('SW_002', '轻度疲劳', 'warn', 'continuous_work_hours', 'gt', '6', NULL, '队伍已连续工作{value}小时，注意监控状态', 'low', 21),
    ('SW_003', '非关键装备缺失', 'warn', 'missing_optional_equipment_count', 'gt', '0', NULL, '缺少{value}件可选装备，可能影响效率', 'low', 22),
    ('SW_004', '路线拥堵', 'warn', 'route_congestion_level', 'gt', '0.5', NULL, '推荐路线拥堵指数{value}，预计延时', 'low', 23),
    ('SW_005', '非最优匹配', 'warn', 'better_match_exists', 'eq', 'true', NULL, '有更专业的队伍可选，但距离较远', 'low', 24),
    ('SW_006', '存在更近队伍', 'warn', 'closer_team_exists', 'eq', 'true', NULL, '有更近的队伍，但专业能力略弱', 'low', 25),
    ('SW_007', '天气变化趋势', 'warn', 'weather_forecast_worsening', 'eq', 'true', NULL, '未来数小时天气可能恶化', 'medium', 26),
    ('SW_008', '电量中等', 'warn', 'battery_level', 'lt', '70', NULL, '设备电量{value}%中等，建议优先完成任务', 'low', 27)
ON CONFLICT (rule_id) DO NOTHING;

-- 补充 SW_002 的条件（仅当工作时间在6-12小时之间）
UPDATE config.safety_rules 
SET condition_field = 'continuous_work_hours', 
    condition_operator = 'lte', 
    condition_value = '12'
WHERE rule_id = 'SW_002';

-- 补充 SW_008 的条件（仅当电量在50%-70%之间）
UPDATE config.safety_rules 
SET condition_field = 'battery_level', 
    condition_operator = 'gte', 
    condition_value = '50'
WHERE rule_id = 'SW_008';

COMMIT;

-- ============================================================================
-- 验证
-- ============================================================================
-- SELECT rule_type, count(*) FROM config.safety_rules GROUP BY rule_type;
-- 预期: reject=5, break_glass=10, warn=8
