-- ============================================================================
-- 队伍资源关联表 V19
-- 
-- 业务背景:
--   当指挥员下达出发指令后，车辆通过 mobilize 接口转换为救援队伍。
--   本文件创建的关联表用于记录救援队伍在本次想定中携带的设备、物资、模块。
--   数据来源于 car_item_assignment 表中指挥员选定的装备清单。
--
-- 数据流向:
--   1. AI智能体推荐装备 → equipment_recommendations_v2.loading_plan
--   2. 指挥员调整选择 → car_item_assignment (is_selected)
--   3. 出发动员(mobilize) → 本文件创建的关联表 (team_devices_v2等)
--   4. 救援队伍执行任务时可查询携带的完整资源
--
-- 关联关系:
--   rescue_teams_v2 (队伍) ←→ vehicles_v2 (车辆) [通过 team_vehicles_v2]
--   rescue_teams_v2 (队伍) ←→ devices_v2 (设备) [通过 team_devices_v2]
--   rescue_teams_v2 (队伍) ←→ supplies_v2 (物资) [通过 team_supplies_v2]
--   rescue_teams_v2 (队伍) ←→ modules_v2 (模块) [通过 team_modules_v2]
-- ============================================================================

-- ============================================================================
-- 1. 队伍-设备关联表 (team_devices_v2)
--    记录救援队伍携带的智能设备（无人机、机器人、探测器等）
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.team_devices_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    device_id UUID NOT NULL REFERENCES operational_v2.devices_v2(id) ON DELETE CASCADE,
    quantity INT DEFAULT 1,
    status VARCHAR(20) DEFAULT 'ready',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_team_devices_v2_team ON operational_v2.team_devices_v2(team_id);
CREATE INDEX IF NOT EXISTS idx_team_devices_v2_device ON operational_v2.team_devices_v2(device_id);

COMMENT ON TABLE operational_v2.team_devices_v2 IS '队伍-设备关联表：记录救援队伍在本次想定中携带的智能设备（无人机、机器人、探测器等）';
COMMENT ON COLUMN operational_v2.team_devices_v2.id IS '主键ID';
COMMENT ON COLUMN operational_v2.team_devices_v2.team_id IS '所属救援队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_devices_v2.device_id IS '携带的设备ID，关联devices_v2表';
COMMENT ON COLUMN operational_v2.team_devices_v2.quantity IS '携带数量，默认1台';
COMMENT ON COLUMN operational_v2.team_devices_v2.status IS '设备状态：ready(就绪可用)/in_use(使用中)/damaged(损坏)';
COMMENT ON COLUMN operational_v2.team_devices_v2.created_at IS '记录创建时间（动员时写入）';
COMMENT ON COLUMN operational_v2.team_devices_v2.updated_at IS '记录更新时间';

-- ============================================================================
-- 2. 队伍-物资关联表 (team_supplies_v2)
--    记录救援队伍携带的消耗性物资（药品、食品、工具等）
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.team_supplies_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    supply_id UUID NOT NULL REFERENCES operational_v2.supplies_v2(id) ON DELETE CASCADE,
    quantity INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, supply_id)
);

CREATE INDEX IF NOT EXISTS idx_team_supplies_v2_team ON operational_v2.team_supplies_v2(team_id);
CREATE INDEX IF NOT EXISTS idx_team_supplies_v2_supply ON operational_v2.team_supplies_v2(supply_id);

COMMENT ON TABLE operational_v2.team_supplies_v2 IS '队伍-物资关联表：记录救援队伍在本次想定中携带的消耗性物资（药品、食品、工具等）';
COMMENT ON COLUMN operational_v2.team_supplies_v2.id IS '主键ID';
COMMENT ON COLUMN operational_v2.team_supplies_v2.team_id IS '所属救援队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_supplies_v2.supply_id IS '携带的物资ID，关联supplies_v2表';
COMMENT ON COLUMN operational_v2.team_supplies_v2.quantity IS '携带数量（件/箱/套等，单位由物资定义）';
COMMENT ON COLUMN operational_v2.team_supplies_v2.created_at IS '记录创建时间（动员时写入）';
COMMENT ON COLUMN operational_v2.team_supplies_v2.updated_at IS '记录更新时间';

