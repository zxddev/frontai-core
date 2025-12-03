-- ============================================================================
-- v45_fix_capability_coverage.sql
-- 修复低覆盖能力：COMMAND_COORDINATION, BUILDING_SHORING, DEMOLITION
-- ============================================================================

-- ============================================================================
-- 一、COMMAND_COORDINATION (指挥协调) - 新增10+支队伍
-- ============================================================================

-- 1. 所有指挥中心类队伍
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 5, 100
FROM operational_v2.rescue_teams_v2 
WHERE team_type = 'command'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'COMMAND_COORDINATION'
  );

-- 2. 应急管理局相关队伍
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 80
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%应急管理局%' OR name LIKE '%应急指挥%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'COMMAND_COORDINATION'
  );

-- 3. 通信保障类队伍(具备卫星通信的)
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT t.id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 60
FROM operational_v2.rescue_teams_v2 t
JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
WHERE tc.capability_code = 'SATELLITE_COMM'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc2 
    WHERE tc2.team_id = t.id AND tc2.capability_code = 'COMMAND_COORDINATION'
  );

-- 4. 消防救援总队特勤大队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'COMMAND_COORDINATION', '指挥协调', 'command', 4, 80
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%特勤%' OR name LIKE '%总队%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'COMMAND_COORDINATION'
  );

-- ============================================================================
-- 二、BUILDING_SHORING (建筑支撑加固) - 新增8+支队伍
-- ============================================================================

-- 1. 工程类队伍(破拆、支撑、桥梁相关)
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 4, 40
FROM operational_v2.rescue_teams_v2 
WHERE (name LIKE '%破拆%' OR name LIKE '%支撑%' OR name LIKE '%桥梁%' OR name LIKE '%路桥%' OR name LIKE '%起吊%')
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'BUILDING_SHORING'
  );

-- 2. 爆破救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 4, 30
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%爆破%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'BUILDING_SHORING'
  );

-- 3. 消防特勤队伍(具备结构救援能力的)
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT DISTINCT t.id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 3, 30
FROM operational_v2.rescue_teams_v2 t
JOIN operational_v2.team_capabilities_v2 tc ON tc.team_id = t.id
WHERE t.team_type = 'fire_rescue'
  AND tc.capability_code = 'STRUCTURAL_RESCUE'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc2 
    WHERE tc2.team_id = t.id AND tc2.capability_code = 'BUILDING_SHORING'
  );

-- 4. 地震应急救援队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'BUILDING_SHORING', '建筑支撑加固', 'engineering', 4, 40
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%地震%救援%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'BUILDING_SHORING'
  );

-- ============================================================================
-- 三、DEMOLITION (破拆作业) - 新增6+支队伍
-- ============================================================================

-- 1. 破拆、爆破相关队伍
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 5, 40
FROM operational_v2.rescue_teams_v2 
WHERE (name LIKE '%破拆%' OR name LIKE '%爆破%')
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'DEMOLITION'
  );

-- 2. 隧道抢险队
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 4, 35
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%隧道%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'DEMOLITION'
  );

-- 3. 建筑支撑队、路桥队伍
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 4, 35
FROM operational_v2.rescue_teams_v2 
WHERE (name LIKE '%支撑%' OR name LIKE '%路桥%')
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'DEMOLITION'
  );

-- 4. 消防特勤队伍
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 4, 30
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%特勤%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'DEMOLITION'
  );

-- 5. 住建局抢险队(未添加的)
INSERT INTO operational_v2.team_capabilities_v2 (team_id, capability_code, capability_name, capability_category, proficiency_level, max_capacity)
SELECT id, 'DEMOLITION', '破拆作业', 'engineering', 4, 35
FROM operational_v2.rescue_teams_v2 
WHERE name LIKE '%住建%'
  AND NOT EXISTS (
    SELECT 1 FROM operational_v2.team_capabilities_v2 tc 
    WHERE tc.team_id = rescue_teams_v2.id AND tc.capability_code = 'DEMOLITION'
  );

-- ============================================================================
-- 验证结果
-- ============================================================================
SELECT capability_code, COUNT(DISTINCT team_id) as team_count
FROM operational_v2.team_capabilities_v2
WHERE capability_code IN ('COMMAND_COORDINATION', 'BUILDING_SHORING', 'DEMOLITION')
GROUP BY capability_code
ORDER BY capability_code;
