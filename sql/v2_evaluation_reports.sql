-- ============================================================================
-- 评估报告表 evaluation_reports_v2
-- 存储救援行动评估报告（AI生成或人工编写）
-- ============================================================================

-- 报告生成来源枚举（如果不存在则创建）
DO $$ BEGIN
    CREATE TYPE report_source_v2 AS ENUM (
        'ai_generated',   -- AI生成
        'manual'          -- 人工编写
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- 评估报告主表
-- ============================================================================
CREATE TABLE IF NOT EXISTS evaluation_reports_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联（一个事件只有一份最终报告）
    event_id UUID NOT NULL UNIQUE,
    scenario_id UUID NOT NULL,
    
    -- 报告内容（JSONB存储完整报告）
    report_data JSONB NOT NULL,
    
    -- 报告元信息
    generated_by VARCHAR(50) NOT NULL DEFAULT 'ai_generated',
    generated_at TIMESTAMPTZ NOT NULL,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_evaluation_reports_v2_event ON evaluation_reports_v2(event_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_reports_v2_scenario ON evaluation_reports_v2(scenario_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_reports_v2_generated ON evaluation_reports_v2(generated_at);

-- ============================================================================
-- 触发器：自动更新updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_evaluation_report_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_evaluation_reports_v2_updated ON evaluation_reports_v2;
CREATE TRIGGER tr_evaluation_reports_v2_updated
    BEFORE UPDATE ON evaluation_reports_v2
    FOR EACH ROW EXECUTE FUNCTION update_evaluation_report_timestamp();

-- 表注释
COMMENT ON TABLE evaluation_reports_v2 IS '评估报告表 - 存储救援行动评估报告';
COMMENT ON COLUMN evaluation_reports_v2.report_data IS 'JSONB格式存储完整报告内容，包括summary/timeline/resource_usage/rescue_results/lessons_learned/ai_analysis';
