-- ============================================================================
-- v33_emergency_ai_params.sql
-- EmergencyAI 算法参数配置
-- 
-- 参数说明：
-- - CAPACITY_SAFETY_FACTOR: 救援容量安全系数，1.2表示配置120%冗余
-- - BASE_ROAD_FACTOR: 正常道路的ETA系数（直线距离→实际距离）
-- - DAMAGED_ROAD_FACTOR: 道路损坏时的ETA系数
-- ============================================================================

INSERT INTO config.algorithm_parameters 
(category, code, version, name, name_cn, params, reference, description)
VALUES
-- 容量安全系数（原0.8改为1.2，确保不放弃任何被困者）
('emergency_ai', 'CAPACITY_SAFETY_FACTOR', '1.0', 
 'Capacity Safety Factor', '救援容量安全系数',
 '{"value": 1.2}',
 '救援资源配置规范',
 '被困人员救援容量冗余系数，1.2表示配置120%容量，确保冗余'),

-- 正常道路系数
('emergency_ai', 'BASE_ROAD_FACTOR', '1.0',
 'Base Road Factor', '基础道路系数', 
 '{"value": 1.4}',
 '山区道路ETA计算标准',
 '正常道路情况下直线距离到实际道路距离的系数'),

-- 道路损坏系数
('emergency_ai', 'DAMAGED_ROAD_FACTOR', '1.0',
 'Damaged Road Factor', '道路损坏系数',
 '{"value": 2.8}',
 '灾区道路ETA计算标准', 
 '道路受损时的ETA惩罚系数，约为正常的2倍')

ON CONFLICT (category, code, version, region_code, department_code) 
DO UPDATE SET 
    params = EXCLUDED.params, 
    name = EXCLUDED.name,
    name_cn = EXCLUDED.name_cn,
    reference = EXCLUDED.reference,
    description = EXCLUDED.description,
    updated_at = NOW();

-- 验证
SELECT category, code, params->>'value' AS value, name_cn 
FROM config.algorithm_parameters 
WHERE category = 'emergency_ai' AND is_active = TRUE;
