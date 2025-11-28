-- ============================================================================
-- V16 Sphere 标准参数修正 (v16_fix_sphere_parameters.sql)
-- 
-- 功能: 修正 supplies_v2 表中的物资参数，使其符合 WHO/Sphere 标准
--   1. 修正 per_person_per_day 参数
--   2. 添加 scaling_basis 字段（区分按人/按伤员/按面积计算）
--   3. 添加 sphere_code 关联到 sphere_standards_v2
--   4. 添加 applicable_phases 字段
--
-- 参考标准:
--   - Sphere Handbook 2018 Edition
--   - WHO Technical Notes on WASH in Emergencies
--   - 中国国家应急物资储备标准
-- ============================================================================

SET search_path TO operational_v2, public;

-- ============================================================================
-- 1. 修正生活物资参数
-- ============================================================================

-- 帐篷: 4人帐篷 = 0.25 顶/转移人员
-- 注意: 按转移人数计算，不是总受灾人数
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 0.25,
        'sphere_code', 'SPHERE-SHELTER-002',
        'scaling_basis', 'per_displaced',
        'notes', '4人帐篷，按转移安置人数计算'
    ),
    scaling_basis = 'per_displaced',
    sphere_category = 'SHELTER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE code = 'SP-LIFE-001' OR name LIKE '%帐篷%';

-- 毛毯/保温毯: 1-2 条/人
-- 气候影响: 寒冷地区需要2倍
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 1.0,
        'sphere_code', 'SPHERE-SHELTER-003',
        'scaling_basis', 'per_person',
        'climate_factor_cold', 2.0,
        'climate_factor_tropical', 0.5,
        'notes', 'Sphere标准: 1条/人，寒冷地区2条/人'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'SHELTER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE code = 'SP-LIFE-002' OR name LIKE '%毛毯%' OR name LIKE '%保温毯%';

-- 饮用水: 7.5-15 L/人/天 (基本标准)
-- 立即响应阶段: 2.5-3 L/人/天 (生存标准)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 7.5,
        'per_person_immediate', 2.5,
        'sphere_code', 'SPHERE-WASH-002',
        'scaling_basis', 'per_person',
        'climate_factor_arid', 1.5,
        'climate_factor_tropical', 1.2,
        'notes', 'Sphere标准: 7.5-15L/人/天，立即响应2.5L/人/天'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'WASH',
    applicable_phases = ARRAY['immediate', 'short_term', 'recovery']::varchar[]
WHERE code = 'SP-LIFE-003' OR name LIKE '%饮用水%' OR name LIKE '%矿泉水%';

-- 方便面/压缩饼干: ~0.5-0.6 kg/人/天 (2100 kcal)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 0.5,
        'sphere_code', 'SPHERE-FOOD-002',
        'scaling_basis', 'per_person',
        'kcal_per_unit', 400,
        'notes', 'Sphere标准: 2100 kcal/人/天，约0.5kg干粮'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'FOOD',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE name LIKE '%方便面%' OR name LIKE '%压缩饼干%' OR name LIKE '%干粮%';

-- 睡袋/睡垫: 1 个/人
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 1.0,
        'sphere_code', 'SPHERE-SHELTER-004',
        'scaling_basis', 'per_person',
        'notes', 'Sphere标准: 每人1个睡袋/睡垫'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'SHELTER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE name LIKE '%睡袋%' OR name LIKE '%睡垫%';

-- ============================================================================
-- 2. 修正医疗物资参数
-- ============================================================================

-- 急救包: 0.1 个/伤员 (每10个伤员1个)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_casualty', 0.1,
        'sphere_code', 'SPHERE-HEALTH-001',
        'scaling_basis', 'per_casualty',
        'notes', 'Sphere标准: 每10名伤员1个急救包'
    ),
    scaling_basis = 'per_casualty',
    sphere_category = 'HEALTH',
    applicable_phases = ARRAY['immediate']::varchar[]
WHERE name LIKE '%急救包%' OR name LIKE '%急救箱%';

-- 担架: 0.02-0.05 个/伤员 (每20-50个伤员1副)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_casualty', 0.02,
        'per_casualty_target', 0.05,
        'sphere_code', 'SPHERE-HEALTH-002',
        'scaling_basis', 'per_casualty',
        'notes', 'Sphere标准: 每20-50名伤员1副担架'
    ),
    scaling_basis = 'per_casualty',
    sphere_category = 'HEALTH',
    applicable_phases = ARRAY['immediate']::varchar[]
WHERE name LIKE '%担架%';

-- 药品包: 0.001 个/人 (每1000人1个标准药品包)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 0.001,
        'sphere_code', 'SPHERE-HEALTH-003',
        'scaling_basis', 'per_person',
        'notes', 'WHO标准: 每1000人1个基础药品包'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'HEALTH',
    applicable_phases = ARRAY['short_term', 'recovery']::varchar[]
WHERE name LIKE '%药品%' AND (name LIKE '%包%' OR name LIKE '%箱%');

-- 消毒液/消毒剂: 按面积计算
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_area_km2', 100,
        'per_person_per_day', 0.1,
        'scaling_basis', 'per_area_km2',
        'notes', '消毒液按受灾面积计算，或每人每天0.1L'
    ),
    scaling_basis = 'per_area_km2',
    sphere_category = 'HEALTH',
    applicable_phases = ARRAY['short_term', 'recovery']::varchar[]
