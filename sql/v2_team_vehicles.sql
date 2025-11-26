-- ============================================================================
-- 队伍-车辆关联表
-- 建立救援队伍与车辆的多对多关系
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.team_vehicles_v2 (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 关联关系
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    vehicle_id UUID NOT NULL REFERENCES operational_v2.vehicles_v2(id) ON DELETE CASCADE,
    
    -- 分配信息
    is_primary BOOLEAN DEFAULT false,              -- 是否主力车辆
    assignment_type VARCHAR(20) DEFAULT 'permanent', -- permanent永久/temporary临时
    
    -- 状态
    status VARCHAR(20) DEFAULT 'available',        -- available可用/deployed出动/maintenance维护
    
    -- 时间记录
    assigned_at TIMESTAMPTZ DEFAULT now(),
    unassigned_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(team_id, vehicle_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_team ON operational_v2.team_vehicles_v2(team_id);
CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_vehicle ON operational_v2.team_vehicles_v2(vehicle_id);
CREATE INDEX IF NOT EXISTS idx_team_vehicles_v2_status ON operational_v2.team_vehicles_v2(status);

-- 注释
COMMENT ON TABLE operational_v2.team_vehicles_v2 IS '队伍车辆关联表 - 记录队伍拥有或分配的车辆';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.id IS '记录唯一标识符';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.team_id IS '队伍ID';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.vehicle_id IS '车辆ID';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.is_primary IS '是否主力车辆（优先调度）';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.assignment_type IS '分配类型: permanent永久分配/temporary临时调配';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.status IS '状态: available可用/deployed已出动/maintenance维护中';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.assigned_at IS '分配时间';
COMMENT ON COLUMN operational_v2.team_vehicles_v2.unassigned_at IS '取消分配时间';

-- ============================================================================
-- 插入测试数据：为队伍分配车辆
-- ============================================================================

-- 茂县消防救援大队 - 分配前突侦察控制车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-FR-001' AND v.code = 'VH-001'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 茂县消防救援大队 - 分配综合保障车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, false, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-FR-001' AND v.code = 'VH-002'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 汶川消防救援大队 - 分配无人机输送车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-FR-002' AND v.code = 'VH-003'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 成都特勤消防救援站 - 分配全地形越野指挥车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-FR-003' AND v.code = 'VH-006'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 茂县人民医院急救队 - 分配医疗救援车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-MD-001' AND v.code = 'VH-005'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 都江堰水上救援队 - 分配无人艇输送车
INSERT INTO operational_v2.team_vehicles_v2 (team_id, vehicle_id, is_primary, assignment_type)
SELECT t.id, v.id, true, 'permanent'
FROM operational_v2.rescue_teams_v2 t, operational_v2.vehicles_v2 v
WHERE t.code = 'RT-WR-001' AND v.code = 'VH-004'
ON CONFLICT (team_id, vehicle_id) DO NOTHING;

-- 验证
SELECT 
    t.code as team_code, 
    t.name as team_name,
    v.code as vehicle_code,
    v.name as vehicle_name,
    tv.is_primary
FROM operational_v2.team_vehicles_v2 tv
JOIN operational_v2.rescue_teams_v2 t ON tv.team_id = t.id
JOIN operational_v2.vehicles_v2 v ON tv.vehicle_id = v.id
ORDER BY t.code;
