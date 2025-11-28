-- ============================================================
-- 修复路网交叉口拓扑问题
-- 问题：道路在交叉口几何相交但没有共享节点，导致路网不连通
-- 解决方案：
--   1. 检测几何相交的边对
--   2. 在交点处创建新节点
--   3. 拆分原有的边（在交点处断开）
--   4. 更新边的 from_node_id/to_node_id
-- 
-- 注意：此脚本执行时间较长，建议分批执行
-- ============================================================

-- 步骤 1: 创建临时表存储需要修复的交叉口
CREATE TEMP TABLE IF NOT EXISTS intersection_fixes AS
WITH crossing_edges AS (
    -- 找出几何相交但不共享节点的边对
    SELECT 
        e1.id as edge1_id,
        e2.id as edge2_id,
        ST_Intersection(e1.geometry::geometry, e2.geometry::geometry) as intersection_geom
    FROM operational_v2.road_edges_v2 e1
    JOIN operational_v2.road_edges_v2 e2 ON e1.id < e2.id
    WHERE ST_Intersects(e1.geometry::geometry, e2.geometry::geometry)
    AND NOT ST_Touches(e1.geometry::geometry, e2.geometry::geometry)
    -- 确保不共享端点
    AND e1.from_node_id != e2.from_node_id
    AND e1.from_node_id != e2.to_node_id
    AND e1.to_node_id != e2.from_node_id
    AND e1.to_node_id != e2.to_node_id
    -- 限制处理数量（可分批执行）
    LIMIT 50000
)
SELECT 
    edge1_id,
    edge2_id,
    ST_X(intersection_geom) as int_lon,
    ST_Y(intersection_geom) as int_lat,
    intersection_geom::geography as int_location
FROM crossing_edges
WHERE GeometryType(intersection_geom) = 'POINT';  -- 只处理点交叉

-- 查看需要修复的数量
SELECT COUNT(*) as fixes_needed FROM intersection_fixes;

-- 步骤 2: 为每个交叉点创建新节点
INSERT INTO operational_v2.road_nodes_v2 (
    id, osm_id, lon, lat, location, node_type, edge_count,
    is_signal, is_toll, properties, created_at, updated_at
)
SELECT DISTINCT ON (int_lon, int_lat)
    gen_random_uuid() as id,
    NULL as osm_id,  -- 人工创建的节点
    int_lon as lon,
    int_lat as lat,
    int_location as location,
    'intersection' as node_type,
    4 as edge_count,  -- 初始估计
    false as is_signal,
    false as is_toll,
    '{"source": "topology_fix"}'::jsonb as properties,
    NOW() as created_at,
    NOW() as updated_at
FROM intersection_fixes
WHERE NOT EXISTS (
    -- 避免在已有节点附近创建重复节点（10米内）
    SELECT 1 FROM operational_v2.road_nodes_v2 n
    WHERE ST_DWithin(n.location, int_location, 10)
);

-- 步骤 3: 更新 intersection_fixes 表，关联新创建的节点
ALTER TABLE intersection_fixes ADD COLUMN IF NOT EXISTS new_node_id UUID;

UPDATE intersection_fixes f
SET new_node_id = (
    SELECT n.id 
    FROM operational_v2.road_nodes_v2 n
    WHERE ST_DWithin(n.location, f.int_location, 10)
    ORDER BY ST_Distance(n.location, f.int_location)
    LIMIT 1
);

-- 步骤 4: 拆分边（这是最复杂的部分）
-- 对于每条被交叉的边，需要：
--   a) 创建两条新边（交点前半段和后半段）
--   b) 删除原边

