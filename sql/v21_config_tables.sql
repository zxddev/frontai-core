-- ============================================================================
-- v21_config_tables.sql
-- 配置数据表：硬规则、评估权重、枚举映射
-- ============================================================================

-- 创建config schema（如果不存在）
CREATE SCHEMA IF NOT EXISTS config;

-- ============================================================================
-- 1. 硬规则配置表
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.hard_rules (
    rule_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    field VARCHAR(50) NOT NULL,
    operator VARCHAR(10) NOT NULL,
    threshold DECIMAL(10,4) NOT NULL,
    message TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE config.hard_rules IS '硬规则配置表：一票否决规则';
COMMENT ON COLUMN config.hard_rules.field IS '检查字段：risk_level, response_time_min, coverage_rate, capacity_coverage_rate';
COMMENT ON COLUMN config.hard_rules.operator IS '比较操作符：<=, >=, ==, <, >';

TRUNCATE TABLE config.hard_rules;

INSERT INTO config.hard_rules (rule_id, name, field, operator, threshold, message) VALUES
('HR-EM-001', '救援人员安全红线', 'risk_level', '<=', 0.15, '救援人员伤亡风险超过15%，方案否决'),
('HR-EM-002', '黄金救援时间', 'response_time_min', '<=', 180, '预计响应时间超过3小时，方案否决'),
('HR-EM-003', '关键能力覆盖', 'coverage_rate', '>=', 0.7, '关键能力覆盖率不足70%'),
('HR-EM-004', '救援容量底线', 'capacity_coverage_rate', '>=', 0.5, '救援容量覆盖率不足50%，资源严重不足需紧急增援');

-- ============================================================================
-- 2. 评估权重配置表
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.evaluation_weights (
    disaster_type VARCHAR(30) PRIMARY KEY,
    success_rate DECIMAL(4,2) NOT NULL,
    response_time DECIMAL(4,2) NOT NULL,
    coverage_rate DECIMAL(4,2) NOT NULL,
    risk DECIMAL(4,2) NOT NULL,
    redundancy DECIMAL(4,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT check_weights_sum CHECK (
        ABS(success_rate + response_time + coverage_rate + risk + redundancy - 1.0) < 0.01
    )
);

COMMENT ON TABLE config.evaluation_weights IS '5维评估权重配置表';
COMMENT ON COLUMN config.evaluation_weights.disaster_type IS '灾害类型：default, earthquake, fire, flood, hazmat等';

TRUNCATE TABLE config.evaluation_weights;

INSERT INTO config.evaluation_weights (disaster_type, success_rate, response_time, coverage_rate, risk, redundancy, description) VALUES
('default', 0.35, 0.30, 0.20, 0.05, 0.10, '默认权重配置'),
('earthquake', 0.35, 0.35, 0.15, 0.05, 0.10, '地震：黄金72小时，响应时间权重提高'),
('fire', 0.30, 0.40, 0.15, 0.05, 0.10, '火灾：响应时间最关键'),
('flood', 0.30, 0.35, 0.20, 0.05, 0.10, '洪水：覆盖率和响应时间并重'),
('hazmat', 0.25, 0.30, 0.25, 0.10, 0.10, '危化品：风险权重提高');

-- ============================================================================
-- 3. 枚举映射配置表
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.enum_mappings (
    category VARCHAR(30) NOT NULL,
    code VARCHAR(20) NOT NULL,
    display_name VARCHAR(50),
    score DECIMAL(4,2),
    sort_order INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (category, code)
);

COMMENT ON TABLE config.enum_mappings IS '枚举值映射配置表';
COMMENT ON COLUMN config.enum_mappings.category IS '分类：severity, priority';
COMMENT ON COLUMN config.enum_mappings.display_name IS '中文显示名';
COMMENT ON COLUMN config.enum_mappings.score IS '数值评分（用于计算）';

TRUNCATE TABLE config.enum_mappings;

INSERT INTO config.enum_mappings (category, code, display_name, score, sort_order) VALUES
-- 严重程度
('severity', 'critical', '特别严重', 0.9, 1),
('severity', 'high', '严重', 0.7, 2),
('severity', 'medium', '中等', 0.5, 3),
('severity', 'low', '轻微', 0.3, 4),
-- 优先级
('priority', 'critical', '紧急', NULL, 1),
('priority', 'high', '高优先', NULL, 2),
('priority', 'medium', '中优先', NULL, 3),
('priority', 'low', '低优先', NULL, 4);

-- ============================================================================
-- 验证
-- ============================================================================

SELECT 'hard_rules' AS table_name, COUNT(*) AS row_count FROM config.hard_rules
UNION ALL
SELECT 'evaluation_weights', COUNT(*) FROM config.evaluation_weights
UNION ALL
SELECT 'enum_mappings', COUNT(*) FROM config.enum_mappings;
