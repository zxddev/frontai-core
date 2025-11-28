-- ============================================================================
-- 仿真推演模块数据库表
-- 版本: v11
-- 创建时间: 2025-11-27
-- 
-- 架构说明:
-- - 仿真使用真实数据表 + 事务快照还原
-- - 仿真启动时创建 SAVEPOINT，结束后 ROLLBACK
-- - 事件注入直接调用真实的 EventService
-- - 只需要保存仿真元数据和评估报告
-- ============================================================================

-- 创建枚举类型
DO $$ BEGIN
    CREATE TYPE simulation_status_v2 AS ENUM ('ready', 'running', 'paused', 'completed', 'stopped');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE simulation_source_type_v2 AS ENUM ('new', 'from_history');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================================
-- 仿真场景表（元数据）
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.simulation_scenarios_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    name VARCHAR(200) NOT NULL,
    description TEXT,
    
    -- 关联想定
    scenario_id UUID NOT NULL REFERENCES public.scenarios_v2(id),
    
    -- 来源信息
    source_type simulation_source_type_v2 NOT NULL DEFAULT 'new',
    source_scenario_id UUID,  -- 历史想定ID（复制来源）
    
    -- 时间控制
    time_scale NUMERIC(5,2) NOT NULL DEFAULT 1.0 CHECK (time_scale >= 0.5 AND time_scale <= 10.0),
    start_simulation_time TIMESTAMPTZ,  -- 仿真起始时间（仿真世界中的时间）
    current_simulation_time TIMESTAMPTZ, -- 当前仿真时间
    
    -- 状态
    status simulation_status_v2 NOT NULL DEFAULT 'ready',
    
    -- 参与人员 [{user_id, role, joined_at}]
    participants JSONB DEFAULT '[]'::jsonb,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,  -- 实际开始时间（真实世界）
    paused_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- 累计暂停时长（秒）
    total_pause_duration_s NUMERIC(10,2) DEFAULT 0,
    
    -- 事务快照名称（用于仿真结束后还原）
    savepoint_name VARCHAR(100)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_simulation_scenarios_scenario_id ON public.simulation_scenarios_v2(scenario_id);
CREATE INDEX IF NOT EXISTS idx_simulation_scenarios_status ON public.simulation_scenarios_v2(status);
CREATE INDEX IF NOT EXISTS idx_simulation_scenarios_created_at ON public.simulation_scenarios_v2(created_at DESC);

COMMENT ON TABLE public.simulation_scenarios_v2 IS '仿真场景元数据表';
COMMENT ON COLUMN public.simulation_scenarios_v2.time_scale IS '时间倍率，1.0=实时，2.0=2倍速';
COMMENT ON COLUMN public.simulation_scenarios_v2.start_simulation_time IS '仿真世界的起始时间';
COMMENT ON COLUMN public.simulation_scenarios_v2.current_simulation_time IS '当前仿真时间（含时间倍率计算）';
COMMENT ON COLUMN public.simulation_scenarios_v2.savepoint_name IS 'PostgreSQL SAVEPOINT名称，用于仿真结束后还原数据';


-- ============================================================================
-- 演练评估表
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.drill_assessments_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联仿真场景（一对一）
    simulation_id UUID NOT NULL UNIQUE REFERENCES public.simulation_scenarios_v2(id) ON DELETE CASCADE,
    
    -- 总分
    overall_score NUMERIC(5,2) NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    
    -- 各项得分
    response_time_score NUMERIC(5,2) CHECK (response_time_score >= 0 AND response_time_score <= 100),
    decision_score NUMERIC(5,2) CHECK (decision_score >= 0 AND decision_score <= 100),
    coordination_score NUMERIC(5,2) CHECK (coordination_score >= 0 AND coordination_score <= 100),
    resource_utilization_score NUMERIC(5,2) CHECK (resource_utilization_score >= 0 AND resource_utilization_score <= 100),
    
    -- 详细评估 {grades, timeline_analysis, recommendations}
    details JSONB DEFAULT '{}'::jsonb,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_drill_assessments_simulation_id ON public.drill_assessments_v2(simulation_id);
CREATE INDEX IF NOT EXISTS idx_drill_assessments_overall_score ON public.drill_assessments_v2(overall_score DESC);

COMMENT ON TABLE public.drill_assessments_v2 IS '演练评估表';
COMMENT ON COLUMN public.drill_assessments_v2.details IS '详细评估JSON，包含各项详细得分、时间线分析和改进建议';


-- ============================================================================
-- 授权
-- ============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON public.simulation_scenarios_v2 TO frontai_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.drill_assessments_v2 TO frontai_app;
