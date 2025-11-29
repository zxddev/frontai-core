-- ============================================================================
-- v19: Sphere人道主义标准数据
-- 
-- 数据来源: Sphere Handbook 2018 Edition
-- https://spherestandards.org/handbook-2018/
--
-- 共25条标准，覆盖：
--   - WASH (水、卫生): 3条
--   - FOOD (食物): 2条
--   - SHELTER (庇护所): 4条
--   - HEALTH (医疗): 6条
--   - NFI (非食物): 2条
--   - COMM (通信): 4条
--   - RESCUE_OPS (救援保障): 4条
--
-- 执行方式: psql -U postgres -d frontai -f sql/v19_algorithm_parameters_sphere.sql
-- ============================================================================

-- 清理旧数据（如果存在）
DELETE FROM config.algorithm_parameters WHERE category = 'sphere';

-- ============================================================================
-- WASH - 水、卫生与个人卫生
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-WASH-001', '2018', 'Survival Water', '生存用水', 
 '{
   "min_quantity": 2.5,
   "target_quantity": 3.0,
   "unit": "liter",
   "scaling_basis": "per_person",
   "applicable_phases": ["immediate"],
   "climate_factors": {"tropical": 1.2, "temperate": 1.0, "cold": 0.8, "arid": 1.5}
 }'::jsonb,
 'Sphere Handbook 2018, WASH Standard 1',
 '立即响应阶段最低生存用水，仅供饮用和食物制备'),

('sphere', 'SPHERE-WASH-002', '2018', 'Basic Water', '基本用水',
 '{
   "min_quantity": 7.5,
   "target_quantity": 15.0,
   "unit": "liter",
   "scaling_basis": "per_person",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 1.2, "temperate": 1.0, "cold": 0.8, "arid": 1.3}
 }'::jsonb,
 'Sphere Handbook 2018, WASH Standard 1',
 '短期/恢复阶段基本用水，含饮用、烹饪和个人卫生'),

('sphere', 'SPHERE-WASH-003', '2018', 'Toilet Ratio', '厕所配比',
 '{
   "min_quantity": 0.05,
   "target_quantity": 0.05,
   "unit": "unit",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, WASH Standard 3',
 '每20人1个厕所，即0.05个/人');

-- ============================================================================
-- FOOD - 食物安全与营养
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-FOOD-001', '2018', 'Daily Calorie Intake', '每日热量摄入',
 '{
   "min_quantity": 2100,
   "target_quantity": 2100,
   "unit": "kcal",
   "scaling_basis": "per_person",
   "applicable_phases": ["immediate", "short_term", "recovery"],
   "climate_factors": {"tropical": 0.95, "temperate": 1.0, "cold": 1.15, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, Food Security Standard 1',
 '每人每日最低热量摄入'),

('sphere', 'SPHERE-FOOD-002', '2018', 'Dry Rations', '干粮配给',
 '{
   "min_quantity": 0.5,
   "target_quantity": 0.6,
   "unit": "kg",
   "scaling_basis": "per_person",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.1, "arid": 1.0}
 }'::jsonb,
 'Calculated from 2100 kcal standard',
 '0.5kg干粮约等于2100kcal');

-- ============================================================================
-- SHELTER - 庇护所与安置
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-SHELTER-001', '2018', 'Covered Living Space', '人均居住面积',
 '{
   "min_quantity": 3.5,
   "target_quantity": 4.5,
   "unit": "m2",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 0.9, "temperate": 1.0, "cold": 1.2, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, Shelter Standard 3',
 '人均最低有盖居住面积'),

('sphere', 'SPHERE-SHELTER-002', '2018', 'Tent (4-person)', '帐篷(4人)',
 '{
   "min_quantity": 0.25,
   "target_quantity": 0.25,
   "unit": "unit",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Standard 4-person emergency tent',
 '4人帐篷，即0.25顶/人'),

('sphere', 'SPHERE-SHELTER-003', '2018', 'Blanket/Thermal Sheet', '毛毯/保温毯',
 '{
   "min_quantity": 1.0,
   "target_quantity": 2.0,
   "unit": "piece",
   "scaling_basis": "per_person",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 0.5, "temperate": 1.0, "cold": 2.0, "arid": 0.8}
 }'::jsonb,
 'Sphere Handbook 2018, Shelter Standard 4',
 '毛毯，寒冷气候需要加倍'),

('sphere', 'SPHERE-SHELTER-004', '2018', 'Sleeping Mat', '睡垫/睡袋',
 '{
   "min_quantity": 1.0,
   "target_quantity": 1.0,
   "unit": "piece",
   "scaling_basis": "per_person",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, Shelter Standard 4',
 '每人1个睡垫或睡袋');

-- ============================================================================
-- HEALTH - 医疗
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-HEALTH-001', '2018', 'First Aid Kit', '急救包',
 '{
   "min_quantity": 0.1,
   "target_quantity": 0.1,
   "unit": "kit",
   "scaling_basis": "per_casualty",
   "applicable_phases": ["immediate"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Emergency medical response standard',
 '每10名伤员1个急救包'),

