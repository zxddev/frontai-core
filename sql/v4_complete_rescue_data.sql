-- ============================================================================
-- 完整救援资源数据补充 V4
-- 包含：队伍、能力、装备
-- 针对茂县及周边区域的完整救援体系
-- ============================================================================

-- ============================================================================
-- 1. 补充救援队伍数据
-- ============================================================================

-- 1.1 茂县本地队伍
INSERT INTO rescue_teams_v2 (
    code, name, team_type, parent_org, base_address,
    base_location,
    total_personnel, available_personnel,
    contact_phone, status, capability_level
) VALUES
-- 消防队伍
('MX-FR-001', '茂县消防救援大队', 'fire_rescue', '茂县', '四川省阿坝州茂县凤仪镇消防路1号',
 ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326),
 60, 55, '0837-7422119', 'standby', 4),
('MX-FR-002', '茂县第二消防救援站', 'fire_rescue', '茂县', '四川省阿坝州茂县南新镇',
 ST_SetSRID(ST_MakePoint(103.8680, 31.6720), 4326),
 35, 30, '0837-7423119', 'standby', 3),

-- 医疗队伍
('MX-MD-001', '茂县人民医院急救队', 'medical', '茂县', '四川省阿坝州茂县凤仪镇医院路',
 ST_SetSRID(ST_MakePoint(103.8520, 31.6810), 4326),
 30, 25, '0837-7422120', 'standby', 4),
('MX-MD-002', '茂县中医院急救队', 'medical', '茂县', '四川省阿坝州茂县凤仪镇中医院路',
 ST_SetSRID(ST_MakePoint(103.8550, 31.6800), 4326),
 25, 20, '0837-7422121', 'standby', 3),

-- 应急管理局救援队
('MX-SR-001', '茂县应急管理局救援队', 'search_rescue', '茂县', '四川省阿坝州茂县凤仪镇应急中心',
 ST_SetSRID(ST_MakePoint(103.8530, 31.6820), 4326),
 50, 45, '0837-7422112', 'standby', 4),

-- 工程抢险队伍
('MX-EN-001', '茂县住建局抢险队', 'engineering', '茂县', '四川省阿坝州茂县凤仪镇建设路',
 ST_SetSRID(ST_MakePoint(103.8540, 31.6808), 4326),
 40, 35, '0837-7422333', 'standby', 3),
('MX-EN-002', '茂县交通运输局抢险队', 'engineering', '茂县', '四川省阿坝州茂县凤仪镇交通路',
 ST_SetSRID(ST_MakePoint(103.8600, 31.6780), 4326),
 35, 30, '0837-7422444', 'standby', 3),

-- 水上救援队伍
('MX-WR-001', '茂县水上救援队', 'water_rescue', '茂县', '四川省阿坝州茂县凤仪镇水利局',
 ST_SetSRID(ST_MakePoint(103.8537, 31.6815), 4326),
 25, 20, '0837-7422555', 'standby', 4),

-- 志愿者队伍
('MX-VL-001', '蓝天救援队茂县分队', 'volunteer', '茂县', '四川省阿坝州茂县凤仪镇志愿者中心',
 ST_SetSRID(ST_MakePoint(103.8535, 31.6818), 4326),
 40, 35, '13800138001', 'standby', 3)
ON CONFLICT (code) DO UPDATE SET
    status = 'standby',
    available_personnel = EXCLUDED.available_personnel;

-- 1.2 阿坝州级队伍
INSERT INTO rescue_teams_v2 (
    code, name, team_type, parent_org, base_address,
    base_location,
    total_personnel, available_personnel,
    contact_phone, status, capability_level
) VALUES
('AB-FR-001', '阿坝州消防救援支队', 'fire_rescue', '阿坝州', '四川省阿坝州马尔康市消防支队',
 ST_SetSRID(ST_MakePoint(102.2065, 31.9057), 4326),
 200, 180, '0837-2822119', 'standby', 5),
('AB-WR-001', '阿坝州水上应急救援支队', 'water_rescue', '阿坝州', '四川省阿坝州马尔康市应急局',
 ST_SetSRID(ST_MakePoint(102.2065, 31.9057), 4326),
 60, 50, '0837-2822120', 'standby', 5),
