-- ============================================================================
-- V2 图层与实体模型 (v2_layer_entity_model.sql)
-- 保持与现有前端 emergency-rescue-brain 的完全兼容
-- ============================================================================

-- 实体类型枚举 (与旧Java项目EntityType保持一致)
CREATE TYPE entity_type_v2 AS ENUM (
    -- 装备设备类
    'command_vehicle',           -- 指挥车
    'uav',                       -- 无人机
    'drone',                     -- 无人机(别名)
    'robotic_dog',               -- 机器狗
    'usv',                       -- 无人船
    'ship',                      -- 无人船(别名)
    'realTime_uav',              -- 实时无人机
    'realTime_robotic_dog',      -- 实时机器狗
    'realTime_usv',              -- 实时无人艇
    'realTime_command_vhicle',   -- 实时指挥车
    
    -- 路径类
    'start_point',               -- 路径起点
    'end_point',                 -- 路径终点
    'planned_route',             -- 规划路线
    
    -- 救援目标类
    'rescue_target',             -- 救援目标(被困人员)
    'resettle_point',            -- 安置点
    'rescue_team',               -- 救援队伍
    'resource_point',            -- 应急资源点
    
    -- 区域类
    'danger_area',               -- 风险区域
    'danger_zone',               -- 危险区
    'safety_area',               -- 安全区域
    'investigation_area',        -- 侦查区域
    'weather_area',              -- 天气区域
    
    -- 事件态势类
    'event_point',               -- 应急事件点
    'event_range',               -- 事件范围
    'situation_point',           -- 态势描述点
    'command_post_candidate',    -- 指挥所候选点
    
    -- 灾害信息类
    'earthquake_epicenter'       -- 震中
);

-- 实体来源
CREATE TYPE entity_source_v2 AS ENUM (
    'system',     -- 系统生成
    'manual'      -- 人工标绘
);

-- 图层分类
CREATE TYPE layer_category_v2 AS ENUM (
    'system',     -- 系统图层
    'manual',     -- 人工图层
    'hybrid'      -- 混合图层
);

-- 图层访问范围(角色权限)
CREATE TYPE layer_access_scope_v2 AS ENUM (
    'full',       -- 完全访问(增删改查)
    'read_only',  -- 只读
    'hidden'      -- 不可见
);

-- 几何类型
CREATE TYPE geometry_kind_v2 AS ENUM (
    'point',      -- 点
    'line',       -- 线
    'polygon',    -- 面
    'circle'      -- 圆
);

-- ============================================================================
-- 图层表 layers_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS layers_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 图层编码 (唯一标识, 如: layer.event, layer.resource)
    code VARCHAR(100) NOT NULL UNIQUE,
    
    -- 图层名称
    name VARCHAR(200) NOT NULL,
    
    -- 图层分类
    category layer_category_v2 NOT NULL DEFAULT 'system',
    
    -- 是否默认可见
    visible_by_default BOOLEAN NOT NULL DEFAULT true,
    
    -- 样式配置 (JSONB)
    -- 结构: { point: {...}, line: {...}, polygon: {...}, circle: {...} }
    style_config JSONB DEFAULT '{}',
    
    -- 刷新间隔(秒), NULL表示不自动刷新
    update_interval_seconds INTEGER,
    
    -- 图层描述
    description TEXT,
    
    -- 排序序号
    sort_order INTEGER NOT NULL DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_layers_v2_code ON layers_v2(code) WHERE deleted_at IS NULL;
CREATE INDEX idx_layers_v2_category ON layers_v2(category) WHERE deleted_at IS NULL;

