-- ============================================================================
-- 实体轨迹表 entity_tracks_v2
-- 记录动态实体的历史位置轨迹
-- ============================================================================

CREATE TABLE IF NOT EXISTS entity_tracks_v2 (
    -- 主键：BIGSERIAL提高插入性能（轨迹点数量大）
    id BIGSERIAL PRIMARY KEY,
    
    -- 关联实体（外键约束确保数据完整性）
    entity_id UUID NOT NULL REFERENCES entities_v2(id) ON DELETE CASCADE,
    
    -- 轨迹点位置（PostGIS Point）
    location GEOMETRY(Point, 4326) NOT NULL,
    
    -- 速度（km/h）
    speed_kmh DECIMAL(6,2),
    
    -- 航向角度（0-360度，正北为0）
    heading INTEGER CHECK (heading IS NULL OR (heading >= 0 AND heading < 360)),
    
    -- 高度（米，海拔）
    altitude_m DECIMAL(8,2),
    
    -- 记录时间戳
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 复合索引：查询单个实体的轨迹（entity_id + 时间范围）
CREATE INDEX idx_entity_tracks_v2_entity_time 
    ON entity_tracks_v2(entity_id, recorded_at DESC);

-- 时间索引：用于清理旧数据
CREATE INDEX idx_entity_tracks_v2_recorded 
    ON entity_tracks_v2(recorded_at);

-- 空间索引：范围查询轨迹点
CREATE INDEX idx_entity_tracks_v2_location 
    ON entity_tracks_v2 USING GIST(location);

-- 表注释
COMMENT ON TABLE entity_tracks_v2 IS '实体轨迹表 - 记录动态实体的历史位置轨迹';
COMMENT ON COLUMN entity_tracks_v2.entity_id IS '关联实体ID（entities_v2.id）';
COMMENT ON COLUMN entity_tracks_v2.location IS '轨迹点位置（WGS84坐标系）';
COMMENT ON COLUMN entity_tracks_v2.speed_kmh IS '移动速度（千米/小时）';
COMMENT ON COLUMN entity_tracks_v2.heading IS '航向角度（0-360度，正北为0度）';
COMMENT ON COLUMN entity_tracks_v2.altitude_m IS '海拔高度（米）';
COMMENT ON COLUMN entity_tracks_v2.recorded_at IS '轨迹点记录时间';

-- ============================================================================
-- 轨迹清理函数（保留最近N天数据）
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_entity_tracks_v2(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM entity_tracks_v2 
    WHERE recorded_at < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_entity_tracks_v2 IS '清理过期轨迹数据（默认保留30天）';