('AB-HZ-001', '阿坝州危化品应急救援队', 'hazmat', '阿坝州', '四川省阿坝州马尔康市化工园区',
 ST_SetSRID(ST_MakePoint(102.2100, 31.9100), 4326),
 45, 40, '0837-2822130', 'standby', 5),
('AB-MD-001', '阿坝州医疗急救中心', 'medical', '阿坝州', '四川省阿坝州马尔康市人民医院',
 ST_SetSRID(ST_MakePoint(102.2050, 31.9050), 4326),
 80, 70, '0837-2822150', 'standby', 5),
('AB-SR-001', '阿坝州地质灾害应急救援队', 'search_rescue', '阿坝州', '四川省阿坝州马尔康市国土局',
 ST_SetSRID(ST_MakePoint(102.2080, 31.9070), 4326),
 50, 45, '0837-2822160', 'standby', 5),
('AB-CM-001', '阿坝州通信保障应急队', 'communication', '阿坝州', '四川省阿坝州马尔康市通信管理局',
 ST_SetSRID(ST_MakePoint(102.2090, 31.9080), 4326),
 30, 25, '0837-2822170', 'standby', 4)
ON CONFLICT (code) DO UPDATE SET
    status = 'standby',
    available_personnel = EXCLUDED.available_personnel;

-- 1.3 省级专业队伍
INSERT INTO rescue_teams_v2 (
    code, name, team_type, parent_org, base_address,
    base_location,
    total_personnel, available_personnel,
    contact_phone, status, capability_level
) VALUES
('SC-FR-001', '四川省消防救援总队特勤大队', 'fire_rescue', '四川省', '四川省成都市武侯区消防总队',
 ST_SetSRID(ST_MakePoint(104.0668, 30.5728), 4326),
 300, 280, '028-86303119', 'standby', 5),
('SC-HZ-001', '四川省危化品应急救援队', 'hazmat', '四川省', '四川省成都市青白江区化工基地',
 ST_SetSRID(ST_MakePoint(104.2500, 30.7800), 4326),
 100, 90, '028-86303130', 'standby', 5),
('SC-WR-001', '四川省水上救援总队', 'water_rescue', '四川省', '四川省成都市都江堰市水利局',
 ST_SetSRID(ST_MakePoint(103.6200, 30.9900), 4326),
 150, 130, '028-86303140', 'standby', 5),
('SC-MR-001', '四川省矿山救护队', 'mine_rescue', '四川省', '四川省成都市龙泉驿区矿山救护基地',
 ST_SetSRID(ST_MakePoint(104.1000, 30.6500), 4326),
 120, 100, '028-86303150', 'standby', 5),
('SC-MD-001', '华西医院应急医疗队', 'medical', '四川省', '四川省成都市武侯区华西医院',
 ST_SetSRID(ST_MakePoint(104.0400, 30.6400), 4326),
 100, 90, '028-85422120', 'standby', 5),
('SC-SR-001', '四川省地震应急救援队', 'search_rescue', '四川省', '四川省成都市金牛区地震局',
 ST_SetSRID(ST_MakePoint(104.0600, 30.6700), 4326),
 150, 130, '028-86303160', 'standby', 5),
('SC-EN-001', '四川路桥抢险救援队', 'engineering', '四川省', '四川省成都市成华区四川路桥',
 ST_SetSRID(ST_MakePoint(104.0800, 30.6600), 4326),
 200, 180, '028-86303170', 'standby', 5),
('DY-SR-001', '德阳市应急救援中心', 'search_rescue', '德阳市', '四川省德阳市旌阳区应急中心',
 ST_SetSRID(ST_MakePoint(104.3970, 31.1270), 4326),
 80, 70, '0838-2222119', 'standby', 4)
ON CONFLICT (code) DO UPDATE SET
    status = 'standby',
    available_personnel = EXCLUDED.available_personnel;

-- ============================================================================
-- 2. 补充队伍能力数据 (先删除再插入，避免重复)
-- ============================================================================