-- ============================================================================
-- 图层类型定义表 layer_type_defaults_v2
-- 定义每个图层支持的实体类型及其元数据
-- ============================================================================
CREATE TABLE IF NOT EXISTS layer_type_defaults_v2 (
    id SERIAL PRIMARY KEY,
    
    -- 图层编码
    layer_code VARCHAR(100) NOT NULL REFERENCES layers_v2(code) ON DELETE CASCADE,
    
    -- 实体类型
    entity_type entity_type_v2 NOT NULL,
    
    -- 几何类型
    geometry_kind geometry_kind_v2 NOT NULL DEFAULT 'point',
    
    -- 图标标识 (前端映射)
    icon VARCHAR(100),
    
    -- 属性键列表 (前端弹窗显示优先级)
    property_keys TEXT[] DEFAULT '{}',
    
    -- 类型默认样式
    default_style JSONB DEFAULT '{}',
    
    UNIQUE(layer_code, entity_type)
);

CREATE INDEX idx_layer_type_defaults_v2_layer ON layer_type_defaults_v2(layer_code);

-- ============================================================================
-- 角色图层权限表 role_layer_bindings_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS role_layer_bindings_v2 (
    id SERIAL PRIMARY KEY,
    
    -- 角色ID (关联 roles_v2)
    role_id UUID NOT NULL,
    
    -- 图层编码
    layer_code VARCHAR(100) NOT NULL REFERENCES layers_v2(code) ON DELETE CASCADE,
    
    -- 访问范围
    access_scope layer_access_scope_v2 NOT NULL DEFAULT 'read_only',
    
    -- 是否默认可见(覆盖图层默认值)
    visible_by_default BOOLEAN,
    
    -- 排序序号
    sort_order INTEGER NOT NULL DEFAULT 0,
    
    UNIQUE(role_id, layer_code)
);

CREATE INDEX idx_role_layer_bindings_v2_role ON role_layer_bindings_v2(role_id);

