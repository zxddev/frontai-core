-- ============================================================================
-- 补充水上救援队伍数据
-- 解决泥石流/洪水场景缺少WATER_RESCUE能力的问题
-- ============================================================================

-- 1. 添加茂县水上救援队（茂县本地）
INSERT INTO rescue_teams_v2 (
    name, team_type, jurisdiction, base_address,
    base_longitude, base_latitude,
    total_personnel, available_personnel,
    contact_phone, status, capability_level, max_capacity
) VALUES (
    '茂县水上救援队', 'water_rescue', '茂县',
    '四川省阿坝州茂县凤仪镇水利局',
    103.8537, 31.6815,
    25, 20,
    '0837-7422333', 'standby', 4, 50
) ON CONFLICT (name, jurisdiction) DO UPDATE SET
    status = 'standby',
    available_personnel = 20;

-- 获取刚插入的队伍ID
DO $$
DECLARE
    v_team_id UUID;
BEGIN
    SELECT id INTO v_team_id FROM rescue_teams_v2 
    WHERE name = '茂县水上救援队' AND jurisdiction = '茂县';
    
    -- 添加水上救援能力
    INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level)
    VALUES 
        (v_team_id, 'WATER_RESCUE', '水上救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 3),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 3)
    ON CONFLICT (team_id, capability_code) DO UPDATE SET
        proficiency_level = EXCLUDED.proficiency_level;
END $$;

-- 2. 添加阿坝州水上应急救援支队（州级支援）
INSERT INTO rescue_teams_v2 (
    name, team_type, jurisdiction, base_address,
    base_longitude, base_latitude,
    total_personnel, available_personnel,
    contact_phone, status, capability_level, max_capacity
) VALUES (
    '阿坝州水上应急救援支队', 'water_rescue', '阿坝州',
    '四川省阿坝州马尔康市消防救援支队',
    102.2065, 31.9057,
    60, 50,
    '0837-2822119', 'standby', 5, 120
) ON CONFLICT (name, jurisdiction) DO UPDATE SET
    status = 'standby',
    available_personnel = 50;

DO $$
DECLARE
    v_team_id UUID;
BEGIN
    SELECT id INTO v_team_id FROM rescue_teams_v2 
    WHERE name = '阿坝州水上应急救援支队' AND jurisdiction = '阿坝州';
    
    INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level)
    VALUES 
        (v_team_id, 'WATER_RESCUE', '水上救援', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 4),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 4)
    ON CONFLICT (team_id, capability_code) DO UPDATE SET
        proficiency_level = EXCLUDED.proficiency_level;
END $$;

-- 3. 添加四川省水上救援总队（省级支援）
INSERT INTO rescue_teams_v2 (
    name, team_type, jurisdiction, base_address,
    base_longitude, base_latitude,
    total_personnel, available_personnel,
    contact_phone, status, capability_level, max_capacity
) VALUES (
    '四川省水上救援总队', 'water_rescue', '四川省',
    '四川省成都市武侯区消防救援总队',
    104.0668, 30.5728,
    150, 120,
    '028-86303119', 'standby', 5, 300
) ON CONFLICT (name, jurisdiction) DO UPDATE SET
    status = 'standby',
    available_personnel = 120;

DO $$
DECLARE
    v_team_id UUID;
BEGIN
    SELECT id INTO v_team_id FROM rescue_teams_v2 
    WHERE name = '四川省水上救援总队' AND jurisdiction = '四川省';
    
    INSERT INTO team_capabilities_v2 (team_id, capability_code, capability_name, proficiency_level)
    VALUES 
        (v_team_id, 'WATER_RESCUE', '水上救援', 5),
        (v_team_id, 'STRUCTURAL_RESCUE', '结构救援', 4),
        (v_team_id, 'LIFE_DETECTION', '生命探测', 5),
        (v_team_id, 'EVACUATION_COORDINATION', '疏散协调', 5)
    ON CONFLICT (team_id, capability_code) DO UPDATE SET
        proficiency_level = EXCLUDED.proficiency_level;
END $$;

-- 验证插入结果
SELECT t.name, t.jurisdiction, t.team_type, 
       array_agg(tc.capability_code) as capabilities
FROM rescue_teams_v2 t
JOIN team_capabilities_v2 tc ON t.id = tc.team_id
WHERE tc.capability_code = 'WATER_RESCUE'
GROUP BY t.id, t.name, t.jurisdiction, t.team_type;
