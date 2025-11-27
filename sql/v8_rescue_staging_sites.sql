-- ============================================================================
-- 救援队驻扎点数据表 v8
-- 用于存储救援队前沿驻扎点候选位置及其属性
-- ============================================================================

-- 驻扎点类型枚举
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'staging_site_type_v2') THEN
        CREATE TYPE operational_v2.staging_site_type_v2 AS ENUM (
            'open_ground',       -- 空旷地带
            'parking_lot',       -- 停车场
            'sports_field',      -- 运动场
            'school_yard',       -- 学校操场
            'factory_yard',      -- 工厂空地
            'plaza',             -- 广场
            'helipad',           -- 直升机场
            'logistics_center',  -- 物流中心
            'other'              -- 其他
        );
    END IF;
END $$;

-- 地面稳定性枚举
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ground_stability_v2') THEN
        CREATE TYPE operational_v2.ground_stability_v2 AS ENUM (
            'excellent',   -- 优良（硬化地面/基岩）
            'good',        -- 良好（压实土壤）
            'moderate',    -- 中等（普通土壤）
            'poor',        -- 较差（松软/易滑）
            'unknown'      -- 未知
        );
    END IF;
END $$;

-- 通信类型枚举 - 已在v2_environment_model.sql中定义，这里跳过

-- ============================================================================
-- 救援队驻扎点表 rescue_staging_sites_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.rescue_staging_sites_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 所属想定 (NULL表示常备驻扎点)
    scenario_id UUID,
    
    -- 基本信息
    site_code VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    site_type operational_v2.staging_site_type_v2 NOT NULL DEFAULT 'open_ground',
    
    -- 位置
    location GEOMETRY(POINT, 4326) NOT NULL,
    boundary GEOMETRY(POLYGON, 4326),
    address TEXT,
    
    -- 面积 (平方米)
    area_m2 DECIMAL(12,2),
    
    -- 地形条件
    elevation_m DECIMAL(8,2),           -- 海拔高度
    slope_degree DECIMAL(5,2),          -- 坡度（度）
    terrain_type VARCHAR(50),           -- 地形类型: flat/hilly/mountainous
    ground_stability operational_v2.ground_stability_v2 DEFAULT 'unknown',
    
    -- 承载能力
    max_vehicles INT,                   -- 最大可容纳车辆数
    max_personnel INT,                  -- 最大可容纳人数
    max_weight_kg DECIMAL(12,2),        -- 最大承重（kg）
    
    -- 设施条件
    has_water_supply BOOLEAN DEFAULT false,
    water_supply_capacity_l DECIMAL(10,2),   -- 日供水能力（升）
    has_power_supply BOOLEAN DEFAULT false,
    power_capacity_kw DECIMAL(8,2),          -- 供电能力（千瓦）
    has_sanitation BOOLEAN DEFAULT false,
    has_shelter_structure BOOLEAN DEFAULT false,  -- 是否有遮蔽结构
    
    -- 直升机起降
    can_helicopter_land BOOLEAN DEFAULT false,
    helipad_diameter_m DECIMAL(6,2),         -- 起降场直径（米）
    
    -- 通信条件
    primary_network_type VARCHAR(20) DEFAULT 'none',  -- 5g/4g_lte/3g/satellite/shortwave/mesh/none
    signal_quality VARCHAR(20),              -- excellent/good/fair/poor
    has_backup_comm BOOLEAN DEFAULT false,
    
    -- 道路可达性
    nearest_road_distance_m DECIMAL(10,2),   -- 到最近道路距离
    road_access_width_m DECIMAL(6,2),        -- 入口道路宽度
    can_heavy_vehicle_access BOOLEAN DEFAULT true,  -- 重型车辆可达
    
    -- 预计算距离（定期更新或触发计算）
    nearest_supply_depot_m DECIMAL(10,2),
    nearest_medical_point_m DECIMAL(10,2),
    nearest_command_post_m DECIMAL(10,2),
    
    -- 安全评估（动态更新）
    safety_score DECIMAL(5,2),               -- 0-100安全评分
    last_safety_assessment_at TIMESTAMPTZ,
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',  -- available/occupied/damaged/reserved
    occupied_by_team_id UUID,                -- 当前占用的队伍ID
    
    -- 管理信息
    managing_organization VARCHAR(200),
    contact_person VARCHAR(100),
    contact_phone VARCHAR(50),
    
    -- 备注
    notes TEXT,
    
    -- 扩展属性
    properties JSONB DEFAULT '{}',
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 索引
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_scenario 
    ON operational_v2.rescue_staging_sites_v2(scenario_id);
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_location 
    ON operational_v2.rescue_staging_sites_v2 USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_boundary 
    ON operational_v2.rescue_staging_sites_v2 USING GIST(boundary);
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_type 
    ON operational_v2.rescue_staging_sites_v2(site_type);
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_status 
    ON operational_v2.rescue_staging_sites_v2(status);
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_slope 
    ON operational_v2.rescue_staging_sites_v2(slope_degree) 
    WHERE status = 'available';
