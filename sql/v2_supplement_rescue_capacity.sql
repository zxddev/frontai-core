-- ============================================================================
-- 补充救援队伍救援容量数据
-- 
-- 为team_capabilities_v2表补充max_capacity字段，用于计算救援容量
-- 救援容量 = 72小时内该能力可处理的最大人数
-- ============================================================================

-- 消防救援队伍的救援能力
UPDATE operational_v2.team_capabilities_v2 tc
SET max_capacity = CASE
    WHEN tc.capability_code = 'STRUCTURAL_RESCUE' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 2
    WHEN tc.capability_code = 'LIFE_DETECTION' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 3
    WHEN tc.capability_code = 'FIRE_SUPPRESS' THEN 1  -- 灭火能力不直接救人
    ELSE tc.max_capacity
END
WHERE tc.capability_code IN ('STRUCTURAL_RESCUE', 'LIFE_DETECTION', 'FIRE_SUPPRESS')
  AND tc.max_capacity IS NULL OR tc.max_capacity = 0;

-- 医疗队伍的救援能力
UPDATE operational_v2.team_capabilities_v2 tc
SET max_capacity = CASE
    WHEN tc.capability_code = 'MEDICAL_TRIAGE' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 10
    WHEN tc.capability_code = 'EMERGENCY_TREATMENT' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 5
    WHEN tc.capability_code = 'MEDICAL_FIRST_AID' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 8
    ELSE tc.max_capacity
END
WHERE tc.capability_code IN ('MEDICAL_TRIAGE', 'EMERGENCY_TREATMENT', 'MEDICAL_FIRST_AID')
  AND tc.max_capacity IS NULL OR tc.max_capacity = 0;

-- 搜救队伍的救援能力
UPDATE operational_v2.team_capabilities_v2 tc
SET max_capacity = CASE
    WHEN tc.capability_code = 'SEARCH_LIFE_DETECT' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 3
    WHEN tc.capability_code = 'RESCUE_STRUCTURAL' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 2
    WHEN tc.capability_code = 'RESCUE_CONFINED' THEN 
        COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 1
    ELSE tc.max_capacity
END
WHERE tc.capability_code IN ('SEARCH_LIFE_DETECT', 'RESCUE_STRUCTURAL', 'RESCUE_CONFINED')
  AND tc.max_capacity IS NULL OR tc.max_capacity = 0;

-- 疏散协调能力
UPDATE operational_v2.team_capabilities_v2 tc
SET max_capacity = COALESCE((SELECT t.available_personnel FROM operational_v2.rescue_teams_v2 t WHERE t.id = tc.team_id), 0) * 20
WHERE tc.capability_code = 'EVACUATION_COORDINATION'
  AND tc.max_capacity IS NULL OR tc.max_capacity = 0;

-- 道路抢通能力（不直接救人，但影响其他队伍到达）
UPDATE operational_v2.team_capabilities_v2 tc
SET max_capacity = 0  -- 工程能力不直接救人
WHERE tc.capability_code = 'ROAD_CLEARANCE'
  AND tc.max_capacity IS NULL;

-- 输出统计信息
DO $$
DECLARE
    v_total INT;
    v_with_capacity INT;
BEGIN
    SELECT COUNT(*) INTO v_total FROM operational_v2.team_capabilities_v2;
    SELECT COUNT(*) INTO v_with_capacity FROM operational_v2.team_capabilities_v2 WHERE max_capacity > 0;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE '救援容量数据补充完成';
    RAISE NOTICE '能力记录总数: %', v_total;
    RAISE NOTICE '有救援容量记录数: %', v_with_capacity;
    RAISE NOTICE '========================================';
END $$;

-- 查询验证
SELECT 
    t.name AS team_name,
    t.team_type,
    t.available_personnel,
    tc.capability_code,
    tc.capability_name,
    tc.max_capacity
FROM operational_v2.rescue_teams_v2 t
JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
ORDER BY t.name, tc.capability_code;