-- ============================================================================
-- 实体表 entities_v2
-- ============================================================================
CREATE TABLE IF NOT EXISTS entities_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 实体类型
    type entity_type_v2 NOT NULL,
    
    -- 所属图层编码
    layer_code VARCHAR(100) NOT NULL REFERENCES layers_v2(code),
    
    -- 关联设备ID (如果是设备实体)
    device_id VARCHAR(100),
    
    -- 地理位置 (PostGIS几何)
    geometry GEOMETRY NOT NULL,
    
    -- 动态属性 (JSONB)
    -- 不同类型有不同属性:
    -- event_point: {level, time, textContent}
    -- uav: {name, state, battery, speed, model}
    -- realTime_*: {battery, speed, videoUrl, state, name, model}
    -- rescue_target: {locationName, level, time, textContent}
    -- danger_area: {locationName, textContent}
    -- resource_point: {address, contact, telephone}
    -- command_vehicle: {locationName, address, contact, telephone, photo}
    properties JSONB NOT NULL DEFAULT '{}',
    
    -- 实体来源
    source entity_source_v2 NOT NULL DEFAULT 'system',
    
    -- 是否在地图显示
    visible_on_map BOOLEAN NOT NULL DEFAULT true,
    
    -- 是否为动态实体(可实时更新位置)
    is_dynamic BOOLEAN NOT NULL DEFAULT false,
    
    -- 最新定位时间 (动态实体)
    last_position_at TIMESTAMPTZ,
    
    -- 样式覆盖配置 (JSONB)
    style_overrides JSONB DEFAULT '{}',
    
    -- 所属场景ID (可选, 关联 scenarios_v2)
    scenario_id UUID,
    
    -- 关联事件ID (可选)
    event_id UUID,
    
    -- 创建者/更新者
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- 索引
CREATE INDEX idx_entities_v2_layer ON entities_v2(layer_code) WHERE deleted_at IS NULL;
CREATE INDEX idx_entities_v2_type ON entities_v2(type) WHERE deleted_at IS NULL;
CREATE INDEX idx_entities_v2_device ON entities_v2(device_id) WHERE device_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_entities_v2_scenario ON entities_v2(scenario_id) WHERE scenario_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_entities_v2_event ON entities_v2(event_id) WHERE event_id IS NOT NULL AND deleted_at IS NULL;
CREATE INDEX idx_entities_v2_geometry ON entities_v2 USING GIST(geometry) WHERE deleted_at IS NULL;
CREATE INDEX idx_entities_v2_updated ON entities_v2(updated_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_entities_v2_visible ON entities_v2(visible_on_map) WHERE deleted_at IS NULL;
CREATE INDEX idx_entities_v2_dynamic ON entities_v2(is_dynamic) WHERE is_dynamic = true AND deleted_at IS NULL;

-- ============================================================================
-- 视图: 实体DTO (兼容前端API格式)
-- ============================================================================
CREATE OR REPLACE VIEW entities_dto_v2 AS
SELECT 
    e.id::TEXT as id,
    e.layer_code as "layerCode",
    l.name as "layerName",
    e.device_id as "deviceId",
    e.type::TEXT as type,
    ST_AsGeoJSON(e.geometry)::JSONB as geometry,
    e.properties,
    e.visible_on_map as "visibleOnMap",
    e.is_dynamic as dynamic,
    e.source::TEXT as source,
    e.last_position_at::TEXT as "lastPositionAt",
    e.style_overrides as "styleOverrides",
    e.created_at::TEXT as "createdAt",
    e.updated_at::TEXT as "updatedAt"
FROM entities_v2 e
JOIN layers_v2 l ON l.code = e.layer_code
WHERE e.deleted_at IS NULL AND l.deleted_at IS NULL;

-- ============================================================================
-- 视图: 图层DTO (兼容前端API格式)
-- ============================================================================
CREATE OR REPLACE VIEW layers_dto_v2 AS
SELECT 
    l.code,
    l.name,
    l.category::TEXT as category,
    l.visible_by_default as "visibleByDefault",
    l.style_config as "styleConfig",
    l.update_interval_seconds as "updateIntervalSeconds",
    l.description,
    COALESCE(
        (SELECT json_agg(json_build_object(
            'type', ltd.entity_type::TEXT,
            'geometryKind', ltd.geometry_kind::TEXT,
            'icon', ltd.icon,
            'propertyKeys', ltd.property_keys
        ))
        FROM layer_type_defaults_v2 ltd
        WHERE ltd.layer_code = l.code),
        '[]'::json
    ) as "supportedTypes"
FROM layers_v2 l
WHERE l.deleted_at IS NULL;

-- ============================================================================
-- 函数: 根据角色获取可访问图层
-- ============================================================================
CREATE OR REPLACE FUNCTION get_role_layers_v2(
    p_role_id UUID,
    p_layer_codes TEXT[] DEFAULT NULL,
    p_categories layer_category_v2[] DEFAULT NULL,
    p_include_entities BOOLEAN DEFAULT false,
    p_include_hidden_entities BOOLEAN DEFAULT false
)
RETURNS TABLE(
    layer_code VARCHAR(100),
    layer_name VARCHAR(200),
    category layer_category_v2,
    access_scope layer_access_scope_v2,
    visible_by_default BOOLEAN,
    sort_order INTEGER,
    style_config JSONB,
    update_interval_seconds INTEGER,
    supported_types JSONB,
    entities JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        l.code as layer_code,
        l.name as layer_name,
        l.category,
        COALESCE(rlb.access_scope, 'read_only'::layer_access_scope_v2) as access_scope,
        COALESCE(rlb.visible_by_default, l.visible_by_default) as visible_by_default,
        COALESCE(rlb.sort_order, l.sort_order) as sort_order,
        l.style_config,
        l.update_interval_seconds,
        COALESCE(
            (SELECT jsonb_agg(jsonb_build_object(
                'type', ltd.entity_type::TEXT,
                'geometryKind', ltd.geometry_kind::TEXT,
                'icon', ltd.icon,
                'propertyKeys', ltd.property_keys
            ))
            FROM layer_type_defaults_v2 ltd
            WHERE ltd.layer_code = l.code),
            '[]'::jsonb
        ) as supported_types,
        CASE WHEN p_include_entities THEN
            COALESCE(
                (SELECT jsonb_agg(jsonb_build_object(
                    'id', e.id::TEXT,
                    'layerCode', e.layer_code,
                    'deviceId', e.device_id,
                    'type', e.type::TEXT,
                    'geometry', ST_AsGeoJSON(e.geometry)::JSONB,
                    'properties', e.properties,
                    'visibleOnMap', e.visible_on_map,
                    'dynamic', e.is_dynamic,
                    'source', e.source::TEXT,
                    'lastPositionAt', e.last_position_at::TEXT,
                    'styleOverrides', e.style_overrides,
                    'createdAt', e.created_at::TEXT,
                    'updatedAt', e.updated_at::TEXT
                ))
                FROM entities_v2 e
                WHERE e.layer_code = l.code
                  AND e.deleted_at IS NULL
                  AND (p_include_hidden_entities OR e.visible_on_map = true)),
                '[]'::jsonb
            )
        ELSE NULL::jsonb
        END as entities
    FROM layers_v2 l
    LEFT JOIN role_layer_bindings_v2 rlb ON rlb.layer_code = l.code AND rlb.role_id = p_role_id
    WHERE l.deleted_at IS NULL
      AND (p_layer_codes IS NULL OR l.code = ANY(p_layer_codes))
      AND (p_categories IS NULL OR l.category = ANY(p_categories))
      AND COALESCE(rlb.access_scope, 'read_only'::layer_access_scope_v2) != 'hidden'
    ORDER BY COALESCE(rlb.sort_order, l.sort_order);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 预置图层数据
-- ============================================================================
INSERT INTO layers_v2 (code, name, category, visible_by_default, description, sort_order, style_config) VALUES
    -- 系统图层
    ('layer.event', '应急事件', 'system', true, '灾害事件及态势信息', 1, 
     '{"point": {"scale": 1.0}, "polygon": {"color": "#FF4444", "opacity": 0.3}}'),
    ('layer.resource', '应急资源', 'system', true, '物资、设施等资源点位', 2,
     '{"point": {"scale": 0.8}}'),
    ('layer.device', '无人设备', 'system', true, '无人机、机器狗、无人船等设备', 3,
     '{"point": {"scale": 0.9}}'),
    ('layer.realtime', '实时位置', 'system', true, '设备实时位置追踪', 4,
     '{"point": {"scale": 0.9}}'),
    ('layer.rescue', '救援目标', 'system', true, '被困人员、待救援目标', 5,
     '{"point": {"scale": 1.0}}'),
    ('layer.route', '规划路线', 'system', true, '导航路线及路径规划', 6,
     '{"line": {"width": 4, "color": "#00E4FF"}}'),
    ('layer.area', '区域标注', 'hybrid', true, '危险区、安全区等区域', 7,
     '{"polygon": {"opacity": 0.25}}'),
    ('layer.team', '救援队伍', 'system', true, '救援队伍位置', 8,
     '{"point": {"scale": 0.8}}'),
    ('layer.shelter', '安置点', 'system', true, '临时安置点、避难所', 9,
     '{"point": {"scale": 0.8}}'),
    
    -- 人工标绘图层
    ('layer.manual', '人工标绘', 'manual', true, '用户手动标绘的点线面', 10,
     '{"point": {"scale": 0.8}, "line": {"width": 2}, "polygon": {"opacity": 0.2}}')
ON CONFLICT (code) DO NOTHING;

-- 图层类型定义
INSERT INTO layer_type_defaults_v2 (layer_code, entity_type, geometry_kind, icon, property_keys) VALUES
    -- 事件图层
    ('layer.event', 'event_point', 'point', '应急事件图标', ARRAY['level', 'time', 'textContent']),
    ('layer.event', 'event_range', 'polygon', NULL, ARRAY['level', 'textContent']),
    ('layer.event', 'situation_point', 'point', '态势描述图标', ARRAY['locationName', 'time', 'textContent']),
    ('layer.event', 'earthquake_epicenter', 'point', '震中图标', ARRAY['magnitude', 'depth', 'time']),
    
    -- 资源图层
    ('layer.resource', 'resource_point', 'point', '应急资源图标', ARRAY['address', 'contact', 'telephone']),
    ('layer.resource', 'command_post_candidate', 'point', '指挥所图标', ARRAY['locationName', 'capacity']),
    
    -- 设备图层
    ('layer.device', 'uav', 'point', '无人设备图标', ARRAY['name', 'state', 'model']),
    ('layer.device', 'drone', 'point', '无人设备图标', ARRAY['name', 'state', 'model']),
    ('layer.device', 'robotic_dog', 'point', '无人设备图标', ARRAY['name', 'state', 'model']),
    ('layer.device', 'usv', 'point', '无人设备图标', ARRAY['name', 'state', 'model']),
    ('layer.device', 'ship', 'point', '无人设备图标', ARRAY['name', 'state', 'model']),
    ('layer.device', 'command_vehicle', 'point', '指挥车图标', ARRAY['locationName', 'address', 'contact', 'telephone']),
    
    -- 实时位置图层
    ('layer.realtime', 'realTime_uav', 'point', '无人设备图标', ARRAY['battery', 'speed', 'videoUrl', 'state', 'name', 'model']),
    ('layer.realtime', 'realTime_robotic_dog', 'point', '无人设备图标', ARRAY['battery', 'speed', 'videoUrl', 'state', 'name', 'model']),
    ('layer.realtime', 'realTime_usv', 'point', '无人设备图标', ARRAY['battery', 'speed', 'videoUrl', 'state', 'name', 'model']),
    ('layer.realtime', 'realTime_command_vhicle', 'point', '指挥车图标', ARRAY['locationName', 'address', 'contact', 'telephone', 'photo', 'battery', 'speed', 'videoUrl', 'state']),
    
    -- 救援目标图层
    ('layer.rescue', 'rescue_target', 'point', '救援点位图标', ARRAY['locationName', 'level', 'time', 'textContent']),
    
    -- 路线图层
    ('layer.route', 'planned_route', 'line', NULL, ARRAY['distance', 'duration', 'waypoints']),
    ('layer.route', 'start_point', 'point', '起点图标', ARRAY['name']),
    ('layer.route', 'end_point', 'point', '终点图标', ARRAY['name']),
    
    -- 区域图层
    ('layer.area', 'danger_area', 'polygon', NULL, ARRAY['locationName', 'textContent']),
    ('layer.area', 'danger_zone', 'polygon', NULL, ARRAY['locationName', 'level']),
    ('layer.area', 'safety_area', 'polygon', NULL, ARRAY['locationName', 'capacity']),
    ('layer.area', 'investigation_area', 'polygon', NULL, ARRAY['textContent', 'status']),
    ('layer.area', 'weather_area', 'polygon', NULL, ARRAY['weatherType', 'severity']),
    
    -- 队伍图层
    ('layer.team', 'rescue_team', 'point', '救援队伍图标', ARRAY['name', 'memberCount', 'capabilities']),
    
    -- 安置点图层
    ('layer.shelter', 'resettle_point', 'point', '安全点位图标', ARRAY['name', 'capacity', 'currentCount', 'contact'])
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 触发器: 自动更新 updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_timestamp_v2()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tr_layers_v2_updated ON layers_v2;
CREATE TRIGGER tr_layers_v2_updated
    BEFORE UPDATE ON layers_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

DROP TRIGGER IF EXISTS tr_entities_v2_updated ON entities_v2;
CREATE TRIGGER tr_entities_v2_updated
    BEFORE UPDATE ON entities_v2
    FOR EACH ROW EXECUTE FUNCTION update_timestamp_v2();

COMMENT ON TABLE layers_v2 IS '图层定义表 - 与前端emergency-rescue-brain完全兼容';
COMMENT ON TABLE entities_v2 IS '实体表 - 地图上所有动态事物的统一模型';
COMMENT ON TABLE layer_type_defaults_v2 IS '图层类型定义 - 每个图层支持的实体类型及元数据';
COMMENT ON TABLE role_layer_bindings_v2 IS '角色图层权限绑定';
