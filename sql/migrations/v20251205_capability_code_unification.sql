-- ============================================================================
-- 能力代码统一迁移脚本
-- 版本: v20251205
-- 目的: 将 team_capabilities_v2 中的旧能力代码迁移为 capability_codes_v2 标准代码
-- 
-- 问题背景:
--   系统存在三套能力代码体系，导致资源匹配失败：
--   1. capability_codes_v2 (标准): SEARCH_LIFE_DETECT, HAZMAT_DECON 等
--   2. team_capabilities_v2 (实际): LIFE_DETECTION, DECONTAMINATION 等
--   3. Neo4j 知识图谱: 同样使用旧代码
--
-- 执行前请备份数据！
-- ============================================================================

-- 开始事务
BEGIN;

-- ============================================================================
-- 1. 首先检查需要新增的能力代码（在 team_capabilities_v2 中使用但 capability_codes_v2 中不存在）
-- ============================================================================

-- 新增 COMMAND_COORDINATION (指挥协调)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('COMMAND_COORDINATION', '指挥协调', 'command', '现场指挥协调能力', '{communication}')
ON CONFLICT (code) DO NOTHING;

-- 新增 EVACUATION_COORDINATION (疏散协调) - 与 LOG_SHELTER 区分
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('EVACUATION_COORDINATION', '疏散协调', 'evacuation', '组织协调人员安全疏散', '{communication,transport}')
ON CONFLICT (code) DO NOTHING;

-- 新增 UAV_THERMAL (无人机热成像)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('UAV_THERMAL', '无人机热成像', 'search', '使用无人机热成像进行搜索', '{search_detect}')
ON CONFLICT (code) DO NOTHING;

-- 新增 CHEMICAL_FIRE (化学火灾扑救) - 与 HAZMAT_FIRE 同义
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('CHEMICAL_FIRE', '化学火灾扑救', 'hazmat', '危化品火灾扑救', '{hazmat,protection}')
ON CONFLICT (code) DO NOTHING;

-- 新增 CPR_AED (心肺复苏/AED)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('CPR_AED', '心肺复苏', 'medical', 'CPR和AED急救', '{medical}')
ON CONFLICT (code) DO NOTHING;

-- 新增 TRAUMA_CARE (创伤护理)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('TRAUMA_CARE', '创伤护理', 'medical', '创伤紧急护理', '{medical}')
ON CONFLICT (code) DO NOTHING;

-- 新增 EMERGENCY_TREATMENT (紧急救治)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('EMERGENCY_TREATMENT', '紧急救治', 'medical', '现场紧急医疗救治', '{medical}')
ON CONFLICT (code) DO NOTHING;

-- 新增 SUPPLY_TRANSPORT (物资运输)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('SUPPLY_TRANSPORT', '物资运输', 'logistics', '救援物资运输', '{transport}')
ON CONFLICT (code) DO NOTHING;

-- 新增 STRUCTURAL_RESCUE (结构救援) - 兼容旧代码
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('STRUCTURAL_RESCUE', '结构救援', 'rescue', '倒塌建筑结构救援', '{rescue_tool}')
ON CONFLICT (code) DO NOTHING;

-- 新增 COMMUNICATION_SUPPORT (通信保障)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('COMMUNICATION_SUPPORT', '通信保障', 'logistics', '应急通信保障', '{communication}')
ON CONFLICT (code) DO NOTHING;

-- 新增 POWER_EMERGENCY (应急供电)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('POWER_EMERGENCY', '应急供电', 'logistics', '现场应急电力供应', '{power}')
ON CONFLICT (code) DO NOTHING;

-- 新增 LIGHTING_MOBILE (移动照明)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('LIGHTING_MOBILE', '移动照明', 'logistics', '现场移动照明', '{lighting}')
ON CONFLICT (code) DO NOTHING;

-- 新增 LIFE_DETECTION (生命探测) - 作为 SEARCH_LIFE_DETECT 的别名
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('LIFE_DETECTION', '生命探测', 'search', '使用设备探测被困人员生命迹象', '{search_detect}')
ON CONFLICT (code) DO NOTHING;

-- 新增 HAZMAT_CONTAINMENT (危化品围堵)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('HAZMAT_CONTAINMENT', '危化品围堵', 'hazmat', '对泄漏危化品进行围堵控制', '{hazmat,protection}')
ON CONFLICT (code) DO NOTHING;

-- 新增 HAZMAT_DETECTION (危化品检测)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('HAZMAT_DETECTION', '危化品检测', 'hazmat', '检测识别危险化学品种类和浓度', '{hazmat}')
ON CONFLICT (code) DO NOTHING;

-- 新增 DECONTAMINATION (洗消去污) - 关键！这是导致 330km 搜索失败的原因
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('DECONTAMINATION', '洗消去污', 'hazmat', '对人员和设备进行洗消去污', '{hazmat}')
ON CONFLICT (code) DO NOTHING;

