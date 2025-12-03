-- ============================================================================
-- v47_expand_team_capabilities.sql
-- 扩展队伍能力，提高任务-资源匹配覆盖率
-- ============================================================================

-- 1. 为消防队(fire_rescue)增加更多能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'advanced', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('ROAD_CLEARANCE'),
    ('COMMUNICATION_SUPPORT')
) AS cap(code)
WHERE t.team_type = 'fire_rescue'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 2. 为搜救队(search_rescue)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'intermediate', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('DEMOLITION'),
    ('HAZMAT_DETECTION')
) AS cap(code)
WHERE t.team_type = 'search_rescue'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 3. 为工程队(engineering)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'advanced', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('FIRE_SUPPRESSION'),
    ('HAZMAT_CONTAINMENT')
) AS cap(code)
WHERE t.team_type = 'engineering'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 4. 为医疗队(medical)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'intermediate', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('EVACUATION_COORDINATION'),
    ('COMMUNICATION_SUPPORT')
) AS cap(code)
WHERE t.team_type = 'medical'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 5. 为指挥中心(command)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'expert', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('HAZMAT_DETECTION'),
    ('LIFE_DETECTION')
) AS cap(code)
WHERE t.team_type = 'command'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 6. 为通信队(communication)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'advanced', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('EVACUATION_COORDINATION'),
    ('HAZMAT_DETECTION')
) AS cap(code)
WHERE t.team_type = 'communication'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 7. 为危化品队(hazmat)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'advanced', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('COMMUNICATION_SUPPORT'),
    ('STRUCTURAL_RESCUE')
) AS cap(code)
WHERE t.team_type = 'hazmat'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 8. 为志愿者队伍(volunteer)增加能力
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, proficiency_level, certification_date)
SELECT t.id, cap.code, 'basic', NOW()
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN (VALUES 
    ('COMMUNICATION_SUPPORT'),
    ('PATIENT_TRANSPORT')
) AS cap(code)
WHERE t.team_type = 'volunteer'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 c 
    WHERE c.team_id = t.id AND c.capability_code = cap.code
  );

-- 输出统计
DO $$
DECLARE
    total_caps INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_caps FROM operational_v2.team_capabilities_v2;
    RAISE NOTICE 'v47: 队伍能力扩展完成，当前总能力记录数: %', total_caps;
END $$;
