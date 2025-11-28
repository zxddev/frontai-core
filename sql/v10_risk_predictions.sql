-- 风险预测记录表
-- RealTimeRiskAgent 预测结果持久化

CREATE TABLE IF NOT EXISTS operational_v2.risk_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID REFERENCES operational_v2.scenarios_v2(id) ON DELETE CASCADE,
    
    -- 预测类型
    prediction_type VARCHAR(50) NOT NULL,  -- path_risk/operation_risk/disaster_spread
    
    -- 预测目标
    target_type VARCHAR(50) NOT NULL,      -- team/vehicle/area
    target_id UUID,
    target_name VARCHAR(255),
    
    -- 预测输入
    input_data JSONB NOT NULL,
    
    -- 预测结果
    risk_level VARCHAR(20) NOT NULL,       -- red/orange/yellow/blue
    risk_score DECIMAL(5,2),               -- 0-100
    confidence_score DECIMAL(3,2),         -- 0-1
    
    -- 预测时间范围
    prediction_horizon_hours INT,          -- 1/6/24
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    
    -- 风险详情
    risk_factors JSONB,                    -- 风险因素列表
    recommendations JSONB,                 -- 建议列表
    explanation TEXT,                      -- LLM生成的解释
    
    -- 人工审核
    requires_human_review BOOLEAN DEFAULT FALSE,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_decision VARCHAR(20),           -- approved/rejected/modified
    review_notes TEXT,
    
    -- 追踪
    trace JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_risk_predictions_scenario 
    ON operational_v2.risk_predictions(scenario_id);
CREATE INDEX IF NOT EXISTS idx_risk_predictions_target 
    ON operational_v2.risk_predictions(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_risk_predictions_level 
    ON operational_v2.risk_predictions(risk_level);
CREATE INDEX IF NOT EXISTS idx_risk_predictions_type 
    ON operational_v2.risk_predictions(prediction_type);
CREATE INDEX IF NOT EXISTS idx_risk_predictions_review 
    ON operational_v2.risk_predictions(requires_human_review) 
    WHERE requires_human_review = TRUE;
CREATE INDEX IF NOT EXISTS idx_risk_predictions_created 
    ON operational_v2.risk_predictions(created_at DESC);

-- 触发器: 自动更新 updated_at
CREATE OR REPLACE FUNCTION operational_v2.update_risk_predictions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_risk_predictions_updated_at ON operational_v2.risk_predictions;
CREATE TRIGGER trg_risk_predictions_updated_at
    BEFORE UPDATE ON operational_v2.risk_predictions
    FOR EACH ROW
    EXECUTE FUNCTION operational_v2.update_risk_predictions_updated_at();

COMMENT ON TABLE operational_v2.risk_predictions IS '风险预测记录表 - RealTimeRiskAgent预测结果';
COMMENT ON COLUMN operational_v2.risk_predictions.prediction_type IS '预测类型: path_risk(路径风险), operation_risk(作业风险), disaster_spread(灾害扩散)';
COMMENT ON COLUMN operational_v2.risk_predictions.risk_level IS '风险等级: red(红色), orange(橙色), yellow(黄色), blue(蓝色)';
COMMENT ON COLUMN operational_v2.risk_predictions.confidence_score IS '置信度: 0-1之间';
COMMENT ON COLUMN operational_v2.risk_predictions.requires_human_review IS '是否需要人工审核(红色风险默认需要)';
