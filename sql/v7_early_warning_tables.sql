-- 预警监测智能体数据表
-- v7_early_warning_tables.sql

-- 灾害态势表
CREATE TABLE IF NOT EXISTS operational_v2.disaster_situations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scenario_id UUID REFERENCES operational_v2.scenarios(id) ON DELETE CASCADE,
    disaster_type VARCHAR(50) NOT NULL,           -- fire/flood/chemical/landslide/earthquake
    disaster_name VARCHAR(200),                   -- 灾害名称
    boundary GEOMETRY(POLYGON, 4326),             -- 灾害范围多边形 (GeoJSON)
    center_point GEOMETRY(POINT, 4326),           -- 中心点
    buffer_distance_m INT DEFAULT 3000,           -- 预警缓冲距离（米）
    spread_direction VARCHAR(20),                 -- 扩散方向 N/NE/E/SE/S/SW/W/NW
    spread_speed_mps DECIMAL(10,2),               -- 扩散速度 m/s
    severity_level INT DEFAULT 3 CHECK (severity_level BETWEEN 1 AND 5),  -- 严重程度 1-5
    status VARCHAR(20) DEFAULT 'active',          -- active/contained/resolved
    source VARCHAR(100),                          -- 数据来源
    source_update_time TIMESTAMP,                 -- 数据源更新时间
    properties JSONB DEFAULT '{}',                -- 扩展属性
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 灾害态势空间索引
CREATE INDEX IF NOT EXISTS idx_disaster_situations_boundary 
    ON operational_v2.disaster_situations USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_disaster_situations_scenario 
    ON operational_v2.disaster_situations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_disaster_situations_status 
    ON operational_v2.disaster_situations(status);

-- 预警记录表
CREATE TABLE IF NOT EXISTS operational_v2.warning_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    disaster_id UUID REFERENCES operational_v2.disaster_situations(id) ON DELETE CASCADE,
    scenario_id UUID REFERENCES operational_v2.scenarios(id) ON DELETE CASCADE,
    
    -- 受影响对象
    affected_type VARCHAR(20) NOT NULL,           -- vehicle/team
    affected_id UUID NOT NULL,                    -- 车辆/队伍ID
    affected_name VARCHAR(200),                   -- 名称（冗余便于查询）
    affected_location GEOMETRY(POINT, 4326),      -- 当时位置
    
    -- 通知目标
    notify_target_type VARCHAR(20) NOT NULL,      -- commander/team_leader
    notify_target_id UUID,                        -- 通知目标用户ID
    notify_target_name VARCHAR(100),              -- 通知目标名称
    
    -- 预警信息
    warning_level VARCHAR(10) NOT NULL DEFAULT 'yellow',  -- blue/yellow/orange/red
    distance_m DECIMAL(10,2),                     -- 距离危险区域距离（米）
    estimated_contact_minutes INT,                -- 预计接触时间（分钟）
    route_affected BOOLEAN DEFAULT FALSE,         -- 路径是否受影响
    route_intersection_point GEOMETRY(POINT, 4326),  -- 路径穿越点
    
    -- 预警内容
    warning_title VARCHAR(200),                   -- 预警标题
    warning_message TEXT,                         -- 预警消息内容
    
    -- 状态跟踪
    status VARCHAR(20) DEFAULT 'pending',         -- pending/acknowledged/responded/resolved/cancelled
    response_action VARCHAR(20),                  -- continue/detour/standby
    response_reason TEXT,                         -- 响应理由
    selected_route_id VARCHAR(100),               -- 选择的绕行路线ID
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    responded_at TIMESTAMP,
    resolved_at TIMESTAMP,
    
    -- 追踪
    properties JSONB DEFAULT '{}'                 -- 扩展属性
);

-- 预警记录索引
CREATE INDEX IF NOT EXISTS idx_warning_records_disaster 
    ON operational_v2.warning_records(disaster_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_scenario 
    ON operational_v2.warning_records(scenario_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_affected 
    ON operational_v2.warning_records(affected_type, affected_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_status 
    ON operational_v2.warning_records(status);
CREATE INDEX IF NOT EXISTS idx_warning_records_notify_target 
    ON operational_v2.warning_records(notify_target_id);
CREATE INDEX IF NOT EXISTS idx_warning_records_created 
    ON operational_v2.warning_records(created_at DESC);

-- 预警级别说明
COMMENT ON COLUMN operational_v2.warning_records.warning_level IS 
    'blue: >5km, yellow: 3-5km, orange: 1-3km, red: <1km';

-- 更新时间触发器
CREATE OR REPLACE FUNCTION operational_v2.update_disaster_situation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_disaster_situation_timestamp 
    ON operational_v2.disaster_situations;
CREATE TRIGGER trigger_update_disaster_situation_timestamp
    BEFORE UPDATE ON operational_v2.disaster_situations
    FOR EACH ROW
    EXECUTE FUNCTION operational_v2.update_disaster_situation_timestamp();
