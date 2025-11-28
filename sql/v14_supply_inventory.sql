-- ============================================================================
-- V14 物资库存管理体系 (v14_supply_inventory.sql)
-- 
-- 功能: 建立完整的物资库存管理体系，支持：
--   1. 物资存放点管理（仓库/队伍基地/车辆/前线临时点）
--   2. 物资库存追踪（数量/预留量/安全库存）
--   3. 物资调拨流程（申请/审批/在途/完成）
--
-- 业务场景:
--   - equipment_preparation: 出发前从仓库选择物资
--   - emergency_ai: 前线统一调度所有可用物资
-- ============================================================================

SET search_path TO operational_v2, public;

-- ============================================================================
-- 1. 创建枚举类型
-- ============================================================================

-- 存放点类型
DO $$ BEGIN
    CREATE TYPE operational_v2.depot_type_v2 AS ENUM (
        'warehouse',      -- 中央物资仓库
        'team_base',      -- 救援队伍基地
        'vehicle',        -- 车辆（指挥车/运输车）
        'field_depot'     -- 前线临时存放点
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 存放点归属类型
DO $$ BEGIN
    CREATE TYPE operational_v2.depot_owner_type_v2 AS ENUM (
        'organization',   -- 独立机构（如应急管理局）
        'rescue_team',    -- 救援队伍
        'vehicle'         -- 车辆
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 调拨状态
DO $$ BEGIN
    CREATE TYPE operational_v2.transfer_status_v2 AS ENUM (
        'pending',        -- 待审批
        'approved',       -- 已审批
        'in_transit',     -- 在途
        'completed',      -- 已完成
        'cancelled'       -- 已取消
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 2. 创建物资存放点表 (supply_depots_v2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.supply_depots_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基本信息
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    depot_type operational_v2.depot_type_v2 NOT NULL,
    
    -- 位置
    location GEOGRAPHY(Point, 4326),
    address VARCHAR(500),
    
    -- 归属关系
    owner_type operational_v2.depot_owner_type_v2,
    owner_id UUID,  -- 关联 rescue_teams_v2.id 或 vehicles_v2.id
    
    -- 想定关联（field_depot 专用）
    scenario_id UUID,
    
    -- 联系方式
    contact_person VARCHAR(100),
    contact_phone VARCHAR(20),
    
    -- 状态
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- 扩展属性
    properties JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_supply_depots_type 
    ON operational_v2.supply_depots_v2(depot_type);
CREATE INDEX IF NOT EXISTS idx_supply_depots_owner 
    ON operational_v2.supply_depots_v2(owner_type, owner_id);
CREATE INDEX IF NOT EXISTS idx_supply_depots_scenario 
    ON operational_v2.supply_depots_v2(scenario_id) WHERE scenario_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_supply_depots_active 
    ON operational_v2.supply_depots_v2(is_active) WHERE is_active = true;

-- 注释
COMMENT ON TABLE operational_v2.supply_depots_v2 
    IS '物资存放点表 - 记录仓库、队伍基地、车辆、前线临时点等物资存放位置';
COMMENT ON COLUMN operational_v2.supply_depots_v2.depot_type 
    IS '存放点类型: warehouse=仓库, team_base=队伍基地, vehicle=车辆, field_depot=前线临时点';
COMMENT ON COLUMN operational_v2.supply_depots_v2.owner_id 
    IS '归属ID: team_base关联rescue_teams_v2, vehicle关联vehicles_v2';

-- ============================================================================
-- 3. 创建物资库存表 (supply_inventory_v2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.supply_inventory_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    depot_id UUID NOT NULL REFERENCES operational_v2.supply_depots_v2(id) ON DELETE CASCADE,
    supply_id UUID NOT NULL REFERENCES operational_v2.supplies_v2(id) ON DELETE RESTRICT,
    
    -- 库存量
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
    
    -- 安全库存
    min_stock INTEGER DEFAULT 0,
    
    -- 批次信息
    batch_no VARCHAR(50),
    expiry_date DATE,
    
    -- 单位（冗余，方便查询）
    unit VARCHAR(20) DEFAULT 'piece',
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 约束：预留量不能超过总量
    CONSTRAINT chk_reserved_lte_quantity CHECK (reserved_quantity <= quantity)
);

-- 唯一索引：同一存放点+物资+批次 唯一
CREATE UNIQUE INDEX IF NOT EXISTS idx_supply_inventory_unique 
    ON operational_v2.supply_inventory_v2(depot_id, supply_id, COALESCE(batch_no, ''));

-- 其他索引
CREATE INDEX IF NOT EXISTS idx_supply_inventory_depot 
    ON operational_v2.supply_inventory_v2(depot_id);
CREATE INDEX IF NOT EXISTS idx_supply_inventory_supply 
    ON operational_v2.supply_inventory_v2(supply_id);
CREATE INDEX IF NOT EXISTS idx_supply_inventory_expiry 
    ON operational_v2.supply_inventory_v2(expiry_date) WHERE expiry_date IS NOT NULL;

-- 注释
COMMENT ON TABLE operational_v2.supply_inventory_v2 
    IS '物资库存表 - 记录每个存放点的物资库存量';
COMMENT ON COLUMN operational_v2.supply_inventory_v2.quantity 
    IS '库存总量';
COMMENT ON COLUMN operational_v2.supply_inventory_v2.reserved_quantity 
    IS '已预留量（调拨申请中但未出库）';
COMMENT ON COLUMN operational_v2.supply_inventory_v2.min_stock 
    IS '安全库存量，低于此值触发告警';

-- ============================================================================
-- 4. 创建物资调拨表 (supply_transfers_v2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.supply_transfers_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 调拨单号
    transfer_code VARCHAR(50) NOT NULL UNIQUE,
    
    -- 调拨路径
    from_depot_id UUID NOT NULL REFERENCES operational_v2.supply_depots_v2(id),
    to_depot_id UUID NOT NULL REFERENCES operational_v2.supply_depots_v2(id),
    
    -- 关联业务
    scenario_id UUID,
    event_id UUID,
    
    -- 状态
    status operational_v2.transfer_status_v2 NOT NULL DEFAULT 'pending',
    
    -- 审批流程
    requested_by UUID,
    approved_by UUID,
    
    -- 时间节点
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    shipped_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    
    -- 备注
    note TEXT,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- 约束：源和目标不能相同
    CONSTRAINT chk_different_depots CHECK (from_depot_id != to_depot_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_supply_transfers_status 
    ON operational_v2.supply_transfers_v2(status);
CREATE INDEX IF NOT EXISTS idx_supply_transfers_from 
    ON operational_v2.supply_transfers_v2(from_depot_id);
CREATE INDEX IF NOT EXISTS idx_supply_transfers_to 
    ON operational_v2.supply_transfers_v2(to_depot_id);
CREATE INDEX IF NOT EXISTS idx_supply_transfers_scenario 
    ON operational_v2.supply_transfers_v2(scenario_id) WHERE scenario_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_supply_transfers_event 
    ON operational_v2.supply_transfers_v2(event_id) WHERE event_id IS NOT NULL;

-- 注释
COMMENT ON TABLE operational_v2.supply_transfers_v2 
    IS '物资调拨表 - 记录物资从一个存放点到另一个存放点的调拨过程';

-- ============================================================================
-- 5. 创建调拨明细表 (supply_transfer_items_v2)
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.supply_transfer_items_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    transfer_id UUID NOT NULL REFERENCES operational_v2.supply_transfers_v2(id) ON DELETE CASCADE,
    supply_id UUID NOT NULL REFERENCES operational_v2.supplies_v2(id),
    
    -- 数量
    requested_quantity INTEGER NOT NULL CHECK (requested_quantity > 0),
    approved_quantity INTEGER DEFAULT 0,
    actual_quantity INTEGER DEFAULT 0,
    
    -- 单位
    unit VARCHAR(20) DEFAULT 'piece',
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_transfer_items_transfer 
    ON operational_v2.supply_transfer_items_v2(transfer_id);
CREATE INDEX IF NOT EXISTS idx_transfer_items_supply 
    ON operational_v2.supply_transfer_items_v2(supply_id);

-- 注释
COMMENT ON TABLE operational_v2.supply_transfer_items_v2 
    IS '调拨明细表 - 记录每次调拨的物资清单和数量';

-- ============================================================================
-- 6. 创建触发器 - 自动更新时间戳
-- ============================================================================

-- supply_depots_v2
DROP TRIGGER IF EXISTS tr_supply_depots_updated ON operational_v2.supply_depots_v2;
CREATE TRIGGER tr_supply_depots_updated
    BEFORE UPDATE ON operational_v2.supply_depots_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- supply_inventory_v2
DROP TRIGGER IF EXISTS tr_supply_inventory_updated ON operational_v2.supply_inventory_v2;
CREATE TRIGGER tr_supply_inventory_updated
    BEFORE UPDATE ON operational_v2.supply_inventory_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- supply_transfers_v2
DROP TRIGGER IF EXISTS tr_supply_transfers_updated ON operational_v2.supply_transfers_v2;
CREATE TRIGGER tr_supply_transfers_updated
    BEFORE UPDATE ON operational_v2.supply_transfers_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.update_timestamp();

-- ============================================================================
-- 7. 创建视图 - 可用库存汇总
-- ============================================================================

CREATE OR REPLACE VIEW operational_v2.v_supply_available_inventory AS
SELECT 
    si.id AS inventory_id,
    sd.id AS depot_id,
    sd.code AS depot_code,
    sd.name AS depot_name,
    sd.depot_type,
    sd.owner_type,
    sd.owner_id,
    sd.scenario_id,
    s.id AS supply_id,
    s.code AS supply_code,
    s.name AS supply_name,
    s.category,
    si.quantity,
    si.reserved_quantity,
    (si.quantity - si.reserved_quantity) AS available_quantity,
    si.min_stock,
    si.unit,
    si.batch_no,
    si.expiry_date,
    CASE 
        WHEN si.expiry_date IS NOT NULL AND si.expiry_date < CURRENT_DATE THEN true
        ELSE false
    END AS is_expired,
    CASE 
        WHEN si.min_stock > 0 AND (si.quantity - si.reserved_quantity) < si.min_stock THEN true
        ELSE false
    END AS is_low_stock,
    ST_Y(sd.location::geometry) AS latitude,
    ST_X(sd.location::geometry) AS longitude
FROM operational_v2.supply_inventory_v2 si
JOIN operational_v2.supply_depots_v2 sd ON sd.id = si.depot_id
JOIN operational_v2.supplies_v2 s ON s.id = si.supply_id
WHERE sd.is_active = true
  AND si.quantity > 0;

COMMENT ON VIEW operational_v2.v_supply_available_inventory 
    IS '可用库存汇总视图 - 包含库存量、可用量、过期/缺货告警';

-- ============================================================================
-- 8. 创建函数 - 生成调拨单号
-- ============================================================================

CREATE OR REPLACE FUNCTION operational_v2.generate_transfer_code()
RETURNS VARCHAR(50) AS $$
DECLARE
    today_str VARCHAR(8);
    seq_num INTEGER;
    new_code VARCHAR(50);
BEGIN
    today_str := TO_CHAR(CURRENT_DATE, 'YYYYMMDD');
    
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(transfer_code FROM 13 FOR 4) AS INTEGER)
    ), 0) + 1 INTO seq_num
    FROM operational_v2.supply_transfers_v2
    WHERE transfer_code LIKE 'TR-' || today_str || '-%';
    
    new_code := 'TR-' || today_str || '-' || LPAD(seq_num::VARCHAR, 4, '0');
    RETURN new_code;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 9. 初始化测试数据 - 创建默认仓库
-- ============================================================================

-- 插入一个默认中央仓库
INSERT INTO operational_v2.supply_depots_v2 (
    code, name, depot_type, 
    location, address,
    owner_type, 
    contact_person, contact_phone,
    is_active
) VALUES (
    'WH-CENTRAL-001',
    '应急物资中央仓库',
    'warehouse',
    ST_SetSRID(ST_MakePoint(103.0, 30.5), 4326)::geography,
    '四川省成都市应急管理局物资储备中心',
    'organization',
    '张主任',
    '028-12345678',
    true
) ON CONFLICT (code) DO NOTHING;

-- 为现有物资创建初始库存（中央仓库）
INSERT INTO operational_v2.supply_inventory_v2 (
    depot_id, supply_id, quantity, reserved_quantity, min_stock, unit
)
SELECT 
    (SELECT id FROM operational_v2.supply_depots_v2 WHERE code = 'WH-CENTRAL-001'),
    s.id,
    100,  -- 初始库存100
    0,    -- 无预留
    10,   -- 安全库存10
    COALESCE(s.unit, 'piece')
FROM operational_v2.supplies_v2 s
WHERE NOT EXISTS (
    SELECT 1 FROM operational_v2.supply_inventory_v2 si 
    WHERE si.supply_id = s.id 
    AND si.depot_id = (SELECT id FROM operational_v2.supply_depots_v2 WHERE code = 'WH-CENTRAL-001')
);

-- ============================================================================
-- 10. 更新 supplies_v2 的 properties 字段（添加需求计算参数）
-- ============================================================================

-- 为医疗类物资设置人均每天消耗量
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 0.1, "min_stock_per_team": 5}'::jsonb
WHERE category = 'medical' AND (properties->>'per_person_per_day') IS NULL;

-- 为防护类物资设置
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 1.0, "min_stock_per_team": 10}'::jsonb
WHERE category = 'protection' AND (properties->>'per_person_per_day') IS NULL;

-- 为救援类物资设置
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 0.05, "min_stock_per_team": 2}'::jsonb
WHERE category = 'rescue' AND (properties->>'per_person_per_day') IS NULL;

-- 为生活类物资设置
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 2.0, "min_stock_per_team": 20}'::jsonb
WHERE category = 'life' AND (properties->>'per_person_per_day') IS NULL;

-- 为通信类物资设置
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 0.02, "min_stock_per_team": 2}'::jsonb
WHERE category = 'communication' AND (properties->>'per_person_per_day') IS NULL;

-- 为工具类物资设置
UPDATE operational_v2.supplies_v2 
SET properties = properties || '{"per_person_per_day": 0.01, "min_stock_per_team": 3}'::jsonb
WHERE category = 'tool' AND (properties->>'per_person_per_day') IS NULL;

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'V14 Supply Inventory migration completed!' AS result;
