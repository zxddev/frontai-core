-- ============================================================================
-- 路网数据模型 V2
-- 支持A*路径规划、地形分析、灾害影响区域
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 创建新schema
CREATE SCHEMA IF NOT EXISTS operational_v2;

-- ============================================================================
-- 1. 道路类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.road_type_v2 CASCADE;
CREATE TYPE operational_v2.road_type_v2 AS ENUM (
    'motorway',              -- 高速公路
    'motorway_link',         -- 高速匝道
    'trunk',                 -- 国道/主干道
    'trunk_link',            -- 主干道匝道
    'primary',               -- 省道/一级公路
    'primary_link',          -- 省道匝道
    'secondary',             -- 县道/二级公路
    'secondary_link',        -- 县道匝道
    'tertiary',              -- 乡道/三级公路
    'tertiary_link',         -- 乡道匝道
    'residential',           -- 居民区道路
    'living_street',         -- 生活街道
    'service',               -- 服务道路
    'unclassified',          -- 未分类道路
    'track',                 -- 土路/机耕路
    'path',                  -- 小径
    'footway',               -- 人行道
    'cycleway',              -- 自行车道
    'bridleway',             -- 马道
    'steps'                  -- 台阶
);

-- ============================================================================
-- 2. 路面类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.surface_type_v2 CASCADE;
CREATE TYPE operational_v2.surface_type_v2 AS ENUM (
    'paved',                 -- 铺装路面
    'asphalt',               -- 沥青
    'concrete',              -- 混凝土
    'cobblestone',           -- 鹅卵石
    'gravel',                -- 碎石
    'unpaved',               -- 未铺装
    'dirt',                  -- 土路
    'sand',                  -- 沙地
    'grass',                 -- 草地
    'mud',                   -- 泥泞
    'unknown'                -- 未知
);

-- ============================================================================
-- 3. 地形类型枚举
-- ============================================================================
DROP TYPE IF EXISTS operational_v2.terrain_type_v2 CASCADE;
CREATE TYPE operational_v2.terrain_type_v2 AS ENUM (
    'urban',                 -- 城市
    'suburban',              -- 郊区
    'rural',                 -- 乡村
    'mountain',              -- 山地
    'forest',                -- 森林
    'grassland',             -- 草地
    'water_adjacent',        -- 临水
    'desert',                -- 荒漠
    'wetland',               -- 湿地
    'unknown'                -- 未知
);