-- ============================================================================
-- 3. 队伍-模块关联表 (team_modules_v2)
--    记录救援队伍携带的功能模块及其安装的设备
--    模块是可插拔的功能单元，需要安装在设备上才能工作
-- ============================================================================
CREATE TABLE IF NOT EXISTS operational_v2.team_modules_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id UUID NOT NULL REFERENCES operational_v2.rescue_teams_v2(id) ON DELETE CASCADE,
    module_id UUID NOT NULL REFERENCES operational_v2.modules_v2(id) ON DELETE CASCADE,
    device_id UUID REFERENCES operational_v2.devices_v2(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(team_id, module_id)
);

CREATE INDEX IF NOT EXISTS idx_team_modules_v2_team ON operational_v2.team_modules_v2(team_id);
CREATE INDEX IF NOT EXISTS idx_team_modules_v2_module ON operational_v2.team_modules_v2(module_id);
CREATE INDEX IF NOT EXISTS idx_team_modules_v2_device ON operational_v2.team_modules_v2(device_id);

COMMENT ON TABLE operational_v2.team_modules_v2 IS '队伍-模块关联表：记录救援队伍携带的功能模块（如热成像模块、喊话模块等）及其安装的设备';
COMMENT ON COLUMN operational_v2.team_modules_v2.id IS '主键ID';
COMMENT ON COLUMN operational_v2.team_modules_v2.team_id IS '所属救援队伍ID，关联rescue_teams_v2表';
COMMENT ON COLUMN operational_v2.team_modules_v2.module_id IS '携带的模块ID，关联modules_v2表';
COMMENT ON COLUMN operational_v2.team_modules_v2.device_id IS '模块安装的设备ID，关联devices_v2表（模块必须安装在设备上才能工作）';
COMMENT ON COLUMN operational_v2.team_modules_v2.created_at IS '记录创建时间（动员时写入）';
COMMENT ON COLUMN operational_v2.team_modules_v2.updated_at IS '记录更新时间';

-- ============================================================================
-- 视图：队伍完整资源汇总
-- ============================================================================
CREATE OR REPLACE VIEW operational_v2.v_team_resources_summary AS
SELECT 
    t.id AS team_id,
    t.code AS team_code,
    t.name AS team_name,
    t.status AS team_status,
    -- 车辆
    COALESCE(
        (SELECT json_agg(json_build_object(
            'vehicle_id', v.id,
            'vehicle_name', v.name,
            'vehicle_type', v.vehicle_type,
            'is_primary', tv.is_primary
        ))
        FROM operational_v2.team_vehicles_v2 tv
        JOIN operational_v2.vehicles_v2 v ON tv.vehicle_id = v.id
        WHERE tv.team_id = t.id),
        '[]'::json
    ) AS vehicles,
    -- 设备
    COALESCE(
        (SELECT json_agg(json_build_object(
            'device_id', d.id,
            'device_name', d.name,
            'device_type', d.device_type,
            'quantity', td.quantity
        ))
        FROM operational_v2.team_devices_v2 td
        JOIN operational_v2.devices_v2 d ON td.device_id = d.id
        WHERE td.team_id = t.id),
        '[]'::json
    ) AS devices,
    -- 物资
    COALESCE(
        (SELECT json_agg(json_build_object(
            'supply_id', s.id,
            'supply_name', s.name,
            'category', s.category,
            'quantity', ts.quantity
        ))
        FROM operational_v2.team_supplies_v2 ts
        JOIN operational_v2.supplies_v2 s ON ts.supply_id = s.id
        WHERE ts.team_id = t.id),
        '[]'::json
    ) AS supplies,
    -- 模块
    COALESCE(
        (SELECT json_agg(json_build_object(
            'module_id', m.id,
            'module_name', m.name,
            'installed_on_device_id', tm.device_id
        ))
        FROM operational_v2.team_modules_v2 tm
        JOIN operational_v2.modules_v2 m ON tm.module_id = m.id
        WHERE tm.team_id = t.id),
        '[]'::json
    ) AS modules
FROM operational_v2.rescue_teams_v2 t;

COMMENT ON VIEW operational_v2.v_team_resources_summary IS '队伍完整资源汇总视图，包含车辆、设备、物资、模块';
