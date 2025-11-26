-- ============================================================================
-- AI决策日志表 (v2_ai_decision_logs.sql)
-- 记录所有AI决策过程，支持可追溯可解释
-- ============================================================================

-- 在operational_v2模式下创建表
CREATE TABLE IF NOT EXISTS operational_v2.ai_decision_logs_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID NOT NULL,
    
    -- 关联事件 (如有)
    event_id UUID REFERENCES operational_v2.events_v2(id),
    
    -- 关联方案 (如有)
    scheme_id UUID REFERENCES operational_v2.schemes_v2(id),
    
    -- 决策类型
    decision_type VARCHAR(100) NOT NULL,
    
    -- 使用的算法
    algorithm_used VARCHAR(200),
    
    -- 输入数据快照
    input_snapshot JSONB NOT NULL,
    
    -- 输出结果
    output_result JSONB NOT NULL,
    
    -- 置信度 (0-1)
    confidence_score DECIMAL(5,4),
    
    -- 推理链条 (可解释性)
    reasoning_chain JSONB,
    
    -- 耗时(毫秒)
    processing_time_ms INTEGER,
    
    -- 是否被采纳
    is_accepted BOOLEAN,
    
    -- 人工反馈
    human_feedback TEXT,
    
    -- 反馈评分 (-1=差, 0=中, 1=好)
    feedback_rating INTEGER,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_v2_scenario ON operational_v2.ai_decision_logs_v2(scenario_id);
CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_v2_event ON operational_v2.ai_decision_logs_v2(event_id) WHERE event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_v2_type ON operational_v2.ai_decision_logs_v2(decision_type);
CREATE INDEX IF NOT EXISTS idx_ai_decision_logs_v2_time ON operational_v2.ai_decision_logs_v2(created_at);

COMMENT ON TABLE operational_v2.ai_decision_logs_v2 IS 'AI决策日志 - 记录所有AI决策过程，可追溯可解释';