CREATE INDEX IF NOT EXISTS idx_staging_sites_v2_helicopter 
    ON operational_v2.rescue_staging_sites_v2(can_helicopter_land) 
    WHERE can_helicopter_land = true;

-- ============================================================================
-- 更新时间触发器
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.update_staging_site_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_staging_sites_v2_updated 
    ON operational_v2.rescue_staging_sites_v2;
CREATE TRIGGER tr_staging_sites_v2_updated
    BEFORE UPDATE ON operational_v2.rescue_staging_sites_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_staging_site_timestamp();

-- ============================================================================
-- 查询函数：搜索安全驻扎点候选
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.search_staging_candidates(
    p_scenario_id UUID,
    p_center_lon DOUBLE PRECISION,
    p_center_lat DOUBLE PRECISION,
    p_max_distance_m DOUBLE PRECISION DEFAULT 50000,
    p_min_buffer_from_danger_m DOUBLE PRECISION DEFAULT 500,
    p_max_slope_deg DOUBLE PRECISION DEFAULT 15,
    p_require_water BOOLEAN DEFAULT false,
    p_require_power BOOLEAN DEFAULT false,
    p_require_helicopter BOOLEAN DEFAULT false,
    p_max_results INT DEFAULT 50
)
RETURNS TABLE (
    site_id UUID,
    site_code VARCHAR,
    site_name VARCHAR,
    site_type operational_v2.staging_site_type_v2,
    longitude DOUBLE PRECISION,
    latitude DOUBLE PRECISION,
    area_m2 DECIMAL,
    slope_degree DECIMAL,
    has_water_supply BOOLEAN,
    has_power_supply BOOLEAN,
    can_helicopter_land BOOLEAN,
    primary_network_type VARCHAR,
    distance_from_center_m DOUBLE PRECISION,
    min_distance_to_danger_m DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    WITH danger_zones AS (
        SELECT ST_Union(geometry::geometry) AS geom
        FROM operational_v2.disaster_affected_areas_v2
        WHERE scenario_id = p_scenario_id
          AND area_type IN ('danger_zone', 'blocked', 'flooded', 'collapsed')
    )
    SELECT 
        s.id AS site_id,
        s.site_code,
        s.name AS site_name,
        s.site_type,
        ST_X(s.location::geometry) AS longitude,
        ST_Y(s.location::geometry) AS latitude,
        s.area_m2,
        s.slope_degree,
        s.has_water_supply,
        s.has_power_supply,
        s.can_helicopter_land,
        s.primary_network_type,
        ST_Distance(
            s.location::geography,
            ST_SetSRID(ST_MakePoint(p_center_lon, p_center_lat), 4326)::geography
        ) AS distance_from_center_m,
        COALESCE(
            ST_Distance(s.location::geography, dz.geom::geography),
            999999
        ) AS min_distance_to_danger_m
    FROM operational_v2.rescue_staging_sites_v2 s
    LEFT JOIN danger_zones dz ON true
    WHERE s.status = 'available'
      AND (s.scenario_id = p_scenario_id OR s.scenario_id IS NULL)
      AND ST_DWithin(
          s.location::geography,
          ST_SetSRID(ST_MakePoint(p_center_lon, p_center_lat), 4326)::geography,
          p_max_distance_m
      )
      AND (dz.geom IS NULL OR NOT ST_Intersects(s.location::geometry, dz.geom))
      AND (dz.geom IS NULL OR ST_Distance(s.location::geography, dz.geom::geography) >= p_min_buffer_from_danger_m)
      AND COALESCE(s.slope_degree, 0) <= p_max_slope_deg
      AND (NOT p_require_water OR s.has_water_supply = true)
      AND (NOT p_require_power OR s.has_power_supply = true)
      AND (NOT p_require_helicopter OR s.can_helicopter_land = true)
    ORDER BY min_distance_to_danger_m DESC, distance_from_center_m ASC
    LIMIT p_max_results;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 注释
-- ============================================================================
COMMENT ON TABLE operational_v2.rescue_staging_sites_v2 IS 
    '救援队驻扎点表 - 存储前沿驻扎点候选位置及其属性，用于驻扎点选址算法';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.site_code IS '驻扎点编号';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.site_type IS '驻扎点类型';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.location IS '驻扎点中心点坐标';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.slope_degree IS '地面坡度（度），用于筛选平坦场地';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.ground_stability IS '地面稳定性评级';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.can_helicopter_land IS '是否可供直升机起降';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.primary_network_type IS '主要通信网络类型';
COMMENT ON COLUMN operational_v2.rescue_staging_sites_v2.safety_score IS '安全评分（0-100），由算法动态计算';
COMMENT ON FUNCTION operational_v2.search_staging_candidates IS 
    '搜索安全驻扎点候选函数 - 排除危险区域内的点位，按安全距离和中心距离排序';
