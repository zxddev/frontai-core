-- ============================================================================
-- 救援点管理表 rescue_points_v2
-- 记录灾情现场的救援目标点位
-- ============================================================================

-- 救援点类型枚举
CREATE TYPE rescue_point_type_v2 AS ENUM (
    'trapped_person',      -- 被困人员
    'collapsed_building',  -- 倒塌建筑
    'fire',               -- 火灾点
    'flood_area',         -- 洪涝区域
    'hazmat_leak',        -- 危化品泄漏
    'landslide',          -- 滑坡/泥石流
    'vehicle_accident',   -- 车辆事故
    'medical_emergency',  -- 医疗急救
    'other'               -- 其他
);

-- 救援点状态枚举
CREATE TYPE rescue_point_status_v2 AS ENUM (
    'pending',       -- 待处理
    'in_progress',   -- 救援中
    'completed',     -- 已完成
    'cancelled'      -- 已取消
);

-- 救援点优先级枚举
CREATE TYPE rescue_point_priority_v2 AS ENUM (
    'low',       -- 低
    'medium',    -- 中
    'high',      -- 高
    'critical'   -- 危急
);

-- 检测来源枚举
CREATE TYPE detection_source_v2 AS ENUM (
    'manual',      -- 人工上报
    'uav_image',   -- 无人机图像识别
    'sensor',      -- 传感器检测
    'ai_analysis'  -- AI综合分析
);

-- ============================================================================
-- 救援点主表
-- ============================================================================
CREATE TABLE IF NOT EXISTS rescue_points_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联（救援点属于某个想定下的某个事件）
    scenario_id UUID NOT NULL,
    event_id UUID NOT NULL,
    
    -- 基本信息
    name VARCHAR(200) NOT NULL,
    point_type rescue_point_type_v2 NOT NULL,
    priority rescue_point_priority_v2 NOT NULL DEFAULT 'medium',
    description TEXT,
    
    -- 位置信息
    location GEOMETRY(Point, 4326) NOT NULL,
    address VARCHAR(500),
    
    -- 被困人员统计
    estimated_victims INT NOT NULL DEFAULT 0,
    rescued_count INT NOT NULL DEFAULT 0,
    
    -- 状态
    status rescue_point_status_v2 NOT NULL DEFAULT 'pending',
    
    -- AI检测相关（如果是AI检测创建的）
    detection_id UUID,
    detection_confidence DECIMAL(3,2),
    detection_source detection_source_v2 NOT NULL DEFAULT 'manual',
    source_image_url TEXT,
    
    -- 上报者
    reported_by UUID,
    
    -- 备注
    notes TEXT,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_rescue_points_v2_scenario ON rescue_points_v2(scenario_id);
CREATE INDEX idx_rescue_points_v2_event ON rescue_points_v2(event_id);
CREATE INDEX idx_rescue_points_v2_status ON rescue_points_v2(status);
CREATE INDEX idx_rescue_points_v2_priority ON rescue_points_v2(priority);
CREATE INDEX idx_rescue_points_v2_location ON rescue_points_v2 USING GIST(location);
CREATE INDEX idx_rescue_points_v2_detection ON rescue_points_v2(detection_id) WHERE detection_id IS NOT NULL;

-- ============================================================================
-- 救援点队伍指派表（多对多）
-- ============================================================================
CREATE TABLE IF NOT EXISTS rescue_point_team_assignments_v2 (
    rescue_point_id UUID NOT NULL REFERENCES rescue_points_v2(id) ON DELETE CASCADE,
    team_id UUID NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_by UUID,
    notes TEXT,
    PRIMARY KEY (rescue_point_id, team_id)
);

CREATE INDEX idx_rescue_point_assignments_team ON rescue_point_team_assignments_v2(team_id);

-- ============================================================================
-- 救援点进度记录表（追踪救援过程）
-- ============================================================================
CREATE TABLE IF NOT EXISTS rescue_point_progress_v2 (
    id BIGSERIAL PRIMARY KEY,
    rescue_point_id UUID NOT NULL REFERENCES rescue_points_v2(id) ON DELETE CASCADE,
    
    -- 进度记录
    progress_type VARCHAR(50) NOT NULL,  -- status_change/victim_rescued/team_arrived/resource_request
    previous_value JSONB,
    new_value JSONB,
    
    -- 操作者
    recorded_by UUID,
    
    -- 时间戳
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rescue_point_progress_point ON rescue_point_progress_v2(rescue_point_id);
CREATE INDEX idx_rescue_point_progress_time ON rescue_point_progress_v2(recorded_at);

-- ============================================================================
-- 视图：救援点统计（按事件）
-- ============================================================================
CREATE OR REPLACE VIEW rescue_points_stats_v2 AS
SELECT 
    event_id,
    COUNT(*) as total_points,
    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress_count,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled_count,
    SUM(estimated_victims) as total_estimated_victims,
    SUM(rescued_count) as total_rescued,
    CASE 
        WHEN SUM(estimated_victims) > 0 
        THEN ROUND(SUM(rescued_count)::DECIMAL / SUM(estimated_victims) * 100, 2)
        ELSE 0 
    END as rescue_progress_percent
FROM rescue_points_v2
GROUP BY event_id;

-- ============================================================================
-- 触发器：自动更新updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_rescue_point_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_rescue_points_v2_updated ON rescue_points_v2;
CREATE TRIGGER tr_rescue_points_v2_updated
    BEFORE UPDATE ON rescue_points_v2
    FOR EACH ROW EXECUTE FUNCTION update_rescue_point_timestamp();

-- ============================================================================
-- 触发器：记录状态变更到进度表
-- ============================================================================
CREATE OR REPLACE FUNCTION log_rescue_point_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO rescue_point_progress_v2 (rescue_point_id, progress_type, previous_value, new_value)
        VALUES (NEW.id, 'status_change', 
                jsonb_build_object('status', OLD.status::TEXT),
                jsonb_build_object('status', NEW.status::TEXT));
    END IF;
    
    IF OLD.rescued_count IS DISTINCT FROM NEW.rescued_count THEN
        INSERT INTO rescue_point_progress_v2 (rescue_point_id, progress_type, previous_value, new_value)
        VALUES (NEW.id, 'victim_rescued',
                jsonb_build_object('rescued_count', OLD.rescued_count),
                jsonb_build_object('rescued_count', NEW.rescued_count, 'increment', NEW.rescued_count - OLD.rescued_count));
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_rescue_points_v2_progress ON rescue_points_v2;
CREATE TRIGGER tr_rescue_points_v2_progress
    AFTER UPDATE ON rescue_points_v2
    FOR EACH ROW EXECUTE FUNCTION log_rescue_point_status_change();

-- 表注释
COMMENT ON TABLE rescue_points_v2 IS '救援点表 - 记录灾情现场需要救援的目标点位';
COMMENT ON TABLE rescue_point_team_assignments_v2 IS '救援点队伍指派表 - 记录哪些队伍被指派到哪些救援点';
COMMENT ON TABLE rescue_point_progress_v2 IS '救援点进度记录表 - 追踪救援点状态和进度变更';
