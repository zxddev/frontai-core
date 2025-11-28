-- ============================================================================
-- V12 事件表迁移修复脚本 (v12_events_migration_fix.sql)
-- 
-- 目的: 修复 operational_v2.events_v2 表结构，使用 PostgreSQL ENUM 强约束
-- 说明: 使用 operational_v2 schema 下已存在的 ENUM 类型
-- 
-- ENUM类型要求:
--   - event_type_v2
--   - event_source_type_v2  
--   - event_status_v2
--   - event_priority_v2
-- 
-- 执行前请备份数据！
-- ============================================================================

-- 设置搜索路径
SET search_path TO operational_v2, public;

-- ============================================================================
-- 第一步：确保ENUM类型存在（如果不存在则创建）
-- ============================================================================

-- 事件类型
DO $$ BEGIN
    CREATE TYPE operational_v2.event_type_v2 AS ENUM (
        'trapped_person', 'fire', 'flood', 'landslide', 
        'building_collapse', 'road_damage', 'power_outage', 
        'communication_lost', 'hazmat_leak', 'epidemic', 
        'earthquake_secondary', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 事件来源
DO $$ BEGIN
    CREATE TYPE operational_v2.event_source_type_v2 AS ENUM (
        'manual_report', 'ai_detection', 'sensor_alert', 
        'system_inference', 'external_system'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 事件状态
DO $$ BEGIN
    CREATE TYPE operational_v2.event_status_v2 AS ENUM (
        'pending', 'pre_confirmed', 'confirmed', 'planning', 
        'executing', 'resolved', 'escalated', 'cancelled'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 事件优先级
DO $$ BEGIN
    CREATE TYPE operational_v2.event_priority_v2 AS ENUM (
        'critical', 'high', 'medium', 'low'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 第二步：清理现有表（如果需要重建）
-- ============================================================================

-- 删除视图（如果存在）
DROP VIEW IF EXISTS operational_v2.events_full_v2 CASCADE;

-- 删除现有表（级联删除依赖对象）
DROP TABLE IF EXISTS operational_v2.event_updates_v2 CASCADE;
DROP TABLE IF EXISTS operational_v2.events_v2 CASCADE;

-- ============================================================================
-- 第三步：创建事件表 events_v2（使用ENUM类型）
-- ============================================================================
CREATE TABLE operational_v2.events_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定
    scenario_id UUID NOT NULL,
    
    -- 事件编号 (场景内唯一，用于显示)
    event_code VARCHAR(50) NOT NULL,
    
    -- 事件类型（使用ENUM强约束）
    event_type operational_v2.event_type_v2 NOT NULL,
    
    -- 事件来源（使用ENUM强约束）
    source_type operational_v2.event_source_type_v2 NOT NULL DEFAULT 'manual_report',
    
    -- 来源详情 (报警人信息/传感器ID/AI模型等)
    source_detail JSONB DEFAULT '{}',
    
    -- 事件名称/标题
    title VARCHAR(500) NOT NULL,
    
    -- 事件描述
    description TEXT,
    
    -- 事件位置 (精确点位)
    location GEOMETRY(Point, 4326) NOT NULL,
    
    -- 影响范围 (面状区域)
    affected_area GEOMETRY(Polygon, 4326),
    
    -- 地址描述
    address TEXT,
    
    -- 事件状态（使用ENUM强约束）
    status operational_v2.event_status_v2 NOT NULL DEFAULT 'pending',
    
    -- 优先级（使用ENUM强约束）
    priority operational_v2.event_priority_v2 NOT NULL DEFAULT 'medium',
    
    -- 预估受困人数
    estimated_victims INTEGER DEFAULT 0,
    
    -- 已救出人数
    rescued_count INTEGER DEFAULT 0,
    
    -- 伤亡人数
    casualty_count INTEGER DEFAULT 0,
    
    -- 是否有黄金救援时间限制
    is_time_critical BOOLEAN DEFAULT false,
    
    -- 黄金时间截止 (如有)
    golden_hour_deadline TIMESTAMPTZ,
    
    -- 父事件ID (次生灾害关联)
    parent_event_id UUID,
    
    -- 合并到的事件ID (重复上报合并)
    merged_into_event_id UUID,
    
    -- 关联的地图实体ID
    entity_id UUID,
    
    -- 现场照片/视频
    media_attachments JSONB DEFAULT '[]',
    
    -- 上报人/确认人/关闭人
    reported_by UUID,
    confirmed_by UUID,
    resolved_by UUID,
    
    -- 自动确认标记 (AI评分≥0.85或满足AC规则)
    auto_confirmed BOOLEAN DEFAULT false,
    
    -- 预确认相关字段 (status='pre_confirmed'时使用)
    pre_confirm_expires_at TIMESTAMPTZ,           -- 30分钟倒计时截止时间
    pre_allocated_resources JSONB DEFAULT '[]',   -- 预锁定资源列表
    pre_generated_scheme_id UUID,                 -- 预生成的草案方案ID
    
    -- AI确认评分
    confirmation_score DECIMAL(5,4),              -- 确认评分(0~1)
    matched_auto_confirm_rules VARCHAR(20)[],     -- 匹配的自动确认规则
    
    -- 时间戳
    reported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    pre_confirmed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 自引用外键约束
    CONSTRAINT fk_events_v2_parent FOREIGN KEY (parent_event_id) 
        REFERENCES operational_v2.events_v2(id) ON DELETE SET NULL,
    CONSTRAINT fk_events_v2_merged FOREIGN KEY (merged_into_event_id) 
        REFERENCES operational_v2.events_v2(id) ON DELETE SET NULL,
    
    -- 唯一约束
    CONSTRAINT uq_events_v2_scenario_code UNIQUE(scenario_id, event_code)
);

-- 创建索引
CREATE INDEX idx_events_v2_scenario ON operational_v2.events_v2(scenario_id);
CREATE INDEX idx_events_v2_status ON operational_v2.events_v2(status);
CREATE INDEX idx_events_v2_priority ON operational_v2.events_v2(priority);
CREATE INDEX idx_events_v2_type ON operational_v2.events_v2(event_type);
CREATE INDEX idx_events_v2_location ON operational_v2.events_v2 USING GIST(location);
CREATE INDEX idx_events_v2_affected_area ON operational_v2.events_v2 USING GIST(affected_area) 
    WHERE affected_area IS NOT NULL;
CREATE INDEX idx_events_v2_parent ON operational_v2.events_v2(parent_event_id) 
    WHERE parent_event_id IS NOT NULL;
CREATE INDEX idx_events_v2_time_critical ON operational_v2.events_v2(golden_hour_deadline) 
    WHERE is_time_critical = true;
CREATE INDEX idx_events_v2_pre_confirm_expires ON operational_v2.events_v2(pre_confirm_expires_at) 
    WHERE status = 'pre_confirmed';
CREATE INDEX idx_events_v2_reported_at ON operational_v2.events_v2(reported_at);

-- ============================================================================
-- 第四步：创建事件更新记录表 event_updates_v2
-- ============================================================================
CREATE TABLE operational_v2.event_updates_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    event_id UUID NOT NULL,
    
    -- 更新类型
    update_type VARCHAR(50) NOT NULL,
    
    -- 更新前状态/值
    previous_value JSONB,
    
    -- 更新后状态/值
    new_value JSONB,
    
    -- 更新说明
    description TEXT,
    
    -- 更新来源（使用ENUM强约束）
    source_type operational_v2.event_source_type_v2 NOT NULL DEFAULT 'manual_report',
    
    -- 更新人
    updated_by UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 外键约束
    CONSTRAINT fk_event_updates_v2_event FOREIGN KEY (event_id) 
        REFERENCES operational_v2.events_v2(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_event_updates_v2_event ON operational_v2.event_updates_v2(event_id);
CREATE INDEX idx_event_updates_v2_time ON operational_v2.event_updates_v2(created_at);
CREATE INDEX idx_event_updates_v2_type ON operational_v2.event_updates_v2(update_type);

-- ============================================================================
-- 第五步：创建触发器 - 自动更新时间戳
-- ============================================================================

-- 创建或替换更新时间戳函数
CREATE OR REPLACE FUNCTION operational_v2.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为events_v2创建触发器
DROP TRIGGER IF EXISTS tr_events_v2_updated ON operational_v2.events_v2;
CREATE TRIGGER tr_events_v2_updated
    BEFORE UPDATE ON operational_v2.events_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- ============================================================================
-- 第六步：创建视图 - 事件完整信息
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.events_full_v2 AS
SELECT 
    e.*,
    ST_AsGeoJSON(e.location)::JSONB as location_geojson,
    ST_AsGeoJSON(e.affected_area)::JSONB as affected_area_geojson,
    pe.title as parent_event_title,
    pe.event_code as parent_event_code
FROM operational_v2.events_v2 e
LEFT JOIN operational_v2.events_v2 pe ON pe.id = e.parent_event_id;

-- ============================================================================
-- 第七步：创建辅助函数 - 生成事件编号
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.generate_event_code(p_scenario_id UUID)
RETURNS VARCHAR(50) AS $$
DECLARE
    v_count INTEGER;
    v_code VARCHAR(50);
BEGIN
    SELECT COUNT(*) + 1 INTO v_count 
    FROM operational_v2.events_v2 
    WHERE scenario_id = p_scenario_id;
    
    v_code := 'EVT-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' || LPAD(v_count::TEXT, 4, '0');
    RETURN v_code;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 第八步：添加表注释
-- ============================================================================
COMMENT ON TABLE operational_v2.events_v2 IS '事件表 - 灾情事件管理，支持父子事件、事件合并';
COMMENT ON TABLE operational_v2.event_updates_v2 IS '事件动态更新记录 - 追踪事件状态变化';

COMMENT ON COLUMN operational_v2.events_v2.event_type IS '事件类型: trapped_person/fire/flood/landslide/building_collapse/road_damage/power_outage/communication_lost/hazmat_leak/epidemic/earthquake_secondary/other';
COMMENT ON COLUMN operational_v2.events_v2.source_type IS '来源类型: manual_report/ai_detection/sensor_alert/system_inference/external_system';
COMMENT ON COLUMN operational_v2.events_v2.status IS '状态: pending/pre_confirmed/confirmed/planning/executing/resolved/escalated/cancelled';
COMMENT ON COLUMN operational_v2.events_v2.priority IS '优先级: critical/high/medium/low';
COMMENT ON COLUMN operational_v2.events_v2.confirmation_score IS 'AI确认评分 [0,1]，≥0.85自动确认';
COMMENT ON COLUMN operational_v2.events_v2.pre_confirm_expires_at IS '预确认过期时间（30分钟倒计时）';

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'Migration completed successfully!' AS result;
