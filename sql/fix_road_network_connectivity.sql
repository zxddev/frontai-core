-- ============================================================
-- 修复路网连通性问题
-- 问题：99.4% 的双向道路只存储了单向边
-- 解决方案：为 oneway=False 的边创建反向边
-- 
-- 执行结果（2025-11-27）：
-- - 插入反向边: 358,870 条
-- - 边数: 453,351 → 812,221 (+79%)
-- - 1条边节点: 444,970 → 37,215 (-92%)
-- - 2条边节点: 172,426 → 462,066
-- ============================================================

-- 开始事务
BEGIN;

-- 1. 创建临时表存储需要插入的反向边
CREATE TEMP TABLE reverse_edges AS
SELECT 
    gen_random_uuid() as id,
    e.osm_id,
    e.to_node_id as from_node_id,      -- 反转起终点
    e.from_node_id as to_node_id,
    -- 反转 geometry 方向
    ST_Reverse(e.geometry) as geometry,
    e.road_type,
    e.name,
    e.name_en,
    e.ref,
    false as oneway,  -- 反向边也是双向的一部分
    e.access,
    e.max_speed_kmh,
    e.lanes,
    e.length_m,
    e.width_m,
    e.surface,
    -- 反转高程（起点和终点互换）
    e.end_elevation_m as start_elevation_m,
    e.start_elevation_m as end_elevation_m,
    e.elevation_loss_m as elevation_gain_m,  -- 上坡变下坡
    e.elevation_gain_m as elevation_loss_m,  -- 下坡变上坡
    -e.avg_gradient_percent as avg_gradient_percent,  -- 坡度取反
    e.max_gradient_percent,
    e.terrain_type,
    e.bridge,
    e.tunnel,
    e.bridge_max_weight_ton,
    e.tunnel_height_m,
    e.base_cost,
    e.terrain_cost_factor,
    e.gradient_cost_factor,
    e.speed_factors,
    e.min_width_required_m,
    e.max_weight_allowed_ton,
    e.min_clearance_required_mm,
    e.is_accessible,
    e.blocked_at,
    e.blocked_reason,
    e.blocked_until,
    e.damage_level,
    e.properties,
    NOW() as created_at,
    NOW() as updated_at
FROM operational_v2.road_edges_v2 e
WHERE e.oneway = false
  -- 排除已存在反向边的情况
  AND NOT EXISTS (
      SELECT 1 
      FROM operational_v2.road_edges_v2 e2
      WHERE e2.from_node_id = e.to_node_id
        AND e2.to_node_id = e.from_node_id
  );

-- 2. 查看将要插入的反向边数量
SELECT COUNT(*) as reverse_edges_to_insert FROM reverse_edges;

-- 3. 插入反向边
INSERT INTO operational_v2.road_edges_v2 (
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, blocked_at, blocked_reason, blocked_until, damage_level,
    properties, created_at, updated_at
)
SELECT 
    id, osm_id, from_node_id, to_node_id, geometry,
    road_type, name, name_en, ref, oneway, access,
    max_speed_kmh, lanes, length_m, width_m, surface,
    start_elevation_m, end_elevation_m, elevation_gain_m, elevation_loss_m,
    avg_gradient_percent, max_gradient_percent, terrain_type,
    bridge, tunnel, bridge_max_weight_ton, tunnel_height_m,
    base_cost, terrain_cost_factor, gradient_cost_factor, speed_factors,
    min_width_required_m, max_weight_allowed_ton, min_clearance_required_mm,
    is_accessible, blocked_at, blocked_reason, blocked_until, damage_level,
    properties, created_at, updated_at
FROM reverse_edges;

-- 4. 更新节点的 edge_count
UPDATE operational_v2.road_nodes_v2 n
SET edge_count = (
    SELECT COUNT(*)
    FROM operational_v2.road_edges_v2 e
    WHERE e.from_node_id = n.id OR e.to_node_id = n.id
);

-- 5. 验证修复结果
SELECT '修复后统计' as label;

SELECT 
    (SELECT COUNT(*) FROM operational_v2.road_edges_v2) as total_edges,
    (SELECT COUNT(*) FROM operational_v2.road_nodes_v2) as total_nodes;

-- 节点边数分布
SELECT edge_count, COUNT(*) as node_count
FROM operational_v2.road_nodes_v2
GROUP BY edge_count
ORDER BY edge_count;

-- 删除临时表
DROP TABLE IF EXISTS reverse_edges;

-- 提交事务
COMMIT;

-- ============================================================
-- 执行说明：
-- 1. 在 psql 中执行: \i sql/fix_road_network_connectivity.sql
-- 2. 或通过 Python: await db.execute(text(open('sql/fix_road_network_connectivity.sql').read()))
-- 
-- 预期结果：
-- - 边数从 ~453,351 增加到 ~814,000（约 +360,000 反向边）
-- - 节点边数分布更均匀（大多数节点应有 2-4 条边）
-- ============================================================