-- ============================================================================
-- 4. 路网节点表 (road_nodes_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.road_nodes_v2 CASCADE;
CREATE TABLE operational_v2.road_nodes_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    osm_id BIGINT UNIQUE,                          -- OSM节点ID
    
    -- 位置
    location GEOGRAPHY(POINT, 4326) NOT NULL,      -- 节点位置
    lon DOUBLE PRECISION NOT NULL,                 -- 经度
    lat DOUBLE PRECISION NOT NULL,                 -- 纬度
    
    -- 高程信息 (从DEM提取)
    elevation_m DOUBLE PRECISION,                  -- 海拔高度(米)
    
    -- 节点类型
    node_type VARCHAR(50) DEFAULT 'intersection',  -- intersection/endpoint/waypoint
    
    -- 关联信息
    edge_count INT DEFAULT 0,                      -- 连接的边数量
    
    -- 地形信息 (从周边landuse推断)
    terrain_type operational_v2.terrain_type_v2 DEFAULT 'unknown',
    
    -- 状态
    is_accessible BOOLEAN DEFAULT true,            -- 是否可通行
    blocked_reason TEXT,                           -- 封锁原因
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_road_nodes_v2_location ON operational_v2.road_nodes_v2 USING GIST(location);
CREATE INDEX idx_road_nodes_v2_osm ON operational_v2.road_nodes_v2(osm_id);
CREATE INDEX idx_road_nodes_v2_type ON operational_v2.road_nodes_v2(node_type);

COMMENT ON TABLE operational_v2.road_nodes_v2 IS '路网节点表 - 存储道路交叉点、端点';
COMMENT ON COLUMN operational_v2.road_nodes_v2.id IS '节点唯一标识符';
COMMENT ON COLUMN operational_v2.road_nodes_v2.osm_id IS 'OpenStreetMap节点ID';
COMMENT ON COLUMN operational_v2.road_nodes_v2.location IS '节点地理位置';
COMMENT ON COLUMN operational_v2.road_nodes_v2.lon IS '经度';
COMMENT ON COLUMN operational_v2.road_nodes_v2.lat IS '纬度';
COMMENT ON COLUMN operational_v2.road_nodes_v2.elevation_m IS '海拔高度（米），从DEM提取';
COMMENT ON COLUMN operational_v2.road_nodes_v2.node_type IS '节点类型: intersection交叉口/endpoint端点/waypoint路点';
COMMENT ON COLUMN operational_v2.road_nodes_v2.edge_count IS '连接的边数量';
COMMENT ON COLUMN operational_v2.road_nodes_v2.terrain_type IS '地形类型，从周边landuse推断';
COMMENT ON COLUMN operational_v2.road_nodes_v2.is_accessible IS '是否可通行';
COMMENT ON COLUMN operational_v2.road_nodes_v2.blocked_reason IS '封锁原因';
COMMENT ON COLUMN operational_v2.road_nodes_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.road_nodes_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.road_nodes_v2.updated_at IS '更新时间';

-- ============================================================================
-- 5. 路网边表 (road_edges_v2) - 核心表
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.road_edges_v2 CASCADE;
CREATE TABLE operational_v2.road_edges_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    osm_id BIGINT,                                 -- OSM way ID
    
    -- 拓扑关系
    from_node_id UUID REFERENCES operational_v2.road_nodes_v2(id),
    to_node_id UUID REFERENCES operational_v2.road_nodes_v2(id),
    
    -- 几何
    geometry GEOGRAPHY(LINESTRING, 4326) NOT NULL, -- 路段几何
    
    -- 基本属性 (从OSM导入)
    road_type operational_v2.road_type_v2,            -- 道路类型
    name VARCHAR(500),                             -- 道路名称
    name_en VARCHAR(500),                          -- 英文名称
    ref VARCHAR(100),                              -- 道路编号 (如G318)
    
    -- 通行规则
    oneway BOOLEAN DEFAULT false,                  -- 是否单行道
    access VARCHAR(50) DEFAULT 'yes',              -- 通行权限
    max_speed_kmh INT,                             -- 限速(km/h)
    lanes INT,                                     -- 车道数
    
    -- 物理属性
    length_m DOUBLE PRECISION NOT NULL,            -- 长度(米)
    width_m DOUBLE PRECISION,                      -- 宽度(米)
    surface operational_v2.surface_type_v2 DEFAULT 'unknown', -- 路面类型
    
    -- 高程/坡度 (从DEM提取)
    start_elevation_m DOUBLE PRECISION,            -- 起点海拔
    end_elevation_m DOUBLE PRECISION,              -- 终点海拔
    elevation_gain_m DOUBLE PRECISION,             -- 累计爬升
    elevation_loss_m DOUBLE PRECISION,             -- 累计下降
    avg_gradient_percent DOUBLE PRECISION,         -- 平均坡度(%)
    max_gradient_percent DOUBLE PRECISION,         -- 最大坡度(%)
    
    -- 地形信息
    terrain_type operational_v2.terrain_type_v2 DEFAULT 'unknown',
    
    -- 桥梁/隧道
    bridge BOOLEAN DEFAULT false,                  -- 是否桥梁
    tunnel BOOLEAN DEFAULT false,                  -- 是否隧道
    bridge_max_weight_ton DOUBLE PRECISION,        -- 桥梁限重(吨)
    tunnel_height_m DOUBLE PRECISION,              -- 隧道限高(米)
    
    -- A*代价计算
    base_cost DOUBLE PRECISION,                    -- 基础代价 (长度)
    terrain_cost_factor DOUBLE PRECISION DEFAULT 1.0, -- 地形代价系数
    gradient_cost_factor DOUBLE PRECISION DEFAULT 1.0, -- 坡度代价系数
    
    -- 不同车辆类型的速度系数
    speed_factors JSONB DEFAULT '{}',              -- {"all_terrain":0.8,"urban":1.0}
    
    -- 通行性约束
    min_width_required_m DOUBLE PRECISION,         -- 最小通行宽度
    max_weight_allowed_ton DOUBLE PRECISION,       -- 最大允许重量
    min_clearance_required_mm INT,                 -- 最小离地间隙要求
    
    -- 状态
    is_accessible BOOLEAN DEFAULT true,            -- 是否可通行
    blocked_at TIMESTAMPTZ,                        -- 封锁时间
    blocked_reason TEXT,                           -- 封锁原因
    blocked_until TIMESTAMPTZ,                     -- 预计恢复时间
    damage_level VARCHAR(20),                      -- none/light/moderate/severe/destroyed
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_road_edges_v2_geometry ON operational_v2.road_edges_v2 USING GIST(geometry);
CREATE INDEX idx_road_edges_v2_from ON operational_v2.road_edges_v2(from_node_id);
CREATE INDEX idx_road_edges_v2_to ON operational_v2.road_edges_v2(to_node_id);
CREATE INDEX idx_road_edges_v2_osm ON operational_v2.road_edges_v2(osm_id);
CREATE INDEX idx_road_edges_v2_type ON operational_v2.road_edges_v2(road_type);
CREATE INDEX idx_road_edges_v2_accessible ON operational_v2.road_edges_v2(is_accessible);

COMMENT ON TABLE operational_v2.road_edges_v2 IS '路网边表 - 存储道路段，支持A*路径规划';
COMMENT ON COLUMN operational_v2.road_edges_v2.id IS '边唯一标识符';
COMMENT ON COLUMN operational_v2.road_edges_v2.osm_id IS 'OpenStreetMap way ID';
COMMENT ON COLUMN operational_v2.road_edges_v2.from_node_id IS '起始节点ID';
COMMENT ON COLUMN operational_v2.road_edges_v2.to_node_id IS '终止节点ID';
COMMENT ON COLUMN operational_v2.road_edges_v2.geometry IS '路段几何线串';
COMMENT ON COLUMN operational_v2.road_edges_v2.road_type IS '道路类型枚举';
COMMENT ON COLUMN operational_v2.road_edges_v2.name IS '道路名称';
COMMENT ON COLUMN operational_v2.road_edges_v2.name_en IS '道路英文名称';
COMMENT ON COLUMN operational_v2.road_edges_v2.ref IS '道路编号，如G318、S303';
COMMENT ON COLUMN operational_v2.road_edges_v2.oneway IS '是否单行道';
COMMENT ON COLUMN operational_v2.road_edges_v2.access IS '通行权限: yes/no/private/permissive';
COMMENT ON COLUMN operational_v2.road_edges_v2.max_speed_kmh IS '限速（公里/小时）';
COMMENT ON COLUMN operational_v2.road_edges_v2.lanes IS '车道数';
COMMENT ON COLUMN operational_v2.road_edges_v2.length_m IS '路段长度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.width_m IS '路面宽度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.surface IS '路面类型枚举';
COMMENT ON COLUMN operational_v2.road_edges_v2.start_elevation_m IS '起点海拔高度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.end_elevation_m IS '终点海拔高度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.elevation_gain_m IS '累计爬升高度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.elevation_loss_m IS '累计下降高度（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.avg_gradient_percent IS '平均坡度百分比';
COMMENT ON COLUMN operational_v2.road_edges_v2.max_gradient_percent IS '最大坡度百分比';
COMMENT ON COLUMN operational_v2.road_edges_v2.terrain_type IS '地形类型';
COMMENT ON COLUMN operational_v2.road_edges_v2.bridge IS '是否为桥梁';
COMMENT ON COLUMN operational_v2.road_edges_v2.tunnel IS '是否为隧道';
COMMENT ON COLUMN operational_v2.road_edges_v2.bridge_max_weight_ton IS '桥梁限重（吨）';
COMMENT ON COLUMN operational_v2.road_edges_v2.tunnel_height_m IS '隧道限高（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.base_cost IS 'A*基础代价，通常为长度';
COMMENT ON COLUMN operational_v2.road_edges_v2.terrain_cost_factor IS '地形代价系数，1.0为标准';
COMMENT ON COLUMN operational_v2.road_edges_v2.gradient_cost_factor IS '坡度代价系数，坡度越大系数越高';
COMMENT ON COLUMN operational_v2.road_edges_v2.speed_factors IS '不同车辆类型的速度系数JSON';
COMMENT ON COLUMN operational_v2.road_edges_v2.min_width_required_m IS '最小通行宽度要求（米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.max_weight_allowed_ton IS '最大允许通行重量（吨）';
COMMENT ON COLUMN operational_v2.road_edges_v2.min_clearance_required_mm IS '最小离地间隙要求（毫米）';
COMMENT ON COLUMN operational_v2.road_edges_v2.is_accessible IS '当前是否可通行';
COMMENT ON COLUMN operational_v2.road_edges_v2.blocked_at IS '封锁开始时间';
COMMENT ON COLUMN operational_v2.road_edges_v2.blocked_reason IS '封锁原因';
COMMENT ON COLUMN operational_v2.road_edges_v2.blocked_until IS '预计恢复通行时间';
COMMENT ON COLUMN operational_v2.road_edges_v2.damage_level IS '损坏程度: none无/light轻微/moderate中等/severe严重/destroyed毁坏';
COMMENT ON COLUMN operational_v2.road_edges_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.road_edges_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.road_edges_v2.updated_at IS '更新时间';

-- ============================================================================
-- 6. 灾害影响区域表 (disaster_affected_areas_v2)
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.disaster_affected_areas_v2 CASCADE;
CREATE TABLE operational_v2.disaster_affected_areas_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id UUID,                              -- 关联想定
    
    -- 区域信息
    name VARCHAR(200),                             -- 区域名称
    area_type VARCHAR(50) NOT NULL,                -- danger_zone/blocked/damaged/flooded/contaminated
    geometry GEOGRAPHY(POLYGON, 4326) NOT NULL,    -- 影响区域多边形
    
    -- 影响程度
    severity VARCHAR(20) DEFAULT 'medium',         -- low/medium/high/critical
    risk_level INT DEFAULT 5 CHECK (risk_level BETWEEN 1 AND 10), -- 风险等级1-10
    
    -- 通行性影响
    passable BOOLEAN DEFAULT false,                -- 是否可通行
    passable_vehicle_types TEXT[],                 -- 可通行的车辆类型
    speed_reduction_percent INT DEFAULT 100,       -- 速度降低百分比(100表示完全不可通行)
    
    -- 时间窗口
    started_at TIMESTAMPTZ DEFAULT now(),          -- 开始时间
    estimated_end_at TIMESTAMPTZ,                  -- 预计结束时间
    
    -- 描述
    description TEXT,
    
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_disaster_areas_v2_geometry ON operational_v2.disaster_affected_areas_v2 USING GIST(geometry);
CREATE INDEX idx_disaster_areas_v2_scenario ON operational_v2.disaster_affected_areas_v2(scenario_id);
CREATE INDEX idx_disaster_areas_v2_type ON operational_v2.disaster_affected_areas_v2(area_type);

COMMENT ON TABLE operational_v2.disaster_affected_areas_v2 IS '灾害影响区域表 - 定义危险区、封锁区等';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.id IS '区域唯一标识符';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.scenario_id IS '关联的想定ID';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.name IS '区域名称';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.area_type IS '区域类型: danger_zone危险区/blocked封锁区/damaged损坏区/flooded淹没区/contaminated污染区';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.geometry IS '影响区域多边形';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.severity IS '严重程度: low低/medium中/high高/critical紧急';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.risk_level IS '风险等级1-10，10为最高';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.passable IS '是否允许通行';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.passable_vehicle_types IS '允许通行的车辆类型数组';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.speed_reduction_percent IS '速度降低百分比，100表示完全封锁';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.started_at IS '影响开始时间';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.estimated_end_at IS '预计影响结束时间';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.description IS '区域描述';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.properties IS '扩展属性JSON';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.created_at IS '创建时间';
COMMENT ON COLUMN operational_v2.disaster_affected_areas_v2.updated_at IS '更新时间';

-- ============================================================================
-- 7. 道路类型默认参数表
-- ============================================================================
DROP TABLE IF EXISTS operational_v2.road_type_defaults_v2 CASCADE;
CREATE TABLE operational_v2.road_type_defaults_v2 (
    road_type operational_v2.road_type_v2 PRIMARY KEY,
    
    default_speed_kmh INT,                         -- 默认速度
    default_lanes INT,                             -- 默认车道数
    default_width_m DOUBLE PRECISION,              -- 默认宽度
    
    -- 车辆通行性
    passable_by_car BOOLEAN DEFAULT true,
    passable_by_truck BOOLEAN DEFAULT true,
    passable_by_emergency BOOLEAN DEFAULT true,
    
    -- 代价系数
    base_cost_factor DOUBLE PRECISION DEFAULT 1.0, -- 基础代价系数
    
    description VARCHAR(200)
);

INSERT INTO operational_v2.road_type_defaults_v2 VALUES
('motorway', 120, 4, 14.0, true, true, true, 0.8, '高速公路'),
('motorway_link', 60, 1, 5.0, true, true, true, 0.9, '高速匝道'),
('trunk', 100, 4, 12.0, true, true, true, 0.85, '国道/主干道'),
('trunk_link', 50, 1, 4.5, true, true, true, 0.95, '主干道匝道'),
('primary', 80, 2, 10.0, true, true, true, 0.9, '省道/一级公路'),
('primary_link', 40, 1, 4.0, true, true, true, 1.0, '省道匝道'),
('secondary', 60, 2, 8.0, true, true, true, 1.0, '县道/二级公路'),
('secondary_link', 30, 1, 3.5, true, true, true, 1.1, '县道匝道'),
('tertiary', 40, 2, 6.0, true, true, true, 1.1, '乡道/三级公路'),
('tertiary_link', 25, 1, 3.0, true, true, true, 1.2, '乡道匝道'),
('residential', 30, 2, 5.0, true, false, true, 1.2, '居民区道路'),
('living_street', 20, 1, 4.0, true, false, true, 1.3, '生活街道'),
('service', 20, 1, 3.5, true, false, true, 1.3, '服务道路'),
('unclassified', 30, 1, 4.0, true, true, true, 1.2, '未分类道路'),
('track', 20, 1, 3.0, false, false, true, 1.5, '土路/机耕路'),
('path', 5, 1, 1.5, false, false, false, 2.0, '小径'),
('footway', 5, 1, 2.0, false, false, false, 3.0, '人行道'),
('cycleway', 15, 1, 2.0, false, false, false, 2.5, '自行车道'),
('bridleway', 10, 1, 2.5, false, false, false, 2.5, '马道'),
('steps', 2, 1, 1.5, false, false, false, 10.0, '台阶');

COMMENT ON TABLE operational_v2.road_type_defaults_v2 IS '道路类型默认参数 - 用于A*代价计算';

-- ============================================================================
-- 8. 函数：计算边的A*代价
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.calc_edge_cost(
    p_edge_id UUID,
    p_vehicle_type VARCHAR(50) DEFAULT 'standard',
    p_prefer_speed BOOLEAN DEFAULT false
) RETURNS DOUBLE PRECISION AS $$
DECLARE
    v_edge operational_v2.road_edges_v2%ROWTYPE;
    v_defaults operational_v2.road_type_defaults_v2%ROWTYPE;
    v_cost DOUBLE PRECISION;
    v_speed_factor DOUBLE PRECISION := 1.0;
BEGIN
    SELECT * INTO v_edge FROM operational_v2.road_edges_v2 WHERE id = p_edge_id;
    
    IF v_edge.id IS NULL THEN
        RETURN NULL;
    END IF;
    
    -- 不可通行返回极大值
    IF NOT v_edge.is_accessible THEN
        RETURN 999999999;
    END IF;
    
    -- 获取道路类型默认参数
    SELECT * INTO v_defaults FROM operational_v2.road_type_defaults_v2 WHERE road_type = v_edge.road_type;
    
    -- 基础代价 = 长度
    v_cost := v_edge.length_m;
    
    -- 应用地形代价系数
    v_cost := v_cost * COALESCE(v_edge.terrain_cost_factor, 1.0);
    
    -- 应用坡度代价系数
    v_cost := v_cost * COALESCE(v_edge.gradient_cost_factor, 1.0);
    
    -- 应用道路类型代价系数
    IF v_defaults.road_type IS NOT NULL THEN
        v_cost := v_cost * COALESCE(v_defaults.base_cost_factor, 1.0);
    END IF;
    
    -- 应用车辆类型速度系数
    IF v_edge.speed_factors ? p_vehicle_type THEN
        v_speed_factor := (v_edge.speed_factors ->> p_vehicle_type)::DOUBLE PRECISION;
        IF v_speed_factor > 0 THEN
            v_cost := v_cost / v_speed_factor;
        END IF;
    END IF;
    
    -- 如果偏好速度，用时间代替距离
    IF p_prefer_speed THEN
        DECLARE
            v_speed INT := COALESCE(v_edge.max_speed_kmh, v_defaults.default_speed_kmh, 30);
        BEGIN
            -- 时间(秒) = 距离(米) / 速度(km/h) * 3.6
            v_cost := (v_edge.length_m / v_speed) * 3.6;
        END;
    END IF;
    
    RETURN v_cost;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.calc_edge_cost IS '计算边的A*代价，考虑地形、坡度、车辆类型';

-- ============================================================================
-- 9. 函数：检查车辆能否通过边
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.check_vehicle_can_pass_edge(
    p_edge_id UUID,
    p_vehicle_id UUID
) RETURNS TABLE (
    can_pass BOOLEAN,
    reason TEXT
) AS $$
DECLARE
    v_edge operational_v2.road_edges_v2%ROWTYPE;
    v_vehicle operational_v2.vehicles_v2%ROWTYPE;
BEGIN
    SELECT * INTO v_edge FROM operational_v2.road_edges_v2 WHERE id = p_edge_id;
    SELECT * INTO v_vehicle FROM operational_v2.vehicles_v2 WHERE id = p_vehicle_id;
    
    IF v_edge.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '路段不存在';
        RETURN;
    END IF;
    
    IF v_vehicle.id IS NULL THEN
        RETURN QUERY SELECT FALSE, '车辆不存在';
        RETURN;
    END IF;
    
    -- 检查道路是否可通行
    IF NOT v_edge.is_accessible THEN
        RETURN QUERY SELECT FALSE, '道路已封锁: ' || COALESCE(v_edge.blocked_reason, '未知原因');
        RETURN;
    END IF;
    
    -- 检查宽度
    IF v_edge.width_m IS NOT NULL AND v_vehicle.width_m IS NOT NULL THEN
        IF v_vehicle.width_m > v_edge.width_m THEN
            RETURN QUERY SELECT FALSE, '车宽' || v_vehicle.width_m || 'm超过路宽' || v_edge.width_m || 'm';
            RETURN;
        END IF;
    END IF;
    
    -- 检查桥梁限重
    IF v_edge.bridge AND v_edge.bridge_max_weight_ton IS NOT NULL THEN
        IF (v_vehicle.self_weight_kg + v_vehicle.max_weight_kg) / 1000 > v_edge.bridge_max_weight_ton THEN
            RETURN QUERY SELECT FALSE, '车辆总重超过桥梁限重' || v_edge.bridge_max_weight_ton || '吨';
            RETURN;
        END IF;
    END IF;
    
    -- 检查隧道限高
    IF v_edge.tunnel AND v_edge.tunnel_height_m IS NOT NULL THEN
        IF v_vehicle.height_m IS NOT NULL AND v_vehicle.height_m > v_edge.tunnel_height_m THEN
            RETURN QUERY SELECT FALSE, '车高' || v_vehicle.height_m || 'm超过隧道限高' || v_edge.tunnel_height_m || 'm';
            RETURN;
        END IF;
    END IF;
    
    -- 检查坡度
    IF v_edge.max_gradient_percent IS NOT NULL AND v_vehicle.max_gradient_percent IS NOT NULL THEN
        IF v_edge.max_gradient_percent > v_vehicle.max_gradient_percent THEN
            RETURN QUERY SELECT FALSE, '坡度' || v_edge.max_gradient_percent || '%超过车辆能力' || v_vehicle.max_gradient_percent || '%';
            RETURN;
        END IF;
    END IF;
    
    -- 检查地形兼容性
    IF v_edge.terrain_type IS NOT NULL AND v_vehicle.terrain_capabilities IS NOT NULL THEN
        IF NOT v_edge.terrain_type::TEXT = ANY(v_vehicle.terrain_capabilities) THEN
            -- 非全地形车辆，检查是否能通过该地形
            IF NOT v_vehicle.is_all_terrain THEN
                RETURN QUERY SELECT FALSE, '车辆不支持' || v_edge.terrain_type || '地形';
                RETURN;
            END IF;
        END IF;
    END IF;
    
    RETURN QUERY SELECT TRUE, '可以通行';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.check_vehicle_can_pass_edge IS '检查车辆能否通过指定路段';

-- ============================================================================
-- 10. 函数：根据灾害区域更新路网状态
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.update_edges_by_disaster_area(
    p_area_id UUID
) RETURNS INT AS $$
DECLARE
    v_area operational_v2.disaster_affected_areas_v2%ROWTYPE;
    v_updated INT := 0;
BEGIN
    SELECT * INTO v_area FROM operational_v2.disaster_affected_areas_v2 WHERE id = p_area_id;
    
    IF v_area.id IS NULL THEN
        RETURN 0;
    END IF;
    
    -- 更新与灾害区域相交的路段
    UPDATE operational_v2.road_edges_v2 e
    SET 
        is_accessible = v_area.passable,
        blocked_at = CASE WHEN NOT v_area.passable THEN v_area.started_at ELSE NULL END,
        blocked_reason = CASE WHEN NOT v_area.passable THEN v_area.area_type || ': ' || COALESCE(v_area.description, '') ELSE NULL END,
        blocked_until = v_area.estimated_end_at,
        damage_level = CASE 
            WHEN v_area.severity = 'critical' THEN 'destroyed'
            WHEN v_area.severity = 'high' THEN 'severe'
            WHEN v_area.severity = 'medium' THEN 'moderate'
            ELSE 'light'
        END,
        updated_at = now()
    WHERE ST_Intersects(e.geometry::geometry, v_area.geometry::geometry);
    
    GET DIAGNOSTICS v_updated = ROW_COUNT;
    
    RETURN v_updated;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.update_edges_by_disaster_area IS '根据灾害区域更新路网通行状态';

-- ============================================================================
-- 11. 函数：获取从起点到终点的邻居边
-- ============================================================================
CREATE OR REPLACE FUNCTION operational_v2.get_neighbor_edges(
    p_node_id UUID,
    p_vehicle_id UUID DEFAULT NULL
) RETURNS TABLE (
    edge_id UUID,
    to_node_id UUID,
    length_m DOUBLE PRECISION,
    cost DOUBLE PRECISION,
    can_pass BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id AS edge_id,
        CASE 
            WHEN e.from_node_id = p_node_id THEN e.to_node_id
            ELSE e.from_node_id
        END AS to_node_id,
        e.length_m,
        operational_v2.calc_edge_cost(e.id, 'standard', false) AS cost,
        CASE 
            WHEN p_vehicle_id IS NULL THEN e.is_accessible
            ELSE (SELECT cp.can_pass FROM operational_v2.check_vehicle_can_pass_edge(e.id, p_vehicle_id) cp)
        END AS can_pass
    FROM operational_v2.road_edges_v2 e
    WHERE (e.from_node_id = p_node_id OR (e.to_node_id = p_node_id AND NOT e.oneway))
      AND e.is_accessible = true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION operational_v2.get_neighbor_edges IS '获取节点的邻居边，用于A*搜索';

-- ============================================================================
-- 12. 视图：路网统计
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_road_network_stats_v2 AS
SELECT 
    COUNT(*) AS total_edges,
    COUNT(*) FILTER (WHERE is_accessible) AS accessible_edges,
    COUNT(*) FILTER (WHERE NOT is_accessible) AS blocked_edges,
    SUM(length_m) / 1000 AS total_length_km,
    SUM(length_m) FILTER (WHERE is_accessible) / 1000 AS accessible_length_km,
    COUNT(DISTINCT road_type) AS road_type_count,
    AVG(avg_gradient_percent) AS avg_gradient,
    MAX(max_gradient_percent) AS max_gradient
FROM operational_v2.road_edges_v2;

COMMENT ON VIEW operational_v2.v_road_network_stats_v2 IS '路网统计视图';

-- ============================================================================
-- 输出创建结果
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '路网数据模型 V2 创建完成';
    RAISE NOTICE '表: road_nodes_v2, road_edges_v2, disaster_affected_areas_v2, road_type_defaults_v2';
    RAISE NOTICE '函数: calc_edge_cost, check_vehicle_can_pass_edge, update_edges_by_disaster_area, get_neighbor_edges';
    RAISE NOTICE '========================================';
END $$;