-- 新增 SHELTER_MANAGEMENT (安置点管理)
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('SHELTER_MANAGEMENT', '安置点管理', 'evacuation', '管理临时安置点', '{other}')
ON CONFLICT (code) DO NOTHING;

-- 新增 ENG_DEMOLITION (破拆清障) - 兼容别名
INSERT INTO operational_v2.capability_codes_v2 (code, name, category, description, related_equipment_categories)
VALUES ('ENG_DEMOLITION', '破拆清障', 'engineering', '障碍物破拆清除', '{rescue_tool}')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- 2. 关键修复：为具备 HAZMAT_DECON 能力的队伍添加 DECONTAMINATION 别名
-- 原因：Neo4j 规则要求 DECONTAMINATION，但队伍存储的是 HAZMAT_DECON
-- ============================================================================

-- 为所有具备 HAZMAT_DECON 的队伍添加 DECONTAMINATION 能力（如果不存在）
INSERT INTO operational_v2.team_capabilities_v2 
    (id, team_id, capability_code, capability_name, capability_category, proficiency_level, training_date, max_capacity, equipment_ids, notes)
SELECT 
    gen_random_uuid(),
    tc.team_id,
    'DECONTAMINATION',
    '洗消去污',
    'hazmat',
    tc.proficiency_level,
    tc.training_date,
    tc.max_capacity,
    tc.equipment_ids,
    '{"alias_of": "HAZMAT_DECON"}'
FROM operational_v2.team_capabilities_v2 tc
WHERE tc.capability_code = 'HAZMAT_DECON'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc2 
    WHERE tc2.team_id = tc.team_id AND tc2.capability_code = 'DECONTAMINATION'
);

-- 同样为其他关键能力创建别名映射
-- HAZMAT_DETECT -> HAZMAT_DETECTION
INSERT INTO operational_v2.team_capabilities_v2 
    (id, team_id, capability_code, capability_name, capability_category, proficiency_level, training_date, max_capacity, equipment_ids, notes)
SELECT 
    gen_random_uuid(),
    tc.team_id,
    'HAZMAT_DETECTION',
    '危化品检测',
    'hazmat',
    tc.proficiency_level,
    tc.training_date,
    tc.max_capacity,
    tc.equipment_ids,
    '{"alias_of": "HAZMAT_DETECT"}'
FROM operational_v2.team_capabilities_v2 tc
WHERE tc.capability_code = 'HAZMAT_DETECT'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc2 
    WHERE tc2.team_id = tc.team_id AND tc2.capability_code = 'HAZMAT_DETECTION'
);

-- HAZMAT_CONTAIN -> HAZMAT_CONTAINMENT
INSERT INTO operational_v2.team_capabilities_v2 
    (id, team_id, capability_code, capability_name, capability_category, proficiency_level, training_date, max_capacity, equipment_ids, notes)
SELECT 
    gen_random_uuid(),
    tc.team_id,
    'HAZMAT_CONTAINMENT',
    '危化品围堵',
    'hazmat',
    tc.proficiency_level,
    tc.training_date,
    tc.max_capacity,
    tc.equipment_ids,
    '{"alias_of": "HAZMAT_CONTAIN"}'
FROM operational_v2.team_capabilities_v2 tc
WHERE tc.capability_code = 'HAZMAT_CONTAIN'
AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc2 
    WHERE tc2.team_id = tc.team_id AND tc2.capability_code = 'HAZMAT_CONTAINMENT'
);

-- ============================================================================
-- 3. 验证：查看现在 capability_codes_v2 中的所有代码
-- ============================================================================

-- SELECT code, name, category FROM operational_v2.capability_codes_v2 ORDER BY category, code;

-- ============================================================================
-- 4. 验证：检查 team_capabilities_v2 中是否还有未定义的能力代码
-- ============================================================================

-- SELECT DISTINCT tc.capability_code 
-- FROM operational_v2.team_capabilities_v2 tc
-- LEFT JOIN operational_v2.capability_codes_v2 cc ON tc.capability_code = cc.code
-- WHERE cc.code IS NULL;

-- 提交事务
COMMIT;

-- ============================================================================
-- 执行完成后的验证查询（手动执行）
-- ============================================================================
-- 
-- 1. 检查新增的能力代码：
-- SELECT * FROM operational_v2.capability_codes_v2 WHERE created_at > NOW() - INTERVAL '1 hour';
--
-- 2. 检查是否还有孤立的能力代码：
-- SELECT DISTINCT tc.capability_code, COUNT(*) as team_count
-- FROM operational_v2.team_capabilities_v2 tc
-- LEFT JOIN operational_v2.capability_codes_v2 cc ON tc.capability_code = cc.code
-- WHERE cc.code IS NULL
-- GROUP BY tc.capability_code;