-- 2.1 消防队伍能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 茂县消防救援大队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-FR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'FIRE_SUPPRESSION', '火灾扑救', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 4),
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 3),
        (v_team_id, 'ROPE_RESCUE', '绳索救援', 3);
    END IF;
    
    -- 茂县第二消防救援站
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-FR-002';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'FIRE_SUPPRESSION', '火灾扑救', 4),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 3),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 3);
    END IF;
    
    -- 阿坝州消防救援支队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-FR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'FIRE_SUPPRESSION', '火灾扑救', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 5),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 4),
        (v_team_id, 'ROPE_RESCUE', '绳索救援', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4);
    END IF;
    
    -- 四川省消防救援总队特勤大队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-FR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'FIRE_SUPPRESSION', '火灾扑救', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 5),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 5),
        (v_team_id, 'HAZMAT_CONTAINMENT', '危化品堵漏', 5),
        (v_team_id, 'ROPE_RESCUE', '绳索救援', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5);
    END IF;
END $$;

-- 2.2 医疗队伍能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 茂县人民医院急救队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-MD-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'MEDICAL_TRIAGE', '医疗分诊', 5),
        (v_team_id, 'EMERGENCY_TREATMENT', '紧急救治', 5),
        (v_team_id, 'TRAUMA_CARE', '创伤处理', 4),
        (v_team_id, 'CPR_AED', '心肺复苏', 5);
    END IF;
    
    -- 茂县中医院急救队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-MD-002';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'MEDICAL_TRIAGE', '医疗分诊', 4),
        (v_team_id, 'EMERGENCY_TREATMENT', '紧急救治', 4),
        (v_team_id, 'TRAUMA_CARE', '创伤处理', 3);
    END IF;
    
    -- 阿坝州医疗急救中心
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-MD-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'MEDICAL_TRIAGE', '医疗分诊', 5),
        (v_team_id, 'EMERGENCY_TREATMENT', '紧急救治', 5),
        (v_team_id, 'TRAUMA_CARE', '创伤处理', 5),
        (v_team_id, 'PATIENT_TRANSPORT', '患者转运', 5),
        (v_team_id, 'CPR_AED', '心肺复苏', 5);
    END IF;
    
    -- 华西医院应急医疗队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-MD-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'MEDICAL_TRIAGE', '医疗分诊', 5),
        (v_team_id, 'EMERGENCY_TREATMENT', '紧急救治', 5),
        (v_team_id, 'TRAUMA_CARE', '创伤处理', 5),
        (v_team_id, 'SURGERY', '现场手术', 5),
        (v_team_id, 'PATIENT_TRANSPORT', '患者转运', 5),
        (v_team_id, 'CPR_AED', '心肺复苏', 5);
    END IF;
END $$;

-- 2.3 应急救援队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 茂县应急管理局救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-SR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5),
        (v_team_id, 'COMMAND_COORDINATION', '指挥协调', 5);
    END IF;
    
    -- 蓝天救援队茂县分队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-VL-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 3),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 3),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4),
        (v_team_id, 'VOLUNTEER_SUPPORT', '志愿服务', 5);
    END IF;
    
    -- 阿坝州地质灾害应急救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-SR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 5),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5),
        (v_team_id, 'LANDSLIDE_RESCUE', '滑坡救援', 5);
    END IF;
    
    -- 四川省地震应急救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-SR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 5),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5),
        (v_team_id, 'HEAVY_LIFTING', '重型起吊', 5),
        (v_team_id, 'ROPE_RESCUE', '绳索救援', 5);
    END IF;
    
    -- 德阳市应急救援中心
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'DY-SR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4);
    END IF;
END $$;

-- 2.4 工程抢险队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 茂县住建局抢险队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-EN-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 3),
        (v_team_id, 'ROAD_CLEARANCE', '道路清障', 5),
        (v_team_id, 'BUILDING_SHORING', '建筑支撑', 4),
        (v_team_id, 'DEMOLITION', '破拆作业', 4);
    END IF;
    
    -- 茂县交通运输局抢险队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-EN-002';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'ROAD_CLEARANCE', '道路清障', 5),
        (v_team_id, 'BRIDGE_REPAIR', '桥梁抢修', 4),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 3);
    END IF;
    
    -- 四川路桥抢险救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-EN-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'ROAD_CLEARANCE', '道路清障', 5),
        (v_team_id, 'BRIDGE_REPAIR', '桥梁抢修', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'HEAVY_LIFTING', '重型起吊', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4);
    END IF;
END $$;