('sphere', 'SPHERE-HEALTH-002', '2018', 'Stretcher', '担架',
 '{
   "min_quantity": 0.02,
   "target_quantity": 0.05,
   "unit": "unit",
   "scaling_basis": "per_casualty",
   "applicable_phases": ["immediate"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Emergency medical response standard',
 '每50名伤员1副担架（最低），每20名1副（目标）'),

('sphere', 'SPHERE-HEALTH-003', '2018', 'Basic Medical Kit', '基础药品包',
 '{
   "min_quantity": 0.001,
   "target_quantity": 0.001,
   "unit": "kit",
   "scaling_basis": "per_person",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'WHO Essential Medicines',
 '每1000人1套基础药品包'),

('sphere', 'SPHERE-HEALTH-004', '2018', 'Basic Medical Station', '基础医疗点',
 '{
   "min_quantity": 0.0001,
   "target_quantity": 0.0002,
   "unit": "unit",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'WHO Emergency Standards',
 '每10000名受灾群众1个医疗点'),

('sphere', 'SPHERE-HEALTH-005', '2018', 'Patient Beds', '伤员床位',
 '{
   "min_quantity": 1.2,
   "target_quantity": 1.5,
   "unit": "unit",
   "scaling_basis": "per_casualty",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'WHO Emergency Standards',
 '床位数=重伤员数×1.2，预留周转'),

('sphere', 'SPHERE-HEALTH-006', '2018', 'Medical Personnel', '医护人员',
 '{
   "min_quantity": 0.3,
   "target_quantity": 0.5,
   "unit": "person",
   "scaling_basis": "per_bed",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'WHO Emergency Standards',
 '医护人员配比：每10张床位3名医护');

-- ============================================================================
-- NFI - 非食物物资
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-NFI-001', '2018', 'Cooking Set', '烹饪套装',
 '{
   "min_quantity": 0.2,
   "target_quantity": 0.2,
   "unit": "set",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, Food Security Standard',
 '每5人1套烹饪用具'),

('sphere', 'SPHERE-NFI-002', '2018', 'Hygiene Kit', '卫生用品包',
 '{
   "min_quantity": 1.0,
   "target_quantity": 1.0,
   "unit": "kit",
   "scaling_basis": "per_person",
   "applicable_phases": ["short_term", "recovery"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 'Sphere Handbook 2018, WASH Standard',
 '每人每月1套个人卫生用品');

-- ============================================================================
-- COMM - 通信设备（国家地震应急预案）
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-COMM-001', '2018', 'Satellite Phone', '卫星电话',
 '{
   "min_quantity": 1.0,
   "target_quantity": 2.0,
   "unit": "unit",
   "scaling_basis": "per_team",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 '国家地震应急预案 2025, 通信保障',
 '每支救援队伍1部卫星电话'),

('sphere', 'SPHERE-COMM-002', '2018', 'Digital Radio', '数字对讲机',
 '{
   "min_quantity": 1.0,
   "target_quantity": 1.0,
   "unit": "unit",
   "scaling_basis": "per_rescuer",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 '国家地震应急预案 2025, 通信保障',
 '每名救援人员1部数字对讲机'),

('sphere', 'SPHERE-COMM-003', '2018', 'Portable Repeater', '便携中继台',
 '{
   "min_quantity": 1.0,
   "target_quantity": 1.0,
   "unit": "unit",
   "scaling_basis": "per_command_group",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 '国家地震应急预案 2025, 通信保障',
 '每个指挥组1台便携中继台'),

('sphere', 'SPHERE-COMM-004', '2018', 'Emergency Communication Vehicle', '应急通信车',
 '{
   "min_quantity": 0.002,
   "target_quantity": 0.002,
   "unit": "unit",
   "scaling_basis": "per_displaced",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 '国家地震应急预案 2025, 通信保障',
 '每500受灾群众1辆应急通信车');

-- ============================================================================
-- RESCUE_OPS - 救援人员保障
-- ============================================================================

INSERT INTO config.algorithm_parameters (category, code, version, name, name_cn, params, reference, description) VALUES
('sphere', 'SPHERE-RES-001', '2018', 'Rescuer Drinking Water', '救援人员饮水',
 '{
   "min_quantity": 5.0,
   "target_quantity": 7.0,
   "unit": "liter",
   "scaling_basis": "per_rescuer",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.4, "temperate": 1.0, "cold": 0.8, "arid": 1.6}
 }'::jsonb,
 '消防员健康标准, 应急救援作业规范',
 '救援人员高强度作业需要5L/人/天（群众标准的2倍）'),

('sphere', 'SPHERE-RES-002', '2018', 'Rescuer Hot Meals', '救援人员热食',
 '{
   "min_quantity": 3.0,
   "target_quantity": 3.0,
   "unit": "meal",
   "scaling_basis": "per_rescuer",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.2, "arid": 1.0}
 }'::jsonb,
 '应急救援作业规范',
 '每名救援人员每天3餐热食'),

('sphere', 'SPHERE-RES-003', '2018', 'Max Continuous Work Hours', '连续作业上限',
 '{
   "min_quantity": 8.0,
   "target_quantity": 6.0,
   "unit": "hour",
   "scaling_basis": "fixed",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 0.75, "temperate": 1.0, "cold": 0.9, "arid": 0.8}
 }'::jsonb,
 '消防员健康标准',
 '连续作业不超过8小时，高温环境减少'),

('sphere', 'SPHERE-RES-004', '2018', 'Minimum Rest Period', '最低休息时间',
 '{
   "min_quantity": 6.0,
   "target_quantity": 8.0,
   "unit": "hour",
   "scaling_basis": "fixed",
   "applicable_phases": ["immediate", "short_term"],
   "climate_factors": {"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}
 }'::jsonb,
 '消防员健康标准',
 '每轮换周期后至少休息6小时');

-- ============================================================================
-- 验证数据完整性
-- ============================================================================
DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM config.algorithm_parameters WHERE category = 'sphere';
    IF v_count = 25 THEN
        RAISE NOTICE 'v19: Sphere标准数据插入完成，共%条记录', v_count;
    ELSE
        RAISE WARNING 'v19: Sphere标准数据数量异常，期望25条，实际%条', v_count;
    END IF;
END $$;
