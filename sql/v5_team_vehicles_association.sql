-- ============================================================================
-- 队伍-车辆关联表创建与数据初始化
-- 
-- 问题背景：
--   db_route_engine.py的get_team_primary_vehicle函数预期查询team_vehicles_v2表
--   但该表在数据库中不存在，导致无法获取队伍的车辆参数计算真实ETA
--
-- 解决方案：
--   1. 创建team_vehicles_v2表
--   2. 按队伍类型分配合适的车辆
--   3. 每个队伍至少有一辆主力车辆(is_primary=true)
--
-- 车辆分配原则：
--   - fire_rescue: VH-001(侦察车,全地形) 或 VH-006(指挥车,全地形)
--   - medical: VH-005(医疗车)
--   - search_rescue: VH-003(无人机车,全地形)
--   - hazmat: VH-002(保障车)
--   - engineering: VH-002(保障车)
--   - communication: VH-002(保障车)
--   - water_rescue: VH-004(无人艇车)
--   - mine_rescue: VH-001(侦察车,全地形)
--   - armed_police: VH-006(指挥车,全地形)
--   - volunteer: VH-002(保障车)
-- ============================================================================

-- 1. 创建team_vehicles_v2表
CREATE TABLE IF NOT EXISTS operational_v2.team_vehicles_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    vehicle_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    
    is_primary BOOLEAN DEFAULT false,
    assignment_type VARCHAR(20) DEFAULT 'permanent',
    status VARCHAR(20) DEFAULT 'available',
    
    assigned_at TIMESTAMPTZ DEFAULT now(),
    unassigned_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(team_id, vehicle_id)
);

CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_team ON operational_v2.team_vehicles_v2(team_id);
CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_vehicle ON operational_v2.team_vehicles_v2(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_status ON operational_v2.team_vehicles_v2(status);

COMMENT ON TABLE operational_v2.team_vehicles_v2 IS '队伍车辆关联表';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.is_primary IS '是否主力车辆（ETA计算使用主力车辆参数）';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.status IS '状态: available可用/deployed已出动/maintenance维护中';

-- 2. 清理旧数据（如果有）
TRUNCATE operational_v2.team_vehicles_v2;

-- 3. 为消防队伍分配车辆（VH-001侦察车或VH-006指挥车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'fire_rescue'
  AND v.code = 'VH-001'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 省级/州级消防队加配指挥车作为备用
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, false, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'fire_rescue'
  AND (t.code LIKE 'SC-%' OR t.code LIKE 'AB-%')
  AND v.code = 'VH-006'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 4. 为医疗队伍分配车辆（VH-005医疗车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'medical'
  AND v.code = 'VH-005'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 5. 为搜救队伍分配车辆（VH-003无人机车，全地形）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'search_rescue'
  AND v.code = 'VH-003'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 6. 为危化品队伍分配车辆（VH-002保障车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'hazmat'
  AND v.code = 'VH-002'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 7. 为工程队伍分配车辆（VH-002保障车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'engineering'
  AND v.code = 'VH-002'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 8. 为通信队伍分配车辆（VH-002保障车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'communication'
  AND v.code = 'VH-002'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 9. 为水上救援队伍分配车辆（VH-004无人艇车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'water_rescue'
  AND v.code = 'VH-004'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 10. 为矿山救护队伍分配车辆（VH-001侦察车，全地形适合矿山）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'mine_rescue'
  AND v.code = 'VH-001'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 11. 为武警队伍分配车辆（VH-006指挥车，全地形高速）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'armed_police'
  AND v.code = 'VH-006'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- 12. 为志愿者队伍分配车辆（VH-002保障车）
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t
CROSS JOIN operational_v2.vehicles_v2 v
WHERE t.team_type = 'volunteer'
  AND v.code = 'VH-002'
ON CONFLICT (team_id, vehicle_id) DO UPDATE SET is_primary = true;

-- ============================================================================
-- 验证结果
-- ============================================================================

-- 统计每个队伍类型的车辆分配情况
SELECT 
    t.team_type,
    COUNT(DISTINCT t.id) as team_count,
    COUNT(tv.id) as vehicle_assignments,
    COUNT(CASE WHEN tv.is_primary THEN 1 END) as primary_vehicles
FROM operational_v2.rescue_teams_v2 t
LEFT JOIN operational_v2.team_vehicles_v2 tv ON tv.team_id = t.id
GROUP BY t.team_type
ORDER BY t.team_type;

-- 显示详细的队伍-车辆关联
SELECT 
    t.code as team_code,
    t.name as team_name,
    t.team_type,
    v.code as vehicle_code,
    v.name as vehicle_name,
    v.max_speed_kmh,
    v.is_all_terrain,
    tv.is_primary
FROM operational_v2.team_vehicles_v2 tv
JOIN operational_v2.rescue_teams_v2 t ON tv.team_id = t.id
JOIN operational_v2.vehicles_v2 v ON tv.vehicle_id = v.id
ORDER BY t.team_type, t.code;

-- 检查是否有未分配车辆的队伍
SELECT t.code, t.name, t.team_type
FROM operational_v2.rescue_teams_v2 t
LEFT JOIN operational_v2.team_vehicles_v2 tv ON tv.team_id = t.id
WHERE tv.id IS NULL;