-- 2.5 水上救援队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 茂县水上救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'MX-WR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'WATER_RESCUE', '水上救援', 4),
        (v_team_id, 'SWIFT_WATER_RESCUE', '急流救援', 3),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 3),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4);
    END IF;
    
    -- 阿坝州水上应急救援支队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-WR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'WATER_RESCUE', '水上救援', 5),
        (v_team_id, 'SWIFT_WATER_RESCUE', '急流救援', 5),
        (v_team_id, 'DIVING_RESCUE', '潜水救援', 4),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5);
    END IF;
    
    -- 四川省水上救援总队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-WR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'WATER_RESCUE', '水上救援', 5),
        (v_team_id, 'SWIFT_WATER_RESCUE', '急流救援', 5),
        (v_team_id, 'DIVING_RESCUE', '潜水救援', 5),
        (v_team_id, 'UNDERWATER_SEARCH', '水下搜索', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5);
    END IF;
END $$;

-- 2.6 危化品处置队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 阿坝州危化品应急救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-HZ-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 5),
        (v_team_id, 'HAZMAT_CONTAINMENT', '危化品堵漏', 5),
        (v_team_id, 'DECONTAMINATION', '洗消去污', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4);
    END IF;
    
    -- 四川省危化品应急救援队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-HZ-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 5),
        (v_team_id, 'HAZMAT_CONTAINMENT', '危化品堵漏', 5),
        (v_team_id, 'DECONTAMINATION', '洗消去污', 5),
        (v_team_id, 'CHEMICAL_FIRE', '化学火灾处置', 5),
        (v_team_id, 'RADIATION_PROTECTION', '辐射防护', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5);
    END IF;
END $$;

-- 2.7 通信保障队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 阿坝州通信保障应急队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'AB-CM-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'COMMUNICATION_SUPPORT', '通信保障', 5),
        (v_team_id, 'NETWORK_RECOVERY', '网络恢复', 5),
        (v_team_id, 'SATELLITE_COMM', '卫星通信', 4);
    END IF;
END $$;

-- 2.8 矿山救护队能力
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    -- 四川省矿山救护队
    SELECT id INTO v_team_id FROM rescue_teams_v2 WHERE code = 'SC-MR-001';
    IF v_team_id IS NOT NULL THEN
        DELETE FROM team_capabilities_v2 WHERE team_id = v_team_id;
        INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level) VALUES
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 5),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'CONFINED_SPACE_RESCUE', '密闭空间救援', 5),
        (v_team_id, 'HAZMAT_DETECTION', '危化品侦检', 4),
        (v_team_id, 'ROPE_RESCUE', '绳索救援', 5);
    END IF;
END $$;

-- ============================================================================
-- 3. 补充装备数据
-- ============================================================================

-- 补充水上救援装备
INSERT INTO equipment_v2 (code, name, category, model, manufacturer, weight_kg, applicable_scenarios, specifications) VALUES
('EQ-WR-005', '大型冲锋舟', 'water_rescue', 'AS-550', '天海', 180.0, '{flood,water_rescue}',
 '{"length_m": 5.5, "capacity_persons": 12, "motor_hp": 60, "max_speed_kmh": 45}'),
('EQ-WR-006', '充气救生艇', 'water_rescue', 'RB-420', '宏帆', 45.0, '{flood,water_rescue}',
 '{"length_m": 4.2, "capacity_persons": 8, "inflatable": true}'),
('EQ-WR-007', '水上摩托艇', 'water_rescue', 'PWC-200', '雅马哈', 280.0, '{flood,water_rescue}',
 '{"max_speed_kmh": 65, "capacity_persons": 3, "rescue_sled": true}'),
('EQ-WR-008', '潜水装备套装', 'water_rescue', 'DIVE-PRO', '水肺', 35.0, '{flood,water_rescue}',
 '{"depth_rating_m": 40, "air_capacity_min": 60, "includes": ["wetsuit","fins","mask","regulator"]}'),
('EQ-WR-009', '水下推进器', 'water_rescue', 'DPV-100', 'Seabob', 12.0, '{flood,water_rescue}',
 '{"speed_kmh": 6, "depth_m": 40, "battery_min": 60}'),
('EQ-WR-010', '抛绳器', 'water_rescue', 'THROW-50', '救生设备', 3.5, '{flood,water_rescue}',
 '{"range_m": 50, "rope_length_m": 30}'),
('EQ-WR-011', '水上担架', 'water_rescue', 'FLOAT-S', '医疗器械', 8.0, '{flood,water_rescue}',
 '{"buoyancy_kg": 200, "foldable": true}'),
