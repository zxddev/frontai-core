-- ============================================================================
-- 审计日志表迁移脚本
-- 版本: v20251207
-- 目的: 创建审计 Schema 和 Break Glass 覆盖记录表
-- 
-- 审计日志设计原则:
--   1. 不可删除 - 仅支持 INSERT 和 SELECT
--   2. 完整记录 - 操作员、规则、目标、原因、时间
--   3. 场景关联 - 通过 scenario_id 关联到具体场景
--
-- 执行前请备份数据！
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. 创建审计 Schema（如果不存在）
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA audit IS '审计日志Schema，记录所有安全相关操作';

-- ============================================================================
-- 2. 创建 Break Glass 覆盖记录表
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit.safety_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 时间
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 操作员信息
    operator_id VARCHAR(64) NOT NULL,
    operator_name VARCHAR(128) NOT NULL,
    operator_role VARCHAR(32) NOT NULL,
    auth_method VARCHAR(32) NOT NULL,

    -- 规则信息
    rule_id VARCHAR(32) NOT NULL,
    rule_name VARCHAR(128) NOT NULL,
    risk_overridden TEXT NOT NULL,

    -- 操作详情
    action_type VARCHAR(64) NOT NULL,
    target_resource JSONB NOT NULL,
    target_event JSONB,

    -- AI 建议
    ai_recommendation JSONB,
    was_adopted BOOLEAN NOT NULL DEFAULT FALSE,

    -- 环境快照与结果
    context JSONB NOT NULL,
    outcome JSONB,
    outcome_recorded_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 约束
    CONSTRAINT chk_confirmation_method CHECK (auth_method IN ('long_press_5s', 'password', 'dual_confirm'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_safety_overrides_operator ON audit.safety_overrides(operator_id);
CREATE INDEX IF NOT EXISTS idx_safety_overrides_rule ON audit.safety_overrides(rule_id);
CREATE INDEX IF NOT EXISTS idx_safety_overrides_time ON audit.safety_overrides(timestamp);

COMMENT ON TABLE audit.safety_overrides IS 'Break Glass 和传感器校准覆盖记录';
COMMENT ON COLUMN audit.safety_overrides.auth_method IS '用于验证确认方式（如长按5秒/密码/双人确认）';

-- ============================================================================
-- 3. 创建传感器校准记录表
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit.sensor_calibrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 时间
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 操作员信息
    operator_id VARCHAR(64) NOT NULL,
    operator_name VARCHAR(128) NOT NULL,
    
    -- 传感器信息
    device_id VARCHAR(64) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,            -- battery, weight, gps, signal
    
    -- 校准值
    original_value NUMERIC NOT NULL,
    calibrated_value NUMERIC NOT NULL,
    calibration_reason TEXT NOT NULL,
    requires_password BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- 约束
    CONSTRAINT chk_sensor_type CHECK (sensor_type IN ('battery', 'weight', 'gps', 'signal', 'temperature', 'wind'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sensor_calibrations_device ON audit.sensor_calibrations(device_id);
CREATE INDEX IF NOT EXISTS idx_sensor_calibrations_time ON audit.sensor_calibrations(timestamp);

COMMENT ON TABLE audit.sensor_calibrations IS '传感器校准记录，用于审计传感器读数修正';

-- ============================================================================
-- 4. 创建审计日志视图（方便查询）
-- ============================================================================

CREATE OR REPLACE VIEW audit.recent_overrides AS
SELECT 
    so.id,
    so.operator_name,
    so.operator_role,
    so.rule_id,
    so.rule_name,
    so.risk_overridden,
    so.timestamp,
    sr.message_template AS rule_message,
    sr.risk_description
FROM audit.safety_overrides so
LEFT JOIN config.safety_rules sr ON so.rule_id = sr.rule_id
WHERE so.timestamp > NOW() - INTERVAL '7 days'
ORDER BY so.timestamp DESC;

COMMENT ON VIEW audit.recent_overrides IS '最近7天的 Break Glass 覆盖记录';

-- ============================================================================
-- 5. 创建触发器防止删除（可选，取消注释启用）
-- ============================================================================

-- CREATE OR REPLACE FUNCTION audit.prevent_delete()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     RAISE EXCEPTION 'DELETE operation is not allowed on audit tables';
--     RETURN NULL;
-- END;
-- $$ LANGUAGE plpgsql;

-- CREATE TRIGGER prevent_safety_overrides_delete
-- BEFORE DELETE ON audit.safety_overrides
-- FOR EACH ROW EXECUTE FUNCTION audit.prevent_delete();

-- CREATE TRIGGER prevent_sensor_calibrations_delete
-- BEFORE DELETE ON audit.sensor_calibrations
-- FOR EACH ROW EXECUTE FUNCTION audit.prevent_delete();

COMMIT;

-- ============================================================================
-- 验证
-- ============================================================================
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'audit';
-- 预期: safety_overrides, sensor_calibrations
