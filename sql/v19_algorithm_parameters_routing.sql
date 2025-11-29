-- ============================================================================
-- v19: 道路与地形参数
-- 
-- 数据来源: 
--   - 中国公路工程技术标准
--   - OpenStreetMap道路分类
--
-- 参数说明:
--   - default_speed_kmh: 默认速度(km/h)
--   - terrain_factors: 地形速度调整系数
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_routing.sql
-- ============================================================================

-- 清理旧数据
DELETE FROM config.algorithm_parameters WHERE category = 'routing';

-- ============================================================================
-- 道路类型速度参数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
-- 高速公路类
('routing', 'ROAD-SPEED-MOTORWAY', '1.0', 'Motorway Speed', '高速公路速度',
 '{"default_speed_kmh": 120, "min_speed_kmh": 60, "max_speed_kmh": 120}'::jsonb,
 '中国公路工程技术标准',
 '高速公路设计速度'),

('routing', 'ROAD-SPEED-MOTORWAY_LINK', '1.0', 'Motorway Link Speed', '高速匝道速度',
 '{"default_speed_kmh": 60, "min_speed_kmh": 40, "max_speed_kmh": 80}'::jsonb,
 '中国公路工程技术标准',
 '高速公路匝道'),

-- 干线公路类
('routing', 'ROAD-SPEED-TRUNK', '1.0', 'Trunk Road Speed', '快速路速度',
 '{"default_speed_kmh": 100, "min_speed_kmh": 60, "max_speed_kmh": 100}'::jsonb,
 '中国公路工程技术标准',
 '一级公路/城市快速路'),

('routing', 'ROAD-SPEED-TRUNK_LINK', '1.0', 'Trunk Link Speed', '快速路匝道速度',
 '{"default_speed_kmh": 50, "min_speed_kmh": 30, "max_speed_kmh": 60}'::jsonb,
 '中国公路工程技术标准',
 '快速路匝道'),

('routing', 'ROAD-SPEED-PRIMARY', '1.0', 'Primary Road Speed', '主干路速度',
 '{"default_speed_kmh": 80, "min_speed_kmh": 40, "max_speed_kmh": 80}'::jsonb,
 '中国公路工程技术标准',
 '二级公路/城市主干路'),

('routing', 'ROAD-SPEED-PRIMARY_LINK', '1.0', 'Primary Link Speed', '主干路匝道速度',
 '{"default_speed_kmh": 40, "min_speed_kmh": 25, "max_speed_kmh": 50}'::jsonb,
 '中国公路工程技术标准',
 '主干路匝道'),

-- 次级道路类
('routing', 'ROAD-SPEED-SECONDARY', '1.0', 'Secondary Road Speed', '次干路速度',
 '{"default_speed_kmh": 60, "min_speed_kmh": 30, "max_speed_kmh": 60}'::jsonb,
 '中国公路工程技术标准',
 '三级公路/城市次干路'),

('routing', 'ROAD-SPEED-SECONDARY_LINK', '1.0', 'Secondary Link Speed', '次干路匝道速度',
 '{"default_speed_kmh": 30, "min_speed_kmh": 20, "max_speed_kmh": 40}'::jsonb,
 '中国公路工程技术标准',
 '次干路匝道'),

('routing', 'ROAD-SPEED-TERTIARY', '1.0', 'Tertiary Road Speed', '支路速度',
 '{"default_speed_kmh": 40, "min_speed_kmh": 20, "max_speed_kmh": 50}'::jsonb,
 '中国公路工程技术标准',
 '四级公路/城市支路'),

('routing', 'ROAD-SPEED-TERTIARY_LINK', '1.0', 'Tertiary Link Speed', '支路匝道速度',
 '{"default_speed_kmh": 25, "min_speed_kmh": 15, "max_speed_kmh": 35}'::jsonb,
 '中国公路工程技术标准',
 '支路匝道'),

-- 城市道路类
('routing', 'ROAD-SPEED-RESIDENTIAL', '1.0', 'Residential Road Speed', '居住区道路速度',
 '{"default_speed_kmh": 30, "min_speed_kmh": 15, "max_speed_kmh": 40}'::jsonb,
 '城市道路设计规范',
 '居住区内部道路'),