WHERE name LIKE '%消毒%';

-- ============================================================================
-- 3. 修正救援装备参数 (按队伍计算)
-- ============================================================================

-- 生命探测仪: 按队伍配置
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_team', 2,
        'scaling_basis', 'per_team',
        'notes', '每支搜救队配置2台生命探测仪'
    ),
    scaling_basis = 'per_team',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate']::varchar[]
WHERE name LIKE '%生命探测%';

-- 破拆工具: 按队伍配置
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_team', 1,
        'scaling_basis', 'per_team',
        'notes', '每支搜救队配置1套破拆工具'
    ),
    scaling_basis = 'per_team',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate']::varchar[]
WHERE name LIKE '%破拆%' OR name LIKE '%液压剪%' OR name LIKE '%扩张器%';

-- 发电机: 按队伍配置
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_team', 1,
        'per_area_km2', 0.5,
        'scaling_basis', 'per_team',
        'notes', '每支队伍配置1台，或每2km²配置1台'
    ),
    scaling_basis = 'per_team',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE name LIKE '%发电机%';

-- 照明设备: 按队伍配置
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_team', 4,
        'scaling_basis', 'per_team',
        'notes', '每支队伍配置4套照明设备'
    ),
    scaling_basis = 'per_team',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE name LIKE '%照明%' OR name LIKE '%探照灯%';

-- ============================================================================
-- 4. 修正防护装备参数 (按队员计算)
-- ============================================================================

-- 防护服: 1 套/人
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 1.0,
        'scaling_basis', 'per_person',
        'consumable', false,
        'notes', '防护服按救援人员配置，非消耗品'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate', 'short_term']::varchar[]
WHERE name LIKE '%防护服%';

-- 防毒面具: 1 套/人
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 1.0,
        'scaling_basis', 'per_person',
        'consumable', false,
        'notes', '防毒面具按救援人员配置'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'OTHER',
    applicable_phases = ARRAY['immediate']::varchar[]
WHERE name LIKE '%防毒面具%' OR name LIKE '%呼吸器%';

-- ============================================================================
-- 5. NFI (非食品物资) 参数
-- ============================================================================

-- 烹饪套装: 0.2 套/转移人员 (每5人1套)
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_displaced', 0.2,
        'sphere_code', 'SPHERE-NFI-001',
        'scaling_basis', 'per_displaced',
        'notes', 'Sphere标准: 每5人1套烹饪用具'
    ),
    scaling_basis = 'per_displaced',
    sphere_category = 'NFI',
    applicable_phases = ARRAY['short_term', 'recovery']::varchar[]
WHERE name LIKE '%烹饪%' OR name LIKE '%炊具%';

-- 卫生用品包: 1 套/人/月
UPDATE operational_v2.supplies_v2 
SET 
    properties = COALESCE(properties, '{}'::jsonb) || jsonb_build_object(
        'per_person_per_day', 0.033,
        'sphere_code', 'SPHERE-NFI-002',
        'scaling_basis', 'per_person',
        'notes', 'Sphere标准: 每人每月1套卫生用品'
    ),
    scaling_basis = 'per_person',
    sphere_category = 'NFI',
    applicable_phases = ARRAY['short_term', 'recovery']::varchar[]
WHERE name LIKE '%卫生用品%' OR name LIKE '%洗漱%';

-- ============================================================================
-- 6. 创建物资-Sphere标准关联视图
-- ============================================================================

CREATE OR REPLACE VIEW operational_v2.v_supplies_with_sphere AS
SELECT 
    s.id,
    s.code,
    s.name,
    s.category,
    s.scaling_basis,
    s.sphere_category,
    s.applicable_phases,
    s.properties->>'per_person_per_day' AS per_person_per_day,
    s.properties->>'per_casualty' AS per_casualty,
    s.properties->>'per_displaced' AS per_displaced,
    s.properties->>'per_team' AS per_team,
    s.properties->>'sphere_code' AS sphere_code,
    ss.name AS sphere_standard_name,
    ss.min_quantity AS sphere_min_quantity,
    ss.target_quantity AS sphere_target_quantity,
    ss.unit AS sphere_unit,
    ss.climate_factors AS sphere_climate_factors
FROM operational_v2.supplies_v2 s
LEFT JOIN operational_v2.sphere_standards_v2 ss 
    ON s.properties->>'sphere_code' = ss.code
ORDER BY s.category, s.code;

COMMENT ON VIEW operational_v2.v_supplies_with_sphere 
    IS '物资与Sphere标准关联视图，用于需求计算验证';

-- ============================================================================
-- 7. 验证修正结果
-- ============================================================================

SELECT 
    '修正后物资统计' AS report,
    COUNT(*) FILTER (WHERE scaling_basis = 'per_person') AS per_person_count,
    COUNT(*) FILTER (WHERE scaling_basis = 'per_displaced') AS per_displaced_count,
    COUNT(*) FILTER (WHERE scaling_basis = 'per_casualty') AS per_casualty_count,
    COUNT(*) FILTER (WHERE scaling_basis = 'per_team') AS per_team_count,
    COUNT(*) FILTER (WHERE sphere_category IS NOT NULL) AS has_sphere_category
FROM operational_v2.supplies_v2;

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'V16 Sphere Parameters Fix completed!' AS result;