-- 4a: 创建前半段边（from_node -> intersection_node）
INSERT INTO operational_v2.road_edges_v2 (
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, properties, created_at, updated_at
)
SELECT DISTINCT ON (f.edge1_id, f.new_node_id)
    gen_random_uuid() as id,
    e.osm_id,
    e.from_node_id,
    f.new_node_id as to_node_id,
    -- 截取几何：从起点到交点
    ST_LineSubstring(
        e.geometry::geometry,
        0,
        ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))
    )::geography as geometry,
    e.road_type, e.name, e.name_en, e.ref, e.oneway, e.access,
    e.max_speed_kmh, e.lanes,
    -- 按比例计算长度
    e.length_m * ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)) as length_m,
    e.width_m, e.surface,
    e.start_elevation_m, NULL, NULL, NULL,
    e.avg_gradient_percent, e.max_gradient_percent, e.terrain_type,
    e.bridge, e.tunnel, e.bridge_max_weight_ton, e.tunnel_height_m,
    e.base_cost, e.terrain_cost_factor, e.gradient_cost_factor, e.speed_factors,
    e.min_width_required_m, e.max_weight_allowed_ton, e.min_clearance_required_mm,
    e.is_accessible, 
    jsonb_set(COALESCE(e.properties, '{}'::jsonb), '{split_from}', to_jsonb(e.id::text)),
    NOW(), NOW()
FROM intersection_fixes f
JOIN operational_v2.road_edges_v2 e ON e.id = f.edge1_id
WHERE f.new_node_id IS NOT NULL;

-- 4b: 创建后半段边（intersection_node -> to_node）
INSERT INTO operational_v2.road_edges_v2 (
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, properties, created_at, updated_at
)
SELECT DISTINCT ON (f.edge1_id, f.new_node_id)
    gen_random_uuid() as id,
    e.osm_id,
    f.new_node_id as from_node_id,
    e.to_node_id,
    -- 截取几何：从交点到终点
    ST_LineSubstring(
        e.geometry::geometry,
        ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)),
        1
    )::geography as geometry,
    e.road_type, e.name, e.name_en, e.ref, e.oneway, e.access,
    e.max_speed_kmh, e.lanes,
    -- 按比例计算长度
    e.length_m * (1 - ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))) as length_m,
    e.width_m, e.surface,
    NULL, e.end_elevation_m, NULL, NULL,
    e.avg_gradient_percent, e.max_gradient_percent, e.terrain_type,
    e.bridge, e.tunnel, e.bridge_max_weight_ton, e.tunnel_height_m,
    e.base_cost, e.terrain_cost_factor, e.gradient_cost_factor, e.speed_factors,
    e.min_width_required_m, e.max_weight_allowed_ton, e.min_clearance_required_mm,
    e.is_accessible,
    jsonb_set(COALESCE(e.properties, '{}'::jsonb), '{split_from}', to_jsonb(e.id::text)),
    NOW(), NOW()
FROM intersection_fixes f
JOIN operational_v2.road_edges_v2 e ON e.id = f.edge1_id
WHERE f.new_node_id IS NOT NULL;

-- 对 edge2 做同样处理
INSERT INTO operational_v2.road_edges_v2 (
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, properties, created_at, updated_at
)
SELECT DISTINCT ON (f.edge2_id, f.new_node_id)
    gen_random_uuid() as id,
    e.osm_id,
    e.from_node_id,
    f.new_node_id as to_node_id,
    ST_LineSubstring(
        e.geometry::geometry,
        0,
        ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))
    )::geography as geometry,
    e.road_type, e.name, e.name_en, e.ref, e.oneway, e.access,
    e.max_speed_kmh, e.lanes,
    e.length_m * ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)) as length_m,
    e.width_m, e.surface,
    e.start_elevation_m, NULL, NULL, NULL,
    e.avg_gradient_percent, e.max_gradient_percent, e.terrain_type,
    e.bridge, e.tunnel, e.bridge_max_weight_ton, e.tunnel_height_m,
    e.base_cost, e.terrain_cost_factor, e.gradient_cost_factor, e.speed_factors,
    e.min_width_required_m, e.max_weight_allowed_ton, e.min_clearance_required_mm,
    e.is_accessible,
    jsonb_set(COALESCE(e.properties, '{}'::jsonb), '{split_from}', to_jsonb(e.id::text)),
    NOW(), NOW()