('routing', 'ROAD-SPEED-LIVING_STREET', '1.0', 'Living Street Speed', '生活街道速度',
 '{"default_speed_kmh": 20, "min_speed_kmh": 10, "max_speed_kmh": 30}'::jsonb,
 '城市道路设计规范',
 '步行优先的生活街道'),

('routing', 'ROAD-SPEED-SERVICE', '1.0', 'Service Road Speed', '服务道路速度',
 '{"default_speed_kmh": 20, "min_speed_kmh": 10, "max_speed_kmh": 30}'::jsonb,
 '城市道路设计规范',
 '停车场/加油站内部道路'),

('routing', 'ROAD-SPEED-UNCLASSIFIED', '1.0', 'Unclassified Road Speed', '未分类道路速度',
 '{"default_speed_kmh": 30, "min_speed_kmh": 15, "max_speed_kmh": 40}'::jsonb,
 '默认值',
 '未分类道路默认速度'),

-- 特殊道路类
('routing', 'ROAD-SPEED-TRACK', '1.0', 'Track Speed', '机耕路速度',
 '{"default_speed_kmh": 20, "min_speed_kmh": 10, "max_speed_kmh": 30}'::jsonb,
 '农村道路标准',
 '农村机耕路/林道'),

('routing', 'ROAD-SPEED-PATH', '1.0', 'Path Speed', '小路速度',
 '{"default_speed_kmh": 10, "min_speed_kmh": 5, "max_speed_kmh": 20}'::jsonb,
 '默认值',
 '徒步小路/自行车道'),

('routing', 'ROAD-SPEED-FOOTWAY', '1.0', 'Footway Speed', '人行道速度',
 '{"default_speed_kmh": 5, "min_speed_kmh": 3, "max_speed_kmh": 10}'::jsonb,
 '默认值',
 '人行道（仅步行）');

-- ============================================================================
-- 地形速度系数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('routing', 'TERRAIN-FACTORS', '1.0', 'Terrain Speed Factors', '地形速度系数',
 '{
   "urban": 1.0,
   "suburban": 0.9,
   "rural": 0.85,
   "mountain": 0.6,
   "forest": 0.5,
   "grassland": 0.7,
   "water_adjacent": 0.4,
   "desert": 0.7,
   "wetland": 0.3,
   "unknown": 0.8
 }'::jsonb,
 '应急车辆通行标准',
 '不同地形对车速的影响系数');

-- ============================================================================
-- 灾害影响系数
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('routing', 'DISASTER-IMPACT-FACTORS', '1.0', 'Disaster Impact on Roads', '灾害道路影响系数',
 '{
   "earthquake": {
     "damage_radius_km": 50,
     "speed_factor_inner": 0.3,
     "speed_factor_outer": 0.7,
     "bridge_closure_probability": 0.5
   },
   "flood": {
     "depth_threshold_m": 0.3,
     "speed_factor": 0.5,
     "impassable_depth_m": 0.5
   },
   "landslide": {
     "speed_factor": 0.2,
     "clearance_time_hours": 24
   },
   "fire": {
     "buffer_distance_m": 500,
     "speed_factor": 0.4
   }
 }'::jsonb,
 '应急道路通行评估标准',
 '各类灾害对道路通行能力的影响');

-- ============================================================================
-- 车辆类型速度限制
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('routing', 'VEHICLE-SPEED-LIMITS', '1.0', 'Vehicle Type Speed Limits', '车辆类型速度限制',
 '{
   "car": {"max_speed_kmh": 120, "urban_limit_kmh": 60},
   "truck": {"max_speed_kmh": 100, "urban_limit_kmh": 50},
   "heavy_truck": {"max_speed_kmh": 80, "urban_limit_kmh": 40},
   "ambulance": {"max_speed_kmh": 120, "urban_limit_kmh": 80, "emergency_bonus": 1.2},
   "fire_truck": {"max_speed_kmh": 100, "urban_limit_kmh": 70, "emergency_bonus": 1.2},
   "rescue_vehicle": {"max_speed_kmh": 100, "urban_limit_kmh": 60, "emergency_bonus": 1.1},
   "helicopter": {"max_speed_kmh": 250, "terrain_independent": true}
 }'::jsonb,
 '车辆通行规范',
 '不同车辆类型的速度限制');

-- ============================================================================
-- 验证数据完整性
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM config.algorithm_parameters WHERE category = 'routing';
    RAISE NOTICE 'v19: 道路参数插入完成，共%条记录', v_count;
END $$;