('EQ-WR-012', '水下声纳探测仪', 'search_detect', 'SONAR-500', '海洋科技', 15.0, '{flood,water_rescue}',
 '{"range_m": 500, "depth_m": 100, "resolution": "high"}')
ON CONFLICT (code) DO NOTHING;

-- 补充危化品处置装备
INSERT INTO equipment_v2 (code, name, category, model, manufacturer, weight_kg, applicable_scenarios, specifications) VALUES
('EQ-HZ-001', '便携式气体检测仪', 'hazmat', 'GD-4000', '华瑞', 0.8, '{hazmat,fire}',
 '{"gases": ["CO","H2S","O2","LEL"], "alarm": true, "data_logging": true}'),
('EQ-HZ-002', '多参数水质分析仪', 'hazmat', 'WQ-500', '哈希', 2.5, '{hazmat,flood}',
 '{"parameters": ["pH","conductivity","dissolved_oxygen","turbidity"]}'),
('EQ-HZ-003', '辐射检测仪', 'hazmat', 'RAD-100', '核仪器', 1.2, '{hazmat}',
 '{"detection_types": ["alpha","beta","gamma"], "range": "0.01-9999uSv/h"}'),
('EQ-HZ-004', '重型防化服', 'protection', 'LEVEL-A-PRO', '杜邦', 4.5, '{hazmat}',
 '{"protection_level": "A", "material": "Tychem-TK", "self_contained": true}'),
('EQ-HZ-005', '洗消帐篷', 'hazmat', 'DECON-T', '应急装备', 120.0, '{hazmat}',
 '{"capacity_persons": 20, "setup_time_min": 15, "water_supply": "external"}'),
('EQ-HZ-006', '堵漏工具套装', 'hazmat', 'PLUG-KIT', '消防装备', 45.0, '{hazmat}',
 '{"includes": ["木楔","气囊","堵漏胶","捆扎带"], "pipe_diameter_range": "50-300mm"}')
ON CONFLICT (code) DO NOTHING;

-- 补充通信设备
INSERT INTO equipment_v2 (code, name, category, model, manufacturer, weight_kg, applicable_scenarios, specifications) VALUES
('EQ-CM-004', '移动通信基站', 'communication', 'BTS-100', '华为', 250.0, '{earthquake,flood}',
 '{"coverage_km": 10, "capacity_users": 500, "4g_5g": true}'),
('EQ-CM-005', '无人机通信中继', 'communication', 'RELAY-AIR', '大疆', 2.5, '{earthquake,flood,landslide}',
 '{"altitude_m": 500, "coverage_km": 5, "bandwidth_mbps": 100}'),
('EQ-CM-006', '应急广播系统', 'communication', 'PA-5000', '音响设备', 35.0, '{earthquake,flood,fire}',
 '{"power_w": 500, "coverage_m": 1000, "siren": true}')
ON CONFLICT (code) DO NOTHING;

-- 补充照明设备
INSERT INTO equipment_v2 (code, name, category, model, manufacturer, weight_kg, applicable_scenarios, specifications) VALUES
('EQ-LT-003', '气球照明灯', 'lighting', 'BALLOON-2K', '华荣', 25.0, '{earthquake,flood}',
 '{"power_w": 2000, "height_m": 6, "coverage_m2": 5000, "inflation": "helium"}'),
('EQ-LT-004', '便携式投光灯', 'lighting', 'SPOT-500', '海洋王', 8.0, '{earthquake,flood,fire}',
 '{"power_w": 500, "beam_distance_m": 500, "battery_hours": 4}')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- 4. 验证数据
-- ============================================================================

-- 输出统计
DO $$
DECLARE
    v_teams INT;
    v_capabilities INT;
    v_equipment INT;
BEGIN
    SELECT COUNT(*) INTO v_teams FROM rescue_teams_v2;
    SELECT COUNT(*) INTO v_capabilities FROM team_capabilities_v2;
    SELECT COUNT(*) INTO v_equipment FROM equipment_v2;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '救援资源数据补充完成';
    RAISE NOTICE '救援队伍总数: %', v_teams;
    RAISE NOTICE '能力配置总数: %', v_capabilities;
    RAISE NOTICE '装备类型总数: %', v_equipment;
    RAISE NOTICE '========================================';
END $$;