FROM intersection_fixes f
JOIN operational_v2.road_edges_v2 e ON e.id = f.edge2_id
WHERE f.new_node_id IS NOT NULL;

INSERT INTO operational_v2.road_edges_v2 (
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, properties, created_at, updated_at
)
SELECT DISTINCT ON (f.edge2_id, f.new_node_id)
    gen_random_uuid() as id,
    e.osm_id,
    f.new_node_id as from_node_id,
    e.to_node_id,
    ST_LineSubstring(
        e.geometry::geometry,
        ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326)),
        1
    )::geography as geometry,
    e.road_type, e.name, e.name_en, e.ref, e.oneway, e.access,
    e.max_speed_kmh, e.lanes,
    e.length_m * (1 - ST_LineLocatePoint(e.geometry::geometry, ST_SetSRID(ST_MakePoint(f.int_lon, f.int_lat), 4326))) as length_m,
    e.width_m, e.surface,
    NULL, e.end_elevation_m, NULL, NULL,
    e.avg_gradient_percent, e.max_gradient_percent, e.terrain_type,
    e.bridge, e.tunnel, e.bridge_max_weight_ton, e.tunnel_height_m,
    e.base_cost, e.terrain_cost_factor, e.gradient_cost_factor, e.speed_factors,
    e.min_width_required_m, e.max_weight_allowed_ton, e.min_clearance_required_mm,
    e.is_accessible,
    jsonb_set(COALESCE(e.properties, '{}'::jsonb), '{split_from}', to_jsonb(e.id::text)),
    NOW(), NOW()
FROM intersection_fixes f
JOIN operational_v2.road_edges_v2 e ON e.id = f.edge2_id
WHERE f.new_node_id IS NOT NULL;

-- 步骤 5: 标记原边为不可用（保留数据但不参与路径规划）
UPDATE operational_v2.road_edges_v2
SET is_accessible = false,
    properties = jsonb_set(COALESCE(properties, '{}'::jsonb), '{replaced_by_split}', 'true'::jsonb)
WHERE id IN (SELECT edge1_id FROM intersection_fixes WHERE new_node_id IS NOT NULL)
   OR id IN (SELECT edge2_id FROM intersection_fixes WHERE new_node_id IS NOT NULL);

-- 步骤 6: 更新节点的 edge_count
UPDATE operational_v2.road_nodes_v2 n
SET edge_count = (
    SELECT COUNT(*)
    FROM operational_v2.road_edges_v2 e
    WHERE (e.from_node_id = n.id OR e.to_node_id = n.id)
    AND e.is_accessible = true
)
WHERE id IN (
    SELECT new_node_id FROM intersection_fixes WHERE new_node_id IS NOT NULL
    UNION
    SELECT from_node_id FROM operational_v2.road_edges_v2 
    WHERE id IN (SELECT edge1_id FROM intersection_fixes) OR id IN (SELECT edge2_id FROM intersection_fixes)
    UNION
    SELECT to_node_id FROM operational_v2.road_edges_v2 
    WHERE id IN (SELECT edge1_id FROM intersection_fixes) OR id IN (SELECT edge2_id FROM intersection_fixes)
);

-- 验证结果
SELECT '修复完成' as status;
SELECT COUNT(*) as new_intersection_nodes 
FROM operational_v2.road_nodes_v2 
WHERE properties->>'source' = 'topology_fix';

SELECT COUNT(*) as split_edges 
FROM operational_v2.road_edges_v2 
WHERE properties ? 'split_from';

SELECT COUNT(*) as disabled_edges 
FROM operational_v2.road_edges_v2 
WHERE properties->>'replaced_by_split' = 'true';

-- 清理临时表
DROP TABLE IF EXISTS intersection_fixes;
