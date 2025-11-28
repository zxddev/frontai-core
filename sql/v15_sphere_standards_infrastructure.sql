-- ============================================================================
-- V15 Sphere 人道主义标准基础设施 (v15_sphere_standards_infrastructure.sql)
-- 
-- 功能: 为符合 WHO/Sphere 人道主义标准的物资管理系统提供数据库支持
--   1. 响应阶段枚举 (immediate/short_term/recovery)
--   2. 物资状态枚举 (serviceable/damaged/expired/destroyed/quarantined)
--   3. 库存审计表 (变更追踪)
--   4. 乐观锁支持 (version字段)
--   5. 气候类型枚举 (tropical/temperate/cold/arid)
--
-- 参考标准:
--   - Sphere Handbook 2018 Edition
--   - WHO Technical Notes on Drinking-Water, Sanitation and Hygiene in Emergencies
--   - USGS PAGER methodology for casualty estimation
-- ============================================================================

SET search_path TO operational_v2, public;

-- ============================================================================
-- 1. 创建响应阶段枚举
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE operational_v2.response_phase_v2 AS ENUM (
        'immediate',    -- 0-72小时: 搜救、分检、紧急疏散
        'short_term',   -- 3-14天: 安置、基本生活保障
        'recovery'      -- 14天+: 恢复重建、临时住房
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON TYPE operational_v2.response_phase_v2 
    IS '响应阶段: immediate=立即响应(0-72h), short_term=短期救济(3-14d), recovery=恢复重建(14d+)';

-- ============================================================================
-- 2. 创建物资状态枚举
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE operational_v2.supply_condition_v2 AS ENUM (
        'serviceable',   -- 可用
        'damaged',       -- 损坏（可修复）
        'expired',       -- 过期
        'destroyed',     -- 损毁（不可用）
        'quarantined'    -- 隔离检查中
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON TYPE operational_v2.supply_condition_v2 
    IS '物资状态: serviceable=可用, damaged=损坏, expired=过期, destroyed=损毁, quarantined=隔离';

-- ============================================================================
-- 3. 创建气候类型枚举 (影响物资需求计算)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE operational_v2.climate_type_v2 AS ENUM (
        'tropical',     -- 热带: 水需求+20%, 保暖物资-50%
        'temperate',    -- 温带: 标准需求
        'cold',         -- 寒冷: 水需求-20%, 保暖物资+100%
        'arid'          -- 干旱: 水需求+50%
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON TYPE operational_v2.climate_type_v2 
    IS '气候类型: 影响Sphere标准中的物资需求调整系数';

-- ============================================================================
-- 4. 创建缩放基准枚举 (物资需求计算依据)
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE operational_v2.scaling_basis_v2 AS ENUM (
        'per_person',       -- 按总受灾人数
        'per_displaced',    -- 按转移安置人数
        'per_casualty',     -- 按伤亡人数
        'per_trapped',      -- 按被困人数
        'per_area_km2',     -- 按受灾面积(km²)
        'per_team',         -- 按救援队伍数
        'fixed'             -- 固定数量
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

COMMENT ON TYPE operational_v2.scaling_basis_v2 
    IS '物资需求缩放基准: 决定物资数量计算的依据';

-- ============================================================================
-- 5. 创建库存审计表
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.supply_inventory_audit (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 关联
    inventory_id UUID NOT NULL REFERENCES operational_v2.supply_inventory_v2(id) ON DELETE CASCADE,
    
    -- 变更前后值
    old_quantity INTEGER,
    new_quantity INTEGER,
    old_reserved INTEGER,
    new_reserved INTEGER,
    old_condition VARCHAR(20),
    new_condition VARCHAR(20),
    
    -- 变更类型
    change_type VARCHAR(30) NOT NULL,  -- reserve/release/transfer_out/transfer_in/damaged/expired/adjust
    
    -- 变更原因和关联
    change_reason TEXT,
    transfer_id UUID REFERENCES operational_v2.supply_transfers_v2(id),
    event_id UUID,
    scenario_id UUID,
    
    -- 操作人
    changed_by UUID,
    changed_by_name VARCHAR(100),
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_audit_inventory 
    ON operational_v2.supply_inventory_audit(inventory_id);
CREATE INDEX IF NOT EXISTS idx_audit_time 
    ON operational_v2.supply_inventory_audit(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_transfer 
    ON operational_v2.supply_inventory_audit(transfer_id) WHERE transfer_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_type 
    ON operational_v2.supply_inventory_audit(change_type);

COMMENT ON TABLE operational_v2.supply_inventory_audit 
    IS '库存审计表 - 记录所有库存变更的完整历史';

-- ============================================================================
-- 6. 扩展 supply_inventory_v2 表
-- ============================================================================

-- 添加乐观锁版本号
ALTER TABLE operational_v2.supply_inventory_v2 
ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1;

-- 添加物资状态
ALTER TABLE operational_v2.supply_inventory_v2 
ADD COLUMN IF NOT EXISTS condition VARCHAR(20) DEFAULT 'serviceable'
CHECK (condition IN ('serviceable', 'damaged', 'expired', 'destroyed', 'quarantined'));

-- 添加最后盘点时间
ALTER TABLE operational_v2.supply_inventory_v2 
ADD COLUMN IF NOT EXISTS last_audit_at TIMESTAMPTZ;

COMMENT ON COLUMN operational_v2.supply_inventory_v2.version 
    IS '乐观锁版本号，每次更新自动+1';
COMMENT ON COLUMN operational_v2.supply_inventory_v2.condition 
    IS '物资状态: serviceable/damaged/expired/destroyed/quarantined';

-- ============================================================================
-- 7. 扩展 supply_transfers_v2 表
-- ============================================================================

-- 添加响应阶段
ALTER TABLE operational_v2.supply_transfers_v2 
ADD COLUMN IF NOT EXISTS response_phase VARCHAR(20) DEFAULT 'immediate'
CHECK (response_phase IN ('immediate', 'short_term', 'recovery'));

-- 添加紧急程度
ALTER TABLE operational_v2.supply_transfers_v2 
ADD COLUMN IF NOT EXISTS urgency VARCHAR(20) DEFAULT 'normal'
CHECK (urgency IN ('critical', 'urgent', 'normal', 'low'));

COMMENT ON COLUMN operational_v2.supply_transfers_v2.response_phase 
    IS '响应阶段: immediate/short_term/recovery';
COMMENT ON COLUMN operational_v2.supply_transfers_v2.urgency 
    IS '紧急程度: critical=生命攸关, urgent=紧急, normal=常规, low=低优先';

-- ============================================================================
-- 8. 扩展 supplies_v2 表 (物资主数据)
-- ============================================================================

-- 添加缩放基准字段
ALTER TABLE operational_v2.supplies_v2 
ADD COLUMN IF NOT EXISTS scaling_basis VARCHAR(30) DEFAULT 'per_person'
CHECK (scaling_basis IN ('per_person', 'per_displaced', 'per_casualty', 'per_trapped', 'per_area_km2', 'per_team', 'fixed'));

-- 添加 Sphere 品类字段
ALTER TABLE operational_v2.supplies_v2 
ADD COLUMN IF NOT EXISTS sphere_category VARCHAR(20)
CHECK (sphere_category IN ('WASH', 'FOOD', 'SHELTER', 'HEALTH', 'NFI', 'OTHER'));

-- 添加响应阶段适用性
ALTER TABLE operational_v2.supplies_v2 
ADD COLUMN IF NOT EXISTS applicable_phases VARCHAR(50)[] DEFAULT ARRAY['immediate', 'short_term', 'recovery'];

COMMENT ON COLUMN operational_v2.supplies_v2.scaling_basis 
    IS '需求缩放基准: 决定数量计算依据（人/伤员/面积等）';
COMMENT ON COLUMN operational_v2.supplies_v2.sphere_category 
    IS 'Sphere人道主义标准品类: WASH/FOOD/SHELTER/HEALTH/NFI';
COMMENT ON COLUMN operational_v2.supplies_v2.applicable_phases 
    IS '适用的响应阶段数组';

-- ============================================================================
-- 9. 创建审计触发器函数
-- ============================================================================

CREATE OR REPLACE FUNCTION operational_v2.log_inventory_change()
RETURNS TRIGGER AS $$
BEGIN
    -- 只在数量或状态变化时记录
    IF (OLD.quantity IS DISTINCT FROM NEW.quantity) OR 
       (OLD.reserved_quantity IS DISTINCT FROM NEW.reserved_quantity) OR
       (OLD.condition IS DISTINCT FROM NEW.condition) THEN
        
        INSERT INTO operational_v2.supply_inventory_audit (
            inventory_id,
            old_quantity, new_quantity,
            old_reserved, new_reserved,
            old_condition, new_condition,
            change_type,
            created_at
        ) VALUES (
            NEW.id,
            OLD.quantity, NEW.quantity,
            OLD.reserved_quantity, NEW.reserved_quantity,
            OLD.condition, NEW.condition,
            CASE 
                WHEN NEW.reserved_quantity > OLD.reserved_quantity THEN 'reserve'
                WHEN NEW.reserved_quantity < OLD.reserved_quantity THEN 'release'
                WHEN NEW.quantity < OLD.quantity THEN 'transfer_out'
                WHEN NEW.quantity > OLD.quantity THEN 'transfer_in'
                WHEN NEW.condition != OLD.condition THEN 'condition_change'
                ELSE 'adjust'
            END,
            NOW()
        );
    END IF;
    
    -- 自动递增版本号
    NEW.version := OLD.version + 1;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器
DROP TRIGGER IF EXISTS tr_inventory_audit ON operational_v2.supply_inventory_v2;
CREATE TRIGGER tr_inventory_audit
    BEFORE UPDATE ON operational_v2.supply_inventory_v2
    FOR EACH ROW EXECUTE FUNCTION operational_v2.log_inventory_change();

-- ============================================================================
-- 10. 创建 Sphere 标准参考表
-- ============================================================================

CREATE TABLE IF NOT EXISTS operational_v2.sphere_standards_v2 (
    -- 主键
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 标准代码
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    
    -- Sphere 品类
    sphere_category VARCHAR(20) NOT NULL
        CHECK (sphere_category IN ('WASH', 'FOOD', 'SHELTER', 'HEALTH', 'NFI')),
    
    -- 需求量 (每单位基准)
    min_quantity DECIMAL(10, 4) NOT NULL,
    target_quantity DECIMAL(10, 4) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    
    -- 缩放基准
    scaling_basis VARCHAR(30) NOT NULL DEFAULT 'per_person',
    
    -- 适用阶段
    applicable_phases VARCHAR(50)[] NOT NULL DEFAULT ARRAY['immediate', 'short_term', 'recovery'],
    
    -- 气候调整系数 (JSON: {"tropical": 1.2, "cold": 0.8, ...})
    climate_factors JSONB DEFAULT '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    
    -- 参考来源
    reference_source VARCHAR(200) DEFAULT 'Sphere Handbook 2018',
    
    -- 说明
    description TEXT,
    
    -- 时间戳
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sphere_category 
    ON operational_v2.sphere_standards_v2(sphere_category);

COMMENT ON TABLE operational_v2.sphere_standards_v2 
    IS 'Sphere 人道主义最低标准参考表 - 基于 WHO/Sphere Handbook 2018';

-- ============================================================================
-- 11. 初始化 Sphere 标准数据
-- ============================================================================

-- WASH (Water, Sanitation and Hygiene)
INSERT INTO operational_v2.sphere_standards_v2 (
    code, name, sphere_category, min_quantity, target_quantity, unit, 
    scaling_basis, applicable_phases, climate_factors, description
) VALUES 
(
    'SPHERE-WASH-001', '生存用水', 'WASH', 2.5, 3.0, 'liter',
    'per_person', ARRAY['immediate'],
    '{"tropical": 1.2, "temperate": 1.0, "cold": 0.8, "arid": 1.5}',
    'Sphere最低标准: 2.5-3L/人/天用于饮用和食物准备 (立即响应阶段)'
),
(
    'SPHERE-WASH-002', '基本用水', 'WASH', 7.5, 15.0, 'liter',
    'per_person', ARRAY['short_term', 'recovery'],
    '{"tropical": 1.2, "temperate": 1.0, "cold": 0.8, "arid": 1.3}',
    'Sphere标准: 7.5-15L/人/天包括饮用、烹饪和个人卫生'
),
(
    'SPHERE-WASH-003', '厕所/人比', 'WASH', 0.05, 0.05, 'unit',
    'per_person', ARRAY['short_term', 'recovery'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    'Sphere标准: 最大20人共用1个厕所 (0.05个/人)'
)
ON CONFLICT (code) DO NOTHING;

-- FOOD (Food Security and Nutrition)
INSERT INTO operational_v2.sphere_standards_v2 (
    code, name, sphere_category, min_quantity, target_quantity, unit, 
    scaling_basis, applicable_phases, climate_factors, description
) VALUES 
(
    'SPHERE-FOOD-001', '每日热量', 'FOOD', 2100, 2100, 'kcal',
    'per_person', ARRAY['immediate', 'short_term', 'recovery'],
    '{"tropical": 0.95, "temperate": 1.0, "cold": 1.15, "arid": 1.0}',
    'Sphere标准: 2100 kcal/人/天最低能量摄入'
),
(
    'SPHERE-FOOD-002', '干粮配给', 'FOOD', 0.5, 0.6, 'kg',
    'per_person', ARRAY['immediate', 'short_term'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.1, "arid": 1.0}',
    '按2100kcal折算: 约500-600g干粮/人/天'
)
ON CONFLICT (code) DO NOTHING;

-- SHELTER (Shelter and Settlement)
INSERT INTO operational_v2.sphere_standards_v2 (
    code, name, sphere_category, min_quantity, target_quantity, unit, 
    scaling_basis, applicable_phases, climate_factors, description
) VALUES 
(
    'SPHERE-SHELTER-001', '人均居住面积', 'SHELTER', 3.5, 4.5, 'm2',
    'per_displaced', ARRAY['short_term', 'recovery'],
    '{"tropical": 0.9, "temperate": 1.0, "cold": 1.2, "arid": 1.0}',
    'Sphere标准: 最低3.5m²/人有遮盖空间'
),
(
    'SPHERE-SHELTER-002', '帐篷(4人)', 'SHELTER', 0.25, 0.25, 'unit',
    'per_displaced', ARRAY['immediate', 'short_term'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '4人帐篷标准配置: 1顶/4人 = 0.25顶/人'
),
(
    'SPHERE-SHELTER-003', '毛毯/保温毯', 'SHELTER', 1.0, 2.0, 'piece',
    'per_person', ARRAY['immediate', 'short_term'],
    '{"tropical": 0.5, "temperate": 1.0, "cold": 2.0, "arid": 0.8}',
    'Sphere标准: 最低1条/人，寒冷地区2条/人'
)
ON CONFLICT (code) DO NOTHING;

-- HEALTH (Health)
INSERT INTO operational_v2.sphere_standards_v2 (
    code, name, sphere_category, min_quantity, target_quantity, unit, 
    scaling_basis, applicable_phases, climate_factors, description
) VALUES 
(
    'SPHERE-HEALTH-001', '急救包', 'HEALTH', 0.1, 0.1, 'kit',
    'per_casualty', ARRAY['immediate'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '急救包: 每10名伤员1个急救包'
),
(
    'SPHERE-HEALTH-002', '担架', 'HEALTH', 0.02, 0.05, 'unit',
    'per_casualty', ARRAY['immediate'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '担架: 每20-50名伤员1副'
),
(
    'SPHERE-HEALTH-003', '基础药品包', 'HEALTH', 0.001, 0.001, 'kit',
    'per_person', ARRAY['short_term', 'recovery'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '基础药品包: 每1000人1个标准药品包'
)
ON CONFLICT (code) DO NOTHING;

-- NFI (Non-Food Items)
INSERT INTO operational_v2.sphere_standards_v2 (
    code, name, sphere_category, min_quantity, target_quantity, unit, 
    scaling_basis, applicable_phases, climate_factors, description
) VALUES 
(
    'SPHERE-NFI-001', '烹饪套装', 'NFI', 0.2, 0.2, 'set',
    'per_displaced', ARRAY['short_term', 'recovery'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '烹饪套装: 每5人1套 (0.2套/人)'
),
(
    'SPHERE-NFI-002', '卫生用品包', 'NFI', 1.0, 1.0, 'kit',
    'per_person', ARRAY['short_term', 'recovery'],
    '{"tropical": 1.0, "temperate": 1.0, "cold": 1.0, "arid": 1.0}',
    '个人卫生用品包: 每人1套/月'
)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- 12. 创建辅助视图 - 按阶段和品类汇总标准
-- ============================================================================

CREATE OR REPLACE VIEW operational_v2.v_sphere_standards_by_phase AS
SELECT 
    unnest(applicable_phases) AS phase,
    sphere_category,
    code,
    name,
    min_quantity,
    target_quantity,
    unit,
    scaling_basis,
    climate_factors,
    description
FROM operational_v2.sphere_standards_v2
ORDER BY phase, sphere_category, code;

COMMENT ON VIEW operational_v2.v_sphere_standards_by_phase 
    IS '按响应阶段展开的Sphere标准视图';

-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'V15 Sphere Standards Infrastructure migration completed!' AS result;
